from __future__ import annotations

import csv
import io
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import experiment
from .schemas import CustomRunRequest, FormalRunRequest
from .store import FormalJobStore


APP_ROOT = Path(__file__).resolve().parents[2]


_REPLAY_AGGREGATE_FILES: dict[str, tuple[str, ...]] = {
    "retrieval_ablation": ("stage2/objective_metrics.json",),
    "rq1_architecture": (),
    "rq4_debate": ("objective_metrics.json",),
    "research_b": ("analysis.json",),
    "research_c": ("analysis.json",),
    "a3_v1_3": ("formal/objective_metrics.json",),
}

# Frozen historical access is intentionally limited to these trusted paths.
# Missing RQ1, RQ4 and A3 aggregates are reported as unavailable rather than
# reconstructed from execution rows, smoke outputs, or aborted runs.
_HISTORICAL_AGGREGATE_FILES: dict[str, tuple[str, ...]] = {
    "retrieval_ablation": (
        "research/retrieval_ablation/formal_stage2/stage2_final_results.json",
    ),
    "rq1_architecture": (),
    "rq4_debate": (),
    "research_b": (
        "research/research_b/formal_run_v1/final_analysis/research_b_final_manifest.json",
    ),
    "research_c": (
        "research/research_c/formal_run_v1/research_c_final_results.json",
    ),
    "a3_v1_3": (),
}

_HISTORICAL_UNAVAILABLE_REASONS = {
    "rq1_architecture": "No machine-readable frozen aggregate metric file is available.",
    "rq4_debate": "The frozen manifest exists, but its referenced aggregate metric files are absent.",
    "a3_v1_3": "No completed frozen A3 aggregate exists; smoke validation and aborted runs are excluded.",
}

# Research C aliases are limited to metrics with the same definition in the
# replay analysis and frozen result. No other field names are normalized.
_COMPARABLE_METRICS: dict[str, list[dict[str, str]]] = {
    "retrieval_ablation": [
        {"metric": f"{condition} citation recall", "new_replay": f"{condition}.citation_recall", "historical_paper": f"citation.citation_recall.{condition}"}
        for condition in ("R0", "R3")
    ] + [
        {"metric": f"{condition} citation precision", "new_replay": f"{condition}.citation_precision", "historical_paper": f"citation.citation_precision.{condition}"}
        for condition in ("R0", "R3")
    ] + [
        {"metric": f"{condition} mean generation latency", "new_replay": f"{condition}.mean_latency_ms", "historical_paper": f"latency.generation_latency_ms.{condition}.mean"}
        for condition in ("R0", "R3")
    ],
    "research_b": [
        {"metric": f"{condition} {metric}", "new_replay": f"{condition}.{metric}", "historical_paper": f"{condition.casefold()}_{metric}"}
        for condition in ("J1", "J2") for metric in ("accuracy", "macro_f1")
    ] + [
        {"metric": f"{condition} {label} latency", "new_replay": f"{condition}.{source}", "historical_paper": f"authoritative_latency.{condition}.{target}"}
        for condition in ("J1", "J2")
        for label, source, target in (("mean", "mean_latency_ms", "mean_ms"), ("median", "median_latency_ms", "median_ms"))
    ],
    "research_c": [
        {"metric": f"{condition} {metric}", "new_replay": f"{condition}.{metric}", "historical_paper": f"{condition}.{metric}"}
        for condition in ("K1", "K2") for metric in ("accuracy", "macro_f1")
    ] + [
        {"metric": f"{condition} {label} latency", "new_replay": f"{condition}.{source}", "historical_paper": f"latency.{condition}.{target}"}
        for condition in ("K1", "K2")
        for label, source, target in (("mean", "mean_latency_ms", "mean_ms"), ("median", "median_latency_ms", "median_ms"))
    ] + [
        {"metric": f"{condition} citation coverage", "new_replay": f"{condition}.dual_citation_rate", "historical_paper": f"reliability.{condition}.citation_coverage"}
        for condition in ("K1", "K2")
    ] + [
        {"metric": f"{condition} viewpoint preservation", "new_replay": f"{condition}.dual_viewpoint_rate", "historical_paper": f"reliability.{condition}.viewpoint_preservation"}
        for condition in ("K1", "K2")
    ] + [
        {"metric": f"{condition} uncertainty rate", "new_replay": f"{condition}.uncertainty_rate", "historical_paper": f"reliability.{condition}.uncertainty_rate"}
        for condition in ("K1", "K2")
    ],
}


def _selected_fields(value: Any, names: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {name: value[name] for name in names if name in value}


def _condition_projection(value: Any, conditions: tuple[str, ...], fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        condition: _selected_fields(value.get(condition), fields)
        for condition in conditions
        if isinstance(value, dict) and isinstance(value.get(condition), dict)
    }


def _project_replay_metrics(experiment_id: str, value: dict[str, Any]) -> dict[str, Any]:
    if experiment_id == "retrieval_ablation":
        return _condition_projection(value, ("R0", "R3"), (
            "usable", "total", "usable_rate", "mean_latency_ms", "citation_recall", "citation_precision",
        ))
    if experiment_id == "rq4_debate":
        return _selected_fields(value, ("records",))
    if experiment_id == "research_b":
        metrics = _condition_projection(value, ("J1", "J2"), (
            "accuracy", "macro_f1", "usable", "total", "usable_rate", "mean_latency_ms", "median_latency_ms",
        ))
        metrics.update(_selected_fields(value, (
            "difference_j2_minus_j1", "paired_usable_cases", "paired_accuracy_discordance",
        )))
        return metrics
    if experiment_id == "research_c":
        metrics = _condition_projection(value, ("K1", "K2"), (
            "accuracy", "macro_f1", "usable", "total", "usable_rate", "dual_citation_rate",
            "dual_viewpoint_rate", "uncertainty_rate", "mean_latency_ms", "median_latency_ms",
        ))
        metrics.update(_selected_fields(value, (
            "difference_k2_minus_k1", "paired_usable_cases", "paired_accuracy_discordance",
        )))
        return metrics
    if experiment_id == "a3_v1_3":
        return _selected_fields(value, (
            "canonical_executions", "m1_executions", "m2_executions", "complete_usable_pairs_for_quality",
            "usable_rate", "citation_recall", "citation_precision", "latency_seconds", "provider_by_model",
        ))
    return {}


def _project_historical_metrics(experiment_id: str, value: dict[str, Any]) -> dict[str, Any]:
    if experiment_id == "retrieval_ablation":
        return _selected_fields(value, (
            "status", "primary", "secondary", "retrieval_confirmation", "citation", "latency",
        ))
    if experiment_id == "research_b":
        return _selected_fields(value, (
            "total_executions", "j1_usable", "j2_usable", "j1_accuracy", "j1_macro_f1",
            "j2_accuracy", "j2_macro_f1", "accuracy_diff_j2_minus_j1",
            "macro_f1_diff_j2_minus_j1", "mcnemar_p_value", "authoritative_latency",
        ))
    if experiment_id == "research_c":
        return _selected_fields(value, (
            "K1", "K2", "paired_statistics", "latency", "reliability", "scheduled_executions", "provider_attempts",
        ))
    return {}


def _iso_timestamp(value: float | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def _compact_text(value: Any, limit: int = 280) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = " ".join(value.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _citation_count(text: Any) -> int | None:
    if not isinstance(text, str):
        return None
    return len(set(re.findall(r"\[(tcmv1-[^\]]+)\]", text)))


def _formal_execution_summary(experiment_id: str, row: dict[str, Any]) -> dict[str, Any]:
    """Project exactly one persisted execution into a compact scientific summary."""
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    summary: dict[str, Any] = {
        "sequence": row["sequence"],
        "case_id": row.get("case_id") or result.get("case_id") or result.get("question_id"),
        "condition": row.get("condition") or result.get("condition") or result.get("condition_id") or result.get("retrieval_condition"),
        "status": row.get("status"),
    }

    def include(name: str, value: Any) -> None:
        if value is not None:
            summary[name] = value

    if experiment_id == "retrieval_ablation":
        summary["summary_type"] = "retrieval"
        include("stage", result.get("stage"))
        for metric in ("chunk_recall_at_4", "gold_evidence_recall", "hit_at_4"):
            include(metric, result.get(metric))
        retrieved = result.get("retrieved_ids")
        if not isinstance(retrieved, list):
            retrieved = result.get("retrieved_chunk_ids")
        include("retrieved_count", len(retrieved) if isinstance(retrieved, list) else None)
        citations = result.get("citation_ids")
        include("citation_count", len(citations) if isinstance(citations, list) else None)
        include("answer_excerpt", _compact_text(result.get("answer")))
        include("latency_ms", result.get("retrieval_latency_ms", result.get("latency_ms")))
        include("usable", result.get("usable"))
        include("fallback", result.get("fallback"))
    elif experiment_id == "rq1_architecture":
        summary["summary_type"] = "architecture"
        answer = result.get("full_answer")
        include("answer_excerpt", _compact_text(answer))
        evidence = result.get("retrieved_evidence_ids")
        include("retrieved_count", len(evidence) if isinstance(evidence, list) else None)
        include("citation_count", _citation_count(answer))
        include("provider", result.get("provider"))
        include("model", result.get("model_actually_called") or result.get("model"))
        include("latency_ms", result.get("latency_ms"))
        include("fallback", result.get("fallback"))
        include("usable", result.get("usable"))
    elif experiment_id == "rq4_debate":
        summary["summary_type"] = "debate"
        answer = result.get("full_answer")
        debate = result.get("debate") if isinstance(result.get("debate"), dict) else {}
        include("answer_excerpt", _compact_text(answer))
        include("debate_enabled", debate.get("enabled"))
        evidence = result.get("retrieved_evidence_ids")
        include("retrieved_count", len(evidence) if isinstance(evidence, list) else None)
        include("citation_count", _citation_count(answer))
        include("latency_ms", result.get("latency_ms"))
        include("fallback", result.get("fallback"))
        include("usable", result.get("usable"))
    elif experiment_id == "research_b":
        summary["summary_type"] = "judgment"
        include("prediction", result.get("prediction"))
        include("confidence", result.get("confidence"))
        include("reason_excerpt", _compact_text(result.get("reason")))
        include("usable", result.get("usable"))
        include("latency_ms", result.get("latency_ms"))
    elif experiment_id == "research_c":
        summary["summary_type"] = "conflict"
        include("prediction", result.get("prediction"))
        include("answer_excerpt", _compact_text(result.get("answer")))
        include("preserves_both_viewpoints", result.get("preserves_both_viewpoints"))
        include("cites_both_sources", result.get("cites_both_sources"))
        include("expresses_uncertainty", result.get("expresses_uncertainty"))
        include("confidence", result.get("confidence"))
        include("usable", result.get("usable"))
        include("latency_ms", result.get("latency_ms"))
    elif experiment_id == "a3_v1_3":
        summary["summary_type"] = "multi_model_consensus"
        include("answer_excerpt", _compact_text(result.get("final_answer")))
        include("consensus_model", result.get("consensus_model"))
        citations = result.get("citations") if isinstance(result.get("citations"), dict) else {}
        cited = citations.get("cited_evidence_ids")
        retrieved = citations.get("retrieved_evidence_ids")
        include("citation_count", len(cited) if isinstance(cited, list) else None)
        include("retrieved_count", len(retrieved) if isinstance(retrieved, list) else None)
        include("citation_precision", citations.get("citation_precision"))
        include("citation_recall", citations.get("citation_recall"))
        include("usable", result.get("usable"))
        include("latency_seconds", result.get("total_latency_seconds"))
    else:
        summary["summary_type"] = "execution"
    return summary


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

    def _replay_aggregate(self, run_id: str, experiment_id: str) -> tuple[dict[str, Any], list[str]]:
        metrics: dict[str, Any] = {}
        source_files: list[str] = []
        for name in _REPLAY_AGGREGATE_FILES.get(experiment_id, ()):
            try:
                _, content = self.store.artifact(run_id, name)
                value = json.loads(content)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            projected = _project_replay_metrics(experiment_id, value)
            if projected:
                metrics.update(projected)
                source_files.append(name)
        return metrics, source_files

    @staticmethod
    def _historical_aggregate(experiment_id: str) -> tuple[dict[str, Any], list[str]]:
        metrics: dict[str, Any] = {}
        source_files: list[str] = []
        root = APP_ROOT.resolve()
        for relative in _HISTORICAL_AGGREGATE_FILES.get(experiment_id, ()):
            path = (root / relative).resolve()
            if root != path and root not in path.parents:
                continue
            try:
                value = json.loads(path.read_bytes())
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                continue
            projected = _project_historical_metrics(experiment_id, value)
            if projected:
                metrics.update(projected)
                source_files.append(relative)
        return metrics, source_files

    def experiment_summary(self, run_id: str) -> dict[str, Any]:
        status = self.get(run_id)
        experiment_id = status["experiment_id"]
        replay_metrics, replay_files = self._replay_aggregate(run_id, experiment_id)
        incomplete_note = "Partial replay — aggregate paper metrics are not available from an incomplete run."

        if status["status"] != "complete":
            replay = {
                "availability": "partial",
                "metrics": replay_metrics,
                "source_files": replay_files,
                "note": incomplete_note,
            }
        elif experiment_id == "rq1_architecture":
            replay = {
                "availability": "unavailable",
                "metrics": {},
                "source_files": [],
                "reason": "No aggregate artifact is produced by the current formal replay.",
            }
        elif experiment_id == "rq4_debate" and replay_metrics:
            replay = {
                "availability": "partial",
                "metrics": replay_metrics,
                "source_files": replay_files,
                "note": "Only existing aggregate record metadata is available; per-record scores are not returned or recomputed.",
            }
        elif replay_metrics:
            replay = {
                "availability": "available",
                "metrics": replay_metrics,
                "source_files": replay_files,
            }
        else:
            replay = {
                "availability": "unavailable",
                "metrics": {},
                "source_files": [],
                "reason": "No generated aggregate artifact is available for this replay.",
            }

        historical_metrics, historical_files = self._historical_aggregate(experiment_id)
        if historical_metrics:
            historical = {
                "availability": "available",
                "metrics": historical_metrics,
                "source_files": historical_files,
                "frozen_read_only": True,
            }
        else:
            historical = {
                "availability": "unavailable",
                "metrics": {},
                "source_files": [],
                "frozen_read_only": True,
                "reason": _HISTORICAL_UNAVAILABLE_REASONS.get(
                    experiment_id, "No whitelisted frozen aggregate metric file is available."
                ),
            }

        comparable = _COMPARABLE_METRICS.get(experiment_id, [])
        if replay["availability"] == "available" and historical["availability"] == "available" and comparable:
            comparison = {
                "availability": "partial" if experiment_id == "retrieval_ablation" else "available",
                "comparable_metrics": comparable,
            }
            if experiment_id == "retrieval_ablation":
                comparison["note"] = "Only metrics present in both aggregate artifacts are listed."
        elif replay["availability"] == "partial" and historical["availability"] == "available":
            comparison = {
                "availability": "partial",
                "comparable_metrics": [],
                "note": incomplete_note if status["status"] != "complete" else "Replay paper-level aggregate metrics are incomplete.",
            }
        else:
            comparison = {
                "availability": "unavailable",
                "comparable_metrics": [],
                "reason": "Comparable aggregate metrics are not available from both replay and frozen historical sources.",
            }

        return {
            "experiment_id": experiment_id,
            "run_id": run_id,
            "status": status["status"],
            "new_replay": replay,
            "historical_paper": historical,
            "comparison": comparison,
        }

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

    def result(self, run_id: str, sequence: int) -> dict[str, Any]:
        self.get(run_id)
        return self.store.execution(run_id, sequence)

    def summaries(self, run_id: str, *, after: int = 0, limit: int = 50) -> dict[str, Any]:
        status = self.get(run_id)
        bounded_limit = max(1, min(50, int(limit)))
        rows = self.store.execution_batch(run_id, after=after, limit=bounded_limit + 1)
        page = rows[:bounded_limit]
        metadata = experiment(status["experiment_id"])
        return {
            "status": status,
            "results": [_formal_execution_summary(status["experiment_id"], row) for row in page],
            "next_cursor": int(page[-1]["sequence"]) if page else max(0, after),
            "has_more": len(rows) > bounded_limit,
            "limit": bounded_limit,
            "final_metrics": self.store.final_metrics(run_id),
            "historical_paper_results": metadata.get("historical_result"),
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

    def result_summaries(self, run_id: str, *, after: int = 0) -> dict[str, Any]:
        status = self.get(run_id)
        return {
            "result_origin": "partial_replay_result" if status["status"] == "stopped" else "new_exploratory_run",
            "result_label": "Partial replay result" if status["status"] == "stopped" else "New exploratory result",
            "formal_paper_reproduction": False,
            "status": status,
            "results": self.store.execution_summaries(run_id, after=after),
            "downloads": self.store.artifacts(run_id),
        }

    def result(self, run_id: str, sequence: int) -> dict[str, Any]:
        self.get(run_id)
        return self.store.execution(run_id, sequence)

    def file(self, run_id: str, relative_path: str) -> tuple[str, bytes]:
        self.get(run_id)
        return self.store.artifact(run_id, relative_path)


custom_jobs = CustomJobService()
