from __future__ import annotations

import csv
import io
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import experiment
from .schemas import CustomRunRequest, FormalRunRequest
from .store import FormalJobStore


APP_ROOT = Path(__file__).resolve().parents[2]


def _iso_timestamp(value: float | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def persist_partial_report(store: FormalJobStore, run_id: str) -> dict[str, Any]:
    """Create truthful exports from completed rows only; no frozen result is read or changed."""
    job = store.get(run_id)
    rows = store.executions(run_id, include_payload=True)
    by_condition: dict[str, dict[str, int]] = {}
    for row in rows:
        condition = str(row.get("condition") or "unknown")
        counts = by_condition.setdefault(condition, {"completed": 0, "successful": 0, "failed": 0})
        counts["completed"] += 1
        counts["successful" if row.get("status") == "Completed" else "failed"] += 1
    warning = "Partial replay — not directly comparable to the complete paper result."
    report = {
        "result_origin": "partial_replay_result",
        "label": "Partial replay result",
        "warning": warning,
        "experiment_name": job["metadata"].get("title") or job["metadata"].get("experiment_id", job["experiment_id"]),
        "run_id": run_id,
        "job_kind": job.get("job_kind", "formal"),
        "original_scheduled_execution_count": job["total"],
        "completed_execution_count": len(rows),
        "stop_timestamp": _iso_timestamp(job.get("stopped_at") or time.time()),
        "conditions": job["metadata"].get("conditions", [job.get("current_condition")]),
        "models": job["metadata"].get("models") or {
            "specialists": job["request"].get("specialist_model_targets"),
            "consensus": job["request"].get("consensus_model_target"),
        },
        "protocol": {
            "run_mode": job["run_mode"],
            "runner": job["metadata"].get("runner"),
            "dataset_path": job["metadata"].get("dataset_path"),
            "request": job["request"],
        },
        "descriptive_metrics_completed_rows_only": {
            "completed": len(rows),
            "successful": sum(row.get("status") == "Completed" for row in rows),
            "failed": sum(row.get("status") != "Completed" for row in rows),
            "by_condition": by_condition,
        },
        "completed_rows": rows,
    }
    json_bytes = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer)
    writer.writerow(["sequence", "case_id", "condition", "status", "result_json"])
    for row in rows:
        writer.writerow([
            row.get("sequence"), row.get("case_id"), row.get("condition"), row.get("status"),
            json.dumps(row.get("result", {}), ensure_ascii=False, separators=(",", ":")),
        ])
    markdown_rows = "\n".join(
        f"| {row.get('sequence')} | {str(row.get('case_id') or '—').replace('|', '\\|')} | {str(row.get('condition') or '—').replace('|', '\\|')} | {row.get('status')} |"
        for row in rows
    ) or "| — | — | — | No completed executions |"
    markdown = (
        f"# Partial replay result\n\n"
        f"- Experiment: {report['experiment_name']}\n"
        f"- Run ID: {run_id}\n"
        f"- Completed: {len(rows)} / {job['total']} executions\n"
        f"- Stopped: {report['stop_timestamp']}\n\n"
        f"> {warning}\n\n"
        "## Protocol metadata\n\n"
        f"- Run mode: {job['run_mode']}\n"
        f"- Conditions: {json.dumps(report['conditions'], ensure_ascii=False)}\n"
        f"- Models: {json.dumps(report['models'], ensure_ascii=False)}\n"
        f"- Runner: {report['protocol']['runner'] or 'Custom Workbench provider layer'}\n"
        f"- Dataset: {report['protocol']['dataset_path'] or 'User-supplied Custom questions'}\n\n"
        "## Descriptive metrics (completed rows only)\n\n"
        f"- Successful: {report['descriptive_metrics_completed_rows_only']['successful']}\n"
        f"- Failed: {report['descriptive_metrics_completed_rows_only']['failed']}\n\n"
        "## Completed executions\n\n"
        "| Sequence | Case | Condition | Status |\n"
        "|---:|---|---|---|\n"
        f"{markdown_rows}\n\n"
        "The accompanying JSON and CSV files contain the complete persisted payload for every row listed above.\n"
    )
    store.store_artifact_bytes(run_id, "partial_report.md", markdown.encode("utf-8"), "text/markdown")
    store.store_artifact_bytes(run_id, "partial_results.csv", csv_buffer.getvalue().encode("utf-8-sig"), "text/csv")
    store.store_artifact_bytes(run_id, "partial_results.json", json_bytes, "application/json")
    return report


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
            for key in ("experiment_id", "title", "runner", "dataset_path", "conditions", "models", "provider", "planned_executions", "dataset_size")
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
        value["stop_requested"] = bool(value.pop("cancellation_requested", False))
        for key in ("request", "metadata", "created_at", "started_at", "updated_at", "worker_id", "lease_until"):
            value.pop(key, None)
        return value

    def stop(self, run_id: str) -> dict[str, Any]:
        value = self.store.request_stop(run_id)
        if value["status"] == "stopped":
            persist_partial_report(self.store, run_id)
        return self.get(run_id)

    def resume(self, run_id: str) -> dict[str, Any]:
        self.store.request_resume(run_id)
        return self.get(run_id)

    def results(self, run_id: str, *, after: int = 0) -> dict[str, Any]:
        status = self.get(run_id)
        metadata = experiment(status["experiment_id"])
        return {
            "result_origin": "partial_replay_result" if status["status"] == "stopped" else "new_replay",
            "result_label": "Partial replay result" if status["status"] == "stopped" else "New replay result",
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
            "title": "Custom Research Workbench",
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
            "stop_requested_at", "stopped_at",
        }
        result = {key: value[key] for key in keep if key in value}
        result["stop_requested"] = bool(value.get("cancellation_requested"))
        return result

    def stop(self, run_id: str) -> dict[str, Any]:
        value = self.store.request_stop(run_id)
        if value["status"] == "stopped":
            persist_partial_report(self.store, run_id)
        return self.get(run_id)

    def results(self, run_id: str, *, after: int = 0) -> dict[str, Any]:
        status = self.get(run_id)
        return {
            "result_origin": "partial_replay_result" if status["status"] == "stopped" else "new_exploratory_run",
            "result_label": "Partial replay result" if status["status"] == "stopped" else "New exploratory result",
            "formal_paper_reproduction": False,
            "status": status,
            "results": self.store.executions(run_id, after=after, include_payload=True),
            "final_metrics": self.store.final_metrics(run_id),
            "downloads": self.store.artifacts(run_id),
        }

    def file(self, run_id: str, relative_path: str) -> tuple[str, bytes]:
        self.get(run_id)
        return self.store.artifact(run_id, relative_path)


custom_jobs = CustomJobService()
