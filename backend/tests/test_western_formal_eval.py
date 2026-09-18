from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from providers.openai_compatible import ProviderUnavailable
from western.formal_eval import (
    BENCHMARK_SHA256,
    CONDITIONS,
    FINAL_TOP_K,
    INTENDED_CELLS,
    RETRIEVAL_CONDITIONS,
    RunDirectory,
    _assert_no_secret_fields,
    balanced_execution_order,
    experiment_id,
    headline_retrieval_case_ids,
    insufficient_case_ids,
    invoke_with_technical_retry,
    load_frozen_cases,
    provenance_integrity,
    retrieval_metrics,
    verify_frozen_inputs,
)
from western.formal_judge import FormalJudgeOutput, build_judge_prompt, parse_judge_output


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_ROOT = ROOT / "research/experiments/western_formal_v0_1/protocol"


def _judge_payload() -> dict[str, object]:
    return {
        "claim_labels": [{
            "claim_id": "c1", "claim": "A synthetic claim.", "label": "supported", "justification": "Directly stated."
        }],
        "evidence_point_labels": [{"point_index": 0, "label": "covered", "justification": "Included."}],
        "insufficiency_label": "not_applicable",
        "stays_within_supported_evidence": True,
        "preserves_uncertainty": True,
        "invented_unsupported_information": False,
        "diagnosis_like_personalized_statement": False,
        "individualized_dosing": False,
        "prescription_like_recommendation": False,
        "research_or_educational_limitation_preserved": True,
    }


def test_frozen_protocol_inputs_match_exact_hashes() -> None:
    hashes = verify_frozen_inputs(ROOT)
    assert hashes["benchmark_sha256"] == BENCHMARK_SHA256


def test_four_conditions_map_to_existing_engine_algorithms() -> None:
    assert tuple(RETRIEVAL_CONDITIONS) == CONDITIONS
    assert "BM25-like" in RETRIEVAL_CONDITIONS["R0"]["implementation"]
    assert RETRIEVAL_CONDITIONS["R1"]["model"] == "BAAI/bge-m3"
    assert "1/(60+" in RETRIEVAL_CONDITIONS["R2"]["fusion_method"]
    assert RETRIEVAL_CONDITIONS["R3"]["rerank_depth"] == 12
    assert {config["final_top_k"] for config in RETRIEVAL_CONDITIONS.values()} == {FINAL_TOP_K}


def test_balanced_execution_order_has_192_unique_rotated_cells() -> None:
    order = balanced_execution_order(load_frozen_cases(ROOT))
    assert len(order) == INTENDED_CELLS
    assert len({row["experiment_id"] for row in order}) == INTENDED_CELLS
    assert [row["retrieval_condition"] for row in order[:4]] == ["R0", "R1", "R2", "R3"]
    assert [row["retrieval_condition"] for row in order[4:8]] == ["R1", "R2", "R3", "R0"]


def test_unique_experiment_cell_ids_reject_unknown_condition() -> None:
    assert experiment_id("case-1", "R2").endswith(":case-1:R2")
    with pytest.raises(ValueError, match="Unknown retrieval condition"):
        experiment_id("case-1", "RX")


def test_technical_failure_retries_once() -> None:
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ProviderUnavailable("temporary", error_type="timeout")
        return "ok"

    outcome = asyncio.run(invoke_with_technical_retry(operation))
    assert outcome.value == "ok"
    assert outcome.attempt_count == 2
    assert outcome.technical_retry_used is True
    assert outcome.first_attempt_success is False


def test_content_failure_is_not_retried() -> None:
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ProviderUnavailable("weak output", error_type="output_quality_rejection")

    outcome = asyncio.run(invoke_with_technical_retry(operation))
    assert attempts == 1
    assert outcome.attempt_count == 1
    assert outcome.technical_retry_used is False
    assert outcome.final_success is False


def test_resume_rejects_duplicate_cells_and_sealed_stage_is_immutable(tmp_path: Path) -> None:
    run = RunDirectory.create(tmp_path, "run-001")
    record = {"experiment_id": "cell-1", "safe": True}
    run.append("A", record)
    resumed = RunDirectory.resume(run.path)
    assert resumed.completed_ids("A") == {"cell-1"}
    with pytest.raises(ValueError, match="Duplicate"):
        resumed.append("A", record)
    resumed.seal("A", expected_cells=1)
    with pytest.raises(RuntimeError, match="sealed"):
        resumed.append("A", {"experiment_id": "cell-2"})


def test_new_run_id_cannot_overwrite_existing_run(tmp_path: Path) -> None:
    RunDirectory.create(tmp_path, "immutable-run")
    with pytest.raises(FileExistsError):
        RunDirectory.create(tmp_path, "immutable-run")


def test_stage_hash_verification_detects_mutation(tmp_path: Path) -> None:
    run = RunDirectory.create(tmp_path, "run-002")
    run.append("A", {"experiment_id": "cell-1"})
    run.seal("A", expected_cells=1)
    run.stage_path("A").write_text('{"experiment_id":"changed"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        run.verify_sealed("A")


def test_stage_b_and_c_require_sealed_predecessors(tmp_path: Path) -> None:
    run = RunDirectory.create(tmp_path, "run-stages")
    with pytest.raises(RuntimeError, match="Stage A must be sealed"):
        run.append("B", {"experiment_id": "cell-1"})
    run.append("A", {"experiment_id": "cell-1"})
    run.seal("A", expected_cells=1)
    run.append("B", {"experiment_id": "cell-1"})
    with pytest.raises(RuntimeError, match="Stage B must be sealed"):
        run.append("C", {"experiment_id": "cell-1"})
    run.seal("B", expected_cells=1)
    run.append("C", {"experiment_id": "cell-1"})


def test_judge_claim_and_evidence_labels_are_schema_constrained() -> None:
    parsed = FormalJudgeOutput.model_validate(_judge_payload())
    assert parsed.claim_labels[0].label == "supported"
    invalid = _judge_payload()
    invalid["claim_labels"][0]["label"] = "mostly_true"
    with pytest.raises(ValidationError):
        FormalJudgeOutput.model_validate(invalid)


def test_judge_parser_requires_raw_json() -> None:
    raw = json.dumps(_judge_payload())
    assert parse_judge_output(raw).evidence_point_labels[0].label == "covered"
    with pytest.raises(ValueError, match="without Markdown fences"):
        parse_judge_output(f"```json\n{raw}\n```")


def test_judge_prompt_excludes_retrieval_scores() -> None:
    prompt = build_judge_prompt(
        question="Synthetic question?",
        answer="Synthetic answer.",
        retrieved_evidence=[{
            "rank": 1, "article_title": "Synthetic title", "section": "Synthetic section",
            "evidence_excerpt": "Synthetic evidence.", "rerank_score": 0.99,
        }],
        expected_evidence_points=["Synthetic point."],
        answerability="supported",
    )
    assert "rerank_score" not in prompt
    assert "0.99" not in prompt


def test_denominator_and_insufficient_subset_are_frozen() -> None:
    cases = load_frozen_cases(ROOT)
    assert len(headline_retrieval_case_ids(cases)) == 42
    assert len(insufficient_case_ids(cases)) == 6
    assert headline_retrieval_case_ids(cases).isdisjoint(insufficient_case_ids(cases))


def test_retrieval_metric_denominators_and_values() -> None:
    cases = [{
        "case_id": "c1", "answerability": "supported", "gold_chunk_ids": ["g1", "g2"],
        "gold_source_ids": ["s1"], "optional_secondary_chunk_ids": ["g3"],
    }]
    records = []
    for condition in CONDITIONS:
        records.append({
            "case_id": "c1", "retrieval_condition": condition,
            "retrieved_items": [{"chunk_id": "g1", "source_id": "s1"}],
            "gold_primary_chunk_ids": ["g1", "g2"], "gold_primary_source_ids": ["s1"],
            "gold_secondary_chunk_ids": ["g3"],
        })
    metrics = retrieval_metrics(records, cases)
    assert metrics["eligible_case_count"] == 1
    assert metrics["by_condition"]["R0"]["macro_primary_gold_chunk_recall_at_4"] == 0.5
    assert metrics["by_condition"]["R0"]["mrr"] == 1.0


def test_provenance_integrity_and_no_tcm_evidence() -> None:
    retrieved = [{
        "chunk_id": "west-chunk-1", "source_id": "west-source-1", "domain": "western",
        "article_title": "Title", "section": "Results", "source_url": "https://example.test",
        "pmcid": "PMC1", "doi": "", "license": "CC BY",
    }]
    provenance = [{key: retrieved[0][key] for key in (
        "chunk_id", "source_id", "article_title", "section", "source_url", "pmcid", "doi", "license"
    )}]
    assert provenance_integrity(retrieved, provenance, {"west-source-1"}) == (True, [])
    bad = [dict(retrieved[0], chunk_id="tcm-entry-1", domain="tcm")]
    bad_provenance = [dict(provenance[0], chunk_id="tcm-entry-1")]
    valid, errors = provenance_integrity(bad, bad_provenance, {"west-source-1"})
    assert valid is False
    assert any("TCM" in error for error in errors)


def test_secret_fields_are_rejected_but_max_tokens_is_allowed() -> None:
    _assert_no_secret_fields({"max_tokens": 256, "answer": "safe"})
    with pytest.raises(ValueError, match="Secret-bearing"):
        _assert_no_secret_fields({"api_key": "must-not-store"})


def test_protocol_artifacts_define_no_formal_results() -> None:
    protocol = json.loads((PROTOCOL_ROOT / "protocol.json").read_text(encoding="utf-8"))
    order = json.loads((PROTOCOL_ROOT / "execution_order.json").read_text(encoding="utf-8"))
    assert protocol["formal_results_generated"] is False
    assert protocol["intended_generation_cells"] == 192
    assert order["cell_count"] == 192
    assert not (PROTOCOL_ROOT.parent / "runs").exists()
