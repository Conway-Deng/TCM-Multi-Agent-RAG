from __future__ import annotations

import copy
import json
from pathlib import Path

from western.benchmark import load_benchmark, validate_benchmark
from western.corpus import DEFAULT_CORPUS_ROOT, load_runtime_corpus


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "research" / "benchmarks" / "western_pilot_v0_1"


def _fixture():
    corpus = load_runtime_corpus(DEFAULT_CORPUS_ROOT)
    cases, parse_errors = load_benchmark(BENCHMARK_ROOT / "benchmark.jsonl")
    assert parse_errors == []
    return corpus, cases


def test_valid_48_case_benchmark_and_manifest_hash_linkage() -> None:
    corpus, cases = _fixture()
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    manifest = json.loads((BENCHMARK_ROOT / "benchmark_manifest.json").read_text(encoding="utf-8"))
    corpus_manifest = json.loads((DEFAULT_CORPUS_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert result["status"] == "PASS"
    assert result["hard_errors"] == []
    assert result["case_count"] == 48
    assert manifest["benchmark_case_count"] == 48
    assert manifest["corpus_chunks_sha256"] == corpus_manifest["chunks_sha256"]
    assert manifest["corpus_source_registry_sha256"] == corpus_manifest["source_registry_sha256"]
    assert manifest["build_git_commit"] == "e6b02f6e37534008427cb18cd06ce7f086153103"
    assert manifest["generation_policy"] == "ai_assisted_draft_secondary_model_reviewed"
    assert manifest["secondary_reviewer_type"] == "ai_model"
    assert manifest["secondary_reviewer_model"] == "GPT-5.6 Sol"
    assert manifest["review_basis"] == "frozen_pilot_corpus_review_packet"
    assert manifest["human_verified"] is False
    assert manifest["domain_expert_verified"] is False


def test_secondary_model_adjudication_report_is_complete() -> None:
    report = json.loads(
        (BENCHMARK_ROOT / "reports" / "secondary_model_adjudication.json").read_text(encoding="utf-8")
    )
    assert report["adjudicated_case_count"] == 15
    assert report["unchanged_case_count"] == 33
    assert report["secondary_reviewer_type"] == "ai_model"
    assert report["secondary_reviewer_model"] == "GPT-5.6 Sol"
    assert report["review_basis"] == "frozen_pilot_corpus_review_packet"
    assert report["human_verified"] is False
    assert report["domain_expert_verified"] is False
    assert len({item["case_id"] for item in report["changes"]}) == 15
    assert all(set(item) == {"case_id", "field", "before", "after", "rationale"} for item in report["changes"])


def test_duplicate_id_rejected() -> None:
    corpus, cases = _fixture()
    cases[1]["case_id"] = cases[0]["case_id"]
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("duplicate case_id" in item for item in result["hard_errors"])


def test_duplicate_question_rejected() -> None:
    corpus, cases = _fixture()
    cases[1]["question"] = cases[0]["question"]
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("duplicate question" in item for item in result["hard_errors"])


def test_wrong_topic_distribution_rejected() -> None:
    corpus, cases = _fixture()
    cases[0]["topic"] = "headache"
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("topic cough must contain 12" in item for item in result["hard_errors"])


def test_wrong_question_type_distribution_rejected() -> None:
    corpus, cases = _fixture()
    cases[0]["question_type"] = "paraphrased_retrieval"
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("question_type direct_evidence" in item for item in result["hard_errors"])


def test_unknown_chunk_rejected() -> None:
    corpus, cases = _fixture()
    cases[0]["gold_chunk_ids"] = ["west-pmc-unknown-chunk"]
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("unknown chunk_id" in item for item in result["hard_errors"])


def test_source_chunk_mismatch_rejected() -> None:
    corpus, cases = _fixture()
    cases[0]["gold_source_ids"] = ["west-pmc-9397766"]
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("chunk/source mismatch" in item for item in result["hard_errors"])


def test_supported_without_gold_rejected() -> None:
    corpus, cases = _fixture()
    cases[0]["gold_source_ids"] = []
    cases[0]["gold_chunk_ids"] = []
    cases[0]["optional_secondary_chunk_ids"] = []
    cases[0]["expected_evidence_points"] = []
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("supported case has no primary gold evidence" in item for item in result["hard_errors"])


def test_malformed_answerability_rejected() -> None:
    corpus, cases = _fixture()
    cases[0]["answerability"] = "maybe"
    result = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("invalid answerability" in item for item in result["hard_errors"])


def test_insufficient_semantics_are_corpus_bounded() -> None:
    corpus, cases = _fixture()
    insufficient = next(item for item in cases if item["answerability"] == "insufficient")
    valid = validate_benchmark(copy.deepcopy(cases), corpus.sources, corpus.chunks)
    assert not any(insufficient["case_id"] in item for item in valid["hard_errors"])
    insufficient["annotation_notes"] = "No medical evidence exists."
    invalid = validate_benchmark(cases, corpus.sources, corpus.chunks)
    assert any("corpus-bounded" in item or "literature-wide" in item for item in invalid["hard_errors"])


def test_malformed_jsonl_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    path.write_text('{"case_id": "ok"}\n{broken}\n', encoding="utf-8")
    cases, errors = load_benchmark(path)
    assert len(cases) == 1
    assert any("malformed JSONL" in item for item in errors)
