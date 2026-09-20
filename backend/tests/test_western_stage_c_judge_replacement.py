from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import (
    OpenAICompatibleLLMProvider,
    ProviderUnavailable,
    _chat_payload,
    _supports_thinking_toggle,
)
from western import formal_eval as f
from western import stage_c_judge_replacement as jr
from western.formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT
from western.stage_c_preflight import (
    R3_PREFLIGHT_PROBE_COUNT,
    StageCR3PreflightError,
    get_synthetic_probe_plan,
)
from western.stage_c_preflight_v3 import (
    build_stage_c_r3_json_mode_prompt,
    validate_stage_c_r3_json_mode_probe_output,
)


ROOT = Path(__file__).resolve().parents[2]


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
                "justification": "Synthetic replacement fixture justification.",
            }
            for index, label in enumerate(claim_labels)
        ],
        "evidence_point_labels": [
            {
                "point_index": index,
                "label": label,
                "justification": "Synthetic replacement fixture justification.",
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
    candidate: jr.ReplacementCandidate,
    payload: dict[str, Any] | None = None,
    reported_model: str | None = None,
) -> GenerationResult:
    return GenerationResult(
        text=json.dumps(payload if payload is not None else _mock_payload(probe)),
        provider=jr.REPLACEMENT_PROVIDER,
        model=reported_model or candidate.model_id,
        finish_reason="stop",
    )


def _all_results(
    candidate: jr.ReplacementCandidate, reported_model: str | None = None
) -> list[GenerationResult]:
    return [
        _result(probe, candidate, reported_model=reported_model)
        for probe in get_synthetic_probe_plan()
    ]


class MockReplacementProvider:
    name = jr.REPLACEMENT_PROVIDER
    supports_response_format = True
    supports_json_object_response_format = True
    timeout = jr.REPLACEMENT_TIMEOUT_SECONDS
    max_tokens = jr.REPLACEMENT_MAX_TOKENS
    enable_thinking = False

    def __init__(
        self,
        candidate: jr.ReplacementCandidate,
        results: list[GenerationResult | Exception],
        *,
        override_model: str | None = None,
        override_timeout: float | None = None,
        override_enable_thinking: bool | None = None,
    ) -> None:
        self.candidate = candidate
        self.model = override_model or candidate.model_id
        if override_timeout is not None:
            self.timeout = override_timeout
        if override_enable_thinking is not None:
            self.enable_thinking = override_enable_thinking
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> GenerationResult:
        self.calls.append(kwargs)
        outcome = self.results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _build_valid_manifest(
    candidate_number: int,
    replicate_number: int,
    passed: bool,
    completed_at: datetime,
) -> dict[str, Any]:
    candidate = jr.get_candidate(candidate_number)
    plan = get_synthetic_probe_plan()

    probes: list[dict[str, Any]] = []
    for idx, spec in enumerate(plan):
        is_successful = passed or (idx != 0)
        probes.append({
            "probe_number": spec["probe_number"],
            "probe_id": spec["probe_id"],
            "answerability": spec["answerability"],
            "expected_evidence_point_count": len(spec["retrieval"]["expected_evidence_points"]),
            "expected_insufficiency_label": spec.get("expected_insufficiency_label"),
            "synthetic_non_formal": True,
            "provider_call_success": is_successful,
            "json_contract_success": is_successful,
            "formal_timeout_compatible": is_successful,
            "normalization": "none" if is_successful else None,
            "provider_reported_model": candidate.model_id if is_successful else None,
            "finish_reason": "stop" if is_successful else None,
            "latency_ms": 1000.0,
            "error_type": None if is_successful else "schema_or_contract_failure",
            "error_message": None if is_successful else "Mocked probe failure",
            "response_sha256": "a" * 64 if is_successful else None,
            "raw_response_stored": False,
        })

    per_answerability = {
        "supported": {
            "attempted": 2,
            "json_contract_successful": 2 if passed else 1,
            "json_contract_passed": passed,
            "formal_timeout_compatible": passed,
            "timeouts": 0,
        },
        "partially_supported": {
            "attempted": 2,
            "json_contract_successful": 2,
            "json_contract_passed": True,
            "formal_timeout_compatible": True,
            "timeouts": 0,
        },
        "insufficient": {
            "attempted": 2,
            "json_contract_successful": 2,
            "json_contract_passed": True,
            "formal_timeout_compatible": True,
            "timeouts": 0,
        },
    }

    qualification_status = (
        ("replicate_01_passed_pending_replicate_02" if replicate_number == 1 else "qualified_and_selected")
        if passed
        else f"terminally_failed_on_replicate_{replicate_number:02d}"
    )
    next_eligibility = (
        ("blocked_pending_replicate_02" if replicate_number == 1 else "permanently_blocked_earlier_candidate_qualified")
        if passed
        else (f"candidate_{candidate_number + 1:02d}_eligible" if candidate_number < 3 else "all_exhausted")
    )

    return {
        "policy_version": jr.REPLACEMENT_POLICY_VERSION,
        "protocol_amendment_version": jr.PROTOCOL_AMENDMENT_VERSION,
        "candidate_number": candidate.candidate_number,
        "candidate_slug": candidate.slug,
        "requested_model_id": candidate.model_id,
        "replicate_number": replicate_number,
        "replicate_id": jr.candidate_replicate_id(candidate_number, replicate_number),
        "status": "passed" if passed else "failed",
        "replicate_passed": passed,
        "candidate_qualification_status": qualification_status,
        "next_candidate_eligibility": next_eligibility,
        "started_at": (completed_at - timedelta(seconds=60)).isoformat(),
        "completed_at": completed_at.isoformat(),
        "replicate_spacing_seconds": 3600.0 if replicate_number == 2 else None,
        "synthetic_non_formal": True,
        "formal_stage_c_run_created": False,
        "outputs_eligible_as_research_data": False,
        "outputs_must_never_enter_formal_analysis": True,
        "provider": jr.REPLACEMENT_PROVIDER,
        "response_format": copy.deepcopy(jr.REPLACEMENT_TRANSPORT),
        "temperature": jr.REPLACEMENT_TEMPERATURE,
        "max_tokens": jr.REPLACEMENT_MAX_TOKENS,
        "timeout_seconds": jr.REPLACEMENT_TIMEOUT_SECONDS,
        "enable_thinking": False,
        "probe_plan_version": jr.R3_PREFLIGHT_PROBE_PLAN_VERSION,
        "probe_count": R3_PREFLIGHT_PROBE_COUNT,
        "successful_probe_count": 6 if passed else 5,
        "json_contract_passed": passed,
        "formal_timeout_compatible": passed,
        "timeout_occurrences": 0,
        "per_answerability_summary": per_answerability,
        "latency_metrics": {
            "mean_latency_ms": 1000.0,
            "median_latency_ms": 1000.0,
            "max_latency_ms": 1000.0,
        },
        "source_policy_sha256": jr.REPLACEMENT_POLICY_SHA256,
        "source_historical_and_scientific_hashes": {
            "protocol_v0_1_2_sha256": jr.PROTOCOL_V0_1_2_SHA256,
            "stage_a_retrieval_sha256": jr.STAGE_A_EXPECTED_SHA256,
            "primary_stage_b_sha256": jr.PRIMARY_STAGE_B_EXPECTED_SHA256,
            "primary_stage_b_run_manifest_sha256": jr.PRIMARY_STAGE_B_RUN_MANIFEST_EXPECTED_SHA256,
            "analysis_json_sha256": jr.STAGE_C_R2_ANALYSIS_EXPECTED_SHA256,
            "r2_judgments_sha256": jr.STAGE_C_R2_JUDGMENTS_SHA256,
            "r2_incident_manifest_sha256": jr.STAGE_C_R2_INCIDENT_MANIFEST_SHA256,
            "preflight_v1_sha256": jr.R3_PREFLIGHT_V1_READINESS_SHA256,
            "preflight_v2_sha256": jr.R3_PREFLIGHT_V2_READINESS_SHA256,
            "preflight_v3_sha256": jr.R3_PREFLIGHT_V3_READINESS_SHA256,
        },
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
            "semantic_normalization": False,
            "synonym_repair": False,
            "post_hoc_value_repair": False,
        },
        "raw_response_stored": False,
        "probes": probes,
    }


def _write_mock_manifest(
    manifests_dir: Path,
    candidate_number: int,
    replicate_number: int,
    passed: bool,
    completed_at: datetime,
) -> Path:
    filename = jr.candidate_manifest_name(candidate_number, replicate_number)
    path = manifests_dir / filename
    manifest_data = _build_valid_manifest(candidate_number, replicate_number, passed, completed_at)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test 1: Policy candidate order exact and immutable
# ---------------------------------------------------------------------------
def test_01_policy_candidate_order_exact_and_immutable() -> None:
    expected_order = [
        (1, "deepseek-ai/DeepSeek-V3.2", "deepseek-v3-2"),
        (2, "openai/gpt-oss-120b", "gpt-oss-120b"),
        (3, "Qwen/Qwen3.5-35B-A3B", "qwen3-5-35b-a3b"),
    ]
    assert len(jr.FROZEN_CANDIDATE_REGISTRY) == 3
    for idx, (expected_num, expected_model, expected_slug) in enumerate(expected_order):
        cand = jr.FROZEN_CANDIDATE_REGISTRY[idx]
        assert cand.candidate_number == expected_num
        assert cand.model_id == expected_model
        assert cand.slug == expected_slug

    with pytest.raises(TypeError):
        jr.FROZEN_CANDIDATE_REGISTRY[0] = None  # type: ignore


# ---------------------------------------------------------------------------
# Test 2: Arbitrary model ID cannot bypass registry
# ---------------------------------------------------------------------------
def test_02_arbitrary_model_id_cannot_bypass_registry() -> None:
    with pytest.raises(jr.StageCJudgeReplacementError, match="not in the frozen replacement candidate registry"):
        jr.get_candidate_by_model("unregistered/arbitrary-llm-123")
    with pytest.raises(jr.StageCJudgeReplacementError, match="Invalid candidate number 99"):
        jr.get_candidate(99)


# ---------------------------------------------------------------------------
# Test 3: Candidate 01 replicate 01 allowed from clean state
# ---------------------------------------------------------------------------
def test_03_candidate_01_replicate_01_allowed_from_clean_state(tmp_path: Path) -> None:
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 1, 1)
    assert eligible is True
    assert "eligible" in reason


# ---------------------------------------------------------------------------
# Test 4: Candidate 01 replicate 02 blocked if replicate 01 absent
# ---------------------------------------------------------------------------
def test_04_candidate_01_replicate_02_blocked_if_replicate_01_absent(tmp_path: Path) -> None:
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 1, 2)
    assert eligible is False
    assert "replicate 1 does not exist" in reason


# ---------------------------------------------------------------------------
# Test 5: Replicate 02 blocked if replicate 01 failed
# ---------------------------------------------------------------------------
def test_05_replicate_02_blocked_if_replicate_01_failed(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=False, completed_at=now - timedelta(hours=2))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)
    assert eligible is False
    assert "replicate 1 failed" in reason


# ---------------------------------------------------------------------------
# Test 6: Replicate 02 blocked before 3600 seconds
# ---------------------------------------------------------------------------
def test_06_replicate_02_blocked_before_3600_seconds(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=True, completed_at=now - timedelta(minutes=30))
    eligible, reason, elapsed = jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)
    assert eligible is False
    assert "spacing rule" in reason
    assert elapsed is not None and elapsed < 3600.0


# ---------------------------------------------------------------------------
# Test 7: Replicate 02 allowed after >=3600 seconds if replicate 01 passed
# ---------------------------------------------------------------------------
def test_07_replicate_02_allowed_after_3600_seconds_if_replicate_01_passed(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=True, completed_at=now - timedelta(seconds=3605))
    eligible, reason, elapsed = jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)
    assert eligible is True
    assert "eligible" in reason
    assert elapsed is not None and elapsed >= 3600.0


# ---------------------------------------------------------------------------
# Test 8: Candidate 02 blocked while candidate 01 is not terminally failed
# ---------------------------------------------------------------------------
def test_08_candidate_02_blocked_while_candidate_01_not_terminally_failed(tmp_path: Path) -> None:
    # Clean state
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1)
    assert eligible is False
    assert "prior candidate 01 has not been attempted" in reason

    # Candidate 1 passed replicate 1, replicate 2 pending
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=True, completed_at=now - timedelta(hours=1))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1, current_time=now)
    assert eligible is False
    assert "replicate 2 is pending" in reason


# ---------------------------------------------------------------------------
# Test 9: Candidate 02 allowed after candidate 01 terminal failure
# ---------------------------------------------------------------------------
def test_09_candidate_02_allowed_after_candidate_01_terminal_failure(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=False, completed_at=now - timedelta(hours=2))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1, current_time=now)
    assert eligible is True


# ---------------------------------------------------------------------------
# Test 10: Candidate 03 follows exact same sequential logic
# ---------------------------------------------------------------------------
def test_10_candidate_03_same_logic(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=False, completed_at=now - timedelta(hours=4))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 3, 1, current_time=now)
    assert eligible is False
    assert "prior candidate 02 has not been attempted" in reason

    _write_mock_manifest(tmp_path, 2, 1, passed=False, completed_at=now - timedelta(hours=2))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 3, 1, current_time=now)
    assert eligible is True


# ---------------------------------------------------------------------------
# Test 11: Later candidate blocked after earlier candidate qualifies
# ---------------------------------------------------------------------------
def test_11_later_candidate_blocked_after_earlier_candidate_qualifies(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=True, completed_at=now - timedelta(hours=3))
    _write_mock_manifest(tmp_path, 1, 2, passed=True, completed_at=now - timedelta(hours=1))

    eligible_c2, reason_c2, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1, current_time=now)
    assert eligible_c2 is False
    assert "already passed both replicates and qualified" in reason_c2

    eligible_c3, reason_c3, _ = jr.evaluate_runner_eligibility(tmp_path, 3, 1, current_time=now)
    assert eligible_c3 is False
    assert "already passed both replicates and qualified" in reason_c3


# ---------------------------------------------------------------------------
# Test 12: Third replicate impossible
# ---------------------------------------------------------------------------
def test_12_third_replicate_impossible(tmp_path: Path) -> None:
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 1, 3)
    assert eligible is False
    assert "only replicates 1 and 2 are permitted" in reason


# ---------------------------------------------------------------------------
# Test 13: Selective probe retry impossible (runner executes all 6 probes sequentially)
# ---------------------------------------------------------------------------
def test_13_selective_probe_retry_impossible(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert len(manifest["probes"]) == 6
    assert [p["probe_number"] for p in manifest["probes"]] == [1, 2, 3, 4, 5, 6]
    assert len(provider.calls) == 6


# ---------------------------------------------------------------------------
# Test 14: Exact six-probe matrix retained
# ---------------------------------------------------------------------------
def test_14_exact_six_probe_matrix_retained() -> None:
    plan = get_synthetic_probe_plan()
    assert len(plan) == 6
    assert plan[0]["answerability"] == "supported"
    assert plan[1]["answerability"] == "supported"
    assert plan[2]["answerability"] == "partially_supported"
    assert plan[3]["answerability"] == "partially_supported"
    assert plan[4]["answerability"] == "insufficient"
    assert plan[4]["expected_insufficiency_label"] == "appropriate_abstention"
    assert plan[5]["answerability"] == "insufficient"
    assert plan[5]["expected_insufficiency_label"] == "appropriate_bounded_insufficiency"


# ---------------------------------------------------------------------------
# Test 15: JSON Mode exactly {"type": "json_object"}
# ---------------------------------------------------------------------------
def test_15_json_mode_exactly_json_object(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["response_format"] == {"type": "json_object"}
    for call in provider.calls:
        assert call["response_format"] == {"type": "json_object"}
        assert "json_schema" not in call["response_format"]


# ---------------------------------------------------------------------------
# Test 16: Timeout exactly 120 seconds
# ---------------------------------------------------------------------------
def test_16_timeout_exactly_120_seconds(tmp_path: Path) -> None:
    assert jr.REPLACEMENT_TIMEOUT_SECONDS == 120.0
    cand = jr.get_candidate(1)
    bad_provider = MockReplacementProvider(cand, _all_results(cand), override_timeout=300.0)
    with pytest.raises(jr.StageCJudgeReplacementError, match="timeout mismatch"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                candidate_number=1,
                replicate_number=1,
                provider=bad_provider,
                manifests_dir=tmp_path,
            )
        )


# ---------------------------------------------------------------------------
# Test 17: 6/6 required for replicate pass
# ---------------------------------------------------------------------------
def test_17_six_of_six_required(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    results = _all_results(cand)
    results[0] = GenerationResult(
        text="invalid non json",
        provider=jr.REPLACEMENT_PROVIDER,
        model=cand.model_id,
        finish_reason="stop",
    )
    provider = MockReplacementProvider(cand, results)
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["successful_probe_count"] == 5
    assert manifest["replicate_passed"] is False
    assert manifest["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 18: Any class failure fails replicate
# ---------------------------------------------------------------------------
def test_18_any_class_failure_fails_replicate(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    results = _all_results(cand)
    bad_payload = _mock_payload(get_synthetic_probe_plan()[4])
    bad_payload["insufficiency_label"] = "wrong_label"
    results[4] = GenerationResult(
        text=json.dumps(bad_payload),
        provider=jr.REPLACEMENT_PROVIDER,
        model=cand.model_id,
        finish_reason="stop",
    )
    provider = MockReplacementProvider(cand, results)
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["per_answerability_summary"]["insufficient"]["json_contract_passed"] is False
    assert manifest["replicate_passed"] is False


# ---------------------------------------------------------------------------
# Test 19: Any timeout fails replicate
# ---------------------------------------------------------------------------
def test_19_any_timeout_fails_replicate(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    results = _all_results(cand)
    results[2] = ProviderUnavailable("Timed out waiting for upstream response", error_type="timeout")
    provider = MockReplacementProvider(cand, results)
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["timeout_occurrences"] == 1
    assert manifest["replicate_passed"] is False


# ---------------------------------------------------------------------------
# Test 20: >120 seconds cannot pass
# ---------------------------------------------------------------------------
def test_20_greater_than_120_seconds_cannot_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cand = jr.get_candidate(1)
    results = _all_results(cand)

    call_count = 0

    def fake_perf_counter() -> float:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return 0.0
        elif call_count == 2:
            return 125.0
        return float(call_count * 5)

    monkeypatch.setattr(jr, "perf_counter", fake_perf_counter)

    provider = MockReplacementProvider(cand, results)
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["probes"][0]["formal_timeout_compatible"] is False
    assert manifest["formal_timeout_compatible"] is False
    assert manifest["replicate_passed"] is False


# ---------------------------------------------------------------------------
# Test 21: Wrong provider-reported model fails
# ---------------------------------------------------------------------------
def test_21_wrong_provider_reported_model_fails(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand, reported_model="wrong/model-name"))
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["replicate_passed"] is False
    assert manifest["successful_probe_count"] == 0


# ---------------------------------------------------------------------------
# Test 22: No raw response stored
# ---------------------------------------------------------------------------
def test_22_no_raw_response_stored(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["raw_response_stored"] is False
    for probe in manifest["probes"]:
        assert probe["raw_response_stored"] is False
        assert "text" not in probe
        assert "response_text" not in probe


# ---------------------------------------------------------------------------
# Test 23: Response hashes stored
# ---------------------------------------------------------------------------
def test_23_response_hashes_stored(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    for probe in manifest["probes"]:
        assert isinstance(probe["response_sha256"], str)
        assert len(probe["response_sha256"]) == 64


# ---------------------------------------------------------------------------
# Test 24: No overwrite
# ---------------------------------------------------------------------------
def test_24_no_overwrite(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    output_path = tmp_path / jr.candidate_manifest_name(1, 1)
    output_path.write_text("existing content", encoding="utf-8")
    provider = MockReplacementProvider(cand, _all_results(cand))
    with pytest.raises(FileExistsError, match="overwrite is prohibited"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                output_path,
                candidate_number=1,
                replicate_number=1,
                provider=provider,
                manifests_dir=tmp_path,
            )
        )


# ---------------------------------------------------------------------------
# Test 25: Output prohibited from formal runs/
# ---------------------------------------------------------------------------
def test_25_output_prohibited_from_formal_runs() -> None:
    forbidden_path = ROOT / "research/experiments/western_formal_v0_1/runs/stage_c_judge_replacement_preflight_v1_candidate_01_replicate_01.json"
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    with pytest.raises(jr.StageCJudgeReplacementError, match="must never enter the formal Stage C runs directory"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                forbidden_path,
                candidate_number=1,
                replicate_number=1,
                provider=provider,
                manifests_dir=ROOT / "research/experiments/western_formal_v0_1/runs",
            )
        )


# ---------------------------------------------------------------------------
# Test 26: Preflight v1/v2/v3 hashes verified
# ---------------------------------------------------------------------------
def test_26_v1_v2_v3_hashes_verified() -> None:
    hashes = jr.verify_scientific_and_historical_hashes(ROOT)
    assert hashes["preflight_v1_sha256"] == jr.R3_PREFLIGHT_V1_READINESS_SHA256 == "4129c0fae0ddf8f8da3d81bc6e18e673bdd71b5d512ff4c97fc01973a530d9e3"
    assert hashes["preflight_v2_sha256"] == jr.R3_PREFLIGHT_V2_READINESS_SHA256 == "1a70f189b52cb9f539807b0f8fa172be6a47ced21d384bcca7db0b81a514df94"
    assert hashes["preflight_v3_sha256"] == jr.R3_PREFLIGHT_V3_READINESS_SHA256 == "b864d2dd45120eade9b7f4ff8688eb35ce7ba9c75262d6eddd365c90dc58b3d2"


# ---------------------------------------------------------------------------
# Test 27: r2 incident hashes verified
# ---------------------------------------------------------------------------
def test_27_r2_incident_hashes_verified() -> None:
    hashes = jr.verify_scientific_and_historical_hashes(ROOT)
    assert hashes["r2_judgments_sha256"] == "fd3544854e4eadfbb498cf9ab5329cee0fb45a03380b25b2c82fabef03ed5363"
    assert hashes["r2_incident_manifest_sha256"] == "24577b182eb9ba0c5a68d88419eac27fab4ab1709f19d850f050ae225dda9531"


# ---------------------------------------------------------------------------
# Test 28: Stage A/B/analysis hashes verified
# ---------------------------------------------------------------------------
def test_28_stage_a_b_analysis_hashes_verified() -> None:
    hashes = jr.verify_scientific_and_historical_hashes(ROOT)
    assert hashes["protocol_v0_1_2_sha256"] == "af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192"
    assert hashes["stage_a_retrieval_sha256"] == "91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e"
    assert hashes["primary_stage_b_sha256"] == "afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c"
    assert hashes["primary_stage_b_run_manifest_sha256"] == "32fbc0765fc91395af187abb46b92d2fb13b9eed3acbea016f8ac18a6bc00511"
    assert hashes["analysis_json_sha256"] == "123322b8a416697cd814561b66b3722291d421206ff6310de6667b9d31b79ec8"


# ---------------------------------------------------------------------------
# Test 29: No formal replacement run/freeze created
# ---------------------------------------------------------------------------
def test_29_no_formal_replacement_run_freeze_created() -> None:
    formal_runs_dir = ROOT / "research/experiments/western_formal_v0_1/runs"
    matching_runs = list(formal_runs_dir.glob("western-formal-v0.1.3*"))
    assert len(matching_runs) == 0, f"Found unexpected formal run: {matching_runs}"

    freeze_dir = ROOT / "research/experiments/western_formal_v0_1" / jr.RESERVED_FORMAL_DIR_NAME
    assert not freeze_dir.exists(), f"Reserved formal execution directory {freeze_dir} must not exist"


# ---------------------------------------------------------------------------
# Test 30: Historical v3 code/schema/prompt behavior unchanged
# ---------------------------------------------------------------------------
def test_30_historical_v3_code_schema_prompt_behavior_unchanged() -> None:
    plan = get_synthetic_probe_plan()
    probe = plan[2]
    retrieval = probe["retrieval"]
    prompt = build_stage_c_r3_json_mode_prompt(
        question=probe["question"],
        answer=probe["answer"],
        retrieved_evidence=probe["evidence"],
        expected_evidence_points=retrieval["expected_evidence_points"],
        answerability=retrieval["answerability"],
    )
    parsed = json.loads(prompt)
    assert "required_output_schema" in parsed
    assert parsed["question"] == probe["question"]

    valid_payload = _mock_payload(probe)
    parsed_output, norm = validate_stage_c_r3_json_mode_probe_output(
        json.dumps(valid_payload),
        retrieval=retrieval,
        expected_insufficiency_label="not_applicable",
        require_all_enums_exercised=True,
    )
    assert isinstance(parsed_output, FormalJudgeOutput)
    assert norm == "none"


# ---------------------------------------------------------------------------
# Test 31: Provider/API not contacted in offline tests
# ---------------------------------------------------------------------------
def test_31_provider_api_not_contacted_in_offline_tests(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_connect(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Network calls prohibited in offline test suite")

    try:
        import socket
        monkeypatch.setattr(socket, "create_connection", fake_connect)
    except Exception:
        pass

    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["replicate_passed"] is True


# ===========================================================================
# NEW ADVERSARIAL HARDENING TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Test 32: DeepSeek outgoing payload contains enable_thinking=false
# ---------------------------------------------------------------------------
def test_32_deepseek_outgoing_payload_contains_enable_thinking_false() -> None:
    assert _supports_thinking_toggle("deepseek-ai/DeepSeek-V3.2") is True
    payload = _chat_payload(
        model="deepseek-ai/DeepSeek-V3.2",
        system="sys",
        prompt="prompt",
        temperature=0.0,
        max_tokens=1200,
        frequency_penalty=0.0,
        response_format={"type": "json_object"},
    )
    assert payload.get("enable_thinking") is False

    provider = OpenAICompatibleLLMProvider(
        api_key="mock-key",
        base_url="https://api.siliconflow.cn/v1",
        model="deepseek-ai/DeepSeek-V3.2",
        timeout=120.0,
        max_tokens=1200,
    )
    assert provider.enable_thinking is False


# ---------------------------------------------------------------------------
# Test 33: Frozen timeout override 119/121/300 rejected
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_timeout", [119.0, 121.0, 300.0, 60.0])
def test_33_timeout_override_rejected(tmp_path: Path, bad_timeout: float) -> None:
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    with pytest.raises(jr.StageCJudgeReplacementError, match="timeout must be exactly 120.0s"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                candidate_number=1,
                replicate_number=1,
                provider=provider,
                manifests_dir=tmp_path,
                timeout_seconds=bad_timeout,
            )
        )


# ---------------------------------------------------------------------------
# Test 34: Canonical manifest directory cannot be bypassed in production
# ---------------------------------------------------------------------------
def test_34_canonical_manifest_dir_cannot_be_bypassed_in_production() -> None:
    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    arbitrary_output = ROOT / "scratch/arbitrary_manifest.json"
    with pytest.raises(jr.StageCJudgeReplacementError, match="Arbitrary output path override is prohibited"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                output_path=arbitrary_output,
                candidate_number=1,
                replicate_number=1,
                provider=provider,
                manifests_dir=None,  # production mode
            )
        )


# ---------------------------------------------------------------------------
# Test 35: Forged replicate_passed=true manifest rejected (fail closed)
# ---------------------------------------------------------------------------
def test_35_forged_replicate_passed_manifest_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    forged = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    # Invalidate one probe while keeping replicate_passed=true
    forged["probes"][0]["json_contract_success"] = False

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(forged, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="json_contract_success is false on passed replicate"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 36: Wrong model ID in prior manifest rejected
# ---------------------------------------------------------------------------
def test_36_wrong_model_id_in_prior_manifest_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["requested_model_id"] = "forged/unregistered-model"

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="requested_model_id mismatch"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 37: Wrong replicate ID in prior manifest rejected
# ---------------------------------------------------------------------------
def test_37_wrong_replicate_id_in_prior_manifest_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["replicate_id"] = "wrong-replicate-id-format"

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="replicate_id mismatch"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 38: Wrong policy version rejected
# ---------------------------------------------------------------------------
def test_38_wrong_policy_version_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["policy_version"] = "forged-policy-v99"

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="policy_version mismatch"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 39: Wrong policy SHA rejected
# ---------------------------------------------------------------------------
def test_39_wrong_policy_sha_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["source_policy_sha256"] = "0" * 64

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="source_policy_sha256 mismatch"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 40: Wrong historical hash rejected
# ---------------------------------------------------------------------------
def test_40_wrong_historical_hash_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["source_historical_and_scientific_hashes"]["protocol_v0_1_2_sha256"] = "bad" + "0" * 61

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="hash mismatch for 'protocol_v0_1_2_sha256'"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 41: Inconsistent 6/6 summary rejected
# ---------------------------------------------------------------------------
def test_41_inconsistent_summary_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["successful_probe_count"] = 5  # Inconsistent with replicate_passed=True

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="successful_probe_count must be 6"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 42: Missing probe rejected
# ---------------------------------------------------------------------------
def test_42_missing_probe_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["probes"].pop()  # Only 5 probes

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="probes array must contain exactly 6 probes"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 43: Altered probe order rejected
# ---------------------------------------------------------------------------
def test_43_altered_probe_order_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    # Swap probes 0 and 1
    manifest_data["probes"][0], manifest_data["probes"][1] = (
        manifest_data["probes"][1],
        manifest_data["probes"][0],
    )

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="probe_number mismatch"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 44: >120s "passed" manifest rejected
# ---------------------------------------------------------------------------
def test_44_greater_than_120s_passed_manifest_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["probes"][0]["latency_ms"] = 125000.0  # > 120,000ms

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="exceeds frozen timeout"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 45: Timeout-containing "passed" manifest rejected
# ---------------------------------------------------------------------------
def test_45_timeout_containing_passed_manifest_rejected(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    manifest_data = _build_valid_manifest(1, 1, passed=True, completed_at=now - timedelta(hours=2))
    manifest_data["timeout_occurrences"] = 1

    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="timeout_occurrences must be 0"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2, current_time=now)


# ---------------------------------------------------------------------------
# Test 46: Malformed JSON manifest fails closed
# ---------------------------------------------------------------------------
def test_46_malformed_json_manifest_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / jr.candidate_manifest_name(1, 1)
    path.write_text("{broken json string", encoding="utf-8")

    with pytest.raises(jr.StageCJudgeReplacementError, match="or malformed JSON manifest"):
        jr.evaluate_runner_eligibility(tmp_path, 1, 2)


# ---------------------------------------------------------------------------
# Test 47: Unexpected internal exception aborts without advancement
# ---------------------------------------------------------------------------
def test_47_unexpected_internal_exception_aborts_without_advancement(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    results = _all_results(cand)
    # Inject an unexpected RuntimeError (e.g. internal bug, not ProviderUnavailable)
    results[2] = RuntimeError("Unexpected internal crash inside provider library")
    provider = MockReplacementProvider(cand, results)

    # Execution must raise RuntimeError and abort
    with pytest.raises(RuntimeError, match="Unexpected internal crash"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                candidate_number=1,
                replicate_number=1,
                provider=provider,
                manifests_dir=tmp_path,
            )
        )

    # Verify no manifest was written to disk
    matching_manifests = list(tmp_path.glob("*.json"))
    assert len(matching_manifests) == 0

    # Verify Candidate 02 is NOT unlocked because Candidate 01 has not terminally failed via manifest
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1)
    assert eligible is False
    assert "prior candidate 01 has not been attempted" in reason


# ---------------------------------------------------------------------------
# Test 48: Expected schema failure still completes all six probes
# ---------------------------------------------------------------------------
def test_48_expected_schema_failure_still_completes_all_six_probes(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)
    results = _all_results(cand)
    # Probe 1 fails with expected malformed JSON
    results[1] = GenerationResult(
        text="invalid non json response",
        provider=jr.REPLACEMENT_PROVIDER,
        model=cand.model_id,
        finish_reason="stop",
    )
    provider = MockReplacementProvider(cand, results)

    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    # All 6 calls completed and diagnostic record preserved
    assert len(provider.calls) == 6
    assert len(manifest["probes"]) == 6
    assert manifest["probes"][1]["json_contract_success"] is False
    assert manifest["probes"][1]["error_type"] == "schema_or_contract_failure"
    assert manifest["replicate_passed"] is False
    assert manifest["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 49: Policy.json one-byte mutation blocks before provider call
# ---------------------------------------------------------------------------
def test_49_policy_json_mutation_blocks_before_provider_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate policy.json having a modified hash
    orig_sha = jr._sha256

    def fake_sha(path: Path) -> str:
        if path.name == "policy.json":
            return "bad" + "0" * 61
        return orig_sha(path)

    monkeypatch.setattr(jr, "_sha256", fake_sha)

    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))

    with pytest.raises(jr.StageCJudgeReplacementError, match="policy.json SHA256 mismatch"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                candidate_number=1,
                replicate_number=1,
                provider=provider,
                manifests_dir=tmp_path,
            )
        )
    # Zero provider calls were made
    assert len(provider.calls) == 0


# ---------------------------------------------------------------------------
# Test 50: Replacement runner rejects a provider reporting differing model ID
# ---------------------------------------------------------------------------
def test_50_replacement_runner_rejects_differing_provider_model(tmp_path: Path) -> None:
    cand = jr.get_candidate(1)

    results = _all_results(cand, reported_model="some/other-model")
    provider = MockReplacementProvider(cand, results)

    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            candidate_number=1,
            replicate_number=1,
            provider=provider,
            manifests_dir=tmp_path,
        )
    )
    assert manifest["replicate_passed"] is False
    assert manifest["status"] == "failed"
    for probe in manifest["probes"]:
        assert probe["error_type"] == "model_identity_mismatch"
        assert probe["provider_reported_model"] == "some/other-model"
        assert "expected 'deepseek-ai/DeepSeek-V3.2', got 'some/other-model'" in probe["error_message"]


# ---------------------------------------------------------------------------
# Test 51: Real OpenAICompatibleLLMProvider extracts provider response model
# ---------------------------------------------------------------------------
def test_51_openai_compatible_provider_model_extraction_in_preflight(tmp_path: Path) -> None:
    from providers.openai_compatible import OpenAICompatibleLLMProvider
    OpenAICompatibleLLMProvider._shared_http_client = None

    class MockResponse:
        def __init__(self, data: dict) -> None:
            self._data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._data

    class MockClient:
        def __init__(self, response_model: str) -> None:
            self.response_model = response_model
            self.call_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *args: Any, **kwargs: Any) -> MockResponse:
            self.call_count += 1
            probe_spec = get_synthetic_probe_plan()[self.call_count - 1]
            content = json.dumps(_mock_payload(probe_spec))
            return MockResponse({
                "model": self.response_model,
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100},
            })

    # Case A: Provider returns substituted/aliased model "some/other-model"
    mock_client_sub = MockClient(response_model="some/other-model")
    OpenAICompatibleLLMProvider._shared_http_client = mock_client_sub

    real_provider_sub = OpenAICompatibleLLMProvider(
        api_key="unit-test-key",
        base_url="https://api.siliconflow.cn/v1",
        model="deepseek-ai/DeepSeek-V3.2",
        timeout=120.0,
        max_tokens=1200,
        provider_name="siliconflow",
    )

    try:
        manifest_sub = asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                candidate_number=1,
                replicate_number=1,
                provider=real_provider_sub,
                manifests_dir=tmp_path / "sub",
            )
        )
        assert manifest_sub["replicate_passed"] is False
        assert manifest_sub["probes"][0]["error_type"] == "model_identity_mismatch"
        assert manifest_sub["probes"][0]["provider_reported_model"] == "some/other-model"

        # Case B: Provider returns exact requested model "deepseek-ai/DeepSeek-V3.2"
        mock_client_exact = MockClient(response_model="deepseek-ai/DeepSeek-V3.2")
        OpenAICompatibleLLMProvider._shared_http_client = mock_client_exact

        real_provider_exact = OpenAICompatibleLLMProvider(
            api_key="unit-test-key",
            base_url="https://api.siliconflow.cn/v1",
            model="deepseek-ai/DeepSeek-V3.2",
            timeout=120.0,
            max_tokens=1200,
            provider_name="siliconflow",
        )

        manifest_exact = asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                candidate_number=1,
                replicate_number=1,
                provider=real_provider_exact,
                manifests_dir=tmp_path / "exact",
            )
        )
        assert manifest_exact["replicate_passed"] is True
        assert manifest_exact["status"] == "passed"
        assert manifest_exact["probes"][0]["provider_reported_model"] == "deepseek-ai/DeepSeek-V3.2"
        assert manifest_exact["probes"][0]["json_contract_success"] is True
    finally:
        OpenAICompatibleLLMProvider._shared_http_client = None

