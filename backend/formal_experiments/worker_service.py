from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .jobs import FormalJobService
from .registry import frozen_root
from .store import FormalJobStore


def resident_memory_mb() -> float:
    """Best-effort RSS instrumentation for the 512 MB worker envelope."""
    try:
        import psutil
        process = psutil.Process()
        rss = process.memory_info().rss
        for child in process.children(recursive=True):
            try:
                rss += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return round(rss / (1024 * 1024), 2)
    except ImportError:  # pragma: no cover - Linux deployment has resource
        try:
            import resource
            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return round(value / 1024, 2)
        except (ImportError, OSError):
            return 0.0


class FormalReplayWorker:
    """Single-concurrency durable worker for formal replays and custom batches."""

    def __init__(
        self,
        store: FormalJobStore | None = None,
        *,
        worker_id: str | None = None,
        poll_seconds: float = 0.25,
        lease_seconds: int = 180,
    ) -> None:
        self.store = store or FormalJobStore()
        self.jobs = FormalJobService(self.store)
        self.worker_id = worker_id or f"experiment-worker-{uuid.uuid4().hex[:10]}"
        self.poll_seconds = max(0.1, poll_seconds)
        self.lease_seconds = max(30, lease_seconds)
        self.active_run_id: str | None = None
        self.peak_rss_mb = resident_memory_mb()
        self._checkpoint_files: dict[str, dict[str, tuple[int, int, str]]] = {}

    def _record_rss(self) -> None:
        self.peak_rss_mb = max(self.peak_rss_mb, resident_memory_mb())

    def _sync_formal(self, job: dict, output: Path) -> list[dict]:
        # Snapshot first. If a process stops between these operations, the
        # restored JSONL is authoritative and rows can be reconstructed.
        known = self._checkpoint_files.setdefault(job["run_id"], {})
        self.store.store_checkpoints(job["run_id"], output, known)
        rows = self.jobs._result_rows(output)
        self.store.replace_executions(job["run_id"], rows)
        status = self.jobs._worker_status(output)
        status.update(status="running", resume_state="checkpointed", current_stage=status.get("current_stage") or "executing")
        self.store.heartbeat(job["run_id"], self.worker_id, self.lease_seconds, **status)
        self._record_rss()
        return rows

    def _run_formal(self, job: dict) -> None:
        from .worker import run_replay

        request = job["request"]
        mutable_environment = (
            "LLM_MODEL", "TCM_CORPUS_MODE", "TCM_CORPUS_PATH", "EMBEDDING_PROVIDER",
            "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "RERANK_PROVIDER", "RERANK_API_KEY",
            "RERANK_MODEL", "RETRIEVAL_ABLATION_EXECUTION",
        )
        previous_environment = {name: os.environ.get(name) for name in mutable_environment}
        with tempfile.TemporaryDirectory(prefix=f"tcm-{job['run_id']}-") as temporary:
            output = Path(temporary) / "replay"
            output.mkdir(parents=True)
            restored = self.store.restore_checkpoints(job["run_id"], output)
            if not restored:
                self.jobs._write_manifest(output, request, job["metadata"], job)
                known = self._checkpoint_files.setdefault(job["run_id"], {})
                self.store.store_checkpoints(job["run_id"], output, known)
            try:
                with ThreadPoolExecutor(max_workers=1, thread_name_prefix="formal-adapter") as executor:
                    future = executor.submit(
                        run_replay,
                        experiment_id=request["experiment_id"],
                        run_mode=request["run_mode"],
                        condition=request.get("condition"),
                        case_id=request.get("case_id"),
                        frozen_root=frozen_root(),
                        output=output,
                    )
                    while not future.done():
                        self._sync_formal(job, output)
                        time.sleep(self.poll_seconds)
                    future.result()
            finally:
                for name, value in previous_environment.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value
                try:
                    from config import get_settings
                    get_settings.cache_clear()
                except ImportError:
                    pass
            self._sync_formal(job, output)
            self.store.store_artifacts(job["run_id"], output)
        rows = self.store.executions(job["run_id"])
        self.store.update(
            job["run_id"],
            status="complete",
            completed=job["total"],
            successful=sum(item["status"] == "Completed" for item in rows),
            failed=sum(item["status"] != "Completed" for item in rows),
            current_stage="complete",
            resume_state="complete",
            error=None,
            lease_until=None,
        )
        self.store.delete_checkpoints(job["run_id"])
        self._checkpoint_files.pop(job["run_id"], None)

    @staticmethod
    def _research_request(request: dict, question: str):
        from schemas.research import ResearchRequest

        fields = {key: value for key, value in request.items() if key != "questions"}
        return ResearchRequest.model_validate({"question": question, **fields})

    def _run_custom(self, job: dict) -> None:
        from orchestration.workbench import ResearchWorkbench

        request = job["request"]
        questions = request["questions"]
        completed_rows = self.store.executions(job["run_id"])
        completed = {int(row["sequence"]) for row in completed_rows}
        successful = sum(row["status"] == "Completed" for row in completed_rows)
        failed = len(completed_rows) - successful
        workbench = ResearchWorkbench(cache_results=False)
        async def execute_questions() -> tuple[int, int]:
            nonlocal successful, failed
            for sequence, question in enumerate(questions, start=1):
                if sequence in completed:
                    continue
                case_id = f"CUSTOM-{sequence:03d}"
                self.store.heartbeat(
                    job["run_id"], self.worker_id, self.lease_seconds,
                    current_stage="running_custom_question", current_case=case_id,
                    completed=len(completed), successful=successful, failed=failed,
                )
                try:
                    result = (await workbench.run(self._research_request(request, question))).model_dump(mode="json")
                    result["question_id"] = case_id
                    result["question"] = question
                    self.store.upsert_execution(job["run_id"], sequence, result)
                    successful += 1
                except Exception as exc:
                    self.store.upsert_execution(job["run_id"], sequence, {
                        "question_id": case_id,
                        "question": question,
                        "condition_id": request["condition_id"],
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    failed += 1
                completed.add(sequence)
                self.store.heartbeat(
                    job["run_id"], self.worker_id, self.lease_seconds,
                    current_stage="persisted_custom_result", current_case=case_id,
                    completed=len(completed), successful=successful, failed=failed,
                )
                self._record_rss()
            return successful, failed

        async def execute_and_close_provider() -> tuple[int, int]:
            try:
                return await execute_questions()
            finally:
                from providers.openai_compatible import OpenAICompatibleLLMProvider
                await OpenAICompatibleLLMProvider.close_shared_http_client()

        successful, failed = asyncio.run(execute_and_close_provider())

        summary = {
            "result_origin": "new_exploratory_run",
            "formal_paper_reproduction": False,
            "scheduled_questions": len(questions),
            "completed": len(completed),
            "successful": successful,
            "failed": failed,
            "specialist_model_targets": request["specialist_model_targets"],
            "consensus_model_target": request["consensus_model_target"],
            "condition_id": request["condition_id"],
            "retrieval_strategy": request["retrieval_strategy"],
        }
        self.store.store_artifact_bytes(
            job["run_id"], "custom_summary.json",
            (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        self.store.update(
            job["run_id"], status="complete", completed=len(completed), successful=successful,
            failed=failed, current_stage="complete", resume_state="complete", error=None, lease_until=None,
        )

    def run_job(self, job: dict) -> None:
        self.active_run_id = job["run_id"]
        try:
            if job.get("job_kind") == "custom":
                self._run_custom(job)
            else:
                self._run_formal(job)
        except Exception as exc:
            self._checkpoint_files.pop(job["run_id"], None)
            self.store.update(
                job["run_id"], status="failed", current_stage="failed",
                resume_state="checkpointed_for_resume", error=f"{type(exc).__name__}: {exc}",
                lease_until=None,
            )
        finally:
            self._record_rss()
            self.active_run_id = None

    def run_once(self) -> bool:
        job = self.store.claim_next(self.worker_id, self.lease_seconds)
        if job is None:
            return False
        self.run_job(job)
        return True

    def run_until_idle(self) -> int:
        processed = 0
        while self.run_once():
            processed += 1
        return processed

    def run_forever(self) -> None:
        while True:
            if not self.run_once():
                time.sleep(self.poll_seconds)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Durable experiment worker (CLI fallback)")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job")
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("FORMAL_WORKER_POLL_SECONDS", "0.25")))
    arguments = parser.parse_args()
    worker = FormalReplayWorker(poll_seconds=arguments.poll_seconds)
    if arguments.once:
        worker.run_once()
    else:
        worker.run_forever()


if __name__ == "__main__":
    main()
