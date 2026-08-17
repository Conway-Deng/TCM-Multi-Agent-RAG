from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents import planner as planner_module
from agents.planner import QueryPlannerAgent
from agents.specialists import HerbalKnowledgeAgent, LifestyleYangshengAgent
from config import get_settings
from corpus import corpus_version, load_chunks, validate_corpus
from corpus import registry as corpus_registry
from evaluation.research_metrics import hit_rate_at_k, ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank
from evaluation.statistics import paired_comparison, summarize
from ingestion.pipeline import deterministic_chunk_id, normalize_text
from prompts import prompt_metadata
from retrieval import RetrievalEngine
from schemas.research import DatasetItem
from schemas.research import RetrievalItem, RetrievalStrategy
from research.run_experiment import load_config, load_dataset


def test_planner_routes_tcm_subdomains() -> None:
    plan = QueryPlannerAgent().plan("Explain herbal formula concepts for insomnia without prescribing a dose")
    assert "herbal" in plan.subdomains
    assert "herbal" in plan.required_agents
    assert plan.language == "en"


def test_corpus_and_deterministic_ids() -> None:
    assert validate_corpus() == []
    assert corpus_version() == corpus_version()
    assert deterministic_chunk_id("src", "section", " hello  world ") == deterministic_chunk_id("src", "section", "hello world")
    assert normalize_text("a\n b") == "a b"


def test_prompt_versions_and_hashes_are_complete() -> None:
    versions, hashes = prompt_metadata()
    assert versions.keys() == hashes.keys()
    assert len(versions) >= 17
    assert all(len(value) == 64 for value in hashes.values())


def test_retrieval_metrics() -> None:
    retrieved = ["a", "b", "c"]
    relevant = {"b", "d"}
    assert precision_at_k(retrieved, relevant, 2) == 0.5
    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert hit_rate_at_k(retrieved, relevant, 1) == 0.0
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert 0 < ndcg_at_k(retrieved, relevant, 3) < 1


def test_statistics_do_not_invent_significance() -> None:
    summary = summarize([1.0, 2.0, 3.0])
    assert summary["count"] == 3
    assert "p_value" not in summary
    paired = paired_comparison([1.0, 2.0], [1.5, 2.5])
    assert paired["pairs"] == 2


def test_all_experiment_configs_and_seed_items_validate() -> None:
    project = BACKEND.parent
    configs = list((project / "research" / "configs").glob("*.yaml"))
    assert len(configs) >= 6
    for path in configs:
        config = load_config(path)
        assert config["dataset"]
        assert config.get("conditions")
        assert config.get("retrieval_modes")
    items = load_dataset(project / "research" / "datasets" / "seed_tcm.jsonl")
    assert len(items) >= 14
    assert all(isinstance(item, DatasetItem) for item in items)
    assert all("synthetic" in item.expert_review_status for item in items)


def test_specialists_route_by_chunk_metadata_not_ambiguous_substrings() -> None:
    item = RetrievalItem(
        chunk_id="tcm_yangsheng_001",
        source_id="fixture",
        rank=1,
        lexical_score=1.0,
        retrieval_method="lexical",
        chunk_text="Traditional lifestyle teaching discusses 生活方式 and sleep.",
        topics=["lifestyle_yangsheng", "sleep"],
    )
    assert HerbalKnowledgeAgent()._supports(item) is False
    assert LifestyleYangshengAgent()._supports(item) is True


def test_real_llm_execution_is_explicitly_disabled_by_default() -> None:
    assert get_settings().research_real_llm_enabled is False


def test_planner_routes_known_corpus_entity_without_generic_herb_word() -> None:
    entity = next(name for chunk in load_chunks() for name in chunk.herbs if name)
    plan = QueryPlannerAgent().plan(f"What are the traditional TCM properties and uses of {entity}?")
    assert plan.scope_state.value == "supported"
    assert "herbal" in plan.subdomains
    assert "herbal" in plan.required_agents


def test_red_ginseng_r0_retrieval_and_herbal_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    path = BACKEND.parent / "research" / "corpus" / "tcm_v1" / "chunks.jsonl"
    if not path.exists():
        pytest.skip("Restricted local Corpus v1 artifact is intentionally not distributed.")
    monkeypatch.setenv("TCM_CORPUS_MODE", "required")
    monkeypatch.setenv("TCM_CORPUS_PATH", str(path))
    corpus_registry._v1_chunks.cache_clear()
    corpus_registry.load_chunks.cache_clear()
    corpus_registry.load_sources.cache_clear()
    planner_module._corpus_entity_patterns.cache_clear()

    async def exercise():
        question = "What are the traditional TCM properties and uses of Red Ginseng?"
        plan = QueryPlannerAgent().plan(question)
        evidence = await RetrievalEngine().search(
            question,
            strategy=RetrievalStrategy.R0,
            top_k=10,
            topics=None,
        )
        herbal = await HerbalKnowledgeAgent().answer(
            question,
            plan.language,
            evidence,
            provider="local",
            model="deterministic-evidence-mapper-v1",
        )
        return plan, evidence, herbal

    try:
        plan, evidence, herbal = asyncio.run(exercise())
        assert plan.scope_state.value == "supported"
        assert plan.required_agents == ["herbal"]
        assert [item.chunk_id for item in evidence[:2]] == [
            "tcmv1-010f829f0c703d4a98d24324",
            "tcmv1-0aaba1cbd4c4296e8ce6e234",
        ]
        assert all("herbal_medicine" in item.topics for item in evidence[:2])
        assert herbal.abstained is False
        assert set(herbal.evidence_ids) >= {item.chunk_id for item in evidence[:2]}
    finally:
        corpus_registry._v1_chunks.cache_clear()
        corpus_registry.load_chunks.cache_clear()
        corpus_registry.load_sources.cache_clear()
        planner_module._corpus_entity_patterns.cache_clear()
