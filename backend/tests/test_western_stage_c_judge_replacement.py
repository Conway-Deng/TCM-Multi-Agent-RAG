from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable
from western import formal_eval as f
from western import stage_c_judge_replacement as jr
from western.formal_judge import FormalJudgeOutput, JUDGE_SYSTEM_PROMPT
from western.stage_c_preflight import (
    R3_PREFLIGHT_PROBE_COUNT,
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


def _write_mock_manifest(
    manifests_dir: Path,
    candidate_number: int,
    replicate_number: int,
    passed: bool,
    completed_at: datetime,
) -> Path:
    cand = jr.get_candidate(candidate_number)
    filename = jr.candidate_manifest_name(candidate_number, replicate_number)
    path = manifests_dir / filename
    manifest_data = {
        "policy_version": jr.REPLACEMENT_POLICY_VERSION,
        "candidate_number": candidate_number,
        "candidate_slug": cand.slug,
        "requested_model_id": cand.model_id,
        "replicate_number": replicate_number,
        "replicate_id": jr.candidate_replicate_id(candidate_number, replicate_number),
        "status": "passed" if passed else "failed",
        "replicate_passed": passed,
        "completed_at": completed_at.isoformat(),
    }
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

    # Verify tuple is immutable
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
    # Subcase A: Clean state (candidate 1 not attempted)
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1)
    assert eligible is False
    assert "prior candidate 01 has not been attempted" in reason

    # Subcase B: Candidate 1 passed replicate 1, replicate 2 pending
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=True, completed_at=now - timedelta(hours=1))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1, current_time=now)
    assert eligible is False
    assert "replicate 2 is pending" in reason


# ---------------------------------------------------------------------------
# Test 9: Candidate 02 allowed after candidate 01 terminal failure
# ---------------------------------------------------------------------------
def test_09_candidate_02_allowed_after_candidate_01_terminal_failure(tmp_path: Path) -> None:
    # Subcase A: Candidate 1 failed replicate 1
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=False, completed_at=now - timedelta(hours=2))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1, current_time=now)
    assert eligible is True

    # Subcase B: Candidate 1 passed replicate 1 but failed replicate 2
    _write_mock_manifest(tmp_path, 1, 1, passed=True, completed_at=now - timedelta(hours=3))
    _write_mock_manifest(tmp_path, 1, 2, passed=False, completed_at=now - timedelta(hours=1))
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1, current_time=now)
    assert eligible is True


# ---------------------------------------------------------------------------
# Test 10: Candidate 03 follows exact same sequential logic
# ---------------------------------------------------------------------------
def test_10_candidate_03_same_logic(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _write_mock_manifest(tmp_path, 1, 1, passed=False, completed_at=now - timedelta(hours=4))
    # Candidate 2 not attempted yet -> Candidate 3 blocked
    eligible, reason, _ = jr.evaluate_runner_eligibility(tmp_path, 3, 1, current_time=now)
    assert eligible is False
    assert "prior candidate 02 has not been attempted" in reason

    # Candidate 2 terminally fails -> Candidate 3 allowed
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

    # Candidate 2 blocked
    eligible_c2, reason_c2, _ = jr.evaluate_runner_eligibility(tmp_path, 2, 1, current_time=now)
    assert eligible_c2 is False
    assert "already passed both replicates and qualified" in reason_c2

    # Candidate 3 blocked
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
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    # If provider timeout is not 120, validation fails
    bad_provider = MockReplacementProvider(cand, _all_results(cand), override_timeout=300.0)
    output_path = tmp_path / "manifest.json"
    with pytest.raises(jr.StageCJudgeReplacementError, match="timeout mismatch"):
        asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                output_path,
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
    # Make probe 0 return invalid JSON
    results[0] = GenerationResult(
        text="invalid non json",
        provider=jr.REPLACEMENT_PROVIDER,
        model=cand.model_id,
        finish_reason="stop",
    )
    provider = MockReplacementProvider(cand, results)
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    # Make probe 4 (insufficient 1) have wrong insufficiency label
    bad_payload = _mock_payload(get_synthetic_probe_plan()[4])
    bad_payload["insufficiency_label"] = "wrong_label"
    results[4] = GenerationResult(
        text=json.dumps(bad_payload),
        provider=jr.REPLACEMENT_PROVIDER,
        model=cand.model_id,
        finish_reason="stop",
    )
    provider = MockReplacementProvider(cand, results)
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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

    # Monkeypatch perf_counter to simulate >120s latency on probe 1
    call_count = 0

    def fake_perf_counter() -> float:
        nonlocal call_count
        call_count += 1
        # probe 1 takes 125 seconds
        if call_count == 1:
            return 0.0
        elif call_count == 2:
            return 125.0
        return float(call_count * 5)

    monkeypatch.setattr(jr, "perf_counter", fake_perf_counter)

    provider = MockReplacementProvider(cand, results)
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    # Provider reports wrong model string
    provider = MockReplacementProvider(cand, _all_results(cand, reported_model="wrong/model-name"))
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    output_path = tmp_path / "manifest.json"
    manifest = asyncio.run(
        jr.run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
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
    output_path = tmp_path / "manifest.json"
    output_path.write_text("existing content", encoding="utf-8")
    cand = jr.get_candidate(1)
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
    forbidden_path = ROOT / "research/experiments/western_formal_v0_1/runs/manifest.json"
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

    # Validate output validator still works identically
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
def test_31_provider_api_not_contacted_in_offline_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure any attempt to call httpx or socket would fail
    def fake_connect(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Network calls prohibited in offline test suite")

    try:
        import socket
        monkeypatch.setattr(socket, "create_connection", fake_connect)
    except Exception:
        pass

    cand = jr.get_candidate(1)
    provider = MockReplacementProvider(cand, _all_results(cand))
    tmp_file = ROOT / "scratch_test_manifest.tmp"
    try:
        manifest = asyncio.run(
            jr.run_stage_c_judge_replacement_preflight(
                ROOT,
                tmp_file,
                candidate_number=1,
                replicate_number=1,
                provider=provider,
                manifests_dir=ROOT,
            )
        )
        assert manifest["replicate_passed"] is True
    finally:
        if tmp_file.exists():
            tmp_file.unlink()
