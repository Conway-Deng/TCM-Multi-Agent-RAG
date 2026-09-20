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

# Historical and scientific hash anchors
POLICY_JSON_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/stage_c_judge_replacement_policy_v1/policy.json"
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
    """Execution readiness or policy violation for replacement judge preflight."""


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


def inspect_candidate_manifests(
    manifests_dir: Path,
) -> dict[int, dict[int, dict[str, Any]]]:
    """Inspect and index all replacement preflight candidate manifests found in manifests_dir."""
    record: dict[int, dict[int, dict[str, Any]]] = {
        cand.candidate_number: {} for cand in FROZEN_CANDIDATE_REGISTRY
    }
    if not manifests_dir.is_dir():
        return record

    for path in manifests_dir.glob("stage_c_judge_replacement_preflight_v1_candidate_*_replicate_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        c_num = data.get("candidate_number")
        r_num = data.get("replicate_number")
        if isinstance(c_num, int) and isinstance(r_num, int) and c_num in record:
            record[c_num][r_num] = data
    return record


def evaluate_runner_eligibility(
    manifests_dir: Path,
    target_candidate: int,
    target_replicate: int,
    *,
    current_time: datetime | None = None,
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

    records = inspect_candidate_manifests(manifests_dir)
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
            # Replicate 1 passed; did replicate 2 fail?
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
    output_path: Path,
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
    - Candidate frozen order
    - State machine verification against prior manifests
    - Two-replicate requirement
    - >=3600 seconds replicate spacing
    - Immutable historical and scientific hashes
    - Formal-compatible 120s timeout
    - 6/6 JSON contract pass
    """
    candidate = get_candidate(candidate_number)
    rep_id = candidate_replicate_id(candidate_number, replicate_number)
    output_path = _validate_output_path(repository_root, output_path)

    # Verify state machine
    search_dir = manifests_dir or output_path.parent
    is_eligible, reason, elapsed_spacing = evaluate_runner_eligibility(
        search_dir,
        candidate_number,
        replicate_number,
        current_time=current_time,
    )
    if not is_eligible:
        raise StageCJudgeReplacementError(f"Candidate preflight rejected by state machine: {reason}")

    # Verify scientific & historical integrity
    source_hashes = verify_scientific_and_historical_hashes(repository_root)
    policy_path = repository_root / POLICY_JSON_RELATIVE_PATH
    if not policy_path.is_file():
        raise StageCJudgeReplacementError(f"Policy JSON is missing at {POLICY_JSON_RELATIVE_PATH}")
    policy_sha256 = _sha256(policy_path)

    # Validate provider contract
    active = provider or build_llm_provider(candidate.model_id, timeout_override=timeout_seconds)
    _validate_replacement_provider(active, candidate, timeout_seconds)

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
                raise StageCJudgeReplacementError(
                    f"Provider-reported model mismatch: expected '{candidate.model_id}', got '{reported_model}'"
                )
            if getattr(result, "finish_reason", None) not in {None, "stop"}:
                raise StageCJudgeReplacementError(
                    f"Unsupported finish_reason={getattr(result, 'finish_reason', None)}"
                )
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
        except TypeError as exc:
            raise StageCJudgeReplacementError(
                "Configured provider rejected the JSON-object response_format argument"
            ) from exc
        except Exception as exc:
            error_type = "schema_or_contract_failure"
            error_message = str(exc)

        latency_ms = round((perf_counter() - started) * 1000, 3)
        formal_timeout_compatible = (
            result is not None
            and error_type != "timeout"
            and latency_ms <= timeout_seconds * 1000
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
        else:  # replicate_number == 2
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
        "timeout_seconds": timeout_seconds,
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
        "source_policy_sha256": policy_sha256,
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

    _atomic_new_json(output_path, manifest)
    return manifest
