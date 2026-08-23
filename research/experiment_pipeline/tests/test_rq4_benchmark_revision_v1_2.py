from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research/experiment_pipeline"))

import revise_rq4_benchmark_v1_2 as revision
import rq4_platform as platform


BENCH = ROOT / "research/benchmarks/tcm_gold_rq4_v1"
OLD = revision.rows(BENCH / "benchmark_rq4_v1_1_draft.jsonl")
NEW = revision.rows(BENCH / "benchmark_rq4_v1_2_draft.jsonl")
OLD_BY_ID = {item["question_id"]: item for item in OLD}
NEW_BY_ID = {item["question_id"]: item for item in NEW}
PACKET = revision._read_csv(BENCH / "external_source_review_v1_2_for_gpt.csv")


def test_second_review_import_is_exact_and_has_expected_disposition():
    imported = revision._read_csv(BENCH / "revision_v1_2/second_round_review_imported.csv")
    expected = revision._read_csv(BENCH / "external_source_review_v1_1_for_gpt.csv")
    result = revision.validate_second_review(expected, imported)
    assert result["rows"] == result["unique_row_ids"] == 232
    assert result["status_counts"] == {"APPROVE": 187, "REVISE": 45}
    assert result["approved_questions"] == 83
    assert set(result["revised_question_ids"]) == revision.REPLACE_IDS


def test_all_83_approved_questions_are_byte_equivalent_objects():
    for qid in set(OLD_BY_ID) - revision.REPLACE_IDS:
        assert NEW_BY_ID[qid] == OLD_BY_ID[qid]


def test_only_17_allowed_questions_changed_and_all_targets_changed():
    changed = {qid for qid in OLD_BY_ID if OLD_BY_ID[qid] != NEW_BY_ID[qid]}
    assert changed == revision.REPLACE_IDS
    for qid in revision.REPLACE_IDS:
        assert not (set(OLD_BY_ID[qid]["source_evidence_ids"]) & set(NEW_BY_ID[qid]["source_evidence_ids"]))
        assert not (
            {revision.normalize_entity(value) for value in OLD_BY_ID[qid]["source_entity_names"]}
            & {revision.normalize_entity(value) for value in NEW_BY_ID[qid]["source_entity_names"]}
        )


def test_global_reservation_blocks_approved_and_prior_replacement_targets():
    candidates = [
        {"chunk_id": "tcmv1-" + "1" * 24, "entity_name": "Reserved herb", "aliases": []},
        {"chunk_id": "tcmv1-" + "2" * 24, "entity_name": "First fresh herb", "aliases": []},
        {"chunk_id": "tcmv1-" + "3" * 24, "entity_name": "Second fresh herb", "aliases": []},
    ]
    entities = {revision.normalize_entity("Reserved herb")}
    evidence = {candidates[0]["chunk_id"]}
    first = revision._next_chunk(candidates, entities, evidence)
    second = revision._next_chunk(candidates, entities, evidence)
    assert first["entity_name"] == "First fresh herb"
    assert second["entity_name"] == "Second fresh herb"


def test_final_questions_and_material_targets_are_unique():
    assert len(NEW) == len(NEW_BY_ID) == 100
    assert len({revision.normalize_text(item["question"]) for item in NEW}) == 100
    entity_owners: dict[str, set[str]] = defaultdict(set)
    evidence_owners: dict[str, set[str]] = defaultdict(set)
    signatures: dict[str, set[str]] = defaultdict(set)
    for item in NEW:
        for entity in item["source_entity_names"]:
            entity_owners[revision.normalize_entity(entity)].add(item["question_id"])
        for evidence_id in item["source_evidence_ids"]:
            evidence_owners[evidence_id].add(item["question_id"])
        for signature in revision.component_signatures(item):
            signatures[signature.rsplit("::", 1)[0]].add(item["question_id"])
    assert not {key: owners for key, owners in entity_owners.items() if len(owners) > 1}
    assert not {key: owners for key, owners in evidence_owners.items() if len(owners) > 1}
    assert not {key: owners for key, owners in signatures.items() if len(owners) > 1}


def test_multi_target_replacements_reuse_neither_standalone_nor_other_components():
    standalone_entities = {
        revision.normalize_entity(entity)
        for item in NEW if "+" not in item["domain"] for entity in item["source_entity_names"]
    }
    standalone_evidence = {
        evidence_id for item in NEW if "+" not in item["domain"] for evidence_id in item["source_evidence_ids"]
    }
    replacement_components = [
        (revision.normalize_entity(entity), evidence_id)
        for qid in revision.MULTI_REPLACE_IDS
        for entity, evidence_id in zip(NEW_BY_ID[qid]["source_entity_names"], NEW_BY_ID[qid]["source_evidence_ids"])
    ]
    assert len(replacement_components) == len(set(replacement_components)) == 6
    assert not ({entity for entity, _ in replacement_components} & standalone_entities)
    assert not ({evidence for _, evidence in replacement_components} & standalone_evidence)


def test_known_duplicate_and_reuse_pairs_are_eliminated():
    for replaced, prior in revision.DUPLICATED_WITH.items():
        assert revision.normalize_text(NEW_BY_ID[replaced]["question"]) != revision.normalize_text(NEW_BY_ID[prior]["question"])
        assert not (set(NEW_BY_ID[replaced]["source_evidence_ids"]) & set(NEW_BY_ID[prior]["source_evidence_ids"]))


def test_distribution_source_quality_and_evidence_validity():
    assert Counter(item["domain"] for item in NEW) == Counter({
        "herbal_medicine": 60, "syndrome_differentiation": 25,
        "herbal_medicine + syndrome_differentiation": 15,
    })
    assert Counter(item["difficulty"] for item in NEW) == Counter({"easy": 40, "medium": 40, "hard": 20})
    corpus_ids = {chunk["chunk_id"] for chunk in revision.rows(revision.CORPUS)}
    for item in NEW:
        assert item["held_out"] is True and set(item["source_evidence_ids"]) <= corpus_ids
        for fact in item["gold_facts"]:
            assert fact["fact"].strip() and fact["evidence_excerpt"].strip()
            assert set(fact["preferred_evidence_ids"]) <= corpus_ids
            assert not revision._is_cross_reference(fact["fact"].split(":", 1)[-1])


def test_duplicate_audit_and_leakage_report_pass():
    audit = json.loads((BENCH / "duplicate_audit_rq4_v1_2.json").read_text(encoding="utf-8"))
    assert audit["status"] == "PASS"
    assert audit["unique_question_ids"] == audit["unique_normalized_questions"] == 100
    for key, value in audit.items():
        if key.endswith("conflicts") or key.endswith("overlap") or key.endswith("duplicates"):
            assert value == []


def test_final_packet_is_complete_protected_and_blank():
    assert len(PACKET) == 232 and len({row["row_id"] for row in PACKET}) == 232
    assert len({row["question_id"] for row in PACKET}) == 100
    required = {
        "row_id", "question_id", "domain", "difficulty", "question", "gold_atomic_fact",
        "gold_fact_index", "preferred_evidence_id", "acceptable_alternate_evidence_ids", "evidence_excerpt",
        "source_entity_names", "revision_origin",
    }
    assert required <= set(PACKET[0])
    assert all(not row["source_review_status"] and not row["review_reason"] and not row["confidence"] for row in PACKET)


def test_revision_ledger_has_all_17_replacements_and_audit_fields():
    ledger = revision._read_csv(BENCH / "revision_v1_2/second_review_revision_ledger.csv")
    assert len(ledger) == 17 and {row["question_id"] for row in ledger} == revision.REPLACE_IDS
    assert all(row["why_genuinely_unused"] and row["replacement_gold_signature"] for row in ledger)


def test_v1_2_draft_remains_unfrozen_and_pipeline_never_skips_review_gate():
    state = json.loads((revision.RQ4 / "rq4_state.json").read_text(encoding="utf-8"))
    manifest = json.loads((BENCH / "heldout_manifest_rq4_v1_2_draft.json").read_text(encoding="utf-8"))
    assert manifest["frozen"] is False and manifest["provider_calls"] == 0
    assert manifest["source_review"]["final_external_review"] == "PENDING"
    if state["state"] == "BENCHMARK_SOURCE_REVIEW_REQUIRED":
        assert platform.next_action(state["state"]).endswith("external_source_review_v1_2_for_gpt.csv")
    else:
        frozen = json.loads((BENCH / "freeze_manifest_rq4_v1.json").read_text(encoding="utf-8"))
        assert frozen["source_review"] == "232_OF_232_APPROVED"
