from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .registry import experiment
from .schemas import CustomRunRequest, FormalRunRequest
from .store import FormalJobStore


APP_ROOT = Path(__file__).resolve().parents[2]


class FormalJobService:
    """Durable API facade; execution belongs to the separate worker service."""

    def __init__(self, store: FormalJobStore | None = None) -> None:
        self.store = store or FormalJobStore()

    def create(self, request: FormalRunRequest) -> dict[str, Any]:
        metadata = experiment(request.experiment_id)
        if request.run_mode not in metadata["available_run_modes"]:
            capability = metadata.get("run_capabilities", {}).get(request.run_mode, {})
            reason = metadata.get("disabled_reason") or capability.get("reason") or f"{request.run_mode} is not supported by the frozen runner"
            raise ValueError(reason)
        valid_conditions = [item["id"] for item in metadata["conditions"]]
        if request.condition and request.condition not in valid_conditions:
            raise ValueError("Condition is not part of this paper protocol")
        run_id = f"replay-{request.experiment_id}-{uuid.uuid4().hex[:12]}"
        replay_workspace = f"{request.experiment_id}/{run_id}"
        now = time.time()
        job = {
            "run_id": run_id,
            "job_kind": "formal",
            "experiment_id": request.experiment_id,
            "run_mode": request.run_mode,
            "status": "queued",
            "completed": 0,
            "total": self._total(request, metadata),
            "current_stage": "queued",
            "current_condition": request.condition,
            "current_case": request.case_id,
            "successful": 0,
            "failed": 0,
            "created_at": now,
            "started_at": None,
            "updated_at": now,
            "resume_state": "queued",
            "replay_output_dir": replay_workspace,
            "persistence": "PostgreSQL source of truth; execution is performed by a separate cloud worker",
            "error": None,
        }
        request_value = request.model_dump(mode="json")
        metadata_value = {
            key: metadata[key]
            for key in ("experiment_id", "runner", "dataset_path", "conditions", "models", "provider", "planned_executions", "dataset_size")
        }
        self.store.create(job, request_value, metadata_value)
        return self.get(run_id)

    @staticmethod
    def _total(request: FormalRunRequest, metadata: dict[str, Any]) -> int:
        if request.run_mode == "one_case":
            return 1
        if request.run_mode == "paired":
            return 2
        return metadata.get("planned_executions", metadata["dataset_size"] * len({item["id"] for item in metadata["conditions"]}))

    @staticmethod
    def _write_manifest(output: Path, request: dict[str, Any], metadata: dict[str, Any], job: dict[str, Any]) -> None:
        value = {
            "result_origin": "new_replay",
            "historical_results_modified": False,
            "request": request,
            "paper_protocol": metadata,
            "job": job,
        }
        (output / "replay_manifest.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _result_rows(output: Path) -> list[dict[str, Any]]:
        candidates = (
            output / "results.jsonl",
            output / "formal_results.jsonl",
            output / "formal" / "formal_results.jsonl",
            output / "stage1" / "results.jsonl",
            output / "stage2" / "results.jsonl",
        )
        rows: list[dict[str, Any]] = []
        for path in candidates:
            if path.exists():
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        # A polling read may overlap the writer's final append. The next poll sees the complete row.
                        continue
        return rows

    @staticmethod
    def _worker_status(output: Path) -> dict[str, Any]:
        path = output / "worker_status.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        value = {key: data[key] for key in ("completed", "current_stage", "current_condition", "current_case", "successful", "failed") if key in data}
        progress_paths = [output / "run_progress.json", output / "formal" / "run_progress.json", output / "runtime" / "runtime_state.json"]
        for progress_path in progress_paths:
            if progress_path.exists():
                progress = json.loads(progress_path.read_text(encoding="utf-8"))
                value["completed"] = progress.get("completed_canonical", progress.get("completed", value.get("completed", 0)))
                if progress.get("stage"):
                    value["current_stage"] = progress["stage"]
                value["current_condition"] = progress.get("current_condition", value.get("current_condition"))
                value["current_case"] = progress.get("current_question_id", progress.get("current_case", value.get("current_case")))
        rows = FormalJobService._result_rows(output)
        if rows:
            value["completed"] = max(value.get("completed", 0), len(rows))
            value["successful"] = sum(FormalJobService._row_completed(row) for row in rows)
            value["failed"] = len(rows) - value["successful"]
            value["current_condition"] = rows[-1].get("condition", rows[-1].get("condition_id"))
            value["current_case"] = rows[-1].get("case_id", rows[-1].get("question_id"))
        return value

    @staticmethod
    def _row_completed(row: dict[str, Any]) -> bool:
        if "usable" in row:
            return bool(row["usable"])
        if "run_status" in row:
            return row["run_status"] in {"PASS", "PASS_WITH_RETRY"}
        return not bool(row.get("error"))

    def get(self, run_id: str) -> dict[str, Any]:
        value = self.store.get(run_id)
        for key in ("request", "metadata", "created_at", "started_at", "updated_at", "worker_id", "lease_until"):
            value.pop(key, None)
        return value

    def resume(self, run_id: str) -> dict[str, Any]:
        self.store.request_resume(run_id)
        return self.get(run_id)

    def results(self, run_id: str, *, after: int = 0) -> dict[str, Any]:
        status = self.get(run_id)
        metadata = experiment(status["experiment_id"])
        return {
            "result_origin": "new_replay",
            "historical_paper_results": metadata.get("historical_result"),
            "status": status,
            "results": self.store.executions(run_id, after=after),
            "final_metrics": self.store.final_metrics(run_id),
            "downloads": self.store.artifacts(run_id),
        }

    def file(self, run_id: str, relative_path: str) -> tuple[str, bytes]:
        self.get(run_id)
        return self.store.artifact(run_id, relative_path)


formal_jobs = FormalJobService()


class CustomJobService:
    """Control-plane facade for exploratory batches executed by the worker."""

    def __init__(self, store: FormalJobStore | None = None) -> None:
        self.store = store or FormalJobStore()

    def create(self, request: CustomRunRequest) -> dict[str, Any]:
        run_id = f"custom-{uuid.uuid4().hex[:16]}"
        now = time.time()
        job = {
            "run_id": run_id,
            "job_kind": "custom",
            "experiment_id": "custom_workbench",
            "run_mode": "custom_batch",
            "status": "queued",
            "completed": 0,
            "total": len(request.questions),
            "current_stage": "queued",
            "current_condition": request.condition_id.value,
            "current_case": None,
            "successful": 0,
            "failed": 0,
            "created_at": now,
            "started_at": None,
            "updated_at": now,
            "resume_state": "queued",
            "replay_output_dir": f"custom/{run_id}",
            "persistence": "durable PostgreSQL queue/results; execution is performed by the cloud worker",
            "error": None,
        }
        metadata = {
            "result_origin": "new_exploratory_run",
            "formal_paper_reproduction": False,
            "question_count": len(request.questions),
        }
        self.store.create(job, request.model_dump(mode="json"), metadata)
        return self.get(run_id)

    def get(self, run_id: str) -> dict[str, Any]:
        value = self.store.get(run_id)
        if value.get("job_kind") != "custom":
            raise KeyError(run_id)
        keep = {
            "run_id", "status", "completed", "total", "current_stage", "current_case",
            "successful", "failed", "elapsed_seconds", "resume_state", "persistence", "error",
        }
        return {key: value[key] for key in keep if key in value}

    def results(self, run_id: str, *, after: int = 0) -> dict[str, Any]:
        return {
            "result_origin": "new_exploratory_run",
            "formal_paper_reproduction": False,
            "status": self.get(run_id),
            "results": self.store.executions(run_id, after=after, include_payload=True),
            "final_metrics": self.store.final_metrics(run_id),
            "downloads": self.store.artifacts(run_id),
        }

    def file(self, run_id: str, relative_path: str) -> tuple[str, bytes]:
        self.get(run_id)
        return self.store.artifact(run_id, relative_path)


custom_jobs = CustomJobService()
