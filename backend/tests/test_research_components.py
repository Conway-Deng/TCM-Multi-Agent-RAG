from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents import planner as planner_module
from agents.planner import QueryPlannerAgent
from agents.specialists import HerbalKnowledgeAgent, LifestyleYangshengAgent, SingleRAGAgent, SyndromeDifferentiationAgent
from config import get_settings
from corpus import corpus_version, load_chunks, validate_corpus
from corpus import registry as corpus_registry
from evaluation.research_metrics import hit_rate_at_k, ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank
from evaluation.statistics import paired_comparison, summarize
from ingestion.pipeline import deterministic_chunk_id, normalize_text
from prompts import prompt_metadata
from retrieval import RetrievalEngine
from orchestration.conditions import CONDITIONS
from orchestration.debate import debate
from orchestration.workbench import _agent_prompt, _synthesis
from schemas.research import ConditionId, DatasetItem
from schemas.research import RetrievalItem, RetrievalStrategy
from research.run_experiment import load_config, load_dataset


@pytest.fixture(autouse=True)
def clear_corpus_caches_after_test():
    yield
    corpus_registry._v1_chunks.cache_clear()
    corpus_registry.load_chunks.cache_clear()
    corpus_registry.load_sources.cache_clear()
    planner_module._corpus_entity_patterns.cache_clear()


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


def test_planner_routes_liver_yang_corpus_entity_before_context_abstention(monkeypatch: pytest.MonkeyPatch) -> None:
    path = BACKEND.parent / "research" / "corpus" / "tcm_v1" / "chunks.jsonl"
    if not path.exists():
        pytest.skip("Restricted local Corpus v1 artifact is intentionally not distributed.")
    monkeypatch.setenv("TCM_CORPUS_MODE", "required"); monkeypatch.setenv("TCM_CORPUS_PATH", str(path))
    corpus_registry._v1_chunks.cache_clear(); corpus_registry.load_chunks.cache_clear(); corpus_registry.load_sources.cache_clear(); planner_module._corpus_entity_patterns.cache_clear()
    plan = QueryPlannerAgent().plan("What does the TCM Research Corpus record about liver yang?")
    assert plan.scope_state.value == "supported"
    assert "syndrome" in plan.subdomains
    assert "syndrome" in plan.required_agents


def test_r0_multi_target_anchors_cover_both_targets_and_grounding_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    path = BACKEND.parent / "research" / "corpus" / "tcm_v1" / "chunks.jsonl"
    if not path.exists():
        pytest.skip("Restricted local Corpus v1 artifact is intentionally not distributed.")
    monkeypatch.setenv("TCM_CORPUS_MODE", "required"); monkeypatch.setenv("TCM_CORPUS_PATH", str(path))
    corpus_registry._v1_chunks.cache_clear(); corpus_registry.load_chunks.cache_clear(); corpus_registry.load_sources.cache_clear(); planner_module._corpus_entity_patterns.cache_clear()
    question = "How are Red Ginseng and deficiency of the kidney-yang represented in the TCM corpus, and what evidence is recorded for each?"
    async def exercise():
        engine = RetrievalEngine()
        evidence, _ = await engine.search_with_reflection(question, strategy=RetrievalStrategy.R0, top_k=4, topics=["herbal", "syndrome"], enabled=False)
        return engine, evidence
    engine, evidence = asyncio.run(exercise())
    ids = {item.chunk_id for item in evidence}
    assert ids & {"tcmv1-010f829f0c703d4a98d24324", "tcmv1-0aaba1cbd4c4296e8ce6e234"}
    assert ids & {"tcmv1-01b61fa93d54e8bdd1c408f6", "tcmv1-d643f3c47d062f033e552170"}
    assert engine.unsupported_multi_entity_claim(question, "Red Ginseng is associated with kidney-yang deficiency.", evidence) is not None
    assert engine.unsupported_multi_entity_claim(question, "Red Ginseng is described in one paragraph. Kidney-yang deficiency is described separately.", evidence) is None
    assert engine.unsupported_multi_entity_claim(question, "Syndrome: deficiency of the kidney-yang. Herb: Red Ginseng. Properties are listed separately.", evidence) is None
    target_plan = engine.multi_target_evidence_plan(question, evidence)
    assert target_plan is not None
    targets = {item["label"]: item for item in target_plan["requested_targets"]}
    assert targets["Red Ginseng"]["supporting_evidence_ids"]
    assert targets["deficiency of the kidney-yang"]["supporting_evidence_ids"]
    assert target_plan["relationship_evidence_ids"] == []


def test_c1_and_c2_prompts_preserve_multi_target_separation(monkeypatch: pytest.MonkeyPatch) -> None:
    path = BACKEND.parent / "research" / "corpus" / "tcm_v1" / "chunks.jsonl"
    if not path.exists():
        pytest.skip("Restricted local Corpus v1 artifact is intentionally not distributed.")
    monkeypatch.setenv("TCM_CORPUS_MODE", "required"); monkeypatch.setenv("TCM_CORPUS_PATH", str(path))
    corpus_registry._v1_chunks.cache_clear(); corpus_registry.load_chunks.cache_clear(); corpus_registry.load_sources.cache_clear(); planner_module._corpus_entity_patterns.cache_clear()
    question = "How are Red Ginseng and deficiency of the kidney-yang represented in the TCM corpus, and what evidence is recorded for each?"

    async def exercise():
        engine = RetrievalEngine()
        evidence, _ = await engine.search_with_reflection(question, strategy=RetrievalStrategy.R0, top_k=4, topics=["herbal", "syndrome"], enabled=False)
        target_plan = engine.multi_target_evidence_plan(question, evidence)
        single = SingleRAGAgent(); herbal = HerbalKnowledgeAgent(); syndrome = SyndromeDifferentiationAgent()
        baselines = [await agent.answer(question, "en", evidence, provider="local", model="test") for agent in (single, herbal, syndrome)]
        prompts = [_agent_prompt(agent, question, "en", baseline, evidence, target_plan) for agent, baseline in zip((single, herbal, syndrome), baselines)]
        return target_plan, baselines, prompts

    target_plan, baselines, prompts = asyncio.run(exercise())
    assert target_plan is not None and target_plan["relationship_evidence_ids"] == []
    single_payload = json.loads(prompts[0][1]); herbal_payload = json.loads(prompts[1][1]); syndrome_payload = json.loads(prompts[2][1])
    assert {group["target"] for group in single_payload["requested_targets"]} >= {"Red Ginseng", "deficiency of the kidney-yang"}
    assert {group["target"] for group in herbal_payload["requested_targets"]} == {"Red Ginseng"}
    assert {group["target"] for group in syndrome_payload["requested_targets"]} == {"deficiency of the kidney-yang"}
    assert "kidney-yang" not in herbal_payload["question"]
    assert "Red Ginseng" not in syndrome_payload["question"]
    assert single_payload["relationship_evidence"] == []
    answer, *_ = _synthesis(baselines[:2], CONDITIONS[ConditionId.C2], debate(baselines[:2], 0), [], separate_targets=True)
    assert "does not establish an explicit relationship" in answer
