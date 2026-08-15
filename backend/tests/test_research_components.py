from __future__ import annotations

from pathlib import Path
import sys


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from agents.planner import QueryPlannerAgent
from corpus import corpus_version, validate_corpus
from evaluation.research_metrics import hit_rate_at_k, ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank
from evaluation.statistics import paired_comparison, summarize
from ingestion.pipeline import deterministic_chunk_id, normalize_text
from prompts import prompt_metadata
from schemas.research import DatasetItem
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
