from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from providers.base import GenerationResult
from providers.openai_compatible import ProviderUnavailable
from western import formal_eval as f
from western.formal_judge import FormalJudgeOutput


ROOT = Path(__file__).resolve().parents[2]


def _analysis() -> dict[str, object]:
    return f._expected_stage_c_analysis_plan()


def _execution_config() -> dict[str, object]:
    analysis = _analysis()
    return {
        "execution_version": f.STAGE_C_EXECUTION_VERSION,
        "stage_c_run_id": f.STAGE_C_RUN_ID,
        "protocol_version": f.PROTOCOL_VERSION,
        "protocol_sha256": f.PROTOCOL_SHA256,
        "stage_a_run_id": f.STAGE_A_RUN_ID,
        "stage_a_checkpoint_commit": f.STAGE_A_CHECKPOINT_COMMIT,
        "stage_a_retrieval_sha256": f.STAGE_A_RETRIEVAL_SHA256,
        "primary_stage_b_run_id": f.STAGE_B_REPEAT_RUN_ID,
        "primary_stage_b_sha256": f.PRIMARY_STAGE_B_SHA256,
        "primary_stage_b_seal_manifest_sha256": f.PRIMARY_STAGE_B_SEAL_SHA256,
        "primary_stage_b_raw_sha256": f.PRIMARY_STAGE_B_SHA256,
        "primary_stage_b_execution_manifest_sha256": f.PRIMARY_STAGE_B_EXECUTION_MANIFEST_SHA256,
        "primary_stage_b_readiness_manifest_sha256": f.PRIMARY_STAGE_B_READINESS_MANIFEST_SHA256,
        "primary_stage_b_incident_manifest_sha256": f.PRIMARY_STAGE_B_INCIDENT_MANIFEST_SHA256,
        "primary_stage_b_run_manifest_sha256": f.PRIMARY_STAGE_B_RUN_MANIFEST_SHA256,
        "repeat_execution_freeze_commit": "d68df8018798219b2bcf8dd36ee067dedbf66dfc",
        "repeat_execution_json_sha256": "de06ad2c834c287fa0d6715c45c56c26147fdc9ee697f68d7fa2d78a314e2617",
        "provider": f.JUDGE_PROVIDER,
        "model": f.JUDGE_MODEL,
        "temperature": f.JUDGE_TEMPERATURE,
        "max_tokens": f.JUDGE_MAX_TOKENS,
        "timeout_seconds": f.JUDGE_TIMEOUT_SECONDS,
        "enable_thinking": False,
        "intended_cell_count": f.INTENDED_CELLS,
        "analysis_sha256": f._canonical_json_sha256(analysis),
        "scientific_sha256": f._stage_c_scientific_sha256(ROOT),
        "outcome_enum": sorted(f.STAGE_C_OUTCOMES),
        "implementation_commit": "1" * 40,
        "implementation_sha256": {
            "backend/western/formal_eval.py": f._sha256(ROOT / "backend/western/formal_eval.py"),
            "backend/western/formal_judge.py": f._sha256(ROOT / "backend/western/formal_judge.py"),
        },
    }


def _freeze_kwargs() -> dict[str, object]:
    return {
        "expected_execution_commit": f._git_head(ROOT),
        "require_clean_worktree": False,
        "execution_config": _execution_config(),
        "analysis_config": _analysis(),
    }


def _frozen_inputs() -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    cases = f.load_frozen_cases(ROOT)
    cases_by_id = {case["case_id"]: case for case in cases}
    order = f.load_frozen_execution_order(ROOT, cases)
    stage_a: list[dict[str, object]] = []
    stage_b: list[dict[str, object]] = []
    for cell in order:
        case = cases_by_id[cell["case_id"]]
        retrieval = {
            "experiment_id": cell["experiment_id"],
            "case_id": cell["case_id"],
            "retrieval_condition": cell["retrieval_condition"],
            "question": case["question"],
            "topic": case["topic"],
            "answerability": case["answerability"],
            "expected_evidence_points": case["expected_evidence_points"],
            "gold_primary_chunk_ids": case["gold_chunk_ids"],
            "gold_primary_source_ids": case["gold_source_ids"],
            "gold_secondary_chunk_ids": case["optional_secondary_chunk_ids"],
            "retrieval_success": True,
            "retrieved_items": [],
            "retrieval_latency_ms": 1.0,
            "errors": [],
            "timestamps": {},
        }
        stage_a.append(retrieval)
        stage_b.append({
            "experiment_id": cell["experiment_id"],
            "generation_success": True,
            "final_generation_success": True,
            "generation_outcome": "completed",
            "first_attempt_success": True,
            "attempt_count": 1,
            "technical_retry_used": False,
            "first_error_type": None,
            "final_error_type": None,
            "generation_latency_ms": 1.0,
            "answer": "A synthetic non-empty answer.",
            "provenance": [],
            "provider_reported_model": f.GENERATOR_MODEL,
            "errors": [],
            "timestamps": {},
        })
    manifest = {
        "status": "stage_b_repeat_frozen_primary",
        "repeat_outage_classification": {"run_level_outage": False},
    }
    return stage_a, stage_b, manifest


def _judge_payload(retrieval: dict[str, object]) -> dict[str, object]:
    partial = retrieval["answerability"] == "partially_supported"
    insufficient = retrieval["answerability"] == "insufficient"
    return {
        "claim_labels": [{
            "claim_id": "c1", "claim": "Synthetic claim.", "label": "supported",
            "justification": "The supplied evidence supports it.",
        }],
        "evidence_point_labels": [
            {"point_index": index, "label": "covered", "justification": "Included."}
            for index, _ in enumerate(retrieval["expected_evidence_points"])
        ],
        "insufficiency_label": "appropriate_bounded_insufficiency" if insufficient else "not_applicable",
        "stays_within_supported_evidence": True if partial else None,
        "preserves_uncertainty": True if partial else None,
        "invented_unsupported_information": False if partial else None,
        "diagnosis_like_personalized_statement": False,
        "individualized_dosing": False,
        "prescription_like_recommendation": False,
        "research_or_educational_limitation_preserved": True,
    }


def _completed_record(retrieval: dict[str, object]) -> dict[str, object]:
    payload = _judge_payload(retrieval)
    return {
        "experiment_id": retrieval["experiment_id"],
        "judge_success": True,
        "final_judge_success": True,
        "judge_outcome": "completed",
        "judge_first_attempt_success": True,
        "judge_attempt_count": 1,
        "judge_technical_retry_used": False,
        "judge_first_error_type": None,
        "judge_final_error_type": None,
        "judge_provider_reported_model": f.JUDGE_MODEL,
        "judge_finish_reason": "stop",
        "judge_latency_ms": 1.0,
        "claim_labels": payload["claim_labels"],
        "evidence_point_labels": payload["evidence_point_labels"],
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
        "upstream_failure": None,
        "errors": [],
        "timestamps": {"judge_completed_at": "test"},
    }


class ScriptedJudge:
    name = f.JUDGE_PROVIDER
    model = f.JUDGE_MODEL
    timeout = f.JUDGE_TIMEOUT_SECONDS
    max_tokens = f.JUDGE_MAX_TOKENS
    enable_thinking = False
    api_key = "offline-test"

    def __init__(self, script: list[object] | None = None) -> None:
        self.script = list(script or [])
        self.calls = 0

    async def generate(self, **kwargs: object) -> GenerationResult:
        if kwargs:
            assert kwargs["temperature"] == 0.0
            assert kwargs["max_tokens"] == 1200
        self.calls += 1
        value = self.script.pop(0)
        if isinstance(value, Exception):
            raise value
        return value  # type: ignore[return-value]


def _result(payload: dict[str, object], *, finish_reason: str | None = "stop", model: str = f.JUDGE_MODEL) -> GenerationResult:
    return GenerationResult(
        text=json.dumps(payload), provider=f.JUDGE_PROVIDER, model=model,
        finish_reason=finish_reason,
    )


def _prepare_complete_stage_c(tmp_path: Path) -> tuple[f.StageCDirectory, tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]]:
    frozen = _frozen_inputs()
    stage_a, stage_b, _ = frozen
    stage_c = f.StageCDirectory(tmp_path / f.STAGE_C_RUN_ID)
    stage_c.path.mkdir(parents=True)
    anchor = f.verify_stage_c_execution_freeze(ROOT, **_freeze_kwargs())
    f._atomic_new_json(stage_c.execution_manifest_path(), f._stage_c_execution_manifest_payload(anchor))
    rows = [_completed_record(retrieval) for retrieval in stage_a]
    stage_c.stage_path().write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8",
    )
    stage_c.seal([row["experiment_id"] for row in stage_b])
    return stage_c, frozen


def test_stage_c_freeze_rejects_wrong_head_dirty_tree_and_analysis_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _execution_config()
    analysis = _analysis()
    with pytest.raises(f.FatalFormalRunError, match="requires execution freeze HEAD"):
        f.verify_stage_c_execution_freeze(
            ROOT, expected_execution_commit="0" * 40, require_clean_worktree=False,
            execution_config=config, analysis_config=analysis,
        )
    monkeypatch.setattr(f, "_git_worktree_clean", lambda root: False)
    with pytest.raises(f.FatalFormalRunError, match="clean Git working tree"):
        f.verify_stage_c_execution_freeze(
            ROOT, expected_execution_commit=f._git_head(ROOT), require_clean_worktree=True,
            execution_config=config, analysis_config=analysis,
        )
    bad = dict(analysis)
    bad["analysis_version"] = "changed"
    with pytest.raises(f.FatalFormalRunError, match="preregistered plan"):
        f.verify_stage_c_execution_freeze(
            ROOT, expected_execution_commit=f._git_head(ROOT), require_clean_worktree=False,
            execution_config=config, analysis_config=bad,
        )


def test_primary_stage_b_and_original_incident_exact_anchors_are_valid() -> None:
    stage_a, stage_b, manifest = f._verify_primary_stage_b_inputs(ROOT)
    assert len(stage_a) == len(stage_b) == 192
    assert manifest["status"] == "stage_b_repeat_frozen_primary"
    assert manifest["repeat_outage_classification"]["run_level_outage"] is False


def test_exact_stage_c_run_id_is_required(tmp_path: Path) -> None:
    with pytest.raises(f.FatalFormalRunError, match="exact run ID"):
        f.StageCDirectory(tmp_path / "wrong")


def test_judge_contract_forbids_extra_fields_and_requires_scope_keys() -> None:
    retrieval = _frozen_inputs()[0][0]
    payload = _judge_payload(retrieval)
    extra = dict(payload, extra_field=True)
    with pytest.raises(ValueError):
        FormalJudgeOutput.model_validate(extra)
    missing = dict(payload)
    missing.pop("stays_within_supported_evidence")
    with pytest.raises(ValueError):
        FormalJudgeOutput.model_validate(missing)


def test_evidence_point_claim_partial_and_insufficiency_contracts() -> None:
    stage_a, _, _ = _frozen_inputs()
    supported = next(row for row in stage_a if row["answerability"] == "supported" and row["expected_evidence_points"])
    partial = next(row for row in stage_a if row["answerability"] == "partially_supported")
    insufficient = next(row for row in stage_a if row["answerability"] == "insufficient")
    parsed = FormalJudgeOutput.model_validate(_judge_payload(supported))
    f._validate_completed_judge_output(parsed, supported)
    for mutation, message in (
        (lambda p: p.update(evidence_point_labels=[]), "Evidence-point"),
        (lambda p: p.update(claim_labels=[]), "claim label"),
        (lambda p: p["claim_labels"].append(dict(p["claim_labels"][0])), "unique"),
    ):
        payload = _judge_payload(supported)
        mutation(payload)
        with pytest.raises(f.StageCOutputSchemaError, match=message):
            f._validate_completed_judge_output(FormalJudgeOutput.model_validate(payload), supported)
    partial_payload = _judge_payload(partial)
    partial_payload["preserves_uncertainty"] = None
    with pytest.raises(f.StageCOutputSchemaError, match="scope Booleans"):
        f._validate_completed_judge_output(FormalJudgeOutput.model_validate(partial_payload), partial)
    supported_payload = _judge_payload(supported)
    supported_payload["stays_within_supported_evidence"] = True
    with pytest.raises(f.StageCOutputSchemaError, match="null scope"):
        f._validate_completed_judge_output(FormalJudgeOutput.model_validate(supported_payload), supported)
    insufficient_payload = _judge_payload(insufficient)
    insufficient_payload["insufficiency_label"] = "not_applicable"
    with pytest.raises(f.StageCOutputSchemaError, match="cannot be not_applicable"):
        f._validate_completed_judge_output(FormalJudgeOutput.model_validate(insufficient_payload), insufficient)


@pytest.mark.parametrize(
    ("finish_reason", "expected"),
    [("length", "truncated_response"), ("content_filter", "nonretryable_provider_failure")],
)
def test_finish_reason_failures_are_terminal_without_retry(finish_reason: str, expected: str) -> None:
    retrieval = _frozen_inputs()[0][0]
    judge = ScriptedJudge([_result(_judge_payload(retrieval), finish_reason=finish_reason)])
    outcome = asyncio.run(f.invoke_stage_c_judgment(lambda: judge.generate(), retrieval))
    assert outcome.judge_outcome == expected
    assert judge.calls == 1 and outcome.technical_retry_used is False


def test_missing_finish_reason_is_allowed_when_output_valid() -> None:
    retrieval = _frozen_inputs()[0][0]
    judge = ScriptedJudge([_result(_judge_payload(retrieval), finish_reason=None)])
    outcome = asyncio.run(f.invoke_stage_c_judgment(lambda: judge.generate(), retrieval))
    assert outcome.judge_success is True and outcome.provider_result.finish_reason is None


def test_malformed_model_json_and_schema_invalid_json_are_not_retried() -> None:
    retrieval = _frozen_inputs()[0][0]
    malformed = GenerationResult(text="not-json", provider=f.JUDGE_PROVIDER, model=f.JUDGE_MODEL, finish_reason="stop")
    invalid = _judge_payload(retrieval)
    invalid["claim_labels"] = []
    for result in (malformed, _result(invalid)):
        judge = ScriptedJudge([result])
        outcome = asyncio.run(f.invoke_stage_c_judgment(lambda: judge.generate(), retrieval))
        assert outcome.judge_outcome == "output_schema_failure"
        assert judge.calls == 1


@pytest.mark.parametrize("error_type", ["connectivity", "timeout", "http_5xx", "malformed_response"])
def test_retryable_transport_errors_retry_once(error_type: str) -> None:
    retrieval = _frozen_inputs()[0][0]
    judge = ScriptedJudge([
        ProviderUnavailable("temporary", error_type=error_type),
        _result(_judge_payload(retrieval)),
    ])
    outcome = asyncio.run(f.invoke_stage_c_judgment(lambda: judge.generate(), retrieval))
    assert outcome.judge_success is True
    assert outcome.attempt_count == 2 and outcome.technical_retry_used is True


def test_rate_limit_no_retry_and_auth_is_fatal() -> None:
    retrieval = _frozen_inputs()[0][0]
    rate = ScriptedJudge([ProviderUnavailable("limited", error_type="rate_limit")])
    outcome = asyncio.run(f.invoke_stage_c_judgment(lambda: rate.generate(), retrieval))
    assert outcome.judge_outcome == "rate_limit" and rate.calls == 1
    auth = ScriptedJudge([ProviderUnavailable("bad key", error_type="authentication")])
    with pytest.raises(f.FatalFormalRunError, match="configuration/authentication"):
        asyncio.run(f.invoke_stage_c_judgment(lambda: auth.generate(), retrieval))


def test_wrong_provider_model_settings_and_thinking_are_rejected() -> None:
    for attribute, value in (("model", "wrong"), ("timeout", 30.0), ("max_tokens", 100), ("enable_thinking", True)):
        judge = ScriptedJudge([])
        setattr(judge, attribute, value)
        with pytest.raises(f.FatalFormalRunError):
            f._validate_formal_judge_provider(judge)
    for missing in ("name", "model", "timeout", "max_tokens", "enable_thinking", "api_key"):
        judge = ScriptedJudge([])
        delattr(judge, missing) if missing in judge.__dict__ else setattr(judge, missing, None)
        with pytest.raises(f.FatalFormalRunError):
            f._validate_formal_judge_provider(judge)


def test_fresh_execution_creates_manifest_and_exact_seal(tmp_path: Path) -> None:
    frozen = _frozen_inputs()
    script = [_result(_judge_payload(retrieval)) for retrieval in frozen[0]]
    judge = ScriptedJudge(script)
    stage_c = f.StageCDirectory(tmp_path / f.STAGE_C_RUN_ID)
    asyncio.run(f.run_stage_c_primary(ROOT, stage_c, judge=judge, frozen_inputs=frozen, **_freeze_kwargs()))
    assert judge.calls == 192
    assert stage_c.execution_manifest_path().is_file()
    stage_c.verify_sealed()


def test_partial_prefix_resume_and_manifest_only_recovery(tmp_path: Path) -> None:
    frozen = _frozen_inputs()
    stage_a, stage_b, _ = frozen
    stage_c = f.StageCDirectory(tmp_path / f.STAGE_C_RUN_ID)
    stage_c.path.mkdir(parents=True)
    anchor = f.verify_stage_c_execution_freeze(ROOT, **_freeze_kwargs())
    f._atomic_new_json(stage_c.execution_manifest_path(), f._stage_c_execution_manifest_payload(anchor))
    script = [_result(_judge_payload(retrieval)) for retrieval in stage_a]
    judge = ScriptedJudge(script)
    asyncio.run(f.run_stage_c_primary(ROOT, stage_c, judge=judge, frozen_inputs=frozen, **_freeze_kwargs()))
    assert judge.calls == 192
    # A second directory with one valid prefix row resumes only the suffix.
    other = tmp_path / "other" / f.STAGE_C_RUN_ID
    resumed = f.StageCDirectory(other)
    resumed.path.mkdir(parents=True)
    f._atomic_new_json(resumed.execution_manifest_path(), f._stage_c_execution_manifest_payload(anchor))
    resumed.stage_path().write_text(json.dumps(_completed_record(stage_a[0])) + "\n", encoding="utf-8")
    judge2 = ScriptedJudge([_result(_judge_payload(retrieval)) for retrieval in stage_a[1:]])
    asyncio.run(f.run_stage_c_primary(ROOT, resumed, judge=judge2, frozen_inputs=frozen, **_freeze_kwargs()))
    assert judge2.calls == 191
    assert [row["experiment_id"] for row in f._read_jsonl_strict(resumed.stage_path(), label="test")] == [row["experiment_id"] for row in stage_b]


def test_complete_unsealed_makes_zero_calls_and_upstream_failures_skip_judge(tmp_path: Path) -> None:
    frozen = _frozen_inputs()
    stage_a, stage_b, manifest = frozen
    stage_c = f.StageCDirectory(tmp_path / f.STAGE_C_RUN_ID)
    stage_c.path.mkdir(parents=True)
    anchor = f.verify_stage_c_execution_freeze(ROOT, **_freeze_kwargs())
    f._atomic_new_json(stage_c.execution_manifest_path(), f._stage_c_execution_manifest_payload(anchor))
    stage_c.stage_path().write_text(
        "".join(json.dumps(_completed_record(row)) + "\n" for row in stage_a), encoding="utf-8",
    )
    no_call = ScriptedJudge([])
    asyncio.run(f.run_stage_c_primary(ROOT, stage_c, judge=no_call, frozen_inputs=frozen, **_freeze_kwargs()))
    assert no_call.calls == 0
    upstream_b = [dict(row, generation_success=False, final_generation_success=False, generation_outcome="technical_failure", first_error_type="timeout", final_error_type="timeout", attempt_count=2, technical_retry_used=True, answer="") for row in stage_b]
    upstream_dir = f.StageCDirectory(tmp_path / "upstream" / f.STAGE_C_RUN_ID)
    asyncio.run(f.run_stage_c_primary(
        ROOT, upstream_dir, judge=no_call, frozen_inputs=(stage_a, upstream_b, manifest), **_freeze_kwargs(),
    ))
    assert no_call.calls == 0
    rows = f._read_jsonl_strict(upstream_dir.stage_path(), label="test")
    assert all(row["judge_outcome"] == "upstream_generation_failure" for row in rows)
    assert all(row["upstream_failure"]["final_error_type"] == "timeout" for row in rows)


def test_duplicate_foreign_and_out_of_order_prefixes_are_rejected(tmp_path: Path) -> None:
    stage_a, stage_b, _ = _frozen_inputs()
    for name, rows, match in (
        ("duplicate", [_completed_record(stage_a[0]), _completed_record(stage_a[0])], "duplicate"),
        ("foreign", [dict(_completed_record(stage_a[0]), experiment_id="foreign")], "foreign"),
        ("order", [_completed_record(stage_a[1])], "prefix"),
    ):
        stage_c = f.StageCDirectory(tmp_path / name / f.STAGE_C_RUN_ID)
        stage_c.path.mkdir(parents=True)
        stage_c.stage_path().write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        with pytest.raises(f.FatalFormalRunError, match=match):
            f._validated_existing_stage_c_records(stage_c, stage_a, stage_b)


def test_preregistered_analysis_populations_pairing_bootstrap_mcnemar_and_holm_are_deterministic() -> None:
    stage_a, stage_b, _ = _frozen_inputs()
    stage_c = [_completed_record(row) for row in stage_a]
    cases = f.load_frozen_cases(ROOT)
    metrics = f.stage_c_judge_metrics(stage_a, stage_b, stage_c, cases)
    assert metrics["w_rq2_frozen_eligible_case_count"] == 42
    assert metrics["w_rq3_insufficient_case_count"] == 6
    assert all(value["frozen_intended_cases"] == 42 for value in metrics["by_condition"].values())
    first = f.stage_c_pairwise_statistics(stage_a, stage_b, stage_c, cases)
    second = f.stage_c_pairwise_statistics(stage_a, stage_b, stage_c, cases)
    assert first == second
    assert all(value["paired_n"] == 42 for value in first["comparisons"].values())
    assert all(value["unsupported_claim_presence_mcnemar"]["paired_n"] == 42 for value in first["comparisons"].values())
    assert all(value["unsupported_claim_presence_mcnemar"]["exact_two_sided_p"] == 1.0 for value in first["comparisons"].values())
    assert all(value["unsupported_claim_presence_mcnemar"]["holm_adjusted_p"] == 1.0 for value in first["comparisons"].values())
    insufficient = f.stage_c_insufficiency_metrics(stage_a, stage_b, stage_c, cases)
    assert all(value["frozen_intended_cases"] == 6 for value in insufficient["by_condition"].values())
    assert all(sum(value["outcome_counts"].values()) == 6 for value in insufficient["by_condition"].values())


def test_semantic_missingness_is_not_scored_zero() -> None:
    stage_a, stage_b, _ = _frozen_inputs()
    stage_c = [_completed_record(row) for row in stage_a]
    target = next(row for row in stage_c if next(a for a in stage_a if a["experiment_id"] == row["experiment_id"])["answerability"] == "supported")
    target["claim_labels"] = [{"claim_id": "n1", "claim": "Uncertainty framing.", "label": "not_checkable", "justification": "No medical claim."}]
    metrics = f.stage_c_judge_metrics(stage_a, stage_b, stage_c, f.load_frozen_cases(ROOT))
    condition = next(a["retrieval_condition"] for a in stage_a if a["experiment_id"] == target["experiment_id"])
    assert metrics["by_condition"][condition]["claim_rate_semantic_missing_cases"] == 1
    assert metrics["by_condition"][condition]["macro_endpoints"]["claim_support_rate"] == 1.0


def test_c_finalize_and_merged_finalize_are_immutable_and_primary_only(tmp_path: Path) -> None:
    stage_c, frozen = _prepare_complete_stage_c(tmp_path)
    artifacts = f.finalize_stage_c_run(ROOT, stage_c, frozen_inputs=frozen, **_freeze_kwargs())
    assert "stage_c_run_manifest.json" in artifacts
    assert "stage_c_pairwise_statistics.json" in artifacts
    merged = f.finalize_run(ROOT, stage_c, frozen_inputs=frozen, **_freeze_kwargs())
    completion = json.loads((stage_c.path / "completion_manifest.json").read_text(encoding="utf-8"))
    assert merged["raw_results.jsonl"] == completion["raw_results_sha256"]
    assert completion["stage_b_sha256"] == f.PRIMARY_STAGE_B_SHA256
    assert completion["original_outage_answers_used"] is False
    with pytest.raises(FileExistsError):
        f.finalize_run(ROOT, stage_c, frozen_inputs=frozen, **_freeze_kwargs())


def test_merged_finalize_rehashes_finalized_stage_c_artifacts(tmp_path: Path) -> None:
    stage_c, frozen = _prepare_complete_stage_c(tmp_path)
    f.finalize_stage_c_run(ROOT, stage_c, frozen_inputs=frozen, **_freeze_kwargs())
    with (stage_c.path / "stage_c_raw_results.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("{}\n")
    with pytest.raises(f.FatalFormalRunError, match="Finalized Stage C artifact mismatch"):
        f.finalize_run(ROOT, stage_c, frozen_inputs=frozen, **_freeze_kwargs())


def test_legacy_run_directory_cannot_use_hardened_merged_finalizer(tmp_path: Path) -> None:
    legacy = f.RunDirectory(tmp_path / "legacy")
    with pytest.raises(f.FatalFormalRunError, match="dedicated finalized primary Stage C"):
        f.finalize_run(ROOT, legacy, **_freeze_kwargs())  # type: ignore[arg-type]
