from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "research/benchmarks/tcm_gold_rq4_v1"
OLD = [json.loads(line) for line in (BENCH / "benchmark_rq4_v1_draft.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
NEW = [json.loads(line) for line in (BENCH / "benchmark_rq4_v1_1_draft.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
PACKET = list(csv.DictReader((BENCH / "external_source_review_v1_1_for_gpt.csv").open(encoding="utf-8-sig", newline="")))
REVISE = {"rq4-v1-001", "rq4-v1-002", "rq4-v1-004", "rq4-v1-007", "rq4-v1-008", "rq4-v1-015", "rq4-v1-018", "rq4-v1-019", "rq4-v1-026", "rq4-v1-039", "rq4-v1-044", "rq4-v1-045", "rq4-v1-048", "rq4-v1-050", "rq4-v1-051", "rq4-v1-055", "rq4-v1-057", "rq4-v1-086", "rq4-v1-088", "rq4-v1-097"}


def test_first_round_review_imported_exactly():
    rows = list(csv.DictReader((BENCH / "revision_v1_1/first_round_review_imported.csv").open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 232 and len({x["row_id"] for x in rows}) == 232
    assert Counter(x["source_review_status"] for x in rows) == Counter({"APPROVE": 195, "REVISE": 37})
    assert {x["question_id"] for x in rows if x["source_review_status"] == "REVISE"} == REVISE


def test_eighty_approved_questions_preserved():
    old = {x["question_id"]: x for x in OLD}; new = {x["question_id"]: x for x in NEW}
    for qid in old.keys() - REVISE:
        candidate = {key: value for key, value in new[qid].items() if key not in {"revision_status", "revision_note"}}
        assert candidate == old[qid]


def test_all_twenty_affected_questions_addressed():
    assert {x["question_id"] for x in NEW if x["revision_status"] != "APPROVED_UNCHANGED"} == REVISE
    assert Counter(x["revision_status"] for x in NEW) == Counter({"APPROVED_UNCHANGED": 80, "REPLACED_AFTER_FIRST_SOURCE_REVIEW": 17, "REWRITTEN_AFTER_FIRST_SOURCE_REVIEW": 3})


def test_completeness_mismatch_prompts_narrowed():
    new = {x["question_id"]: x for x in NEW}
    for qid in {"rq4-v1-002", "rq4-v1-019", "rq4-v1-039"}:
        assert "function and indication" in new[qid]["question"]
        assert "used part" not in new[qid]["question"]
        assert len(new[qid]["gold_facts"]) == 2


def test_no_cross_reference_gold_remains():
    assert not any(re.search(r"(?i)\bsee\b", fact["fact"]) for item in NEW for fact in item["gold_facts"])


def test_final_distribution_and_ids():
    assert len(NEW) == 100 and len({x["question_id"] for x in NEW}) == 100
    assert Counter(x["domain"] for x in NEW) == Counter({"herbal_medicine": 60, "syndrome_differentiation": 25, "herbal_medicine + syndrome_differentiation": 15})
    assert Counter(x["difficulty"] for x in NEW) == Counter({"easy": 40, "medium": 40, "hard": 20})


def test_all_gold_evidence_is_nonempty_and_valid():
    corpus_ids = {json.loads(line)["chunk_id"] for line in (ROOT / "research/corpus/tcm_v1/chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}
    for item in NEW:
        assert item["question"].strip() and item["held_out"] is True
        assert set(item["source_evidence_ids"]) <= corpus_ids
        for fact in item["gold_facts"]:
            assert fact["fact"].strip() and fact["evidence_excerpt"].strip() and set(fact["preferred_evidence_ids"]) <= corpus_ids


def test_second_packet_contains_all_questions_and_blank_review_fields():
    assert len(PACKET) == 232 and len({x["question_id"] for x in PACKET}) == 100
    assert len({x["row_id"] for x in PACKET}) == 232
    assert all(not row["source_review_status"] and not row["review_reason"] and not row["confidence"] for row in PACKET)


def test_second_packet_protected_fields_are_present():
    required = {"row_id", "question_id", "domain", "difficulty", "question", "gold_atomic_fact", "preferred_evidence_id", "evidence_excerpt", "source_entity_names", "source_review_revision_status"}
    assert required <= set(PACKET[0])


def test_leakage_report_is_zero_for_forbidden_material():
    report = (BENCH / "leakage_report_rq4_v1_1.md").read_text(encoding="utf-8")
    assert "entity_overlap: 0" in report and "evidence_id_overlap: 0" in report
    assert "replaced_first_rq4_entity_overlap: 0" in report and "replaced_first_rq4_evidence_overlap: 0" in report


def test_v1_1_candidate_is_not_frozen_and_current_state_requires_source_review():
    manifest = json.loads((BENCH / "heldout_manifest_rq4_v1_1_draft.json").read_text(encoding="utf-8"))
    state = json.loads((ROOT / "research/experiments/rq4_debate_vs_multiagent/rq4_state.json").read_text(encoding="utf-8"))
    assert manifest["frozen"] is False and manifest["source_review"] == "SECOND_REVIEW_PENDING"
    assert state["state"] == "BENCHMARK_SOURCE_REVIEW_REQUIRED"
    assert state["second_source_review"] in {"PENDING", "COMPLETED"}
    if state["second_source_review"] == "COMPLETED":
        assert state["final_source_review"] == "PENDING"


def test_revision_ledger_has_twenty_rows_and_actions():
    rows = list(csv.DictReader((BENCH / "revision_v1_1/first_round_review_revision_ledger.csv").open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 20 and Counter(x["action"] for x in rows) == Counter({"REPLACE": 17, "REWRITE": 3})


def test_revision_did_not_call_provider():
    manifest = json.loads((BENCH / "heldout_manifest_rq4_v1_1_draft.json").read_text(encoding="utf-8"))
    assert manifest["provider_calls"] == 0
