from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable
from western import formal_eval as f
from western.formal_judge import normalize_judge_json_envelope, parse_judge_output


ROOT = Path(__file__).resolve().parents[2]


def _retrieval(answerability: str = "supported", point_count: int = 1) -> dict[str, object]:
    return {
        "experiment_id": "synthetic:R0",
        "answerability": answerability,
        "expected_evidence_points": [f"point-{index}" for index in range(point_count)],
    }


def _payload(answerability: str = "supported", point_count: int = 1) -> dict[str, object]:
    partial = answerability == "partially_supported"
    return {
        "claim_labels": [{
            "claim_id": "c1", "claim": "Synthetic claim.", "label": "supported",
            "justification": "Supported by the supplied evidence.",
        }],
        "evidence_point_labels": [
            {"point_index": index, "label": "covered", "justification": "Included."}
            for index in range(point_count)
        ],
        "insufficiency_label": "appropriate_bounded_insufficiency" if answerability == "insufficient" else "not_applicable",
        "stays_within_supported_evidence": True if partial else None,
        "preserves_uncertainty": True if partial else None,
        "invented_unsupported_information": False if partial else None,
        "diagnosis_like_personalized_statement": False,
        "individualized_dosing": False,
        "prescription_like_recommendation": False,
        "research_or_educational_limitation_preserved": True,
    }


def _result(text: str, *, finish_reason: str | None = "stop") -> GenerationResult:
    return GenerationResult(
        text=text, provider=f.JUDGE_PROVIDER, model=f.JUDGE_MODEL, finish_reason=finish_reason,
    )


class ScriptedJudge:
    def __init__(self, values: list[object]) -> None:
        self.values = list(values)
        self.calls = 0

    async def generate(self) -> GenerationResult:
        self.calls += 1
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[return-value]


def _invoke(judge: ScriptedJudge, retrieval: dict[str, object] | None = None) -> f.StageCJudgeOutcome:
    return asyncio.run(f.invoke_stage_c_judgment(judge.generate, retrieval or _retrieval()))


@pytest.mark.parametrize(
    ("envelope", "expected_status"),
    [
        ("{payload}", "none"),
        ("```json\n{payload}\n```", "outer_json_markdown_fence_removed"),
        ("```\n{payload}\n```", "outer_json_markdown_fence_removed"),
        (" \n```json\n{payload}\n```\n ", "outer_json_markdown_fence_removed"),
    ],
)
def test_allowed_json_envelopes_are_deterministic(envelope: str, expected_status: str) -> None:
    raw = json.dumps(_payload())
    normalized, status = normalize_judge_json_envelope(envelope.format(payload=raw))
    assert status == expected_status
    assert json.loads(normalized) == json.loads(raw)
    assert parse_judge_output(envelope.format(payload=raw)).claim_labels[0].claim_id == "c1"


@pytest.mark.parametrize(
    "wrapped",
    [
        "Here is the answer:\n```json\n{payload}\n```",
        "```json\n{payload}\n```\nDone.",
        "```json\n{payload}\n```\n```json\n{payload}\n```",
        "```json\n```\n{payload}\n```\n```",
        "```json\n{payload}",
    ],
)
def test_prose_multiple_nested_and_incomplete_fences_are_rejected(wrapped: str) -> None:
    with pytest.raises(ValueError, match="valid JSON"):
        parse_judge_output(wrapped.format(payload=json.dumps(_payload())))


def test_fenced_success_records_normalization_without_retry() -> None:
    raw = json.dumps(_payload())
    judge = ScriptedJudge([_result(f"```json\n{raw}\n```")])
    outcome = _invoke(judge)
    assert outcome.judge_success is True
    assert outcome.output_normalization == "outer_json_markdown_fence_removed"
    assert outcome.attempt_count == 1 and judge.calls == 1


def test_raw_success_records_none_normalization() -> None:
    judge = ScriptedJudge([_result(json.dumps(_payload()))])
    outcome = _invoke(judge)
    assert outcome.judge_success is True
    assert outcome.output_normalization == "none"


@pytest.mark.parametrize("text", ["```json\n{broken}\n```", "not-json"])
def test_malformed_model_json_does_not_retry_and_preserves_known_normalization(text: str) -> None:
    judge = ScriptedJudge([_result(text)])
    outcome = _invoke(judge)
    assert outcome.judge_outcome == "output_schema_failure"
    expected = "outer_json_markdown_fence_removed" if text.startswith("```") else "none"
    assert outcome.output_normalization == expected
    assert judge.calls == 1


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_schema_invalid_fenced_json_does_not_retry(mutation: str) -> None:
    payload = _payload()
    if mutation == "missing":
        payload.pop("preserves_uncertainty")
    else:
        payload["extra"] = True
    judge = ScriptedJudge([_result(f"```json\n{json.dumps(payload)}\n```")])
    outcome = _invoke(judge)
    assert outcome.judge_outcome == "output_schema_failure"
    assert outcome.output_normalization == "outer_json_markdown_fence_removed"
    assert judge.calls == 1


@pytest.mark.parametrize("error_type", ["connectivity", "timeout", "http_5xx"])
def test_transport_retry_policy_is_unchanged(error_type: str) -> None:
    judge = ScriptedJudge([
        ProviderUnavailable("temporary", error_type=error_type),
        _result(json.dumps(_payload())),
    ])
    outcome = _invoke(judge)
    assert outcome.judge_success is True
    assert outcome.attempt_count == 2 and judge.calls == 2


def test_rate_limit_and_length_remain_terminal_without_retry() -> None:
    limited = ScriptedJudge([ProviderUnavailable("limited", error_type="rate_limit")])
    assert _invoke(limited).judge_outcome == "rate_limit"
    assert limited.calls == 1
    truncated = ScriptedJudge([_result(json.dumps(_payload()), finish_reason="length")])
    assert _invoke(truncated).judge_outcome == "truncated_response"
    assert truncated.calls == 1


def _record(normalization: str | None = "none") -> dict[str, object]:
    payload = _payload()
    return {
        "experiment_id": "synthetic:R0", "judge_success": True, "final_judge_success": True,
        "judge_outcome": "completed", "judge_first_attempt_success": True,
        "judge_attempt_count": 1, "judge_technical_retry_used": False,
        "judge_first_error_type": None, "judge_final_error_type": None,
        "judge_provider_reported_model": f.JUDGE_MODEL, "judge_finish_reason": "stop",
        "judge_latency_ms": 1.0, "judge_output_normalization": normalization,
        "claim_labels": payload["claim_labels"], "evidence_point_labels": payload["evidence_point_labels"],
        "insufficiency_label": payload["insufficiency_label"],
        "stays_within_supported_evidence": payload["stays_within_supported_evidence"],
        "preserves_uncertainty": payload["preserves_uncertainty"],
        "invented_unsupported_information": payload["invented_unsupported_information"],
        "observable_safety_flags": {
            key: payload[key] for key in (
                "diagnosis_like_personalized_statement", "individualized_dosing",
                "prescription_like_recommendation", "research_or_educational_limitation_preserved",
            )
        },
        "upstream_failure": None, "errors": [], "timestamps": {"judge_completed_at": "test"},
    }


@pytest.mark.parametrize("normalization", ["none", "outer_json_markdown_fence_removed"])
def test_successful_record_accepts_only_preregistered_normalization_values(normalization: str) -> None:
    f._validate_stage_c_record(_retrieval(), {"experiment_id": "synthetic:R0"}, _record(normalization))


def test_failure_null_invalid_enum_and_missing_normalization_validation() -> None:
    upstream = _record(None)
    upstream.update({
        "judge_success": False, "final_judge_success": False,
        "judge_outcome": "upstream_generation_failure", "judge_first_attempt_success": False,
        "judge_attempt_count": 0, "judge_provider_reported_model": None,
        "judge_finish_reason": None, "judge_latency_ms": 0.0,
        "claim_labels": [], "evidence_point_labels": [], "observable_safety_flags": {},
        "upstream_failure": {"source_stage": "B"},
    })
    f._validate_stage_c_record(_retrieval(), {"experiment_id": "synthetic:R0"}, upstream)
    invalid = _record("invalid")
    with pytest.raises(f.FatalFormalRunError, match="normalization"):
        f._validate_stage_c_record(_retrieval(), {"experiment_id": "synthetic:R0"}, invalid)
    missing = _record()
    missing.pop("judge_output_normalization")
    with pytest.raises(f.FatalFormalRunError, match="missing fields"):
        f._validate_stage_c_record(_retrieval(), {"experiment_id": "synthetic:R0"}, missing)


def test_resume_validation_requires_normalization_field(tmp_path: Path) -> None:
    retrieval = _retrieval()
    generation = {"experiment_id": "synthetic:R0"}
    stage_c = f.StageCDirectory(tmp_path / f.STAGE_C_RUN_ID)
    stage_c.path.mkdir(parents=True)
    record = _record()
    record.pop("judge_output_normalization")
    stage_c.stage_path().write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(f.FatalFormalRunError, match="missing fields"):
        f._validated_existing_stage_c_records(stage_c, [retrieval], [generation])


def test_provider_metrics_account_for_normalization() -> None:
    rows = [_record("none"), dict(_record("outer_json_markdown_fence_removed"), experiment_id="synthetic:R1")]
    metrics = f.stage_c_provider_metrics(rows)
    assert metrics["output_normalization_counts"] == {
        "none": 1, "outer_json_markdown_fence_removed": 1, "null": 0,
    }


def test_r2_identity_is_prospective_and_has_no_formal_run_directory() -> None:
    assert f.STAGE_C_RUN_ID == "western-formal-v0.1.2-stage-c-r2-20260920-01"
    assert f.STAGE_C_EXECUTION_VERSION == "western-stage-c-execution-v0.1.2-r2"
    runs = ROOT / "research/experiments/western_formal_v0_1/runs"
    assert not (runs / "western-formal-v0.1.2-stage-c-r1-20260919-01").exists()
    assert not (runs / f.STAGE_C_RUN_ID).exists()


def test_superseded_r1_run_id_cannot_use_the_r2_formal_path(tmp_path: Path) -> None:
    with pytest.raises(f.FatalFormalRunError, match="exact run ID"):
        f.StageCDirectory(tmp_path / "western-formal-v0.1.2-stage-c-r1-20260919-01")
