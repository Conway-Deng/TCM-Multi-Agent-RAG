from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable, _chat_payload
from western import formal_eval as f
from western.stage_c_preflight import (
    ALWAYS_BOOLEAN_FIELDS,
    INSUFFICIENT_LABELS,
    R3_PREFLIGHT_TIMEOUT_SECONDS,
    R3_PREFLIGHT_V1_READINESS_PATH,
    R3_PREFLIGHT_V1_READINESS_SHA256,
    R3_PREFLIGHT_VERSION,
    SCOPE_FIELDS,
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


# 1. canonical FormalJudgeOutput.model_json_schema remains unchanged after specialization
def test_canonical_model_json_schema_remains_unchanged_after_specialization() -> None:
    canonical_before = copy.deepcopy(f.FormalJudgeOutput.model_json_schema())
    rf_part = stage_c_r3_response_format(answerability="partially_supported", expected_evidence_point_count=4)
    rf_supp = stage_c_r3_response_format(answerability="supported", expected_evidence_point_count=2)
    rf_ins = stage_c_r3_response_format(answerability="insufficient", expected_evidence_point_count=0)
    del rf_part, rf_supp, rf_ins

    canonical_after = f.FormalJudgeOutput.model_json_schema()
    assert canonical_after == canonical_before
    # Check that canonical schema still allows anyOf (boolean | null) for scope fields
    assert "anyOf" in canonical_after["properties"]["stays_within_supported_evidence"]
    # Check that canonical insufficiency_label has all 5 labels
    assert len(canonical_after["properties"]["insufficiency_label"]["enum"]) == 5


# 2. partially_supported schema: all three scope fields Boolean-only
def test_partially_supported_schema_all_three_scope_fields_boolean_only() -> None:
    rf = stage_c_r3_response_format(answerability="partially_supported", expected_evidence_point_count=4)
    props = rf["json_schema"]["schema"]["properties"]
    for field in SCOPE_FIELDS:
        assert props[field]["type"] == "boolean"
        assert "anyOf" not in props[field]


# 3. supported schema: all three scope fields null-only
def test_supported_schema_all_three_scope_fields_null_only() -> None:
    rf = stage_c_r3_response_format(answerability="supported", expected_evidence_point_count=2)
    props = rf["json_schema"]["schema"]["properties"]
    for field in SCOPE_FIELDS:
        assert props[field]["type"] == "null"
        assert "anyOf" not in props[field]


# 4. insufficient schema: all three scope fields null-only
def test_insufficient_schema_all_three_scope_fields_null_only() -> None:
    rf = stage_c_r3_response_format(answerability="insufficient", expected_evidence_point_count=3)
    props = rf["json_schema"]["schema"]["properties"]
    for field in SCOPE_FIELDS:
        assert props[field]["type"] == "null"
        assert "anyOf" not in props[field]


# 5. supported insufficiency_label: only not_applicable
def test_supported_insufficiency_label_only_not_applicable() -> None:
    rf = stage_c_r3_response_format(answerability="supported", expected_evidence_point_count=2)
    assert rf["json_schema"]["schema"]["properties"]["insufficiency_label"]["enum"] == ["not_applicable"]


# 6. partially_supported insufficiency_label: only not_applicable
def test_partially_supported_insufficiency_label_only_not_applicable() -> None:
    rf = stage_c_r3_response_format(answerability="partially_supported", expected_evidence_point_count=4)
    assert rf["json_schema"]["schema"]["properties"]["insufficiency_label"]["enum"] == ["not_applicable"]


# 7. insufficient insufficiency_label: exactly the four frozen allowed successful outcomes and excludes not_applicable
def test_insufficient_insufficiency_label_exactly_four_frozen_outcomes_excludes_not_applicable() -> None:
    rf = stage_c_r3_response_format(answerability="insufficient", expected_evidence_point_count=4)
    enum_vals = rf["json_schema"]["schema"]["properties"]["insufficiency_label"]["enum"]
    assert set(enum_vals) == set(INSUFFICIENT_LABELS)
    assert "not_applicable" not in enum_vals


# 8. evidence_point_labels: minItems and maxItems exactly equal expected point count
@pytest.mark.parametrize("count", [0, 1, 4, 7])
def test_evidence_point_labels_min_max_items_match_expected_count(count: int) -> None:
    rf = stage_c_r3_response_format(answerability="partially_supported", expected_evidence_point_count=count)
    props = rf["json_schema"]["schema"]["properties"]["evidence_point_labels"]
    assert props["minItems"] == count
    assert props["maxItems"] == count


# 9. claim_labels: minItems = 1
@pytest.mark.parametrize("ans", ["partially_supported", "supported", "insufficient"])
def test_claim_labels_min_items_equals_one(ans: str) -> None:
    rf = stage_c_r3_response_format(answerability=ans, expected_evidence_point_count=4)
    assert rf["json_schema"]["schema"]["properties"]["claim_labels"]["minItems"] == 1


# 10. partially_supported null scope field rejected
@pytest.mark.parametrize("field", ["stays_within_supported_evidence", "preserves_uncertainty", "invented_unsupported_information"])
def test_partially_supported_null_scope_field_rejected(field: str) -> None:
    payload = _payload()
    payload[field] = None
    with pytest.raises(StageCR3PreflightError, match="invalid scope Boolean fields"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 11. supported Boolean scope field rejected
@pytest.mark.parametrize("field", ["stays_within_supported_evidence", "preserves_uncertainty", "invented_unsupported_information"])
def test_supported_boolean_scope_field_rejected(field: str) -> None:
    payload = _payload()
    payload["stays_within_supported_evidence"] = None
    payload["preserves_uncertainty"] = None
    payload["invented_unsupported_information"] = None
    payload[field] = True
    with pytest.raises(StageCR3PreflightError, match="non-null scope fields for answerability 'supported'"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="supported")


# 12. insufficient Boolean scope field rejected
@pytest.mark.parametrize("field", ["stays_within_supported_evidence", "preserves_uncertainty", "invented_unsupported_information"])
def test_insufficient_boolean_scope_field_rejected(field: str) -> None:
    payload = _payload()
    payload["stays_within_supported_evidence"] = None
    payload["preserves_uncertainty"] = None
    payload["invented_unsupported_information"] = None
    payload["insufficiency_label"] = "appropriate_abstention"
    payload[field] = True
    with pytest.raises(StageCR3PreflightError, match="non-null scope fields for answerability 'insufficient'"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="insufficient")


# 13. four always-Boolean safety fields reject null
@pytest.mark.parametrize("field", list(ALWAYS_BOOLEAN_FIELDS))
def test_four_always_boolean_safety_fields_reject_null(field: str) -> None:
    payload = _payload()
    payload[field] = None
    with pytest.raises(StageCR3PreflightError, match="invalid Boolean fields"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 14. invalid enum still rejected
def test_invalid_enum_still_rejected() -> None:
    payload = _payload()
    payload["claim_labels"][0]["label"] = "unrecognized_label"  # type: ignore[index]
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 15. malformed JSON still rejected
def test_malformed_json_still_rejected() -> None:
    with pytest.raises(StageCR3PreflightError, match="malformed JSON"):
        validate_stage_c_r3_probe_output("{broken")


# 16. invalid evidence-point indices still rejected
def test_invalid_evidence_point_indices_still_rejected() -> None:
    payload = _payload()
    payload["evidence_point_labels"][2]["point_index"] = 9  # type: ignore[index]
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 17. synonym repair does not exist
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("claim", "exactly supported"),
        ("claim", "partially supported"),
        ("evidence", "exactly covered"),
        ("evidence", "not covered"),
        ("evidence", "partially covered"),
    ],
)
def test_synonym_repair_does_not_exist(field: str, value: str) -> None:
    payload = _payload()
    if field == "claim":
        payload["claim_labels"][0]["label"] = value  # type: ignore[index]
    else:
        payload["evidence_point_labels"][0]["label"] = value  # type: ignore[index]
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 18. 3/3 gate remains required
def test_three_of_three_gate_remains_required(tmp_path: Path) -> None:
    provider = PreflightProvider([_result()] * 3)
    with pytest.raises(StageCR3PreflightError, match="At least three"):
        asyncio.run(run_stage_c_r3_structured_output_preflight(
            ROOT, tmp_path / "too-few.json", provider=provider, probe_count=2,
        ))


# 19. one failed probe makes readiness fail
def test_one_failed_probe_makes_readiness_fail(tmp_path: Path) -> None:
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


# 20. timeout makes readiness fail
def test_timeout_makes_readiness_fail(tmp_path: Path) -> None:
    provider = PreflightProvider([
        _result(), ProviderUnavailable("timed out", error_type="timeout"), _result(),
    ])
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / "timeout-readiness.json", provider=provider,
    ))
    assert manifest["status"] == "failed"
    assert manifest["timeout_occurrences"] == 1
    assert manifest["successful_probe_count"] == 2
    assert manifest["all_required_probes_passed"] is False


# 21. formal runs output path remains prohibited
def test_formal_runs_output_path_remains_prohibited(tmp_path: Path) -> None:
    provider = PreflightProvider([_result()] * 3)
    with pytest.raises(StageCR3PreflightError, match="must never enter"):
        asyncio.run(run_stage_c_r3_structured_output_preflight(
            ROOT, R2_RUN / "readiness.json", provider=provider,
        ))


# 22. r2 incident remains immutable
def test_r2_incident_remains_immutable() -> None:
    r2_jsonl = R2_RUN / "stage_c_judge.jsonl"
    r2_manifest = R2_RUN / "stage_c_incident_manifest.json"
    assert hashlib.sha256(r2_jsonl.read_bytes()).hexdigest() == f.STAGE_C_R2_JUDGMENTS_SHA256
    assert hashlib.sha256(r2_manifest.read_bytes()).hexdigest() == "24577b182eb9ba0c5a68d88419eac27fab4ab1709f19d850f050ae225dda9531"


# 23. v1 readiness result remains immutable
def test_v1_readiness_result_remains_immutable() -> None:
    v1_file = ROOT / R3_PREFLIGHT_V1_READINESS_PATH
    assert v1_file.is_file()
    assert hashlib.sha256(v1_file.read_bytes()).hexdigest() == R3_PREFLIGHT_V1_READINESS_SHA256


# 24. no r3 formal freeze exists
def test_no_r3_formal_freeze_exists() -> None:
    r3_freeze = ROOT / "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_2_r3"
    assert not r3_freeze.exists()


# 25. no formal r3 run exists
def test_no_formal_r3_run_exists() -> None:
    runs = ROOT / "research/experiments/western_formal_v0_1/runs"
    matching = [p for p in runs.iterdir() if "stage-c-r3" in p.name]
    assert matching == []


def test_exact_synthetic_output_contract_passes_without_value_repair() -> None:
    parsed, normalization = validate_stage_c_r3_probe_output(json.dumps(_payload()))
    assert normalization == "none"
    assert {item.label for item in parsed.claim_labels} == {
        "supported", "partially_supported", "unsupported", "not_checkable",
    }
    assert {item.label for item in parsed.evidence_point_labels} == {
        "covered", "partially_covered", "not_covered", "contradicted",
    }


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
    output = tmp_path / "non-formal" / "readiness_v2.json"
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, output, provider=provider,
    ))
    assert manifest["preflight_version"] == R3_PREFLIGHT_VERSION
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


def test_preflight_manifest_anchors_incident_and_v1_and_records_latency(tmp_path: Path) -> None:
    provider = PreflightProvider([_result()] * 3)
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / "readiness_v2.json", provider=provider,
    ))
    assert manifest["source_r2_incident_manifest_sha256"] == hashlib.sha256(
        (R2_RUN / "stage_c_incident_manifest.json").read_bytes()
    ).hexdigest()
    assert manifest["source_r3_preflight_v1_readiness_sha256"] == R3_PREFLIGHT_V1_READINESS_SHA256
    assert manifest["prior_preflight_v1_observed_latency"]["timeouts"] == 0
    assert manifest["formal_timeout_seconds_unchanged"] == 120.0
    assert manifest["preflight_timeout_seconds"] == 300.0
    assert manifest["timeout_occurrences"] == 0
    assert manifest["mean_latency_ms"] >= 0
    assert manifest["median_latency_ms"] >= 0
    assert manifest["max_latency_ms"] >= 0
