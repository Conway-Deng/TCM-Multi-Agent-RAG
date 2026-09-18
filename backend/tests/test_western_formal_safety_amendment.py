from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from providers.openai_compatible import ProviderUnavailable
import western.formal_eval as formal_eval
from western.formal_eval import (
    BENCHMARK_COMMIT,
    BENCHMARK_MANIFEST_SHA256,
    BENCHMARK_SHA256,
    CONDITIONS,
    CORPUS_CHUNKS_SHA256,
    ORIGINAL_PROTOCOL_COMMIT,
    PROTOCOL_SHA256,
    RUNTIME_COMMIT,
    SOURCE_REGISTRY_SHA256,
    FatalFormalRunError,
    RunDirectory,
    _base_record,
    _assert_no_secret_fields,
    balanced_execution_order,
    finalize_stage_a_run,
    formal_retrieve_cell,
    load_frozen_cases,
    load_frozen_execution_order,
    pairwise_retrieval_statistics,
    retrieval_metrics,
    run_stage_b,
    run_stage_c,
)


ROOT = Path(__file__).resolve().parents[2]


class StubSource:
    def model_dump(self) -> dict[str, str]:
        return {"title": "Synthetic source", "source_url": "https://example.test", "pmcid": "", "doi": "", "license": "CC0"}


class StubReranker:
    name = "siliconflow"
    model = "BAAI/bge-reranker-v2-m3"

    def __init__(self, outcomes: list[object] | None = None) -> None:
        self.outcomes = list(outcomes or [[0.9, 0.1]])
        self.calls = 0

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        del query, documents
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]


class StubEngine:
    formal_strict = True

    def __init__(self, dense_outcomes: list[object] | None = None, rerank_outcomes: list[object] | None = None) -> None:
        self.chunks = (
            SimpleNamespace(chunk_id="west-synthetic-1", source_id="source-1", text="alpha evidence", keywords=(), topics=("cough",), section="Results"),
            SimpleNamespace(chunk_id="west-synthetic-2", source_id="source-1", text="beta evidence", keywords=(), topics=("cough",), section="Methods"),
        )
        self.sources = {"source-1": StubSource()}
        self.providers = SimpleNamespace(rerank=StubReranker(rerank_outcomes))
        self.dense_outcomes = list(dense_outcomes or [{"west-synthetic-1": 0.9, "west-synthetic-2": 0.1}])
        self.semantic_calls = 0
        self.actual_embedding_provider = "none"
        self.actual_embedding_model = "none"
        self.actual_reranker_provider = "none"
        self.actual_reranker_model = "none"

    def _lexical(self, query: str) -> dict[str, float]:
        del query
        return {"west-synthetic-1": 0.8, "west-synthetic-2": 0.2}

    async def _semantic(self, query: str) -> dict[str, float]:
        del query
        self.semantic_calls += 1
        outcome = self.dense_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]

    def _validate_formal_reranker(self, reranker: object) -> None:
        assert getattr(reranker, "name") == "siliconflow"


def _timeout() -> ProviderUnavailable:
    return ProviderUnavailable("synthetic timeout", error_type="timeout")


def _run(engine: StubEngine, condition: str) -> dict[str, object]:
    return asyncio.run(formal_retrieve_cell(engine, query="synthetic query", condition=condition, topics=["cough"]))


def test_a_r1_dense_first_attempt_success() -> None:
    result = _run(StubEngine(), "R1")
    assert result["terminal_state"] == "success"
    assert result["attempt_count"] == 1
    assert result["technical_retry_used"] is False


def test_b_r1_dense_timeout_then_success() -> None:
    engine = StubEngine([_timeout(), {"west-synthetic-1": 0.9, "west-synthetic-2": 0.1}])
    result = _run(engine, "R1")
    assert result["terminal_state"] == "success"
    assert result["attempt_count"] == 2
    assert result["technical_retry_used"] is True
    assert result["technical_retry_stage"] == "dense"
    assert engine.semantic_calls == 2


def test_c_r1_dense_fails_twice_and_terminal_failure_is_retained() -> None:
    result = _run(StubEngine([_timeout(), _timeout()]), "R1")
    assert result["terminal_state"] == "technical_failure"
    assert result["retrieval_success"] is False
    assert result["attempt_count"] == 2
    assert len(result["errors"]) == 2  # type: ignore[arg-type]
    assert result["results"] == []


def test_d_r3_reranker_retry_does_not_repeat_dense() -> None:
    engine = StubEngine(rerank_outcomes=[_timeout(), [0.9, 0.1]])
    result = _run(engine, "R3")
    assert result["terminal_state"] == "success"
    assert result["technical_retry_stage"] == "reranker"
    assert engine.semantic_calls == 1
    assert engine.providers.rerank.calls == 2


def test_e_r3_consumed_retry_budget_allows_no_third_attempt() -> None:
    engine = StubEngine([_timeout(), {"west-synthetic-1": 0.9, "west-synthetic-2": 0.1}], [_timeout(), [0.9, 0.1]])
    result = _run(engine, "R3")
    assert result["terminal_state"] == "technical_failure"
    assert result["technical_retry_stage"] == "dense"
    assert engine.semantic_calls == 2
    assert engine.providers.rerank.calls == 1


def _terminal(index: int, *, success: bool = True, condition: str | None = None) -> dict[str, object]:
    state = "success" if success else "technical_failure"
    return {
        "experiment_id": f"cell-{index}", "case_id": f"case-{index}",
        "retrieval_condition": condition or CONDITIONS[index % 4],
        "terminal_state": state, "retrieval_success": success,
    }


def _frozen_order() -> list[dict[str, object]]:
    return load_frozen_execution_order(ROOT, load_frozen_cases(ROOT))


def test_f_190_successes_plus_two_terminal_failures_can_seal(tmp_path: Path) -> None:
    order = _frozen_order()
    pairs = {(str(cell["case_id"]), str(cell["retrieval_condition"])) for cell in order}
    run = RunDirectory.create(tmp_path, "mixed-terminal", expected_stage_a_pairs=pairs)
    for index, cell in enumerate(order):
        record = _terminal(index, success=index < 190, condition=str(cell["retrieval_condition"]))
        record["case_id"] = cell["case_id"]
        run.append("A", record)
    manifest = run.seal("A")
    assert manifest["successful_cells"] == 190
    assert manifest["technical_failure_cells"] == 2


def test_g_191_terminal_cells_cannot_seal(tmp_path: Path) -> None:
    order = _frozen_order()
    pairs = {(str(cell["case_id"]), str(cell["retrieval_condition"])) for cell in order}
    run = RunDirectory.create(tmp_path, "missing-terminal", expected_stage_a_pairs=pairs)
    for index, cell in enumerate(order[:191]):
        record = _terminal(index, condition=str(cell["retrieval_condition"]))
        record["case_id"] = cell["case_id"]
        run.append("A", record)
    with pytest.raises(RuntimeError, match="192 unique"):
        run.seal("A")


def test_h_duplicate_case_condition_prevents_sealing(tmp_path: Path) -> None:
    order = _frozen_order()
    pairs = {(str(cell["case_id"]), str(cell["retrieval_condition"])) for cell in order}
    run = RunDirectory.create(tmp_path, "duplicate-pair", expected_stage_a_pairs=pairs)
    for index, cell in enumerate(order):
        record = _terminal(index, condition=str(cell["retrieval_condition"]))
        record["case_id"] = cell["case_id"]
        if index == 191:
            record["case_id"] = order[0]["case_id"]
            record["retrieval_condition"] = order[0]["retrieval_condition"]
        run.append("A", record)
    with pytest.raises(RuntimeError, match="duplicate case/condition"):
        run.seal("A")


def test_192_unique_but_wrong_pairs_cannot_seal(tmp_path: Path) -> None:
    expected = {(str(cell["case_id"]), str(cell["retrieval_condition"])) for cell in _frozen_order()}
    run = RunDirectory.create(tmp_path, "wrong-matrix", expected_stage_a_pairs=expected)
    for index in range(192):
        run.append("A", _terminal(index))
    with pytest.raises(RuntimeError, match="differs from frozen order"):
        run.seal("A")


def _complete_stage_a(run: RunDirectory) -> None:
    cases = load_frozen_cases(ROOT)
    by_id = {case["case_id"]: case for case in cases}
    for cell in balanced_execution_order(cases):
        case = by_id[cell["case_id"]]
        run.append("A", {
            **_base_record(case, cell["retrieval_condition"]),
            "retrieval_success": True, "terminal_state": "success",
            "attempt_count": 1, "technical_retry_used": False,
            "technical_retry_stage": "none", "first_error_type": None,
            "final_error_type": None, "errors": [], "provider_operation_trace": [],
            "retrieval_latency_ms": 1.0, "retrieved_items": [], "timestamps": {},
        })
    run.seal("A")


def test_i_j_stage_a_finalizes_without_b_or_c_and_emits_required_artifacts(tmp_path: Path) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    run = RunDirectory.create(
        tmp_path, "stage-a-only", repository_root=ROOT,
        expected_protocol_commit=head, require_clean_worktree=False,
    )
    _complete_stage_a(run)
    hashes = finalize_stage_a_run(
        ROOT, run, expected_protocol_commit=head, require_clean_worktree=False,
    )
    required = {
        "stage_a_raw_results.jsonl", "stage_a_retrieval_metrics.json",
        "stage_a_provider_metrics.json", "stage_a_run_manifest.json",
        "stage_a_pairwise_statistics.json", "STAGE_A_FROZEN.md",
    }
    assert required <= set(hashes)
    assert not run.stage_path("B").exists()
    assert not run.stage_path("C").exists()


def test_k_technical_failure_is_excluded_not_scored_zero() -> None:
    cases = [{"case_id": "c1", "answerability": "supported", "gold_chunk_ids": ["g1"], "gold_source_ids": ["s1"], "optional_secondary_chunk_ids": []}]
    records = [{
        "case_id": "c1", "retrieval_condition": condition,
        "retrieval_success": condition != "R1", "retrieved_items": [],
        "gold_primary_chunk_ids": ["g1"], "gold_primary_source_ids": ["s1"],
        "gold_secondary_chunk_ids": [],
    } for condition in CONDITIONS]
    metrics = retrieval_metrics(records, cases)["by_condition"]["R1"]
    assert metrics["successful_eligible_cases_used"] == 0
    assert metrics["technical_missing_eligible_cases_excluded"] == 1
    assert metrics["macro_primary_gold_chunk_recall_at_4"] is None


def test_l_pairwise_comparison_uses_successful_intersection() -> None:
    cases = [{"case_id": case_id, "answerability": "supported", "gold_chunk_ids": ["g"], "gold_source_ids": ["s"], "optional_secondary_chunk_ids": []} for case_id in ("c1", "c2")]
    records = []
    for case_id in ("c1", "c2"):
        for condition in CONDITIONS:
            records.append({
                "case_id": case_id, "retrieval_condition": condition,
                "retrieval_success": not (case_id == "c2" and condition == "R1"),
                "retrieved_items": [{"chunk_id": "g", "source_id": "s"}],
                "gold_primary_chunk_ids": ["g"], "gold_primary_source_ids": ["s"],
            })
    stats = pairwise_retrieval_statistics(records, cases)["comparisons"]
    assert stats["R0_vs_R1"]["paired_n"] == 1
    assert stats["R0_vs_R2"]["paired_n"] == 2


def test_m_run_manifest_contains_all_required_commits_and_hashes(tmp_path: Path) -> None:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    run = RunDirectory.create(
        tmp_path, "manifest", repository_root=ROOT,
        expected_protocol_commit=head, require_clean_worktree=False,
    )
    manifest = __import__("json").loads((run.path / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["runtime_checkpoint_commit"] == RUNTIME_COMMIT
    assert manifest["benchmark_checkpoint_commit"] == BENCHMARK_COMMIT
    assert manifest["original_protocol_v0_1_commit"] == ORIGINAL_PROTOCOL_COMMIT
    assert manifest["benchmark_sha256"] == BENCHMARK_SHA256
    assert manifest["benchmark_manifest_sha256"] == BENCHMARK_MANIFEST_SHA256
    assert manifest["protocol_sha256"] == PROTOCOL_SHA256
    assert manifest["corpus_chunks_sha256"] == CORPUS_CHUNKS_SHA256
    assert manifest["source_registry_sha256"] == SOURCE_REGISTRY_SHA256
    assert manifest["superseded_before_formal_execution"] is True


def test_n_local_r0_exception_is_fatal_not_quality_failure() -> None:
    engine = StubEngine()
    engine._lexical = lambda query: (_ for _ in ()).throw(ValueError("synthetic defect"))  # type: ignore[method-assign]
    with pytest.raises(FatalFormalRunError, match="local lexical"):
        _run(engine, "R0")


def test_o_sealed_stage_a_cannot_resume_or_overwrite(tmp_path: Path) -> None:
    run = RunDirectory.create(tmp_path, "sealed")
    run.append("A", _terminal(0, condition="R0"))
    run.seal("A", expected_cells=1)
    with pytest.raises(RuntimeError, match="resume is prohibited"):
        RunDirectory.resume_stage_a(run.path)
    with pytest.raises(RuntimeError, match="sealed"):
        run.append("A", _terminal(1, condition="R1"))


def test_p_no_api_secret_can_be_serialized() -> None:
    with pytest.raises(ValueError, match="Secret-bearing"):
        _assert_no_secret_fields({"provider_trace": {"api_key": "synthetic-secret"}})


def test_q_frozen_scientific_inputs_are_still_exact() -> None:
    import hashlib

    paths = {
        ROOT / "research/benchmarks/western_pilot_v0_1/benchmark.jsonl": BENCHMARK_SHA256,
        ROOT / "research/benchmarks/western_pilot_v0_1/benchmark_manifest.json": BENCHMARK_MANIFEST_SHA256,
        ROOT / "research/corpus/west_v0_1/chunks.jsonl": CORPUS_CHUNKS_SHA256,
        ROOT / "research/corpus/west_v0_1/source_registry.json": SOURCE_REGISTRY_SHA256,
    }
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == expected for path, expected in paths.items())


def test_v0_1_1_order_preserves_all_original_sequence_case_condition_tuples() -> None:
    old = json.loads((ROOT / "research/experiments/western_formal_v0_1/protocol/execution_order.json").read_text(encoding="utf-8"))["cells"]
    new = json.loads((ROOT / "research/experiments/western_formal_v0_1/protocol_v0_1_1/execution_order.json").read_text(encoding="utf-8"))["cells"]
    fields = ("sequence", "case_id", "retrieval_condition")
    assert [tuple(cell[field] for field in fields) for cell in new] == [tuple(cell[field] for field in fields) for cell in old]


def test_v0_1_2_order_preserves_all_original_sequence_case_condition_tuples() -> None:
    old = json.loads((ROOT / "research/experiments/western_formal_v0_1/protocol/execution_order.json").read_text(encoding="utf-8"))["cells"]
    new = json.loads((ROOT / "research/experiments/western_formal_v0_1/protocol_v0_1_2/execution_order.json").read_text(encoding="utf-8"))["cells"]
    fields = ("sequence", "case_id", "retrieval_condition")
    assert [tuple(cell[field] for field in fields) for cell in new] == [tuple(cell[field] for field in fields) for cell in old]


def test_exact_freeze_head_is_accepted_before_run_directory_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze = "f" * 40
    monkeypatch.setattr(formal_eval, "_git_head", lambda root: freeze)
    monkeypatch.setattr(formal_eval, "resolve_protocol_freeze_commit", lambda root: freeze)
    monkeypatch.setattr(formal_eval, "_git_worktree_clean", lambda root: True)
    run = RunDirectory.create(tmp_path, "accepted", repository_root=ROOT)
    manifest = json.loads((run.path / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["protocol_checkpoint_commit"] == freeze


def test_later_head_is_rejected_without_creating_run_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(formal_eval, "_git_head", lambda root: "b" * 40)
    monkeypatch.setattr(formal_eval, "resolve_protocol_freeze_commit", lambda root: "a" * 40)
    monkeypatch.setattr(formal_eval, "_git_worktree_clean", lambda root: True)
    with pytest.raises(FatalFormalRunError, match="requires protocol freeze HEAD"):
        RunDirectory.create(tmp_path, "rejected-head", repository_root=ROOT)
    assert not (tmp_path / "rejected-head").exists()


def test_dirty_worktree_is_rejected_without_creating_run_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze = "a" * 40
    monkeypatch.setattr(formal_eval, "_git_head", lambda root: freeze)
    monkeypatch.setattr(formal_eval, "resolve_protocol_freeze_commit", lambda root: freeze)
    monkeypatch.setattr(formal_eval, "_git_worktree_clean", lambda root: False)
    with pytest.raises(FatalFormalRunError, match="clean Git working tree"):
        RunDirectory.create(tmp_path, "rejected-dirty", repository_root=ROOT)
    assert not (tmp_path / "rejected-dirty").exists()


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **kwargs: object) -> object:
        del kwargs
        self.calls += 1
        raise AssertionError("provider must not be called for upstream retrieval missingness")


def test_stage_a_technical_failure_skips_qwen_and_glm_but_retains_cell(tmp_path: Path) -> None:
    run = RunDirectory.create(tmp_path, "upstream-missing")
    run.append("A", {
        "experiment_id": "missing-cell", "case_id": "synthetic-case", "retrieval_condition": "R1",
        "terminal_state": "technical_failure", "retrieval_success": False,
        "retrieved_items": [], "topic": "cough", "question": "synthetic non-benchmark question",
        "expected_evidence_points": [], "answerability": "supported",
    })
    run.seal("A", expected_cells=1)
    generator = CountingProvider()
    asyncio.run(run_stage_b(ROOT, run, generator=generator, expected_cells=1))
    generation = json.loads(run.stage_path("B").read_text(encoding="utf-8"))
    assert generator.calls == 0
    assert generation["experiment_id"] == "missing-cell"
    assert generation["generation_outcome"] == "upstream_retrieval_technical_failure"
    assert generation["attempt_count"] == 0 and generation["answer"] == "" and generation["provenance"] == []
    judge = CountingProvider()
    asyncio.run(run_stage_c(ROOT, run, judge=judge, expected_cells=1))
    judgment = json.loads(run.stage_path("C").read_text(encoding="utf-8"))
    assert judge.calls == 0
    assert judgment["experiment_id"] == "missing-cell"
    assert judgment["judge_outcome"] == "upstream_retrieval_technical_failure"
    assert judgment["insufficiency_label"] == "not_applicable"
    assert judgment["claim_labels"] == [] and judgment["evidence_point_labels"] == []
