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
    FatalFormalRunError,
    StageCDirectory,
    _atomic_new_json,
    _error_type,
    _sha256,
    _utc_now,
    _validate_completed_judge_output,
    _verify_stage_c_r2_incident_artifacts,
)
from .formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT, build_judge_prompt, normalize_judge_json_envelope


R3_PREFLIGHT_VERSION = "western-stage-c-r3-structured-output-preflight-v2"
R3_PREFLIGHT_PROBE_PLAN_VERSION = "western-stage-c-r3-preflight-matrix-v1"
R3_PREFLIGHT_PROBE_COUNT = 6
R3_PREFLIGHT_TIMEOUT_SECONDS = 300.0
R3_PREFLIGHT_CAPABILITY_SOURCE = "https://docs.siliconflow.com/cn/userguide/guides/json-mode-struct"
R3_STRUCTURED_RESPONSE_FORMAT_TYPE = "json_schema"
CLAIM_LABELS = {"supported", "partially_supported", "unsupported", "not_checkable"}
EVIDENCE_LABELS = {"covered", "partially_covered", "not_covered", "contradicted"}
ALWAYS_BOOLEAN_FIELDS = {
    "diagnosis_like_personalized_statement",
    "individualized_dosing",
    "prescription_like_recommendation",
    "research_or_educational_limitation_preserved",
}
SCOPE_FIELDS = {
    "stays_within_supported_evidence",
    "preserves_uncertainty",
    "invented_unsupported_information",
}
INSUFFICIENT_LABELS = [
    "appropriate_abstention",
    "appropriate_bounded_insufficiency",
    "substantive_answer_without_insufficiency_acknowledgement",
    "overclaim_beyond_pilot_evidence",
]
R3_PREFLIGHT_V1_READINESS_PATH = "research/experiments/western_formal_v0_1/stage_c_r3_preflight_readiness.json"
R3_PREFLIGHT_V1_READINESS_SHA256 = "4129c0fae0ddf8f8da3d81bc6e18e673bdd71b5d512ff4c97fc01973a530d9e3"
R3_PREFLIGHT_V1_OBSERVED_LATENCY = {
    "probe_count": 3,
    "timeouts": 0,
    "mean_latency_ms": 59030.17166666667,
    "median_latency_ms": 58087.616,
    "max_latency_ms": 63760.028,
}


class StageCR3PreflightError(RuntimeError):
    """A non-formal readiness failure that never authorizes formal r3 execution."""


def stage_c_r3_response_format(
    *,
    answerability: str = "partially_supported",
    expected_evidence_point_count: int = 4,
) -> dict[str, Any]:
    if answerability not in {"partially_supported", "supported", "insufficient"}:
        raise StageCR3PreflightError(f"Unsupported answerability: {answerability}")
    if expected_evidence_point_count < 0:
        raise StageCR3PreflightError(f"expected_evidence_point_count must be non-negative, got {expected_evidence_point_count}")

    schema = copy.deepcopy(FormalJudgeOutput.model_json_schema())

    # Scope field specialization
    if answerability == "partially_supported":
        for field in SCOPE_FIELDS:
            schema["properties"][field] = {
                "title": schema["properties"][field].get("title", field.replace("_", " ").title()),
                "type": "boolean",
            }
    else:  # supported or insufficient
        for field in SCOPE_FIELDS:
            schema["properties"][field] = {
                "title": schema["properties"][field].get("title", field.replace("_", " ").title()),
                "type": "null",
            }

    # Insufficiency label specialization
    if answerability in {"supported", "partially_supported"}:
        schema["properties"]["insufficiency_label"]["enum"] = ["not_applicable"]
    else:  # insufficient
        schema["properties"]["insufficiency_label"]["enum"] = list(INSUFFICIENT_LABELS)

    # Array constraint specialization
    schema["properties"]["claim_labels"]["minItems"] = 1
    schema["properties"]["evidence_point_labels"]["minItems"] = expected_evidence_point_count
    schema["properties"]["evidence_point_labels"]["maxItems"] = expected_evidence_point_count

    return {
        "type": R3_STRUCTURED_RESPONSE_FORMAT_TYPE,
        "json_schema": {
            "name": "western_stage_c_judge_output",
            "schema": schema,
        },
    }


def get_synthetic_probe_plan() -> list[dict[str, Any]]:
    return [
        {
            "probe_number": 1,
            "probe_id": "synthetic-supported-probe-01",
            "answerability": "supported",
            "retrieval": {
                "experiment_id": "synthetic-supported-probe-01",
                "answerability": "supported",
                "expected_evidence_points": [
                    "Synthetic supported point zero is fully verified in the local fixture.",
                    "Synthetic supported point one is verified in the local fixture.",
                ],
            },
            "question": (
                "Synthetic schema-readiness exercise for supported answerability. "
                "Verify whether all synthetic claims are supported by the provided evidence."
            ),
            "answer": (
                "Synthetic claim 0 is fully present. Synthetic claim 1 is fully present."
            ),
            "evidence": [{
                "rank": 1,
                "article_title": "Synthetic Supported Readiness Fixture One",
                "section": "Synthetic",
                "evidence_excerpt": (
                    "Synthetic supported point zero is fully verified in the local fixture. "
                    "Synthetic supported point one is verified in the local fixture."
                ),
            }],
            "expected_insufficiency_label": "not_applicable",
            "require_all_enums_exercised": False,
        },
        {
            "probe_number": 2,
            "probe_id": "synthetic-supported-probe-02",
            "answerability": "supported",
            "retrieval": {
                "experiment_id": "synthetic-supported-probe-02",
                "answerability": "supported",
                "expected_evidence_points": [
                    "Synthetic supported point alpha is verified in the reference text.",
                    "Synthetic supported point beta is verified in the reference text.",
                    "Synthetic supported point gamma is verified in the reference text.",
                ],
            },
            "question": (
                "Synthetic schema-readiness exercise for supported answerability replay. "
                "Verify whether all synthetic claims are supported."
            ),
            "answer": (
                "Synthetic claim alpha is supported. Synthetic claim beta is supported. Synthetic claim gamma is supported."
            ),
            "evidence": [{
                "rank": 1,
                "article_title": "Synthetic Supported Readiness Fixture Two",
                "section": "Synthetic",
                "evidence_excerpt": (
                    "Synthetic supported point alpha is verified in the reference text. "
                    "Synthetic supported point beta is verified in the reference text. "
                    "Synthetic supported point gamma is verified in the reference text."
                ),
            }],
            "expected_insufficiency_label": "not_applicable",
            "require_all_enums_exercised": False,
        },
        {
            "probe_number": 3,
            "probe_id": "synthetic-partially-supported-probe-01",
            "answerability": "partially_supported",
            "retrieval": {
                "experiment_id": "synthetic-partially-supported-probe-01",
                "answerability": "partially_supported",
                "expected_evidence_points": [
                    "Synthetic point zero is explicitly present.",
                    "Synthetic point one is only partly present.",
                    "Synthetic point two is absent.",
                    "Synthetic point three is contradicted.",
                ],
            },
            "question": (
                "Synthetic schema-readiness exercise only. Return exactly four unique claim labels using each allowed "
                "claim enum once, and exactly four evidence-point labels at indices 0,1,2,3 using each allowed evidence "
                "enum once. This is not a benchmark case and must never be used as research data."
            ),
            "answer": (
                "Synthetic claim A is directly supplied. Synthetic claim B is partly supplied. Synthetic claim C is not "
                "supplied. The phrase 'formatting exercise' is not an externally checkable claim."
            ),
            "evidence": [{
                "rank": 1,
                "article_title": "Synthetic non-formal readiness fixture",
                "section": "Synthetic",
                "evidence_excerpt": (
                    "Synthetic point zero is explicitly present. Synthetic point one is partly present. "
                    "Synthetic point three is explicitly contradicted."
                ),
            }],
            "expected_insufficiency_label": "not_applicable",
            "require_all_enums_exercised": True,
        },
        {
            "probe_number": 4,
            "probe_id": "synthetic-partially-supported-probe-02",
            "answerability": "partially_supported",
            "retrieval": {
                "experiment_id": "synthetic-partially-supported-probe-02",
                "answerability": "partially_supported",
                "expected_evidence_points": [
                    "Synthetic scope point zero is documented.",
                    "Synthetic scope point one is partly documented.",
                    "Synthetic scope point two is unverified.",
                ],
            },
            "question": (
                "Synthetic schema-readiness exercise for partially supported scope verification. "
                "Evaluate claims against the partial evidence."
            ),
            "answer": (
                "Synthetic claim 1 is documented. Synthetic claim 2 is partly documented. Synthetic claim 3 is unverified."
            ),
            "evidence": [{
                "rank": 1,
                "article_title": "Synthetic Scope Fixture Two",
                "section": "Synthetic",
                "evidence_excerpt": (
                    "Synthetic scope point zero is documented. Synthetic scope point one is partly documented."
                ),
            }],
            "expected_insufficiency_label": "not_applicable",
            "require_all_enums_exercised": False,
        },
        {
            "probe_number": 5,
            "probe_id": "synthetic-insufficient-probe-01",
            "answerability": "insufficient",
            "retrieval": {
                "experiment_id": "synthetic-insufficient-probe-01",
                "answerability": "insufficient",
                "expected_evidence_points": [
                    "Synthetic clinical claim cannot be established from the retrieved evidence.",
                    "Synthetic guidance point is missing from available evidence.",
                ],
            },
            "question": (
                "Synthetic schema-readiness exercise for insufficient answerability. "
                "The evidence is entirely insufficient to answer the query safely."
            ),
            "answer": (
                "Due to lack of supporting evidence in the available records, this query cannot be answered. "
                "Further consultation with primary clinical documentation is required."
            ),
            "evidence": [{
                "rank": 1,
                "article_title": "Synthetic Unrelated Article One",
                "section": "Synthetic",
                "evidence_excerpt": (
                    "This excerpt does not contain information relevant to the query."
                ),
            }],
            "expected_insufficiency_label": "appropriate_abstention",
            "require_all_enums_exercised": False,
        },
        {
            "probe_number": 6,
            "probe_id": "synthetic-insufficient-probe-02",
            "answerability": "insufficient",
            "retrieval": {
                "experiment_id": "synthetic-insufficient-probe-02",
                "answerability": "insufficient",
                "expected_evidence_points": [
                    "Synthetic evidence does not support establishing dosage or efficacy.",
                    "Synthetic safety boundary must be explicitly stated.",
                ],
            },
            "question": (
                "Synthetic schema-readiness exercise for bounded insufficiency. "
                "The answer acknowledges the clinical evidence limitations and bounds its scope appropriately."
            ),
            "answer": (
                "While preliminary background suggests general therapeutic interest, the available synthetic evidence "
                "does not support specific dosage or efficacy conclusions. The guidance is strictly bounded by these evidence limits."
            ),
            "evidence": [{
                "rank": 1,
                "article_title": "Synthetic Limited Scope Fixture",
                "section": "Synthetic",
                "evidence_excerpt": (
                    "Synthetic preliminary overview mentions therapeutic interest, but specifies that clinical efficacy and dosing remain unestablished."
                ),
            }],
            "expected_insufficiency_label": "appropriate_bounded_insufficiency",
            "require_all_enums_exercised": False,
        },
    ]


def _synthetic_probe_input() -> tuple[dict[str, Any], str]:
    probe = get_synthetic_probe_plan()[2]
    prompt = build_judge_prompt(
        question=probe["question"],
        answer=probe["answer"],
        retrieved_evidence=probe["evidence"],
        expected_evidence_points=probe["retrieval"]["expected_evidence_points"],
        answerability=probe["retrieval"]["answerability"],
    )
    return probe["retrieval"], prompt


def validate_stage_c_r3_probe_output(
    text: str,
    *,
    retrieval: dict[str, Any] | None = None,
    answerability: str | None = None,
    expected_evidence_points: list[str] | None = None,
    expected_insufficiency_label: str | None = None,
    require_all_enums_exercised: bool = False,
) -> tuple[FormalJudgeOutput, str]:
    effective_answerability = (
        (retrieval.get("answerability") if retrieval else None)
        or answerability
        or "partially_supported"
    )
    if effective_answerability not in {"partially_supported", "supported", "insufficient"}:
        raise StageCR3PreflightError(f"Unsupported answerability: {effective_answerability}")

    normalized, normalization = normalize_judge_json_envelope(text)
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise StageCR3PreflightError("Synthetic readiness output is malformed JSON") from exc
    if not isinstance(payload, dict):
        raise StageCR3PreflightError("Synthetic readiness output must be one JSON object")

    # Raw type validation for ALWAYS_BOOLEAN_FIELDS
    invalid_booleans = sorted(field for field in ALWAYS_BOOLEAN_FIELDS if type(payload.get(field)) is not bool)
    if invalid_booleans:
        raise StageCR3PreflightError(f"Synthetic readiness output has invalid Boolean fields: {invalid_booleans}")

    # Raw type validation for SCOPE_FIELDS
    if effective_answerability == "partially_supported":
        invalid_scope_booleans = sorted(field for field in SCOPE_FIELDS if type(payload.get(field)) is not bool)
        if invalid_scope_booleans:
            raise StageCR3PreflightError(f"Synthetic readiness output has invalid scope Boolean fields: {invalid_scope_booleans}")
    else:
        invalid_scope_non_null = sorted(field for field in SCOPE_FIELDS if payload.get(field) is not None)
        if invalid_scope_non_null:
            raise StageCR3PreflightError(
                f"Synthetic readiness output has non-null scope fields for answerability '{effective_answerability}': {invalid_scope_non_null}"
            )

    # Determine effective retrieval for production semantic validation
    if retrieval is not None:
        active_retrieval = dict(retrieval)
    else:
        synthetic_retrieval, _ = _synthetic_probe_input()
        active_retrieval = dict(synthetic_retrieval)
        active_retrieval["answerability"] = effective_answerability
        if expected_evidence_points is not None:
            active_retrieval["expected_evidence_points"] = expected_evidence_points

    try:
        parsed = FormalJudgeOutput.model_validate(payload)
        _validate_completed_judge_output(parsed, active_retrieval)
    except (ValueError, FatalFormalRunError) as exc:
        raise StageCR3PreflightError(f"Synthetic readiness output violates the frozen schema: {exc}") from exc

    # Additional fixture-aware synthetic contract checks
    if effective_answerability in {"supported", "partially_supported"}:
        if parsed.insufficiency_label != "not_applicable":
            raise StageCR3PreflightError("Synthetic readiness output for non-insufficient case must use not_applicable")
    elif effective_answerability == "insufficient":
        if parsed.insufficiency_label == "not_applicable":
            raise StageCR3PreflightError("Synthetic readiness output for insufficient case cannot use not_applicable")
        if parsed.insufficiency_label not in INSUFFICIENT_LABELS:
            raise StageCR3PreflightError(f"Synthetic readiness output has invalid insufficiency_label '{parsed.insufficiency_label}'")
        if expected_insufficiency_label is not None and parsed.insufficiency_label != expected_insufficiency_label:
            raise StageCR3PreflightError(
                f"Synthetic readiness output expected insufficiency_label '{expected_insufficiency_label}', got '{parsed.insufficiency_label}'"
            )

    # Enum exercise check for probes requiring all enums
    check_all_enums = require_all_enums_exercised or (
        retrieval is None
        and expected_evidence_points is None
        and effective_answerability == "partially_supported"
    )
    if check_all_enums:
        claim_labels = [item.label for item in parsed.claim_labels]
        evidence_labels = [item.label for item in parsed.evidence_point_labels]
        if len(claim_labels) != 4 or set(claim_labels) != CLAIM_LABELS:
            raise StageCR3PreflightError("Synthetic readiness output must exercise each exact claim enum once")
        if len(evidence_labels) != 4 or set(evidence_labels) != EVIDENCE_LABELS:
            raise StageCR3PreflightError("Synthetic readiness output must exercise each exact evidence enum once")

    return parsed, normalization


def _validate_preflight_provider(provider: Any, timeout_seconds: float) -> None:
    if getattr(provider, "name", None) != JUDGE_PROVIDER or getattr(provider, "model", None) != JUDGE_MODEL:
        raise StageCR3PreflightError("Structured-output preflight requires the frozen judge provider and model")
    if getattr(provider, "supports_response_format", False) is not True:
        raise StageCR3PreflightError("Configured provider does not explicitly support response_format")
    if getattr(provider, "supports_json_schema_response_format", False) is not True:
        raise StageCR3PreflightError("Configured provider does not explicitly support JSON Schema structured output")
    if float(getattr(provider, "timeout", -1)) != timeout_seconds:
        raise StageCR3PreflightError("Structured-output preflight provider timeout mismatch")
    if int(getattr(provider, "max_tokens", -1)) < JUDGE_MAX_TOKENS:
        raise StageCR3PreflightError("Structured-output preflight provider max_tokens is insufficient")
    if getattr(provider, "enable_thinking", None) is not False:
        raise StageCR3PreflightError("Structured-output preflight requires enable_thinking=false")


def _validate_preflight_output_path(repository_root: Path, output_path: Path) -> Path:
    resolved = output_path.resolve()
    formal_runs = (repository_root / "research/experiments/western_formal_v0_1/runs").resolve()
    if resolved == formal_runs or formal_runs in resolved.parents:
        raise StageCR3PreflightError("Synthetic readiness output must never enter the formal Stage C runs directory")
    if resolved.exists() or resolved.with_suffix(resolved.suffix + ".tmp").exists():
        raise FileExistsError("Synthetic readiness output already exists; overwrite is prohibited")
    return resolved


async def run_stage_c_r3_structured_output_preflight(
    repository_root: Path,
    output_path: Path,
    *,
    provider: Any | None = None,
    probe_count: int = R3_PREFLIGHT_PROBE_COUNT,
    timeout_seconds: float = R3_PREFLIGHT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if probe_count < R3_PREFLIGHT_PROBE_COUNT:
        raise StageCR3PreflightError(
            f"At least {R3_PREFLIGHT_PROBE_COUNT} synthetic readiness probes (two per answerability class) are required"
        )
    output_path = _validate_preflight_output_path(repository_root, output_path)
    incident = StageCDirectory(
        repository_root / "research/experiments/western_formal_v0_1/runs" / STAGE_C_RUN_ID
    )
    incident_manifest = _verify_stage_c_r2_incident_artifacts(repository_root, incident)

    # Verify v1 readiness artifact immutability if present
    v1_readiness_path = repository_root / R3_PREFLIGHT_V1_READINESS_PATH
    if v1_readiness_path.exists():
        v1_sha = _sha256(v1_readiness_path)
        if v1_sha != R3_PREFLIGHT_V1_READINESS_SHA256:
            raise StageCR3PreflightError(
                f"Stage C r3 preflight v1 readiness artifact modified: expected {R3_PREFLIGHT_V1_READINESS_SHA256}, actual {v1_sha}"
            )

    active = provider or build_llm_provider(JUDGE_MODEL, timeout_override=timeout_seconds)
    _validate_preflight_provider(active, timeout_seconds)

    probe_plan = get_synthetic_probe_plan()
    if probe_count != len(probe_plan):
        raise StageCR3PreflightError(
            f"Probe count mismatch: matrix requires exactly {len(probe_plan)} probes, got {probe_count}"
        )

    probes: list[dict[str, Any]] = []
    for spec in probe_plan:
        probe_number = spec["probe_number"]
        ans = spec["answerability"]
        retrieval = spec["retrieval"]
        expected_count = len(retrieval["expected_evidence_points"])
        prompt = build_judge_prompt(
            question=spec["question"],
            answer=spec["answer"],
            retrieved_evidence=spec["evidence"],
            expected_evidence_points=retrieval["expected_evidence_points"],
            answerability=retrieval["answerability"],
        )
        response_format = stage_c_r3_response_format(
            answerability=ans,
            expected_evidence_point_count=expected_count,
        )

        started = perf_counter()
        result: Any | None = None
        error_type: str | None = None
        error_message: str | None = None
        normalization: str | None = None
        schema_success = False
        try:
            result = await active.generate(
                system=JUDGE_SYSTEM_PROMPT,
                prompt=prompt,
                temperature=JUDGE_TEMPERATURE,
                max_tokens=JUDGE_MAX_TOKENS,
                response_format=response_format,
            )
            if getattr(result, "model", None) != JUDGE_MODEL:
                raise StageCR3PreflightError("Synthetic readiness provider-reported model mismatch")
            if getattr(result, "finish_reason", None) not in {None, "stop"}:
                raise StageCR3PreflightError(
                    f"Synthetic readiness returned unsupported finish_reason={getattr(result, 'finish_reason', None)}"
                )
            _, normalization = validate_stage_c_r3_probe_output(
                result.text,
                retrieval=retrieval,
                expected_insufficiency_label=spec.get("expected_insufficiency_label"),
                require_all_enums_exercised=spec.get("require_all_enums_exercised", False),
            )
            schema_success = True
        except ProviderUnavailable as exc:
            error_type = _error_type(exc)
            error_message = str(exc)
        except TypeError as exc:
            raise StageCR3PreflightError("Configured provider rejected the structured response_format argument") from exc
        except StageCR3PreflightError as exc:
            error_type = "schema_or_contract_failure"
            error_message = str(exc)
        latency_ms = round((perf_counter() - started) * 1000, 3)
        probes.append({
            "probe_number": probe_number,
            "probe_id": spec["probe_id"],
            "answerability": ans,
            "expected_evidence_point_count": expected_count,
            "synthetic_non_formal": True,
            "provider_call_success": result is not None,
            "schema_validation_success": schema_success,
            "normalization": normalization,
            "provider_reported_model": getattr(result, "model", None),
            "finish_reason": getattr(result, "finish_reason", None),
            "latency_ms": latency_ms,
            "error_type": error_type,
            "error_message": error_message,
            "response_sha256": (
                hashlib.sha256(result.text.encode("utf-8")).hexdigest()
                if result is not None and isinstance(getattr(result, "text", None), str) else None
            ),
            "raw_response_stored": False,
        })

    latencies = [float(probe["latency_ms"]) for probe in probes]
    successful = sum(probe["schema_validation_success"] is True for probe in probes)
    timeout_count = sum(probe["error_type"] == "timeout" for probe in probes)

    per_answerability: dict[str, dict[str, Any]] = {}
    for ans in ("supported", "partially_supported", "insufficient"):
        ans_probes = [p for p in probes if p["answerability"] == ans]
        attempted = len(ans_probes)
        successful_ans = sum(p["schema_validation_success"] is True for p in ans_probes)
        timeouts_ans = sum(p["error_type"] == "timeout" for p in ans_probes)
        per_answerability[ans] = {
            "attempted": attempted,
            "successful": successful_ans,
            "timeouts": timeouts_ans,
            "passed": attempted >= 2 and successful_ans == attempted and timeouts_ans == 0,
        }

    all_classes_passed = all(summary["passed"] is True for summary in per_answerability.values())
    passed = successful == probe_count and timeout_count == 0 and all_classes_passed

    manifest = {
        "preflight_version": R3_PREFLIGHT_VERSION,
        "probe_plan_version": R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "status": "passed" if passed else "failed",
        "synthetic_non_formal": True,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "protocol_version": PROTOCOL_VERSION,
        "source_r2_incident_manifest_sha256": _sha256(incident.incident_manifest_path()),
        "source_r3_preflight_v1_readiness_sha256": R3_PREFLIGHT_V1_READINESS_SHA256 if v1_readiness_path.exists() else None,
        "prior_preflight_v1_observed_latency": R3_PREFLIGHT_V1_OBSERVED_LATENCY,
        "provider": JUDGE_PROVIDER,
        "model": JUDGE_MODEL,
        "temperature": JUDGE_TEMPERATURE,
        "max_tokens": JUDGE_MAX_TOKENS,
        "formal_timeout_seconds_unchanged": JUDGE_TIMEOUT_SECONDS,
        "preflight_timeout_seconds": timeout_seconds,
        "enable_thinking": False,
        "judge_system_prompt_sha256": hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "judge_system_prompt_unchanged": True,
        "provider_documented_capability_source": R3_PREFLIGHT_CAPABILITY_SOURCE,
        "probe_count": probe_count,
        "successful_probe_count": successful,
        "all_required_probes_passed": passed,
        "all_answerability_classes_passed": all_classes_passed,
        "per_answerability_summary": per_answerability,
        "timeout_occurrences": timeout_count,
        "mean_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
        "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "max_latency_ms": max(latencies) if latencies else 0.0,
        "no_synonym_or_post_hoc_value_repair": True,
        "eligible_to_propose_formal_r3_freeze": passed,
        "formal_r3_frozen": False,
        "probes": probes,
        "completed_at": _utc_now(),
    }
    _atomic_new_json(output_path, manifest)
    return manifest
