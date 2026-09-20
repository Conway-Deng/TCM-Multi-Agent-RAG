from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import OpenAICompatibleLLMProvider, ProviderUnavailable, _chat_payload
from western import formal_eval as f
from western import stage_c_preflight_v3 as v3
from western.formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT, build_judge_prompt
from western.stage_c_preflight import (
    INSUFFICIENT_LABELS,
    R3_PREFLIGHT_PROBE_COUNT,
    SCOPE_FIELDS,
    StageCR3PreflightError,
    get_synthetic_probe_plan,
)


ROOT = Path(__file__).resolve().parents[2]
R2_RUN = ROOT / "research/experiments/western_formal_v0_1/runs" / f.STAGE_C_RUN_ID
V1_READINESS = ROOT / "research/experiments/western_formal_v0_1/stage_c_r3_preflight_readiness.json"
V2_READINESS = ROOT / v3.R3_PREFLIGHT_V2_READINESS_PATH
SYSTEM_PROMPT_SHA256 = "b5c5b71ae89871d9854a806ea7f413caec36cba98aa74f396ff2224dfd0c5226"
CANONICAL_SCHEMA_SHA256 = "2f33277a2e6292ad1c02fff423b6f0aa226b1da03bbb96da9b648bb1625e1d7a"
HISTORICAL_PROMPT_SHA256 = "8f6f994246a445f4be754986d3d4d73c52213b604a6729b4f304cd985a0cb566"


def _schema_sha256() -> str:
    encoded = json.dumps(
        FormalJudgeOutput.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mock_payload(probe: dict[str, Any]) -> dict[str, Any]:
    answerability = probe["answerability"]
    count = len(probe["retrieval"]["expected_evidence_points"])
    if answerability == "partially_supported" and probe.get("require_all_enums_exercised"):
        claim_labels = ["supported", "partially_supported", "unsupported", "not_checkable"]
        evidence_labels = ["covered", "partially_covered", "not_covered", "contradicted"]
    else:
        claim_labels = ["supported"] * max(1, count)
        evidence_labels = ["covered"] * count
    if answerability == "partially_supported":
        scope = (True, True, False)
    else:
        scope = (None, None, None)
    insufficiency = (
        probe.get("expected_insufficiency_label", "appropriate_abstention")
        if answerability == "insufficient"
        else "not_applicable"
    )
    return {
        "claim_labels": [
            {
                "claim_id": f"c{index}",
                "claim": f"Synthetic claim {index}.",
                "label": label,
                "justification": "Synthetic fixture justification.",
            }
            for index, label in enumerate(claim_labels)
        ],
        "evidence_point_labels": [
            {
                "point_index": index,
                "label": label,
                "justification": "Synthetic fixture justification.",
            }
            for index, label in enumerate(evidence_labels)
        ],
        "insufficiency_label": insufficiency,
        "stays_within_supported_evidence": scope[0],
        "preserves_uncertainty": scope[1],
        "invented_unsupported_information": scope[2],
        "diagnosis_like_personalized_statement": False,
        "individualized_dosing": False,
        "prescription_like_recommendation": False,
        "research_or_educational_limitation_preserved": True,
    }


def _result(probe: dict[str, Any], payload: dict[str, Any] | None = None) -> GenerationResult:
    return GenerationResult(
        text=json.dumps(payload if payload is not None else _mock_payload(probe)),
        provider=f.JUDGE_PROVIDER,
        model=f.JUDGE_MODEL,
        finish_reason="stop",
    )


def _all_results() -> list[GenerationResult]:
    return [_result(probe) for probe in get_synthetic_probe_plan()]


class JsonModeProvider:
    name = f.JUDGE_PROVIDER
    model = f.JUDGE_MODEL
    timeout = v3.R3_PREFLIGHT_TIMEOUT_SECONDS
    max_tokens = f.JUDGE_MAX_TOKENS
    enable_thinking = False
    supports_response_format = True
    supports_json_object_response_format = True

    def __init__(self, results: list[GenerationResult | Exception]) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> GenerationResult:
        self.calls.append(kwargs)
        outcome = self.results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _run(tmp_path: Path, provider: JsonModeProvider) -> dict[str, Any]:
    return asyncio.run(v3.run_stage_c_r3_json_mode_preflight_v3(
        ROOT,
        tmp_path / "stage_c_r3_preflight_readiness_v3.json",
        provider=provider,
    ))


def test_json_mode_transport_is_exact_and_has_no_json_schema(tmp_path: Path) -> None:
    provider = JsonModeProvider(_all_results())
    manifest = _run(tmp_path, provider)
    assert manifest["response_format"] == {"type": "json_object"}
    assert len(provider.calls) == 6
    for call in provider.calls:
        assert call["response_format"] == {"type": "json_object"}
        assert set(call["response_format"]) == {"type"}
        assert "json_schema" not in call["response_format"]
    payload = _chat_payload(
        model=f.JUDGE_MODEL,
        system="system",
        prompt="prompt",
        temperature=0.0,
        max_tokens=1200,
        frequency_penalty=0.0,
        response_format={"type": "json_object"},
    )
    assert payload["response_format"] == {"type": "json_object"}
    assert OpenAICompatibleLLMProvider.supports_json_object_response_format is True


def test_six_probe_matrix_and_order_are_preserved() -> None:
    plan = get_synthetic_probe_plan()
    assert len(plan) == R3_PREFLIGHT_PROBE_COUNT == 6
    assert [probe["probe_number"] for probe in plan] == [1, 2, 3, 4, 5, 6]
    assert [probe["answerability"] for probe in plan] == [
        "supported",
        "supported",
        "partially_supported",
        "partially_supported",
        "insufficient",
        "insufficient",
    ]
    assert plan[4]["expected_insufficiency_label"] == "appropriate_abstention"
    assert plan[5]["expected_insufficiency_label"] == "appropriate_bounded_insufficiency"


def test_each_prompt_has_case_specific_schema_and_exact_point_contract() -> None:
    canonical_before = copy.deepcopy(FormalJudgeOutput.model_json_schema())
    for probe in get_synthetic_probe_plan():
        retrieval = probe["retrieval"]
        expected_points = retrieval["expected_evidence_points"]
        prompt = json.loads(v3.build_stage_c_r3_json_mode_prompt(
            question=probe["question"],
            answer=probe["answer"],
            retrieved_evidence=probe["evidence"],
            expected_evidence_points=expected_points,
            answerability=probe["answerability"],
        ))
        schema = prompt["required_output_schema"]
        properties = schema["properties"]
        if probe["answerability"] == "partially_supported":
            assert all(properties[field]["type"] == "boolean" for field in SCOPE_FIELDS)
        else:
            assert all(properties[field]["type"] == "null" for field in SCOPE_FIELDS)
        if probe["answerability"] == "insufficient":
            assert "not_applicable" not in properties["insufficiency_label"]["enum"]
            assert set(properties["insufficiency_label"]["enum"]) == set(INSUFFICIENT_LABELS)
        else:
            assert properties["insufficiency_label"]["enum"] == ["not_applicable"]
        assert properties["claim_labels"]["minItems"] == 1
        evidence = properties["evidence_point_labels"]
        assert evidence["minItems"] == len(expected_points)
        assert evidence["maxItems"] == len(expected_points)
        assert evidence["items"] is False
        assert [
            item["allOf"][1]["properties"]["point_index"]["const"]
            for item in evidence["prefixItems"]
        ] == list(range(len(expected_points)))
    assert FormalJudgeOutput.model_json_schema() == canonical_before


def test_historical_prompt_canonical_schema_and_system_prompt_are_unchanged() -> None:
    historical = build_judge_prompt(
        question="q",
        answer="a",
        retrieved_evidence=[{
            "rank": 1,
            "article_title": "t",
            "section": "s",
            "evidence_excerpt": "e",
        }],
        expected_evidence_points=["p"],
        answerability="supported",
    )
    assert hashlib.sha256(historical.encode("utf-8")).hexdigest() == HISTORICAL_PROMPT_SHA256
    assert hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest() == SYSTEM_PROMPT_SHA256
    assert _schema_sha256() == CANONICAL_SCHEMA_SHA256
    assert "anyOf" in FormalJudgeOutput.model_json_schema()["properties"]["stays_within_supported_evidence"]


def test_strict_validator_accepts_exact_six_fixture_outputs() -> None:
    for probe in get_synthetic_probe_plan():
        parsed, normalization = v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(_mock_payload(probe)),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe.get("expected_insufficiency_label"),
            require_all_enums_exercised=probe.get("require_all_enums_exercised", False),
        )
        assert normalization == "none"
        assert len(parsed.claim_labels) >= 1


def test_malformed_json_fails_without_repair() -> None:
    probe = get_synthetic_probe_plan()[0]
    with pytest.raises(StageCR3PreflightError, match="malformed JSON"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            "{broken",
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=False,
        )


@pytest.mark.parametrize("value", ["exactly supported", "partially supported"])
def test_claim_synonyms_fail_without_repair(value: str) -> None:
    probe = get_synthetic_probe_plan()[0]
    payload = _mock_payload(probe)
    payload["claim_labels"][0]["label"] = value
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=False,
        )


@pytest.mark.parametrize("value", ["exactly covered", "not covered", "partially covered"])
def test_evidence_synonyms_fail_without_repair(value: str) -> None:
    probe = get_synthetic_probe_plan()[0]
    payload = _mock_payload(probe)
    payload["evidence_point_labels"][0]["label"] = value
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=False,
        )


@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_partial_scope_coercions_fail(value: Any) -> None:
    probe = get_synthetic_probe_plan()[2]
    payload = _mock_payload(probe)
    payload["stays_within_supported_evidence"] = value
    with pytest.raises(StageCR3PreflightError, match="raw scope Boolean"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=probe["require_all_enums_exercised"],
        )


def test_always_boolean_coercion_fails() -> None:
    probe = get_synthetic_probe_plan()[0]
    payload = _mock_payload(probe)
    payload["individualized_dosing"] = 0
    with pytest.raises(StageCR3PreflightError, match="raw Boolean"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=False,
        )


def test_point_index_string_coercion_fails() -> None:
    probe = get_synthetic_probe_plan()[0]
    payload = _mock_payload(probe)
    payload["evidence_point_labels"][0]["point_index"] = "0"
    with pytest.raises(StageCR3PreflightError, match="raw integer"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=False,
        )


def test_wrong_point_index_order_fails() -> None:
    probe = get_synthetic_probe_plan()[0]
    payload = _mock_payload(probe)
    payload["evidence_point_labels"][0]["point_index"] = 1
    with pytest.raises(StageCR3PreflightError, match="frozen schema"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=False,
        )


def test_wrong_fixture_insufficiency_label_fails() -> None:
    probe = get_synthetic_probe_plan()[4]
    payload = _mock_payload(probe)
    payload["insufficiency_label"] = "appropriate_bounded_insufficiency"
    with pytest.raises(StageCR3PreflightError, match="expected insufficiency_label"):
        v3.validate_stage_c_r3_json_mode_probe_output(
            json.dumps(payload),
            retrieval=probe["retrieval"],
            expected_insufficiency_label=probe["expected_insufficiency_label"],
            require_all_enums_exercised=False,
        )


def test_six_of_six_contract_and_timeout_compatibility_are_required(tmp_path: Path) -> None:
    manifest = _run(tmp_path, JsonModeProvider(_all_results()))
    assert manifest["status"] == "passed"
    assert manifest["successful_probe_count"] == 6
    assert manifest["json_contract_passed"] is True
    assert manifest["formal_timeout_compatible"] is True
    assert manifest["eligible_to_propose_formal_r3_freeze"] is True
    assert manifest["formal_r3_frozen"] is False
    assert all(item["json_contract_passed"] for item in manifest["per_answerability_summary"].values())


def test_five_of_six_fails_readiness(tmp_path: Path) -> None:
    plan = get_synthetic_probe_plan()
    results = _all_results()
    invalid = _mock_payload(plan[0])
    invalid["stays_within_supported_evidence"] = True
    results[0] = _result(plan[0], invalid)
    manifest = _run(tmp_path, JsonModeProvider(results))
    assert manifest["successful_probe_count"] == 5
    assert manifest["json_contract_passed"] is False
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False


@pytest.mark.parametrize("index", [0, 2, 4])
def test_failure_in_any_answerability_class_fails(tmp_path: Path, index: int) -> None:
    plan = get_synthetic_probe_plan()
    results = _all_results()
    invalid = _mock_payload(plan[index])
    invalid["claim_labels"][0]["label"] = "invalid"
    results[index] = _result(plan[index], invalid)
    manifest = _run(tmp_path, JsonModeProvider(results))
    failing_class = plan[index]["answerability"]
    assert manifest["per_answerability_summary"][failing_class]["json_contract_passed"] is False
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False


def test_timeout_is_recorded_and_fails_both_gates(tmp_path: Path) -> None:
    results: list[GenerationResult | Exception] = list(_all_results())
    results[5] = ProviderUnavailable("synthetic timeout", error_type="timeout")
    manifest = _run(tmp_path, JsonModeProvider(results))
    assert manifest["timeout_occurrences"] == 1
    assert manifest["probes"][5]["error_type"] == "timeout"
    assert manifest["json_contract_passed"] is False
    assert manifest["formal_timeout_compatible"] is False
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False


def test_slow_contract_success_does_not_authorize_120_second_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    times = iter([
        0.0, 121.0,
        122.0, 123.0,
        124.0, 125.0,
        126.0, 127.0,
        128.0, 129.0,
        130.0, 131.0,
    ])
    monkeypatch.setattr(v3, "perf_counter", lambda: next(times))
    manifest = _run(tmp_path, JsonModeProvider(_all_results()))
    assert manifest["successful_probe_count"] == 6
    assert manifest["json_contract_passed"] is True
    assert manifest["probes"][0]["latency_ms"] == 121000.0
    assert manifest["probes"][0]["formal_timeout_compatible"] is False
    assert manifest["formal_timeout_compatible"] is False
    assert manifest["status"] == "failed"
    assert manifest["eligible_to_propose_formal_r3_freeze"] is False


def test_manifest_anchors_history_and_stores_no_raw_responses(tmp_path: Path) -> None:
    manifest = _run(tmp_path, JsonModeProvider(_all_results()))
    assert manifest["source_r3_preflight_v1_readiness_sha256"] == v3.R3_PREFLIGHT_V1_READINESS_SHA256
    assert manifest["source_r3_preflight_v2_readiness_sha256"] == v3.R3_PREFLIGHT_V2_READINESS_SHA256
    assert manifest["source_r2_incident_manifest_sha256"] == hashlib.sha256(
        (R2_RUN / "stage_c_incident_manifest.json").read_bytes()
    ).hexdigest()
    assert manifest["formal_timeout_seconds"] == 120.0
    assert manifest["preflight_timeout_seconds"] == 300.0
    assert manifest["model_operational_risk"]["provider_listing_status"] == "deprecated"
    assert manifest["model_operational_risk"]["semantic_quality_inference"] is False
    assert all(probe["raw_response_stored"] is False for probe in manifest["probes"])
    assert all(probe["response_sha256"] for probe in manifest["probes"])
    serialized = json.dumps(manifest)
    assert "Synthetic fixture justification." not in serialized


def test_provider_must_advertise_json_object_capability(tmp_path: Path) -> None:
    provider = JsonModeProvider(_all_results())
    provider.supports_json_object_response_format = False
    with pytest.raises(StageCR3PreflightError, match="JSON-object"):
        _run(tmp_path, provider)
    assert provider.calls == []


def test_formal_runs_cannot_receive_preflight_artifact() -> None:
    provider = JsonModeProvider(_all_results())
    with pytest.raises(StageCR3PreflightError, match="must never enter"):
        asyncio.run(v3.run_stage_c_r3_json_mode_preflight_v3(
            ROOT,
            R2_RUN / "stage_c_r3_preflight_readiness_v3.json",
            provider=provider,
        ))
    assert provider.calls == []


def test_v1_v2_and_r2_artifacts_remain_immutable() -> None:
    assert hashlib.sha256(V1_READINESS.read_bytes()).hexdigest() == v3.R3_PREFLIGHT_V1_READINESS_SHA256
    assert hashlib.sha256(V2_READINESS.read_bytes()).hexdigest() == v3.R3_PREFLIGHT_V2_READINESS_SHA256
    assert hashlib.sha256((R2_RUN / "stage_c_judge.jsonl").read_bytes()).hexdigest() == f.STAGE_C_R2_JUDGMENTS_SHA256
    assert hashlib.sha256((R2_RUN / "stage_c_incident_manifest.json").read_bytes()).hexdigest() == (
        "24577b182eb9ba0c5a68d88419eac27fab4ab1709f19d850f050ae225dda9531"
    )


def test_no_formal_r3_run_or_freeze_exists() -> None:
    freeze = ROOT / "research/experiments/western_formal_v0_1/stage_c_execution_v0_1_2_r3"
    assert not freeze.exists()
    runs = ROOT / "research/experiments/western_formal_v0_1/runs"
    assert [path for path in runs.iterdir() if "stage-c-r3" in path.name] == []
