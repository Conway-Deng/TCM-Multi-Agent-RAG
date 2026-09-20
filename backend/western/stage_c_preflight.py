from __future__ import annotations

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


R3_PREFLIGHT_VERSION = "western-stage-c-r3-structured-output-preflight-v1"
R3_PREFLIGHT_PROBE_COUNT = 3
R3_PREFLIGHT_TIMEOUT_SECONDS = 300.0
R3_PREFLIGHT_CAPABILITY_SOURCE = "https://docs.siliconflow.com/cn/userguide/guides/json-mode-struct"
R3_STRUCTURED_RESPONSE_FORMAT_TYPE = "json_schema"
CLAIM_LABELS = {"supported", "partially_supported", "unsupported", "not_checkable"}
EVIDENCE_LABELS = {"covered", "partially_covered", "not_covered", "contradicted"}
BOOLEAN_FIELDS = {
    "stays_within_supported_evidence", "preserves_uncertainty", "invented_unsupported_information",
    "diagnosis_like_personalized_statement", "individualized_dosing",
    "prescription_like_recommendation", "research_or_educational_limitation_preserved",
}


class StageCR3PreflightError(RuntimeError):
    """A non-formal readiness failure that never authorizes formal r3 execution."""


def stage_c_r3_response_format() -> dict[str, Any]:
    return {
        "type": R3_STRUCTURED_RESPONSE_FORMAT_TYPE,
        "json_schema": {
            "name": "western_stage_c_judge_output",
            "schema": FormalJudgeOutput.model_json_schema(),
        },
    }


def _synthetic_probe_input() -> tuple[dict[str, Any], str]:
    retrieval = {
        "experiment_id": "synthetic-non-formal-stage-c-r3-readiness",
        "answerability": "partially_supported",
        "expected_evidence_points": [
            "Synthetic point zero is explicitly present.",
            "Synthetic point one is only partly present.",
            "Synthetic point two is absent.",
            "Synthetic point three is contradicted.",
        ],
    }
    question = (
        "Synthetic schema-readiness exercise only. Return exactly four unique claim labels using each allowed "
        "claim enum once, and exactly four evidence-point labels at indices 0,1,2,3 using each allowed evidence "
        "enum once. This is not a benchmark case and must never be used as research data."
    )
    answer = (
        "Synthetic claim A is directly supplied. Synthetic claim B is partly supplied. Synthetic claim C is not "
        "supplied. The phrase 'formatting exercise' is not an externally checkable claim."
    )
    evidence = [{
        "rank": 1,
        "article_title": "Synthetic non-formal readiness fixture",
        "section": "Synthetic",
        "evidence_excerpt": (
            "Synthetic point zero is explicitly present. Synthetic point one is partly present. "
            "Synthetic point three is explicitly contradicted."
        ),
    }]
    prompt = build_judge_prompt(
        question=question,
        answer=answer,
        retrieved_evidence=evidence,
        expected_evidence_points=retrieval["expected_evidence_points"],
        answerability=retrieval["answerability"],
    )
    return retrieval, prompt


def validate_stage_c_r3_probe_output(text: str) -> tuple[FormalJudgeOutput, str]:
    normalized, normalization = normalize_judge_json_envelope(text)
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise StageCR3PreflightError("Synthetic readiness output is malformed JSON") from exc
    if not isinstance(payload, dict):
        raise StageCR3PreflightError("Synthetic readiness output must be one JSON object")
    invalid_booleans = sorted(field for field in BOOLEAN_FIELDS if type(payload.get(field)) is not bool)
    if invalid_booleans:
        raise StageCR3PreflightError(f"Synthetic readiness output has invalid Boolean fields: {invalid_booleans}")
    try:
        parsed = FormalJudgeOutput.model_validate(payload)
        retrieval, _ = _synthetic_probe_input()
        _validate_completed_judge_output(parsed, retrieval)
    except (ValueError, FatalFormalRunError) as exc:
        raise StageCR3PreflightError(f"Synthetic readiness output violates the frozen schema: {exc}") from exc
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
        raise StageCR3PreflightError("At least three synthetic readiness probes are required")
    output_path = _validate_preflight_output_path(repository_root, output_path)
    incident = StageCDirectory(
        repository_root / "research/experiments/western_formal_v0_1/runs" / STAGE_C_RUN_ID
    )
    incident_manifest = _verify_stage_c_r2_incident_artifacts(repository_root, incident)
    active = provider or build_llm_provider(JUDGE_MODEL, timeout_override=timeout_seconds)
    _validate_preflight_provider(active, timeout_seconds)
    response_format = stage_c_r3_response_format()
    retrieval, prompt = _synthetic_probe_input()
    probes: list[dict[str, Any]] = []
    for probe_number in range(1, probe_count + 1):
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
            _, normalization = validate_stage_c_r3_probe_output(result.text)
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
    passed = successful == probe_count and timeout_count == 0
    manifest = {
        "preflight_version": R3_PREFLIGHT_VERSION,
        "status": "passed" if passed else "failed",
        "synthetic_non_formal": True,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "protocol_version": PROTOCOL_VERSION,
        "source_r2_incident_manifest_sha256": _sha256(incident.incident_manifest_path()),
        "provider": JUDGE_PROVIDER,
        "model": JUDGE_MODEL,
        "temperature": JUDGE_TEMPERATURE,
        "max_tokens": JUDGE_MAX_TOKENS,
        "formal_timeout_seconds_unchanged": JUDGE_TIMEOUT_SECONDS,
        "preflight_timeout_seconds": timeout_seconds,
        "enable_thinking": False,
        "judge_system_prompt_sha256": hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "judge_system_prompt_unchanged": True,
        "response_format": response_format,
        "response_format_sha256": hashlib.sha256(
            json.dumps(response_format, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "provider_documented_capability_source": R3_PREFLIGHT_CAPABILITY_SOURCE,
        "probe_count": probe_count,
        "successful_probe_count": successful,
        "all_required_probes_passed": passed,
        "timeout_occurrences": timeout_count,
        "mean_latency_ms": statistics.fmean(latencies),
        "median_latency_ms": statistics.median(latencies),
        "max_latency_ms": max(latencies),
        "no_synonym_or_post_hoc_value_repair": True,
        "eligible_to_propose_formal_r3_freeze": passed,
        "formal_r3_frozen": False,
        "probes": probes,
        "completed_at": _utc_now(),
    }
    _atomic_new_json(output_path, manifest)
    return manifest
