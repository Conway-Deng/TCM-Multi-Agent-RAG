from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .registry import experiment, frozen_root, validate_replay_path
from .schemas import FormalRunRequest


APP_ROOT = Path(__file__).resolve().parents[2]


class FormalJobService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    @property
    def replay_root(self) -> Path:
        configured = os.getenv("FORMAL_REPLAY_ROOT", "").strip()
        path = Path(configured) if configured else Path("research/replays")
        resolved = (path if path.is_absolute() else APP_ROOT / path).resolve()
        return validate_replay_path(frozen_root(), resolved)

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
        output = self.replay_root / request.experiment_id / run_id
        output.mkdir(parents=True, exist_ok=False)
        now = time.time()
        job = {
            "run_id": run_id, "experiment_id": request.experiment_id, "run_mode": request.run_mode,
            "status": "queued", "completed": 0, "total": self._total(request, metadata),
            "current_condition": request.condition, "current_case": request.case_id,
            "successful": 0, "failed": 0, "started_at": now, "elapsed_seconds": 0,
            "resume_state": "queued", "replay_output_dir": str(output), "error": None,
            "persistence": "process-local job state; replay files are not guaranteed durable on hosted ephemeral filesystems",
            "_request": request,
        }
        self._write_manifest(output, request, metadata, job)
        with self._lock:
            self._jobs[run_id] = job
        threading.Thread(target=self._run, args=(run_id, request, output), daemon=True, name=run_id).start()
        return self.get(run_id)

    @staticmethod
    def _total(request: FormalRunRequest, metadata: dict[str, Any]) -> int:
        if request.run_mode == "one_case": return 1
        if request.run_mode == "paired": return 2
        return metadata.get("planned_executions", metadata["dataset_size"] * len({item["id"] for item in metadata["conditions"]}))

    @staticmethod
    def _write_manifest(output: Path, request: FormalRunRequest, metadata: dict[str, Any], job: dict[str, Any]) -> None:
        value = {
            "result_origin": "new_replay", "historical_results_modified": False,
            "request": request.model_dump(), "paper_protocol": {key: metadata[key] for key in ("experiment_id", "runner", "dataset_path", "conditions", "models", "provider")},
            "job": {key: value for key, value in job.items() if not key.startswith("_")},
        }
        (output / "replay_manifest.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _run(self, run_id: str, request: FormalRunRequest, output: Path) -> None:
        self._update(run_id, status="running", resume_state="running")
        command = [
            sys.executable, "-m", "formal_experiments.worker", "--experiment", request.experiment_id,
            "--run-mode", request.run_mode, "--frozen-root", str(frozen_root()), "--output", str(output),
        ]
        if request.condition: command.extend(["--condition", request.condition])
        if request.case_id: command.extend(["--case-id", request.case_id])
        env = os.environ.copy(); env["PYTHONPATH"] = str(APP_ROOT / "backend") + os.pathsep + env.get("PYTHONPATH", "")
        try:
            with (output / "worker.stdout.log").open("w", encoding="utf-8") as stdout, (output / "worker.stderr.log").open("w", encoding="utf-8") as stderr:
                completed = subprocess.run(command, cwd=frozen_root(), env=env, stdout=stdout, stderr=stderr, check=False)
            worker = self._worker_status(output)
            if completed.returncode:
                error = (output / "worker.stderr.log").read_text(encoding="utf-8", errors="replace")[-2000:]
                self._update(run_id, **worker, status="failed", resume_state="replay_files_retained", error=error or f"worker exited {completed.returncode}")
            else:
                worker["completed"] = self._jobs[run_id]["total"]
                self._update(run_id, **worker, status="complete", resume_state="complete")
        except Exception as exc:
            self._update(run_id, status="failed", resume_state="replay_files_retained", error=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _worker_status(output: Path) -> dict[str, Any]:
        path = output / "worker_status.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        value = {key: data[key] for key in ("completed", "current_condition", "current_case", "successful", "failed") if key in data}
        progress_paths = [output / "run_progress.json", output / "formal" / "run_progress.json", output / "runtime" / "runtime_state.json"]
        for progress_path in progress_paths:
            if progress_path.exists():
                progress = json.loads(progress_path.read_text(encoding="utf-8"))
                value["completed"] = progress.get("completed_canonical", progress.get("completed", value.get("completed", 0)))
                value["current_condition"] = progress.get("current_condition", value.get("current_condition"))
                value["current_case"] = progress.get("current_question_id", progress.get("current_case", value.get("current_case")))
        for result_path in (output / "results.jsonl", output / "formal_results.jsonl", output / "formal" / "formal_results.jsonl", output / "stage2" / "results.jsonl"):
            if result_path.exists():
                rows = [json.loads(line) for line in result_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                value["completed"] = max(value.get("completed", 0), len(rows))
                value["successful"] = sum(bool(row.get("usable", row.get("run_status") in {"PASS", "PASS_WITH_RETRY"})) for row in rows)
                value["failed"] = len(rows) - value["successful"]
                if rows:
                    value["current_condition"] = rows[-1].get("condition")
                    value["current_case"] = rows[-1].get("case_id", rows[-1].get("question_id"))
        return value

    def _update(self, run_id: str, **values: Any) -> None:
        with self._lock:
            self._jobs[run_id].update(values)

    def get(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            if run_id not in self._jobs: raise KeyError(run_id)
            result = dict(self._jobs[run_id])
        result.update(self._worker_status(Path(result["replay_output_dir"])))
        result["elapsed_seconds"] = round(time.time() - result["started_at"], 3)
        result.pop("started_at", None)
        result.pop("_request", None)
        return result

    def resume(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            if run_id not in self._jobs: raise KeyError(run_id)
            job = self._jobs[run_id]
            if job["status"] not in {"failed"}:
                raise ValueError("Only a failed replay job can be resumed")
            request = job["_request"]
            output = Path(job["replay_output_dir"])
            job.update(status="queued", error=None, resume_state="queued", started_at=time.time())
        threading.Thread(target=self._run, args=(run_id, request, output), daemon=True, name=f"{run_id}-resume").start()
        return self.get(run_id)

    def results(self, run_id: str) -> dict[str, Any]:
        status = self.get(run_id); output = Path(status["replay_output_dir"])
        files = []
        for path in output.rglob("*"):
            if path.is_file() and path.name not in {"worker.stdout.log", "worker.stderr.log"}:
                files.append({"name": str(path.relative_to(output)).replace("\\", "/"), "size": path.stat().st_size})
        rows = []
        for name in ("results.jsonl", "formal_results.jsonl", "formal/formal_results.jsonl"):
            path = output / name
            if path.exists(): rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return {"result_origin": "new_replay", "historical_paper_results": None, "status": status, "results": rows, "downloads": files}

    def file(self, run_id: str, relative_path: str) -> Path:
        output = Path(self.get(run_id)["replay_output_dir"]).resolve()
        candidate = (output / relative_path).resolve()
        if candidate == output or output not in candidate.parents or not candidate.is_file():
            raise ValueError("Replay file not found")
        return candidate


formal_jobs = FormalJobService()
