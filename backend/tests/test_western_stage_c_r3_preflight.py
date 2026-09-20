from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable, _chat_payload
from western import formal_eval as f
from western.stage_c_preflight import (
    R3_PREFLIGHT_TIMEOUT_SECONDS,
    StageCR3PreflightError,
    run_stage_c_r3_structured_output_preflight,
    stage_c_r3_response_format,
    validate_stage_c_r3_probe_output,
)


ROOT = Path(__file__).resolve().parents[2]
R2_RUN = ROOT / "research/experiments/western_formal_v0_1/runs" / f.STAGE_C_RUN_ID


def _payload() -> dict[str, object]:
    claim_labels = ["supported", "partially_supported", "unsupported", "not_checkable"]
    evidence_labels = ["covered", "partially_covered", "not_covered", "contradicted"]
    return {
        "claim_labels": [
            {
                "claim_id": f"c{index}", "claim": f"Synthetic claim {index}.", "label": label,
                "justification": "Synthetic non-formal readiness fixture.",
            }
            for index, label in enumerate(claim_labels)
        ],
        "evidence_point_labels": [
            {
                "point_index": index, "label": label,
                "justification": "Synthetic non-formal readiness fixture.",
            }
            for index, label in enumerate(evidence_labels)
        ],
        "insufficiency_label": "not_applicable",
        "stays_within_supported_evidence": True,
        "preserves_uncertainty": True,
        "invented_unsupported_information": False,
        "diagnosis_like_personalized_statement": False,
        "individualized_dosing": False,
        "prescription_like_recommendation": False,
        "research_or_educational_limitation_preserved": True,
    }


def _result(payload: dict[str, object] | None = None) -> GenerationResult:
    return GenerationResult(
        text=json.dumps(payload or _payload()),
        provider=f.JUDGE_PROVIDER,
        model=f.JUDGE_MODEL,
        finish_reason="stop",
    )


class PreflightProvider:
    name = f.JUDGE_PROVIDER
    model = f.JUDGE_MODEL
    timeout = R3_PREFLIGHT_TIMEOUT_SECONDS
    max_tokens = f.JUDGE_MAX_TOKENS
    enable_thinking = False
    supports_response_format = True
    supports_json_schema_response_format = True

    def __init__(self, results: list[GenerationResult | Exception]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs: object) -> GenerationResult:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_openai_compatible_payload_supports_json_object_and_json_schema() -> None:
    for response_format in ({"type": "json_object"}, stage_c_r3_response_format()):
        payload = _chat_payload(
            model=f.JUDGE_MODEL,
            system="system",
            prompt="synthetic",
            temperature=0.0,
            max_tokens=1200,
            frequency_penalty=0.0,
            response_format=response_format,
        )
        assert payload["response_format"] == response_format
        assert payload["enable_thinking"] is False


def test_structured_response_format_uses_unchanged_formal_schema() -> None:
    response_format = stage_c_r3_response_format()
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == f.FormalJudgeOutput.model_json_schema()


def test_exact_synthetic_output_contract_passes_without_value_repair() -> None:
    parsed, normalization = validate_stage_c_r3_probe_output(json.dumps(_payload()))
    assert normalization == "none"
    assert {item.label for item in parsed.claim_labels} == {
        "supported", "partially_supported", "unsupported", "not_checkable",
    }
    assert {item.label for item in parsed.evidence_point_labels} == {
        "covered", "partially_covered", "not_covered", "contradicted",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [("claim", "exactly supported"), ("claim", "partially supported"), ("evidence", "exactly covered"), ("evidence", "not covered")],
)
def test_observed_synonyms_are_rejected_without_post_hoc_repair(field: str, value: str) -> None:
    payload = _payload()
    if field == "claim":
        payload["claim_labels"][0]["label"] = value  # type: ignore[index]
    else:
        payload["evidence_point_labels"][0]["label"] = value  # type: ignore[index]
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        validate_stage_c_r3_probe_output(json.dumps(payload))


def test_malformed_json_invalid_boolean_and_evidence_indices_remain_rejected() -> None:
    with pytest.raises(StageCR3PreflightError, match="malformed JSON"):
        validate_stage_c_r3_probe_output("{broken")
    invalid_bool = _payload()
    invalid_bool["preserves_uncertainty"] = "true"
    with pytest.raises(StageCR3PreflightError, match="Boolean"):
        validate_stage_c_r3_probe_output(json.dumps(invalid_bool))
    invalid_index = _payload()
    invalid_index["evidence_point_labels"][2]["point_index"] = 9  # type: ignore[index]
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        validate_stage_c_r3_probe_output(json.dumps(invalid_index))


def test_unsupported_structured_output_capability_fails_explicitly(tmp_path: Path) -> None:
    provider = PreflightProvider([_result()] * 3)
    provider.supports_json_schema_response_format = False
    with pytest.raises(StageCR3PreflightError, match="does not explicitly support JSON Schema"):
        asyncio.run(run_stage_c_r3_structured_output_preflight(
            ROOT, tmp_path / "readiness.json", provider=provider,
        ))
    assert provider.calls == []


def test_three_synthetic_probes_must_all_pass_and_never_touch_formal_rows(tmp_path: Path) -> None:
    provider = PreflightProvider([_result(), _result(), _result()])
    raw_before = (R2_RUN / "stage_c_judge.jsonl").read_bytes()
    output = tmp_path / "non-formal" / "readiness.json"
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, output, provider=provider,
    ))
    assert manifest["status"] == "passed"
    assert manifest["successful_probe_count"] == 3
    assert manifest["all_required_probes_passed"] is True
    assert manifest["eligible_to_propose_formal_r3_freeze"] is True
    assert manifest["formal_r3_frozen"] is False
    assert manifest["synthetic_non_formal"] is True
    assert manifest["outputs_eligible_as_research_data"] is False
    assert all(probe["raw_response_stored"] is False for probe in manifest["probes"])
    assert all(call["response_format"]["type"] == "json_schema" for call in provider.calls)  # type: ignore[index]
    assert all(call["system"] == f.JUDGE_SYSTEM_PROMPT for call in provider.calls)
    assert (R2_RUN / "stage_c_judge.jsonl").read_bytes() == raw_before
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "passed"


def test_one_schema_failure_fails_readiness_without_repair(tmp_path: Path) -> None:
    invalid = _payload()
    invalid["claim_labels"][0]["label"] = "exactly supported"  # type: ignore[index]
    provider = PreflightProvider([_result(), _result(invalid), _result()])
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / "failed-readiness.json", provider=provider,
    ))
    assert manifest["status"] == "failed"
    assert manifest["successful_probe_count"] == 2
    assert manifest["all_required_probes_passed"] is False
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False
    assert len(provider.calls) == 3


def test_timeout_is_measured_as_failed_readiness_without_hidden_retry(tmp_path: Path) -> None:
    provider = PreflightProvider([
        _result(), ProviderUnavailable("timed out", error_type="timeout"), _result(),
    ])
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / "timeout-readiness.json", provider=provider,
    ))
    assert manifest["status"] == "failed"
    assert manifest["timeout_occurrences"] == 1
    assert manifest["successful_probe_count"] == 2
    assert len(provider.calls) == 3


def test_preflight_requires_at_least_three_probes_and_nonformal_output_path(tmp_path: Path) -> None:
    provider = PreflightProvider([_result()] * 3)
    with pytest.raises(StageCR3PreflightError, match="At least three"):
        asyncio.run(run_stage_c_r3_structured_output_preflight(
            ROOT, tmp_path / "too-few.json", provider=provider, probe_count=2,
        ))
    with pytest.raises(StageCR3PreflightError, match="must never enter"):
        asyncio.run(run_stage_c_r3_structured_output_preflight(
            ROOT, R2_RUN / "readiness.json", provider=provider,
        ))
    assert provider.calls == []


def test_preflight_manifest_anchors_incident_and_records_latency(tmp_path: Path) -> None:
    provider = PreflightProvider([_result()] * 3)
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / "readiness.json", provider=provider,
    ))
    assert manifest["source_r2_incident_manifest_sha256"] == hashlib.sha256(
        (R2_RUN / "stage_c_incident_manifest.json").read_bytes()
    ).hexdigest()
    assert manifest["formal_timeout_seconds_unchanged"] == 120.0
    assert manifest["preflight_timeout_seconds"] == 300.0
    assert manifest["timeout_occurrences"] == 0
    assert manifest["mean_latency_ms"] >= 0
    assert manifest["median_latency_ms"] >= 0
    assert manifest["max_latency_ms"] >= 0
