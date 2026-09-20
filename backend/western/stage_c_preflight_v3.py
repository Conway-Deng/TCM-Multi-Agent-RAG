from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import statistics
from time import perf_counter
from typing import Any

from providers import build_llm_provider
from providers.openai_compatible import ProviderUnavailable

from .formal_eval import (
    JUDGE_MAX_TOKENS,
    JUDGE_MODEL,
    JUDGE_PROVIDER,
    JUDGE_TEMPERATURE,
    JUDGE_TIMEOUT_SECONDS,
    PROTOCOL_VERSION,
    STAGE_C_RUN_ID,
    StageCDirectory,
    _atomic_new_json,
    _error_type,
    _sha256,
    _utc_now,
    _verify_stage_c_r2_incident_artifacts,
)
from .formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT, build_judge_prompt, normalize_judge_json_envelope
from .stage_c_preflight import (
    ALWAYS_BOOLEAN_FIELDS,
    R3_PREFLIGHT_CAPABILITY_SOURCE,
    R3_PREFLIGHT_PROBE_COUNT,
    R3_PREFLIGHT_PROBE_PLAN_VERSION,
    R3_PREFLIGHT_TIMEOUT_SECONDS,
    R3_PREFLIGHT_V1_READINESS_PATH,
    R3_PREFLIGHT_V1_READINESS_SHA256,
    SCOPE_FIELDS,
    StageCR3PreflightError,
    get_synthetic_probe_plan,
    stage_c_r3_response_format,
    validate_stage_c_r3_probe_output,
)


R3_JSON_MODE_PREFLIGHT_VERSION = "western-stage-c-r3-json-mode-preflight-v3"
R3_JSON_MODE_RESPONSE_FORMAT = {"type": "json_object"}
R3_PREFLIGHT_V2_READINESS_PATH = (
    "research/experiments/western_formal_v0_1/stage_c_r3_preflight_readiness_v2.json"
)
R3_PREFLIGHT_V2_READINESS_SHA256 = (
    "1a70f189b52cb9f539807b0f8fa172be6a47ced21d384bcca7db0b81a514df94"
)
R3_MODEL_PROVIDER_STATUS = "deprecated"


def stage_c_r3_json_mode_case_schema(
    *,
    answerability: str,
    expected_evidence_point_count: int,
) -> dict[str, Any]:
    """Derive the prospective prompt schema without changing the canonical model schema.

    The already-frozen v2 specialization is reused as the source of the
    answerability-specific scientific constraints. Exact evidence-point order
    is then made explicit for JSON Mode, where the provider does not enforce a
    JSON Schema response format.
    """
    response_format = stage_c_r3_response_format(
        answerability=answerability,
        expected_evidence_point_count=expected_evidence_point_count,
    )
    schema = copy.deepcopy(response_format["json_schema"]["schema"])
    evidence_schema = schema["properties"]["evidence_point_labels"]
    item_schema = copy.deepcopy(evidence_schema["items"])
    evidence_schema["prefixItems"] = [
        {
            "allOf": [
                copy.deepcopy(item_schema),
                {
                    "type": "object",
                    "properties": {"point_index": {"const": point_index}},
                    "required": ["point_index"],
                },
            ]
        }
        for point_index in range(expected_evidence_point_count)
    ]
    evidence_schema["items"] = False
    evidence_schema["description"] = (
        "Return exactly one judgment per expected evidence point, in order, "
        f"with point_index exactly 0..{expected_evidence_point_count - 1}."
        if expected_evidence_point_count
        else "Return an empty list because this case has no expected evidence points."
    )
    return schema


def build_stage_c_r3_json_mode_prompt(
    *,
    question: str,
    answer: str,
    retrieved_evidence: list[dict[str, object]],
    expected_evidence_points: list[str],
    answerability: str,
) -> str:
    """Build a prospective case-specific prompt while preserving the historical builder."""
    historical_prompt = build_judge_prompt(
        question=question,
        answer=answer,
        retrieved_evidence=retrieved_evidence,
        expected_evidence_points=expected_evidence_points,
        answerability=answerability,
    )
    payload = json.loads(historical_prompt)
    payload["required_output_schema"] = stage_c_r3_json_mode_case_schema(
        answerability=answerability,
        expected_evidence_point_count=len(expected_evidence_points),
    )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _require_raw_string(value: Any, path: str) -> None:
    if type(value) is not str or not value:
        raise StageCR3PreflightError(f"Synthetic readiness output has invalid raw string at {path}")


def _validate_raw_json_types(payload: Any, *, answerability: str) -> None:
    """Reject coercible values before Pydantic sees them."""
    if not isinstance(payload, dict):
        raise StageCR3PreflightError("Synthetic readiness output must be one JSON object")

    claim_labels = payload.get("claim_labels")
    if type(claim_labels) is not list or not claim_labels:
        raise StageCR3PreflightError("Synthetic readiness output requires a non-empty raw claim_labels list")
    for index, claim in enumerate(claim_labels):
        if not isinstance(claim, dict):
            raise StageCR3PreflightError(f"Synthetic readiness output has invalid raw claim at index {index}")
        for field in ("claim_id", "claim", "label", "justification"):
            _require_raw_string(claim.get(field), f"claim_labels[{index}].{field}")

    evidence_labels = payload.get("evidence_point_labels")
    if type(evidence_labels) is not list:
        raise StageCR3PreflightError("Synthetic readiness output requires a raw evidence_point_labels list")
    for index, evidence in enumerate(evidence_labels):
        if not isinstance(evidence, dict):
            raise StageCR3PreflightError(f"Synthetic readiness output has invalid raw evidence label at index {index}")
        if type(evidence.get("point_index")) is not int:
            raise StageCR3PreflightError(
                f"Synthetic readiness output has invalid raw integer at evidence_point_labels[{index}].point_index"
            )
        for field in ("label", "justification"):
            _require_raw_string(evidence.get(field), f"evidence_point_labels[{index}].{field}")

    _require_raw_string(payload.get("insufficiency_label"), "insufficiency_label")
    invalid_booleans = sorted(
        field for field in ALWAYS_BOOLEAN_FIELDS if type(payload.get(field)) is not bool
    )
    if invalid_booleans:
        raise StageCR3PreflightError(
            f"Synthetic readiness output has invalid raw Boolean fields: {invalid_booleans}"
        )
    if answerability == "partially_supported":
        invalid_scope = sorted(field for field in SCOPE_FIELDS if type(payload.get(field)) is not bool)
        if invalid_scope:
            raise StageCR3PreflightError(
                f"Synthetic readiness output has invalid raw scope Boolean fields: {invalid_scope}"
            )
    else:
        invalid_scope = sorted(field for field in SCOPE_FIELDS if payload.get(field) is not None)
        if invalid_scope:
            raise StageCR3PreflightError(
                f"Synthetic readiness output has non-null raw scope fields for answerability '{answerability}': {invalid_scope}"
            )


def validate_stage_c_r3_json_mode_probe_output(
    text: str,
    *,
    retrieval: dict[str, Any],
    expected_insufficiency_label: str | None,
    require_all_enums_exercised: bool,
) -> tuple[FormalJudgeOutput, str]:
    normalized, _ = normalize_judge_json_envelope(text)
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise StageCR3PreflightError("Synthetic readiness output is malformed JSON") from exc
    answerability = retrieval.get("answerability")
    if answerability not in {"supported", "partially_supported", "insufficient"}:
        raise StageCR3PreflightError(f"Unsupported answerability: {answerability}")
    _validate_raw_json_types(payload, answerability=answerability)
    return validate_stage_c_r3_probe_output(
        text,
        retrieval=retrieval,
        expected_insufficiency_label=expected_insufficiency_label,
        require_all_enums_exercised=require_all_enums_exercised,
    )


def _validate_json_mode_provider(provider: Any, timeout_seconds: float) -> None:
    if getattr(provider, "name", None) != JUDGE_PROVIDER or getattr(provider, "model", None) != JUDGE_MODEL:
        raise StageCR3PreflightError("JSON Mode preflight requires the frozen judge provider and model")
    if getattr(provider, "supports_response_format", False) is not True:
        raise StageCR3PreflightError("Configured provider does not explicitly support response_format")
    if getattr(provider, "supports_json_object_response_format", False) is not True:
        raise StageCR3PreflightError("Configured provider does not explicitly support JSON-object response_format")
    if float(getattr(provider, "timeout", -1)) != timeout_seconds:
        raise StageCR3PreflightError("JSON Mode preflight provider timeout mismatch")
    if int(getattr(provider, "max_tokens", -1)) < JUDGE_MAX_TOKENS:
        raise StageCR3PreflightError("JSON Mode preflight provider max_tokens is insufficient")
    if getattr(provider, "enable_thinking", None) is not False:
        raise StageCR3PreflightError("JSON Mode preflight requires enable_thinking=false")


def _validate_output_path(repository_root: Path, output_path: Path) -> Path:
    resolved = output_path.resolve()
    formal_runs = (repository_root / "research/experiments/western_formal_v0_1/runs").resolve()
    if resolved == formal_runs or formal_runs in resolved.parents:
        raise StageCR3PreflightError("Synthetic readiness output must never enter the formal Stage C runs directory")
    if resolved.exists() or resolved.with_suffix(resolved.suffix + ".tmp").exists():
        raise FileExistsError("Synthetic readiness output already exists; overwrite is prohibited")
    return resolved


def _verify_readiness_anchor(repository_root: Path, relative_path: str, expected_sha256: str, label: str) -> str:
    path = repository_root / relative_path
    if not path.is_file():
        raise StageCR3PreflightError(f"{label} readiness artifact is missing")
    actual = _sha256(path)
    if actual != expected_sha256:
        raise StageCR3PreflightError(
            f"{label} readiness artifact modified: expected {expected_sha256}, actual {actual}"
        )
    return actual


async def run_stage_c_r3_json_mode_preflight_v3(
    repository_root: Path,
    output_path: Path,
    *,
    provider: Any | None = None,
    probe_count: int = R3_PREFLIGHT_PROBE_COUNT,
    timeout_seconds: float = R3_PREFLIGHT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if probe_count != R3_PREFLIGHT_PROBE_COUNT:
        raise StageCR3PreflightError(
            f"JSON Mode v3 requires exactly {R3_PREFLIGHT_PROBE_COUNT} frozen synthetic probes"
        )
    output_path = _validate_output_path(repository_root, output_path)
    incident = StageCDirectory(
        repository_root / "research/experiments/western_formal_v0_1/runs" / STAGE_C_RUN_ID
    )
    _verify_stage_c_r2_incident_artifacts(repository_root, incident)
    v1_sha = _verify_readiness_anchor(
        repository_root,
        R3_PREFLIGHT_V1_READINESS_PATH,
        R3_PREFLIGHT_V1_READINESS_SHA256,
        "Stage C r3 preflight v1",
    )
    v2_sha = _verify_readiness_anchor(
        repository_root,
        R3_PREFLIGHT_V2_READINESS_PATH,
        R3_PREFLIGHT_V2_READINESS_SHA256,
        "Stage C r3 preflight v2",
    )

    active = provider or build_llm_provider(JUDGE_MODEL, timeout_override=timeout_seconds)
    _validate_json_mode_provider(active, timeout_seconds)
    probe_plan = get_synthetic_probe_plan()
    if len(probe_plan) != R3_PREFLIGHT_PROBE_COUNT:
        raise StageCR3PreflightError("Frozen synthetic probe matrix has changed")

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
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
                response_format=copy.deepcopy(R3_JSON_MODE_RESPONSE_FORMAT),
            )
            if getattr(result, "model", None) != JUDGE_MODEL:
                raise StageCR3PreflightError("Synthetic readiness provider-reported model mismatch")
            if getattr(result, "finish_reason", None) not in {None, "stop"}:
                raise StageCR3PreflightError(
                    f"Synthetic readiness returned unsupported finish_reason={getattr(result, 'finish_reason', None)}"
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
            raise StageCR3PreflightError("Configured provider rejected the JSON-object response_format argument") from exc
        except StageCR3PreflightError as exc:
            error_type = "schema_or_contract_failure"
            error_message = str(exc)

        latency_ms = round((perf_counter() - started) * 1000, 3)
        formal_timeout_compatible = (
            result is not None
            and error_type != "timeout"
            and latency_ms <= JUDGE_TIMEOUT_SECONDS * 1000
        )
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
            "response_sha256": (
                hashlib.sha256(result.text.encode("utf-8")).hexdigest()
                if result is not None and isinstance(getattr(result, "text", None), str)
                else None
            ),
            "raw_response_stored": False,
        })

    latencies = [float(probe["latency_ms"]) for probe in probes]
    successful = sum(probe["json_contract_success"] is True for probe in probes)
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
        successful == R3_PREFLIGHT_PROBE_COUNT
        and all(item["json_contract_passed"] is True for item in per_answerability.values())
    )
    formal_timeout_compatible = all(
        probe["formal_timeout_compatible"] is True for probe in probes
    )
    eligible = json_contract_passed and formal_timeout_compatible
    manifest = {
        "preflight_version": R3_JSON_MODE_PREFLIGHT_VERSION,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "status": "passed" if eligible else "failed",
        "synthetic_non_formal": True,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "protocol_version": PROTOCOL_VERSION,
        "source_r2_incident_manifest_sha256": _sha256(incident.incident_manifest_path()),
        "source_r3_preflight_v1_readiness_sha256": v1_sha,
        "source_r3_preflight_v2_readiness_sha256": v2_sha,
        "provider": JUDGE_PROVIDER,
        "model": JUDGE_MODEL,
        "response_format": copy.deepcopy(R3_JSON_MODE_RESPONSE_FORMAT),
        "temperature": JUDGE_TEMPERATURE,
        "max_tokens": JUDGE_MAX_TOKENS,
        "formal_timeout_seconds": JUDGE_TIMEOUT_SECONDS,
        "preflight_timeout_seconds": timeout_seconds,
        "enable_thinking": False,
        "judge_system_prompt_sha256": hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "judge_system_prompt_unchanged": True,
        "canonical_formal_judge_output_schema_sha256": hashlib.sha256(
            json.dumps(FormalJudgeOutput.model_json_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "case_specific_prompt_schema": True,
        "post_response_validator_authoritative": True,
        "provider_documented_capability_source": R3_PREFLIGHT_CAPABILITY_SOURCE,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "successful_probe_count": successful,
        "json_contract_passed": json_contract_passed,
        "formal_timeout_compatible": formal_timeout_compatible,
        "all_required_probes_passed": eligible,
        "per_answerability_summary": per_answerability,
        "timeout_occurrences": timeout_count,
        "mean_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
        "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "max_latency_ms": max(latencies) if latencies else 0.0,
        "no_repair_declaration": {
            "coercion": False,
            "semantic_normalization": False,
            "synonym_repair": False,
            "post_hoc_value_repair": False,
        },
        "model_operational_risk": {
            "provider_listing_status": R3_MODEL_PROVIDER_STATUS,
            "semantic_quality_inference": False,
            "replacement_requires_separate_prospective_execution_amendment": True,
            "replacement_must_never_be_silent": True,
        },
        "eligible_to_propose_formal_r3_freeze": eligible,
        "formal_r3_frozen": False,
        "probes": probes,
        "completed_at": _utc_now(),
    }
    _atomic_new_json(output_path, manifest)
    return manifest
