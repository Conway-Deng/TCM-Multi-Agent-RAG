from __future__ import annotations

import asyncio
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from typing import Any

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import (
    ProviderUnavailable,
    _chat_payload,
    _extract_response_model,
)
from western import formal_eval as f
from western import stage_c_free_judge as free
from western.stage_c_preflight import get_synthetic_probe_plan


ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / free.FREE_POLICY_RELATIVE_DIR
OLD_POLICY = ROOT / free.OLD_POLICY_V1_RELATIVE_PATH
PAID_INCIDENT = ROOT / free.PAID_DEEPSEEK_INCIDENT_RELATIVE_PATH
AMENDMENT_DIR = ROOT / free.OPERATIONAL_UNEVALUABILITY_AMENDMENT_RELATIVE_DIR
F1_ORDINARY = ROOT / free.F1_ORDINARY_MANIFEST_RELATIVE_PATH
F1_RECOVERY = ROOT / free.F1_RECOVERY_MANIFEST_RELATIVE_PATH


def _payload(probe: dict[str, Any]) -> dict[str, Any]:
    answerability = probe["answerability"]
    count = len(probe["retrieval"]["expected_evidence_points"])
    if answerability == "partially_supported" and probe.get("require_all_enums_exercised"):
        claim_labels = ["supported", "partially_supported", "unsupported", "not_checkable"]
        evidence_labels = ["covered", "partially_covered", "not_covered", "contradicted"]
    else:
        claim_labels = ["supported"] * max(1, count)
        evidence_labels = ["covered"] * count
    scope = (True, True, False) if answerability == "partially_supported" else (None, None, None)
    insufficiency = (
        probe.get("expected_insufficiency_label", "appropriate_abstention")
        if answerability == "insufficient"
        else "not_applicable"
    )
    return {
        "claim_labels": [
            {
                "claim_id": f"c{index}",
                "claim": f"Synthetic claim {index}",
                "label": label,
                "justification": "Free policy synthetic fixture.",
            }
            for index, label in enumerate(claim_labels)
        ],
        "evidence_point_labels": [
            {
                "point_index": index,
                "label": label,
                "justification": "Free policy synthetic fixture.",
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


def _result(
    probe: dict[str, Any],
    candidate: free.FreeJudgeCandidate,
    *,
    payload: dict[str, Any] | None = None,
    reported_model: str | None = None,
) -> GenerationResult:
    return GenerationResult(
        text=json.dumps(payload if payload is not None else _payload(probe)),
        provider=free.FREE_PROVIDER,
        model=reported_model if reported_model is not None else candidate.model_id,
        finish_reason="stop",
    )


def _successes(candidate_number: int) -> list[GenerationResult]:
    candidate = free.get_free_candidate(candidate_number)
    return [_result(probe, candidate) for probe in get_synthetic_probe_plan()]


class MockProvider:
    name = free.FREE_PROVIDER
    timeout = free.FREE_TIMEOUT_SECONDS
    max_tokens = free.FREE_MAX_TOKENS
    supports_response_format = True
    supports_json_object_response_format = True

    def __init__(
        self,
        candidate: free.FreeJudgeCandidate,
        results: list[GenerationResult | Exception],
    ) -> None:
        self.model = candidate.model_id
        self.enable_thinking = candidate.expected_provider_enable_thinking
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> GenerationResult:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _provider(candidate_number: int, results: list[GenerationResult | Exception] | None = None) -> MockProvider:
    candidate = free.get_free_candidate(candidate_number)
    return MockProvider(candidate, results if results is not None else list(_successes(candidate_number)))


def _run(
    manifests: Path,
    candidate_number: int = 1,
    replicate_number: int = 1,
    recovery_number: int = 0,
    provider: MockProvider | None = None,
    current_time: Any | None = None,
) -> dict[str, Any]:
    return asyncio.run(free.run_free_judge_preflight(
        ROOT,
        candidate_number=candidate_number,
        replicate_number=replicate_number,
        recovery_number=recovery_number,
        zero_cost_confirmed=True,
        provider=provider or _provider(candidate_number),
        test_manifests_dir=manifests,
        current_time=current_time,
    ))


def _completed_at(manifest: dict[str, Any]):
    return free._parse_utc(manifest["completed_at"])


def test_exact_free_candidate_order_and_thinking_metadata() -> None:
    assert [(candidate.model_id, candidate.thinking_toggle) for candidate in free.FREE_CANDIDATES] == [
        ("XingChenAGI/Xing4.0-29B", "omit"),
        ("THUDM/GLM-4-9B-0414", "omit"),
        ("deepseek-ai/DeepSeek-R1-0528-Qwen3-8B", "send_false"),
        ("Qwen/Qwen3.5-4B", "omit"),
    ]


def test_arbitrary_model_id_is_impossible(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(free.StageCFreeJudgeError, match="not in the frozen free candidate registry"):
        free.get_free_candidate_by_model("arbitrary/provider-model")
    monkeypatch.setenv("STAGE_C_FREE_MODEL", "arbitrary/provider-model")
    assert free.get_free_candidate(1).model_id == "XingChenAGI/Xing4.0-29B"


def test_policy_and_historical_artifacts_are_pinned_and_separate() -> None:
    assert hashlib.sha256((POLICY_DIR / "policy.json").read_bytes()).hexdigest() == free.FREE_POLICY_SHA256
    assert hashlib.sha256(OLD_POLICY.read_bytes()).hexdigest() == free.OLD_POLICY_V1_SHA256
    assert hashlib.sha256(PAID_INCIDENT.read_bytes()).hexdigest() == free.PAID_DEEPSEEK_INCIDENT_SHA256
    assert POLICY_DIR != OLD_POLICY.parent
    hashes = free.verify_free_policy_and_history(ROOT)
    assert hashes["free_policy_sha256"] == free.FREE_POLICY_SHA256
    assert hashes["paid_deepseek_candidate_01_incident_sha256"] == free.PAID_DEEPSEEK_INCIDENT_SHA256


def test_candidate_01_replicate_01_is_initially_eligible(tmp_path: Path) -> None:
    allowed, _, _ = free.evaluate_free_runner_eligibility(tmp_path, 1, 1)
    assert allowed is True


def test_candidate_02_blocked_while_candidate_01_unresolved(tmp_path: Path) -> None:
    allowed, reason, _ = free.evaluate_free_runner_eligibility(tmp_path, 2, 1)
    assert allowed is False
    assert "prior candidate 01" in reason


def test_replicate_02_blocked_without_replicate_01(tmp_path: Path) -> None:
    allowed, reason, _ = free.evaluate_free_runner_eligibility(tmp_path, 1, 2)
    assert allowed is False
    assert "effective replicate 01 is missing" in reason


def test_replicate_02_requires_3600_seconds(tmp_path: Path) -> None:
    rep1 = _run(tmp_path)
    completed = _completed_at(rep1)
    early = free.evaluate_free_runner_eligibility(
        tmp_path, 1, 2, current_time=completed + timedelta(seconds=3599)
    )
    ready = free.evaluate_free_runner_eligibility(
        tmp_path, 1, 2, current_time=completed + timedelta(seconds=3600)
    )
    assert early[0] is False
    assert ready[0] is True


def test_two_successful_replicates_select_primary_and_block_later_candidates(tmp_path: Path) -> None:
    rep1 = _run(tmp_path)
    rep2 = _run(
        tmp_path,
        replicate_number=2,
        current_time=_completed_at(rep1) + timedelta(seconds=3601),
    )
    assert rep2["candidate_qualification_status"] == "qualified_and_selected_primary_judge"
    allowed, reason, _ = free.evaluate_free_runner_eligibility(tmp_path, 2, 1)
    assert allowed is False
    assert "already selected" in reason


def test_ordinary_third_replicate_and_second_recovery_are_impossible() -> None:
    with pytest.raises(free.StageCFreeJudgeError, match="Only replicate numbers 1 and 2"):
        free.free_manifest_name(1, 3)
    with pytest.raises(free.StageCFreeJudgeError, match="Only recovery number 1"):
        free.free_manifest_name(1, 1, 2)


def test_exact_six_probe_transport_and_frozen_settings(tmp_path: Path) -> None:
    provider = _provider(1)
    manifest = _run(tmp_path, provider=provider)
    assert manifest["probe_count"] == 6
    assert manifest["successful_probe_count"] == 6
    assert manifest["response_format"] == {"type": "json_object"}
    assert manifest["temperature"] == 0
    assert manifest["max_tokens"] == 1200
    assert manifest["timeout_seconds"] == 120.0
    assert [probe["probe_id"] for probe in manifest["probes"]] == [
        "synthetic-supported-probe-01",
        "synthetic-supported-probe-02",
        "synthetic-partially-supported-probe-01",
        "synthetic-partially-supported-probe-02",
        "synthetic-insufficient-probe-01",
        "synthetic-insufficient-probe-02",
    ]
    assert len(provider.calls) == 6
    for call in provider.calls:
        assert call["response_format"] == {"type": "json_object"}
        assert call["temperature"] == 0
        assert call["max_tokens"] == 1200


def test_six_of_six_and_two_per_class_are_required(tmp_path: Path) -> None:
    plan = get_synthetic_probe_plan()
    candidate = free.get_free_candidate(1)
    results = list(_successes(1))
    invalid = _payload(plan[0])
    invalid["claim_labels"][0]["label"] = "exactly supported"
    results[0] = _result(plan[0], candidate, payload=invalid)
    manifest = _run(tmp_path, provider=_provider(1, results))
    assert manifest["successful_probe_count"] == 5
    assert manifest["execution_classification"] == "candidate_readiness_failure"
    assert manifest["per_answerability_summary"]["supported"]["json_contract_passed"] is False
    assert manifest["advancement_authorized"] is True


def test_wrong_expected_insufficiency_label_is_candidate_failure(tmp_path: Path) -> None:
    plan = get_synthetic_probe_plan()
    candidate = free.get_free_candidate(1)
    results = list(_successes(1))
    invalid = _payload(plan[4])
    invalid["insufficiency_label"] = "appropriate_bounded_insufficiency"
    results[4] = _result(plan[4], candidate, payload=invalid)
    manifest = _run(tmp_path, provider=_provider(1, results))
    assert manifest["execution_classification"] == "candidate_readiness_failure"


def test_exact_provider_model_identity_required(tmp_path: Path) -> None:
    plan = get_synthetic_probe_plan()
    candidate = free.get_free_candidate(1)
    results = list(_successes(1))
    results[0] = _result(plan[0], candidate, reported_model="some/alias")
    manifest = _run(tmp_path, provider=_provider(1, results))
    assert manifest["probes"][0]["error_type"] == "model_identity_mismatch"
    assert manifest["execution_classification"] == "candidate_readiness_failure"


@pytest.mark.parametrize("data", [{}, {"model": None}, {"model": ""}, {"model": 7}])
def test_malformed_provider_reported_model_fails(data: dict[str, Any]) -> None:
    with pytest.raises((KeyError, TypeError, ValueError)):
        _extract_response_model(data)
    classification, error = free.classify_provider_exception(
        ProviderUnavailable("malformed provider response", error_type="malformed_response")
    )
    assert (classification, error) == ("ambiguous_technical_failure", "malformed_provider_response")


def test_no_raw_responses_stored(tmp_path: Path) -> None:
    manifest = _run(tmp_path)
    serialized = json.dumps(manifest)
    assert "Free policy synthetic fixture." not in serialized
    assert manifest["raw_response_stored"] is False
    assert all(probe["raw_response_stored"] is False for probe in manifest["probes"])
    assert all(probe["response_sha256"] for probe in manifest["probes"])


def test_output_overwrite_and_formal_directory_are_prohibited(tmp_path: Path) -> None:
    target = tmp_path / free.free_manifest_name(1, 1)
    target.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        free._validate_output_target(ROOT, target, tmp_path)
    formal = ROOT / "research/experiments/western_formal_v0_1/runs"
    with pytest.raises(free.StageCFreeJudgeError, match="must never enter"):
        free._validate_output_target(ROOT, formal / free.free_manifest_name(1, 1), formal)


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (ProviderUnavailable("payment", error_type="http_4xx", http_status=402), "http_402"),
        (ProviderUnavailable("rate", error_type="rate_limit", http_status=429), "http_429"),
        (ProviderUnavailable("connect", error_type="connectivity"), "connectivity"),
        (ProviderUnavailable("server", error_type="http_5xx", http_status=503), "http_5xx"),
    ],
)
def test_qualifying_provider_failures_are_infrastructure_incidents(
    tmp_path: Path, exc: ProviderUnavailable, expected_error: str
) -> None:
    provider = _provider(1, [exc] * 6)
    manifest = _run(tmp_path, provider=provider)
    assert manifest["execution_classification"] == "infrastructure_incident"
    assert manifest["infrastructure_recovery_authorized"] is True
    assert manifest["advancement_authorized"] is False
    assert manifest["probes"][0]["error_type"] == expected_error


def test_required_parameter_rejection_is_candidate_failure(tmp_path: Path) -> None:
    exc = ProviderUnavailable("bad request", error_type="http_4xx", http_status=422)
    manifest = _run(tmp_path, provider=_provider(1, [exc] * 6))
    assert manifest["execution_classification"] == "candidate_readiness_failure"
    assert manifest["advancement_authorized"] is True


def test_infrastructure_incident_does_not_unlock_candidate_02(tmp_path: Path) -> None:
    exc = ProviderUnavailable("payment", error_type="http_4xx", http_status=402)
    _run(tmp_path, provider=_provider(1, [exc] * 6))
    allowed, reason, _ = free.evaluate_free_runner_eligibility(tmp_path, 2, 1)
    assert allowed is False
    assert "pending_recovery" in reason


def test_exactly_one_complete_recovery_can_become_effective_replicate(tmp_path: Path) -> None:
    exc = ProviderUnavailable("payment", error_type="http_4xx", http_status=402)
    ordinary = _run(tmp_path, provider=_provider(1, [exc] * 6))
    assert ordinary["replicate_passed"] is False
    recovery_provider = _provider(1)
    recovery = _run(tmp_path, recovery_number=1, provider=recovery_provider)
    assert recovery["replicate_passed"] is True
    assert len(recovery_provider.calls) == 6
    assert recovery["probes"][0]["probe_number"] == 1
    completion = _completed_at(recovery)
    early = free.evaluate_free_runner_eligibility(
        tmp_path, 1, 2, current_time=completion + timedelta(seconds=3599)
    )
    ready = free.evaluate_free_runner_eligibility(
        tmp_path, 1, 2, current_time=completion + timedelta(seconds=3600)
    )
    assert early[0] is False
    assert ready[0] is True
    another_recovery = free.evaluate_free_runner_eligibility(tmp_path, 1, 1, 1)
    assert another_recovery[0] is False


def test_candidate_failure_during_recovery_unlocks_next_candidate(tmp_path: Path) -> None:
    infra = ProviderUnavailable("connect", error_type="connectivity")
    _run(tmp_path, provider=_provider(1, [infra] * 6))
    plan = get_synthetic_probe_plan()
    candidate = free.get_free_candidate(1)
    results = list(_successes(1))
    invalid = _payload(plan[0])
    invalid["claim_labels"][0]["label"] = "wrong"
    results[0] = _result(plan[0], candidate, payload=invalid)
    recovery = _run(tmp_path, recovery_number=1, provider=_provider(1, results))
    assert recovery["execution_classification"] == "candidate_readiness_failure"
    assert free.evaluate_free_runner_eligibility(tmp_path, 2, 1)[0] is True


def test_second_infrastructure_incident_requires_manual_review_and_stops(tmp_path: Path) -> None:
    infra = ProviderUnavailable("connect", error_type="connectivity")
    _run(tmp_path, provider=_provider(1, [infra] * 6))
    recovery = _run(tmp_path, recovery_number=1, provider=_provider(1, [infra] * 6))
    assert recovery["manual_methodology_review_required"] is True
    assert recovery["advancement_authorized"] is False
    assert free.evaluate_free_runner_eligibility(tmp_path, 2, 1)[0] is False
    assert free.evaluate_free_runner_eligibility(tmp_path, 1, 1, 1)[0] is False


def test_candidate_failure_precedes_simultaneous_infrastructure_incident(tmp_path: Path) -> None:
    plan = get_synthetic_probe_plan()
    candidate = free.get_free_candidate(1)
    invalid = _payload(plan[0])
    invalid["claim_labels"][0]["label"] = "wrong"
    results: list[GenerationResult | Exception] = [
        _result(plan[0], candidate, payload=invalid),
        ProviderUnavailable("connect", error_type="connectivity"),
        *_successes(1)[2:],
    ]
    manifest = _run(tmp_path, provider=_provider(1, results))
    assert manifest["execution_classification"] == "candidate_readiness_failure"
    assert manifest["infrastructure_recovery_authorized"] is False


def test_unexpected_internal_exception_creates_no_manifest_or_advancement(tmp_path: Path) -> None:
    provider = _provider(1, [RuntimeError("unexpected internal defect")])
    with pytest.raises(RuntimeError, match="unexpected internal defect"):
        _run(tmp_path, provider=provider)
    assert list(tmp_path.glob("*.json")) == []
    assert free.evaluate_free_runner_eligibility(tmp_path, 2, 1)[0] is False


def test_no_provider_call_without_zero_cost_acknowledgement(tmp_path: Path) -> None:
    provider = _provider(1)
    with pytest.raises(free.StageCFreeJudgeError, match="zero-cost confirmation"):
        asyncio.run(free.run_free_judge_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            zero_cost_confirmed=False,
            provider=provider,
            test_manifests_dir=tmp_path,
        ))
    assert provider.calls == []


def test_zero_cost_ineligibility_is_recorded_without_call_and_advances(tmp_path: Path) -> None:
    note = free.record_zero_cost_ineligibility(
        ROOT, candidate_number=1, test_manifests_dir=tmp_path
    )
    assert note["provider_calls_made"] == 0
    assert note["candidate_quality_interpretation"] is False
    assert free.evaluate_free_runner_eligibility(tmp_path, 2, 1)[0] is True


def test_candidate_specific_thinking_payload_is_frozen() -> None:
    for candidate in free.FREE_CANDIDATES:
        payload = _chat_payload(
            model=candidate.model_id,
            system="system",
            prompt="prompt",
            temperature=0,
            max_tokens=1200,
            frequency_penalty=0,
            response_format={"type": "json_object"},
        )
        if candidate.thinking_toggle == "send_false":
            assert payload["enable_thinking"] is False
        else:
            assert "enable_thinking" not in payload


def test_forged_manifest_fails_closed(tmp_path: Path) -> None:
    _run(tmp_path)
    path = tmp_path / free.free_manifest_name(1, 1)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source_policy_sha256"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(free.StageCFreeJudgeError, match="source_policy_sha256"):
        free.inspect_free_policy_manifests(tmp_path)


def test_production_cli_has_no_model_output_timeout_prompt_or_schema_options() -> None:
    script = ROOT / "scripts/run-western-stage-c-free-judge-preflight.py"
    spec = importlib.util.spec_from_file_location("free_cli", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parser_args = module.parse_args(["--candidate", "1", "--replicate", "1"])
    assert vars(parser_args).keys() == {
        "candidate",
        "replicate",
        "recovery",
        "confirm_zero_cost",
        "execute_candidate_preflight",
        "record_not_zero_cost",
    }
    called = False

    async def forbidden_call(*args: Any, **kwargs: Any) -> None:
        nonlocal called
        called = True

    module.run_free_judge_preflight = forbidden_call
    with pytest.raises(SystemExit, match="both --confirm-zero-cost"):
        module.main(["--candidate", "1", "--replicate", "1"])
    assert called is False


def test_generator_and_formal_contract_remain_unchanged() -> None:
    assert f.GENERATOR_MODEL == "Qwen/Qwen3-8B"
    assert free.FREE_TEMPERATURE == 0
    assert free.FREE_MAX_TOKENS == 1200
    assert free.FREE_TIMEOUT_SECONDS == 120.0


def test_no_formal_free_run_or_freeze_exists() -> None:
    root = ROOT / "research/experiments/western_formal_v0_1"
    assert not (root / "stage_c_execution_v0_1_4_free_jrv1").exists()
    runs = root / "runs"
    assert [path for path in runs.iterdir() if "stage-c-free-jrv1" in path.name] == []


def _copy_amendment(target: Path, *, include_adjudication: bool) -> Path:
    target.mkdir(parents=True)
    shutil.copy2(AMENDMENT_DIR / "amendment.json", target / "amendment.json")
    shutil.copy2(AMENDMENT_DIR / "AMENDMENT.md", target / "AMENDMENT.md")
    adjudications = target / "adjudications"
    adjudications.mkdir()
    if include_adjudication:
        name = free.operational_unevaluability_adjudication_name(1)
        shutil.copy2(AMENDMENT_DIR / "adjudications" / name, adjudications / name)
    return target


def _copy_f1_incidents(target: Path) -> Path:
    target.mkdir(parents=True)
    shutil.copy2(F1_ORDINARY, target / F1_ORDINARY.name)
    shutil.copy2(F1_RECOVERY, target / F1_RECOVERY.name)
    return target


def test_operational_amendment_and_f1_history_are_immutably_pinned() -> None:
    assert hashlib.sha256((POLICY_DIR / "policy.json").read_bytes()).hexdigest() == free.FREE_POLICY_SHA256
    assert hashlib.sha256((AMENDMENT_DIR / "amendment.json").read_bytes()).hexdigest() == (
        free.OPERATIONAL_UNEVALUABILITY_AMENDMENT_SHA256
    )
    assert hashlib.sha256(F1_ORDINARY.read_bytes()).hexdigest() == free.F1_ORDINARY_MANIFEST_SHA256
    assert hashlib.sha256(F1_RECOVERY.read_bytes()).hexdigest() == free.F1_RECOVERY_MANIFEST_SHA256


def test_canonical_f1_adjudication_is_terminal_operational_and_unlocks_only_f2() -> None:
    manifests = free.get_free_manifests_dir(ROOT)
    state = free.inspect_free_policy_manifests(manifests)
    adjudication = state["operationally_unevaluable"][1]
    assert free._candidate_state(state, 1) == free.OPERATIONAL_UNEVALUABILITY_STATE
    assert adjudication["candidate_readiness_failure"] is False
    assert adjudication["semantic_or_capability_conclusion"] is False
    assert adjudication["cross_attempt_pooling"] is False
    assert adjudication["formal_stage_c_eligibility"] is False
    assert free.evaluate_free_runner_eligibility(manifests, 2, 1)[0] is True
    allowed, reason, _ = free.evaluate_free_runner_eligibility(manifests, 3, 1)
    assert allowed is False
    assert "prior candidate 02" in reason


def test_f2_requires_both_amendment_and_valid_adjudication(tmp_path: Path) -> None:
    manifests = _copy_f1_incidents(tmp_path / "manifests")
    assert free.evaluate_free_runner_eligibility(manifests, 2, 1)[0] is False
    amendment = _copy_amendment(tmp_path / "amendment", include_adjudication=False)
    assert free.evaluate_free_runner_eligibility(
        manifests, 2, 1, amendment_dir=amendment
    )[0] is False
    name = free.operational_unevaluability_adjudication_name(1)
    shutil.copy2(
        AMENDMENT_DIR / "adjudications" / name,
        amendment / "adjudications" / name,
    )
    assert free.evaluate_free_runner_eligibility(
        manifests, 2, 1, amendment_dir=amendment
    )[0] is True


def test_forged_operational_adjudication_fails_closed(tmp_path: Path) -> None:
    manifests = _copy_f1_incidents(tmp_path / "manifests")
    amendment = _copy_amendment(tmp_path / "amendment", include_adjudication=True)
    path = amendment / "adjudications" / free.operational_unevaluability_adjudication_name(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["semantic_or_capability_conclusion"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(free.StageCFreeJudgeError, match="semantic_or_capability_conclusion"):
        free.inspect_free_policy_manifests(manifests, amendment_dir=amendment)


def test_infrastructure_pair_creates_atomic_general_adjudication(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    amendment = _copy_amendment(tmp_path / "amendment", include_adjudication=False)
    infra = ProviderUnavailable("connect", error_type="connectivity")
    _run(manifests, provider=_provider(1, [infra] * 6))
    _run(manifests, recovery_number=1, provider=_provider(1, [infra] * 6))
    adjudication = free.create_operational_unevaluability_adjudication(
        ROOT,
        candidate_number=1,
        replicate_number=1,
        manifests_dir=manifests,
        amendment_dir=amendment,
        adjudicated_at=free._parse_utc("2026-09-20T11:15:00+00:00"),
    )
    assert adjudication["adjudication_state"] == free.OPERATIONAL_UNEVALUABILITY_LABEL
    assert free.evaluate_free_runner_eligibility(
        manifests, 2, 1, amendment_dir=amendment
    )[0] is True
    with pytest.raises(FileExistsError):
        free.create_operational_unevaluability_adjudication(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            manifests_dir=manifests,
            amendment_dir=amendment,
        )


def test_partial_successes_are_valid_but_never_pooled(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    amendment = _copy_amendment(tmp_path / "amendment", include_adjudication=False)
    infra = ProviderUnavailable("connect", error_type="connectivity")
    ordinary_results: list[GenerationResult | Exception] = [
        *_successes(1)[:2],
        infra,
        infra,
        infra,
        infra,
    ]
    recovery_results: list[GenerationResult | Exception] = [
        *_successes(1)[:3],
        infra,
        infra,
        infra,
    ]
    ordinary = _run(manifests, provider=_provider(1, ordinary_results))
    recovery = _run(
        manifests,
        recovery_number=1,
        provider=_provider(1, recovery_results),
    )
    assert ordinary["successful_probe_count"] == 2
    assert recovery["successful_probe_count"] == 3
    assert ordinary["execution_classification"] == "infrastructure_incident"
    assert recovery["execution_classification"] == "infrastructure_incident"
    adjudication = free.create_operational_unevaluability_adjudication(
        ROOT,
        candidate_number=1,
        replicate_number=1,
        manifests_dir=manifests,
        amendment_dir=amendment,
        adjudicated_at=free._parse_utc("2026-09-20T11:15:00+00:00"),
    )
    assert adjudication["cross_attempt_pooling"] is False
    assert adjudication["partial_qualification"] is False


def test_readiness_failure_in_either_attempt_prevents_operational_unevaluability(
    tmp_path: Path,
) -> None:
    manifests = tmp_path / "manifests"
    infra = ProviderUnavailable("connect", error_type="connectivity")
    ordinary = _run(manifests, provider=_provider(1, [infra] * 6))
    recovery = _run(manifests, recovery_number=1, provider=_provider(1, [infra] * 6))
    ordinary_failure = json.loads(json.dumps(ordinary))
    ordinary_failure["execution_classification"] = "candidate_readiness_failure"
    with pytest.raises(free.StageCFreeJudgeError, match="ordinary attempt is not"):
        free._require_operational_unevaluability_pair(
            ordinary_failure, recovery, candidate_number=1, replicate_number=1
        )
    recovery_failure = json.loads(json.dumps(recovery))
    recovery_failure["execution_classification"] = "candidate_readiness_failure"
    with pytest.raises(free.StageCFreeJudgeError, match="recovery attempt is not"):
        free._require_operational_unevaluability_pair(
            ordinary, recovery_failure, candidate_number=1, replicate_number=1
        )


def test_ambiguous_failure_remains_manual_review_and_blocks_advancement(tmp_path: Path) -> None:
    ambiguous = ProviderUnavailable(
        "malformed provider response",
        error_type="malformed_response",
    )
    manifest = _run(tmp_path, provider=_provider(1, [ambiguous] * 6))
    assert manifest["execution_classification"] == "ambiguous_technical_failure"
    assert manifest["manual_methodology_review_required"] is True
    assert free.evaluate_free_runner_eligibility(tmp_path, 2, 1)[0] is False


def test_replicate_2_infrastructure_pair_is_terminal_operational(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    amendment = _copy_amendment(tmp_path / "amendment", include_adjudication=False)
    replicate_1 = _run(manifests)
    rep1_completed = _completed_at(replicate_1)
    infra = ProviderUnavailable("server", error_type="http_5xx", http_status=500)
    _run(
        manifests,
        replicate_number=2,
        provider=_provider(1, [infra] * 6),
        current_time=rep1_completed + timedelta(seconds=3600),
    )
    _run(
        manifests,
        replicate_number=2,
        recovery_number=1,
        provider=_provider(1, [infra] * 6),
        current_time=rep1_completed + timedelta(seconds=3601),
    )
    adjudication = free.create_operational_unevaluability_adjudication(
        ROOT,
        candidate_number=1,
        replicate_number=2,
        manifests_dir=manifests,
        amendment_dir=amendment,
        adjudicated_at=free._parse_utc("2026-09-20T11:15:00+00:00"),
    )
    state = free.inspect_free_policy_manifests(manifests, amendment_dir=amendment)
    assert adjudication["affected_replicate"] == 2
    assert free._effective_replicate(state, 1, 1)["status"] == "passed"
    assert free._candidate_state(state, 1) == free.OPERATIONAL_UNEVALUABILITY_STATE
    assert free.evaluate_free_runner_eligibility(
        manifests, 2, 1, amendment_dir=amendment
    )[0] is True


def test_zero_cost_ineligibility_selected_primary_and_no_force_advance_are_distinct(
    tmp_path: Path,
) -> None:
    zero_cost_dir = tmp_path / "zero-cost"
    free.record_zero_cost_ineligibility(ROOT, candidate_number=1, test_manifests_dir=zero_cost_dir)
    zero_state = free.inspect_free_policy_manifests(zero_cost_dir)
    assert free._candidate_state(zero_state, 1) == "terminal_operational_ineligibility"

    selected_dir = tmp_path / "selected"
    rep1 = _run(selected_dir)
    _run(
        selected_dir,
        replicate_number=2,
        current_time=_completed_at(rep1) + timedelta(seconds=3600),
    )
    selected_state = free.inspect_free_policy_manifests(selected_dir)
    assert free._candidate_state(selected_state, 1) == "selected_primary"
    assert free.OPERATIONAL_UNEVALUABILITY_STATE not in {
        "terminal_operational_ineligibility",
        "selected_primary",
    }

    script_text = (
        ROOT / "scripts/run-western-stage-c-free-judge-preflight.py"
    ).read_text(encoding="utf-8")
    assert "force-advance" not in script_text
    assert "candidate-order" not in script_text
