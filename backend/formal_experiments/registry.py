from __future__ import annotations

import os
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[2]


def frozen_root() -> Path:
    configured = os.getenv("FORMAL_EXPERIMENT_ROOT", "").strip()
    path = Path(configured) if configured else APP_ROOT
    return (path if path.is_absolute() else APP_ROOT / path).resolve()


def validate_replay_path(root: Path, path: Path) -> Path:
    """Permit repository writes only under research/replays; external persistent roots remain valid."""
    root = root.resolve()
    path = path.resolve()
    deployed_replays = (root / "research/replays").resolve()
    if (path == root or root in path.parents) and path != deployed_replays and deployed_replays not in path.parents:
        raise ValueError("FORMAL_REPLAY_ROOT must not target deployed source or frozen artifact directories")
    return path


def _full_runs_enabled() -> bool:
    return _cloud_worker_ready() or any(
        os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}
        for name in ("FORMAL_DURABLE_JOBS_ENABLED", "FORMAL_ALLOW_FULL_BENCHMARK")
    )


def _provider_ready() -> bool:
    direct_provider = (
        os.getenv("LLM_PROVIDER", "").strip().casefold() == "siliconflow"
        and bool(os.getenv("LLM_API_KEY", "").strip())
    )
    return direct_provider or _cloud_worker_ready()


def _cloud_worker_ready() -> bool:
    return bool(
        os.getenv("FORMAL_WORKER_PUBLIC_URL", "").strip()
        and os.getenv("FORMAL_DATABASE_URL", "").strip()
    )


def verify_deployment_integrity(root: Path, experiment_id: str) -> tuple[bool, list[str]]:
    manifest_path = root / "research/formal_assets_deployment_manifest.json"
    if not manifest_path.exists():
        return False, ["research/formal_assets_deployment_manifest.json"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        paths = manifest["experiments"][experiment_id]["assets"]
        records = {item["path"]: item for item in manifest["assets"]}
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False, ["invalid deployment manifest"]
    errors = []
    for relative in paths:
        record = records.get(relative); path = root / relative
        if record is None or not path.is_file():
            errors.append(relative + " (missing)"); continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record.get("sha256") or path.stat().st_size != record.get("bytes"):
            errors.append(relative + " (hash mismatch)")
    return not errors, errors


EXPERIMENTS: list[dict[str, Any]] = [
    {
        "experiment_id": "retrieval_ablation",
        "number": "01",
        "title": "Retrieval Ablation",
        "research_question": "How does retrieval strategy affect evidence recall and downstream quality?",
        "paper_label": "Retrieval study · selection and confirmation",
        "dataset": "TCM Gold RQ1 Confirmatory v1.1 (frozen)",
        "dataset_size": 100,
        "planned_executions": 520,
        "conditions": [
            {"id": "R0", "name": "Lexical", "stage": "selection"},
            {"id": "R1", "name": "Dense", "stage": "selection"},
            {"id": "R2", "name": "Hybrid", "stage": "selection"},
            {"id": "R3", "name": "Hybrid + rerank", "stage": "selection"},
            {"id": "R0", "name": "Lexical", "stage": "confirmation"},
            {"id": "R3", "name": "Hybrid + rerank", "stage": "confirmation"},
        ],
        "models": ["Qwen/Qwen3-8B (confirmation only)"],
        "provider": "SiliconFlow embeddings/reranker in selection; SiliconFlow Qwen in confirmation",
        "retrieval": "Stage 1: R0/R1/R2/R3; Stage 2: paired R0/R3",
        "architecture": "C1 in confirmation",
        "consensus_model": None,
        "primary_metrics": ["Full Recall", "Any-Hit Recall", "MRR", "nDCG", "citation recall", "latency"],
        "what_changes": "Retrieval strategy; confirmation compares R0 with selected R3.",
        "what_stays_fixed": "Frozen corpus, benchmark split, top-k and confirmation model.",
        "why": "Measure retrieval effects before and after downstream generation.",
        "runner": "research/retrieval_ablation/runner.py + stage2_runner.py",
        "dataset_path": "research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1_frozen.jsonl",
        "required_paths": ["research/retrieval_ablation/runner.py", "research/retrieval_ablation/stage2_runner.py", "research/retrieval_ablation/selection_manifest.json"],
        "online_run_modes": [], "local_run_modes": ["full_benchmark"],
    },
    {
        "experiment_id": "rq1_architecture",
        "number": "02", "title": "Architecture Comparison",
        "research_question": "Does ordinary Multi-Agent improve over Single-RAG?",
        "paper_label": "RQ1 · C1 vs C2 confirmatory study",
        "dataset": "TCM Gold RQ1 Confirmatory v1.1 (frozen)", "dataset_size": 100,
        "planned_executions": 200,
        "conditions": [{"id": "C1", "name": "Single-RAG"}, {"id": "C2", "name": "Ordinary Multi-Agent"}],
        "models": ["Qwen/Qwen3-8B"], "provider": "SiliconFlow", "retrieval": "R0 · lexical", "architecture": "Paired C1/C2", "consensus_model": "Qwen/Qwen3-8B for C2",
        "primary_metrics": ["evidence recall", "citation recall", "semantic support", "usability", "latency"],
        "what_changes": "C1 single generation versus C2 independent specialist aggregation.", "what_stays_fixed": "Same 100 questions, R0 evidence, Qwen model and run settings.", "why": "Isolate the architecture effect.",
        "runner": "research/experiment_pipeline/rq1_confirmatory.py", "dataset_path": "research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1_frozen.jsonl",
        "required_paths": ["research/experiment_pipeline/rq1_confirmatory.py", "research/experiments/rq1_c1_vs_c2/confirmatory_protocol/rq1_confirmatory.yaml", "research/formal_runtime/rq4_backend/orchestration/workbench.py"], "online_run_modes": ["one_case", "paired"], "local_run_modes": ["full_benchmark"],
    },
    {
        "experiment_id": "rq4_debate",
        "number": "03", "title": "Same-Model Debate", "research_question": "Does adding structured debate improve Multi-Agent performance?", "paper_label": "RQ4 / A2 · C2 vs C4",
        "dataset": "TCM Gold RQ4 v1 (frozen)", "dataset_size": 100, "conditions": [{"id": "C2", "name": "Ordinary Multi-Agent"}, {"id": "C4", "name": "Same-model structured Debate"}],
        "planned_executions": 200,
        "models": ["Qwen/Qwen3-8B"], "provider": "SiliconFlow", "retrieval": "R0 · lexical", "architecture": "Paired C2/C4; one debate round", "consensus_model": "Qwen/Qwen3-8B",
        "primary_metrics": ["Full Recall", "citation recall", "usability", "latency", "semantic support"],
        "what_changes": "C4 adds the frozen critique, revision and consensus stages.", "what_stays_fixed": "Frozen 100-question benchmark, R0, Qwen and evidence.", "why": "Isolate same-model structured debate.",
        "runner": "research/experiment_pipeline/rq4_platform.py", "dataset_path": "research/benchmarks/tcm_gold_rq4_v1/benchmark_rq4_v1_frozen.jsonl",
        "required_paths": ["research/experiment_pipeline/rq4_platform.py", "research/experiments/rq4_debate_vs_multiagent/protocol/protocol_manifest.json", "research/formal_runtime/rq4_backend/orchestration/workbench.py", "research/formal_runtime/rq4_backend/orchestration/genuine_debate.py"], "online_run_modes": ["one_case", "paired"], "local_run_modes": ["full_benchmark"],
    },
    {
        "experiment_id": "research_b", "number": "04", "title": "Evidence-Aware Judging", "research_question": "Does giving the judge reviewed evidence improve classification?", "paper_label": "Research B · J1 vs J2",
        "dataset": "Research B v1 frozen judge cases", "dataset_size": 240,
        "planned_executions": 480,
        "conditions": [{"id": "J1", "name": "Claim only"}, {"id": "J2", "name": "Claim + reviewed evidence"}],
        "labels": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED"], "models": ["Qwen/Qwen3-8B"], "provider": "SiliconFlow", "retrieval": "Frozen reviewed evidence embedded in J2 cases", "architecture": "LLM-as-a-Judge classification", "consensus_model": None,
        "primary_metrics": ["accuracy", "macro-F1", "confusion matrix", "usability", "latency"],
        "what_changes": "J1 sees the claim only; J2 sees the same claim plus reviewed evidence.", "what_stays_fixed": "Same 240 cases, label space, Qwen model and provider settings.", "why": "Measure the effect of evidence access on source-grounded judging.",
        "runner": "research/research_b/runner.py", "dataset_path": "research/research_b/benchmark/research_b_v1_frozen.jsonl", "required_paths": ["research/research_b/runner.py", "research/research_b/config/research_b_judge.json", "research/research_b/benchmark/freeze_manifest_v1.json"], "online_run_modes": ["one_case", "paired"], "local_run_modes": ["full_benchmark"],
    },
    {
        "experiment_id": "research_c", "number": "05", "title": "Conflict Governance", "research_question": "Does conflict-aware governance improve transparency and conflict handling?", "paper_label": "Research C · K1 vs K2",
        "dataset": "Research C v1 frozen conflict cases (including 12 authentic direct-conflict cases)", "dataset_size": 132,
        "planned_executions": 264,
        "conditions": [{"id": "K1", "name": "Standard source-grounded answering without explicit conflict instructions"}, {"id": "K2", "name": "Conflict-aware answering requiring conflict identification, dual viewpoint preservation, and citation"}],
        "models": ["Qwen/Qwen3-8B"], "provider": "SiliconFlow", "retrieval": "Two frozen source excerpts per case", "architecture": "Paired conflict classification and response", "consensus_model": None,
        "primary_metrics": ["macro-F1", "citation coverage", "viewpoint preservation", "uncertainty signalling", "latency"],
        "what_changes": "K2 adds explicit conflict identification, dual-viewpoint preservation and citation instructions.", "what_stays_fixed": "Same 132 cases, source excerpts, Qwen and provider settings.", "why": "Measure whether explicit governance improves transparent conflict handling.",
        "runner": "research/research_c/runner.py", "dataset_path": "research/research_c/benchmark/research_c_v1_frozen.jsonl", "required_paths": ["research/research_c/runner.py", "research/research_c/config/research_c_conflict.json", "research/research_c/benchmark/freeze_manifest_v1.json"], "online_run_modes": ["one_case", "paired"], "local_run_modes": ["full_benchmark"],
    },
    {
        "experiment_id": "a3_v1_3", "number": "06", "title": "Multi-Model Debate", "research_question": "What changes when homogeneous Qwen debate is replaced by a tested heterogeneous Qwen + GLM + DeepSeek configuration?", "paper_label": "A3 v1.3 · M1 vs M2",
        "dataset": "TCM Gold RQ4 v1 frozen benchmark", "dataset_size": 100,
        "planned_executions": 200,
        "conditions": [{"id": "M1", "name": "Homogeneous · Qwen + Qwen + Qwen"}, {"id": "M2", "name": "Heterogeneous · Qwen + GLM + DeepSeek"}],
        "models": ["Qwen/Qwen3-8B", "THUDM/GLM-Z1-9B-0414", "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"], "provider": "SiliconFlow", "retrieval": "Frozen R0 evidence mapping", "architecture": "3 initial + 3 critique + 3 revision + 1 consensus calls per condition", "consensus_model": "Qwen/Qwen3-8B",
        "primary_metrics": ["Full Recall", "citation precision/recall", "usability", "latency", "provider reliability"],
        "what_changes": "M1 uses Qwen in all specialist seats; M2 applies the frozen cyclic Qwen/GLM/DeepSeek role rotation.", "what_stays_fixed": "Benchmark, roles, evidence mapping, topology, prompts and Qwen consensus.", "why": "Compare homogeneous and heterogeneous debate under the frozen A3 protocol.",
        "runner": "research/multi_model_debate/formal_runner.py", "dataset_path": "research/benchmarks/tcm_gold_rq4_v1/benchmark_rq4_v1_frozen.jsonl", "required_paths": ["research/multi_model_debate/formal_runner.py", "research/multi_model_debate/execution_plan.json", "research/multi_model_debate/role_rotation_manifest.json", "research/multi_model_debate/frozen_evidence_manifest.json"], "online_run_modes": ["one_case", "paired"], "local_run_modes": ["full_benchmark"],
    },
]


def public_registry() -> list[dict[str, Any]]:
    root = frozen_root()
    result = deepcopy(EXPERIMENTS)
    for item in result:
        missing = [path for path in item.pop("required_paths") if not (root / path).exists()]
        integrity_ok, integrity_errors = verify_deployment_integrity(root, item["experiment_id"])
        item["paper_protocol_locked"] = True
        item["scheduled_executions"] = item["planned_executions"]
        item["historical_results_label"] = "Historical paper result"
        item["replay_results_label"] = "New replay result"
        item["historical_result"] = {
            "label": "Historical paper result",
            "status": "frozen_read_only",
            "questions": item["dataset_size"],
            "scheduled_executions": item["planned_executions"],
            "historical_results_modified": False,
        }
        item["artifact_root_configured"] = not missing and integrity_ok
        item["hash_verification"] = "PASS" if integrity_ok else "FAIL"
        item["provider_configured"] = _provider_ready()
        item["integrity_errors"] = integrity_errors
        item["missing_artifacts"] = missing
        online = item.pop("online_run_modes")
        local = item.pop("local_run_modes")
        cloud_worker = _cloud_worker_ready()
        item["run_capabilities"] = {
            mode: {
                "state": "READY ONLINE" if mode in online or (mode == "full_benchmark" and mode in local and cloud_worker) else "LOCAL FULL REPLAY" if mode in local else "UNAVAILABLE",
                "reason": "" if mode in online or (mode == "full_benchmark" and mode in local and cloud_worker) else "Requires the durable experiment worker." if mode in local else "The frozen protocol does not expose this mode.",
            }
            for mode in ("one_case", "paired", "full_benchmark")
        }
        if missing or not integrity_ok:
            item["available_run_modes"] = []
            details = missing or integrity_errors
            item["disabled_reason"] = "Formal asset integrity verification failed: " + ", ".join(details)
            item["run_capabilities"] = {
                mode: {"state": "UNAVAILABLE", "reason": item["disabled_reason"]}
                for mode in ("one_case", "paired", "full_benchmark")
            }
        elif not item["provider_configured"]:
            item["available_run_modes"] = []
            item["disabled_reason"] = "Frozen protocol requires the configured SiliconFlow provider and LLM_API_KEY."
            item["run_capabilities"] = {
                mode: {"state": "UNAVAILABLE", "reason": item["disabled_reason"]}
                for mode in ("one_case", "paired", "full_benchmark")
            }
        else:
            item["available_run_modes"] = online + (local if _full_runs_enabled() else [])
    return result


def experiment(experiment_id: str) -> dict[str, Any]:
    for item in public_registry():
        if item["experiment_id"] == experiment_id:
            return item
    raise KeyError(experiment_id)
