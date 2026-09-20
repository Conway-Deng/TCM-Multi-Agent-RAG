from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
from time import perf_counter
from typing import Any, Literal

from providers import build_llm_provider
from providers.openai_compatible import ProviderUnavailable

from .formal_eval import _atomic_new_json, _error_type, _sha256, _utc_now
from .formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT
from .stage_c_judge_replacement import verify_scientific_and_historical_hashes
from .stage_c_preflight import (
    R3_PREFLIGHT_PROBE_COUNT,
    R3_PREFLIGHT_PROBE_PLAN_VERSION,
    StageCR3PreflightError,
    get_synthetic_probe_plan,
)
from .stage_c_preflight_v3 import (
    R3_JSON_MODE_RESPONSE_FORMAT,
    build_stage_c_r3_json_mode_prompt,
    validate_stage_c_r3_json_mode_probe_output,
)


FREE_POLICY_VERSION = "western-stage-c-judge-replacement-policy-v2-free"
FREE_PROTOCOL_AMENDMENT_VERSION = "western_formal_v0.1.4"
FREE_POLICY_SHA256 = "1e77ab1a85ab54e155926c0c9c2b6a7e26728243415d6ccc484cc81c47f89648"
FREE_POLICY_RELATIVE_DIR = (
    "research/experiments/western_formal_v0_1/stage_c_judge_replacement_policy_v2_free"
)
FREE_POLICY_JSON_RELATIVE_PATH = f"{FREE_POLICY_RELATIVE_DIR}/policy.json"
FREE_MANIFESTS_RELATIVE_DIR = f"{FREE_POLICY_RELATIVE_DIR}/manifests"
FREE_PROVIDER = "siliconflow"
FREE_TRANSPORT = copy.deepcopy(R3_JSON_MODE_RESPONSE_FORMAT)
FREE_TEMPERATURE = 0
FREE_MAX_TOKENS = 1200
FREE_TIMEOUT_SECONDS = 120.0
FREE_MINIMUM_SPACING_SECONDS = 3600.0
FREE_REPLICATES_REQUIRED = 2

OPERATIONAL_UNEVALUABILITY_AMENDMENT_ID = (
    "western-stage-c-judge-replacement-policy-v2-free-amendment-01"
)
OPERATIONAL_UNEVALUABILITY_STATE = "terminal_operational_unevaluable"
OPERATIONAL_UNEVALUABILITY_LABEL = (
    "operationally_unevaluable_under_current_provider_conditions"
)
OPERATIONAL_UNEVALUABILITY_AMENDMENT_SHA256 = (
    "87d237841b747fef74d1ed7d39ac99e2a0c8a84bf7ec57bc10222e399192bfc9"
)
OPERATIONAL_UNEVALUABILITY_AMENDMENT_RELATIVE_DIR = (
    f"{FREE_POLICY_RELATIVE_DIR}/amendments/operational_unevaluability_amendment_01"
)
OPERATIONAL_UNEVALUABILITY_AMENDMENT_JSON_RELATIVE_PATH = (
    f"{OPERATIONAL_UNEVALUABILITY_AMENDMENT_RELATIVE_DIR}/amendment.json"
)
OPERATIONAL_UNEVALUABILITY_ADJUDICATIONS_RELATIVE_DIR = (
    f"{OPERATIONAL_UNEVALUABILITY_AMENDMENT_RELATIVE_DIR}/adjudications"
)

F1_ORDINARY_MANIFEST_RELATIVE_PATH = (
    f"{FREE_MANIFESTS_RELATIVE_DIR}/candidate-01-replicate-01.json"
)
F1_ORDINARY_MANIFEST_SHA256 = (
    "1f0a64a7b698e2d49c84f8f0b113d9f492ed4c40e742e4e664d8d0557efb8bf6"
)
F1_RECOVERY_MANIFEST_RELATIVE_PATH = (
    f"{FREE_MANIFESTS_RELATIVE_DIR}/candidate-01-replicate-01-recovery-01.json"
)
F1_RECOVERY_MANIFEST_SHA256 = (
    "dff39085c3d9091b76a40634eadbf167cfc0ef8e360e79a863f399d0c92a33a2"
)

OLD_POLICY_V1_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/stage_c_judge_replacement_policy_v1/policy.json"
)
OLD_POLICY_V1_SHA256 = "d17d538bcb650965ccbef817ceeff0f554f15a082a6461d6b99fcd81961eaae1"
PAID_DEEPSEEK_INCIDENT_RELATIVE_PATH = (
    "research/experiments/western_formal_v0_1/stage_c_judge_replacement_policy_v1/manifests/"
    "stage_c_judge_replacement_preflight_v1_candidate_01_replicate_01.json"
)
PAID_DEEPSEEK_INCIDENT_SHA256 = (
    "9f445fa65b134c754c0ea5ff6235ebc0a3c5f570f37b09e1676d2492bf620563"
)
EXPECTED_SOURCE_HASHES = {
    "free_policy_sha256": FREE_POLICY_SHA256,
    "replacement_policy_v1_sha256": OLD_POLICY_V1_SHA256,
    "paid_deepseek_candidate_01_incident_sha256": PAID_DEEPSEEK_INCIDENT_SHA256,
    "r2_judgments_sha256": "fd3544854e4eadfbb498cf9ab5329cee0fb45a03380b25b2c82fabef03ed5363",
    "r2_incident_manifest_sha256": "24577b182eb9ba0c5a68d88419eac27fab4ab1709f19d850f050ae225dda9531",
    "preflight_v1_sha256": "4129c0fae0ddf8f8da3d81bc6e18e673bdd71b5d512ff4c97fc01973a530d9e3",
    "preflight_v2_sha256": "1a70f189b52cb9f539807b0f8fa172be6a47ced21d384bcca7db0b81a514df94",
    "preflight_v3_sha256": "b864d2dd45120eade9b7f4ff8688eb35ce7ba9c75262d6eddd365c90dc58b3d2",
    "protocol_v0_1_2_sha256": "af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192",
    "stage_a_retrieval_sha256": "91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e",
    "primary_stage_b_sha256": "afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c",
    "primary_stage_b_run_manifest_sha256": "32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511",
    "analysis_json_sha256": "123322b8a416697cd814561b66b3722291d421206ff6310de6667b9d31b79ec8",
}

ThinkingToggle = Literal["send_false", "omit"]
FailureClass = Literal[
    "candidate_readiness_failure",
    "infrastructure_incident",
    "ambiguous_technical_failure",
]
AttemptClassification = Literal[
    "passed",
    "candidate_readiness_failure",
    "infrastructure_incident",
    "ambiguous_technical_failure",
]


class StageCFreeJudgeError(RuntimeError):
    """A fail-closed v2-free policy, integrity, or execution error."""


@dataclass(frozen=True)
class FreeJudgeCandidate:
    candidate_number: int
    model_id: str
    slug: str
    thinking_toggle: ThinkingToggle

    @property
    def expected_provider_enable_thinking(self) -> bool | None:
        return False if self.thinking_toggle == "send_false" else None


FREE_CANDIDATES: tuple[FreeJudgeCandidate, ...] = (
    FreeJudgeCandidate(1, "XingChenAGI/Xing4.0-29B", "xing4-0-29b", "omit"),
    FreeJudgeCandidate(2, "THUDM/GLM-4-9B-0414", "glm-4-9b-0414", "omit"),
    FreeJudgeCandidate(
        3,
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        "deepseek-r1-0528-qwen3-8b",
        "send_false",
    ),
    FreeJudgeCandidate(4, "Qwen/Qwen3.5-4B", "qwen3-5-4b", "omit"),
)

_ATTEMPT_PATTERN = re.compile(
    r"^candidate-(?P<candidate>0[1-4])-replicate-(?P<replicate>0[1-2])"
    r"(?P<recovery>-recovery-01)?\.json$"
)
_INELIGIBILITY_PATTERN = re.compile(
    r"^candidate-(?P<candidate>0[1-4])-zero-cost-ineligibility\.json$"
)
_OPERATIONAL_UNEVALUABILITY_PATTERN = re.compile(
    r"^candidate-(?P<candidate>0[1-4])-operationally-unevaluable\.json$"
)


def get_free_candidate(candidate_number: int) -> FreeJudgeCandidate:
    for candidate in FREE_CANDIDATES:
        if candidate.candidate_number == candidate_number:
            return candidate
    raise StageCFreeJudgeError(
        f"Invalid candidate number {candidate_number}; frozen free registry contains candidates 1..4"
    )


def get_free_candidate_by_model(model_id: str) -> FreeJudgeCandidate:
    for candidate in FREE_CANDIDATES:
        if candidate.model_id == model_id:
            return candidate
    raise StageCFreeJudgeError(f"Model '{model_id}' is not in the frozen free candidate registry")


def free_attempt_id(
    candidate_number: int,
    replicate_number: int,
    recovery_number: int = 0,
) -> str:
    candidate = get_free_candidate(candidate_number)
    if replicate_number not in {1, 2}:
        raise StageCFreeJudgeError("Only replicate numbers 1 and 2 are permitted")
    if recovery_number not in {0, 1}:
        raise StageCFreeJudgeError("Only recovery number 1 is permitted")
    suffix = "-recovery-01" if recovery_number == 1 else ""
    return (
        f"western-stage-c-free-judge-preflight-v1-candidate-{candidate.candidate_number:02d}-"
        f"{candidate.slug}-replicate-{replicate_number:02d}{suffix}"
    )


def free_manifest_name(
    candidate_number: int,
    replicate_number: int,
    recovery_number: int = 0,
) -> str:
    get_free_candidate(candidate_number)
    if replicate_number not in {1, 2}:
        raise StageCFreeJudgeError("Only replicate numbers 1 and 2 are permitted")
    if recovery_number not in {0, 1}:
        raise StageCFreeJudgeError("Only recovery number 1 is permitted")
    suffix = "-recovery-01" if recovery_number == 1 else ""
    return f"candidate-{candidate_number:02d}-replicate-{replicate_number:02d}{suffix}.json"


def zero_cost_ineligibility_name(candidate_number: int) -> str:
    get_free_candidate(candidate_number)
    return f"candidate-{candidate_number:02d}-zero-cost-ineligibility.json"


def get_free_manifests_dir(repository_root: Path) -> Path:
    return repository_root / FREE_MANIFESTS_RELATIVE_DIR


def get_operational_unevaluability_amendment_dir(repository_root: Path) -> Path:
    return repository_root / OPERATIONAL_UNEVALUABILITY_AMENDMENT_RELATIVE_DIR


def operational_unevaluability_adjudication_name(candidate_number: int) -> str:
    get_free_candidate(candidate_number)
    return f"candidate-{candidate_number:02d}-operationally-unevaluable.json"


def _default_operational_amendment_dir(manifests_dir: Path) -> Path | None:
    if (
        manifests_dir.name == "manifests"
        and manifests_dir.parent.name == "stage_c_judge_replacement_policy_v2_free"
    ):
        return manifests_dir.parent / "amendments" / "operational_unevaluability_amendment_01"
    return None


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise StageCFreeJudgeError(f"Invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise StageCFreeJudgeError(f"Timestamp must be timezone-aware: {value!r}")
    return parsed


def _verify_hash(repository_root: Path, relative_path: str, expected: str, label: str) -> str:
    path = repository_root / relative_path
    if not path.is_file():
        raise StageCFreeJudgeError(f"{label} is missing at {relative_path}")
    actual = _sha256(path)
    if actual != expected:
        raise StageCFreeJudgeError(
            f"{label} SHA256 mismatch: expected {expected}, actual {actual}"
        )
    return actual


def verify_free_policy_and_history(repository_root: Path) -> dict[str, str]:
    policy_sha = _verify_hash(
        repository_root,
        FREE_POLICY_JSON_RELATIVE_PATH,
        FREE_POLICY_SHA256,
        "Free-only policy.json",
    )
    old_policy_sha = _verify_hash(
        repository_root,
        OLD_POLICY_V1_RELATIVE_PATH,
        OLD_POLICY_V1_SHA256,
        "Replacement policy v1",
    )
    paid_incident_sha = _verify_hash(
        repository_root,
        PAID_DEEPSEEK_INCIDENT_RELATIVE_PATH,
        PAID_DEEPSEEK_INCIDENT_SHA256,
        "Paid DeepSeek Candidate 01 incident",
    )
    try:
        historical = verify_scientific_and_historical_hashes(repository_root)
    except Exception as exc:
        raise StageCFreeJudgeError(f"Historical/scientific integrity check failed: {exc}") from exc
    return {
        **historical,
        "free_policy_sha256": policy_sha,
        "replacement_policy_v1_sha256": old_policy_sha,
        "paid_deepseek_candidate_01_incident_sha256": paid_incident_sha,
    }


def classify_provider_exception(exc: ProviderUnavailable) -> tuple[FailureClass, str]:
    error_type = _error_type(exc)
    status = getattr(exc, "http_status", None)
    if status in {401, 402, 403, 404, 408, 429}:
        return "infrastructure_incident", f"http_{status}"
    if error_type in {
        "rate_limit",
        "connectivity",
        "http_5xx",
        "timeout",
        "authentication",
        "account_access",
        "model_unavailable",
    }:
        return "infrastructure_incident", error_type
    if error_type == "http_4xx" and status in {400, 422}:
        return "candidate_readiness_failure", "required_parameter_rejected"
    if error_type == "malformed_response":
        return "ambiguous_technical_failure", "malformed_provider_response"
    return "ambiguous_technical_failure", error_type or "unknown"


def _attempt_classification(probes: list[dict[str, Any]]) -> AttemptClassification:
    classes = {probe.get("failure_class") for probe in probes if probe.get("failure_class")}
    if "candidate_readiness_failure" in classes:
        return "candidate_readiness_failure"
    if "ambiguous_technical_failure" in classes:
        return "ambiguous_technical_failure"
    if "infrastructure_incident" in classes:
        return "infrastructure_incident"
    if probes and all(probe.get("json_contract_success") is True for probe in probes):
        return "passed"
    return "ambiguous_technical_failure"


def _classification_flags(
    classification: AttemptClassification,
    recovery_number: int,
) -> dict[str, bool]:
    return {
        "candidate_terminally_failed": classification == "candidate_readiness_failure",
        "advancement_authorized": classification == "candidate_readiness_failure",
        "infrastructure_recovery_authorized": (
            classification == "infrastructure_incident" and recovery_number == 0
        ),
        "manual_methodology_review_required": (
            classification == "ambiguous_technical_failure"
            or (classification == "infrastructure_incident" and recovery_number == 1)
        ),
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise StageCFreeJudgeError(f"Corrupt manifest at {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StageCFreeJudgeError(f"Manifest at {path} must be a JSON object")
    return value


def validate_free_attempt_manifest(path: Path) -> dict[str, Any]:
    match = _ATTEMPT_PATTERN.fullmatch(path.name)
    if not match:
        raise StageCFreeJudgeError(f"Unexpected free-policy attempt filename: {path.name}")
    data = _read_json_object(path)
    candidate_number = int(match.group("candidate"))
    replicate_number = int(match.group("replicate"))
    recovery_number = 1 if match.group("recovery") else 0
    candidate = get_free_candidate(candidate_number)

    exact = {
        "policy_version": FREE_POLICY_VERSION,
        "protocol_amendment_version": FREE_PROTOCOL_AMENDMENT_VERSION,
        "source_policy_sha256": FREE_POLICY_SHA256,
        "candidate_number": candidate_number,
        "candidate_slug": candidate.slug,
        "requested_model_id": candidate.model_id,
        "replicate_number": replicate_number,
        "recovery_number": recovery_number,
        "attempt_kind": "infrastructure_recovery" if recovery_number else "ordinary_replicate",
        "attempt_id": free_attempt_id(candidate_number, replicate_number, recovery_number),
        "provider": FREE_PROVIDER,
        "response_format": FREE_TRANSPORT,
        "temperature": FREE_TEMPERATURE,
        "max_tokens": FREE_MAX_TOKENS,
        "timeout_seconds": FREE_TIMEOUT_SECONDS,
        "thinking_toggle": candidate.thinking_toggle,
        "enable_thinking_sent": candidate.expected_provider_enable_thinking,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "raw_response_stored": False,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
    }
    for key, expected in exact.items():
        if data.get(key) != expected:
            raise StageCFreeJudgeError(
                f"Manifest {path} field {key!r} mismatch: expected {expected!r}, got {data.get(key)!r}"
            )
    confirmation = data.get("zero_cost_confirmation")
    if not isinstance(confirmation, dict) or confirmation.get("confirmed") is not True:
        raise StageCFreeJudgeError(f"Manifest {path} lacks required zero-cost confirmation")
    if confirmation.get("candidate_model_id") != candidate.model_id:
        raise StageCFreeJudgeError(f"Manifest {path} zero-cost candidate identity mismatch")
    _parse_utc(confirmation.get("confirmed_at"))

    source_hashes = data.get("source_historical_and_scientific_hashes")
    if not isinstance(source_hashes, dict):
        raise StageCFreeJudgeError(f"Manifest {path} lacks source hashes")
    for key, expected in EXPECTED_SOURCE_HASHES.items():
        if source_hashes.get(key) != expected:
            raise StageCFreeJudgeError(f"Manifest {path} source hash mismatch for {key}")

    probes = data.get("probes")
    plan = get_synthetic_probe_plan()
    if not isinstance(probes, list) or len(probes) != 6 or len(plan) != 6:
        raise StageCFreeJudgeError(f"Manifest {path} must contain exactly six probes")
    for index, (probe, spec) in enumerate(zip(probes, plan)):
        if not isinstance(probe, dict):
            raise StageCFreeJudgeError(f"Manifest {path} probe {index} is not an object")
        for key in ("text", "response_text", "raw_response"):
            if key in probe:
                raise StageCFreeJudgeError(f"Manifest {path} stores prohibited raw response field {key}")
        if probe.get("raw_response_stored") is not False:
            raise StageCFreeJudgeError(f"Manifest {path} probe {index} raw_response_stored must be false")
        expected_probe = {
            "probe_number": spec["probe_number"],
            "probe_id": spec["probe_id"],
            "answerability": spec["answerability"],
            "expected_insufficiency_label": spec.get("expected_insufficiency_label"),
        }
        for key, expected in expected_probe.items():
            if probe.get(key) != expected:
                raise StageCFreeJudgeError(f"Manifest {path} probe {index} {key} mismatch")
        failure_class = probe.get("failure_class")
        if failure_class not in {None, "candidate_readiness_failure", "infrastructure_incident", "ambiguous_technical_failure"}:
            raise StageCFreeJudgeError(f"Manifest {path} probe {index} has invalid failure_class")
        if probe.get("json_contract_success") is True:
            if failure_class is not None:
                raise StageCFreeJudgeError(f"Manifest {path} successful probe {index} has failure_class")
            if probe.get("provider_reported_model") != candidate.model_id:
                raise StageCFreeJudgeError(f"Manifest {path} successful probe {index} model identity mismatch")
            response_sha = probe.get("response_sha256")
            if not isinstance(response_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", response_sha):
                raise StageCFreeJudgeError(f"Manifest {path} successful probe {index} response SHA invalid")
        if probe.get("provider_call_success") is True:
            reported_model = probe.get("provider_reported_model")
            if not isinstance(reported_model, str) or not reported_model.strip():
                raise StageCFreeJudgeError(f"Manifest {path} probe {index} provider model is malformed")
            response_sha = probe.get("response_sha256")
            if not isinstance(response_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", response_sha):
                raise StageCFreeJudgeError(f"Manifest {path} probe {index} response SHA invalid")
        elif probe.get("provider_reported_model") is not None or probe.get("response_sha256") is not None:
            raise StageCFreeJudgeError(f"Manifest {path} failed provider call {index} has response provenance")
        try:
            latency_ms = float(probe.get("latency_ms"))
        except (TypeError, ValueError) as exc:
            raise StageCFreeJudgeError(f"Manifest {path} probe {index} latency is invalid") from exc
        if latency_ms < 0:
            raise StageCFreeJudgeError(f"Manifest {path} probe {index} latency is negative")

    classification = _attempt_classification(probes)
    if data.get("execution_classification") != classification:
        raise StageCFreeJudgeError(f"Manifest {path} execution classification is inconsistent")
    flags = _classification_flags(classification, recovery_number)
    for key, expected in flags.items():
        if data.get(key) is not expected:
            raise StageCFreeJudgeError(f"Manifest {path} flag {key} is inconsistent")
    replicate_passed = classification == "passed"
    if data.get("replicate_passed") is not replicate_passed:
        raise StageCFreeJudgeError(f"Manifest {path} replicate_passed is inconsistent")
    if data.get("successful_probe_count") != sum(
        probe.get("json_contract_success") is True for probe in probes
    ):
        raise StageCFreeJudgeError(f"Manifest {path} successful_probe_count is inconsistent")
    successful_count = sum(probe.get("json_contract_success") is True for probe in probes)
    if data.get("json_contract_passed") is not (successful_count == 6):
        raise StageCFreeJudgeError(f"Manifest {path} json_contract_passed is inconsistent")
    formal_timeout_compatible = all(
        probe.get("formal_timeout_compatible") is True for probe in probes
    )
    if data.get("formal_timeout_compatible") is not formal_timeout_compatible:
        raise StageCFreeJudgeError(f"Manifest {path} formal_timeout_compatible is inconsistent")
    timeout_occurrences = sum(
        probe.get("error_type") in {"timeout", "http_408"} for probe in probes
    )
    if data.get("timeout_occurrences") != timeout_occurrences:
        raise StageCFreeJudgeError(f"Manifest {path} timeout_occurrences is inconsistent")
    summaries = data.get("per_answerability_summary")
    if not isinstance(summaries, dict):
        raise StageCFreeJudgeError(f"Manifest {path} lacks per-answerability summaries")
    for answerability in ("supported", "partially_supported", "insufficient"):
        subset = [probe for probe in probes if probe.get("answerability") == answerability]
        successes = sum(probe.get("json_contract_success") is True for probe in subset)
        expected_summary = {
            "attempted": 2,
            "json_contract_successful": successes,
            "json_contract_passed": successes == 2,
            "formal_timeout_compatible": all(
                probe.get("formal_timeout_compatible") is True for probe in subset
            ),
            "timeouts": sum(
                probe.get("error_type") in {"timeout", "http_408"} for probe in subset
            ),
        }
        if summaries.get(answerability) != expected_summary:
            raise StageCFreeJudgeError(f"Manifest {path} {answerability} summary is inconsistent")
    expected_no_repair = {
        "coercion": False,
        "synonym_repair": False,
        "semantic_normalization": False,
        "post_hoc_value_repair": False,
    }
    if data.get("no_repair_declaration") != expected_no_repair:
        raise StageCFreeJudgeError(f"Manifest {path} no-repair declaration is inconsistent")
    started_at = _parse_utc(data.get("started_at"))
    completed_at = _parse_utc(data.get("completed_at"))
    if completed_at < started_at:
        raise StageCFreeJudgeError(f"Manifest {path} completion precedes start")
    return data


def validate_operational_unevaluability_amendment(path: Path) -> dict[str, Any]:
    if path.name != "amendment.json":
        raise StageCFreeJudgeError(f"Unexpected operational amendment filename: {path.name}")
    if _sha256(path) != OPERATIONAL_UNEVALUABILITY_AMENDMENT_SHA256:
        raise StageCFreeJudgeError("Operational-unevaluability amendment SHA256 mismatch")
    data = _read_json_object(path)
    expected = {
        "amendment_id": OPERATIONAL_UNEVALUABILITY_AMENDMENT_ID,
        "amendment_type": "operational_execution_policy_only",
        "scientific_protocol_identity": FREE_PROTOCOL_AMENDMENT_VERSION,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise StageCFreeJudgeError(f"Operational amendment field {key!r} mismatch")
    _parse_utc(data.get("effective_at"))
    source_policy = data.get("source_policy")
    if source_policy != {
        "policy_version": FREE_POLICY_VERSION,
        "relative_path": FREE_POLICY_JSON_RELATIVE_PATH,
        "sha256": FREE_POLICY_SHA256,
    }:
        raise StageCFreeJudgeError("Operational amendment source-policy anchor mismatch")
    terminal_state = data.get("terminal_operational_state")
    if not isinstance(terminal_state, dict) or terminal_state.get(
        "internal_name"
    ) != OPERATIONAL_UNEVALUABILITY_STATE or terminal_state.get(
        "scientific_label"
    ) != OPERATIONAL_UNEVALUABILITY_LABEL:
        raise StageCFreeJudgeError("Operational amendment terminal state mismatch")
    for forbidden_conclusion in (
        "candidate_readiness_failure",
        "semantic_failure",
        "selected_primary",
        "capability_conclusion_permitted",
    ):
        if terminal_state.get(forbidden_conclusion) is not False:
            raise StageCFreeJudgeError(
                f"Operational amendment improperly enables {forbidden_conclusion}"
            )
    applicability = data.get("applicability")
    if not isinstance(applicability, dict) or applicability.get("candidate_numbers") != [1, 2, 3, 4]:
        raise StageCFreeJudgeError("Operational amendment candidate applicability mismatch")
    if applicability.get("replicate_numbers") != [1, 2] or applicability.get(
        "applies_identically_to_all_candidates_and_required_replicates"
    ) is not True:
        raise StageCFreeJudgeError("Operational amendment replicate applicability mismatch")
    precedence = data.get("precedence")
    if not isinstance(precedence, dict) or precedence.get(
        "candidate_readiness_failure_is_absolute"
    ) is not True or precedence.get(
        "ambiguous_or_unclassified_failure_state"
    ) != "manual_review_unresolved":
        raise StageCFreeJudgeError("Operational amendment precedence mismatch")
    partial = data.get("partial_success")
    if not isinstance(partial, dict) or partial.get("zero_successful_probes_required") is not False:
        raise StageCFreeJudgeError("Operational amendment partial-success rule mismatch")
    if partial.get("cross_attempt_pooling_prohibited") is not True or partial.get(
        "partial_qualification_prohibited"
    ) is not True:
        raise StageCFreeJudgeError("Operational amendment pooling rule mismatch")
    advancement = data.get("advancement")
    if not isinstance(advancement, dict) or advancement.get(
        "next_frozen_candidate_becomes_eligible"
    ) is not True:
        raise StageCFreeJudgeError("Operational amendment advancement rule mismatch")
    for prohibited in (
        "candidate_order_override_prohibited",
        "manual_force_advance_prohibited",
        "environment_override_prohibited",
        "additional_recovery_prohibited",
    ):
        if advancement.get(prohibited) is not True:
            raise StageCFreeJudgeError(f"Operational amendment must preserve {prohibited}")
    anchors = data.get("candidate_01_historical_anchors")
    if anchors != {
        "ordinary_manifest_path": F1_ORDINARY_MANIFEST_RELATIVE_PATH,
        "ordinary_manifest_sha256": F1_ORDINARY_MANIFEST_SHA256,
        "recovery_manifest_path": F1_RECOVERY_MANIFEST_RELATIVE_PATH,
        "recovery_manifest_sha256": F1_RECOVERY_MANIFEST_SHA256,
    }:
        raise StageCFreeJudgeError("Operational amendment F1 historical anchors mismatch")
    return data


def _require_operational_unevaluability_pair(
    ordinary: dict[str, Any],
    recovery: dict[str, Any],
    *,
    candidate_number: int,
    replicate_number: int,
) -> None:
    for label, attempt, expected_recovery in (
        ("ordinary", ordinary, 0),
        ("recovery", recovery, 1),
    ):
        if attempt.get("candidate_number") != candidate_number:
            raise StageCFreeJudgeError(f"{label} attempt candidate mismatch")
        if attempt.get("replicate_number") != replicate_number:
            raise StageCFreeJudgeError(f"{label} attempt replicate mismatch")
        if attempt.get("recovery_number") != expected_recovery:
            raise StageCFreeJudgeError(f"{label} attempt recovery number mismatch")
        if attempt.get("execution_classification") != "infrastructure_incident":
            raise StageCFreeJudgeError(
                f"{label} attempt is not a solely infrastructure-classified incident"
            )
        if attempt.get("replicate_passed") is not False:
            raise StageCFreeJudgeError(f"{label} attempt independently passed 6/6")
        probes = attempt.get("probes")
        if not isinstance(probes, list) or len(probes) != R3_PREFLIGHT_PROBE_COUNT:
            raise StageCFreeJudgeError(f"{label} attempt does not contain all six probes")
        for probe in probes:
            if probe.get("json_contract_success") is True:
                if probe.get("failure_class") is not None:
                    raise StageCFreeJudgeError(
                        f"{label} attempt has a successful probe with a failure class"
                    )
            elif probe.get("failure_class") != "infrastructure_incident":
                raise StageCFreeJudgeError(
                    f"{label} attempt contains a readiness, ambiguous, or unclassified failure"
                )
    frozen_fields = (
        "policy_version",
        "protocol_amendment_version",
        "source_policy_sha256",
        "candidate_number",
        "candidate_slug",
        "requested_model_id",
        "provider",
        "response_format",
        "temperature",
        "max_tokens",
        "timeout_seconds",
        "thinking_toggle",
        "enable_thinking_sent",
        "probe_plan_version",
        "probe_count",
        "canonical_formal_judge_output_schema_sha256",
        "judge_system_prompt_sha256",
        "no_repair_declaration",
    )
    for field in frozen_fields:
        if ordinary.get(field) != recovery.get(field):
            raise StageCFreeJudgeError(
                f"Recovery does not preserve ordinary execution field {field!r}"
            )


def validate_operational_unevaluability_adjudication(
    path: Path,
    *,
    manifests_dir: Path,
    amendment: dict[str, Any],
) -> dict[str, Any]:
    match = _OPERATIONAL_UNEVALUABILITY_PATTERN.fullmatch(path.name)
    if not match:
        raise StageCFreeJudgeError(f"Unexpected operational adjudication filename: {path.name}")
    data = _read_json_object(path)
    candidate_number = int(match.group("candidate"))
    candidate = get_free_candidate(candidate_number)
    replicate_number = data.get("affected_replicate")
    if replicate_number not in {1, 2}:
        raise StageCFreeJudgeError(f"Operational adjudication {path} has invalid replicate")
    next_candidate = candidate_number + 1 if candidate_number < len(FREE_CANDIDATES) else None
    expected = {
        "adjudication_id": (
            f"{OPERATIONAL_UNEVALUABILITY_AMENDMENT_ID}-candidate-{candidate_number:02d}"
        ),
        "amendment_id": OPERATIONAL_UNEVALUABILITY_AMENDMENT_ID,
        "amendment_sha256": OPERATIONAL_UNEVALUABILITY_AMENDMENT_SHA256,
        "source_policy_version": FREE_POLICY_VERSION,
        "source_policy_sha256": FREE_POLICY_SHA256,
        "scientific_protocol_identity": FREE_PROTOCOL_AMENDMENT_VERSION,
        "candidate_number": candidate_number,
        "candidate_model_id": candidate.model_id,
        "adjudication_state": OPERATIONAL_UNEVALUABILITY_LABEL,
        "internal_state": OPERATIONAL_UNEVALUABILITY_STATE,
        "candidate_readiness_failure": False,
        "semantic_failure": False,
        "selected_primary": False,
        "semantic_or_capability_conclusion": False,
        "cross_attempt_pooling": False,
        "partial_qualification": False,
        "additional_recovery_authorized": False,
        "next_frozen_candidate_number": next_candidate,
        "advancement_authorized": True,
        "formal_stage_c_eligibility": False,
        "data_excluded_from_formal_analysis": True,
        "formal_stage_c_outcome_used": False,
        "raw_provider_text_stored": False,
    }
    expected_keys = set(expected) | {
        "adjudicated_at",
        "affected_replicate",
        "ordinary_manifest",
        "recovery_manifest",
    }
    if set(data) != expected_keys:
        raise StageCFreeJudgeError(
            f"Operational adjudication {path} has missing or unexpected fields"
        )
    for key, value in expected.items():
        if data.get(key) != value:
            raise StageCFreeJudgeError(
                f"Operational adjudication {path} field {key!r} mismatch"
            )
    adjudicated_at = _parse_utc(data.get("adjudicated_at"))
    if adjudicated_at < _parse_utc(amendment.get("effective_at")):
        raise StageCFreeJudgeError("Operational adjudication predates its amendment")

    ordinary_ref = data.get("ordinary_manifest")
    recovery_ref = data.get("recovery_manifest")
    if not isinstance(ordinary_ref, dict) or not isinstance(recovery_ref, dict):
        raise StageCFreeJudgeError("Operational adjudication lacks manifest anchors")
    ordinary_name = free_manifest_name(candidate_number, replicate_number, 0)
    recovery_name = free_manifest_name(candidate_number, replicate_number, 1)
    expected_ordinary_path = f"{FREE_MANIFESTS_RELATIVE_DIR}/{ordinary_name}"
    expected_recovery_path = f"{FREE_MANIFESTS_RELATIVE_DIR}/{recovery_name}"
    ordinary_path = manifests_dir / ordinary_name
    recovery_path = manifests_dir / recovery_name
    ordinary_sha = _verify_hash(
        manifests_dir,
        ordinary_name,
        ordinary_ref.get("sha256"),
        "Operational adjudication ordinary attempt",
    )
    recovery_sha = _verify_hash(
        manifests_dir,
        recovery_name,
        recovery_ref.get("sha256"),
        "Operational adjudication recovery attempt",
    )
    if not re.fullmatch(r"[0-9a-f]{64}", ordinary_sha) or not re.fullmatch(
        r"[0-9a-f]{64}", recovery_sha
    ):
        raise StageCFreeJudgeError("Operational adjudication manifest SHA is invalid")
    if ordinary_ref != {"path": expected_ordinary_path, "sha256": ordinary_sha}:
        raise StageCFreeJudgeError("Operational adjudication ordinary anchor mismatch")
    if recovery_ref != {"path": expected_recovery_path, "sha256": recovery_sha}:
        raise StageCFreeJudgeError("Operational adjudication recovery anchor mismatch")
    ordinary = validate_free_attempt_manifest(ordinary_path)
    recovery = validate_free_attempt_manifest(recovery_path)
    _require_operational_unevaluability_pair(
        ordinary,
        recovery,
        candidate_number=candidate_number,
        replicate_number=replicate_number,
    )
    if replicate_number == 2:
        rep1_ordinary_path = manifests_dir / free_manifest_name(candidate_number, 1, 0)
        if not rep1_ordinary_path.is_file():
            raise StageCFreeJudgeError("Replicate-2 adjudication lacks Replicate 1")
        rep1_ordinary = validate_free_attempt_manifest(rep1_ordinary_path)
        if rep1_ordinary["execution_classification"] == "passed":
            rep1_passed = True
        elif rep1_ordinary["execution_classification"] == "infrastructure_incident":
            rep1_recovery_path = manifests_dir / free_manifest_name(candidate_number, 1, 1)
            if not rep1_recovery_path.is_file():
                raise StageCFreeJudgeError("Replicate-2 adjudication lacks effective Replicate 1")
            rep1_recovery = validate_free_attempt_manifest(rep1_recovery_path)
            rep1_passed = rep1_recovery["execution_classification"] == "passed"
        else:
            rep1_passed = False
        if not rep1_passed:
            raise StageCFreeJudgeError(
                "Replicate-2 operational adjudication requires a passing effective Replicate 1"
            )
    return data


def inspect_operational_unevaluability_amendment(
    amendment_dir: Path | None,
    *,
    manifests_dir: Path,
) -> dict[str, Any]:
    if amendment_dir is None or not amendment_dir.exists():
        return {"present": False, "amendment": None, "adjudications": {}}
    if not amendment_dir.is_dir():
        raise StageCFreeJudgeError("Operational amendment path is not a directory")
    amendment_path = amendment_dir / "amendment.json"
    documentation_path = amendment_dir / "AMENDMENT.md"
    adjudications_dir = amendment_dir / "adjudications"
    if not amendment_path.is_file() or not documentation_path.is_file() or not adjudications_dir.is_dir():
        raise StageCFreeJudgeError("Operational amendment package is incomplete")
    allowed = {"amendment.json", "AMENDMENT.md", "adjudications"}
    unexpected = {entry.name for entry in amendment_dir.iterdir()} - allowed
    if unexpected:
        raise StageCFreeJudgeError(
            f"Unexpected operational amendment entries: {sorted(unexpected)}"
        )
    amendment = validate_operational_unevaluability_amendment(amendment_path)
    adjudications: dict[int, dict[str, Any]] = {}
    for path in sorted(adjudications_dir.iterdir()):
        if not path.is_file() or path.suffix != ".json":
            raise StageCFreeJudgeError(
                f"Unexpected operational adjudication entry: {path.name}"
            )
        adjudication = validate_operational_unevaluability_adjudication(
            path,
            manifests_dir=manifests_dir,
            amendment=amendment,
        )
        candidate_number = adjudication["candidate_number"]
        if candidate_number in adjudications:
            raise StageCFreeJudgeError(
                f"Duplicate operational adjudication for candidate {candidate_number:02d}"
            )
        adjudications[candidate_number] = adjudication
    return {"present": True, "amendment": amendment, "adjudications": adjudications}


def create_operational_unevaluability_adjudication(
    repository_root: Path,
    *,
    candidate_number: int,
    replicate_number: int,
    manifests_dir: Path | None = None,
    amendment_dir: Path | None = None,
    adjudicated_at: datetime | None = None,
) -> dict[str, Any]:
    candidate = get_free_candidate(candidate_number)
    if replicate_number not in {1, 2}:
        raise StageCFreeJudgeError("Operational adjudication requires replicate 1 or 2")
    resolved_manifests = manifests_dir or get_free_manifests_dir(repository_root)
    resolved_amendment = amendment_dir or get_operational_unevaluability_amendment_dir(
        repository_root
    )
    verify_free_policy_and_history(repository_root)
    package = inspect_operational_unevaluability_amendment(
        resolved_amendment,
        manifests_dir=resolved_manifests,
    )
    if not package["present"]:
        raise StageCFreeJudgeError("Operational amendment is not present and valid")
    if candidate_number in package["adjudications"]:
        raise FileExistsError(
            f"Operational adjudication already exists for candidate {candidate_number:02d}"
        )
    ordinary_name = free_manifest_name(candidate_number, replicate_number, 0)
    recovery_name = free_manifest_name(candidate_number, replicate_number, 1)
    ordinary_path = resolved_manifests / ordinary_name
    recovery_path = resolved_manifests / recovery_name
    ordinary = validate_free_attempt_manifest(ordinary_path)
    recovery = validate_free_attempt_manifest(recovery_path)
    _require_operational_unevaluability_pair(
        ordinary,
        recovery,
        candidate_number=candidate_number,
        replicate_number=replicate_number,
    )
    if replicate_number == 2:
        existing_state = inspect_free_policy_manifests(
            resolved_manifests,
            amendment_dir=resolved_amendment,
        )
        if _effective_replicate(existing_state, candidate_number, 1)["status"] != "passed":
            raise StageCFreeJudgeError(
                "Replicate-2 operational adjudication requires a passing effective Replicate 1"
            )
    timestamp = adjudicated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise StageCFreeJudgeError("Operational adjudication timestamp must be timezone-aware")
    next_candidate = candidate_number + 1 if candidate_number < len(FREE_CANDIDATES) else None
    adjudication = {
        "adjudication_id": (
            f"{OPERATIONAL_UNEVALUABILITY_AMENDMENT_ID}-candidate-{candidate_number:02d}"
        ),
        "amendment_id": OPERATIONAL_UNEVALUABILITY_AMENDMENT_ID,
        "amendment_sha256": OPERATIONAL_UNEVALUABILITY_AMENDMENT_SHA256,
        "source_policy_version": FREE_POLICY_VERSION,
        "source_policy_sha256": FREE_POLICY_SHA256,
        "scientific_protocol_identity": FREE_PROTOCOL_AMENDMENT_VERSION,
        "adjudicated_at": timestamp.astimezone(timezone.utc).isoformat(),
        "candidate_number": candidate_number,
        "candidate_model_id": candidate.model_id,
        "affected_replicate": replicate_number,
        "adjudication_state": OPERATIONAL_UNEVALUABILITY_LABEL,
        "internal_state": OPERATIONAL_UNEVALUABILITY_STATE,
        "ordinary_manifest": {
            "path": f"{FREE_MANIFESTS_RELATIVE_DIR}/{ordinary_name}",
            "sha256": _sha256(ordinary_path),
        },
        "recovery_manifest": {
            "path": f"{FREE_MANIFESTS_RELATIVE_DIR}/{recovery_name}",
            "sha256": _sha256(recovery_path),
        },
        "candidate_readiness_failure": False,
        "semantic_failure": False,
        "selected_primary": False,
        "semantic_or_capability_conclusion": False,
        "cross_attempt_pooling": False,
        "partial_qualification": False,
        "additional_recovery_authorized": False,
        "next_frozen_candidate_number": next_candidate,
        "advancement_authorized": True,
        "formal_stage_c_eligibility": False,
        "data_excluded_from_formal_analysis": True,
        "formal_stage_c_outcome_used": False,
        "raw_provider_text_stored": False,
    }
    target = resolved_amendment / "adjudications" / operational_unevaluability_adjudication_name(
        candidate_number
    )
    _atomic_new_json(target, adjudication)
    return validate_operational_unevaluability_adjudication(
        target,
        manifests_dir=resolved_manifests,
        amendment=package["amendment"],
    )


def validate_zero_cost_ineligibility(path: Path) -> dict[str, Any]:
    match = _INELIGIBILITY_PATTERN.fullmatch(path.name)
    if not match:
        raise StageCFreeJudgeError(f"Unexpected zero-cost ineligibility filename: {path.name}")
    data = _read_json_object(path)
    candidate_number = int(match.group("candidate"))
    candidate = get_free_candidate(candidate_number)
    expected = {
        "policy_version": FREE_POLICY_VERSION,
        "protocol_amendment_version": FREE_PROTOCOL_AMENDMENT_VERSION,
        "source_policy_sha256": FREE_POLICY_SHA256,
        "candidate_number": candidate_number,
        "candidate_slug": candidate.slug,
        "model_id": candidate.model_id,
        "status": "operationally_ineligible_nonzero_cost",
        "provider_calls_made": 0,
        "candidate_quality_interpretation": False,
        "advancement_authorized": True,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise StageCFreeJudgeError(f"Zero-cost note {path} field {key} mismatch")
    source_hashes = data.get("source_historical_and_scientific_hashes")
    if not isinstance(source_hashes, dict):
        raise StageCFreeJudgeError(f"Zero-cost note {path} lacks source hashes")
    for key, value in EXPECTED_SOURCE_HASHES.items():
        if source_hashes.get(key) != value:
            raise StageCFreeJudgeError(f"Zero-cost note {path} source hash mismatch for {key}")
    _parse_utc(data.get("verified_at"))
    return data


def inspect_free_policy_manifests(
    manifests_dir: Path,
    *,
    amendment_dir: Path | None = None,
) -> dict[str, Any]:
    attempts: dict[int, dict[int, dict[int, dict[str, Any]]]] = {
        candidate.candidate_number: {1: {}, 2: {}} for candidate in FREE_CANDIDATES
    }
    ineligible: dict[int, dict[str, Any]] = {}
    if manifests_dir.is_dir():
        for path in sorted(manifests_dir.iterdir()):
            if path.name == ".gitkeep":
                continue
            if not path.is_file() or path.suffix != ".json":
                raise StageCFreeJudgeError(f"Unexpected entry in canonical manifests directory: {path.name}")
            attempt_match = _ATTEMPT_PATTERN.fullmatch(path.name)
            ineligible_match = _INELIGIBILITY_PATTERN.fullmatch(path.name)
            if attempt_match:
                data = validate_free_attempt_manifest(path)
                candidate_number = data["candidate_number"]
                replicate_number = data["replicate_number"]
                recovery_number = data["recovery_number"]
                slot = attempts[candidate_number][replicate_number]
                if recovery_number in slot:
                    raise StageCFreeJudgeError(f"Duplicate attempt manifest for {path.name}")
                slot[recovery_number] = data
            elif ineligible_match:
                data = validate_zero_cost_ineligibility(path)
                candidate_number = data["candidate_number"]
                if candidate_number in ineligible:
                    raise StageCFreeJudgeError(f"Duplicate zero-cost ineligibility for candidate {candidate_number}")
                ineligible[candidate_number] = data
            else:
                raise StageCFreeJudgeError(f"Unexpected manifest filename: {path.name}")
    for candidate_number, note in ineligible.items():
        del note
        if any(attempts[candidate_number][replicate] for replicate in (1, 2)):
            raise StageCFreeJudgeError(
                f"Candidate {candidate_number:02d} has both a zero-cost ineligibility note and an execution attempt"
            )
    for candidate_number in attempts:
        for replicate_number in (1, 2):
            slot = attempts[candidate_number][replicate_number]
            if 1 in slot and 0 not in slot:
                raise StageCFreeJudgeError(
                    f"Candidate {candidate_number:02d} replicate {replicate_number:02d} has recovery without ordinary attempt"
                )
    resolved_amendment_dir = (
        amendment_dir
        if amendment_dir is not None
        else _default_operational_amendment_dir(manifests_dir)
    )
    operational = inspect_operational_unevaluability_amendment(
        resolved_amendment_dir,
        manifests_dir=manifests_dir,
    )
    for candidate_number in operational["adjudications"]:
        if candidate_number in ineligible:
            raise StageCFreeJudgeError(
                f"Candidate {candidate_number:02d} has both zero-cost ineligibility and operational unevaluability"
            )
    return {
        "attempts": attempts,
        "zero_cost_ineligible": ineligible,
        "operational_amendment": operational,
        "operationally_unevaluable": operational["adjudications"],
    }


def _effective_replicate(state: dict[str, Any], candidate_number: int, replicate_number: int) -> dict[str, Any]:
    attempts = state["attempts"][candidate_number][replicate_number]
    ordinary = attempts.get(0)
    if ordinary is None:
        return {"status": "missing", "manifest": None}
    classification = ordinary["execution_classification"]
    if classification == "passed":
        return {"status": "passed", "manifest": ordinary}
    if classification == "candidate_readiness_failure":
        return {"status": "terminal_candidate_failure", "manifest": ordinary}
    if classification == "ambiguous_technical_failure":
        return {"status": "manual_review", "manifest": ordinary}
    recovery = attempts.get(1)
    if recovery is None:
        return {"status": "pending_recovery", "manifest": ordinary}
    recovery_classification = recovery["execution_classification"]
    if recovery_classification == "passed":
        return {"status": "passed", "manifest": recovery}
    if recovery_classification == "candidate_readiness_failure":
        return {"status": "terminal_candidate_failure", "manifest": recovery}
    return {"status": "manual_review", "manifest": recovery}


def _candidate_state(state: dict[str, Any], candidate_number: int) -> str:
    if candidate_number in state["zero_cost_ineligible"]:
        return "terminal_operational_ineligibility"
    rep1 = _effective_replicate(state, candidate_number, 1)
    if rep1["status"] == "terminal_candidate_failure":
        return "terminal_candidate_failure"
    rep2 = _effective_replicate(state, candidate_number, 2)
    if rep2["status"] == "terminal_candidate_failure":
        return "terminal_candidate_failure"
    if candidate_number in state["operationally_unevaluable"]:
        return OPERATIONAL_UNEVALUABILITY_STATE
    if rep1["status"] in {"pending_recovery", "manual_review", "missing"}:
        return rep1["status"]
    if rep2["status"] == "passed":
        return "selected_primary"
    return rep2["status"]


def evaluate_free_runner_eligibility(
    manifests_dir: Path,
    candidate_number: int,
    replicate_number: int,
    recovery_number: int = 0,
    *,
    current_time: datetime | None = None,
    amendment_dir: Path | None = None,
) -> tuple[bool, str, float | None]:
    candidate = get_free_candidate(candidate_number)
    if replicate_number not in {1, 2}:
        return False, "Only replicate numbers 1 and 2 are permitted", None
    if recovery_number not in {0, 1}:
        return False, "Only recovery number 1 is permitted", None
    state = inspect_free_policy_manifests(manifests_dir, amendment_dir=amendment_dir)
    now = current_time or datetime.now(timezone.utc)

    for prior in FREE_CANDIDATES:
        prior_status = _candidate_state(state, prior.candidate_number)
        if prior_status == "selected_primary":
            return False, f"Candidate {prior.candidate_number:02d} is already selected as Primary Judge", None
        if prior.candidate_number >= candidate_number:
            break
        if prior_status not in {
            "terminal_candidate_failure",
            "terminal_operational_ineligibility",
            OPERATIONAL_UNEVALUABILITY_STATE,
        }:
            return False, (
                f"Candidate {candidate_number:02d} is blocked because prior candidate "
                f"{prior.candidate_number:02d} is {prior_status}"
            ), None

    if candidate_number in state["zero_cost_ineligible"]:
        return False, f"Candidate {candidate_number:02d} is operationally ineligible under zero-cost policy", None
    if candidate_number in state["operationally_unevaluable"]:
        return False, (
            f"Candidate {candidate_number:02d} is {OPERATIONAL_UNEVALUABILITY_LABEL}; "
            "additional execution is prohibited"
        ), None
    attempts = state["attempts"][candidate_number][replicate_number]
    if recovery_number == 1:
        ordinary = attempts.get(0)
        if ordinary is None:
            return False, "Recovery is blocked because the ordinary replicate does not exist", None
        if ordinary["execution_classification"] != "infrastructure_incident":
            return False, "Recovery is authorized only after a qualifying infrastructure incident", None
        if 1 in attempts:
            return False, "Recovery 01 already exists; additional recovery is prohibited", None
        return True, f"Candidate {candidate_number:02d} replicate {replicate_number:02d} recovery 01 is eligible", None

    if 0 in attempts:
        return False, "Ordinary replicate already exists; overwrite or third ordinary replicate is prohibited", None
    if 1 in attempts:
        return False, "Recovery exists without ordinary attempt; state is invalid", None
    if replicate_number == 1:
        return True, f"Candidate {candidate_number:02d} replicate 01 is eligible", None

    effective_rep1 = _effective_replicate(state, candidate_number, 1)
    if effective_rep1["status"] != "passed":
        return False, f"Replicate 02 is blocked because effective replicate 01 is {effective_rep1['status']}", None
    completed_at = _parse_utc(effective_rep1["manifest"]["completed_at"])
    elapsed = (now - completed_at).total_seconds()
    if elapsed < FREE_MINIMUM_SPACING_SECONDS:
        return False, (
            f"Replicate 02 spacing is {elapsed:.1f}s; at least {FREE_MINIMUM_SPACING_SECONDS:.0f}s is required"
        ), elapsed
    return True, f"Candidate {candidate_number:02d} replicate 02 is eligible", elapsed


def _validate_output_target(repository_root: Path, target: Path, manifests_dir: Path) -> Path:
    resolved = target.resolve()
    formal_runs = (repository_root / "research/experiments/western_formal_v0_1/runs").resolve()
    if resolved == formal_runs or formal_runs in resolved.parents:
        raise StageCFreeJudgeError("Free-policy output must never enter the formal Stage C runs directory")
    if resolved.parent != manifests_dir.resolve():
        raise StageCFreeJudgeError("Free-policy output must use the canonical manifest directory")
    if resolved.exists() or resolved.with_suffix(resolved.suffix + ".tmp").exists():
        raise FileExistsError(f"Free-policy manifest already exists at {resolved}; overwrite prohibited")
    return resolved


def _validate_free_provider(provider: Any, candidate: FreeJudgeCandidate) -> None:
    checks = {
        "provider": (getattr(provider, "name", None), FREE_PROVIDER),
        "model": (getattr(provider, "model", None), candidate.model_id),
        "timeout": (float(getattr(provider, "timeout", -1)), FREE_TIMEOUT_SECONDS),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise StageCFreeJudgeError(f"Free-policy provider {label} mismatch: expected {expected!r}, got {actual!r}")
    if int(getattr(provider, "max_tokens", -1)) < FREE_MAX_TOKENS:
        raise StageCFreeJudgeError("Free-policy provider max_tokens is below 1200")
    if getattr(provider, "supports_response_format", False) is not True:
        raise StageCFreeJudgeError("Provider does not advertise response_format support")
    if getattr(provider, "supports_json_object_response_format", False) is not True:
        raise StageCFreeJudgeError("Provider does not advertise JSON-object response_format support")
    actual_thinking = getattr(provider, "enable_thinking", None)
    if actual_thinking is not candidate.expected_provider_enable_thinking:
        raise StageCFreeJudgeError(
            f"Candidate thinking-toggle contract mismatch: expected {candidate.expected_provider_enable_thinking!r}, got {actual_thinking!r}"
        )


def _resolve_manifests_dir(repository_root: Path, test_manifests_dir: Path | None) -> Path:
    manifests_dir = test_manifests_dir or get_free_manifests_dir(repository_root)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    return manifests_dir


def record_zero_cost_ineligibility(
    repository_root: Path,
    *,
    candidate_number: int,
    verified_at: datetime | None = None,
    test_manifests_dir: Path | None = None,
) -> dict[str, Any]:
    source_hashes = verify_free_policy_and_history(repository_root)
    manifests_dir = _resolve_manifests_dir(repository_root, test_manifests_dir)
    eligible, reason, _ = evaluate_free_runner_eligibility(
        manifests_dir, candidate_number, 1, current_time=verified_at
    )
    if not eligible:
        raise StageCFreeJudgeError(f"Cannot record zero-cost ineligibility: {reason}")
    candidate = get_free_candidate(candidate_number)
    target = _validate_output_target(
        repository_root,
        manifests_dir / zero_cost_ineligibility_name(candidate_number),
        manifests_dir,
    )
    timestamp = (verified_at or datetime.now(timezone.utc)).isoformat()
    note = {
        "policy_version": FREE_POLICY_VERSION,
        "protocol_amendment_version": FREE_PROTOCOL_AMENDMENT_VERSION,
        "source_policy_sha256": FREE_POLICY_SHA256,
        "candidate_number": candidate_number,
        "candidate_slug": candidate.slug,
        "model_id": candidate.model_id,
        "status": "operationally_ineligible_nonzero_cost",
        "verified_at": timestamp,
        "provider_calls_made": 0,
        "candidate_quality_interpretation": False,
        "advancement_authorized": True,
        "reason": "operator_verified_candidate_no_longer_has_zero_input_and_output_price_before_first_call",
        "source_historical_and_scientific_hashes": source_hashes,
    }
    _atomic_new_json(target, note)
    return note


async def run_free_judge_preflight(
    repository_root: Path,
    *,
    candidate_number: int,
    replicate_number: int,
    recovery_number: int = 0,
    zero_cost_confirmed: bool,
    provider: Any | None = None,
    test_manifests_dir: Path | None = None,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    if zero_cost_confirmed is not True:
        raise StageCFreeJudgeError("Live execution requires an immediate manual zero-cost confirmation")
    candidate = get_free_candidate(candidate_number)
    source_hashes = verify_free_policy_and_history(repository_root)
    manifests_dir = _resolve_manifests_dir(repository_root, test_manifests_dir)
    eligible, reason, elapsed_spacing = evaluate_free_runner_eligibility(
        manifests_dir,
        candidate_number,
        replicate_number,
        recovery_number,
        current_time=current_time,
    )
    if not eligible:
        raise StageCFreeJudgeError(f"Free-policy preflight rejected by state machine: {reason}")
    target = _validate_output_target(
        repository_root,
        manifests_dir / free_manifest_name(candidate_number, replicate_number, recovery_number),
        manifests_dir,
    )

    active = provider or build_llm_provider(candidate.model_id, timeout_override=FREE_TIMEOUT_SECONDS)
    _validate_free_provider(active, candidate)
    probe_plan = get_synthetic_probe_plan()
    if [probe["probe_id"] for probe in probe_plan] != [
        "synthetic-supported-probe-01",
        "synthetic-supported-probe-02",
        "synthetic-partially-supported-probe-01",
        "synthetic-partially-supported-probe-02",
        "synthetic-insufficient-probe-01",
        "synthetic-insufficient-probe-02",
    ]:
        raise StageCFreeJudgeError("Frozen six-probe plan changed")

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
        failure_class: FailureClass | None = None
        normalization: str | None = None
        json_contract_success = False
        http_status: int | None = None
        try:
            result = await active.generate(
                system=JUDGE_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=FREE_TEMPERATURE,
                max_tokens=FREE_MAX_TOKENS,
                response_format=copy.deepcopy(FREE_TRANSPORT),
            )
            reported_model = getattr(result, "model", None)
            if reported_model != candidate.model_id:
                failure_class = "candidate_readiness_failure"
                error_type = "model_identity_mismatch"
                error_message = (
                    f"Provider-reported model mismatch: expected {candidate.model_id!r}, got {reported_model!r}"
                )
            elif getattr(result, "finish_reason", None) not in {None, "stop"}:
                failure_class = "candidate_readiness_failure"
                error_type = "unsupported_finish_reason"
                error_message = f"Unsupported finish_reason={getattr(result, 'finish_reason', None)!r}"
            else:
                _, normalization = validate_stage_c_r3_json_mode_probe_output(
                    result.text,
                    retrieval=retrieval,
                    expected_insufficiency_label=spec.get("expected_insufficiency_label"),
                    require_all_enums_exercised=spec.get("require_all_enums_exercised", False),
                )
                json_contract_success = True
        except ProviderUnavailable as exc:
            failure_class, error_type = classify_provider_exception(exc)
            error_message = str(exc)
            http_status = getattr(exc, "http_status", None)
        except (StageCR3PreflightError, json.JSONDecodeError) as exc:
            failure_class = "candidate_readiness_failure"
            error_type = "schema_or_contract_failure"
            error_message = str(exc)
        except TypeError as exc:
            failure_class = "candidate_readiness_failure"
            error_type = "required_parameter_rejected"
            error_message = str(exc)

        latency_ms = round((perf_counter() - started) * 1000, 3)
        if result is not None and latency_ms > FREE_TIMEOUT_SECONDS * 1000:
            failure_class = "candidate_readiness_failure"
            error_type = "completed_response_exceeds_timeout"
            error_message = f"Completed response latency {latency_ms}ms exceeds 120000ms"
        formal_timeout_compatible = result is not None and latency_ms <= 120000.0
        response_sha = (
            hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            if result is not None and isinstance(getattr(result, "text", None), str)
            else None
        )
        probes.append({
            "probe_number": spec["probe_number"],
            "probe_id": spec["probe_id"],
            "answerability": spec["answerability"],
            "expected_evidence_point_count": len(retrieval["expected_evidence_points"]),
            "expected_insufficiency_label": spec.get("expected_insufficiency_label"),
            "provider_call_success": result is not None,
            "provider_reported_model": getattr(result, "model", None),
            "finish_reason": getattr(result, "finish_reason", None),
            "json_contract_success": json_contract_success and failure_class is None,
            "formal_timeout_compatible": formal_timeout_compatible,
            "failure_class": failure_class,
            "error_type": error_type,
            "http_status": http_status,
            "error_message": error_message,
            "normalization": normalization,
            "latency_ms": latency_ms,
            "response_sha256": response_sha,
            "raw_response_stored": False,
            "synthetic_non_formal": True,
        })

    completed_at = _utc_now()
    classification = _attempt_classification(probes)
    flags = _classification_flags(classification, recovery_number)
    replicate_passed = classification == "passed"
    successful_count = sum(probe["json_contract_success"] is True for probe in probes)
    per_answerability: dict[str, dict[str, Any]] = {}
    for answerability in ("supported", "partially_supported", "insufficient"):
        subset = [probe for probe in probes if probe["answerability"] == answerability]
        successes = sum(probe["json_contract_success"] is True for probe in subset)
        per_answerability[answerability] = {
            "attempted": len(subset),
            "json_contract_successful": successes,
            "json_contract_passed": len(subset) == 2 and successes == 2,
            "formal_timeout_compatible": all(
                probe["formal_timeout_compatible"] is True for probe in subset
            ),
            "timeouts": sum(probe["error_type"] in {"timeout", "http_408"} for probe in subset),
        }
    latencies = [float(probe["latency_ms"]) for probe in probes]
    timeout_occurrences = sum(
        probe["error_type"] in {"timeout", "http_408"} for probe in probes
    )
    formal_timeout_compatible = all(
        probe["formal_timeout_compatible"] is True for probe in probes
    )

    if replicate_passed and replicate_number == 2:
        qualification_status = "qualified_and_selected_primary_judge"
    elif replicate_passed:
        qualification_status = "effective_replicate_01_passed_pending_replicate_02"
    elif flags["candidate_terminally_failed"]:
        qualification_status = f"terminally_failed_on_replicate_{replicate_number:02d}"
    elif flags["infrastructure_recovery_authorized"]:
        qualification_status = "candidate_unresolved_recovery_01_authorized"
    else:
        qualification_status = "candidate_unresolved_manual_methodology_review_required"

    manifest = {
        "policy_version": FREE_POLICY_VERSION,
        "protocol_amendment_version": FREE_PROTOCOL_AMENDMENT_VERSION,
        "source_policy_sha256": FREE_POLICY_SHA256,
        "candidate_number": candidate.candidate_number,
        "candidate_slug": candidate.slug,
        "requested_model_id": candidate.model_id,
        "replicate_number": replicate_number,
        "recovery_number": recovery_number,
        "attempt_kind": "infrastructure_recovery" if recovery_number else "ordinary_replicate",
        "attempt_id": free_attempt_id(candidate_number, replicate_number, recovery_number),
        "status": "passed" if replicate_passed else "failed",
        "execution_classification": classification,
        "replicate_passed": replicate_passed,
        "candidate_qualification_status": qualification_status,
        **flags,
        "started_at": started_at,
        "completed_at": completed_at,
        "replicate_spacing_seconds": elapsed_spacing,
        "zero_cost_confirmation": {
            "confirmed": True,
            "confirmed_at": started_at,
            "candidate_model_id": candidate.model_id,
            "meaning": "operator_manually_verified_zero_input_and_output_price_immediately_before_execution",
            "permanent_price_guarantee": False,
        },
        "provider": FREE_PROVIDER,
        "response_format": copy.deepcopy(FREE_TRANSPORT),
        "temperature": FREE_TEMPERATURE,
        "max_tokens": FREE_MAX_TOKENS,
        "timeout_seconds": FREE_TIMEOUT_SECONDS,
        "thinking_toggle": candidate.thinking_toggle,
        "enable_thinking_sent": candidate.expected_provider_enable_thinking,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "successful_probe_count": successful_count,
        "json_contract_passed": successful_count == 6,
        "formal_timeout_compatible": formal_timeout_compatible,
        "timeout_occurrences": timeout_occurrences,
        "per_answerability_summary": per_answerability,
        "latency_metrics": {
            "mean_latency_ms": statistics.fmean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "max_latency_ms": max(latencies),
        },
        "source_historical_and_scientific_hashes": source_hashes,
        "judge_system_prompt_sha256": hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
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
            "synonym_repair": False,
            "semantic_normalization": False,
            "post_hoc_value_repair": False,
        },
        "raw_response_stored": False,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "probes": probes,
    }
    _atomic_new_json(target, manifest)
    return manifest
