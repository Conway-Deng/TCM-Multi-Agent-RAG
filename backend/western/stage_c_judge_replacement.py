from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
from time import perf_counter
from typing import Any

from providers import build_llm_provider
from providers.openai_compatible import ProviderUnavailable

from .formal_eval import (
    PROTOCOL_VERSION,
    STAGE_A_RETRIEVAL_SHA256,
    STAGE_C_RUN_ID,
    PRIMARY_STAGE_B_SHA256,
    PRIMARY_STAGE_B_RUN_MANIFEST_SHA256,
    StageCDirectory,
    _atomic_new_json,
    _error_type,
    _sha256,
    _utc_now,
    _verify_stage_c_r2_incident_artifacts,
)
from .formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT
from .stage_c_preflight import (
    R3_PREFLIGHT_PROBE_COUNT,
    R3_PREFLIGHT_PROBE_PLAN_VERSION,
    R3_PREFLIGHT_V1_READINESS_PATH,
    R3_PREFLIGHT_V1_READINESS_SHA256,
    StageCR3PreflightError,
    get_synthetic_probe_plan,
)
from .stage_c_preflight_v3 import (
    R3_JSON_MODE_RESPONSE_FORMAT,
    R3_PREFLIGHT_V2_READINESS_PATH,
    R3_PREFLIGHT_V2_READINESS_SHA256,
    build_stage_c_r3_json_mode_prompt,
    validate_stage_c_r3_json_mode_probe_output,
)


REPLACEMENT_POLICY_VERSION = "western-stage-c-judge-replacement-policy-v1"
PROTOCOL_AMENDMENT_VERSION = "western_formal_v0.1.3"
DOCUMENTATION_SNAPSHOT_DATE = "2026-09-20"
REPLACEMENT_PROVIDER = "siliconflow"
REPLACEMENT_TRANSPORT = copy.deepcopy(R3_JSON_MODE_RESPONSE_FORMAT)
REPLACEMENT_TEMPERATURE = 0
REPLACEMENT_MAX_TOKENS = 1200
REPLACEMENT_TIMEOUT_SECONDS = 120.0
REPLACEMENT_MINIMUM_SPACING_SECONDS = 3600.0
REPLACEMENT_REPLICATE_COUNT_REQUIRED = 2

RESERVED_FORMAL_RUN_ID_PREFIX = "western-formal-v0.1.3-stage-c-jrv1-"
RESERVED_FORMAL_DIR_NAME = "stage_c_execution_v0_1_3_jrv1"

# Canonical manifests directory relative to repository root
CANONICAL_MANIFESTS_RELATIVE_DIR = (
    "research/experiments/western_formal_v0_1/stage_c_judge_replacement_policy_v1/manifests"
)

# Historical and scientific hash anchors
POLICY_JSON_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/stage_c_judge_replacement_policy_v1/policy.json"
)
REPLACEMENT_POLICY_SHA256 = (
    "d17d538bcb650965ccbef817ceeff0f554f15a082a6461d6b99fcd81961eaae1"
)

R3_PREFLIGHT_V3_READINESS_PATH = (
    "research/experiments/western_formal_v0_1/stage_c_r3_preflight_readiness_v3.json"
)
R3_PREFLIGHT_V3_READINESS_SHA256 = (
    "b864d2dd45120eade9b7f4ff8688eb35ce7ba9c75262d6eddd365c90dc58b3d2"
)
PROTOCOL_V0_1_2_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/protocol_v0_1_2/protocol.json"
)
PROTOCOL_V0_1_2_SHA256 = "af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192"
STAGE_A_RETRIEVAL_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/runs/western-formal-v0.1.2-stage-a-20260918-01/stage_a_retrieval.jsonl"
)
STAGE_A_EXPECTED_SHA256 = "91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e"
PRIMARY_STAGE_B_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/runs/western-formal-v0.1.2-stage-b-r1-20260919-01/stage_b_generation.jsonl"
)
PRIMARY_STAGE_B_EXPECTED_SHA256 = "afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c"
PRIMARY_STAGE_B_RUN_MANIFEST_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/runs/western-formal-v0.1.2-stage-b-r1-20260919-01/stage_b_run_manifest.json"
)
PRIMARY_STAGE_B_RUN_MANIFEST_EXPECTED_SHA256 = (
    "32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511"
)
STAGE_C_R2_ANALYSIS_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_2_r2/analysis.json"
)
STAGE_C_R2_ANALYSIS_EXPECTED_SHA256 = (
    "123322b8a416697cd814561b66b3722291d421206ff6310de6667b9d31b79ec8"
)
STAGE_C_R2_JUDGMENTS_SHA256 = (
    "fd3544854e4eadfbb498cf9ab5329cee0fb45a03380b25b2c82fabef03ed5363"
)
STAGE_C_R2_INCIDENT_MANIFEST_SHA256 = (
    "24577b182eb9ba0c5a68d88419eac27fab4ab1709f19d850f050ae225dda9531"
)


class StageCJudgeReplacementError(RuntimeError):
    """Execution readiness, integrity, or policy violation for replacement judge preflight."""


@dataclass(frozen=True)
class ReplacementCandidate:
    candidate_number: int
    model_id: str
    slug: str
    serverless_supported: bool = True
    json_mode_supported: bool = True
    structured_outputs_supported: bool = False
    context_window: int = 128000
    max_output_tokens: int | None = None
    enable_thinking_required: bool = False


FROZEN_CANDIDATE_REGISTRY: tuple[ReplacementCandidate, ...] = (
    ReplacementCandidate(
        candidate_number=1,
        model_id="deepseek-ai/DeepSeek-V3.2",
        slug="deepseek-v3-2",
        serverless_supported=True,
        json_mode_supported=True,
        structured_outputs_supported=False,
        context_window=164000,
        enable_thinking_required=False,
    ),
    ReplacementCandidate(
        candidate_number=2,
        model_id="openai/gpt-oss-120b",
        slug="gpt-oss-120b",
        serverless_supported=True,
        json_mode_supported=True,
        structured_outputs_supported=False,
        context_window=131000,
        max_output_tokens=8192,
        enable_thinking_required=False,
    ),
    ReplacementCandidate(
        candidate_number=3,
        model_id="Qwen/Qwen3.5-35B-A3B",
        slug="qwen3-5-35b-a3b",
        serverless_supported=True,
        json_mode_supported=True,
        structured_outputs_supported=False,
        context_window=262000,
        enable_thinking_required=False,
    ),
)


def get_candidate(candidate_number: int) -> ReplacementCandidate:
    for cand in FROZEN_CANDIDATE_REGISTRY:
        if cand.candidate_number == candidate_number:
            return cand
    raise StageCJudgeReplacementError(
        f"Invalid candidate number {candidate_number}; frozen registry contains candidates 1..{len(FROZEN_CANDIDATE_REGISTRY)}"
    )


def get_candidate_by_model(model_id: str) -> ReplacementCandidate:
    for cand in FROZEN_CANDIDATE_REGISTRY:
        if cand.model_id == model_id:
            return cand
    raise StageCJudgeReplacementError(
        f"Model '{model_id}' is not in the frozen replacement candidate registry"
    )


def candidate_replicate_id(candidate_number: int, replicate_number: int) -> str:
    candidate = get_candidate(candidate_number)
    return (
        f"western-stage-c-judge-replacement-preflight-v1-candidate-{candidate.candidate_number:02d}-"
        f"{candidate.slug}-replicate-{replicate_number:02d}"
    )


def candidate_manifest_name(candidate_number: int, replicate_number: int) -> str:
    return (
        f"stage_c_judge_replacement_preflight_v1_candidate_{candidate_number:02d}_"
        f"replicate_{replicate_number:02d}.json"
    )


def get_canonical_manifests_dir(repository_root: Path) -> Path:
    return repository_root / CANONICAL_MANIFESTS_RELATIVE_DIR


def canonical_candidate_manifest_path(
    repository_root: Path, candidate_number: int, replicate_number: int
) -> Path:
    return get_canonical_manifests_dir(repository_root) / candidate_manifest_name(
        candidate_number, replicate_number
    )


def _verify_sha256_anchor(
    repository_root: Path, relative_path: str, expected_sha256: str, label: str
) -> str:
    path = repository_root / relative_path
    if not path.is_file():
        raise StageCJudgeReplacementError(f"{label} artifact is missing at {relative_path}")
    actual = _sha256(path)
    if actual != expected_sha256:
        raise StageCJudgeReplacementError(
            f"{label} artifact modified: expected {expected_sha256}, actual {actual}"
        )
    return actual


def verify_scientific_and_historical_hashes(repository_root: Path) -> dict[str, str]:
    incident = StageCDirectory(
        repository_root / "research/experiments/western_formal_v0_1/runs" / STAGE_C_RUN_ID
    )
    _verify_stage_c_r2_incident_artifacts(repository_root, incident)

    r2_judgments_actual = _sha256(incident.stage_path())
    if r2_judgments_actual != STAGE_C_R2_JUDGMENTS_SHA256:
        raise StageCJudgeReplacementError(
            f"Stage C r2 judgments SHA256 mismatch: expected {STAGE_C_R2_JUDGMENTS_SHA256}, actual {r2_judgments_actual}"
        )

    r2_incident_actual = _sha256(incident.incident_manifest_path())
    if r2_incident_actual != STAGE_C_R2_INCIDENT_MANIFEST_SHA256:
        raise StageCJudgeReplacementError(
            f"Stage C r2 incident manifest SHA256 mismatch: expected {STAGE_C_R2_INCIDENT_MANIFEST_SHA256}, actual {r2_incident_actual}"
        )

    policy_path = repository_root / POLICY_JSON_RELATIVE_PATH
    if not policy_path.is_file():
        raise StageCJudgeReplacementError(f"Replacement policy JSON is missing at {POLICY_JSON_RELATIVE_PATH}")
    policy_actual = _sha256(policy_path)
    if policy_actual != REPLACEMENT_POLICY_SHA256:
        raise StageCJudgeReplacementError(
            f"Replacement policy.json SHA256 mismatch: expected {REPLACEMENT_POLICY_SHA256}, actual {policy_actual}"
        )

    return {
        "r2_judgments_sha256": r2_judgments_actual,
        "r2_incident_manifest_sha256": r2_incident_actual,
        "preflight_v1_sha256": _verify_sha256_anchor(
            repository_root,
            R3_PREFLIGHT_V1_READINESS_PATH,
            R3_PREFLIGHT_V1_READINESS_SHA256,
            "Stage C r3 preflight v1",
        ),
        "preflight_v2_sha256": _verify_sha256_anchor(
            repository_root,
            R3_PREFLIGHT_V2_READINESS_PATH,
            R3_PREFLIGHT_V2_READINESS_SHA256,
            "Stage C r3 preflight v2",
        ),
        "preflight_v3_sha256": _verify_sha256_anchor(
            repository_root,
            R3_PREFLIGHT_V3_READINESS_PATH,
            R3_PREFLIGHT_V3_READINESS_SHA256,
            "Stage C r3 preflight v3",
        ),
        "protocol_v0_1_2_sha256": _verify_sha256_anchor(
            repository_root,
            PROTOCOL_V0_1_2_RELATIVE_PATH,
            PROTOCOL_V0_1_2_SHA256,
            "Protocol v0.1.2",
        ),
        "stage_a_retrieval_sha256": _verify_sha256_anchor(
            repository_root,
            STAGE_A_RETRIEVAL_RELATIVE_PATH,
            STAGE_A_EXPECTED_SHA256,
            "Stage A retrieval",
        ),
        "primary_stage_b_sha256": _verify_sha256_anchor(
            repository_root,
            PRIMARY_STAGE_B_RELATIVE_PATH,
            PRIMARY_STAGE_B_EXPECTED_SHA256,
            "Primary Stage B generation",
        ),
        "primary_stage_b_run_manifest_sha256": _verify_sha256_anchor(
            repository_root,
            PRIMARY_STAGE_B_RUN_MANIFEST_RELATIVE_PATH,
            PRIMARY_STAGE_B_RUN_MANIFEST_EXPECTED_SHA256,
            "Primary Stage B run manifest",
        ),
        "analysis_json_sha256": _verify_sha256_anchor(
            repository_root,
            STAGE_C_R2_ANALYSIS_RELATIVE_PATH,
            STAGE_C_R2_ANALYSIS_EXPECTED_SHA256,
            "Stage C r2 analysis.json",
        ),
    }


def parse_utc_timestamp(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def validate_and_load_candidate_manifest(
    path: Path,
    *,
    expected_policy_sha256: str = REPLACEMENT_POLICY_SHA256,
) -> dict[str, Any]:
    """Strictly validate and load an existing replacement candidate manifest.

    Fails closed on any corruption, structural violation, forged status, or hash mismatch.
    """
    if not path.is_file():
        raise StageCJudgeReplacementError(f"Candidate manifest file missing at {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StageCJudgeReplacementError(f"Corrupt or malformed JSON manifest at {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise StageCJudgeReplacementError(f"Candidate manifest at {path} must be a JSON object")

    # Policy and amendment version validation
    if data.get("policy_version") != REPLACEMENT_POLICY_VERSION:
        raise StageCJudgeReplacementError(
            f"Manifest {path} policy_version mismatch: expected {REPLACEMENT_POLICY_VERSION}, got {data.get('policy_version')}"
        )
    if data.get("protocol_amendment_version") != PROTOCOL_AMENDMENT_VERSION:
        raise StageCJudgeReplacementError(
            f"Manifest {path} protocol_amendment_version mismatch: expected {PROTOCOL_AMENDMENT_VERSION}, got {data.get('protocol_amendment_version')}"
        )

    cand_num = data.get("candidate_number")
    if cand_num not in {1, 2, 3}:
        raise StageCJudgeReplacementError(f"Manifest {path} has invalid candidate_number: {cand_num}")
    candidate = get_candidate(cand_num)
    if data.get("candidate_slug") != candidate.slug:
        raise StageCJudgeReplacementError(
            f"Manifest {path} candidate_slug mismatch: expected {candidate.slug}, got {data.get('candidate_slug')}"
        )
    if data.get("requested_model_id") != candidate.model_id:
        raise StageCJudgeReplacementError(
            f"Manifest {path} requested_model_id mismatch: expected {candidate.model_id}, got {data.get('requested_model_id')}"
        )

    rep_num = data.get("replicate_number")
    if rep_num not in {1, 2}:
        raise StageCJudgeReplacementError(f"Manifest {path} has invalid replicate_number: {rep_num}")
    expected_rep_id = candidate_replicate_id(cand_num, rep_num)
    if data.get("replicate_id") != expected_rep_id:
        raise StageCJudgeReplacementError(
            f"Manifest {path} replicate_id mismatch: expected {expected_rep_id}, got {data.get('replicate_id')}"
        )

    expected_filename = candidate_manifest_name(cand_num, rep_num)
    if path.name != expected_filename:
        raise StageCJudgeReplacementError(
            f"Manifest filename mismatch at {path}: expected {expected_filename}, got {path.name}"
        )

    # Provider and execution configuration invariants
    if data.get("provider") != REPLACEMENT_PROVIDER:
        raise StageCJudgeReplacementError(
            f"Manifest {path} provider mismatch: expected {REPLACEMENT_PROVIDER}, got {data.get('provider')}"
        )
    if data.get("response_format") != REPLACEMENT_TRANSPORT:
        raise StageCJudgeReplacementError(f"Manifest {path} response_format mismatch: expected {REPLACEMENT_TRANSPORT}")
    if data.get("temperature") != REPLACEMENT_TEMPERATURE:
        raise StageCJudgeReplacementError(f"Manifest {path} temperature mismatch: expected {REPLACEMENT_TEMPERATURE}")
    if data.get("max_tokens") != REPLACEMENT_MAX_TOKENS:
        raise StageCJudgeReplacementError(f"Manifest {path} max_tokens mismatch: expected {REPLACEMENT_MAX_TOKENS}")
    if float(data.get("timeout_seconds", -1)) != REPLACEMENT_TIMEOUT_SECONDS:
        raise StageCJudgeReplacementError(
            f"Manifest {path} timeout_seconds mismatch: expected {REPLACEMENT_TIMEOUT_SECONDS}, got {data.get('timeout_seconds')}"
        )
    if data.get("enable_thinking") is not False:
        raise StageCJudgeReplacementError(f"Manifest {path} enable_thinking must be false")

    if data.get("probe_plan_version") != R3_PREFLIGHT_PROBE_PLAN_VERSION:
        raise StageCJudgeReplacementError(f"Manifest {path} probe_plan_version mismatch")
    if data.get("probe_count") != R3_PREFLIGHT_PROBE_COUNT:
        raise StageCJudgeReplacementError(f"Manifest {path} probe_count mismatch")
    if data.get("raw_response_stored") is not False:
        raise StageCJudgeReplacementError(f"Manifest {path} raw_response_stored must be false")
    if data.get("outputs_eligible_as_research_data") is not False:
        raise StageCJudgeReplacementError(f"Manifest {path} outputs_eligible_as_research_data must be false")
    if data.get("outputs_must_never_enter_formal_analysis") is not True:
        raise StageCJudgeReplacementError(f"Manifest {path} outputs_must_never_enter_formal_analysis must be true")
    if data.get("formal_stage_c_run_created") is not False:
        raise StageCJudgeReplacementError(f"Manifest {path} formal_stage_c_run_created must be false")

    # Policy SHA verification
    if data.get("source_policy_sha256") != expected_policy_sha256:
        raise StageCJudgeReplacementError(
            f"Manifest {path} source_policy_sha256 mismatch: expected {expected_policy_sha256}, got {data.get('source_policy_sha256')}"
        )

    # Scientific hash anchors verification
    hashes = data.get("source_historical_and_scientific_hashes")
    if not isinstance(hashes, dict):
        raise StageCJudgeReplacementError(f"Manifest {path} missing source_historical_and_scientific_hashes dictionary")

    expected_hashes = {
        "protocol_v0_1_2_sha256": PROTOCOL_V0_1_2_SHA256,
        "stage_a_retrieval_sha256": STAGE_A_EXPECTED_SHA256,
        "primary_stage_b_sha256": PRIMARY_STAGE_B_EXPECTED_SHA256,
        "primary_stage_b_run_manifest_sha256": PRIMARY_STAGE_B_RUN_MANIFEST_EXPECTED_SHA256,
        "analysis_json_sha256": STAGE_C_R2_ANALYSIS_EXPECTED_SHA256,
        "r2_judgments_sha256": STAGE_C_R2_JUDGMENTS_SHA256,
        "r2_incident_manifest_sha256": STAGE_C_R2_INCIDENT_MANIFEST_SHA256,
        "preflight_v1_sha256": R3_PREFLIGHT_V1_READINESS_SHA256,
        "preflight_v2_sha256": R3_PREFLIGHT_V2_READINESS_SHA256,
        "preflight_v3_sha256": R3_PREFLIGHT_V3_READINESS_SHA256,
    }
    for k, v in expected_hashes.items():
        if hashes.get(k) != v:
            raise StageCJudgeReplacementError(
                f"Manifest {path} historical/scientific hash mismatch for '{k}': expected {v}, got {hashes.get(k)}"
            )

    # Probes array validation
    probes = data.get("probes")
    if not isinstance(probes, list) or len(probes) != R3_PREFLIGHT_PROBE_COUNT:
        raise StageCJudgeReplacementError(
            f"Manifest {path} probes array must contain exactly {R3_PREFLIGHT_PROBE_COUNT} probes"
        )
    synthetic_plan = get_synthetic_probe_plan()
    for idx, (spec, probe) in enumerate(zip(synthetic_plan, probes)):
        if not isinstance(probe, dict):
            raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] is not an object")
        if probe.get("probe_number") != spec["probe_number"]:
            raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] probe_number mismatch")
        if probe.get("probe_id") != spec["probe_id"]:
            raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] probe_id mismatch")
        if probe.get("answerability") != spec["answerability"]:
            raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] answerability mismatch")
        if probe.get("expected_insufficiency_label") != spec.get("expected_insufficiency_label"):
            raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] expected_insufficiency_label mismatch")
        if probe.get("raw_response_stored") is not False or "text" in probe or "response_text" in probe:
            raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] violates raw response storage policy")

        if probe.get("json_contract_success") is True:
            if probe.get("provider_reported_model") != candidate.model_id:
                raise StageCJudgeReplacementError(
                    f"Manifest {path} probe[{idx}] provider_reported_model mismatch: expected {candidate.model_id}, got {probe.get('provider_reported_model')}"
                )
            if probe.get("finish_reason") not in {None, "stop"}:
                raise StageCJudgeReplacementError(
                    f"Manifest {path} probe[{idx}] invalid finish_reason: {probe.get('finish_reason')}"
                )
            resp_sha = probe.get("response_sha256")
            if not isinstance(resp_sha, str) or len(resp_sha) != 64:
                raise StageCJudgeReplacementError(
                    f"Manifest {path} probe[{idx}] response_sha256 must be a 64-char hex string"
                )

    replicate_passed = data.get("replicate_passed")
    if replicate_passed is True:
        if data.get("status") != "passed":
            raise StageCJudgeReplacementError(f"Manifest {path} status must be 'passed' when replicate_passed=true")
        if data.get("successful_probe_count") != 6:
            raise StageCJudgeReplacementError(f"Manifest {path} successful_probe_count must be 6 on passed replicate")
        if data.get("json_contract_passed") is not True:
            raise StageCJudgeReplacementError(f"Manifest {path} json_contract_passed must be true on passed replicate")
        if data.get("formal_timeout_compatible") is not True:
            raise StageCJudgeReplacementError(f"Manifest {path} formal_timeout_compatible must be true on passed replicate")
        if data.get("timeout_occurrences", 0) != 0:
            raise StageCJudgeReplacementError(f"Manifest {path} timeout_occurrences must be 0 on passed replicate")

        for idx, probe in enumerate(probes):
            if probe.get("json_contract_success") is not True:
                raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] json_contract_success is false on passed replicate")
            if probe.get("formal_timeout_compatible") is not True:
                raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] formal_timeout_compatible is false on passed replicate")
            latency = float(probe.get("latency_ms", 999999.0))
            if latency > REPLACEMENT_TIMEOUT_SECONDS * 1000:
                raise StageCJudgeReplacementError(
                    f"Manifest {path} probe[{idx}] latency {latency}ms exceeds frozen timeout ({REPLACEMENT_TIMEOUT_SECONDS * 1000}ms)"
                )
            if probe.get("error_type") is not None:
                raise StageCJudgeReplacementError(f"Manifest {path} probe[{idx}] has error_type on passed replicate")

        per_ans = data.get("per_answerability_summary", {})
        for ans in ("supported", "partially_supported", "insufficient"):
            summary = per_ans.get(ans, {})
            if summary.get("json_contract_passed") is not True:
                raise StageCJudgeReplacementError(f"Manifest {path} {ans} summary json_contract_passed is false on passed replicate")
            if summary.get("formal_timeout_compatible") is not True:
                raise StageCJudgeReplacementError(f"Manifest {path} {ans} summary formal_timeout_compatible is false on passed replicate")
            if summary.get("timeouts", 0) != 0:
                raise StageCJudgeReplacementError(f"Manifest {path} {ans} summary has timeouts > 0 on passed replicate")
    elif replicate_passed is False:
        if data.get("status") != "failed":
            raise StageCJudgeReplacementError(f"Manifest {path} status must be 'failed' when replicate_passed=false")
        # Ensure that at least one failure condition is present
        has_failure = (
            data.get("successful_probe_count", 0) < 6
            or data.get("json_contract_passed") is not True
            or data.get("formal_timeout_compatible") is not True
            or data.get("timeout_occurrences", 0) > 0
            or any(
                p.get("json_contract_success") is not True
                or p.get("formal_timeout_compatible") is not True
                or p.get("error_type") is not None
                for p in probes
            )
        )
        if not has_failure:
            raise StageCJudgeReplacementError(
                f"Manifest {path} internally inconsistent: marked failed but all 6 probes passed without error"
            )
    else:
        raise StageCJudgeReplacementError(f"Manifest {path} missing or invalid replicate_passed boolean")

    return data


def inspect_candidate_manifests(
    manifests_dir: Path,
    *,
    expected_policy_sha256: str = REPLACEMENT_POLICY_SHA256,
) -> dict[int, dict[int, dict[str, Any]]]:
    """Inspect, strictly validate, and index all replacement preflight manifests found in manifests_dir.

    Fails closed if any manifest is corrupt, forged, altered, or unverifiable.
    """
    record: dict[int, dict[int, dict[str, Any]]] = {
        cand.candidate_number: {} for cand in FROZEN_CANDIDATE_REGISTRY
    }
    if not manifests_dir.is_dir():
        return record

    for path in sorted(manifests_dir.glob("stage_c_judge_replacement_preflight_v1_candidate_*_replicate_*.json")):
        data = validate_and_load_candidate_manifest(
            path, expected_policy_sha256=expected_policy_sha256
        )
        c_num = data["candidate_number"]
        r_num = data["replicate_number"]
        if r_num in record[c_num]:
            raise StageCJudgeReplacementError(
                f"Duplicate candidate {c_num:02d} replicate {r_num:02d} manifest detected in {manifests_dir}"
            )
        record[c_num][r_num] = data
    return record


def evaluate_runner_eligibility(
    manifests_dir: Path,
    target_candidate: int,
    target_replicate: int,
    *,
    current_time: datetime | None = None,
    expected_policy_sha256: str = REPLACEMENT_POLICY_SHA256,
) -> tuple[bool, str, float | None]:
    """Evaluate whether (target_candidate, target_replicate) is authorized by policy state machine.

    Returns:
        (is_eligible, reason, elapsed_seconds_since_rep1_if_applicable)
    """
    if target_candidate not in {1, 2, 3}:
        return False, f"Invalid candidate number {target_candidate}; must be 1, 2, or 3", None
    if target_replicate not in {1, 2}:
        return (
            False,
            f"Invalid replicate number {target_replicate}; only replicates 1 and 2 are permitted",
            None,
        )

    records = inspect_candidate_manifests(
        manifests_dir, expected_policy_sha256=expected_policy_sha256
    )
    now = current_time or datetime.now(timezone.utc)

    # Rule: Check if ANY candidate has already passed both replicates
    for cand in FROZEN_CANDIDATE_REGISTRY:
        reps = records[cand.candidate_number]
        rep1_passed = reps.get(1, {}).get("replicate_passed") is True
        rep2_passed = reps.get(2, {}).get("replicate_passed") is True
        if rep1_passed and rep2_passed:
            return (
                False,
                f"Candidate {cand.candidate_number:02d} ({cand.model_id}) already passed both replicates and qualified; later execution is permanently prohibited",
                None,
            )

    # Check state for preceding candidates
    for prev_cand_num in range(1, target_candidate):
        prev_reps = records[prev_cand_num]
        prev_rep1 = prev_reps.get(1)
        prev_rep2 = prev_reps.get(2)

        if not prev_rep1:
            return (
                False,
                f"Candidate {target_candidate:02d} is blocked because prior candidate {prev_cand_num:02d} has not been attempted",
                None,
            )

        prev_rep1_passed = prev_rep1.get("replicate_passed") is True
        if prev_rep1_passed:
            if not prev_rep2:
                return (
                    False,
                    f"Candidate {target_candidate:02d} is blocked because prior candidate {prev_cand_num:02d} passed replicate 1 and replicate 2 is pending",
                    None,
                )
            prev_rep2_passed = prev_rep2.get("replicate_passed") is True
            if prev_rep2_passed:
                return (
                    False,
                    f"Candidate {target_candidate:02d} is blocked because prior candidate {prev_cand_num:02d} qualified",
                    None,
                )
            # prev_rep2 failed: candidate terminally failed, so advancement is permitted
        else:
            # prev_rep1 failed: candidate terminally failed on replicate 1, so advancement is permitted
            pass

    # Now check target candidate itself
    cand_reps = records[target_candidate]
    rep1_data = cand_reps.get(1)
    rep2_data = cand_reps.get(2)

    if target_replicate == 1:
        if rep1_data:
            return (
                False,
                f"Candidate {target_candidate:02d} replicate 1 already exists; overwrite or retry is prohibited",
                None,
            )
        return True, f"Candidate {target_candidate:02d} replicate 1 is eligible", None

    if target_replicate == 2:
        if not rep1_data:
            return (
                False,
                f"Candidate {target_candidate:02d} replicate 2 is blocked because replicate 1 does not exist",
                None,
            )
        if rep1_data.get("replicate_passed") is not True:
            return (
                False,
                f"Candidate {target_candidate:02d} replicate 2 is prohibited because replicate 1 failed (candidate terminally failed)",
                None,
            )
        if rep2_data:
            return (
                False,
                f"Candidate {target_candidate:02d} replicate 2 already exists; third replicate or overwrite is prohibited",
                None,
            )

        # Enforce spacing >= 3600 seconds
        completed_at_str = rep1_data.get("completed_at")
        if not completed_at_str:
            return (
                False,
                f"Candidate {target_candidate:02d} replicate 1 manifest lacks completed_at timestamp",
                None,
            )
        completed_at = parse_utc_timestamp(completed_at_str)
        elapsed_seconds = (now - completed_at).total_seconds()
        if elapsed_seconds < REPLACEMENT_MINIMUM_SPACING_SECONDS:
            return (
                False,
                f"Candidate {target_candidate:02d} replicate 2 is blocked by spacing rule: elapsed {elapsed_seconds:.1f}s < required {REPLACEMENT_MINIMUM_SPACING_SECONDS:.0f}s",
                elapsed_seconds,
            )
        return (
            True,
            f"Candidate {target_candidate:02d} replicate 2 is eligible (elapsed {elapsed_seconds:.1f}s >= {REPLACEMENT_MINIMUM_SPACING_SECONDS:.0f}s)",
            elapsed_seconds,
        )

    return False, "Unknown state", None


def _validate_output_path(repository_root: Path, output_path: Path) -> Path:
    resolved = output_path.resolve()
    formal_runs = (repository_root / "research/experiments/western_formal_v0_1/runs").resolve()
    if resolved == formal_runs or formal_runs in resolved.parents:
        raise StageCJudgeReplacementError(
            "Replacement candidate preflight output must never enter the formal Stage C runs directory"
        )
    if resolved.exists() or resolved.with_suffix(resolved.suffix + ".tmp").exists():
        raise FileExistsError(
            f"Candidate preflight output already exists at {resolved}; overwrite is prohibited"
        )
    return resolved


def _validate_replacement_provider(
    provider: Any, candidate: ReplacementCandidate, timeout_seconds: float
) -> None:
    if getattr(provider, "name", None) != REPLACEMENT_PROVIDER:
        raise StageCJudgeReplacementError(
            f"Replacement judge preflight requires provider '{REPLACEMENT_PROVIDER}', got '{getattr(provider, 'name', None)}'"
        )
    if getattr(provider, "model", None) != candidate.model_id:
        raise StageCJudgeReplacementError(
            f"Provider model mismatch: expected '{candidate.model_id}', got '{getattr(provider, 'model', None)}'"
        )
    if getattr(provider, "supports_response_format", False) is not True:
        raise StageCJudgeReplacementError(
            "Configured provider does not explicitly support response_format"
        )
    if getattr(provider, "supports_json_object_response_format", False) is not True:
        raise StageCJudgeReplacementError(
            "Configured provider does not explicitly support JSON-object response_format"
        )
    if float(getattr(provider, "timeout", -1)) != timeout_seconds:
        raise StageCJudgeReplacementError(
            f"Replacement judge provider timeout mismatch: expected {timeout_seconds}, got {getattr(provider, 'timeout', None)}"
        )
    if int(getattr(provider, "max_tokens", -1)) < REPLACEMENT_MAX_TOKENS:
        raise StageCJudgeReplacementError(
            f"Replacement judge provider max_tokens is insufficient: expected >= {REPLACEMENT_MAX_TOKENS}"
        )
    if getattr(provider, "enable_thinking", None) is not False:
        raise StageCJudgeReplacementError(
            "Replacement judge preflight requires enable_thinking=false (non-thinking execution is mandatory)"
        )


async def run_stage_c_judge_replacement_preflight(
    repository_root: Path,
    output_path: Path | None = None,
    *,
    candidate_number: int,
    replicate_number: int,
    provider: Any | None = None,
    manifests_dir: Path | None = None,
    timeout_seconds: float = REPLACEMENT_TIMEOUT_SECONDS,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    """Execute one offline/online candidate preflight replicate.

    Enforces:
    - Rejection of any timeout != REPLACEMENT_TIMEOUT_SECONDS (120.0s)
    - Rejection of arbitrary output paths in production
    - Strict fail-closed verification of all prior candidate manifests
    - Candidate frozen order
    - Two-replicate requirement
    - >=3600 seconds replicate spacing
    - Immutable policy SHA256 and scientific hashes
    - Formal-compatible 120s timeout
    - 6/6 JSON contract pass
    """
    if float(timeout_seconds) != REPLACEMENT_TIMEOUT_SECONDS:
        raise StageCJudgeReplacementError(
            f"Replacement preflight timeout must be exactly {REPLACEMENT_TIMEOUT_SECONDS}s, got {timeout_seconds}s"
        )

    candidate = get_candidate(candidate_number)
    rep_id = candidate_replicate_id(candidate_number, replicate_number)

    # Resolve canonical manifests directory and target output path
    if manifests_dir is None:
        canonical_dir = get_canonical_manifests_dir(repository_root)
        canonical_dir.mkdir(parents=True, exist_ok=True)
        search_dir = canonical_dir
        canonical_output = canonical_candidate_manifest_path(
            repository_root, candidate_number, replicate_number
        )
        if output_path is not None and output_path.resolve() != canonical_output.resolve():
            raise StageCJudgeReplacementError(
                f"Arbitrary output path override is prohibited in production; manifests must be stored at {canonical_output}"
            )
        target_output = canonical_output
    else:
        search_dir = manifests_dir
        if output_path is None:
            target_output = manifests_dir / candidate_manifest_name(
                candidate_number, replicate_number
            )
        else:
            target_output = output_path
        expected_name = candidate_manifest_name(candidate_number, replicate_number)
        if target_output.name != expected_name:
            raise StageCJudgeReplacementError(
                f"Candidate manifest output filename must be '{expected_name}', got '{target_output.name}'"
            )

    target_output = _validate_output_path(repository_root, target_output)

    # Verify policy.json exists and matches pinned SHA256
    policy_path = repository_root / POLICY_JSON_RELATIVE_PATH
    if not policy_path.is_file():
        raise StageCJudgeReplacementError(f"Policy JSON is missing at {POLICY_JSON_RELATIVE_PATH}")
    actual_policy_sha = _sha256(policy_path)
    if actual_policy_sha != REPLACEMENT_POLICY_SHA256:
        raise StageCJudgeReplacementError(
            f"Replacement policy.json SHA256 mismatch: expected {REPLACEMENT_POLICY_SHA256}, actual {actual_policy_sha}"
        )

    # Verify state machine against verified prior manifests
    is_eligible, reason, elapsed_spacing = evaluate_runner_eligibility(
        search_dir,
        candidate_number,
        replicate_number,
        current_time=current_time,
        expected_policy_sha256=REPLACEMENT_POLICY_SHA256,
    )
    if not is_eligible:
        raise StageCJudgeReplacementError(f"Candidate preflight rejected by state machine: {reason}")

    # Verify scientific & historical integrity
    source_hashes = verify_scientific_and_historical_hashes(repository_root)

    # Validate provider contract
    active = provider or build_llm_provider(candidate.model_id, timeout_override=REPLACEMENT_TIMEOUT_SECONDS)
    _validate_replacement_provider(active, candidate, REPLACEMENT_TIMEOUT_SECONDS)

    probe_plan = get_synthetic_probe_plan()
    if len(probe_plan) != R3_PREFLIGHT_PROBE_COUNT:
        raise StageCJudgeReplacementError(
            f"Frozen synthetic probe matrix has changed: expected {R3_PREFLIGHT_PROBE_COUNT}"
        )

    started_at = _utc_now()
    probes: list[dict[str, Any]] = []

    for spec in probe_plan:
        retrieval = spec["retrieval"]
        prompt = build_stage_c_r3_json_mode_prompt(
            question=spec["question"],
            answer=spec["answer"],
            retrieved_evidence=spec["evidence"],
            expected_evidence_points=retrieval["expected_evidence_points"],
            answerability=retrieval["answerability"],
        )
        started = perf_counter()
        result: Any | None = None
        error_type: str | None = None
        error_message: str | None = None
        normalization: str | None = None
        json_contract_success = False

        try:
            result = await active.generate(
                system=JUDGE_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=REPLACEMENT_TEMPERATURE,
                max_tokens=REPLACEMENT_MAX_TOKENS,
                response_format=copy.deepcopy(REPLACEMENT_TRANSPORT),
            )
            reported_model = getattr(result, "model", None)
            if reported_model != candidate.model_id:
                error_type = "model_identity_mismatch"
                error_message = (
                    f"Provider-reported model mismatch: expected '{candidate.model_id}', got '{reported_model}'"
                )
            elif getattr(result, "finish_reason", None) not in {None, "stop"}:
                error_type = "unsupported_finish_reason"
                error_message = (
                    f"Unsupported finish_reason={getattr(result, 'finish_reason', None)}"
                )
            else:
                _, normalization = validate_stage_c_r3_json_mode_probe_output(
                    result.text,
                    retrieval=retrieval,
                    expected_insufficiency_label=spec.get("expected_insufficiency_label"),
                    require_all_enums_exercised=spec.get("require_all_enums_exercised", False),
                )
                json_contract_success = True
        except ProviderUnavailable as exc:
            error_type = _error_type(exc)
            error_message = str(exc)
        except (StageCR3PreflightError, json.JSONDecodeError) as exc:
            error_type = "schema_or_contract_failure"
            error_message = str(exc)
        except TypeError as exc:
            error_type = "transport_or_type_contract_failure"
            error_message = str(exc)
        # Explicit design: unexpected internal exceptions are NOT caught here.
        # They propagate upward, aborting the replicate and creating no manifest.

        latency_ms = round((perf_counter() - started) * 1000, 3)
        formal_timeout_compatible = (
            result is not None
            and error_type != "timeout"
            and latency_ms <= REPLACEMENT_TIMEOUT_SECONDS * 1000
        )

        response_sha256: str | None = None
        if result is not None and isinstance(getattr(result, "text", None), str):
            response_sha256 = hashlib.sha256(result.text.encode("utf-8")).hexdigest()

        probes.append({
            "probe_number": spec["probe_number"],
            "probe_id": spec["probe_id"],
            "answerability": spec["answerability"],
            "expected_evidence_point_count": len(retrieval["expected_evidence_points"]),
            "expected_insufficiency_label": spec.get("expected_insufficiency_label"),
            "synthetic_non_formal": True,
            "provider_call_success": result is not None,
            "json_contract_success": json_contract_success,
            "formal_timeout_compatible": formal_timeout_compatible,
            "normalization": normalization,
            "provider_reported_model": getattr(result, "model", None),
            "finish_reason": getattr(result, "finish_reason", None),
            "latency_ms": latency_ms,
            "error_type": error_type,
            "error_message": error_message,
            "response_sha256": response_sha256,
            "raw_response_stored": False,
        })

    completed_at = _utc_now()
    latencies = [float(probe["latency_ms"]) for probe in probes]
    successful_count = sum(probe["json_contract_success"] is True for probe in probes)
    timeout_count = sum(probe["error_type"] == "timeout" for probe in probes)

    per_answerability: dict[str, dict[str, Any]] = {}
    for answerability in ("supported", "partially_supported", "insufficient"):
        subset = [probe for probe in probes if probe["answerability"] == answerability]
        contract_successes = sum(probe["json_contract_success"] is True for probe in subset)
        timeout_compatible = all(probe["formal_timeout_compatible"] is True for probe in subset)
        per_answerability[answerability] = {
            "attempted": len(subset),
            "json_contract_successful": contract_successes,
            "json_contract_passed": len(subset) == 2 and contract_successes == 2,
            "formal_timeout_compatible": timeout_compatible,
            "timeouts": sum(probe["error_type"] == "timeout" for probe in subset),
        }

    json_contract_passed = (
        successful_count == R3_PREFLIGHT_PROBE_COUNT
        and all(item["json_contract_passed"] is True for item in per_answerability.values())
    )
    all_timeouts_compatible = all(
        probe["formal_timeout_compatible"] is True for probe in probes
    )
    replicate_passed = json_contract_passed and all_timeouts_compatible and timeout_count == 0

    # Determine candidate qualification status
    if replicate_passed:
        if replicate_number == 1:
            qualification_status = "replicate_01_passed_pending_replicate_02"
            next_candidate_eligibility = "blocked_pending_replicate_02"
        else:
            qualification_status = "qualified_and_selected"
            next_candidate_eligibility = "permanently_blocked_earlier_candidate_qualified"
    else:
        qualification_status = f"terminally_failed_on_replicate_{replicate_number:02d}"
        if candidate_number < len(FROZEN_CANDIDATE_REGISTRY):
            next_cand = get_candidate(candidate_number + 1)
            next_candidate_eligibility = (
                f"candidate_{next_cand.candidate_number:02d}_{next_cand.slug}_now_eligible"
            )
        else:
            next_candidate_eligibility = "all_registry_candidates_exhausted"

    manifest: dict[str, Any] = {
        "policy_version": REPLACEMENT_POLICY_VERSION,
        "protocol_amendment_version": PROTOCOL_AMENDMENT_VERSION,
        "candidate_number": candidate.candidate_number,
        "candidate_slug": candidate.slug,
        "requested_model_id": candidate.model_id,
        "replicate_number": replicate_number,
        "replicate_id": rep_id,
        "status": "passed" if replicate_passed else "failed",
        "replicate_passed": replicate_passed,
        "candidate_qualification_status": qualification_status,
        "next_candidate_eligibility": next_candidate_eligibility,
        "started_at": started_at,
        "completed_at": completed_at,
        "replicate_spacing_seconds": elapsed_spacing,
        "synthetic_non_formal": True,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "provider": REPLACEMENT_PROVIDER,
        "response_format": copy.deepcopy(REPLACEMENT_TRANSPORT),
        "temperature": REPLACEMENT_TEMPERATURE,
        "max_tokens": REPLACEMENT_MAX_TOKENS,
        "timeout_seconds": REPLACEMENT_TIMEOUT_SECONDS,
        "enable_thinking": False,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "successful_probe_count": successful_count,
        "json_contract_passed": json_contract_passed,
        "formal_timeout_compatible": all_timeouts_compatible,
        "timeout_occurrences": timeout_count,
        "per_answerability_summary": per_answerability,
        "latency_metrics": {
            "mean_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
            "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
            "max_latency_ms": max(latencies) if latencies else 0.0,
        },
        "source_policy_sha256": actual_policy_sha,
        "source_historical_and_scientific_hashes": source_hashes,
        "judge_system_prompt_sha256": hashlib.sha256(
            JUDGE_SYSTEM_PROMPT.encode("utf-8")
        ).hexdigest(),
        "canonical_formal_judge_output_schema_sha256": hashlib.sha256(
            json.dumps(
                FormalJudgeOutput.model_json_schema(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "no_repair_declaration": {
            "coercion": False,
            "semantic_normalization": False,
            "synonym_repair": False,
            "post_hoc_value_repair": False,
        },
        "raw_response_stored": False,
        "probes": probes,
    }

    _atomic_new_json(target_output, manifest)
    return manifest
