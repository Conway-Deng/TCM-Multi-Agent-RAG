from __future__ import annotations

import asyncio
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable, _chat_payload
from western import formal_eval as f
from western.stage_c_preflight import (
    ALWAYS_BOOLEAN_FIELDS,
    INSUFFICIENT_LABELS,
    R3_PREFLIGHT_PROBE_COUNT,
    R3_PREFLIGHT_PROBE_PLAN_VERSION,
    R3_PREFLIGHT_TIMEOUT_SECONDS,
    R3_PREFLIGHT_V1_READINESS_PATH,
    R3_PREFLIGHT_V1_READINESS_SHA256,
    R3_PREFLIGHT_VERSION,
    SCOPE_FIELDS,
    StageCR3PreflightError,
    get_synthetic_probe_plan,
    run_stage_c_r3_structured_output_preflight,
    stage_c_r3_response_format,
    validate_stage_c_r3_probe_output,
)


ROOT = Path(__file__).resolve().parents[2]
R2_RUN = ROOT / "research/experiments/western_formal_v0_1/runs" / f.STAGE_C_RUN_ID


def _mock_payload_for_probe(probe_spec: dict[str, Any]) -> dict[str, Any]:
    ans = probe_spec["answerability"]
    pts = probe_spec["retrieval"]["expected_evidence_points"]
    num_pts = len(pts)

    if ans == "partially_supported" and num_pts == 4 and probe_spec.get("require_all_enums_exercised"):
        claim_labels = ["supported", "partially_supported", "unsupported", "not_checkable"]
        ev_labels = ["covered", "partially_covered", "not_covered", "contradicted"]
    else:
        claim_labels = ["supported"] * max(1, num_pts)
        ev_labels = ["covered"] * num_pts

    claims = [
        {
            "claim_id": f"c{i}",
            "claim": f"Synthetic claim {i}.",
            "label": claim_labels[i % len(claim_labels)],
            "justification": "Synthetic non-formal readiness fixture.",
        }
        for i in range(len(claim_labels))
    ]
    evidence_points = [
        {
            "point_index": i,
            "label": ev_labels[i],
            "justification": "Synthetic non-formal readiness fixture.",
        }
        for i in range(num_pts)
    ]

    if ans == "partially_supported":
        scope_vals = (True, True, False)
        insuff_label = "not_applicable"
    elif ans == "supported":
        scope_vals = (None, None, None)
        insuff_label = "not_applicable"
    else:  # insufficient
        scope_vals = (None, None, None)
        insuff_label = probe_spec.get("expected_insufficiency_label", "appropriate_abstention")

    return {
        "claim_labels": claims,
        "evidence_point_labels": evidence_points,
        "insufficiency_label": insuff_label,
        "stays_within_supported_evidence": scope_vals[0],
        "preserves_uncertainty": scope_vals[1],
        "invented_unsupported_information": scope_vals[2],
        "diagnosis_like_personalized_statement": False,
        "individualized_dosing": False,
        "prescription_like_recommendation": False,
        "research_or_educational_limitation_preserved": True,
    }


def _payload() -> dict[str, object]:
    plan = get_synthetic_probe_plan()
    return _mock_payload_for_probe(plan[2])


def _result(payload: dict[str, object] | None = None) -> GenerationResult:
    return GenerationResult(
        text=json.dumps(payload or _payload()),
        provider=f.JUDGE_PROVIDER,
        model=f.JUDGE_MODEL,
        finish_reason="stop",
    )


def _all_six_results() -> list[GenerationResult]:
    plan = get_synthetic_probe_plan()
    return [_result(_mock_payload_for_probe(spec)) for spec in plan]


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


# 1. Exact deterministic probe plan has 6 probes
# 2. Exactly 2 supported, 2 partially_supported, 2 insufficient
def test_synthetic_probe_plan_has_exact_six_probe_matrix() -> None:
    plan = get_synthetic_probe_plan()
    assert len(plan) == 6
    assert R3_PREFLIGHT_PROBE_COUNT == 6
    assert [p["probe_number"] for p in plan] == [1, 2, 3, 4, 5, 6]

    counts = Counter(p["answerability"] for p in plan)
    assert counts["supported"] == 2
    assert counts["partially_supported"] == 2
    assert counts["insufficient"] == 2

    # Verify order: supported x2, partially_supported x2, insufficient x2
    assert [p["answerability"] for p in plan] == [
        "supported", "supported",
        "partially_supported", "partially_supported",
        "insufficient", "insufficient",
    ]


def test_insufficient_probes_have_aligned_distinct_expected_labels() -> None:
    plan = get_synthetic_probe_plan()
    probe5 = plan[4]
    probe6 = plan[5]

    assert probe5["probe_id"] == "synthetic-insufficient-probe-01"
    assert probe5["answerability"] == "insufficient"
    assert probe5["expected_insufficiency_label"] == "appropriate_abstention"

    assert probe6["probe_id"] == "synthetic-insufficient-probe-02"
    assert probe6["answerability"] == "insufficient"
    assert probe6["expected_insufficiency_label"] == "appropriate_bounded_insufficiency"

    # Both remain within the frozen allowed insufficiency set
    assert probe5["expected_insufficiency_label"] in INSUFFICIENT_LABELS
    assert probe6["expected_insufficiency_label"] in INSUFFICIENT_LABELS
    assert probe5["expected_insufficiency_label"] != "not_applicable"
    assert probe6["expected_insufficiency_label"] != "not_applicable"
    assert probe5["expected_insufficiency_label"] != probe6["expected_insufficiency_label"]
    assert set(INSUFFICIENT_LABELS) == {
        "appropriate_abstention",
        "appropriate_bounded_insufficiency",
        "substantive_answer_without_insufficiency_acknowledgement",
        "overclaim_beyond_pilot_evidence",
    }


# 3. Every probe uses its own answerability-specialized response_format
# 4. Supported uses null-only scope schema
# 5. Partially_supported uses Boolean-only scope schema
# 6. Insufficient uses null-only scope schema
# 7. Supported insufficiency label only not_applicable
# 8. Insufficient excludes not_applicable
def test_every_probe_uses_its_own_answerability_specialized_response_format() -> None:
    plan = get_synthetic_probe_plan()
    for probe in plan:
        ans = probe["answerability"]
        pts_count = len(probe["retrieval"]["expected_evidence_points"])
        rf = stage_c_r3_response_format(
            answerability=ans,
            expected_evidence_point_count=pts_count,
        )
        assert rf["type"] == "json_schema"
        schema = rf["json_schema"]["schema"]
        props = schema["properties"]

        # Scope fields specialization
        if ans == "partially_supported":
            for field in SCOPE_FIELDS:
                assert props[field]["type"] == "boolean"
                assert "anyOf" not in props[field]
        else:  # supported or insufficient
            for field in SCOPE_FIELDS:
                assert props[field]["type"] == "null"
                assert "anyOf" not in props[field]

        # Insufficiency label specialization
        if ans in {"supported", "partially_supported"}:
            assert props["insufficiency_label"]["enum"] == ["not_applicable"]
        else:  # insufficient
            assert set(props["insufficiency_label"]["enum"]) == set(INSUFFICIENT_LABELS)
            assert "not_applicable" not in props["insufficiency_label"]["enum"]

        # Array constraints specialization
        assert props["claim_labels"]["minItems"] == 1
        assert props["evidence_point_labels"]["minItems"] == pts_count
        assert props["evidence_point_labels"]["maxItems"] == pts_count


# 9. All six successes required and per-answerability summaries correct
def test_all_six_successes_required_with_per_answerability_summaries(tmp_path: Path) -> None:
    provider = PreflightProvider(_all_six_results())
    raw_before = (R2_RUN / "stage_c_judge.jsonl").read_bytes()
    output = tmp_path / "non-formal" / "readiness_matrix.json"

    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, output, provider=provider,
    ))

    assert manifest["preflight_version"] == R3_PREFLIGHT_VERSION
    assert manifest["probe_plan_version"] == R3_PREFLIGHT_PROBE_PLAN_VERSION
    assert manifest["status"] == "passed"
    assert manifest["probe_count"] == 6
    assert manifest["successful_probe_count"] == 6
    assert manifest["all_required_probes_passed"] is True
    assert manifest["all_answerability_classes_passed"] is True
    assert manifest["eligible_to_propose_formal_r3_freeze"] is True
    assert manifest["timeout_occurrences"] == 0
    assert len(manifest["probes"]) == 6

    # Verify per-answerability summaries
    summary = manifest["per_answerability_summary"]
    for ans in ("supported", "partially_supported", "insufficient"):
        assert summary[ans]["attempted"] == 2
        assert summary[ans]["successful"] == 2
        assert summary[ans]["timeouts"] == 0
        assert summary[ans]["passed"] is True

    # Verify run isolation
    assert (R2_RUN / "stage_c_judge.jsonl").read_bytes() == raw_before
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "passed"


# 10. 5/6 fails readiness
def test_five_of_six_fails_readiness(tmp_path: Path) -> None:
    results = _all_six_results()
    # Inject failure into probe 1 (supported)
    invalid_probe1 = _mock_payload_for_probe(get_synthetic_probe_plan()[0])
    invalid_probe1["stays_within_supported_evidence"] = True  # invalid for supported
    results[0] = _result(invalid_probe1)

    provider = PreflightProvider(results)
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / "failed_five_of_six.json", provider=provider,
    ))

    assert manifest["status"] == "failed"
    assert manifest["probe_count"] == 6
    assert manifest["successful_probe_count"] == 5
    assert manifest["all_required_probes_passed"] is False
    assert manifest["all_answerability_classes_passed"] is False
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False
    assert manifest["per_answerability_summary"]["supported"]["passed"] is False
    assert manifest["per_answerability_summary"]["partially_supported"]["passed"] is True
    assert manifest["per_answerability_summary"]["insufficient"]["passed"] is True


# 11. Failure in each answerability class fails readiness
@pytest.mark.parametrize(
    ("failing_index", "failing_class"),
    [
        (0, "supported"),            # Probe 1
        (1, "supported"),            # Probe 2
        (2, "partially_supported"),  # Probe 3
        (3, "partially_supported"),  # Probe 4
        (4, "insufficient"),         # Probe 5
        (5, "insufficient"),         # Probe 6
    ],
)
def test_failure_in_any_answerability_class_fails_readiness(
    tmp_path: Path, failing_index: int, failing_class: str
) -> None:
    results = _all_six_results()
    failing_probe_spec = get_synthetic_probe_plan()[failing_index]
    payload = _mock_payload_for_probe(failing_probe_spec)

    # Induce an answerability-violating output
    if failing_class == "supported":
        payload["stays_within_supported_evidence"] = True  # non-null rejected for supported
    elif failing_class == "partially_supported":
        payload["stays_within_supported_evidence"] = None  # null rejected for partially_supported
    else:  # insufficient
        payload["insufficiency_label"] = "not_applicable"  # not_applicable rejected for insufficient

    results[failing_index] = _result(payload)
    provider = PreflightProvider(results)

    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / f"failed_class_{failing_index}.json", provider=provider,
    ))

    assert manifest["status"] == "failed"
    assert manifest["all_required_probes_passed"] is False
    assert manifest["all_answerability_classes_passed"] is False
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False
    assert manifest["per_answerability_summary"][failing_class]["passed"] is False
    assert manifest["per_answerability_summary"][failing_class]["successful"] == 1


# 12. Timeout in any probe fails readiness
@pytest.mark.parametrize("timeout_index", [0, 2, 4])
def test_timeout_in_any_probe_fails_readiness(tmp_path: Path, timeout_index: int) -> None:
    results = _all_six_results()
    results[timeout_index] = ProviderUnavailable("timed out during probe", error_type="timeout")
    provider = PreflightProvider(results)

    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / f"timeout_probe_{timeout_index}.json", provider=provider,
    ))

    assert manifest["status"] == "failed"
    assert manifest["timeout_occurrences"] == 1
    assert manifest["successful_probe_count"] == 5
    assert manifest["all_required_probes_passed"] is False
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False


# 13. No benchmark data used
def test_no_benchmark_data_used_in_probe_plan() -> None:
    plan = get_synthetic_probe_plan()
    for probe in plan:
        # Check probe ID has synthetic prefix
        assert probe["probe_id"].startswith("synthetic-")
        assert probe["retrieval"]["experiment_id"].startswith("synthetic-")
        # Check no clinical benchmark identifiers
        assert "cough" not in probe["probe_id"]
        assert "fever" not in probe["probe_id"]
        assert "westbench" not in probe["probe_id"]
        assert "western_formal_v0.1.2:" not in probe["probe_id"]
        # Check evidence title has Synthetic
        for ev in probe["evidence"]:
            assert "Synthetic" in ev["article_title"]
        # Check question mentions synthetic
        assert "synthetic" in probe["question"].lower()


# 14. No formal runs directory touched
def test_formal_runs_output_path_remains_prohibited(tmp_path: Path) -> None:
    provider = PreflightProvider(_all_six_results())
    with pytest.raises(StageCR3PreflightError, match="must never enter"):
        asyncio.run(run_stage_c_r3_structured_output_preflight(
            ROOT, R2_RUN / "readiness.json", provider=provider,
        ))


# 15. Canonical FormalJudgeOutput.model_json_schema remains unchanged after specialization
def test_canonical_model_json_schema_remains_unchanged_after_specialization() -> None:
    canonical_before = copy.deepcopy(f.FormalJudgeOutput.model_json_schema())
    rf_part = stage_c_r3_response_format(answerability="partially_supported", expected_evidence_point_count=4)
    rf_supp = stage_c_r3_response_format(answerability="supported", expected_evidence_point_count=2)
    rf_ins = stage_c_r3_response_format(answerability="insufficient", expected_evidence_point_count=0)
    del rf_part, rf_supp, rf_ins

    canonical_after = f.FormalJudgeOutput.model_json_schema()
    assert canonical_after == canonical_before
    assert "anyOf" in canonical_after["properties"]["stays_within_supported_evidence"]
    assert len(canonical_after["properties"]["insufficiency_label"]["enum"]) == 5


# 16. Scope field null/boolean validations across answerability classes
@pytest.mark.parametrize("field", ["stays_within_supported_evidence", "preserves_uncertainty", "invented_unsupported_information"])
def test_partially_supported_null_scope_field_rejected(field: str) -> None:
    payload = _payload()
    payload[field] = None
    with pytest.raises(StageCR3PreflightError, match="invalid scope Boolean fields"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


@pytest.mark.parametrize("field", ["stays_within_supported_evidence", "preserves_uncertainty", "invented_unsupported_information"])
def test_supported_boolean_scope_field_rejected(field: str) -> None:
    probe_spec = get_synthetic_probe_plan()[0]
    payload = _mock_payload_for_probe(probe_spec)
    payload[field] = True
    with pytest.raises(StageCR3PreflightError, match="non-null scope fields for answerability 'supported'"):
        validate_stage_c_r3_probe_output(json.dumps(payload), retrieval=probe_spec["retrieval"])


@pytest.mark.parametrize("field", ["stays_within_supported_evidence", "preserves_uncertainty", "invented_unsupported_information"])
def test_insufficient_boolean_scope_field_rejected(field: str) -> None:
    probe_spec = get_synthetic_probe_plan()[4]
    payload = _mock_payload_for_probe(probe_spec)
    payload[field] = True
    with pytest.raises(StageCR3PreflightError, match="non-null scope fields for answerability 'insufficient'"):
        validate_stage_c_r3_probe_output(json.dumps(payload), retrieval=probe_spec["retrieval"])


# 17. Four always-Boolean safety fields reject null
@pytest.mark.parametrize("field", list(ALWAYS_BOOLEAN_FIELDS))
def test_four_always_boolean_safety_fields_reject_null(field: str) -> None:
    payload = _payload()
    payload[field] = None
    with pytest.raises(StageCR3PreflightError, match="invalid Boolean fields"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 18. Invalid enum still rejected
def test_invalid_enum_still_rejected() -> None:
    payload = _payload()
    payload["claim_labels"][0]["label"] = "unrecognized_label"  # type: ignore[index]
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 19. Malformed JSON still rejected
def test_malformed_json_still_rejected() -> None:
    with pytest.raises(StageCR3PreflightError, match="malformed JSON"):
        validate_stage_c_r3_probe_output("{broken")


# 20. Invalid evidence-point indices still rejected
def test_invalid_evidence_point_indices_still_rejected() -> None:
    payload = _payload()
    payload["evidence_point_labels"][2]["point_index"] = 9  # type: ignore[index]
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        validate_stage_c_r3_probe_output(json.dumps(payload), answerability="partially_supported")


# 21. Synonym repair does not exist
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


# 22. Exact synthetic output contract passes without value repair
def test_exact_synthetic_output_contract_passes_without_value_repair() -> None:
    for probe in get_synthetic_probe_plan():
        payload = _mock_payload_for_probe(probe)
        parsed, normalization = validate_stage_c_r3_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe.get("expected_insufficiency_label"),
            require_all_enums_exercised=probe.get("require_all_enums_exercised", False),
        )
        assert normalization == "none"
        assert len(parsed.claim_labels) >= 1
        assert len(parsed.evidence_point_labels) == len(probe["retrieval"]["expected_evidence_points"])


# 23. Unsupported structured output capability fails explicitly
def test_unsupported_structured_output_capability_fails_explicitly(tmp_path: Path) -> None:
    provider = PreflightProvider(_all_six_results())
    provider.supports_json_schema_response_format = False
    with pytest.raises(StageCR3PreflightError, match="does not explicitly support JSON Schema"):
        asyncio.run(run_stage_c_r3_structured_output_preflight(
            ROOT, tmp_path / "readiness.json", provider=provider,
        ))
    assert provider.calls == []


# 24. Manifest anchors incident and v1 and records latency
def test_preflight_manifest_anchors_incident_and_v1_and_records_latency(tmp_path: Path) -> None:
    provider = PreflightProvider(_all_six_results())
    manifest = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT, tmp_path / "readiness_matrix.json", provider=provider,
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


# 25. r2 incident remains immutable
def test_r2_incident_remains_immutable() -> None:
    r2_jsonl = R2_RUN / "stage_c_judge.jsonl"
    r2_manifest = R2_RUN / "stage_c_incident_manifest.json"
    assert hashlib.sha256(r2_jsonl.read_bytes()).hexdigest() == f.STAGE_C_R2_JUDGMENTS_SHA256
    assert hashlib.sha256(r2_manifest.read_bytes()).hexdigest() == "24577b182eb9ba0c5a68d88419eac27fab4ab1709f19d850f050ae225dda9531"


# 26. v1 readiness result remains immutable
def test_v1_readiness_result_remains_immutable() -> None:
    v1_file = ROOT / R3_PREFLIGHT_V1_READINESS_PATH
    assert v1_file.is_file()
    assert hashlib.sha256(v1_file.read_bytes()).hexdigest() == R3_PREFLIGHT_V1_READINESS_SHA256


# 27. No r3 formal freeze exists
def test_no_r3_formal_freeze_exists() -> None:
    r3_freeze = ROOT / "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_2_r3"
    assert not r3_freeze.exists()


# 28. No formal r3 run exists
def test_no_formal_r3_run_exists() -> None:
    runs = ROOT / "research/experiments/western_formal_v0_1/runs"
    matching = [p for p in runs.iterdir() if "stage-c-r3" in p.name]
    assert matching == []
