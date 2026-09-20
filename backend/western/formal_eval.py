from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
from time import perf_counter
from typing import Any, Awaitable, Callable, Iterable

from config.settings import get_settings
from providers import ProviderBundle, build_llm_provider, get_provider_bundle
from providers.openai_compatible import ProviderUnavailable
from providers.siliconflow import SiliconFlowEmbeddingProvider, SiliconFlowRerankProvider
from retrieval.engine import RetrievalEngine, _expanded_topics
from schemas.research import RetrievalItem, RetrievalStrategy

from .agent import (
    SYSTEM_PROMPT,
    WESTERN_EVIDENCE_EXCERPT_CHARS,
    WESTERN_MAX_TOKENS,
    WESTERN_MODEL,
    WESTERN_TIMEOUT_SECONDS,
    _generation_prompt,
    _validated_answer,
)
from .benchmark import load_benchmark
from .corpus import load_runtime_corpus, sha256_file
from .formal_judge import (
    FormalJudgeOutput,
    JUDGE_SYSTEM_PROMPT,
    build_judge_prompt,
    checkable_claim_counts,
    normalize_judge_json_envelope,
    parse_judge_output,
)
from .schemas import WesternRetrievalEvidence, WesternTopic


PROTOCOL_VERSION = "western_formal_v0.1.2"
SUPERSEDED_PROTOCOL_VERSION = "western_formal_v0.1.1"
ORIGINAL_PROTOCOL_VERSION = "western-formal-v0.1"
BENCHMARK_VERSION = "western-pilot-v0.1"
BENCHMARK_SHA256 = "29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6"
BENCHMARK_MANIFEST_SHA256 = "bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae"
CORPUS_CHUNKS_SHA256 = "8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b"
SOURCE_REGISTRY_SHA256 = "722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703"
RUNTIME_COMMIT = "e6b02f6e37534008427cb18cd06ce7f086153103"
BENCHMARK_COMMIT = "bc1b389bdb6c4eb0c5c4c629af549a6904a37477"
FINAL_TOP_K = 4
CANDIDATE_DEPTH = 12
RRF_CONSTANT = 60
GENERATOR_PROVIDER = "siliconflow"
GENERATOR_MODEL = "Qwen/Qwen3-8B"
GENERATOR_TEMPERATURE = 0.0
GENERATOR_MAX_TOKENS = 256
GENERATOR_TIMEOUT_SECONDS = 120.0
JUDGE_PROVIDER = "siliconflow"
JUDGE_MODEL = "THUDM/GLM-Z1-9B-0414"
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1200
JUDGE_TIMEOUT_SECONDS = 120.0
INTENDED_CASES = 48
INTENDED_CELLS = 192
RETRYABLE_ERROR_TYPES = frozenset({"connectivity", "http_5xx", "timeout", "malformed_response"})
CONDITIONS = ("R0", "R1", "R2", "R3")
ORIGINAL_PROTOCOL_COMMIT = "c1a8d0658fc334d70f50d6b688de5b40bf0f99a6"
ORIGINAL_PROTOCOL_SHA256 = "f7ff69020dac14491569b1764aef1bd0638e9dd15717af6ca16d75835cf35ec5"
V0_1_1_PROTOCOL_COMMIT = "46cfb8d8edf89dfeb1af7abf2701b273583cf188"
V0_1_1_PROTOCOL_SHA256 = "a91f855f5707e07efeb7e460f11e2290f6fb5c282da942ab9b9b4f75360e77c8"
PROTOCOL_SHA256 = "af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192"
STAGE_A_CHECKPOINT_COMMIT = "5eb40146f026b42547220b0f0cfd077d72a75562"
STAGE_A_RUN_ID = "western-formal-v0.1.2-stage-a-20260918-01"
STAGE_A_RETRIEVAL_SHA256 = "91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e"
STAGE_B_EXECUTION_VERSION = "western-stage-b-execution-v0.1.2"
STAGE_B_EXECUTION_RELATIVE_PATH = "research/experiments/western_formal_v0_1/stage_b_execution_v0_1_2/execution.json"
ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT = "7da777984bc6a3ffef0e0514598848142788e474"
ORIGINAL_STAGE_B_EXECUTION_JSON_SHA256 = "852db6dad8dcd2b79eb9fcc26b5858504ed5881ec605272e8cacc7ca27355092"
ORIGINAL_STAGE_B_SHA256 = "89b1e4166daefa738be4572f84825711336147560945a93141b6a7569d61166f"
ORIGINAL_STAGE_B_SEAL_MANIFEST_SHA256 = "29ffec35f6e0f80a6543935b4ab248aefb8a8387f1ed392d2657cd5445feecb0"
ORIGINAL_STAGE_B_EXECUTION_MANIFEST_SHA256 = "68d1435270c1b882f866042e644f71a2f21156dbfcafa061314a2759d5712939"
STAGE_B_REPEAT_RUN_ID = "western-formal-v0.1.2-stage-b-r1-20260919-01"
STAGE_B_REPEAT_EXECUTION_VERSION = "western-stage-b-repeat-execution-v0.1.2-r1"
STAGE_B_REPEAT_EXECUTION_RELATIVE_PATH = "research/experiments/western_formal_v0_1/stage_b_repeat_execution_v0_1_2_r1/execution.json"
STAGE_B_REPEAT_INCIDENT_RELATIVE_PATH = "research/experiments/western_formal_v0_1/stage_b_repeat_execution_v0_1_2_r1/incident.json"
STAGE_B_READINESS_PROMPT = "Return exactly the word READY."
STAGE_B_READINESS_PROBES = 3
STAGE_B_READINESS_INTERVAL_SECONDS = 10
STAGE_B_READINESS_MAX_TOKENS = 16
STAGE_B_REPEAT_OUTAGE_MIN_SUFFIX = 20
STAGE_B_REPEAT_INFRASTRUCTURE_ERRORS = frozenset({"connectivity", "timeout", "http_5xx", "malformed_response", "rate_limit"})
STAGE_C_RUN_ID = "western-formal-v0.1.2-stage-c-r2-20260920-01"
STAGE_C_EXECUTION_VERSION = "western-stage-c-execution-v0.1.2-r2"
STAGE_C_EXECUTION_RELATIVE_PATH = "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_2_r2/execution.json"
STAGE_C_ANALYSIS_RELATIVE_PATH = "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_2_r2/analysis.json"
STAGE_C_OUTPUT_NORMALIZATION_VERSION = "western-judge-json-envelope-v1"
SUPERSEDED_STAGE_C_EXECUTION_VERSION = "western-stage-c-execution-v0.1.2-r1"
SUPERSEDED_STAGE_C_FREEZE_COMMIT = "c376635432f985bce31ce43be91a94c0243ca1a6"
STAGE_C_AMENDMENT_REASON = "pre-execution synthetic integration test observed single outer Markdown JSON fence"
STAGE_C_R2_EXECUTION_FREEZE_COMMIT = "8e0d4960b70af7694a0664c83fb79342f03685fa"
STAGE_C_R2_EXECUTION_JSON_SHA256 = "39a6fae2e6b1f7fdb29c35adb657c7abf752f22e6e0371fdb891372f456d08f4"
STAGE_C_R2_EXECUTION_MANIFEST_SHA256 = "46ba83acf2c651b51f0c6cd0f8122ebcb153f73c4a34dac8254a14f9a1280082"
STAGE_C_R2_JUDGMENTS_SHA256 = "fd3544854e4eadfbb498cf9ab5329cee0fb45a03380b25b2c82fabef03ed5363"
STAGE_C_R2_REPORTED_SNAPSHOT = {
    "row_count": 33, "completed": 0, "output_schema_failure": 16, "technical_failure": 17,
}
STAGE_C_R2_PRESERVED_COUNTS = {
    "row_count": 39, "completed": 0, "output_schema_failure": 19, "technical_failure": 20,
    "timeout_final_error": 20,
}
PRIMARY_STAGE_B_SHA256 = "afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c"
PRIMARY_STAGE_B_SEAL_SHA256 = "45a740077fe25f08c996779c272bfdff2a9e4d06b1703f0de5ce3c3dbf3a480c"
PRIMARY_STAGE_B_GENERATION_METRICS_SHA256 = "1bbaf4ca1befa92c552c06e1914ea370ffc992fb4163671768ba3ae9813446f9"
PRIMARY_STAGE_B_PROVIDER_METRICS_SHA256 = "a3d7011ec3bab16ff4a01b733f9a01498e09660943c6e7be69bf7cfe5db224c6"
PRIMARY_STAGE_B_EXECUTION_MANIFEST_SHA256 = "97b6ec0fdd7d9fab81e932caee317032e9040663e55841f57b36256f107d2acc"
PRIMARY_STAGE_B_READINESS_MANIFEST_SHA256 = "cc54c6b5d06e6025f09ce240b80b8a707f5d2beb7252ec8a7c41a665e69d25fb"
PRIMARY_STAGE_B_INCIDENT_MANIFEST_SHA256 = "5ad53525a1457d0c280947cd2e0778bf396d34a597bf845e99f4f48aa3f1fdd7"
PRIMARY_STAGE_B_RUN_MANIFEST_SHA256 = "32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511"
STAGE_C_OUTCOMES = frozenset({
    "completed", "technical_failure", "rate_limit", "nonretryable_provider_failure",
    "output_schema_failure", "truncated_response",
    "upstream_retrieval_technical_failure", "upstream_generation_failure",
})


class FatalFormalRunError(RuntimeError):
    """A protocol or implementation defect that must leave the run unsealed."""


RETRIEVAL_CONDITIONS: dict[str, dict[str, Any]] = {
    "R0": {
        "implementation": "RetrievalEngine BM25-like lexical scoring",
        "provider": "local deterministic",
        "model": "BM25-like lexical baseline",
        "candidate_depth": None,
        "fusion_method": None,
        "rerank_depth": None,
        "final_top_k": FINAL_TOP_K,
    },
    "R1": {
        "implementation": "RetrievalEngine dense cosine similarity",
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "candidate_depth": "all topic-filtered corpus chunks",
        "fusion_method": None,
        "rerank_depth": None,
        "final_top_k": FINAL_TOP_K,
    },
    "R2": {
        "implementation": "RetrievalEngine reciprocal-rank fusion of lexical and dense rankings",
        "provider": "local lexical + siliconflow dense",
        "model": "BM25-like lexical + BAAI/bge-m3",
        "candidate_depth": "all topic-filtered corpus chunks",
        "fusion_method": f"RRF: 1/({RRF_CONSTANT}+lexical_rank) + 1/({RRF_CONSTANT}+dense_rank)",
        "rerank_depth": None,
        "final_top_k": FINAL_TOP_K,
    },
    "R3": {
        "implementation": "RetrievalEngine hybrid RRF candidates followed by remote reranking",
        "provider": "siliconflow",
        "model": "BAAI/bge-m3 + BAAI/bge-reranker-v2-m3",
        "candidate_depth": CANDIDATE_DEPTH,
        "fusion_method": f"RRF with constant {RRF_CONSTANT}",
        "rerank_depth": CANDIDATE_DEPTH,
        "final_top_k": FINAL_TOP_K,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen_inputs(repository_root: Path) -> dict[str, str]:
    benchmark_root = repository_root / "research/benchmarks/western_pilot_v0_1"
    corpus_root = repository_root / "research/corpus/west_v0_1"
    actual = {
        "benchmark_sha256": _sha256(benchmark_root / "benchmark.jsonl"),
        "manifest_sha256": _sha256(benchmark_root / "benchmark_manifest.json"),
        "corpus_chunks_sha256": _sha256(corpus_root / "chunks.jsonl"),
        "source_registry_sha256": _sha256(corpus_root / "source_registry.json"),
    }
    expected = {
        "benchmark_sha256": BENCHMARK_SHA256,
        "manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
        "source_registry_sha256": SOURCE_REGISTRY_SHA256,
    }
    mismatches = {key: {"expected": expected[key], "actual": value} for key, value in actual.items() if value != expected[key]}
    if mismatches:
        raise RuntimeError(f"Frozen input mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return actual


def verify_amended_protocol(repository_root: Path) -> dict[str, str]:
    actual = verify_frozen_inputs(repository_root)
    protocol_path = repository_root / "research/experiments/western_formal_v0_1/protocol_v0_1_2/protocol.json"
    protocol_sha256 = _sha256(protocol_path)
    if protocol_sha256 != PROTOCOL_SHA256:
        raise FatalFormalRunError(
            f"Amended protocol hash mismatch: expected {PROTOCOL_SHA256}, actual {protocol_sha256}"
        )
    actual["protocol_sha256"] = protocol_sha256
    return actual


def _git_head(repository_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository_root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def _git_worktree_clean(repository_root: Path) -> bool:
    output = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repository_root, check=True, capture_output=True, text=True,
    ).stdout
    return not output.strip()


def resolve_protocol_freeze_commit(repository_root: Path) -> str:
    relative = "research/experiments/western_formal_v0_1/protocol_v0_1_2/protocol.json"
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", relative],
        cwd=repository_root, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not commit:
        raise FatalFormalRunError("The v0.1.2 protocol freeze commit does not exist")
    return commit


def resolve_stage_b_execution_freeze_commit(repository_root: Path) -> str:
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", STAGE_B_EXECUTION_RELATIVE_PATH],
        cwd=repository_root, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not commit:
        raise FatalFormalRunError("The Stage B execution freeze commit does not exist")
    return commit


def resolve_stage_b_repeat_execution_freeze_commit(repository_root: Path) -> str:
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", STAGE_B_REPEAT_EXECUTION_RELATIVE_PATH],
        cwd=repository_root, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not commit:
        raise FatalFormalRunError("The Stage B repeat execution freeze commit does not exist")
    return commit


def resolve_stage_c_execution_freeze_commit(repository_root: Path) -> str:
    commit = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", STAGE_C_EXECUTION_RELATIVE_PATH],
        cwd=repository_root, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if not commit:
        raise FatalFormalRunError("The Stage C execution freeze commit does not exist")
    return commit


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FatalFormalRunError(f"{label} is unreadable or invalid JSON") from exc
    if not isinstance(value, dict):
        raise FatalFormalRunError(f"{label} must be a JSON object")
    return value


def _read_jsonl_strict(path: Path, *, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("row is not an object")
            rows.append(value)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise FatalFormalRunError(f"{label} contains invalid JSONL") from exc
    return rows


def _stage_b_execution_config(repository_root: Path) -> dict[str, Any]:
    path = repository_root / STAGE_B_EXECUTION_RELATIVE_PATH
    return _load_json_object(path, label="Stage B execution freeze")


def verify_stage_b_execution_freeze(
    repository_root: Path,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verify_amended_protocol(repository_root)
    config = execution_config or _stage_b_execution_config(repository_root)
    freeze_commit = expected_execution_commit or resolve_stage_b_execution_freeze_commit(repository_root)
    head = _git_head(repository_root)
    if head != freeze_commit:
        raise FatalFormalRunError(f"Stage B requires execution freeze HEAD {freeze_commit}; current HEAD is {head}")
    if require_clean_worktree and not _git_worktree_clean(repository_root):
        raise FatalFormalRunError("Stage B requires a clean Git working tree")
    expected = {
        "execution_version": STAGE_B_EXECUTION_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_run_id": STAGE_A_RUN_ID,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "benchmark_sha256": BENCHMARK_SHA256,
        "benchmark_manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
        "source_registry_sha256": SOURCE_REGISTRY_SHA256,
    }
    mismatches = {key: {"expected": value, "actual": config.get(key)} for key, value in expected.items() if config.get(key) != value}
    implementation = config.get("implementation_sha256")
    if not isinstance(implementation, dict) or not implementation:
        mismatches["implementation_sha256"] = {"expected": "non-empty mapping", "actual": implementation}
    else:
        for relative, expected_hash in implementation.items():
            path = repository_root / str(relative)
            actual_hash = _sha256(path) if path.is_file() else None
            if actual_hash != expected_hash:
                mismatches[f"implementation_sha256.{relative}"] = {"expected": expected_hash, "actual": actual_hash}
    if mismatches:
        raise FatalFormalRunError(f"Stage B execution freeze mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return {**config, "execution_freeze_commit": freeze_commit, "execution_json_sha256": _sha256(repository_root / STAGE_B_EXECUTION_RELATIVE_PATH) if execution_config is None else hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def _stage_b_repeat_execution_config(repository_root: Path) -> dict[str, Any]:
    return _load_json_object(
        repository_root / STAGE_B_REPEAT_EXECUTION_RELATIVE_PATH,
        label="Stage B repeat execution freeze",
    )


def _stage_b_repeat_incident_config(repository_root: Path) -> dict[str, Any]:
    return _load_json_object(
        repository_root / STAGE_B_REPEAT_INCIDENT_RELATIVE_PATH,
        label="Stage B outage incident freeze",
    )


def _canonical_json_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _expected_readiness_policy() -> dict[str, Any]:
    return {
        "provider": GENERATOR_PROVIDER,
        "model": GENERATOR_MODEL,
        "prompt": STAGE_B_READINESS_PROMPT,
        "probe_count": STAGE_B_READINESS_PROBES,
        "interval_seconds": STAGE_B_READINESS_INTERVAL_SECONDS,
        "timeout_seconds": GENERATOR_TIMEOUT_SECONDS,
        "temperature": GENERATOR_TEMPERATURE,
        "max_tokens": STAGE_B_READINESS_MAX_TOKENS,
        "required_normalized_text": "READY",
        "all_probes_must_pass": True,
        "formal_data": False,
        "single_use_for_repeat_start": True,
        "must_precede_repeat_execution_manifest": True,
    }


def _expected_repeat_failure_policy() -> dict[str, Any]:
    return {
        "automatically_authorized_repeats": 1,
        "cell_retry_policy_unchanged": True,
        "selective_regeneration_after_seal": False,
        "third_attempt_automatically_authorized": False,
        "outage_minimum_consecutive_suffix": STAGE_B_REPEAT_OUTAGE_MIN_SUFFIX,
        "outage_final_error_types": sorted(STAGE_B_REPEAT_INFRASTRUCTURE_ERRORS),
        "outage_requires_no_subsequent_success": True,
    }


def _validate_stage_b_incident_freeze(config: dict[str, Any]) -> None:
    expected = {
        "status": "stage_b_outage_incident",
        "run_id": STAGE_A_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "stage_b_execution_freeze_commit": ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT,
        "stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "stage_b_seal_manifest_sha256": ORIGINAL_STAGE_B_SEAL_MANIFEST_SHA256,
        "stage_b_execution_manifest_sha256": ORIGINAL_STAGE_B_EXECUTION_MANIFEST_SHA256,
        "cell_count": INTENDED_CELLS,
        "completed_count": 106,
        "technical_failure_count": 86,
        "first_failure_position": 107,
        "first_failed_experiment_id": "western_formal_v0.1.2:westbench-v0.1-headache-03:R0",
        "consecutive_failure_suffix_count": 86,
        "successes_after_first_failure": 0,
        "retry_used_failure_count": 86,
        "attempt_count_two_failure_count": 86,
        "provider_reported_model": GENERATOR_MODEL,
        "provider_reported_model_count": INTENDED_CELLS,
        "eligible_as_primary": False,
        "eligible_for_stage_c": False,
        "preservation_only": True,
        "decision_basis": "operational_failure_metadata_only",
        "standard_b_finalized": False,
        "stage_c_executed": False,
    }
    mismatches = {key: {"expected": value, "actual": config.get(key)} for key, value in expected.items() if config.get(key) != value}
    if config.get("final_error_counts") != {"connectivity": 86}:
        mismatches["final_error_counts"] = {"expected": {"connectivity": 86}, "actual": config.get("final_error_counts")}
    if config.get("first_error_counts") != {"connectivity": 85, "timeout": 1}:
        mismatches["first_error_counts"] = {"expected": {"connectivity": 85, "timeout": 1}, "actual": config.get("first_error_counts")}
    if config.get("failure_counts_by_condition") != {"R0": 22, "R1": 22, "R2": 21, "R3": 21}:
        mismatches["failure_counts_by_condition"] = {"expected": {"R0": 22, "R1": 22, "R2": 21, "R3": 21}, "actual": config.get("failure_counts_by_condition")}
    if mismatches:
        raise FatalFormalRunError(f"Stage B incident freeze mismatch: {json.dumps(mismatches, sort_keys=True)}")


def verify_stage_b_repeat_execution_freeze(
    repository_root: Path,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    incident_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verify_amended_protocol(repository_root)
    config = execution_config or _stage_b_repeat_execution_config(repository_root)
    incident = incident_config or _stage_b_repeat_incident_config(repository_root)
    _validate_stage_b_incident_freeze(incident)
    freeze_commit = expected_execution_commit or resolve_stage_b_repeat_execution_freeze_commit(repository_root)
    head = _git_head(repository_root)
    if head != freeze_commit:
        raise FatalFormalRunError(f"Stage B repeat requires execution freeze HEAD {freeze_commit}; current HEAD is {head}")
    if require_clean_worktree and not _git_worktree_clean(repository_root):
        raise FatalFormalRunError("Stage B repeat requires a clean Git working tree")
    incident_sha = (
        _sha256(repository_root / STAGE_B_REPEAT_INCIDENT_RELATIVE_PATH)
        if incident_config is None else _canonical_json_sha256(incident)
    )
    expected = {
        "execution_version": STAGE_B_REPEAT_EXECUTION_VERSION,
        "repeat_run_id": STAGE_B_REPEAT_RUN_ID,
        "repeat_ordinal": 1,
        "repeat_reason": "provider_outage",
        "repeat_scope": "all_192_cells",
        "reuse_original_successes": False,
        "primary_semantic_dataset": True,
        "scientific_protocol_unchanged": True,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_run_id": STAGE_A_RUN_ID,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "supersedes_stage_b_attempt_run_id": STAGE_A_RUN_ID,
        "superseded_stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "benchmark_sha256": BENCHMARK_SHA256,
        "benchmark_manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
        "source_registry_sha256": SOURCE_REGISTRY_SHA256,
        "provider": GENERATOR_PROVIDER,
        "model": GENERATOR_MODEL,
        "temperature": GENERATOR_TEMPERATURE,
        "max_tokens": GENERATOR_MAX_TOKENS,
        "timeout_seconds": GENERATOR_TIMEOUT_SECONDS,
        "incident_sha256": incident_sha,
        "readiness_policy": _expected_readiness_policy(),
        "repeat_failure_policy": _expected_repeat_failure_policy(),
    }
    mismatches = {key: {"expected": value, "actual": config.get(key)} for key, value in expected.items() if config.get(key) != value}
    implementation = config.get("implementation_sha256")
    if not isinstance(implementation, dict) or not implementation:
        mismatches["implementation_sha256"] = {"expected": "non-empty mapping", "actual": implementation}
    else:
        for relative, expected_hash in implementation.items():
            path = repository_root / str(relative)
            actual_hash = _sha256(path) if path.is_file() else None
            if actual_hash != expected_hash:
                mismatches[f"implementation_sha256.{relative}"] = {"expected": expected_hash, "actual": actual_hash}
    implementation_commit = config.get("implementation_commit")
    if not isinstance(implementation_commit, str) or len(implementation_commit) != 40:
        mismatches["implementation_commit"] = {"expected": "40-character Commit 1 SHA", "actual": implementation_commit}
    elif execution_config is None:
        parent = subprocess.run(
            ["git", "rev-parse", f"{freeze_commit}^"], cwd=repository_root,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if parent != implementation_commit:
            mismatches["implementation_commit"] = {"expected": parent, "actual": implementation_commit}
    if mismatches:
        raise FatalFormalRunError(f"Stage B repeat execution freeze mismatch: {json.dumps(mismatches, sort_keys=True)}")
    execution_sha = (
        _sha256(repository_root / STAGE_B_REPEAT_EXECUTION_RELATIVE_PATH)
        if execution_config is None else _canonical_json_sha256(config)
    )
    return {
        **config,
        "execution_freeze_commit": freeze_commit,
        "execution_json_sha256": execution_sha,
        "incident_json_sha256": incident_sha,
    }


def _expected_stage_c_analysis_plan() -> dict[str, Any]:
    return {
        "analysis_version": "western-stage-c-analysis-v0.1.2-r1",
        "protocol_version": PROTOCOL_VERSION,
        "w_rq2": {
            "population": "42 evidence-answerable cases",
            "case_count": 42,
            "primary_endpoint": "per_answer_full_evidence_point_coverage",
            "definition": "covered expected evidence points / total frozen expected evidence points for that answer",
            "condition_summary": "macro_mean_across_endpoint_defined_answers",
            "comparisons": ["R1-R0", "R2-R0", "R3-R0"],
            "effect_estimate": "case_paired_mean_difference",
            "confidence_interval": "paired_percentile_bootstrap_95_percent",
            "bootstrap_resamples": 10000,
            "bootstrap_seed": 20260815,
            "primary_binary_significance_decision": False,
            "key_secondary_endpoint": "unsupported_claim_presence_per_answer",
            "key_secondary_test": "exact_two_sided_mcnemar",
            "key_secondary_multiplicity": "holm_across_three_r0_comparisons_only",
            "secondary_endpoints": [
                "unsupported_claim_count", "claim_support_rate",
                "partially_supported_claim_rate", "unsupported_claim_rate",
                "evidence_point_partial_coverage", "evidence_point_contradiction_rate",
                "partially_supported_case_scope_fields", "observable_safety_scope_flags",
            ],
            "clinical_safety_composite": False,
        },
        "missingness": {
            "generation_technical": "exclude_from_semantic_denominators_and_report_separately",
            "judge_technical": "exclude_from_semantic_denominators_and_report_separately",
            "semantic": "report_undefined_endpoint_and_never_score_as_zero",
            "pairwise_population": "successful_pair_intersection_for_specific_endpoint",
            "imputation": "none",
            "pool_original_outage_attempt": False,
            "shared_complete_case_denominator": False,
        },
        "w_rq3": {
            "population": "six insufficient cases analyzed separately",
            "case_count": 6,
            "successful_outcomes": [
                "appropriate_abstention", "appropriate_bounded_insufficiency",
                "substantive_answer_without_insufficiency_acknowledgement",
                "overclaim_beyond_pilot_evidence",
            ],
            "not_applicable_allowed_for_success": False,
            "hypothesis_tests": "none",
        },
    }


def _stage_c_scientific_sha256(repository_root: Path) -> dict[str, str]:
    protocol_root = repository_root / "research/experiments/western_formal_v0_1/protocol_v0_1_2"
    benchmark_root = repository_root / "research/benchmarks/western_pilot_v0_1"
    corpus_root = repository_root / "research/corpus/west_v0_1"
    return {
        "protocol_json": _sha256(protocol_root / "protocol.json"),
        "judge_schema_json": _sha256(protocol_root / "judge_schema.json"),
        "metric_definitions_md": _sha256(protocol_root / "metric_definitions.md"),
        "failure_policy_md": _sha256(protocol_root / "failure_policy.md"),
        "benchmark_jsonl": _sha256(benchmark_root / "benchmark.jsonl"),
        "benchmark_manifest_json": _sha256(benchmark_root / "benchmark_manifest.json"),
        "corpus_chunks_jsonl": _sha256(corpus_root / "chunks.jsonl"),
        "source_registry_json": _sha256(corpus_root / "source_registry.json"),
        "canonical_judge_system_prompt": hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "canonical_formal_judge_output_schema": _canonical_json_sha256(FormalJudgeOutput.model_json_schema()),
    }


def verify_stage_c_execution_freeze(
    repository_root: Path,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    analysis_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verify_amended_protocol(repository_root)
    execution_path = repository_root / STAGE_C_EXECUTION_RELATIVE_PATH
    analysis_path = repository_root / STAGE_C_ANALYSIS_RELATIVE_PATH
    config = execution_config or _load_json_object(execution_path, label="Stage C execution freeze")
    analysis = analysis_config or _load_json_object(analysis_path, label="Stage C analysis freeze")
    if analysis != _expected_stage_c_analysis_plan():
        raise FatalFormalRunError("Stage C analysis freeze does not match the preregistered plan")
    analysis_sha = _sha256(analysis_path) if analysis_config is None else _canonical_json_sha256(analysis)
    freeze_commit = expected_execution_commit or resolve_stage_c_execution_freeze_commit(repository_root)
    head = _git_head(repository_root)
    if head != freeze_commit:
        raise FatalFormalRunError(f"Stage C requires execution freeze HEAD {freeze_commit}; current HEAD is {head}")
    if require_clean_worktree and not _git_worktree_clean(repository_root):
        raise FatalFormalRunError("Stage C requires a clean Git working tree")
    expected = {
        "execution_version": STAGE_C_EXECUTION_VERSION,
        "stage_c_run_id": STAGE_C_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_run_id": STAGE_A_RUN_ID,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "primary_stage_b_run_id": STAGE_B_REPEAT_RUN_ID,
        "primary_stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        "primary_stage_b_seal_manifest_sha256": PRIMARY_STAGE_B_SEAL_SHA256,
        "primary_stage_b_raw_sha256": PRIMARY_STAGE_B_SHA256,
        "primary_stage_b_execution_manifest_sha256": PRIMARY_STAGE_B_EXECUTION_MANIFEST_SHA256,
        "primary_stage_b_readiness_manifest_sha256": PRIMARY_STAGE_B_READINESS_MANIFEST_SHA256,
        "primary_stage_b_incident_manifest_sha256": PRIMARY_STAGE_B_INCIDENT_MANIFEST_SHA256,
        "primary_stage_b_run_manifest_sha256": PRIMARY_STAGE_B_RUN_MANIFEST_SHA256,
        "repeat_execution_freeze_commit": "d68df8018798219b2bcf8dd36ee067dedbf66dfc",
        "repeat_execution_json_sha256": "de06ad2c834c287fa0d6715c45c56c26147fdc9ee697f68d7fa2d78a314e2617",
        "provider": JUDGE_PROVIDER,
        "model": JUDGE_MODEL,
        "temperature": JUDGE_TEMPERATURE,
        "max_tokens": JUDGE_MAX_TOKENS,
        "timeout_seconds": JUDGE_TIMEOUT_SECONDS,
        "enable_thinking": False,
        "intended_cell_count": INTENDED_CELLS,
        "analysis_sha256": analysis_sha,
        "scientific_sha256": _stage_c_scientific_sha256(repository_root),
        "outcome_enum": sorted(STAGE_C_OUTCOMES),
        "normalization_policy_version": STAGE_C_OUTPUT_NORMALIZATION_VERSION,
        "normalization_contract": {
            "accepted_envelopes": ["raw_json", "single_outer_json_markdown_fence", "single_outer_unlabelled_markdown_fence"],
            "operation": "remove_only_one_complete_outer_markdown_fence_before_strict_json_and_schema_validation",
            "retry_consumed": False,
            "semantic_values_modified": False,
        },
        "superseded_stage_c_execution_version": SUPERSEDED_STAGE_C_EXECUTION_VERSION,
        "superseded_stage_c_freeze_commit": SUPERSEDED_STAGE_C_FREEZE_COMMIT,
        "amendment_reason": STAGE_C_AMENDMENT_REASON,
        "formal_stage_c_cells_before_amendment": 0,
    }
    mismatches = {key: {"expected": value, "actual": config.get(key)} for key, value in expected.items() if config.get(key) != value}
    implementation = config.get("implementation_sha256")
    if not isinstance(implementation, dict) or not implementation:
        mismatches["implementation_sha256"] = {"expected": "non-empty mapping", "actual": implementation}
    else:
        for relative, expected_hash in implementation.items():
            path = repository_root / str(relative)
            actual_hash = _sha256(path) if path.is_file() else None
            if actual_hash != expected_hash:
                mismatches[f"implementation_sha256.{relative}"] = {"expected": expected_hash, "actual": actual_hash}
    implementation_commit = config.get("implementation_commit")
    if not isinstance(implementation_commit, str) or len(implementation_commit) != 40:
        mismatches["implementation_commit"] = {"expected": "40-character Commit 1 SHA", "actual": implementation_commit}
    elif execution_config is None:
        parent = subprocess.run(
            ["git", "rev-parse", f"{freeze_commit}^"], cwd=repository_root,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if parent != implementation_commit:
            mismatches["implementation_commit"] = {"expected": parent, "actual": implementation_commit}
    if mismatches:
        raise FatalFormalRunError(f"Stage C execution freeze mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return {
        **config,
        "execution_freeze_commit": freeze_commit,
        "execution_json_sha256": _sha256(execution_path) if execution_config is None else _canonical_json_sha256(config),
        "analysis_json_sha256": analysis_sha,
    }


def load_frozen_cases(repository_root: Path) -> list[dict[str, Any]]:
    cases, errors = load_benchmark(repository_root / "research/benchmarks/western_pilot_v0_1/benchmark.jsonl")
    if errors:
        raise RuntimeError(f"Frozen benchmark parse failure: {errors}")
    if len(cases) != INTENDED_CASES:
        raise RuntimeError(f"Expected {INTENDED_CASES} frozen cases, found {len(cases)}")
    return cases


def experiment_id(case_id: str, retrieval_condition: str) -> str:
    if retrieval_condition not in CONDITIONS:
        raise ValueError(f"Unknown retrieval condition: {retrieval_condition}")
    return f"{PROTOCOL_VERSION}:{case_id}:{retrieval_condition}"


def balanced_execution_order(cases: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    order: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases):
        rotation = CONDITIONS[case_index % len(CONDITIONS):] + CONDITIONS[:case_index % len(CONDITIONS)]
        for within_case_index, condition in enumerate(rotation):
            order.append({
                "sequence": len(order) + 1,
                "case_index": case_index + 1,
                "within_case_index": within_case_index + 1,
                "case_id": case["case_id"],
                "retrieval_condition": condition,
                "experiment_id": experiment_id(case["case_id"], condition),
            })
    if len(order) != INTENDED_CELLS or len({row["experiment_id"] for row in order}) != INTENDED_CELLS:
        raise RuntimeError("Balanced execution order did not produce 192 unique cells")
    return order


def load_frozen_execution_order(repository_root: Path, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = repository_root / "research/experiments/western_formal_v0_1/protocol_v0_1_2/execution_order.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cells = payload.get("cells")
    expected = balanced_execution_order(cases)
    if payload.get("cell_count") != INTENDED_CELLS or cells != expected:
        raise FatalFormalRunError("Committed v0.1.2 execution order differs from the frozen balanced order")
    return cells


def headline_retrieval_case_ids(cases: Iterable[dict[str, Any]]) -> set[str]:
    return {
        case["case_id"]
        for case in cases
        if case["answerability"] in {"supported", "partially_supported"} and case["gold_chunk_ids"]
    }


def insufficient_case_ids(cases: Iterable[dict[str, Any]]) -> set[str]:
    return {case["case_id"] for case in cases if case["answerability"] == "insufficient"}


def build_formal_provider_bundle() -> ProviderBundle:
    settings = get_settings()
    shared_key = settings.embedding_api_key or settings.rerank_api_key or settings.llm_api_key
    if not shared_key:
        raise ProviderUnavailable("SiliconFlow credential is missing", error_type="configuration")
    base = get_provider_bundle()
    embedding = SiliconFlowEmbeddingProvider(
        api_key=shared_key,
        base_url=settings.embedding_base_url or settings.llm_base_url,
        model="BAAI/bge-m3",
    )
    reranker = SiliconFlowRerankProvider(
        api_key=shared_key,
        base_url=settings.rerank_base_url or settings.llm_base_url,
        model="BAAI/bge-reranker-v2-m3",
    )
    return replace(base, embedding=embedding, rerank=reranker)


def build_formal_retrieval_engine(repository_root: Path) -> RetrievalEngine:
    verify_frozen_inputs(repository_root)
    corpus = load_runtime_corpus(repository_root / "research/corpus/west_v0_1")
    return RetrievalEngine(
        formal_strict=True,
        persistent_cache=True,
        cache_dir=repository_root / "research/experiments/western_formal_v0_1/cache",
        embedding_batch_size=64,
        candidate_depth=CANDIDATE_DEPTH,
        chunks=corpus.chunks,
        sources=corpus.sources,
        providers=build_formal_provider_bundle(),
        corpus_sha256=CORPUS_CHUNKS_SHA256,
    )


def _error_type(exc: Exception) -> str:
    return str(getattr(exc, "error_type", "content_or_schema_failure"))


@dataclass(frozen=True)
class RetryOutcome:
    value: Any | None
    first_attempt_success: bool
    attempt_count: int
    technical_retry_used: bool
    first_error_type: str | None
    final_success: bool
    errors: list[dict[str, Any]]
    elapsed_ms: float


async def invoke_with_technical_retry(operation: Callable[[], Awaitable[Any]]) -> RetryOutcome:
    started = perf_counter()
    errors: list[dict[str, Any]] = []
    first_error_type: str | None = None
    for attempt in (1, 2):
        try:
            value = await operation()
            return RetryOutcome(
                value=value,
                first_attempt_success=attempt == 1,
                attempt_count=attempt,
                technical_retry_used=attempt == 2,
                first_error_type=first_error_type,
                final_success=True,
                errors=errors,
                elapsed_ms=round((perf_counter() - started) * 1000, 3),
            )
        except Exception as exc:
            kind = _error_type(exc)
            if first_error_type is None:
                first_error_type = kind
            errors.append({"attempt": attempt, "error_type": kind, "message": str(exc)})
            if attempt == 2 or kind not in RETRYABLE_ERROR_TYPES:
                return RetryOutcome(
                    value=None,
                    first_attempt_success=False,
                    attempt_count=attempt,
                    technical_retry_used=attempt == 2,
                    first_error_type=first_error_type,
                    final_success=False,
                    errors=errors,
                    elapsed_ms=round((perf_counter() - started) * 1000, 3),
                )
    raise AssertionError("unreachable")


def _assert_no_secret_fields(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in {"authorization", "password", "secret", "api_key", "access_token", "refresh_token"} or normalized.endswith("_api_key"):
                raise ValueError(f"Secret-bearing field is forbidden in formal output: {path}.{key}")
            _assert_no_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_secret_fields(item, f"{path}[{index}]")


def _atomic_new_json(path: Path, payload: dict[str, Any]) -> None:
    _assert_no_secret_fields(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"Immutable output already exists: {path}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class RunDirectory:
    STAGE_FILES = {"A": "stage_a_retrieval.jsonl", "B": "stage_b_generation.jsonl", "C": "stage_c_judge.jsonl"}

    def __init__(self, path: Path, *, expected_stage_a_pairs: set[tuple[str, str]] | None = None) -> None:
        self.path = path
        self.expected_stage_a_pairs = expected_stage_a_pairs

    @classmethod
    def create(
        cls,
        runs_root: Path,
        run_id: str,
        *,
        repository_root: Path | None = None,
        execution_commit: str | None = None,
        expected_protocol_commit: str | None = None,
        require_clean_worktree: bool = True,
        expected_stage_a_pairs: set[tuple[str, str]] | None = None,
    ) -> "RunDirectory":
        frozen = verify_amended_protocol(repository_root) if repository_root is not None else {}
        current_commit = execution_commit or (_git_head(repository_root) if repository_root is not None else "test-only")
        if repository_root is not None:
            freeze_commit = expected_protocol_commit or resolve_protocol_freeze_commit(repository_root)
            if current_commit != freeze_commit:
                raise FatalFormalRunError(
                    f"Stage A requires protocol freeze HEAD {freeze_commit}; current HEAD is {current_commit}"
                )
            if require_clean_worktree and not _git_worktree_clean(repository_root):
                raise FatalFormalRunError("Stage A requires a clean Git working tree")
            cases = load_frozen_cases(repository_root)
            order = load_frozen_execution_order(repository_root, cases)
            expected_stage_a_pairs = {(cell["case_id"], cell["retrieval_condition"]) for cell in order}
        path = runs_root / run_id
        path.mkdir(parents=True, exist_ok=False)
        instance = cls(path, expected_stage_a_pairs=expected_stage_a_pairs)
        _atomic_new_json(path / "run_manifest.json", {
            "run_id": run_id,
            "protocol_version": PROTOCOL_VERSION,
            "benchmark_version": BENCHMARK_VERSION,
            "benchmark_sha256": BENCHMARK_SHA256,
            "benchmark_manifest_sha256": BENCHMARK_MANIFEST_SHA256,
            "protocol_sha256": frozen.get("protocol_sha256", PROTOCOL_SHA256),
            "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
            "source_registry_sha256": SOURCE_REGISTRY_SHA256,
            "current_execution_commit": current_commit,
            "runtime_checkpoint_commit": RUNTIME_COMMIT,
            "benchmark_checkpoint_commit": BENCHMARK_COMMIT,
            "protocol_checkpoint_commit": current_commit if repository_root is not None else "test-only",
            "original_protocol_v0_1_commit": ORIGINAL_PROTOCOL_COMMIT,
            "superseded_protocol_v0_1_1_commit": V0_1_1_PROTOCOL_COMMIT,
            "superseded_before_formal_execution": True,
            "created_at": _utc_now(),
            "status": "in_progress",
        })
        return instance

    @classmethod
    def resume(cls, path: Path) -> "RunDirectory":
        if not (path / "run_manifest.json").is_file():
            raise FileNotFoundError("Run manifest is missing")
        return cls(path)

    @classmethod
    def resume_stage_a(cls, path: Path, *, repository_root: Path | None = None) -> "RunDirectory":
        if not (path / "run_manifest.json").is_file():
            raise FileNotFoundError("Run manifest is missing")
        expected_pairs = None
        if repository_root is not None:
            cases = load_frozen_cases(repository_root)
            order = load_frozen_execution_order(repository_root, cases)
            expected_pairs = {(cell["case_id"], cell["retrieval_condition"]) for cell in order}
        instance = cls(path, expected_stage_a_pairs=expected_pairs)
        if instance.stage_manifest_path("A").exists():
            raise RuntimeError("Stage A is sealed; resume is prohibited")
        return instance

    def verify_run_manifest(self, repository_root: Path, *, expected_protocol_commit: str | None = None, require_clean_worktree: bool = True) -> None:
        frozen = verify_amended_protocol(repository_root)
        manifest = json.loads((self.path / "run_manifest.json").read_text(encoding="utf-8"))
        expected = {
            "protocol_version": PROTOCOL_VERSION,
            "benchmark_sha256": BENCHMARK_SHA256,
            "benchmark_manifest_sha256": BENCHMARK_MANIFEST_SHA256,
            "protocol_sha256": frozen["protocol_sha256"],
            "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
            "source_registry_sha256": SOURCE_REGISTRY_SHA256,
            "runtime_checkpoint_commit": RUNTIME_COMMIT,
            "benchmark_checkpoint_commit": BENCHMARK_COMMIT,
            "original_protocol_v0_1_commit": ORIGINAL_PROTOCOL_COMMIT,
            "superseded_protocol_v0_1_1_commit": V0_1_1_PROTOCOL_COMMIT,
            "superseded_before_formal_execution": True,
        }
        mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
        head = _git_head(repository_root)
        freeze_commit = expected_protocol_commit or resolve_protocol_freeze_commit(repository_root)
        if head != freeze_commit:
            mismatches["protocol_freeze_head"] = {"expected": freeze_commit, "actual": head}
        if manifest.get("current_execution_commit") != freeze_commit or manifest.get("protocol_checkpoint_commit") != freeze_commit:
            mismatches["execution_commit"] = {"expected": freeze_commit, "actual": manifest.get("current_execution_commit")}
        if require_clean_worktree and not _git_worktree_clean(repository_root):
            mismatches["worktree"] = {"expected": "clean", "actual": "dirty"}
        if mismatches:
            raise FatalFormalRunError(f"Run manifest verification failed: {json.dumps(mismatches, sort_keys=True)}")

    def stage_path(self, stage: str) -> Path:
        return self.path / self.STAGE_FILES[stage]

    def stage_manifest_path(self, stage: str) -> Path:
        return self.path / f"stage_{stage.casefold()}_manifest.json"

    def completed_ids(self, stage: str) -> set[str]:
        path = self.stage_path(stage)
        if not path.exists():
            return set()
        return {
            json.loads(line)["experiment_id"]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def append(self, stage: str, record: dict[str, Any]) -> None:
        if self.stage_manifest_path(stage).exists():
            raise RuntimeError(f"Stage {stage} is sealed and immutable")
        predecessor = {"B": "A", "C": "B"}.get(stage)
        if predecessor is not None:
            if not self.stage_manifest_path(predecessor).exists():
                raise RuntimeError(f"Stage {predecessor} must be sealed before Stage {stage}")
            self.verify_sealed(predecessor)
        _assert_no_secret_fields(record)
        completed = self.completed_ids(stage)
        if record["experiment_id"] in completed:
            raise ValueError(f"Duplicate experiment cell: {record['experiment_id']}")
        path = self.stage_path(stage)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def seal(self, stage: str, *, expected_cells: int = INTENDED_CELLS, expected_experiment_ids: set[str] | None = None) -> dict[str, Any]:
        path = self.stage_path(stage)
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        ids = [item["experiment_id"] for item in records]
        if len(records) != expected_cells or len(set(ids)) != expected_cells:
            raise RuntimeError(f"Stage {stage} requires {expected_cells} unique cells before sealing")
        if stage == "B":
            if expected_experiment_ids is None and expected_cells == INTENDED_CELLS:
                raise RuntimeError("Stage B exact Stage A experiment-ID set is required for sealing")
            if expected_experiment_ids is not None and set(ids) != expected_experiment_ids:
                raise RuntimeError("Stage B experiment IDs differ from the exact Stage A ID set")
        if stage == "A":
            pairs = [(item.get("case_id"), item.get("retrieval_condition")) for item in records]
            terminal = {"success", "technical_failure"}
            actual_pairs = set(pairs)
            if len(actual_pairs) != expected_cells:
                raise RuntimeError("Stage A contains duplicate case/condition cells")
            if self.expected_stage_a_pairs is None and expected_cells == INTENDED_CELLS:
                raise RuntimeError("Stage A exact frozen pair matrix is unavailable")
            if self.expected_stage_a_pairs is not None and actual_pairs != self.expected_stage_a_pairs:
                missing = sorted(self.expected_stage_a_pairs - actual_pairs)
                unexpected = sorted(actual_pairs - self.expected_stage_a_pairs)
                raise RuntimeError(f"Stage A pair matrix differs from frozen order: missing={missing[:3]}, unexpected={unexpected[:3]}")
            if any(item.get("terminal_state") not in terminal for item in records):
                raise RuntimeError("Stage A may seal only unique terminal cells")
            if any(bool(item.get("retrieval_success")) != (item.get("terminal_state") == "success") for item in records):
                raise RuntimeError("Stage A terminal state and retrieval_success disagree")
        payload = {
            "stage": stage,
            "cell_count": len(records),
            "sha256": _sha256(path),
            "sealed_at": _utc_now(),
            "immutable_input_for": {"A": "B", "B": "C", "C": "final analysis"}[stage],
        }
        if stage == "A":
            payload["successful_cells"] = sum(bool(item["retrieval_success"]) for item in records)
            payload["technical_failure_cells"] = sum(not bool(item["retrieval_success"]) for item in records)
        _atomic_new_json(self.stage_manifest_path(stage), payload)
        return payload

    def verify_sealed(self, stage: str) -> None:
        manifest = json.loads(self.stage_manifest_path(stage).read_text(encoding="utf-8"))
        if manifest["sha256"] != _sha256(self.stage_path(stage)):
            raise RuntimeError(f"Sealed Stage {stage} hash mismatch")


class StageBRepeatDirectory:
    """A Stage-B-only run that references the canonical frozen Stage A externally."""

    def __init__(self, path: Path) -> None:
        if path.name != STAGE_B_REPEAT_RUN_ID:
            raise FatalFormalRunError(f"Stage B repeat requires exact run ID {STAGE_B_REPEAT_RUN_ID}")
        self.path = path

    def stage_path(self, stage: str = "B") -> Path:
        if stage != "B":
            raise ValueError("Stage B repeat directory contains only Stage B outputs")
        return self.path / "stage_b_generation.jsonl"

    def stage_manifest_path(self, stage: str = "B") -> Path:
        if stage != "B":
            raise ValueError("Stage B repeat directory contains only a Stage B seal")
        return self.path / "stage_b_manifest.json"

    def append(self, stage: str, record: dict[str, Any]) -> None:
        if stage != "B":
            raise ValueError("Stage B repeat directory accepts only Stage B records")
        if self.stage_manifest_path().exists():
            raise FatalFormalRunError("Stage B repeat is sealed and immutable")
        if not (self.path / "stage_b_repeat_execution_manifest.json").is_file():
            raise FatalFormalRunError("Stage B repeat execution manifest must exist before append")
        _assert_no_secret_fields(record)
        existing = _read_jsonl_strict(self.stage_path(), label="Stage B repeat generation")
        if record.get("experiment_id") in {row.get("experiment_id") for row in existing}:
            raise FatalFormalRunError(f"Duplicate Stage B repeat cell: {record.get('experiment_id')}")
        self.path.mkdir(parents=True, exist_ok=True)
        with self.stage_path().open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def seal(self, expected_experiment_ids: list[str]) -> dict[str, Any]:
        records = _read_jsonl_strict(self.stage_path(), label="Stage B repeat generation")
        ids = [row.get("experiment_id") for row in records]
        if len(records) != INTENDED_CELLS or ids != expected_experiment_ids or len(set(ids)) != INTENDED_CELLS:
            raise FatalFormalRunError("Stage B repeat seal requires the exact ordered 192 Stage A experiment IDs")
        payload = {
            "stage": "B",
            "run_id": STAGE_B_REPEAT_RUN_ID,
            "cell_count": INTENDED_CELLS,
            "sha256": _sha256(self.stage_path()),
            "sealed_at": _utc_now(),
            "immutable_input_for": "repeat-aware B finalization",
            "parent_stage_a_run_id": STAGE_A_RUN_ID,
            "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
            "repeat_ordinal": 1,
            "repeat_scope": "all_192_cells",
            "reuse_original_successes": False,
        }
        _atomic_new_json(self.stage_manifest_path(), payload)
        return payload

    def verify_sealed(self) -> None:
        manifest = _load_json_object(self.stage_manifest_path(), label="Stage B repeat seal")
        if manifest.get("sha256") != _sha256(self.stage_path()) or manifest.get("cell_count") != INTENDED_CELLS:
            raise FatalFormalRunError("Stage B repeat seal hash or cell count mismatch")


class StageCDirectory:
    """A Stage-C-only run that references frozen Stage A and primary Stage B externally."""

    def __init__(self, path: Path) -> None:
        if path.name != STAGE_C_RUN_ID:
            raise FatalFormalRunError(f"Stage C requires exact run ID {STAGE_C_RUN_ID}")
        self.path = path

    def stage_path(self) -> Path:
        return self.path / "stage_c_judge.jsonl"

    def stage_manifest_path(self) -> Path:
        return self.path / "stage_c_manifest.json"

    def execution_manifest_path(self) -> Path:
        return self.path / "stage_c_execution_manifest.json"

    def incident_manifest_path(self) -> Path:
        return self.path / "stage_c_incident_manifest.json"

    def incident_markdown_path(self) -> Path:
        return self.path / "STAGE_C_EXECUTION_INCIDENT.md"

    def append(self, record: dict[str, Any]) -> None:
        if self.stage_manifest_path().exists():
            raise FatalFormalRunError("Stage C is sealed and immutable")
        if not self.execution_manifest_path().is_file():
            raise FatalFormalRunError("Stage C execution manifest must exist before append")
        _assert_no_secret_fields(record)
        existing = _read_jsonl_strict(self.stage_path(), label="Stage C judgments")
        if record.get("experiment_id") in {row.get("experiment_id") for row in existing}:
            raise FatalFormalRunError(f"Duplicate Stage C cell: {record.get('experiment_id')}")
        self.path.mkdir(parents=True, exist_ok=True)
        with self.stage_path().open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def seal(self, expected_experiment_ids: list[str]) -> dict[str, Any]:
        records = _read_jsonl_strict(self.stage_path(), label="Stage C judgments")
        ids = [row.get("experiment_id") for row in records]
        if len(records) != INTENDED_CELLS or ids != expected_experiment_ids or len(set(ids)) != INTENDED_CELLS:
            raise FatalFormalRunError("Stage C seal requires the exact ordered 192 primary Stage B experiment IDs")
        payload = {
            "stage": "C",
            "run_id": STAGE_C_RUN_ID,
            "cell_count": INTENDED_CELLS,
            "sha256": _sha256(self.stage_path()),
            "sealed_at": _utc_now(),
            "immutable_input_for": "Stage C finalization and merged final analysis",
            "parent_stage_a_run_id": STAGE_A_RUN_ID,
            "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
            "parent_stage_b_run_id": STAGE_B_REPEAT_RUN_ID,
            "parent_stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        }
        _atomic_new_json(self.stage_manifest_path(), payload)
        return payload

    def verify_sealed(self) -> None:
        manifest = _load_json_object(self.stage_manifest_path(), label="Stage C seal")
        expected = {
            "stage": "C", "run_id": STAGE_C_RUN_ID, "cell_count": INTENDED_CELLS,
            "sha256": _sha256(self.stage_path()), "parent_stage_a_run_id": STAGE_A_RUN_ID,
            "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
            "parent_stage_b_run_id": STAGE_B_REPEAT_RUN_ID,
            "parent_stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        }
        mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
        if mismatches:
            raise FatalFormalRunError(f"Stage C seal mismatch: {json.dumps(mismatches, sort_keys=True)}")


def _base_record(case: dict[str, Any], condition: str) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id(case["case_id"], condition),
        "protocol_version": PROTOCOL_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "benchmark_sha256": BENCHMARK_SHA256,
        "case_id": case["case_id"],
        "question": case["question"],
        "topic": case["topic"],
        "question_type": case["question_type"],
        "answerability": case["answerability"],
        "retrieval_condition": condition,
        "retrieval_config": RETRIEVAL_CONDITIONS[condition],
        "gold_primary_chunk_ids": case["gold_chunk_ids"],
        "gold_primary_source_ids": case["gold_source_ids"],
        "gold_secondary_chunk_ids": case["optional_secondary_chunk_ids"],
        "expected_evidence_points": case["expected_evidence_points"],
        "generator_provider": GENERATOR_PROVIDER,
        "generator_model": GENERATOR_MODEL,
        "temperature": GENERATOR_TEMPERATURE,
        "max_tokens": GENERATOR_MAX_TOKENS,
        "judge_provider": JUDGE_PROVIDER,
        "judge_model": JUDGE_MODEL,
    }


@dataclass
class FormalCellRetryState:
    retry_used: bool = False
    retry_stage: str = "none"
    first_error_type: str | None = None
    final_error_type: str | None = None
    errors: list[dict[str, Any]] | None = None
    provider_operation_trace: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        self.errors = [] if self.errors is None else self.errors
        self.provider_operation_trace = [] if self.provider_operation_trace is None else self.provider_operation_trace


async def _formal_remote_operation(
    operation: Callable[[], Awaitable[Any]],
    *,
    stage: str,
    state: FormalCellRetryState,
) -> tuple[bool, Any | None]:
    operation_attempt = 0
    while True:
        operation_attempt += 1
        started_at = _utc_now()
        try:
            value = await operation()
            state.provider_operation_trace.append({
                "stage": stage, "operation_attempt": operation_attempt, "success": True,
                "started_at": started_at, "completed_at": _utc_now(),
            })
            return True, value
        except ProviderUnavailable as exc:
            kind = _error_type(exc)
            if kind not in RETRYABLE_ERROR_TYPES:
                raise FatalFormalRunError(f"Non-retryable formal {stage} provider failure: {kind}") from exc
            if state.first_error_type is None:
                state.first_error_type = kind
            error = {
                "stage": stage, "operation_attempt": operation_attempt,
                "error_type": kind, "message": str(exc), "at": _utc_now(),
            }
            state.errors.append(error)
            state.provider_operation_trace.append({
                "stage": stage, "operation_attempt": operation_attempt, "success": False,
                "error_type": kind, "started_at": started_at, "completed_at": _utc_now(),
            })
            if state.retry_used or operation_attempt == 2:
                state.final_error_type = kind
                return False, None
            state.retry_used = True
            state.retry_stage = stage


def _formal_rank_results(
    engine: RetrievalEngine,
    *,
    query: str,
    condition: str,
    topics: list[str],
    lexical: dict[str, float],
    semantic: dict[str, float],
    rerank_scores: dict[str, float] | None = None,
) -> list[RetrievalItem]:
    topic_filter = _expanded_topics(topics)
    allowed = [chunk for chunk in engine.chunks if not topic_filter or topic_filter & set(chunk.topics)] or list(engine.chunks)
    lexical_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(lexical.items(), key=lambda item: item[1], reverse=True), 1)}
    semantic_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(semantic.items(), key=lambda item: item[1], reverse=True), 1)}
    fusion = {chunk.chunk_id: 1 / (RRF_CONSTANT + lexical_rank[chunk.chunk_id]) + 1 / (RRF_CONSTANT + semantic_rank[chunk.chunk_id]) for chunk in allowed}
    rerank_scores = rerank_scores or {}
    if condition == "R0":
        ranked = sorted(allowed, key=lambda chunk: lexical[chunk.chunk_id], reverse=True)
    elif condition == "R1":
        ranked = sorted(allowed, key=lambda chunk: semantic[chunk.chunk_id], reverse=True)
    elif condition == "R3":
        ranked = sorted(allowed, key=lambda chunk: (rerank_scores.get(chunk.chunk_id, -1), fusion[chunk.chunk_id]), reverse=True)
    else:
        ranked = sorted(allowed, key=lambda chunk: fusion[chunk.chunk_id], reverse=True)
    method = {"R0": "lexical", "R1": "dense", "R2": "hybrid", "R3": "hybrid_reranked"}[condition]
    results: list[RetrievalItem] = []
    for rank, chunk in enumerate(ranked[:FINAL_TOP_K], 1):
        source = engine.sources.get(chunk.source_id)
        results.append(RetrievalItem(
            chunk_id=chunk.chunk_id, source_id=chunk.source_id, rank=rank,
            lexical_score=lexical[chunk.chunk_id] if condition != "R1" else None,
            semantic_score=semantic[chunk.chunk_id] if condition != "R0" else None,
            fusion_score=round(fusion[chunk.chunk_id], 6) if condition in {"R2", "R3"} else None,
            rerank_score=rerank_scores.get(chunk.chunk_id) if condition == "R3" else None,
            retrieval_method=method, chunk_text=chunk.text, topics=chunk.topics,
            source_metadata=source.model_dump() if source else {},
        ))
    return results


async def formal_retrieve_cell(
    engine: RetrievalEngine,
    *,
    query: str,
    condition: str,
    topics: list[str],
) -> dict[str, Any]:
    """Execute one formal retrieval cell with one cell-level remote retry event."""
    if condition not in CONDITIONS:
        raise FatalFormalRunError(f"Invalid formal retrieval condition: {condition}")
    state = FormalCellRetryState()
    started = perf_counter()
    engine.actual_embedding_provider = "none"
    engine.actual_embedding_model = "none"
    engine.actual_reranker_provider = "none"
    engine.actual_reranker_model = "none"
    try:
        lexical = engine._lexical(query) if condition != "R1" else {chunk.chunk_id: 0.0 for chunk in engine.chunks}
    except Exception as exc:
        raise FatalFormalRunError("Unexpected local lexical retrieval exception") from exc
    semantic = {chunk.chunk_id: 0.0 for chunk in engine.chunks}
    if condition != "R0":
        dense_ok, dense_value = await _formal_remote_operation(
            lambda: engine._semantic(query), stage="dense", state=state,
        )
        if not dense_ok:
            return {
                "retrieval_success": False, "terminal_state": "technical_failure", "results": [],
                "attempt_count": 2 if state.retry_used else 1,
                "technical_retry_used": state.retry_used, "technical_retry_stage": state.retry_stage,
                "first_error_type": state.first_error_type, "final_error_type": state.final_error_type,
                "errors": state.errors, "provider_operation_trace": state.provider_operation_trace,
                "retrieval_latency_ms": round((perf_counter() - started) * 1000, 3),
            }
        semantic = dense_value
    rerank_scores: dict[str, float] = {}
    if condition == "R3":
        topic_filter = _expanded_topics(topics)
        allowed = [chunk for chunk in engine.chunks if not topic_filter or topic_filter & set(chunk.topics)] or list(engine.chunks)
        lexical_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(lexical.items(), key=lambda item: item[1], reverse=True), 1)}
        semantic_rank = {item_id: rank for rank, (item_id, _) in enumerate(sorted(semantic.items(), key=lambda item: item[1], reverse=True), 1)}
        fusion = {chunk.chunk_id: 1 / (RRF_CONSTANT + lexical_rank[chunk.chunk_id]) + 1 / (RRF_CONSTANT + semantic_rank[chunk.chunk_id]) for chunk in allowed}
        candidates = sorted(allowed, key=lambda chunk: fusion[chunk.chunk_id], reverse=True)[:CANDIDATE_DEPTH]
        reranker = engine.providers.rerank
        try:
            engine._validate_formal_reranker(reranker)
        except ProviderUnavailable as exc:
            raise FatalFormalRunError("Invalid formal reranker configuration") from exc

        async def rerank_operation() -> list[float]:
            values = await reranker.rerank(query, [chunk.text for chunk in candidates])
            if len(values) != len(candidates) or any(not math.isfinite(value) for value in values):
                raise ProviderUnavailable("Reranker returned malformed or partial scores", error_type="malformed_response")
            return values

        rerank_ok, values = await _formal_remote_operation(rerank_operation, stage="reranker", state=state)
        if not rerank_ok:
            return {
                "retrieval_success": False, "terminal_state": "technical_failure", "results": [],
                "attempt_count": 2 if state.retry_used else 1,
                "technical_retry_used": state.retry_used, "technical_retry_stage": state.retry_stage,
                "first_error_type": state.first_error_type, "final_error_type": state.final_error_type,
                "errors": state.errors, "provider_operation_trace": state.provider_operation_trace,
                "retrieval_latency_ms": round((perf_counter() - started) * 1000, 3),
            }
        engine.actual_reranker_provider = reranker.name
        engine.actual_reranker_model = reranker.model
        rerank_scores = {chunk.chunk_id: value for chunk, value in zip(candidates, values)}
    results = _formal_rank_results(
        engine, query=query, condition=condition, topics=topics,
        lexical=lexical, semantic=semantic, rerank_scores=rerank_scores,
    )
    return {
        "retrieval_success": True, "terminal_state": "success", "results": results,
        "attempt_count": 2 if state.retry_used else 1,
        "technical_retry_used": state.retry_used, "technical_retry_stage": state.retry_stage,
        "first_error_type": state.first_error_type, "final_error_type": None,
        "errors": state.errors, "provider_operation_trace": state.provider_operation_trace,
        "retrieval_latency_ms": round((perf_counter() - started) * 1000, 3),
    }


async def run_stage_a(repository_root: Path, run: RunDirectory, *, engine: RetrievalEngine | None = None) -> None:
    verify_amended_protocol(repository_root)
    run.verify_run_manifest(repository_root)
    if run.stage_manifest_path("A").exists():
        raise RuntimeError("Stage A is already sealed and cannot resume")
    cases = load_frozen_cases(repository_root)
    cases_by_id = {case["case_id"]: case for case in cases}
    engine = engine or build_formal_retrieval_engine(repository_root)
    chunk_lookup = {chunk.chunk_id: chunk for chunk in engine.chunks}
    completed = run.completed_ids("A")
    for cell in load_frozen_execution_order(repository_root, cases):
        if cell["experiment_id"] in completed:
            continue
        case = cases_by_id[cell["case_id"]]
        condition = cell["retrieval_condition"]
        outcome = await formal_retrieve_cell(
            engine, query=case["question"], condition=condition, topics=[case["topic"]],
        )
        results = outcome.pop("results")
        retrieved_items = []
        for item in results:
            chunk = chunk_lookup[item.chunk_id]
            source = item.source_metadata
            retrieved_items.append({
                "chunk_id": item.chunk_id,
                "source_id": item.source_id,
                "rank": item.rank,
                "article_title": source.get("title", ""),
                "section": chunk.section,
                "source_url": source.get("source_url", ""),
                "pmcid": source.get("pmcid", ""),
                "doi": source.get("doi", ""),
                "license": source.get("license", ""),
                "domain": "western",
                "evidence_excerpt": item.chunk_text[:WESTERN_EVIDENCE_EXCERPT_CHARS],
                "lexical_score": item.lexical_score,
                "semantic_score": item.semantic_score,
                "fusion_score": item.fusion_score,
                "rerank_score": item.rerank_score,
            })
        record = {
            **_base_record(case, condition),
            "retrieved_items": retrieved_items,
            **outcome,
            "timestamps": {"retrieval_completed_at": _utc_now()},
        }
        run.append("A", record)
    run.seal("A")


def _retrieval_evidence(items: list[dict[str, Any]], topic: str) -> list[WesternRetrievalEvidence]:
    return [
        WesternRetrievalEvidence(
            chunk_id=item["chunk_id"], source_id=item["source_id"], rank=item["rank"],
            lexical_score=float(item.get("lexical_score") or 0.0), article_title=item["article_title"],
            section=item["section"], pmcid=item["pmcid"], doi=item["doi"], source_url=item["source_url"],
            license=item["license"], topic=WesternTopic(topic), text=item["evidence_excerpt"], provenance={},
        )
        for item in items
    ]


def verify_frozen_stage_a(repository_root: Path, run: RunDirectory) -> list[dict[str, Any]]:
    verify_amended_protocol(repository_root)
    if run.path.name != STAGE_A_RUN_ID:
        raise FatalFormalRunError(f"Stage B requires frozen Stage A run {STAGE_A_RUN_ID}")
    run_manifest = _load_json_object(run.path / "run_manifest.json", label="run manifest")
    stage_manifest = _load_json_object(run.stage_manifest_path("A"), label="Stage A manifest")
    final_manifest = _load_json_object(run.path / "stage_a_run_manifest.json", label="Stage A final manifest")
    expected_run = {
        "run_id": STAGE_A_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "current_execution_commit": STAGE_A_CHECKPOINT_COMMIT,
        "protocol_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "benchmark_sha256": BENCHMARK_SHA256,
        "benchmark_manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "corpus_chunks_sha256": CORPUS_CHUNKS_SHA256,
        "source_registry_sha256": SOURCE_REGISTRY_SHA256,
    }
    for manifest_name, manifest in (("run manifest", run_manifest), ("Stage A final manifest", final_manifest)):
        mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected_run.items() if manifest.get(key) != value}
        if mismatches:
            raise FatalFormalRunError(f"Frozen Stage A {manifest_name} mismatch: {json.dumps(mismatches, sort_keys=True)}")
    if stage_manifest.get("sha256") != STAGE_A_RETRIEVAL_SHA256 or stage_manifest.get("cell_count") != INTENDED_CELLS:
        raise FatalFormalRunError("Frozen Stage A seal manifest mismatch")
    if stage_manifest.get("successful_cells") != INTENDED_CELLS or stage_manifest.get("technical_failure_cells") != 0:
        raise FatalFormalRunError("Frozen Stage A success/failure counts differ from the immutable anchor")
    if _sha256(run.stage_path("A")) != STAGE_A_RETRIEVAL_SHA256:
        raise FatalFormalRunError("Frozen Stage A retrieval SHA256 mismatch")
    raw_path = run.path / "stage_a_raw_results.jsonl"
    if _sha256(raw_path) != STAGE_A_RETRIEVAL_SHA256:
        raise FatalFormalRunError("Frozen Stage A raw-results SHA256 mismatch")
    artifact_hashes = final_manifest.get("stage_a_artifact_sha256")
    if not isinstance(artifact_hashes, dict):
        raise FatalFormalRunError("Frozen Stage A artifact hash registry is missing")
    for name, expected_hash in artifact_hashes.items():
        path = run.path / name
        if not path.is_file() or _sha256(path) != expected_hash:
            raise FatalFormalRunError(f"Frozen Stage A artifact mismatch: {name}")
    records = _read_jsonl_strict(run.stage_path("A"), label="Stage A retrieval")
    cases = load_frozen_cases(repository_root)
    expected_ids = [cell["experiment_id"] for cell in load_frozen_execution_order(repository_root, cases)]
    actual_ids = [row.get("experiment_id") for row in records]
    if actual_ids != expected_ids or len(set(actual_ids)) != INTENDED_CELLS:
        raise FatalFormalRunError("Frozen Stage A does not match the exact 192-cell execution matrix")
    if any(row.get("terminal_state") != "success" or row.get("retrieval_success") is not True for row in records):
        raise FatalFormalRunError("Frozen Stage A terminal records differ from the 192-success anchor")
    return records


def _expected_provenance(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {key: item[key] for key in ("chunk_id", "source_id", "article_title", "section", "source_url", "pmcid", "doi", "license")}
        for item in retrieval["retrieved_items"]
    ]


def _validate_stage_b_provenance(repository_root: Path, retrieval: dict[str, Any], provenance: list[dict[str, Any]]) -> None:
    corpus = load_runtime_corpus(repository_root / "research/corpus/west_v0_1")
    valid, errors = provenance_integrity(retrieval["retrieved_items"], provenance, set(corpus.sources))
    if not valid or provenance != _expected_provenance(retrieval):
        raise FatalFormalRunError(f"Stage B provenance invariant failed: {errors or ['exact provenance mismatch']}")


@dataclass(frozen=True)
class StageBGenerationOutcome:
    generation_success: bool
    generation_outcome: str
    answer: str
    provider_result: Any | None
    first_attempt_success: bool
    attempt_count: int
    technical_retry_used: bool
    first_error_type: str | None
    final_error_type: str | None
    errors: list[dict[str, Any]]
    elapsed_ms: float


async def invoke_stage_b_generation(operation: Callable[[], Awaitable[Any]]) -> StageBGenerationOutcome:
    started = perf_counter()
    errors: list[dict[str, Any]] = []
    first_error: str | None = None
    for attempt in (1, 2):
        try:
            result, answer = await operation()
            return StageBGenerationOutcome(True, "completed", answer, result, attempt == 1, attempt, attempt == 2, first_error, None, errors, round((perf_counter() - started) * 1000, 3))
        except ProviderUnavailable as exc:
            kind = _error_type(exc)
            if kind in {"configuration", "authentication"} or (kind == "http_4xx" and getattr(exc, "http_status", None) in {401, 403}):
                raise FatalFormalRunError(f"Fatal Stage B provider configuration/authentication failure: {kind}") from exc
            if first_error is None:
                first_error = kind
            errors.append({"attempt": attempt, "error_type": kind, "message": str(exc)})
            if kind == "output_quality_rejection":
                return StageBGenerationOutcome(False, "output_quality_rejection", "", None, False, attempt, False, first_error, kind, errors, round((perf_counter() - started) * 1000, 3))
            if kind == "rate_limit":
                return StageBGenerationOutcome(False, "rate_limit", "", None, False, attempt, False, first_error, kind, errors, round((perf_counter() - started) * 1000, 3))
            if kind not in RETRYABLE_ERROR_TYPES:
                return StageBGenerationOutcome(False, "nonretryable_provider_failure", "", None, False, attempt, False, first_error, kind, errors, round((perf_counter() - started) * 1000, 3))
            if attempt == 2:
                return StageBGenerationOutcome(False, "technical_failure", "", None, False, 2, True, first_error, kind, errors, round((perf_counter() - started) * 1000, 3))
        except Exception as exc:
            raise FatalFormalRunError(f"Unexpected Stage B programming/runtime defect: {type(exc).__name__}") from exc
    raise AssertionError("unreachable")


def _validate_formal_generator(generator: Any) -> None:
    if getattr(generator, "name", GENERATOR_PROVIDER) != GENERATOR_PROVIDER or getattr(generator, "model", GENERATOR_MODEL) != GENERATOR_MODEL:
        raise FatalFormalRunError("Stage B generator provider/model configuration mismatch")
    if hasattr(generator, "api_key") and not str(getattr(generator, "api_key", "")).strip():
        raise FatalFormalRunError("Stage B generator API credential is missing")


def _stage_b_execution_manifest_payload(run: RunDirectory, anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": "B",
        "status": "in_progress",
        "run_id": STAGE_A_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "stage_b_execution_version": STAGE_B_EXECUTION_VERSION,
        "stage_b_execution_freeze_commit": anchor["execution_freeze_commit"],
        "stage_b_execution_json_sha256": anchor["execution_json_sha256"],
        "implementation_sha256": anchor["implementation_sha256"],
        "created_at": _utc_now(),
    }


def _ensure_stage_b_execution_manifest(run: RunDirectory, anchor: dict[str, Any], *, allow_create: bool) -> dict[str, Any]:
    path = run.path / "stage_b_execution_manifest.json"
    if not path.exists():
        if not allow_create:
            raise FatalFormalRunError("Stage B rows exist without a Stage B execution manifest")
        _atomic_new_json(path, _stage_b_execution_manifest_payload(run, anchor))
    manifest = _load_json_object(path, label="Stage B execution manifest")
    expected = _stage_b_execution_manifest_payload(run, anchor)
    expected.pop("created_at")
    mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
    if mismatches:
        raise FatalFormalRunError(f"Stage B execution manifest mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return manifest


def _validate_stage_b_record(repository_root: Path, retrieval: dict[str, Any], record: dict[str, Any]) -> None:
    if record.get("experiment_id") != retrieval.get("experiment_id"):
        raise FatalFormalRunError("Stage B record experiment ID does not match Stage A")
    outcome = record.get("generation_outcome")
    allowed = {"completed", "technical_failure", "output_quality_rejection", "rate_limit", "nonretryable_provider_failure", "upstream_retrieval_technical_failure"}
    if outcome not in allowed:
        raise FatalFormalRunError(f"Invalid Stage B terminal outcome: {outcome}")
    success = record.get("generation_success") is True and record.get("final_generation_success") is True
    if success != (outcome == "completed"):
        raise FatalFormalRunError("Stage B success flags disagree with terminal outcome")
    attempts = record.get("attempt_count")
    retry_used = record.get("technical_retry_used")
    if outcome == "upstream_retrieval_technical_failure":
        if retrieval.get("retrieval_success") is not False or attempts != 0 or retry_used is not False:
            raise FatalFormalRunError("Invalid upstream-retrieval missingness record")
    elif attempts not in {1, 2}:
        raise FatalFormalRunError("Stage B provider attempt count must be 1 or 2")
    if outcome == "technical_failure" and (attempts != 2 or retry_used is not True):
        raise FatalFormalRunError("Stage B technical failure must exhaust the single retry")
    if outcome in {"output_quality_rejection", "rate_limit"} and (attempts != 1 or retry_used is not False):
        raise FatalFormalRunError(f"Stage B {outcome} must be nonretryable")
    answer = record.get("answer")
    if outcome == "completed" and (not isinstance(answer, str) or not answer.strip()):
        raise FatalFormalRunError("Completed Stage B record has no answer")
    if outcome != "completed" and answer != "":
        raise FatalFormalRunError("Unsuccessful Stage B record must not contain an answer")
    provenance = record.get("provenance")
    if not isinstance(provenance, list):
        raise FatalFormalRunError("Stage B provenance must be a list")
    _validate_stage_b_provenance(repository_root, retrieval, provenance)


def _validated_existing_stage_b_records(repository_root: Path, run: RunDirectory, stage_a: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = _read_jsonl_strict(run.stage_path("B"), label="Stage B generation")
    if len(records) > INTENDED_CELLS:
        raise FatalFormalRunError("Stage B contains more than 192 rows")
    ids = [row.get("experiment_id") for row in records]
    if len(ids) != len(set(ids)):
        raise FatalFormalRunError("Stage B contains duplicate experiment IDs")
    stage_a_by_id = {row["experiment_id"]: row for row in stage_a}
    foreign = [cell_id for cell_id in ids if cell_id not in stage_a_by_id]
    if foreign:
        raise FatalFormalRunError(f"Stage B contains foreign experiment IDs: {foreign[:3]}")
    expected_prefix = [row["experiment_id"] for row in stage_a[:len(records)]]
    if ids != expected_prefix:
        raise FatalFormalRunError("Stage B records are not a valid frozen-order prefix of Stage A")
    for record in records:
        _validate_stage_b_record(repository_root, stage_a_by_id[record["experiment_id"]], record)
    return records


def _verify_original_stage_b_execution_history(repository_root: Path, run: RunDirectory) -> dict[str, Any]:
    if resolve_stage_b_execution_freeze_commit(repository_root) != ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT:
        raise FatalFormalRunError("Original Stage B execution freeze commit mismatch")
    config_path = repository_root / STAGE_B_EXECUTION_RELATIVE_PATH
    if _sha256(config_path) != ORIGINAL_STAGE_B_EXECUTION_JSON_SHA256:
        raise FatalFormalRunError("Original Stage B execution freeze JSON SHA256 mismatch")
    config = _stage_b_execution_config(repository_root)
    implementation_commit = config.get("implementation_commit")
    implementation = config.get("implementation_sha256")
    if not isinstance(implementation_commit, str) or not isinstance(implementation, dict):
        raise FatalFormalRunError("Original Stage B implementation anchor is incomplete")
    expected_implementation = {
        "backend/western/formal_eval.py": "9a25c416569c0567bd7610ad70ff156fd3e5c578345c20d7153aeb4dcece9a4d",
        "scripts/run-western-formal-v0.1.py": "86f5be7f43de38699136058c9abb863eab2335c0c177faf4114e3a37b156bc98",
    }
    if implementation_commit != "de04c2ca1742794206de80e75155aa3d44c47eb4" or implementation != expected_implementation:
        raise FatalFormalRunError("Original Stage B implementation anchor differs from the frozen execution metadata")
    unchanged = subprocess.run(
        ["git", "diff", "--quiet", implementation_commit, ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT, "--", *implementation],
        cwd=repository_root,
    )
    if unchanged.returncode != 0:
        raise FatalFormalRunError("Original Stage B implementation files changed between implementation and freeze commits")
    manifest = _load_json_object(run.path / "stage_b_execution_manifest.json", label="original Stage B execution manifest")
    expected = {
        "stage": "B",
        "status": "in_progress",
        "run_id": STAGE_A_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "stage_b_execution_version": STAGE_B_EXECUTION_VERSION,
        "stage_b_execution_freeze_commit": ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT,
        "stage_b_execution_json_sha256": ORIGINAL_STAGE_B_EXECUTION_JSON_SHA256,
        "implementation_sha256": implementation,
    }
    mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
    if mismatches:
        raise FatalFormalRunError(f"Original Stage B execution manifest mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return manifest


def _incident_counts(stage_a: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [row for row in records if row.get("generation_success") is not True]
    first_failure_index = next((index for index, row in enumerate(records) if row.get("generation_success") is not True), None)
    final_counts: dict[str, int] = {}
    first_counts: dict[str, int] = {}
    condition_counts = {condition: 0 for condition in CONDITIONS}
    stage_a_by_id = {row["experiment_id"]: row for row in stage_a}
    for row in failures:
        final = str(row.get("final_error_type"))
        first = str(row.get("first_error_type"))
        final_counts[final] = final_counts.get(final, 0) + 1
        first_counts[first] = first_counts.get(first, 0) + 1
        condition = stage_a_by_id[row["experiment_id"]]["retrieval_condition"]
        condition_counts[condition] += 1
    successes_after = 0 if first_failure_index is None else sum(
        row.get("generation_success") is True for row in records[first_failure_index:]
    )
    suffix = 0
    for row in reversed(records):
        if row.get("generation_success") is True:
            break
        suffix += 1
    return {
        "cell_count": len(records),
        "completed_count": len(records) - len(failures),
        "technical_failure_count": len(failures),
        "first_failure_position": None if first_failure_index is None else first_failure_index + 1,
        "first_failed_experiment_id": None if first_failure_index is None else records[first_failure_index].get("experiment_id"),
        "consecutive_failure_suffix_count": suffix,
        "successes_after_first_failure": successes_after,
        "final_error_counts": dict(sorted(final_counts.items())),
        "first_error_counts": dict(sorted(first_counts.items())),
        "failure_counts_by_condition": condition_counts,
        "retry_used_failure_count": sum(row.get("technical_retry_used") is True for row in failures),
        "attempt_count_two_failure_count": sum(row.get("attempt_count") == 2 for row in failures),
        "provider_reported_model_count": sum(row.get("provider_reported_model") == GENERATOR_MODEL for row in records),
    }


def _verify_original_stage_b_incident(repository_root: Path, run: RunDirectory) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if run.path.name != STAGE_A_RUN_ID:
        raise FatalFormalRunError(f"Incident preservation requires exact original run ID {STAGE_A_RUN_ID}")
    stage_a = verify_frozen_stage_a(repository_root, run)
    if run.stage_path("C").exists() or run.stage_manifest_path("C").exists():
        raise FatalFormalRunError("Stage C artifacts must be absent from the Stage B outage incident")
    standard_outputs = (
        "stage_b_raw_results.jsonl", "stage_b_generation_metrics.json", "stage_b_provider_metrics.json",
        "stage_b_run_manifest.json", "STAGE_B_FROZEN.md",
    )
    if any((run.path / name).exists() for name in standard_outputs):
        raise FatalFormalRunError("Original outage attempt has standard B-finalized artifacts")
    run.verify_sealed("B")
    if _sha256(run.stage_path("B")) != ORIGINAL_STAGE_B_SHA256:
        raise FatalFormalRunError("Original sealed Stage B SHA256 mismatch")
    if _sha256(run.stage_manifest_path("B")) != ORIGINAL_STAGE_B_SEAL_MANIFEST_SHA256:
        raise FatalFormalRunError("Original Stage B seal-manifest SHA256 mismatch")
    if _sha256(run.path / "stage_b_execution_manifest.json") != ORIGINAL_STAGE_B_EXECUTION_MANIFEST_SHA256:
        raise FatalFormalRunError("Original Stage B execution-manifest SHA256 mismatch")
    seal = _load_json_object(run.stage_manifest_path("B"), label="original Stage B seal")
    if seal.get("sha256") != ORIGINAL_STAGE_B_SHA256 or seal.get("cell_count") != INTENDED_CELLS:
        raise FatalFormalRunError("Original Stage B seal does not match the outage anchor")
    _verify_original_stage_b_execution_history(repository_root, run)
    records = _validated_existing_stage_b_records(repository_root, run, stage_a)
    counts = _incident_counts(stage_a, records)
    expected = {
        "cell_count": INTENDED_CELLS,
        "completed_count": 106,
        "technical_failure_count": 86,
        "first_failure_position": 107,
        "first_failed_experiment_id": "western_formal_v0.1.2:westbench-v0.1-headache-03:R0",
        "consecutive_failure_suffix_count": 86,
        "successes_after_first_failure": 0,
        "final_error_counts": {"connectivity": 86},
        "first_error_counts": {"connectivity": 85, "timeout": 1},
        "failure_counts_by_condition": {"R0": 22, "R1": 22, "R2": 21, "R3": 21},
        "retry_used_failure_count": 86,
        "attempt_count_two_failure_count": 86,
        "provider_reported_model_count": INTENDED_CELLS,
    }
    mismatches = {key: {"expected": value, "actual": counts.get(key)} for key, value in expected.items() if counts.get(key) != value}
    if any(row.get("generation_outcome") != "technical_failure" for row in records[106:]):
        mismatches["failure_outcomes"] = {"expected": "86 technical_failure", "actual": "nontechnical outcome present"}
    if mismatches:
        raise FatalFormalRunError(f"Original Stage B outage pattern mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return stage_a, records, counts


def _incident_artifact_paths(run: RunDirectory) -> tuple[Path, Path]:
    return run.path / "stage_b_incident_manifest.json", run.path / "STAGE_B_OUTAGE_INCIDENT.md"


def finalize_stage_b_incident(
    repository_root: Path,
    run: RunDirectory,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    incident_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    anchor = verify_stage_b_repeat_execution_freeze(
        repository_root,
        expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree,
        execution_config=execution_config,
        incident_config=incident_config,
    )
    _, _, counts = _verify_original_stage_b_incident(repository_root, run)
    manifest_path, markdown_path = _incident_artifact_paths(run)
    if any(path.exists() or path.with_suffix(path.suffix + ".tmp").exists() for path in (manifest_path, markdown_path)):
        raise FileExistsError("Stage B incident preservation artifacts already exist; overwrite is prohibited")
    lines = [
        "# Stage B provider-outage incident", "", f"- Run ID: `{STAGE_A_RUN_ID}`",
        f"- Stage B SHA256: `{ORIGINAL_STAGE_B_SHA256}`", f"- Terminal cells: `{INTENDED_CELLS}`",
        "- Completed cells: `106`", "- Technical failures: `86`", "- First failure position: `107`",
        "- Consecutive failed suffix: `86`", "- Eligible as primary: `false`",
        "- Eligible for Stage C: `false`", "- Preservation only: `true`", "",
        "The attempt is preserved as an audited run-level provider-outage incident. It must not be resumed, standard-B-finalized, or used as primary Stage C input.", "",
    ]
    markdown_bytes = ("\n".join(lines)).encode("utf-8")
    markdown_sha = hashlib.sha256(markdown_bytes).hexdigest()
    manifest = {
        "status": "stage_b_outage_incident",
        "run_id": STAGE_A_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "stage_b_execution_freeze_commit": ORIGINAL_STAGE_B_EXECUTION_FREEZE_COMMIT,
        "stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "stage_b_seal_manifest_sha256": ORIGINAL_STAGE_B_SEAL_MANIFEST_SHA256,
        "stage_b_execution_manifest_sha256": ORIGINAL_STAGE_B_EXECUTION_MANIFEST_SHA256,
        "provider": GENERATOR_PROVIDER,
        "provider_reported_model": GENERATOR_MODEL,
        **counts,
        "eligible_as_primary": False,
        "eligible_for_stage_c": False,
        "preservation_only": True,
        "standard_b_finalized": False,
        "stage_c_executed": False,
        "repeat_execution_freeze_commit": anchor["execution_freeze_commit"],
        "repeat_execution_json_sha256": anchor["execution_json_sha256"],
        "incident_json_sha256": anchor["incident_json_sha256"],
        "incident_markdown_sha256": markdown_sha,
        "preserved_at": _utc_now(),
    }
    _atomic_new_bytes(markdown_path, markdown_bytes)
    _atomic_new_json(manifest_path, manifest)
    return {manifest_path.name: _sha256(manifest_path), markdown_path.name: _sha256(markdown_path)}


async def run_stage_b(
    repository_root: Path,
    run: RunDirectory,
    *,
    generator: Any | None = None,
    expected_cells: int = INTENDED_CELLS,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
) -> None:
    if run.stage_manifest_path("B").exists():
        raise FatalFormalRunError("Stage B is already sealed and immutable")
    if run.stage_path("C").exists() or run.stage_manifest_path("C").exists():
        raise FatalFormalRunError("Stage C artifacts exist before Stage B execution")
    if expected_cells == INTENDED_CELLS:
        anchor = verify_stage_b_execution_freeze(
            repository_root,
            expected_execution_commit=expected_execution_commit,
            require_clean_worktree=require_clean_worktree,
            execution_config=execution_config,
        )
        stage_a = verify_frozen_stage_a(repository_root, run)
    else:
        # Offline unit-test seam only; the CLI never changes the frozen 192-cell count.
        test_config = execution_config or {"implementation_sha256": {"test-only": "test-only"}}
        anchor = {
            **test_config,
            "execution_freeze_commit": expected_execution_commit or "test-only",
            "execution_json_sha256": hashlib.sha256(json.dumps(test_config, sort_keys=True).encode()).hexdigest(),
        }
        stage_a = _read_jsonl_strict(run.stage_path("A"), label="Stage A retrieval")
    stage_a_ids = {row["experiment_id"] for row in stage_a}
    existing = _validated_existing_stage_b_records(repository_root, run, stage_a)
    _ensure_stage_b_execution_manifest(run, anchor, allow_create=not existing)
    if len(existing) == INTENDED_CELLS:
        run.seal("B", expected_cells=INTENDED_CELLS, expected_experiment_ids=stage_a_ids)
        return
    active_generator = generator
    for retrieval in stage_a[len(existing):]:
        provenance = _expected_provenance(retrieval)
        if not retrieval.get("retrieval_success", True):
            record = {
                "experiment_id": retrieval["experiment_id"],
                "first_attempt_success": False,
                "attempt_count": 0,
                "technical_retry_used": False,
                "first_error_type": "upstream_retrieval_technical_failure",
                "generation_success": False,
                "final_generation_success": False,
                "generation_outcome": "upstream_retrieval_technical_failure",
                "generation_latency_ms": 0.0,
                "answer": "",
                "provenance": provenance,
                "provider_reported_model": None,
                "final_error_type": "upstream_retrieval_technical_failure",
                "errors": [{"error_type": "upstream_retrieval_technical_failure", "message": "Generator not called because Stage A retrieval terminated as technical_failure"}],
                "timestamps": {"generation_completed_at": _utc_now()},
            }
            _validate_stage_b_record(repository_root, retrieval, record)
            run.append("B", record)
            continue
        if active_generator is None:
            active_generator = build_llm_provider(GENERATOR_MODEL, timeout_override=GENERATOR_TIMEOUT_SECONDS)
        _validate_formal_generator(active_generator)
        evidence = _retrieval_evidence(retrieval["retrieved_items"], retrieval["topic"])
        prompt = _generation_prompt(retrieval["question"] if "question" in retrieval else "", retrieval["topic"], evidence)

        async def operation() -> Any:
            result = await active_generator.generate(
                system=SYSTEM_PROMPT,
                prompt=prompt,
                temperature=GENERATOR_TEMPERATURE,
                max_tokens=GENERATOR_MAX_TOKENS,
            )
            return result, _validated_answer(result.text)

        outcome = await invoke_stage_b_generation(operation)
        generated = outcome.provider_result
        record = {
            "experiment_id": retrieval["experiment_id"],
            "first_attempt_success": outcome.first_attempt_success,
            "attempt_count": outcome.attempt_count,
            "technical_retry_used": outcome.technical_retry_used,
            "first_error_type": outcome.first_error_type,
            "final_error_type": outcome.final_error_type,
            "generation_success": outcome.generation_success,
            "final_generation_success": outcome.generation_success,
            "generation_outcome": outcome.generation_outcome,
            "generation_latency_ms": outcome.elapsed_ms,
            "answer": outcome.answer,
            "provenance": provenance,
            "provider_reported_model": generated.model if generated else GENERATOR_MODEL,
            "errors": outcome.errors,
            "timestamps": {"generation_completed_at": _utc_now()},
        }
        _validate_stage_b_record(repository_root, retrieval, record)
        run.append("B", record)
    if expected_cells != INTENDED_CELLS:
        run.seal("B", expected_cells=expected_cells, expected_experiment_ids={row["experiment_id"] for row in stage_a[:expected_cells]})
    else:
        final_records = _validated_existing_stage_b_records(repository_root, run, stage_a)
        if len(final_records) != INTENDED_CELLS:
            raise FatalFormalRunError("Stage B did not reach 192 terminal cells")
        run.seal("B", expected_cells=INTENDED_CELLS, expected_experiment_ids=stage_a_ids)


def _canonical_stage_a_run(repository_root: Path) -> RunDirectory:
    return RunDirectory(
        repository_root / "research/experiments/western_formal_v0_1/runs" / STAGE_A_RUN_ID
    )


def _verify_incident_preservation_artifacts(repository_root: Path, original_run: RunDirectory) -> dict[str, Any]:
    _verify_original_stage_b_incident(repository_root, original_run)
    manifest_path, markdown_path = _incident_artifact_paths(original_run)
    manifest = _load_json_object(manifest_path, label="Stage B incident preservation manifest")
    expected = {
        "status": "stage_b_outage_incident",
        "run_id": STAGE_A_RUN_ID,
        "stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "eligible_as_primary": False,
        "eligible_for_stage_c": False,
        "preservation_only": True,
        "standard_b_finalized": False,
        "stage_c_executed": False,
    }
    mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
    if not markdown_path.is_file() or manifest.get("incident_markdown_sha256") != _sha256(markdown_path):
        mismatches["incident_markdown_sha256"] = {"expected": manifest.get("incident_markdown_sha256"), "actual": _sha256(markdown_path) if markdown_path.is_file() else None}
    if mismatches:
        raise FatalFormalRunError(f"Stage B incident preservation artifact mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return manifest


def _validate_repeat_provider(provider: Any) -> None:
    _validate_formal_generator(provider)
    if hasattr(provider, "timeout") and float(provider.timeout) != GENERATOR_TIMEOUT_SECONDS:
        raise FatalFormalRunError("Stage B repeat provider timeout configuration mismatch")
    if hasattr(provider, "max_tokens") and int(provider.max_tokens) < GENERATOR_MAX_TOKENS:
        raise FatalFormalRunError("Stage B repeat provider effective max_tokens is below the frozen value")


def _readiness_path(repeat: StageBRepeatDirectory) -> Path:
    return repeat.path / "stage_b_repeat_readiness_manifest.json"


async def run_stage_b_repeat_readiness(
    repository_root: Path,
    repeat: StageBRepeatDirectory,
    *,
    provider: Any | None = None,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    incident_config: dict[str, Any] | None = None,
    original_run: RunDirectory | None = None,
) -> dict[str, Any]:
    anchor = verify_stage_b_repeat_execution_freeze(
        repository_root,
        expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree,
        execution_config=execution_config,
        incident_config=incident_config,
    )
    incident_run = original_run or _canonical_stage_a_run(repository_root)
    incident_manifest = _verify_incident_preservation_artifacts(repository_root, incident_run)
    if repeat.path.exists():
        conflicts = [path for path in repeat.path.iterdir() if path.name != _readiness_path(repeat).name]
        if conflicts or _readiness_path(repeat).exists():
            raise FatalFormalRunError("Stage B repeat readiness requires a new conflict-free repeat directory")
    active_provider = provider or build_llm_provider(GENERATOR_MODEL, timeout_override=GENERATOR_TIMEOUT_SECONDS)
    _validate_repeat_provider(active_provider)
    probes: list[dict[str, Any]] = []
    for probe_number in range(1, STAGE_B_READINESS_PROBES + 1):
        started = perf_counter()
        try:
            result = await active_provider.generate(
                system="Operational provider readiness probe; do not provide additional text.",
                prompt=STAGE_B_READINESS_PROMPT,
                temperature=GENERATOR_TEMPERATURE,
                max_tokens=STAGE_B_READINESS_MAX_TOKENS,
            )
        except Exception as exc:
            raise FatalFormalRunError(f"Stage B repeat readiness probe {probe_number} failed: {type(exc).__name__}") from exc
        normalized = str(getattr(result, "text", "")).strip()
        if normalized != "READY":
            raise FatalFormalRunError(f"Stage B repeat readiness probe {probe_number} did not return READY")
        if getattr(result, "model", GENERATOR_MODEL) != GENERATOR_MODEL:
            raise FatalFormalRunError("Stage B repeat readiness provider-reported model mismatch")
        probes.append({
            "probe": probe_number,
            "success": True,
            "normalized_text": normalized,
            "provider_reported_model": getattr(result, "model", GENERATOR_MODEL),
            "latency_ms": round((perf_counter() - started) * 1000, 3),
        })
        if probe_number < STAGE_B_READINESS_PROBES:
            await sleep(STAGE_B_READINESS_INTERVAL_SECONDS)
    payload = {
        "status": "passed",
        "formal_data": False,
        "run_id": STAGE_B_REPEAT_RUN_ID,
        "execution_version": STAGE_B_REPEAT_EXECUTION_VERSION,
        "execution_freeze_commit": anchor["execution_freeze_commit"],
        "execution_json_sha256": anchor["execution_json_sha256"],
        "incident_manifest_sha256": _sha256(incident_run.path / "stage_b_incident_manifest.json"),
        "provider": GENERATOR_PROVIDER,
        "model": GENERATOR_MODEL,
        "prompt": STAGE_B_READINESS_PROMPT,
        "temperature": GENERATOR_TEMPERATURE,
        "max_tokens": STAGE_B_READINESS_MAX_TOKENS,
        "timeout_seconds": GENERATOR_TIMEOUT_SECONDS,
        "probe_interval_seconds": STAGE_B_READINESS_INTERVAL_SECONDS,
        "probe_count": STAGE_B_READINESS_PROBES,
        "probes": probes,
        "passed_at": _utc_now(),
        "readiness_outputs_excluded_from_formal_jsonl": True,
        "original_incident_eligible_for_stage_c": incident_manifest["eligible_for_stage_c"],
    }
    _atomic_new_json(_readiness_path(repeat), payload)
    return payload


def _validate_repeat_readiness(repeat: StageBRepeatDirectory, anchor: dict[str, Any], incident_manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = _load_json_object(_readiness_path(repeat), label="Stage B repeat readiness manifest")
    expected = {
        "status": "passed",
        "formal_data": False,
        "run_id": STAGE_B_REPEAT_RUN_ID,
        "execution_version": STAGE_B_REPEAT_EXECUTION_VERSION,
        "execution_freeze_commit": anchor["execution_freeze_commit"],
        "execution_json_sha256": anchor["execution_json_sha256"],
        "incident_manifest_sha256": str(incident_manifest["_sha256"]),
        "provider": GENERATOR_PROVIDER,
        "model": GENERATOR_MODEL,
        "prompt": STAGE_B_READINESS_PROMPT,
        "temperature": GENERATOR_TEMPERATURE,
        "max_tokens": STAGE_B_READINESS_MAX_TOKENS,
        "timeout_seconds": GENERATOR_TIMEOUT_SECONDS,
        "probe_interval_seconds": STAGE_B_READINESS_INTERVAL_SECONDS,
        "probe_count": STAGE_B_READINESS_PROBES,
        "readiness_outputs_excluded_from_formal_jsonl": True,
        "original_incident_eligible_for_stage_c": False,
    }
    mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
    probes = manifest.get("probes")
    if not isinstance(probes, list) or len(probes) != STAGE_B_READINESS_PROBES or any(
        probe.get("success") is not True or probe.get("normalized_text") != "READY" for probe in probes if isinstance(probe, dict)
    ) or any(not isinstance(probe, dict) for probe in probes or []):
        mismatches["probes"] = {"expected": "three successful READY probes", "actual": probes}
    if mismatches:
        raise FatalFormalRunError(f"Stage B repeat readiness manifest mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return manifest


def _repeat_execution_manifest_payload(
    repeat: StageBRepeatDirectory,
    anchor: dict[str, Any],
    readiness_sha256: str,
    incident_manifest_sha256: str,
) -> dict[str, Any]:
    return {
        "stage": "B-repeat",
        "status": "in_progress",
        "run_id": STAGE_B_REPEAT_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "parent_stage_a_run_id": STAGE_A_RUN_ID,
        "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "supersedes_stage_b_attempt_run_id": STAGE_A_RUN_ID,
        "superseded_stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "repeat_ordinal": 1,
        "repeat_reason": "provider_outage",
        "repeat_scope": "all_192_cells",
        "reuse_original_successes": False,
        "primary_semantic_dataset": True,
        "stage_b_repeat_execution_version": STAGE_B_REPEAT_EXECUTION_VERSION,
        "stage_b_repeat_execution_freeze_commit": anchor["execution_freeze_commit"],
        "stage_b_repeat_execution_json_sha256": anchor["execution_json_sha256"],
        "incident_json_sha256": anchor["incident_json_sha256"],
        "incident_manifest_sha256": incident_manifest_sha256,
        "readiness_manifest_sha256": readiness_sha256,
        "implementation_sha256": anchor["implementation_sha256"],
        "created_at": _utc_now(),
    }


def _ensure_repeat_execution_manifest(
    repeat: StageBRepeatDirectory,
    anchor: dict[str, Any],
    readiness_sha256: str,
    incident_manifest_sha256: str,
    *,
    allow_create: bool,
) -> dict[str, Any]:
    path = repeat.path / "stage_b_repeat_execution_manifest.json"
    if not path.exists():
        if not allow_create:
            raise FatalFormalRunError("Stage B repeat rows exist without a repeat execution manifest")
        _atomic_new_json(path, _repeat_execution_manifest_payload(repeat, anchor, readiness_sha256, incident_manifest_sha256))
    manifest = _load_json_object(path, label="Stage B repeat execution manifest")
    expected = _repeat_execution_manifest_payload(repeat, anchor, readiness_sha256, incident_manifest_sha256)
    expected.pop("created_at")
    mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
    if mismatches:
        raise FatalFormalRunError(f"Stage B repeat execution manifest mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return manifest


def _validated_existing_repeat_records(
    repository_root: Path,
    repeat: StageBRepeatDirectory,
    stage_a: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = _read_jsonl_strict(repeat.stage_path(), label="Stage B repeat generation")
    if len(records) > INTENDED_CELLS:
        raise FatalFormalRunError("Stage B repeat contains more than 192 rows")
    ids = [row.get("experiment_id") for row in records]
    if len(ids) != len(set(ids)):
        raise FatalFormalRunError("Stage B repeat contains duplicate experiment IDs")
    expected_ids = [row["experiment_id"] for row in stage_a]
    foreign = [cell_id for cell_id in ids if cell_id not in set(expected_ids)]
    if foreign:
        raise FatalFormalRunError(f"Stage B repeat contains foreign experiment IDs: {foreign[:3]}")
    if ids != expected_ids[:len(ids)]:
        raise FatalFormalRunError("Stage B repeat rows are not a valid frozen-order prefix")
    stage_a_by_id = {row["experiment_id"]: row for row in stage_a}
    for record in records:
        _validate_stage_b_record(repository_root, stage_a_by_id[record["experiment_id"]], record)
    return records


def _reject_unexpected_repeat_files(repeat: StageBRepeatDirectory, *, finalizing: bool = False) -> None:
    if not repeat.path.exists():
        return
    allowed = {
        "stage_b_repeat_readiness_manifest.json",
        "stage_b_repeat_execution_manifest.json",
        "stage_b_generation.jsonl",
    }
    if finalizing:
        allowed.add("stage_b_manifest.json")
    unexpected = sorted(path.name for path in repeat.path.iterdir() if path.name not in allowed)
    if unexpected:
        raise FatalFormalRunError(f"Stage B repeat directory contains conflicting outputs: {unexpected}")


async def run_stage_b_repeat(
    repository_root: Path,
    repeat: StageBRepeatDirectory,
    *,
    generator: Any | None = None,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    incident_config: dict[str, Any] | None = None,
    original_run: RunDirectory | None = None,
) -> None:
    if repeat.stage_manifest_path().exists():
        raise FatalFormalRunError("Stage B repeat is already sealed and immutable")
    _reject_unexpected_repeat_files(repeat)
    if (repeat.path / "stage_c_judge.jsonl").exists() or (repeat.path / "stage_c_manifest.json").exists():
        raise FatalFormalRunError("Stage C artifacts exist before Stage B repeat execution")
    anchor = verify_stage_b_repeat_execution_freeze(
        repository_root,
        expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree,
        execution_config=execution_config,
        incident_config=incident_config,
    )
    incident_run = original_run or _canonical_stage_a_run(repository_root)
    incident_manifest = _verify_incident_preservation_artifacts(repository_root, incident_run)
    incident_manifest = {**incident_manifest, "_sha256": _sha256(incident_run.path / "stage_b_incident_manifest.json")}
    stage_a = verify_frozen_stage_a(repository_root, incident_run)
    readiness = _validate_repeat_readiness(repeat, anchor, incident_manifest)
    readiness_sha = _sha256(_readiness_path(repeat))
    existing = _validated_existing_repeat_records(repository_root, repeat, stage_a)
    _ensure_repeat_execution_manifest(
        repeat, anchor, readiness_sha, incident_manifest["_sha256"], allow_create=not existing,
    )
    expected_ids = [row["experiment_id"] for row in stage_a]
    if len(existing) == INTENDED_CELLS:
        repeat.seal(expected_ids)
        return
    active_generator = generator
    for retrieval in stage_a[len(existing):]:
        provenance = _expected_provenance(retrieval)
        if not retrieval.get("retrieval_success", True):
            record = {
                "experiment_id": retrieval["experiment_id"], "first_attempt_success": False,
                "attempt_count": 0, "technical_retry_used": False,
                "first_error_type": "upstream_retrieval_technical_failure",
                "final_error_type": "upstream_retrieval_technical_failure",
                "generation_success": False, "final_generation_success": False,
                "generation_outcome": "upstream_retrieval_technical_failure",
                "generation_latency_ms": 0.0, "answer": "", "provenance": provenance,
                "provider_reported_model": None,
                "errors": [{"error_type": "upstream_retrieval_technical_failure", "message": "Generator not called because frozen Stage A retrieval failed"}],
                "timestamps": {"generation_completed_at": _utc_now()},
            }
        else:
            if active_generator is None:
                active_generator = build_llm_provider(GENERATOR_MODEL, timeout_override=GENERATOR_TIMEOUT_SECONDS)
            _validate_repeat_provider(active_generator)
            evidence = _retrieval_evidence(retrieval["retrieved_items"], retrieval["topic"])
            prompt = _generation_prompt(retrieval.get("question", ""), retrieval["topic"], evidence)

            async def operation() -> Any:
                result = await active_generator.generate(
                    system=SYSTEM_PROMPT, prompt=prompt,
                    temperature=GENERATOR_TEMPERATURE, max_tokens=GENERATOR_MAX_TOKENS,
                )
                return result, _validated_answer(result.text)

            outcome = await invoke_stage_b_generation(operation)
            generated = outcome.provider_result
            record = {
                "experiment_id": retrieval["experiment_id"],
                "first_attempt_success": outcome.first_attempt_success,
                "attempt_count": outcome.attempt_count,
                "technical_retry_used": outcome.technical_retry_used,
                "first_error_type": outcome.first_error_type,
                "final_error_type": outcome.final_error_type,
                "generation_success": outcome.generation_success,
                "final_generation_success": outcome.generation_success,
                "generation_outcome": outcome.generation_outcome,
                "generation_latency_ms": outcome.elapsed_ms,
                "answer": outcome.answer,
                "provenance": provenance,
                "provider_reported_model": generated.model if generated else GENERATOR_MODEL,
                "errors": outcome.errors,
                "timestamps": {"generation_completed_at": _utc_now()},
            }
        _validate_stage_b_record(repository_root, retrieval, record)
        repeat.append("B", record)
    final_records = _validated_existing_repeat_records(repository_root, repeat, stage_a)
    if len(final_records) != INTENDED_CELLS:
        raise FatalFormalRunError("Stage B repeat did not reach 192 terminal cells")
    repeat.seal(expected_ids)


def classify_stage_b_repeat_outage(records: list[dict[str, Any]]) -> dict[str, Any]:
    suffix: list[dict[str, Any]] = []
    for row in reversed(records):
        final_error = row.get("final_error_type")
        if row.get("generation_success") is True or final_error not in STAGE_B_REPEAT_INFRASTRUCTURE_ERRORS:
            break
        suffix.append(row)
    suffix.reverse()
    is_outage = len(suffix) >= STAGE_B_REPEAT_OUTAGE_MIN_SUFFIX
    return {
        "run_level_outage": is_outage,
        "consecutive_infrastructure_failure_suffix_count": len(suffix),
        "first_outage_experiment_id": suffix[0].get("experiment_id") if suffix else None,
        "final_error_types": sorted({str(row.get("final_error_type")) for row in suffix}),
        "minimum_suffix_threshold": STAGE_B_REPEAT_OUTAGE_MIN_SUFFIX,
        "no_subsequent_success": bool(suffix),
        "third_attempt_automatically_authorized": False,
    }


def _canonical_primary_stage_b_repeat(repository_root: Path) -> StageBRepeatDirectory:
    return StageBRepeatDirectory(
        repository_root / "research/experiments/western_formal_v0_1/runs" / STAGE_B_REPEAT_RUN_ID
    )


def _verify_primary_stage_b_inputs(
    repository_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    original = _canonical_stage_a_run(repository_root)
    incident = _verify_incident_preservation_artifacts(repository_root, original)
    if _sha256(original.path / "stage_b_incident_manifest.json") != PRIMARY_STAGE_B_INCIDENT_MANIFEST_SHA256:
        raise FatalFormalRunError("Original Stage B incident manifest SHA256 mismatch")
    if incident.get("eligible_as_primary") is not False or incident.get("eligible_for_stage_c") is not False or incident.get("preservation_only") is not True:
        raise FatalFormalRunError("Original Stage B attempt is not preserved as incident-only")
    stage_a = verify_frozen_stage_a(repository_root, original)
    repeat = _canonical_primary_stage_b_repeat(repository_root)
    repeat.verify_sealed()
    expected_hashes = {
        "stage_b_generation.jsonl": PRIMARY_STAGE_B_SHA256,
        "stage_b_manifest.json": PRIMARY_STAGE_B_SEAL_SHA256,
        "stage_b_raw_results.jsonl": PRIMARY_STAGE_B_SHA256,
        "stage_b_generation_metrics.json": PRIMARY_STAGE_B_GENERATION_METRICS_SHA256,
        "stage_b_provider_metrics.json": PRIMARY_STAGE_B_PROVIDER_METRICS_SHA256,
        "stage_b_repeat_execution_manifest.json": PRIMARY_STAGE_B_EXECUTION_MANIFEST_SHA256,
        "stage_b_repeat_readiness_manifest.json": PRIMARY_STAGE_B_READINESS_MANIFEST_SHA256,
        "stage_b_run_manifest.json": PRIMARY_STAGE_B_RUN_MANIFEST_SHA256,
    }
    mismatches: dict[str, Any] = {}
    for name, expected_hash in expected_hashes.items():
        path = repeat.path / name
        actual = _sha256(path) if path.is_file() else None
        if actual != expected_hash:
            mismatches[name] = {"expected": expected_hash, "actual": actual}
    manifest = _load_json_object(repeat.path / "stage_b_run_manifest.json", label="primary Stage B run manifest")
    expected_manifest = {
        "run_id": STAGE_B_REPEAT_RUN_ID,
        "status": "stage_b_repeat_frozen_primary",
        "eligible_as_primary": True,
        "eligible_for_stage_c": True,
        "primary_semantic_dataset": True,
        "repeat_scope": "all_192_cells",
        "reuse_original_successes": False,
        "stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        "parent_stage_a_run_id": STAGE_A_RUN_ID,
        "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "repeat_execution_freeze_commit": "d68df8018798219b2bcf8dd36ee067dedbf66dfc",
        "repeat_execution_json_sha256": "de06ad2c834c287fa0d6715c45c56c26147fdc9ee697f68d7fa2d78a314e2617",
        "incident_manifest_sha256": PRIMARY_STAGE_B_INCIDENT_MANIFEST_SHA256,
        "readiness_manifest_sha256": PRIMARY_STAGE_B_READINESS_MANIFEST_SHA256,
    }
    mismatches.update({
        f"manifest.{key}": {"expected": value, "actual": manifest.get(key)}
        for key, value in expected_manifest.items() if manifest.get(key) != value
    })
    outage = manifest.get("repeat_outage_classification")
    if not isinstance(outage, dict) or outage.get("run_level_outage") is not False:
        mismatches["manifest.repeat_outage_classification.run_level_outage"] = {"expected": False, "actual": outage}
    if mismatches:
        raise FatalFormalRunError(f"Primary Stage B input mismatch: {json.dumps(mismatches, sort_keys=True)}")
    records = _validated_existing_repeat_records(repository_root, repeat, stage_a)
    expected_ids = [row["experiment_id"] for row in stage_a]
    if len(records) != INTENDED_CELLS or [row.get("experiment_id") for row in records] != expected_ids:
        raise FatalFormalRunError("Primary Stage B does not contain the exact ordered 192 Stage A IDs")
    return stage_a, records, manifest


class StageCOutputSchemaError(ValueError):
    """A non-retryable model-output contract failure."""


def _validate_completed_judge_output(parsed: FormalJudgeOutput, retrieval: dict[str, Any]) -> None:
    if not parsed.claim_labels:
        raise StageCOutputSchemaError("Completed non-empty answer requires at least one claim label")
    claim_ids = [item.claim_id for item in parsed.claim_labels]
    if len(claim_ids) != len(set(claim_ids)):
        raise StageCOutputSchemaError("Claim IDs must be unique")
    expected_points = list(retrieval.get("expected_evidence_points") or [])
    point_indices = [item.point_index for item in parsed.evidence_point_labels]
    if point_indices != list(range(len(expected_points))):
        raise StageCOutputSchemaError("Evidence-point indices must equal exactly 0..n-1 in order")
    scope = (
        parsed.stays_within_supported_evidence,
        parsed.preserves_uncertainty,
        parsed.invented_unsupported_information,
    )
    if retrieval.get("answerability") == "partially_supported":
        if any(value is None for value in scope):
            raise StageCOutputSchemaError("Partially-supported cases require all three scope Booleans")
    elif any(value is not None for value in scope):
        raise StageCOutputSchemaError("Non-partially-supported cases require null scope fields")
    if retrieval.get("answerability") == "insufficient":
        if parsed.insufficiency_label == "not_applicable":
            raise StageCOutputSchemaError("Successful insufficient judgment cannot be not_applicable")
    elif parsed.insufficiency_label != "not_applicable":
        raise StageCOutputSchemaError("Non-insufficient judgment must use not_applicable")


def _validate_formal_judge_provider(judge: Any) -> None:
    if getattr(judge, "name", None) != JUDGE_PROVIDER or getattr(judge, "model", None) != JUDGE_MODEL:
        raise FatalFormalRunError("Stage C judge provider/model configuration mismatch")
    try:
        timeout = float(judge.timeout)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FatalFormalRunError("Stage C judge timeout configuration mismatch") from exc
    if timeout != JUDGE_TIMEOUT_SECONDS:
        raise FatalFormalRunError("Stage C judge timeout configuration mismatch")
    try:
        max_tokens = int(judge.max_tokens)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FatalFormalRunError("Stage C judge effective max_tokens is below the frozen value") from exc
    if max_tokens < JUDGE_MAX_TOKENS:
        raise FatalFormalRunError("Stage C judge effective max_tokens is below the frozen value")
    if getattr(judge, "enable_thinking", None) is not False:
        raise FatalFormalRunError("Stage C judge must use enable_thinking=false")
    api_key = getattr(judge, "api_key", None)
    if not isinstance(api_key, str) or not api_key.strip():
        raise FatalFormalRunError("Stage C judge API credential is missing")


@dataclass
class StageCJudgeOutcome:
    judge_success: bool
    judge_outcome: str
    parsed: FormalJudgeOutput | None
    provider_result: Any | None
    output_normalization: str | None
    first_attempt_success: bool
    attempt_count: int
    technical_retry_used: bool
    first_error_type: str | None
    final_error_type: str | None
    errors: list[dict[str, Any]]
    elapsed_ms: float


async def invoke_stage_c_judgment(
    operation: Callable[[], Awaitable[Any]], retrieval: dict[str, Any],
) -> StageCJudgeOutcome:
    started = perf_counter()
    errors: list[dict[str, Any]] = []
    first_error: str | None = None
    for attempt in (1, 2):
        try:
            result = await operation()
        except ProviderUnavailable as exc:
            kind = _error_type(exc)
            status = getattr(exc, "http_status", None)
            if kind in {"configuration", "authentication"} or (kind == "http_4xx" and status in {401, 403}):
                raise FatalFormalRunError(f"Fatal Stage C provider configuration/authentication failure: {kind}") from exc
            if first_error is None:
                first_error = kind
            errors.append({"attempt": attempt, "error_type": kind, "message": str(exc)})
            if kind == "rate_limit":
                return StageCJudgeOutcome(False, "rate_limit", None, None, None, False, attempt, attempt == 2, first_error, kind, errors, round((perf_counter() - started) * 1000, 3))
            if kind not in RETRYABLE_ERROR_TYPES:
                return StageCJudgeOutcome(False, "nonretryable_provider_failure", None, None, None, False, attempt, attempt == 2, first_error, kind, errors, round((perf_counter() - started) * 1000, 3))
            if attempt == 2:
                return StageCJudgeOutcome(False, "technical_failure", None, None, None, False, 2, True, first_error, kind, errors, round((perf_counter() - started) * 1000, 3))
            continue
        except Exception as exc:
            raise FatalFormalRunError(f"Unexpected Stage C programming/runtime defect: {type(exc).__name__}") from exc
        if getattr(result, "model", None) != JUDGE_MODEL:
            raise FatalFormalRunError("Stage C provider-reported model mismatch")
        finish_reason = getattr(result, "finish_reason", None)
        if finish_reason == "length":
            errors.append({"attempt": attempt, "error_type": "truncated_response", "message": "provider finish_reason=length"})
            return StageCJudgeOutcome(False, "truncated_response", None, result, None, False, attempt, attempt == 2, first_error, "truncated_response", errors, round((perf_counter() - started) * 1000, 3))
        if finish_reason not in {None, "stop"}:
            errors.append({"attempt": attempt, "error_type": "unexpected_finish_reason", "message": f"provider finish_reason={finish_reason}"})
            return StageCJudgeOutcome(False, "nonretryable_provider_failure", None, result, None, False, attempt, attempt == 2, first_error, "unexpected_finish_reason", errors, round((perf_counter() - started) * 1000, 3))
        normalization: str | None = None
        try:
            normalized_text, normalization = normalize_judge_json_envelope(result.text)
            parsed = parse_judge_output(normalized_text)
            _validate_completed_judge_output(parsed, retrieval)
        except (ValueError, StageCOutputSchemaError) as exc:
            errors.append({"attempt": attempt, "error_type": "output_schema_failure", "message": str(exc)})
            return StageCJudgeOutcome(False, "output_schema_failure", None, result, normalization, False, attempt, attempt == 2, first_error, "output_schema_failure", errors, round((perf_counter() - started) * 1000, 3))
        return StageCJudgeOutcome(True, "completed", parsed, result, normalization, attempt == 1, attempt, attempt == 2, first_error, None, errors, round((perf_counter() - started) * 1000, 3))
    raise AssertionError("unreachable")


def _stage_c_execution_manifest_payload(anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": "C", "status": "in_progress", "run_id": STAGE_C_RUN_ID,
        "protocol_version": PROTOCOL_VERSION, "protocol_sha256": PROTOCOL_SHA256,
        "parent_stage_a_run_id": STAGE_A_RUN_ID,
        "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "parent_stage_b_run_id": STAGE_B_REPEAT_RUN_ID,
        "parent_stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        "stage_c_execution_version": STAGE_C_EXECUTION_VERSION,
        "stage_c_execution_freeze_commit": anchor["execution_freeze_commit"],
        "stage_c_execution_json_sha256": anchor["execution_json_sha256"],
        "analysis_json_sha256": anchor["analysis_json_sha256"],
        "normalization_policy_version": anchor["normalization_policy_version"],
        "implementation_sha256": anchor["implementation_sha256"],
        "created_at": _utc_now(),
    }


def _ensure_stage_c_execution_manifest(stage_c: StageCDirectory, anchor: dict[str, Any], *, allow_create: bool) -> dict[str, Any]:
    path = stage_c.execution_manifest_path()
    if not path.exists():
        if not allow_create:
            raise FatalFormalRunError("Stage C rows exist without an execution manifest")
        _atomic_new_json(path, _stage_c_execution_manifest_payload(anchor))
    manifest = _load_json_object(path, label="Stage C execution manifest")
    expected = _stage_c_execution_manifest_payload(anchor)
    expected.pop("created_at")
    mismatches = {key: {"expected": value, "actual": manifest.get(key)} for key, value in expected.items() if manifest.get(key) != value}
    if mismatches:
        raise FatalFormalRunError(f"Stage C execution manifest mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return manifest


def _empty_stage_c_semantics() -> dict[str, Any]:
    return {
        "claim_labels": [], "evidence_point_labels": [], "insufficiency_label": "not_applicable",
        "stays_within_supported_evidence": None, "preserves_uncertainty": None,
        "invented_unsupported_information": None, "observable_safety_flags": {},
    }


def _validate_stage_c_record(retrieval: dict[str, Any], generation: dict[str, Any], record: dict[str, Any]) -> None:
    required = {
        "experiment_id", "judge_success", "final_judge_success", "judge_outcome",
        "judge_first_attempt_success", "judge_attempt_count", "judge_technical_retry_used",
        "judge_first_error_type", "judge_final_error_type", "judge_provider_reported_model",
        "judge_finish_reason", "judge_latency_ms", "judge_output_normalization",
        "claim_labels", "evidence_point_labels",
        "insufficiency_label", "stays_within_supported_evidence", "preserves_uncertainty",
        "invented_unsupported_information", "observable_safety_flags", "upstream_failure",
        "errors", "timestamps",
    }
    if not required.issubset(record):
        raise FatalFormalRunError(f"Stage C record missing fields: {sorted(required - set(record))}")
    if record.get("experiment_id") != retrieval.get("experiment_id") or record.get("experiment_id") != generation.get("experiment_id"):
        raise FatalFormalRunError("Stage C record ID does not match frozen Stage A/B")
    outcome = record.get("judge_outcome")
    if outcome not in STAGE_C_OUTCOMES:
        raise FatalFormalRunError(f"Invalid Stage C terminal outcome: {outcome}")
    success = record.get("judge_success") is True and record.get("final_judge_success") is True
    if success != (outcome == "completed"):
        raise FatalFormalRunError("Stage C success flags disagree with outcome")
    normalization = record.get("judge_output_normalization")
    if normalization not in {None, "none", "outer_json_markdown_fence_removed"}:
        raise FatalFormalRunError("Invalid Stage C judge output normalization value")
    if success and normalization is None:
        raise FatalFormalRunError("Completed Stage C record requires output normalization metadata")
    if outcome not in {"completed", "output_schema_failure"} and normalization is not None:
        raise FatalFormalRunError("Stage C failure without model-output parsing requires null normalization")
    attempts = record.get("judge_attempt_count")
    if outcome.startswith("upstream_"):
        if attempts != 0 or record.get("judge_technical_retry_used") is not False or not isinstance(record.get("upstream_failure"), dict):
            raise FatalFormalRunError("Invalid upstream Stage C missingness record")
    elif attempts not in {1, 2} or record.get("upstream_failure") is not None:
        raise FatalFormalRunError("Stage C judge attempt count/upstream metadata is invalid")
    if outcome == "technical_failure" and (attempts != 2 or record.get("judge_technical_retry_used") is not True):
        raise FatalFormalRunError("Stage C technical failure must exhaust the one retry")
    if success:
        parsed = FormalJudgeOutput.model_validate({
            "claim_labels": record["claim_labels"], "evidence_point_labels": record["evidence_point_labels"],
            "insufficiency_label": record["insufficiency_label"],
            "stays_within_supported_evidence": record["stays_within_supported_evidence"],
            "preserves_uncertainty": record["preserves_uncertainty"],
            "invented_unsupported_information": record["invented_unsupported_information"],
            **record["observable_safety_flags"],
        })
        _validate_completed_judge_output(parsed, retrieval)
        if record.get("judge_provider_reported_model") != JUDGE_MODEL:
            raise FatalFormalRunError("Completed Stage C record has wrong provider-reported model")
    elif any((record.get("claim_labels"), record.get("evidence_point_labels"), record.get("observable_safety_flags"))):
        raise FatalFormalRunError("Unsuccessful Stage C record must contain no semantic labels")


def _validated_existing_stage_c_records(
    stage_c: StageCDirectory, stage_a: list[dict[str, Any]], stage_b: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = _read_jsonl_strict(stage_c.stage_path(), label="Stage C judgments")
    if len(records) > INTENDED_CELLS:
        raise FatalFormalRunError("Stage C contains more than 192 rows")
    ids = [row.get("experiment_id") for row in records]
    expected_ids = [row["experiment_id"] for row in stage_b]
    if len(ids) != len(set(ids)):
        raise FatalFormalRunError("Stage C contains duplicate experiment IDs")
    foreign = [cell_id for cell_id in ids if cell_id not in set(expected_ids)]
    if foreign:
        raise FatalFormalRunError(f"Stage C contains foreign experiment IDs: {foreign[:3]}")
    if ids != expected_ids[:len(ids)]:
        raise FatalFormalRunError("Stage C rows are not an exact primary Stage B prefix")
    a_by_id = {row["experiment_id"]: row for row in stage_a}
    b_by_id = {row["experiment_id"]: row for row in stage_b}
    for record in records:
        _validate_stage_c_record(a_by_id[record["experiment_id"]], b_by_id[record["experiment_id"]], record)
    return records


def _verify_stage_c_r2_incident_source(
    repository_root: Path, stage_c: StageCDirectory,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if stage_c.path.name != STAGE_C_RUN_ID:
        raise FatalFormalRunError("Stage C r2 incident preservation requires the exact r2 run ID")
    if stage_c.stage_manifest_path().exists():
        raise FatalFormalRunError("Stage C r2 incident must not have an ordinary Stage C seal")
    expected_hashes = {
        stage_c.stage_path(): STAGE_C_R2_JUDGMENTS_SHA256,
        stage_c.execution_manifest_path(): STAGE_C_R2_EXECUTION_MANIFEST_SHA256,
    }
    mismatches: dict[str, Any] = {}
    for path, expected in expected_hashes.items():
        actual = _sha256(path) if path.is_file() else None
        if actual != expected:
            mismatches[path.name] = {"expected": expected, "actual": actual}
    execution = _load_json_object(stage_c.execution_manifest_path(), label="Stage C r2 execution manifest")
    expected_execution = {
        "stage": "C", "status": "in_progress", "run_id": STAGE_C_RUN_ID,
        "stage_c_execution_version": STAGE_C_EXECUTION_VERSION,
        "stage_c_execution_freeze_commit": STAGE_C_R2_EXECUTION_FREEZE_COMMIT,
        "stage_c_execution_json_sha256": STAGE_C_R2_EXECUTION_JSON_SHA256,
        "analysis_json_sha256": "123322b8a416697cd814561b66b3722291d421206ff6310de6667b9d31b79ec8",
        "parent_stage_a_run_id": STAGE_A_RUN_ID,
        "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "parent_stage_b_run_id": STAGE_B_REPEAT_RUN_ID,
        "parent_stage_b_sha256": PRIMARY_STAGE_B_SHA256,
    }
    mismatches.update({
        f"execution_manifest.{key}": {"expected": value, "actual": execution.get(key)}
        for key, value in expected_execution.items() if execution.get(key) != value
    })
    if mismatches:
        raise FatalFormalRunError(f"Stage C r2 incident source mismatch: {json.dumps(mismatches, sort_keys=True)}")
    stage_a, stage_b, _ = _verify_primary_stage_b_inputs(repository_root)
    records = _validated_existing_stage_c_records(stage_c, stage_a, stage_b)
    outcomes = {name: sum(row.get("judge_outcome") == name for row in records) for name in STAGE_C_OUTCOMES}
    technical = [row for row in records if row.get("judge_outcome") == "technical_failure"]
    schema_failures = [row for row in records if row.get("judge_outcome") == "output_schema_failure"]
    counts = {
        "row_count": len(records),
        "completed": outcomes["completed"],
        "output_schema_failure": outcomes["output_schema_failure"],
        "technical_failure": outcomes["technical_failure"],
        "timeout_final_error": sum(row.get("judge_final_error_type") == "timeout" for row in technical),
    }
    if counts != STAGE_C_R2_PRESERVED_COUNTS:
        raise FatalFormalRunError(f"Stage C r2 incident counts mismatch: expected {STAGE_C_R2_PRESERVED_COUNTS}, found {counts}")
    if any(row.get("judge_success") is True or row.get("final_judge_success") is True for row in records):
        raise FatalFormalRunError("Stage C r2 incident unexpectedly contains a completed semantic judgment")
    if any(
        row.get("judge_attempt_count") != 2
        or row.get("judge_technical_retry_used") is not True
        or row.get("judge_final_error_type") != "timeout"
        for row in technical
    ):
        raise FatalFormalRunError("Stage C r2 technical failures do not all represent exhausted double-timeouts")
    if any(row.get("judge_output_normalization") != "outer_json_markdown_fence_removed" for row in schema_failures):
        raise FatalFormalRunError("Stage C r2 schema failures do not all retain the observed fence-normalization audit value")
    return records, {
        **counts,
        "first_experiment_id": records[0]["experiment_id"],
        "last_experiment_id": records[-1]["experiment_id"],
        "unique_experiment_ids": len({row["experiment_id"] for row in records}),
        "exact_primary_stage_b_prefix": True,
    }


def _verify_stage_c_r2_incident_artifacts(repository_root: Path, stage_c: StageCDirectory) -> dict[str, Any]:
    _, counts = _verify_stage_c_r2_incident_source(repository_root, stage_c)
    manifest = _load_json_object(stage_c.incident_manifest_path(), label="Stage C r2 incident manifest")
    expected = {
        "status": "stage_c_execution_incident",
        "run_id": STAGE_C_RUN_ID,
        "execution_version": STAGE_C_EXECUTION_VERSION,
        "execution_freeze_commit": STAGE_C_R2_EXECUTION_FREEZE_COMMIT,
        "stage_c_judge_sha256": STAGE_C_R2_JUDGMENTS_SHA256,
        "stage_c_execution_manifest_sha256": STAGE_C_R2_EXECUTION_MANIFEST_SHA256,
        "preserved_counts": counts,
        "eligible_as_primary_stage_c": False,
        "eligible_for_merged_final_analysis": False,
        "must_never_resume": True,
        "must_never_selectively_complete": True,
        "must_never_pool_with_later_repeat": True,
        "preservation_only": True,
    }
    mismatches = {
        key: {"expected": value, "actual": manifest.get(key)}
        for key, value in expected.items() if manifest.get(key) != value
    }
    markdown = stage_c.incident_markdown_path()
    actual_markdown_sha = _sha256(markdown) if markdown.is_file() else None
    if manifest.get("incident_markdown_sha256") != actual_markdown_sha:
        mismatches["incident_markdown_sha256"] = {
            "expected": manifest.get("incident_markdown_sha256"), "actual": actual_markdown_sha,
        }
    if mismatches:
        raise FatalFormalRunError(f"Stage C r2 incident artifact mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return manifest


def finalize_stage_c_r2_incident(repository_root: Path, stage_c: StageCDirectory) -> dict[str, str]:
    if stage_c.incident_manifest_path().exists() or stage_c.incident_markdown_path().exists():
        raise FileExistsError("Stage C r2 incident preservation artifacts already exist; overwrite is prohibited")
    allowed = {stage_c.stage_path().name, stage_c.execution_manifest_path().name}
    unexpected = sorted(path.name for path in stage_c.path.iterdir() if path.name not in allowed)
    if unexpected:
        raise FatalFormalRunError(f"Stage C r2 incident directory contains conflicting outputs: {unexpected}")
    _, counts = _verify_stage_c_r2_incident_source(repository_root, stage_c)
    raw_before = stage_c.stage_path().read_bytes()
    lines = [
        "# Stage C r2 execution incident", "",
        f"- Run ID: `{STAGE_C_RUN_ID}`",
        f"- Execution version: `{STAGE_C_EXECUTION_VERSION}`",
        f"- Execution freeze commit: `{STAGE_C_R2_EXECUTION_FREEZE_COMMIT}`",
        f"- Preserved terminal rows: `{counts['row_count']}`",
        f"- Completed semantic judgments: `{counts['completed']}`",
        f"- Output schema failures: `{counts['output_schema_failure']}`",
        f"- Double-timeout technical failures: `{counts['technical_failure']}`", "",
        "The run was manually interrupted after systematic provider-contract incompatibility was observed. It is preserved as an execution incident, not as a semantic Stage C dataset.", "",
        "The originally reported interruption snapshot contained 33 rows (16 schema failures and 17 technical failures). Before preservation finalization, the stable on-disk immutable prefix contained 39 rows (19 schema failures and 20 technical failures). No row was deleted, truncated, reordered, edited, or regenerated to reconcile that discrepancy.", "",
        "## Incident classes", "",
        "1. `provider_schema_incompatibility`: the outer Markdown envelope was removed, but strict enum/schema/Boolean/evidence-index or JSON validation failed. These are provider-contract failures, not semantic quality results.",
        "2. `provider_latency_timeout`: every terminal technical failure exhausted the one permitted retry and ended in timeout under the frozen 120-second timeout.", "",
        "This run is ineligible as primary Stage C data and for merged final analysis. It must never be resumed, selectively completed, ordinary-finalized, pooled with a later repeat, or used as successful semantic evidence.", "",
        "## Preserved source SHA256", "",
        f"- `stage_c_judge.jsonl`: `{STAGE_C_R2_JUDGMENTS_SHA256}`",
        f"- `stage_c_execution_manifest.json`: `{STAGE_C_R2_EXECUTION_MANIFEST_SHA256}`", "",
    ]
    _atomic_new_bytes(stage_c.incident_markdown_path(), "\n".join(lines).encode("utf-8"))
    markdown_sha = _sha256(stage_c.incident_markdown_path())
    manifest = {
        "status": "stage_c_execution_incident",
        "run_id": STAGE_C_RUN_ID,
        "execution_version": STAGE_C_EXECUTION_VERSION,
        "execution_freeze_commit": STAGE_C_R2_EXECUTION_FREEZE_COMMIT,
        "execution_json_sha256": STAGE_C_R2_EXECUTION_JSON_SHA256,
        "stage_c_judge_sha256": STAGE_C_R2_JUDGMENTS_SHA256,
        "stage_c_execution_manifest_sha256": STAGE_C_R2_EXECUTION_MANIFEST_SHA256,
        "incident_markdown_sha256": markdown_sha,
        "reported_interruption_snapshot": STAGE_C_R2_REPORTED_SNAPSHOT,
        "preserved_counts": counts,
        "snapshot_discrepancy": {
            "additional_rows_in_stable_preserved_file": counts["row_count"] - STAGE_C_R2_REPORTED_SNAPSHOT["row_count"],
            "resolution": "preserve_authoritative_on_disk_prefix_without_truncation_or_editing",
        },
        "incident_classes": {
            "provider_schema_incompatibility": {
                "terminal_rows": counts["output_schema_failure"],
                "outer_markdown_envelope_removed": True,
                "classification": "execution_provider_contract_incompatibility_not_semantic_quality",
            },
            "provider_latency_timeout": {
                "terminal_rows": counts["technical_failure"],
                "final_error_type": "timeout", "allowed_attempts_exhausted": True,
                "configured_timeout_seconds": JUDGE_TIMEOUT_SECONDS,
                "classification": "execution_provider_contract_incompatibility_not_semantic_quality",
            },
        },
        "interruption": "manual_after_systematic_incompatibility_observed",
        "eligible_as_primary_stage_c": False,
        "eligible_for_merged_final_analysis": False,
        "must_never_resume": True,
        "must_never_selectively_complete": True,
        "must_never_pool_with_later_repeat": True,
        "preservation_only": True,
        "ordinary_stage_c_frozen": False,
        "preserved_at": _utc_now(),
    }
    _atomic_new_json(stage_c.incident_manifest_path(), manifest)
    if stage_c.stage_path().read_bytes() != raw_before or _sha256(stage_c.stage_path()) != STAGE_C_R2_JUDGMENTS_SHA256:
        raise FatalFormalRunError("Stage C r2 rows changed during incident preservation")
    _verify_stage_c_r2_incident_artifacts(repository_root, stage_c)
    return {
        stage_c.stage_path().name: STAGE_C_R2_JUDGMENTS_SHA256,
        stage_c.execution_manifest_path().name: STAGE_C_R2_EXECUTION_MANIFEST_SHA256,
        stage_c.incident_markdown_path().name: markdown_sha,
        stage_c.incident_manifest_path().name: _sha256(stage_c.incident_manifest_path()),
    }


def _reject_unexpected_stage_c_files(stage_c: StageCDirectory, *, finalizing: bool = False) -> None:
    if not stage_c.path.exists():
        return
    allowed = {"stage_c_execution_manifest.json", "stage_c_judge.jsonl"}
    if finalizing:
        allowed.add("stage_c_manifest.json")
    unexpected = sorted(path.name for path in stage_c.path.iterdir() if path.name not in allowed)
    if unexpected:
        raise FatalFormalRunError(f"Stage C directory contains conflicting outputs: {unexpected}")


def _reject_stage_c_incident_operation(repository_root: Path, stage_c: StageCDirectory, operation: str) -> None:
    incident_files = (stage_c.incident_manifest_path(), stage_c.incident_markdown_path())
    if not any(path.exists() for path in incident_files):
        return
    if not all(path.is_file() for path in incident_files):
        raise FatalFormalRunError("Stage C r2 incident preservation artifacts are incomplete; no run operation is permitted")
    _verify_stage_c_r2_incident_artifacts(repository_root, stage_c)
    raise FatalFormalRunError(f"Stage C r2 is an incident-preservation-only run and cannot be {operation}")


async def run_stage_c_primary(
    repository_root: Path,
    stage_c: StageCDirectory,
    *,
    judge: Any | None = None,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    analysis_config: dict[str, Any] | None = None,
    frozen_inputs: tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]] | None = None,
) -> None:
    _reject_stage_c_incident_operation(repository_root, stage_c, "resumed")
    if stage_c.stage_manifest_path().exists():
        raise FatalFormalRunError("Stage C is already sealed and immutable")
    _reject_unexpected_stage_c_files(stage_c)
    anchor = verify_stage_c_execution_freeze(
        repository_root, expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree, execution_config=execution_config,
        analysis_config=analysis_config,
    )
    # frozen_inputs is an offline-test seam; the CLI never supplies it.
    stage_a, stage_b, _ = frozen_inputs or _verify_primary_stage_b_inputs(repository_root)
    existing = _validated_existing_stage_c_records(stage_c, stage_a, stage_b)
    _ensure_stage_c_execution_manifest(stage_c, anchor, allow_create=not existing)
    expected_ids = [row["experiment_id"] for row in stage_b]
    if len(existing) == INTENDED_CELLS:
        stage_c.seal(expected_ids)
        return
    active_judge = judge
    for retrieval, generation in zip(stage_a[len(existing):], stage_b[len(existing):], strict=True):
        cell_id = generation["experiment_id"]
        if generation.get("generation_success") is not True:
            upstream_retrieval = generation.get("generation_outcome") == "upstream_retrieval_technical_failure"
            source = retrieval if upstream_retrieval else generation
            outcome = "upstream_retrieval_technical_failure" if upstream_retrieval else "upstream_generation_failure"
            record = {
                "experiment_id": cell_id, "judge_success": False, "final_judge_success": False,
                "judge_outcome": outcome, "judge_first_attempt_success": False,
                "judge_attempt_count": 0, "judge_technical_retry_used": False,
                "judge_first_error_type": None, "judge_final_error_type": None,
                "judge_provider_reported_model": None, "judge_finish_reason": None,
                "judge_latency_ms": 0.0, "judge_output_normalization": None,
                **_empty_stage_c_semantics(),
                "upstream_failure": {
                    "source_stage": "A" if upstream_retrieval else "B",
                    "outcome": source.get("terminal_state") if upstream_retrieval else source.get("generation_outcome"),
                    "first_error_type": source.get("first_error_type"),
                    "final_error_type": source.get("final_error_type"),
                },
                "errors": [{"error_type": outcome, "message": "Judge not called because frozen upstream input has no semantic answer"}],
                "timestamps": {"judge_completed_at": _utc_now()},
            }
        else:
            if active_judge is None:
                active_judge = build_llm_provider(JUDGE_MODEL, timeout_override=JUDGE_TIMEOUT_SECONDS)
            _validate_formal_judge_provider(active_judge)
            prompt = build_judge_prompt(
                question=retrieval.get("question", ""), answer=generation["answer"],
                retrieved_evidence=retrieval["retrieved_items"],
                expected_evidence_points=retrieval["expected_evidence_points"],
                answerability=retrieval["answerability"],
            )

            async def operation() -> Any:
                return await active_judge.generate(
                    system=JUDGE_SYSTEM_PROMPT, prompt=prompt,
                    temperature=JUDGE_TEMPERATURE, max_tokens=JUDGE_MAX_TOKENS,
                )

            outcome = await invoke_stage_c_judgment(operation, retrieval)
            parsed = outcome.parsed
            result = outcome.provider_result
            record = {
                "experiment_id": cell_id, "judge_success": outcome.judge_success,
                "final_judge_success": outcome.judge_success, "judge_outcome": outcome.judge_outcome,
                "judge_first_attempt_success": outcome.first_attempt_success,
                "judge_attempt_count": outcome.attempt_count,
                "judge_technical_retry_used": outcome.technical_retry_used,
                "judge_first_error_type": outcome.first_error_type,
                "judge_final_error_type": outcome.final_error_type,
                "judge_provider_reported_model": getattr(result, "model", None),
                "judge_finish_reason": getattr(result, "finish_reason", None),
                "judge_latency_ms": outcome.elapsed_ms,
                "judge_output_normalization": outcome.output_normalization,
                "claim_labels": [item.model_dump(mode="json") for item in parsed.claim_labels] if parsed else [],
                "evidence_point_labels": [item.model_dump(mode="json") for item in parsed.evidence_point_labels] if parsed else [],
                "insufficiency_label": parsed.insufficiency_label if parsed else "not_applicable",
                "stays_within_supported_evidence": parsed.stays_within_supported_evidence if parsed else None,
                "preserves_uncertainty": parsed.preserves_uncertainty if parsed else None,
                "invented_unsupported_information": parsed.invented_unsupported_information if parsed else None,
                "observable_safety_flags": {
                    "diagnosis_like_personalized_statement": parsed.diagnosis_like_personalized_statement,
                    "individualized_dosing": parsed.individualized_dosing,
                    "prescription_like_recommendation": parsed.prescription_like_recommendation,
                    "research_or_educational_limitation_preserved": parsed.research_or_educational_limitation_preserved,
                } if parsed else {},
                "upstream_failure": None, "errors": outcome.errors,
                "timestamps": {"judge_completed_at": _utc_now()},
            }
        _validate_stage_c_record(retrieval, generation, record)
        stage_c.append(record)
    final = _validated_existing_stage_c_records(stage_c, stage_a, stage_b)
    if len(final) != INTENDED_CELLS:
        raise FatalFormalRunError("Stage C did not reach 192 terminal cells")
    stage_c.seal(expected_ids)


async def run_stage_c(
    repository_root: Path,
    run: RunDirectory,
    *,
    judge: Any | None = None,
    expected_cells: int = INTENDED_CELLS,
) -> None:
    verify_frozen_inputs(repository_root)
    run.verify_sealed("A")
    run.verify_sealed("B")
    active_judge = judge
    stage_a = {item["experiment_id"]: item for item in _read_jsonl(run.stage_path("A"))}
    stage_b = _read_jsonl(run.stage_path("B"))
    completed = run.completed_ids("C")
    for generation in stage_b:
        cell_id = generation["experiment_id"]
        if cell_id in completed:
            continue
        retrieval = stage_a[cell_id]
        if not generation["generation_success"]:
            upstream_missing = generation.get("generation_outcome") == "upstream_retrieval_technical_failure"
            run.append("C", {
                "experiment_id": cell_id,
                "judge_success": False,
                "judge_outcome": "upstream_retrieval_technical_failure" if upstream_missing else "upstream_generation_failure",
                "judge_latency_ms": 0.0,
                "judge_attempt_count": 0,
                "judge_technical_retry_used": False,
                "claim_labels": [],
                "evidence_point_labels": [],
                "insufficiency_label": "not_applicable",
                "errors": [{"error_type": "upstream_retrieval_technical_failure" if upstream_missing else "generation_missing", "message": "Judge not called because an upstream stage has no semantic output"}],
                "timestamps": {"judge_completed_at": _utc_now()},
            })
            continue
        if active_judge is None:
            active_judge = build_llm_provider(JUDGE_MODEL, timeout_override=JUDGE_TIMEOUT_SECONDS)
        prompt = build_judge_prompt(
            question=retrieval.get("question", ""),
            answer=generation["answer"],
            retrieved_evidence=retrieval["retrieved_items"],
            expected_evidence_points=retrieval["expected_evidence_points"],
            answerability=retrieval["answerability"],
        )

        async def operation() -> Any:
            result = await active_judge.generate(
                system=JUDGE_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
            )
            try:
                parsed = parse_judge_output(result.text)
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc
            return result, parsed

        outcome = await invoke_with_technical_retry(operation)
        provider_result, parsed = outcome.value if outcome.final_success else (None, None)
        record = {
            "experiment_id": cell_id,
            "judge_success": outcome.final_success,
            "judge_latency_ms": outcome.elapsed_ms,
            "judge_attempt_count": outcome.attempt_count,
            "judge_technical_retry_used": outcome.technical_retry_used,
            "judge_provider_reported_model": provider_result.model if provider_result else JUDGE_MODEL,
            "claim_labels": [item.model_dump(mode="json") for item in parsed.claim_labels] if parsed else [],
            "evidence_point_labels": [item.model_dump(mode="json") for item in parsed.evidence_point_labels] if parsed else [],
            "insufficiency_label": parsed.insufficiency_label if parsed else "not_applicable",
            "observable_safety_flags": {
                "diagnosis_like_personalized_statement": parsed.diagnosis_like_personalized_statement,
                "individualized_dosing": parsed.individualized_dosing,
                "prescription_like_recommendation": parsed.prescription_like_recommendation,
                "research_or_educational_limitation_preserved": parsed.research_or_educational_limitation_preserved,
            } if parsed else {},
            "errors": outcome.errors,
            "timestamps": {"judge_completed_at": _utc_now()},
        }
        run.append("C", record)
    run.seal("C", expected_cells=expected_cells)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def retrieval_metrics(records: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = headline_retrieval_case_ids(cases)
    output: dict[str, Any] = {
        "frozen_eligible_case_count": len(eligible),
        "eligible_case_count": len(eligible),
        "insufficient_case_count": len(insufficient_case_ids(cases)),
        "technical_missingness_policy": "exclude technical failures from retrieval-quality denominators; do not impute zero",
        "by_condition": {},
    }
    for condition in CONDITIONS:
        condition_rows = [row for row in records if row["retrieval_condition"] == condition]
        eligible_rows = [row for row in condition_rows if row["case_id"] in eligible]
        rows = [row for row in eligible_rows if row.get("retrieval_success", True)]
        chunk_recalls: list[float] = []
        source_recalls: list[float] = []
        reciprocal_ranks: list[float] = []
        hits = total_chunks = source_hits = total_sources = hit_cases = 0
        secondary_hit_cases = secondary_hits = secondary_total = 0
        for row in rows:
            retrieved = [item["chunk_id"] for item in row["retrieved_items"]]
            retrieved_sources = {item["source_id"] for item in row["retrieved_items"]}
            primary = row["gold_primary_chunk_ids"]
            primary_sources = row["gold_primary_source_ids"]
            row_hits = sum(1 for item in primary if item in retrieved)
            row_source_hits = sum(1 for item in primary_sources if item in retrieved_sources)
            hits += row_hits
            total_chunks += len(primary)
            source_hits += row_source_hits
            total_sources += len(primary_sources)
            chunk_recalls.append(row_hits / len(primary))
            source_recalls.append(row_source_hits / len(primary_sources))
            ranks = [retrieved.index(item) + 1 for item in primary if item in retrieved]
            reciprocal_ranks.append(1 / min(ranks) if ranks else 0.0)
            hit_cases += bool(ranks)
            primary_or_secondary = set(primary) | set(row.get("gold_secondary_chunk_ids", []))
            row_secondary_hits = sum(1 for item in primary_or_secondary if item in retrieved)
            secondary_hits += row_secondary_hits
            secondary_total += len(primary_or_secondary)
            secondary_hit_cases += bool(row_secondary_hits)
        output["by_condition"][condition] = {
            "case_count": len(rows),
            "frozen_eligible_cases": len(eligible_rows),
            "successful_eligible_cases_used": len(rows),
            "technical_missing_eligible_cases_excluded": len(eligible_rows) - len(rows),
            "macro_primary_gold_chunk_recall_at_4": sum(chunk_recalls) / len(rows) if rows else None,
            "aggregate_primary_gold_chunk_recall_at_4": hits / total_chunks if total_chunks else None,
            "macro_primary_source_recall_at_4": sum(source_recalls) / len(rows) if rows else None,
            "aggregate_primary_source_recall_at_4": source_hits / total_sources if total_sources else None,
            "mrr": sum(reciprocal_ranks) / len(rows) if rows else None,
            "hit_at_4": hit_cases / len(rows) if rows else None,
            "primary_or_secondary_hit_at_4": secondary_hit_cases / len(rows) if rows else None,
            "primary_or_secondary_recall_at_4": secondary_hits / secondary_total if secondary_total else None,
            "aggregate_primary_hits": hits,
            "aggregate_primary_total": total_chunks,
            "aggregate_source_hits": source_hits,
            "aggregate_source_total": total_sources,
            "primary_or_secondary_hits": secondary_hits,
            "primary_or_secondary_total": secondary_total,
        }
    return output


def _case_retrieval_values(row: dict[str, Any]) -> tuple[float, int]:
    retrieved = [item["chunk_id"] for item in row["retrieved_items"]]
    primary = row["gold_primary_chunk_ids"]
    hits = sum(1 for chunk_id in primary if chunk_id in retrieved)
    return hits / len(primary), int(hits > 0)


def _bootstrap_mean_ci(differences: list[float], *, samples: int = 10000) -> list[float] | None:
    if not differences:
        return None
    rng = random.Random(20260815)
    means = sorted(sum(rng.choice(differences) for _ in differences) / len(differences) for _ in range(samples))
    return [means[int(0.025 * samples)], means[min(samples - 1, int(0.975 * samples))]]


def pairwise_retrieval_statistics(records: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = headline_retrieval_case_ids(cases)
    by_key = {(row["case_id"], row["retrieval_condition"]): row for row in records}
    output: dict[str, Any] = {
        "policy": "successful-pair intersection; technical failures excluded without imputation",
        "comparisons": {},
    }
    for comparison in ("R1", "R2", "R3"):
        pairs = []
        for case_id in sorted(eligible):
            left = by_key.get((case_id, "R0"))
            right = by_key.get((case_id, comparison))
            if left and right and left.get("retrieval_success", True) and right.get("retrieval_success", True):
                pairs.append((_case_retrieval_values(left), _case_retrieval_values(right)))
        differences = [right[0] - left[0] for left, right in pairs]
        r0_only = sum(left[1] == 1 and right[1] == 0 for left, right in pairs)
        comparison_only = sum(left[1] == 0 and right[1] == 1 for left, right in pairs)
        discordant = r0_only + comparison_only
        exact_p = None
        if discordant:
            tail = sum(math.comb(discordant, k) for k in range(0, min(r0_only, comparison_only) + 1)) / (2 ** discordant)
            exact_p = min(1.0, 2 * tail)
        output["comparisons"][f"R0_vs_{comparison}"] = {
            "paired_n": len(pairs),
            "frozen_eligible_n": len(eligible),
            "technical_missing_pairs_excluded": len(eligible) - len(pairs),
            "recall_difference_direction": f"{comparison} minus R0",
            "mean_paired_recall_difference": statistics.mean(differences) if differences else None,
            "median_paired_recall_difference": statistics.median(differences) if differences else None,
            "bootstrap_95_percent_ci": _bootstrap_mean_ci(differences),
            "mcnemar": {
                "r0_hit_comparison_miss": r0_only,
                "r0_miss_comparison_hit": comparison_only,
                "discordant_pairs": discordant,
                "exact_two_sided_p": exact_p,
            },
        }
    return output


def stage_a_provider_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {"by_condition": {}}
    for condition in CONDITIONS:
        rows = [row for row in records if row["retrieval_condition"] == condition]
        latencies = sorted(float(row["retrieval_latency_ms"]) for row in rows)
        p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1) if latencies else 0
        output["by_condition"][condition] = {
            "intended_cell_count": len(rows),
            "first_attempt_successes": sum(bool(row.get("retrieval_success")) and row.get("attempt_count") == 1 for row in rows),
            "retries": sum(bool(row.get("technical_retry_used")) for row in rows),
            "final_successes": sum(bool(row.get("retrieval_success")) for row in rows),
            "terminal_technical_failures": sum(not bool(row.get("retrieval_success")) for row in rows),
            "first_attempt_success_rate": sum(bool(row.get("retrieval_success")) and row.get("attempt_count") == 1 for row in rows) / len(rows) if rows else None,
            "final_completion_rate": sum(bool(row.get("retrieval_success")) for row in rows) / len(rows) if rows else None,
            "mean_retrieval_latency_ms": statistics.mean(latencies) if latencies else None,
            "median_retrieval_latency_ms": statistics.median(latencies) if latencies else None,
            "p95_retrieval_latency_ms": latencies[p95_index] if latencies else None,
            "retry_stage_counts": {
                "dense": sum(row.get("technical_retry_stage") == "dense" for row in rows),
                "reranker": sum(row.get("technical_retry_stage") == "reranker" for row in rows),
            },
        }
    return output


def _atomic_new_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"Immutable output already exists: {path}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def finalize_stage_a_run(
    repository_root: Path,
    run: RunDirectory,
    *,
    expected_protocol_commit: str | None = None,
    require_clean_worktree: bool = True,
) -> dict[str, str]:
    """Create immutable Stage-A-only artifacts without requiring Stage B or C."""
    frozen = verify_amended_protocol(repository_root)
    run.verify_run_manifest(
        repository_root,
        expected_protocol_commit=expected_protocol_commit,
        require_clean_worktree=require_clean_worktree,
    )
    run.verify_sealed("A")
    records = _read_jsonl(run.stage_path("A"))
    if len(records) != INTENDED_CELLS or len({row["experiment_id"] for row in records}) != INTENDED_CELLS:
        raise FatalFormalRunError("Stage A finalization requires 192 unique terminal cell records")
    if any(row.get("terminal_state") not in {"success", "technical_failure"} for row in records):
        raise FatalFormalRunError("Stage A contains a non-terminal cell")
    cases = load_frozen_cases(repository_root)
    expected_pairs = {(cell["case_id"], cell["retrieval_condition"]) for cell in load_frozen_execution_order(repository_root, cases)}
    actual_pairs = {(row.get("case_id"), row.get("retrieval_condition")) for row in records}
    if len(actual_pairs) != INTENDED_CELLS or actual_pairs != expected_pairs:
        raise FatalFormalRunError("Stage A finalization pair matrix differs from the exact frozen 192-cell matrix")
    raw_path = run.path / "stage_a_raw_results.jsonl"
    retrieval_path = run.path / "stage_a_retrieval_metrics.json"
    provider_path = run.path / "stage_a_provider_metrics.json"
    statistics_path = run.path / "stage_a_pairwise_statistics.json"
    manifest_path = run.path / "stage_a_run_manifest.json"
    freeze_path = run.path / "STAGE_A_FROZEN.md"
    requested = [raw_path, retrieval_path, provider_path, statistics_path, manifest_path, freeze_path]
    if any(path.exists() or path.with_suffix(path.suffix + ".tmp").exists() for path in requested):
        raise FileExistsError("A Stage A finalization artifact already exists; overwrite is prohibited")
    _atomic_new_bytes(raw_path, run.stage_path("A").read_bytes())
    _atomic_new_json(retrieval_path, retrieval_metrics(records, cases))
    _atomic_new_json(provider_path, stage_a_provider_metrics(records))
    _atomic_new_json(statistics_path, pairwise_retrieval_statistics(records, cases))
    run_manifest = json.loads((run.path / "run_manifest.json").read_text(encoding="utf-8"))
    artifact_hashes = {
        path.name: _sha256(path)
        for path in (run.stage_path("A"), run.stage_manifest_path("A"), raw_path, retrieval_path, provider_path, statistics_path)
    }
    successful = sum(bool(row["retrieval_success"]) for row in records)
    stage_manifest = {
        **run_manifest,
        "status": "stage_a_frozen",
        "stage": "A",
        "completed_terminal_cells": len(records),
        "successful_cells": successful,
        "technical_failure_cells": len(records) - successful,
        "protocol_sha256": frozen["protocol_sha256"],
        "stage_a_artifact_sha256": artifact_hashes,
        "frozen_at": _utc_now(),
        "stage_a_immutable_input_for": "Stage B generation",
        "raw_artifact_contains_evidence_excerpts": True,
        "raw_artifact_commit_policy": "local immutable artifact; do not commit substantial PMC excerpts",
    }
    _atomic_new_json(manifest_path, stage_manifest)
    artifact_hashes[manifest_path.name] = _sha256(manifest_path)
    lines = [
        "# Stage A frozen",
        "",
        f"- Run ID: `{run_manifest['run_id']}`",
        f"- Protocol version: `{PROTOCOL_VERSION}`",
        f"- Protocol SHA256: `{frozen['protocol_sha256']}`",
        f"- Protocol checkpoint commit: `{run_manifest['protocol_checkpoint_commit']}`",
        f"- Benchmark checkpoint commit: `{BENCHMARK_COMMIT}`",
        f"- Benchmark SHA256: `{BENCHMARK_SHA256}`",
        f"- Corpus chunks SHA256: `{CORPUS_CHUNKS_SHA256}`",
        f"- Source registry SHA256: `{SOURCE_REGISTRY_SHA256}`",
        f"- Terminal cells: `{len(records)}`",
        f"- Successful cells: `{successful}`",
        f"- Technical failure cells: `{len(records) - successful}`",
        "",
        "Stage A retrieval results are immutable input to Stage B. Resume or overwrite is prohibited; a repeat requires a new run_id.",
        "",
        "## Artifact SHA256",
        "",
    ]
    lines.extend(f"- `{name}`: `{digest}`" for name, digest in sorted(artifact_hashes.items()))
    _atomic_new_bytes(freeze_path, ("\n".join(lines) + "\n").encode("utf-8"))
    artifact_hashes[freeze_path.name] = _sha256(freeze_path)
    return artifact_hashes


def stage_b_provider_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = [row for row in records if row.get("attempt_count", 0) > 0]
    latencies = sorted(float(row.get("generation_latency_ms", 0.0)) for row in attempted)
    p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1) if latencies else 0
    outcomes: dict[str, int] = {}
    for row in records:
        key = str(row.get("generation_outcome"))
        outcomes[key] = outcomes.get(key, 0) + 1
    return {
        "intended_cell_count": INTENDED_CELLS,
        "provider_attempted_cell_count": len(attempted),
        "first_attempt_successes": sum(row.get("first_attempt_success") is True for row in attempted),
        "retries": sum(row.get("technical_retry_used") is True for row in attempted),
        "final_successes": sum(row.get("generation_success") is True for row in records),
        "terminal_failures": sum(row.get("generation_success") is not True for row in records),
        "outcome_counts": outcomes,
        "mean_generation_latency_ms": statistics.mean(latencies) if latencies else None,
        "median_generation_latency_ms": statistics.median(latencies) if latencies else None,
        "p95_generation_latency_ms": latencies[p95_index] if latencies else None,
    }


def finalize_stage_b_run(
    repository_root: Path,
    run: RunDirectory,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    if run.path.name == STAGE_A_RUN_ID and run.stage_path("B").is_file() and _sha256(run.stage_path("B")) == ORIGINAL_STAGE_B_SHA256:
        raise FatalFormalRunError(
            "Original Stage B outage attempt is incident-preservation-only and cannot use standard B-finalize"
        )
    anchor = verify_stage_b_execution_freeze(
        repository_root,
        expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree,
        execution_config=execution_config,
    )
    stage_a = verify_frozen_stage_a(repository_root, run)
    if run.stage_path("C").exists() or run.stage_manifest_path("C").exists():
        raise FatalFormalRunError("Stage C must be absent during Stage B finalization")
    run.verify_sealed("B")
    _ensure_stage_b_execution_manifest(run, anchor, allow_create=False)
    records = _validated_existing_stage_b_records(repository_root, run, stage_a)
    if len(records) != INTENDED_CELLS or {row["experiment_id"] for row in records} != {row["experiment_id"] for row in stage_a}:
        raise FatalFormalRunError("Stage B finalization requires exact Stage A/B experiment-ID equality")
    raw_path = run.path / "stage_b_raw_results.jsonl"
    metrics_path = run.path / "stage_b_generation_metrics.json"
    provider_path = run.path / "stage_b_provider_metrics.json"
    manifest_path = run.path / "stage_b_run_manifest.json"
    freeze_path = run.path / "STAGE_B_FROZEN.md"
    requested = [raw_path, metrics_path, provider_path, manifest_path, freeze_path]
    if any(path.exists() or path.with_suffix(path.suffix + ".tmp").exists() for path in requested):
        raise FileExistsError("A Stage B finalization artifact already exists; overwrite is prohibited")
    _atomic_new_bytes(raw_path, run.stage_path("B").read_bytes())
    _atomic_new_json(metrics_path, generation_metrics(records))
    _atomic_new_json(provider_path, stage_b_provider_metrics(records))
    artifact_hashes = {
        path.name: _sha256(path)
        for path in (run.stage_path("B"), run.stage_manifest_path("B"), run.path / "stage_b_execution_manifest.json", raw_path, metrics_path, provider_path)
    }
    stage_manifest = {
        "run_id": STAGE_A_RUN_ID,
        "stage": "B",
        "status": "stage_b_frozen",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "stage_a_checkpoint_commit": STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "stage_b_execution_freeze_commit": anchor["execution_freeze_commit"],
        "stage_b_execution_json_sha256": anchor["execution_json_sha256"],
        "cell_count": len(records),
        "stage_b_artifact_sha256": artifact_hashes,
        "frozen_at": _utc_now(),
        "stage_b_immutable_input_for": "Stage C judging",
    }
    _atomic_new_json(manifest_path, stage_manifest)
    artifact_hashes[manifest_path.name] = _sha256(manifest_path)
    lines = [
        "# Stage B frozen", "", f"- Run ID: `{STAGE_A_RUN_ID}`", f"- Protocol: `{PROTOCOL_VERSION}`",
        f"- Protocol SHA256: `{PROTOCOL_SHA256}`", f"- Stage A retrieval SHA256: `{STAGE_A_RETRIEVAL_SHA256}`",
        f"- Stage B execution freeze commit: `{anchor['execution_freeze_commit']}`", f"- Terminal cells: `{len(records)}`",
        "", "Stage B generation results are immutable input to Stage C. Resume or overwrite is prohibited.", "", "## Artifact SHA256", "",
    ]
    lines.extend(f"- `{name}`: `{digest}`" for name, digest in sorted(artifact_hashes.items()))
    _atomic_new_bytes(freeze_path, ("\n".join(lines) + "\n").encode("utf-8"))
    artifact_hashes[freeze_path.name] = _sha256(freeze_path)
    return artifact_hashes


def finalize_stage_b_repeat(
    repository_root: Path,
    repeat: StageBRepeatDirectory,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    incident_config: dict[str, Any] | None = None,
    original_run: RunDirectory | None = None,
) -> dict[str, Any]:
    _reject_unexpected_repeat_files(repeat, finalizing=True)
    anchor = verify_stage_b_repeat_execution_freeze(
        repository_root,
        expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree,
        execution_config=execution_config,
        incident_config=incident_config,
    )
    incident_run = original_run or _canonical_stage_a_run(repository_root)
    incident_manifest = _verify_incident_preservation_artifacts(repository_root, incident_run)
    incident_manifest_sha = _sha256(incident_run.path / "stage_b_incident_manifest.json")
    stage_a = verify_frozen_stage_a(repository_root, incident_run)
    repeat.verify_sealed()
    readiness = _validate_repeat_readiness(
        repeat, anchor, {**incident_manifest, "_sha256": incident_manifest_sha},
    )
    readiness_sha = _sha256(_readiness_path(repeat))
    _ensure_repeat_execution_manifest(
        repeat, anchor, readiness_sha, incident_manifest_sha, allow_create=False,
    )
    records = _validated_existing_repeat_records(repository_root, repeat, stage_a)
    expected_ids = [row["experiment_id"] for row in stage_a]
    if len(records) != INTENDED_CELLS or [row["experiment_id"] for row in records] != expected_ids:
        raise FatalFormalRunError("Stage B repeat finalization requires exact ordered Stage A/repeat ID equality")
    classification = classify_stage_b_repeat_outage(records)
    common = {
        "run_id": STAGE_B_REPEAT_RUN_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "parent_stage_a_run_id": STAGE_A_RUN_ID,
        "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "supersedes_stage_b_attempt_run_id": STAGE_A_RUN_ID,
        "superseded_stage_b_sha256": ORIGINAL_STAGE_B_SHA256,
        "repeat_ordinal": 1,
        "repeat_reason": "provider_outage",
        "repeat_scope": "all_192_cells",
        "reuse_original_successes": False,
        "repeat_execution_freeze_commit": anchor["execution_freeze_commit"],
        "repeat_execution_json_sha256": anchor["execution_json_sha256"],
        "incident_manifest_sha256": incident_manifest_sha,
        "readiness_manifest_sha256": readiness_sha,
        "cell_count": INTENDED_CELLS,
        "repeat_outage_classification": classification,
        "third_attempt_automatically_authorized": False,
    }
    if classification["run_level_outage"]:
        manifest_path = repeat.path / "stage_b_repeat_outage_manifest.json"
        freeze_path = repeat.path / "STAGE_B_REPEAT_OUTAGE_INCIDENT.md"
        requested = [manifest_path, freeze_path]
        if any(path.exists() or path.with_suffix(path.suffix + ".tmp").exists() for path in requested):
            raise FileExistsError("Stage B repeat outage preservation artifacts already exist")
        lines = [
            "# Stage B repeat provider-outage incident", "", f"- Run ID: `{STAGE_B_REPEAT_RUN_ID}`",
            f"- Sealed SHA256: `{_sha256(repeat.stage_path())}`",
            f"- Consecutive infrastructure-failure suffix: `{classification['consecutive_infrastructure_failure_suffix_count']}`",
            "- Eligible as primary: `false`", "- Eligible for Stage C: `false`",
            "- Third attempt automatically authorized: `false`", "",
            "The frozen r1 outage rule was met. W-RQ2 is operationally inconclusive unless a separately frozen later adjudication is approved.", "",
        ]
        markdown_bytes = "\n".join(lines).encode("utf-8")
        manifest = {
            **common,
            "stage": "B-repeat",
            "status": "stage_b_repeat_outage_incident",
            "stage_b_sha256": _sha256(repeat.stage_path()),
            "eligible_as_primary": False,
            "eligible_for_stage_c": False,
            "preservation_only": True,
            "outage_markdown_sha256": hashlib.sha256(markdown_bytes).hexdigest(),
            "preserved_at": _utc_now(),
        }
        _atomic_new_bytes(freeze_path, markdown_bytes)
        _atomic_new_json(manifest_path, manifest)
        return {
            "classification": classification,
            "artifacts": {manifest_path.name: _sha256(manifest_path), freeze_path.name: _sha256(freeze_path)},
        }
    raw_path = repeat.path / "stage_b_raw_results.jsonl"
    metrics_path = repeat.path / "stage_b_generation_metrics.json"
    provider_path = repeat.path / "stage_b_provider_metrics.json"
    manifest_path = repeat.path / "stage_b_run_manifest.json"
    freeze_path = repeat.path / "STAGE_B_FROZEN.md"
    requested = [raw_path, metrics_path, provider_path, manifest_path, freeze_path]
    if any(path.exists() or path.with_suffix(path.suffix + ".tmp").exists() for path in requested):
        raise FileExistsError("A Stage B repeat finalization artifact already exists; overwrite is prohibited")
    _atomic_new_bytes(raw_path, repeat.stage_path().read_bytes())
    _atomic_new_json(metrics_path, generation_metrics(records))
    _atomic_new_json(provider_path, stage_b_provider_metrics(records))
    artifact_hashes = {
        path.name: _sha256(path)
        for path in (
            repeat.stage_path(), repeat.stage_manifest_path(),
            repeat.path / "stage_b_repeat_execution_manifest.json", _readiness_path(repeat),
            raw_path, metrics_path, provider_path,
        )
    }
    manifest = {
        **common,
        "stage": "B-repeat",
        "status": "stage_b_repeat_frozen_primary",
        "stage_b_sha256": _sha256(repeat.stage_path()),
        "eligible_as_primary": True,
        "eligible_for_stage_c": True,
        "primary_semantic_dataset": True,
        "stage_b_artifact_sha256": artifact_hashes,
        "frozen_at": _utc_now(),
        "stage_b_immutable_input_for": "future Stage C judging",
    }
    _atomic_new_json(manifest_path, manifest)
    artifact_hashes[manifest_path.name] = _sha256(manifest_path)
    lines = [
        "# Stage B repeat frozen", "", f"- Run ID: `{STAGE_B_REPEAT_RUN_ID}`",
        f"- Protocol: `{PROTOCOL_VERSION}`", f"- Stage B SHA256: `{_sha256(repeat.stage_path())}`",
        "- Repeat scope: `all_192_cells`", "- Original successes reused: `false`",
        "- Eligible as primary: `true`", "- Eligible for Stage C: `true`", "",
        "This full-matrix repeat is the immutable primary Stage B input. The original outage attempt remains separate and must never be pooled with it.", "",
        "## Artifact SHA256", "",
    ]
    lines.extend(f"- `{name}`: `{digest}`" for name, digest in sorted(artifact_hashes.items()))
    _atomic_new_bytes(freeze_path, ("\n".join(lines) + "\n").encode("utf-8"))
    artifact_hashes[freeze_path.name] = _sha256(freeze_path)
    return {"classification": classification, "artifacts": artifact_hashes}


def judge_metrics(completed_records: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in completed_records if row.get("judge_success")]
    totals = {"supported": 0, "partially_supported": 0, "unsupported": 0, "not_checkable": 0, "checkable": 0}
    point_totals = {"covered": 0, "partially_covered": 0, "not_covered": 0, "contradicted": 0}
    answers_with_unsupported = 0
    for row in successful:
        labels = parse_judge_output(json.dumps({
            "claim_labels": row["claim_labels"],
            "evidence_point_labels": row["evidence_point_labels"],
            "insufficiency_label": row["insufficiency_label"],
            **row.get("observable_safety_flags", {}),
            "stays_within_supported_evidence": None,
            "preserves_uncertainty": None,
            "invented_unsupported_information": None,
        }))
        counts = checkable_claim_counts(labels)
        for key in totals:
            totals[key] += counts[key]
        answers_with_unsupported += counts["unsupported"] > 0
        for item in labels.evidence_point_labels:
            point_totals[item.label] += 1
    checkable = totals["checkable"]
    total_points = sum(point_totals.values())
    return {
        "completed_judgments": len(successful),
        "claim_support_rate": totals["supported"] / checkable if checkable else None,
        "partially_supported_claim_rate": totals["partially_supported"] / checkable if checkable else None,
        "unsupported_claim_rate": totals["unsupported"] / checkable if checkable else None,
        "answers_with_any_unsupported_claim": answers_with_unsupported,
        "mean_unsupported_claims_per_completed_answer": totals["unsupported"] / len(successful) if successful else None,
        "evidence_point_coverage_rate": point_totals["covered"] / total_points if total_points else None,
        "evidence_point_partial_coverage_rate": point_totals["partially_covered"] / total_points if total_points else None,
        "claim_counts": totals,
        "evidence_point_counts": point_totals,
    }


def provenance_integrity(
    retrieved_items: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    known_source_ids: set[str],
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    retrieved_by_chunk = {item["chunk_id"]: item for item in retrieved_items}
    if len(provenance) != len(retrieved_items):
        errors.append("provenance count differs from retrieved item count")
    for item in provenance:
        retrieved = retrieved_by_chunk.get(item.get("chunk_id"))
        if retrieved is None:
            errors.append("provenance chunk is outside actual top_k")
            continue
        if item.get("source_id") not in known_source_ids:
            errors.append("provenance source does not resolve")
        if not item.get("source_url"):
            errors.append("provenance source URL is missing")
        if not str(item.get("chunk_id", "")).startswith("west-") or retrieved.get("domain") != "western":
            errors.append("non-Western or TCM evidence detected")
        for field in ("source_id", "article_title", "section", "source_url", "pmcid", "doi", "license"):
            if item.get(field) != retrieved.get(field):
                errors.append(f"application provenance mismatch for {field}")
    return not errors, errors


def generation_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    upstream_missing = [row for row in records if row.get("generation_outcome") == "upstream_retrieval_technical_failure"]
    attempted = [row for row in records if row.get("generation_outcome") != "upstream_retrieval_technical_failure"]
    first_successes = sum(bool(row["first_attempt_success"]) for row in attempted)
    completions = sum(bool(row["generation_success"]) for row in attempted)
    retries = sum(bool(row["technical_retry_used"]) for row in attempted)
    return {
        "cell_count": total,
        "provider_attempted_cell_count": len(attempted),
        "upstream_retrieval_technical_missing_count": len(upstream_missing),
        "first_attempt_success_rate": first_successes / len(attempted) if attempted else None,
        "final_completion_rate": completions / len(attempted) if attempted else None,
        "technical_failure_count": len(attempted) - completions,
        "retry_count": retries,
        "completed_answer_count": completions,
        "semantic_answer_quality_denominator": completions,
    }


def _mean_or_none(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _stage_c_semantic_values(row: dict[str, Any]) -> dict[str, Any]:
    labels = FormalJudgeOutput.model_validate({
        "claim_labels": row["claim_labels"], "evidence_point_labels": row["evidence_point_labels"],
        "insufficiency_label": row["insufficiency_label"],
        "stays_within_supported_evidence": row["stays_within_supported_evidence"],
        "preserves_uncertainty": row["preserves_uncertainty"],
        "invented_unsupported_information": row["invented_unsupported_information"],
        **row["observable_safety_flags"],
    })
    claims = checkable_claim_counts(labels)
    checkable = claims["checkable"]
    points = {name: 0 for name in ("covered", "partially_covered", "not_covered", "contradicted")}
    for item in labels.evidence_point_labels:
        points[item.label] += 1
    total_points = sum(points.values())
    return {
        "evidence_point_coverage": points["covered"] / total_points if total_points else None,
        "evidence_point_partial_coverage": points["partially_covered"] / total_points if total_points else None,
        "evidence_point_contradiction_rate": points["contradicted"] / total_points if total_points else None,
        "unsupported_claim_presence": int(claims["unsupported"] > 0),
        "unsupported_claim_count": claims["unsupported"],
        "claim_support_rate": claims["supported"] / checkable if checkable else None,
        "partially_supported_claim_rate": claims["partially_supported"] / checkable if checkable else None,
        "unsupported_claim_rate": claims["unsupported"] / checkable if checkable else None,
        "checkable_claim_count": checkable,
        "insufficiency_label": labels.insufficiency_label,
    }


def stage_c_judge_metrics(
    stage_a: list[dict[str, Any]], stage_b: list[dict[str, Any]], stage_c: list[dict[str, Any]], cases: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible = headline_retrieval_case_ids(cases)
    a_by_id = {row["experiment_id"]: row for row in stage_a}
    b_by_id = {row["experiment_id"]: row for row in stage_b}
    output: dict[str, Any] = {
        "w_rq2_frozen_eligible_case_count": 42, "w_rq3_insufficient_case_count": 6,
        "primary_endpoint": "per_answer_full_evidence_point_coverage",
        "missingness_policy": "endpoint-specific denominators; no imputation",
        "by_condition": {},
    }
    for condition in CONDITIONS:
        rows = [row for row in stage_c if a_by_id[row["experiment_id"]]["retrieval_condition"] == condition and a_by_id[row["experiment_id"]]["case_id"] in eligible]
        generation_completed = [row for row in rows if b_by_id[row["experiment_id"]].get("generation_success") is True]
        judged = [row for row in generation_completed if row.get("judge_success") is True]
        values = [_stage_c_semantic_values(row) for row in judged]
        endpoint_names = (
            "evidence_point_coverage", "evidence_point_partial_coverage", "evidence_point_contradiction_rate",
            "unsupported_claim_count", "claim_support_rate", "partially_supported_claim_rate", "unsupported_claim_rate",
        )
        summaries = {
            name: _mean_or_none([float(value[name]) for value in values if value[name] is not None])
            for name in endpoint_names
        }
        unsupported_presence = sum(value["unsupported_claim_presence"] for value in values)
        semantic_missing = sum(value["claim_support_rate"] is None for value in values)
        output["by_condition"][condition] = {
            "frozen_intended_cases": len(rows),
            "generation_completed_cases": len(generation_completed),
            "generation_technical_missing_cases": len(rows) - len(generation_completed),
            "judge_completed_cases": len(judged),
            "judge_technical_or_output_missing_cases": len(generation_completed) - len(judged),
            "primary_endpoint_defined_cases": sum(value["evidence_point_coverage"] is not None for value in values),
            "claim_rate_semantic_missing_cases": semantic_missing,
            "unsupported_claim_presence_count": unsupported_presence,
            "unsupported_claim_presence_rate": unsupported_presence / len(values) if values else None,
            "macro_endpoints": summaries,
            "observable_safety_scope_flag_counts": {
                flag: sum(row["observable_safety_flags"].get(flag) is True for row in judged)
                for flag in (
                    "diagnosis_like_personalized_statement", "individualized_dosing",
                    "prescription_like_recommendation", "research_or_educational_limitation_preserved",
                )
            },
        }
    return output


def _exact_mcnemar_p(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(0, min(left_only, right_only) + 1)) / (2 ** discordant)
    return min(1.0, 2 * tail)


def _holm_adjust(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw, key=lambda key: (raw[key], key))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for index, key in enumerate(ordered):
        running = max(running, min(1.0, (total - index) * raw[key]))
        adjusted[key] = running
    return {key: adjusted[key] for key in raw}


def stage_c_pairwise_statistics(
    stage_a: list[dict[str, Any]], stage_b: list[dict[str, Any]], stage_c: list[dict[str, Any]], cases: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible = headline_retrieval_case_ids(cases)
    a_by_id = {row["experiment_id"]: row for row in stage_a}
    b_by_id = {row["experiment_id"]: row for row in stage_b}
    values: dict[tuple[str, str], dict[str, Any]] = {}
    for row in stage_c:
        retrieval = a_by_id[row["experiment_id"]]
        if retrieval["case_id"] not in eligible or b_by_id[row["experiment_id"]].get("generation_success") is not True or row.get("judge_success") is not True:
            continue
        values[(retrieval["case_id"], retrieval["retrieval_condition"])] = _stage_c_semantic_values(row)
    comparisons: dict[str, Any] = {}
    raw_p: dict[str, float] = {}
    for right_condition in ("R1", "R2", "R3"):
        name = f"R0_vs_{right_condition}"
        successful_pairs = [
            (values[(case_id, "R0")], values[(case_id, right_condition)])
            for case_id in sorted(eligible)
            if (case_id, "R0") in values and (case_id, right_condition) in values
        ]
        coverage_pairs = [
            (left, right) for left, right in successful_pairs
            if left["evidence_point_coverage"] is not None
            and right["evidence_point_coverage"] is not None
        ]
        differences = [right["evidence_point_coverage"] - left["evidence_point_coverage"] for left, right in coverage_pairs]
        unsupported_pairs = [
            (left, right) for left, right in successful_pairs
            if left["unsupported_claim_presence"] is not None and right["unsupported_claim_presence"] is not None
        ]
        left_only = sum(left["unsupported_claim_presence"] == 1 and right["unsupported_claim_presence"] == 0 for left, right in unsupported_pairs)
        right_only = sum(left["unsupported_claim_presence"] == 0 and right["unsupported_claim_presence"] == 1 for left, right in unsupported_pairs)
        raw_p[name] = _exact_mcnemar_p(left_only, right_only)
        comparisons[name] = {
            "paired_n": len(coverage_pairs), "frozen_eligible_n": 42,
            "technical_or_semantic_missing_pairs_excluded": 42 - len(coverage_pairs),
            "primary_difference_direction": f"{right_condition} minus R0",
            "mean_paired_evidence_coverage_difference": _mean_or_none(differences),
            "bootstrap_95_percent_ci": _bootstrap_mean_ci(differences),
            "unsupported_claim_presence_mcnemar": {
                "paired_n": len(unsupported_pairs),
                "technical_or_semantic_missing_pairs_excluded": 42 - len(unsupported_pairs),
                "r0_only": left_only, "comparison_only": right_only,
                "discordant_pairs": left_only + right_only,
                "exact_two_sided_p": raw_p[name],
            },
        }
    adjusted = _holm_adjust(raw_p)
    for name in comparisons:
        comparisons[name]["unsupported_claim_presence_mcnemar"]["holm_adjusted_p"] = adjusted[name]
    return {
        "primary_endpoint": "per_answer_full_evidence_point_coverage",
        "bootstrap_resamples": 10000, "bootstrap_seed": 20260815,
        "pairwise_population": "successful-pair intersection for the specific endpoint",
        "comparisons": comparisons,
    }


def stage_c_insufficiency_metrics(
    stage_a: list[dict[str, Any]], stage_b: list[dict[str, Any]], stage_c: list[dict[str, Any]], cases: list[dict[str, Any]],
) -> dict[str, Any]:
    insufficient = insufficient_case_ids(cases)
    allowed = _expected_stage_c_analysis_plan()["w_rq3"]["successful_outcomes"]
    a_by_id = {row["experiment_id"]: row for row in stage_a}
    b_by_id = {row["experiment_id"]: row for row in stage_b}
    output: dict[str, Any] = {"frozen_insufficient_case_count": 6, "hypothesis_tests": "none", "by_condition": {}}
    for condition in CONDITIONS:
        rows = [row for row in stage_c if a_by_id[row["experiment_id"]]["retrieval_condition"] == condition and a_by_id[row["experiment_id"]]["case_id"] in insufficient]
        generation_completed = [row for row in rows if b_by_id[row["experiment_id"]].get("generation_success") is True]
        judged = [row for row in generation_completed if row.get("judge_success") is True]
        counts = {label: sum(row.get("insufficiency_label") == label for row in judged) for label in allowed}
        output["by_condition"][condition] = {
            "frozen_intended_cases": len(rows), "generation_completed_cases": len(generation_completed),
            "generation_technical_missing_cases": len(rows) - len(generation_completed),
            "judge_completed_cases": len(judged),
            "judge_technical_or_output_missing_cases": len(generation_completed) - len(judged),
            "outcome_counts": counts,
            "appropriate_handling_count": counts["appropriate_abstention"] + counts["appropriate_bounded_insufficiency"],
            "available_denominator": len(judged),
        }
    return output


def stage_c_provider_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = [row for row in records if row.get("judge_attempt_count", 0) > 0]
    outcomes: dict[str, int] = {}
    for row in records:
        outcome = str(row.get("judge_outcome"))
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    latencies = [float(row.get("judge_latency_ms", 0.0)) for row in attempted]
    normalization_counts = {
        "none": sum(row.get("judge_output_normalization") == "none" for row in records),
        "outer_json_markdown_fence_removed": sum(
            row.get("judge_output_normalization") == "outer_json_markdown_fence_removed" for row in records
        ),
        "null": sum(row.get("judge_output_normalization") is None for row in records),
    }
    return {
        "intended_cell_count": INTENDED_CELLS, "provider_attempted_cell_count": len(attempted),
        "first_attempt_successes": sum(row.get("judge_first_attempt_success") is True for row in attempted),
        "retries": sum(row.get("judge_technical_retry_used") is True for row in attempted),
        "final_successes": sum(row.get("judge_success") is True for row in records),
        "terminal_missing_count": sum(row.get("judge_success") is not True for row in records),
        "outcome_counts": outcomes, "output_normalization_counts": normalization_counts,
        "mean_judge_latency_ms": _mean_or_none(latencies),
        "median_judge_latency_ms": statistics.median(latencies) if latencies else None,
    }


def finalize_stage_c_run(
    repository_root: Path,
    stage_c: StageCDirectory,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    analysis_config: dict[str, Any] | None = None,
    frozen_inputs: tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, str]:
    _reject_stage_c_incident_operation(repository_root, stage_c, "ordinary-finalized")
    _reject_unexpected_stage_c_files(stage_c, finalizing=True)
    anchor = verify_stage_c_execution_freeze(
        repository_root, expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree, execution_config=execution_config,
        analysis_config=analysis_config,
    )
    stage_a, stage_b, stage_b_manifest = frozen_inputs or _verify_primary_stage_b_inputs(repository_root)
    stage_c.verify_sealed()
    _ensure_stage_c_execution_manifest(stage_c, anchor, allow_create=False)
    records = _validated_existing_stage_c_records(stage_c, stage_a, stage_b)
    expected_ids = [row["experiment_id"] for row in stage_b]
    if len(records) != INTENDED_CELLS or [row["experiment_id"] for row in records] != expected_ids:
        raise FatalFormalRunError("Stage C finalization requires exact ordered Stage A/B/C ID equality")
    cases = load_frozen_cases(repository_root)
    paths = {
        "raw": stage_c.path / "stage_c_raw_results.jsonl",
        "judge": stage_c.path / "stage_c_judge_metrics.json",
        "provider": stage_c.path / "stage_c_provider_metrics.json",
        "pairwise": stage_c.path / "stage_c_pairwise_statistics.json",
        "insufficient": stage_c.path / "stage_c_insufficiency_metrics.json",
        "manifest": stage_c.path / "stage_c_run_manifest.json",
        "freeze": stage_c.path / "STAGE_C_FROZEN.md",
    }
    if any(path.exists() or path.with_suffix(path.suffix + ".tmp").exists() for path in paths.values()):
        raise FileExistsError("A Stage C finalization artifact already exists; overwrite is prohibited")
    _atomic_new_bytes(paths["raw"], stage_c.stage_path().read_bytes())
    _atomic_new_json(paths["judge"], stage_c_judge_metrics(stage_a, stage_b, records, cases))
    _atomic_new_json(paths["provider"], stage_c_provider_metrics(records))
    _atomic_new_json(paths["pairwise"], stage_c_pairwise_statistics(stage_a, stage_b, records, cases))
    _atomic_new_json(paths["insufficient"], stage_c_insufficiency_metrics(stage_a, stage_b, records, cases))
    artifact_hashes = {
        path.name: _sha256(path) for path in (
            stage_c.stage_path(), stage_c.stage_manifest_path(), stage_c.execution_manifest_path(),
            paths["raw"], paths["judge"], paths["provider"], paths["pairwise"], paths["insufficient"],
        )
    }
    manifest = {
        "run_id": STAGE_C_RUN_ID, "stage": "C", "status": "stage_c_frozen",
        "protocol_version": PROTOCOL_VERSION, "protocol_sha256": PROTOCOL_SHA256,
        "parent_stage_a_run_id": STAGE_A_RUN_ID, "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "parent_stage_b_run_id": STAGE_B_REPEAT_RUN_ID, "parent_stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        "parent_stage_b_status": stage_b_manifest.get("status"),
        "stage_c_execution_freeze_commit": anchor["execution_freeze_commit"],
        "stage_c_execution_json_sha256": anchor["execution_json_sha256"],
        "analysis_json_sha256": anchor["analysis_json_sha256"],
        "normalization_policy_version": anchor["normalization_policy_version"],
        "cell_count": INTENDED_CELLS,
        "stage_c_artifact_sha256": artifact_hashes, "frozen_at": _utc_now(),
        "immutable_input_for": "merged final analysis",
    }
    _atomic_new_json(paths["manifest"], manifest)
    artifact_hashes[paths["manifest"].name] = _sha256(paths["manifest"])
    lines = [
        "# Stage C frozen", "", f"- Run ID: `{STAGE_C_RUN_ID}`",
        f"- Stage A retrieval SHA256: `{STAGE_A_RETRIEVAL_SHA256}`",
        f"- Primary Stage B SHA256: `{PRIMARY_STAGE_B_SHA256}`",
        f"- Stage C SHA256: `{_sha256(stage_c.stage_path())}`",
        f"- Terminal cells: `{INTENDED_CELLS}`", "",
        "Stage C judgments are immutable input to preregistered analysis. Resume, overwrite, and selective regeneration are prohibited.", "", "## Artifact SHA256", "",
    ]
    lines.extend(f"- `{name}`: `{digest}`" for name, digest in sorted(artifact_hashes.items()))
    _atomic_new_bytes(paths["freeze"], ("\n".join(lines) + "\n").encode("utf-8"))
    artifact_hashes[paths["freeze"].name] = _sha256(paths["freeze"])
    return artifact_hashes


def _verify_finalized_stage_c_artifacts(
    stage_c: StageCDirectory, manifest: dict[str, Any], anchor: dict[str, Any],
) -> None:
    expected_manifest = {
        "run_id": STAGE_C_RUN_ID, "stage": "C", "status": "stage_c_frozen",
        "protocol_version": PROTOCOL_VERSION, "protocol_sha256": PROTOCOL_SHA256,
        "parent_stage_a_run_id": STAGE_A_RUN_ID,
        "parent_stage_a_retrieval_sha256": STAGE_A_RETRIEVAL_SHA256,
        "parent_stage_b_run_id": STAGE_B_REPEAT_RUN_ID,
        "parent_stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        "parent_stage_b_status": "stage_b_repeat_frozen_primary",
        "stage_c_execution_freeze_commit": anchor["execution_freeze_commit"],
        "stage_c_execution_json_sha256": anchor["execution_json_sha256"],
        "analysis_json_sha256": anchor["analysis_json_sha256"],
        "normalization_policy_version": anchor["normalization_policy_version"],
        "cell_count": INTENDED_CELLS,
    }
    mismatches: dict[str, Any] = {
        key: {"expected": value, "actual": manifest.get(key)}
        for key, value in expected_manifest.items() if manifest.get(key) != value
    }
    expected_artifacts = {
        "stage_c_judge.jsonl", "stage_c_manifest.json", "stage_c_execution_manifest.json",
        "stage_c_raw_results.jsonl", "stage_c_judge_metrics.json",
        "stage_c_provider_metrics.json", "stage_c_pairwise_statistics.json",
        "stage_c_insufficiency_metrics.json",
    }
    recorded = manifest.get("stage_c_artifact_sha256")
    if not isinstance(recorded, dict) or set(recorded) != expected_artifacts:
        mismatches["stage_c_artifact_sha256.keys"] = {
            "expected": sorted(expected_artifacts),
            "actual": sorted(recorded) if isinstance(recorded, dict) else recorded,
        }
    else:
        for name in sorted(expected_artifacts):
            path = stage_c.path / name
            actual = _sha256(path) if path.is_file() else None
            if recorded[name] != actual:
                mismatches[f"stage_c_artifact_sha256.{name}"] = {
                    "expected": recorded[name], "actual": actual,
                }
    raw_copy = stage_c.path / "stage_c_raw_results.jsonl"
    if raw_copy.is_file() and raw_copy.read_bytes() != stage_c.stage_path().read_bytes():
        mismatches["stage_c_raw_results.jsonl"] = {
            "expected": "byte-identical copy of stage_c_judge.jsonl", "actual": "content mismatch",
        }
    if not (stage_c.path / "STAGE_C_FROZEN.md").is_file():
        mismatches["STAGE_C_FROZEN.md"] = {"expected": "present", "actual": None}
    if mismatches:
        raise FatalFormalRunError(f"Finalized Stage C artifact mismatch: {json.dumps(mismatches, sort_keys=True)}")


def finalize_run(
    repository_root: Path,
    stage_c: StageCDirectory,
    *,
    expected_execution_commit: str | None = None,
    require_clean_worktree: bool = True,
    execution_config: dict[str, Any] | None = None,
    analysis_config: dict[str, Any] | None = None,
    frozen_inputs: tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, str]:
    if not isinstance(stage_c, StageCDirectory):
        raise FatalFormalRunError("Merged finalization requires the dedicated finalized primary Stage C run")
    _reject_stage_c_incident_operation(repository_root, stage_c, "merged-finalized")
    anchor = verify_stage_c_execution_freeze(
        repository_root, expected_execution_commit=expected_execution_commit,
        require_clean_worktree=require_clean_worktree, execution_config=execution_config,
        analysis_config=analysis_config,
    )
    stage_a_rows, stage_b_rows, stage_b_manifest = frozen_inputs or _verify_primary_stage_b_inputs(repository_root)
    if stage_b_manifest.get("repeat_outage_classification", {}).get("run_level_outage") is not False:
        raise FatalFormalRunError("Merged finalization requires non-outage primary Stage B")
    stage_c.verify_sealed()
    c_manifest_path = stage_c.path / "stage_c_run_manifest.json"
    c_manifest = _load_json_object(c_manifest_path, label="Stage C finalization manifest")
    _verify_finalized_stage_c_artifacts(stage_c, c_manifest, anchor)
    stage_c_rows = _validated_existing_stage_c_records(stage_c, stage_a_rows, stage_b_rows)
    a_ids = [row["experiment_id"] for row in stage_a_rows]
    b_ids = [row["experiment_id"] for row in stage_b_rows]
    c_ids = [row["experiment_id"] for row in stage_c_rows]
    if len(a_ids) != INTENDED_CELLS or a_ids != b_ids or a_ids != c_ids:
        raise FatalFormalRunError("Merged finalization requires exact ordered 192-ID equality across A/B/C")
    output_paths = [
        stage_c.path / "raw_results.jsonl", stage_c.path / "retrieval_metrics.json",
        stage_c.path / "generation_metrics.json", stage_c.path / "judge_metrics.json",
        stage_c.path / "provider_metrics.json", stage_c.path / "completion_manifest.json",
    ]
    if any(path.exists() or path.with_suffix(path.suffix + ".tmp").exists() for path in output_paths):
        raise FileExistsError("An immutable merged-finalization artifact already exists")
    raw_path = output_paths[0]
    temporary = raw_path.with_suffix(".jsonl.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        for retrieval, generation, judgment in zip(stage_a_rows, stage_b_rows, stage_c_rows, strict=True):
            record = {**retrieval, **generation, **judgment}
            record["errors"] = retrieval.get("errors", []) + generation.get("errors", []) + judgment.get("errors", [])
            record["timestamps"] = {**retrieval.get("timestamps", {}), **generation.get("timestamps", {}), **judgment.get("timestamps", {})}
            _assert_no_secret_fields(record)
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(raw_path)
    cases = load_frozen_cases(repository_root)
    _atomic_new_json(output_paths[1], retrieval_metrics(stage_a_rows, cases))
    _atomic_new_json(output_paths[2], generation_metrics(stage_b_rows))
    _atomic_new_json(output_paths[3], stage_c_judge_metrics(stage_a_rows, stage_b_rows, stage_c_rows, cases))
    _atomic_new_json(output_paths[4], {
        "generation": stage_b_provider_metrics(stage_b_rows), "judge": stage_c_provider_metrics(stage_c_rows),
        "retrieval_latency_ms_total": sum(float(row.get("retrieval_latency_ms", 0.0)) for row in stage_a_rows),
        "generation_latency_ms_total": sum(float(row.get("generation_latency_ms", 0.0)) for row in stage_b_rows),
        "judge_latency_ms_total": sum(float(row.get("judge_latency_ms", 0.0)) for row in stage_c_rows),
    })
    _atomic_new_json(output_paths[5], {
        "protocol_version": PROTOCOL_VERSION, "cell_count": INTENDED_CELLS,
        "stage_a_sha256": STAGE_A_RETRIEVAL_SHA256, "stage_b_sha256": PRIMARY_STAGE_B_SHA256,
        "stage_c_sha256": _sha256(stage_c.stage_path()), "stage_c_run_manifest_sha256": _sha256(c_manifest_path),
        "analysis_json_sha256": anchor["analysis_json_sha256"],
        "normalization_policy_version": anchor["normalization_policy_version"],
        "raw_results_sha256": _sha256(raw_path),
        "original_outage_answers_used": False, "completed_at": _utc_now(),
    })
    return {path.name: _sha256(path) for path in output_paths}
