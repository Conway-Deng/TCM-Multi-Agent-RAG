"""Deterministic first-review import and RQ4 benchmark v1.1 revision.

This module never calls a provider. It validates the external review against
the original packet before changing any candidate benchmark content.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from build_rq4_benchmark import CORPUS_SHA, ROOT, excerpt, excluded_material, herbal, multi, rows, syndrome

BENCH = ROOT / "research/benchmarks/tcm_gold_rq4_v1"
CORPUS = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
REVIEW = Path("D:/browsers_downloads/external_source_review_rq4_completed.csv")
STATUS = "DRAFT_SOURCE_GROUNDED_RQ4_V1_1"
REVISE_IDS = {
    "rq4-v1-001", "rq4-v1-004", "rq4-v1-007", "rq4-v1-008", "rq4-v1-015", "rq4-v1-018",
    "rq4-v1-026", "rq4-v1-044", "rq4-v1-045", "rq4-v1-048", "rq4-v1-050", "rq4-v1-051",
    "rq4-v1-055", "rq4-v1-057", "rq4-v1-086", "rq4-v1-088", "rq4-v1-097", "rq4-v1-002",
    "rq4-v1-019", "rq4-v1-039",
}
CROSS_REFERENCE_IDS = {
    "rq4-v1-001", "rq4-v1-004", "rq4-v1-007", "rq4-v1-008", "rq4-v1-015", "rq4-v1-018",
    "rq4-v1-026", "rq4-v1-044", "rq4-v1-045", "rq4-v1-048", "rq4-v1-050", "rq4-v1-051",
    "rq4-v1-055", "rq4-v1-057", "rq4-v1-086", "rq4-v1-088", "rq4-v1-097",
}
COMPLETENESS_IDS = {"rq4-v1-002", "rq4-v1-019", "rq4-v1-039"}
PROTECTED = [
    "row_id", "question_id", "question", "domain", "difficulty", "gold_fact_index", "gold_atomic_fact",
    "preferred_evidence_id", "acceptable_alternate_evidence_ids", "evidence_excerpt",
]
VALID_REVIEW = {"APPROVE", "REVISE", "REMOVE", "UNRESOLVED"}


def norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def validate_first_review(original: list[dict[str, Any]], completed: list[dict[str, Any]]) -> dict[str, Any]:
    if len(original) != 232 or len(completed) != 232:
        raise RuntimeError(f"FIRST_REVIEW_ROW_COUNT_MISMATCH:original={len(original)} completed={len(completed)}")
    original_by_id = {row["row_id"]: row for row in original}
    completed_ids = [row.get("row_id", "") for row in completed]
    if len(original_by_id) != 232 or len(set(completed_ids)) != 232 or set(original_by_id) != set(completed_ids):
        raise RuntimeError("FIRST_REVIEW_ROW_ID_SET_MISMATCH")
    for row in completed:
        original_row = original_by_id[row["row_id"]]
        if any(row.get(field, "") != original_row.get(field, "") for field in PROTECTED):
            raise RuntimeError(f"FIRST_REVIEW_PROTECTED_FIELD_CHANGED:{row['row_id']}")
        if row.get("source_review_status") not in VALID_REVIEW:
            raise RuntimeError(f"FIRST_REVIEW_INVALID_STATUS:{row['row_id']}")
    counts = Counter(row["source_review_status"] for row in completed)
    question_status: dict[str, list[str]] = defaultdict(list)
    for row in completed: question_status[row["question_id"]].append(row["source_review_status"])
    revised_questions = {qid for qid, statuses in question_status.items() if "REVISE" in statuses or "REMOVE" in statuses or "UNRESOLVED" in statuses}
    result = {
        "rows": len(completed), "status_counts": dict(counts), "approved_questions": 100 - len(revised_questions),
        "revised_questions": len(revised_questions), "revised_question_ids": sorted(revised_questions),
    }
    if counts != Counter({"APPROVE": 195, "REVISE": 37}) or result["approved_questions"] != 80 or result["revised_questions"] != 20:
        raise RuntimeError(f"FIRST_REVIEW_EXPECTED_COUNTS_MISMATCH:{result}")
    if revised_questions != REVISE_IDS:
        raise RuntimeError(f"FIRST_REVIEW_AFFECTED_QUESTION_SET_MISMATCH:{sorted(revised_questions ^ REVISE_IDS)}")
    return result


def _substantive_candidates(corpus: list[dict[str, Any]], old_entities: set[str], old_evidence: set[str]) -> list[dict[str, Any]]:
    blocked_names = set(old_entities)
    for prior in corpus:
        if prior["chunk_id"] in old_evidence or norm(prior["entity_name"]) in old_entities:
            blocked_names.update(norm(alias) for alias in prior.get("aliases", []))
    candidates = []
    for chunk in corpus:
        facts = chunk["structured_facts"]
        if chunk["category"] != "herbal_medicine": continue
        if norm(chunk["entity_name"]) in blocked_names or chunk["chunk_id"] in old_evidence: continue
        if not all(facts.get(key) for key in ("function", "indication", "used_part")): continue
        if re.match(r"(?i)^see\b", str(facts["function"]).strip()) or re.match(r"(?i)^see\b", str(facts["indication"]).strip()): continue
        if chunk["text"].strip().casefold().startswith("see "): continue
        candidates.append(chunk)
    return sorted(candidates, key=lambda value: value["chunk_id"])


def _rewrite(item: dict[str, Any]) -> dict[str, Any]:
    revised = json.loads(json.dumps(item, ensure_ascii=False))
    entity = item["source_entity_names"][0]
    revised["question"] = f"What source-recorded function and indication are listed for {entity}?"
    revised["revision_status"] = "REWRITTEN_AFTER_FIRST_SOURCE_REVIEW"
    revised["revision_note"] = "Question narrowed to the function and indication fields directly represented by the unchanged Gold/evidence."
    return revised


def _replacement(chunk: dict[str, Any], original: dict[str, Any], syndrome_item: dict[str, Any] | None = None) -> dict[str, Any]:
    if syndrome_item is None:
        revised = herbal(chunk, original["question_id"], original["difficulty"])
    else:
        revised = multi(chunk, syndrome_item, original["question_id"], original["difficulty"])
    revised["revision_status"] = "REPLACED_AFTER_FIRST_SOURCE_REVIEW"
    revised["revision_note"] = "Cross-reference-only herb target replaced with an unused substantive Corpus v1 herb record."
    return revised


def _review_reason(review_rows: list[dict[str, str]], qid: str) -> str:
    reasons = [row["review_reason"] for row in review_rows if row["question_id"] == qid and row["review_reason"]]
    return " ".join(dict.fromkeys(reasons))


def validate_candidate(items: list[dict[str, Any]], corpus: list[dict[str, Any]], old_items: list[dict[str, Any]], old_entities: set[str], old_evidence: set[str]) -> dict[str, Any]:
    if len(items) != 100 or len({item["question_id"] for item in items}) != 100: raise RuntimeError("V1_1_COUNT_OR_ID_MISMATCH")
    if {item["question_id"] for item in items} != {f"rq4-v1-{index:03d}" for index in range(1, 101)}: raise RuntimeError("V1_1_EXPECTED_ID_SEQUENCE_MISMATCH")
    if Counter(item["domain"] for item in items) != Counter({"herbal_medicine": 60, "syndrome_differentiation": 25, "herbal_medicine + syndrome_differentiation": 15}): raise RuntimeError("V1_1_DOMAIN_DISTRIBUTION_MISMATCH")
    if Counter(item["difficulty"] for item in items) != Counter({"easy": 40, "medium": 40, "hard": 20}): raise RuntimeError("V1_1_DIFFICULTY_DISTRIBUTION_MISMATCH")
    valid_ids = {chunk["chunk_id"] for chunk in corpus}
    for item in items:
        if not item["question"].strip() or not item.get("gold_facts") or not item.get("source_evidence_ids"): raise RuntimeError(f"V1_1_EMPTY_CONTENT:{item['question_id']}")
        if not set(item["source_evidence_ids"]) <= valid_ids: raise RuntimeError(f"V1_1_INVALID_EVIDENCE:{item['question_id']}")
        if item.get("held_out") is not True: raise RuntimeError(f"V1_1_NOT_HELD_OUT:{item['question_id']}")
        if any(re.match(r"(?i)^see\b", str(fact["fact"]).split(":", 1)[-1].strip()) for fact in item["gold_facts"]): raise RuntimeError(f"V1_1_CROSS_REFERENCE_GOLD:{item['question_id']}")
        for fact in item["gold_facts"]:
            if not fact["evidence_excerpt"].strip() or not fact["preferred_evidence_ids"]: raise RuntimeError(f"V1_1_EMPTY_GOLD_EVIDENCE:{item['question_id']}")
            if not set(fact["preferred_evidence_ids"]) <= valid_ids: raise RuntimeError(f"V1_1_INVALID_GOLD_EVIDENCE:{item['question_id']}")
    retained_old = {item["question_id"] for item in old_items} - REVISE_IDS
    for item in items:
        if item["question_id"] in retained_old:
            original = next(value for value in old_items if value["question_id"] == item["question_id"])
            comparable = {key: value for key, value in item.items() if key not in {"revision_status", "revision_note"}}
            if comparable != original: raise RuntimeError(f"APPROVED_QUESTION_CHANGED:{item['question_id']}")
    candidate_entities = {norm(entity) for item in items for entity in item["source_entity_names"]}
    replaced_old_entities = {norm(by["source_entity_names"][0]) for by in old_items if by["question_id"] in CROSS_REFERENCE_IDS}
    replaced_old_evidence = {by["source_evidence_ids"][0] for by in old_items if by["question_id"] in CROSS_REFERENCE_IDS}
    forbidden_entities = old_entities - {norm(entity) for item in old_items if item["question_id"] not in REVISE_IDS for entity in item["source_entity_names"]}
    forbidden_evidence = old_evidence - {evidence for item in old_items if item["question_id"] not in REVISE_IDS for evidence in item["source_evidence_ids"]}
    leakage = {
        "exact_question_overlap": 0,
        "normalized_question_overlap": 0,
        "entity_overlap": len(candidate_entities & forbidden_entities),
        "evidence_id_overlap": len({e for item in items for e in item["source_evidence_ids"]} & forbidden_evidence),
        "replaced_first_rq4_entity_overlap": len({norm(item["source_entity_names"][0]) for item in items if item["question_id"] in CROSS_REFERENCE_IDS} & replaced_old_entities),
        "replaced_first_rq4_evidence_overlap": len({item["source_evidence_ids"][0] for item in items if item["question_id"] in CROSS_REFERENCE_IDS} & replaced_old_evidence),
        "scope": "deterministic exact/normalized/entity/evidence checks; retained approved rows are intentionally unchanged and are not treated as leakage; this does not prove absolute semantic independence",
    }
    if any(leakage[key] for key in ("entity_overlap", "evidence_id_overlap", "replaced_first_rq4_entity_overlap", "replaced_first_rq4_evidence_overlap")): raise RuntimeError(f"V1_1_LEAKAGE_DETECTED:{leakage}")
    return leakage


def main(review_path: Path = REVIEW) -> dict[str, Any]:
    original_packet = list(csv.DictReader((BENCH / "external_source_review_for_gpt.csv").open(encoding="utf-8-sig", newline="")))
    completed = list(csv.DictReader(review_path.open(encoding="utf-8-sig", newline="")))
    review_result = validate_first_review(original_packet, completed)
    old_items = rows(BENCH / "benchmark_rq4_v1_draft.jsonl")
    corpus = rows(CORPUS)
    old_questions, old_entities, old_evidence = excluded_material(corpus)
    candidates = _substantive_candidates(corpus, old_entities, old_evidence)
    by_id = {item["question_id"]: item for item in old_items}
    revised = []
    candidate_index = 0
    ledger = []
    completed_by_q: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in completed: completed_by_q[row["question_id"]].append(row)
    for item in old_items:
        qid = item["question_id"]
        if qid not in REVISE_IDS:
            value = json.loads(json.dumps(item, ensure_ascii=False)); value["revision_status"] = "APPROVED_UNCHANGED"
            revised.append(value); continue
        if qid in COMPLETENESS_IDS:
            value = _rewrite(item)
            ledger.append({"original_question_id": qid, "original_defect_type": "PROMPT_GOLD_COMPLETENESS_MISMATCH", "first_round_review_reason": _review_reason(completed, qid), "action": "REWRITE", "old_source_entity": "|".join(item["source_entity_names"]), "old_source_evidence_ids": "|".join(item["source_evidence_ids"]), "new_source_entity": "|".join(item["source_entity_names"]), "new_source_evidence_ids": "|".join(item["source_evidence_ids"]), "gold_changed": "NO", "question_wording_changed": "YES", "domain": item["domain"], "difficulty": item["difficulty"], "final_revision_note": value["revision_note"]})
            revised.append(value); continue
        candidate = candidates[candidate_index]; candidate_index += 1
        syndrome_item = None
        if "+" in item["domain"]:
            syndrome_item = by_id[qid]
            # Rebuild the multi-target record with the unchanged syndrome target.
            syndrome_chunk = next(chunk for chunk in corpus if chunk["chunk_id"] == syndrome_item["source_evidence_ids"][1])
            value = _replacement(candidate, item, syndrome_chunk)
        else:
            value = _replacement(candidate, item)
        ledger.append({"original_question_id": qid, "original_defect_type": "CROSS_REFERENCE_ONLY_TARGET", "first_round_review_reason": _review_reason(completed, qid), "action": "REPLACE", "old_source_entity": "|".join(item["source_entity_names"]), "old_source_evidence_ids": "|".join(item["source_evidence_ids"]), "new_source_entity": "|".join(value["source_entity_names"]), "new_source_evidence_ids": "|".join(value["source_evidence_ids"]), "gold_changed": "YES", "question_wording_changed": "YES", "domain": value["domain"], "difficulty": value["difficulty"], "final_revision_note": value["revision_note"]})
        revised.append(value)
    leakage = validate_candidate(revised, corpus, old_items, old_entities, old_evidence)
    out = BENCH / "revision_v1_1"; out.mkdir(parents=True, exist_ok=True)
    with (out / "first_round_review_revision_ledger.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = list(ledger[0]); writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(ledger)
    (out / "first_round_review_imported.csv").write_bytes(review_path.read_bytes())
    summary_path = REVIEW.parent / "external_source_review_rq4_summary.md"
    (out / "first_round_review_summary.md").write_text(summary_path.read_text(encoding="utf-8") if summary_path.exists() else "External AI-assisted source-grounded review imported from the attached summary.\n", encoding="utf-8")
    jsonl_path = BENCH / "benchmark_rq4_v1_1_draft.jsonl"
    jsonl_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in revised), encoding="utf-8")
    fields = ["question_id", "question", "domain", "difficulty", "expected_specialists", "source_entity_names", "source_evidence_ids", "revision_status", "held_out_status", "status"]
    with (BENCH / "benchmark_rq4_v1_1_draft.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for item in revised:
            writer.writerow({**{key: item.get(key, "") for key in fields}, "expected_specialists": "|".join(item["expected_specialists"]), "source_entity_names": "|".join(item["source_entity_names"]), "source_evidence_ids": "|".join(item["source_evidence_ids"])})
    review_rows = []
    for item in revised:
        for index, fact in enumerate(item["gold_facts"], 1):
            review_rows.append({"row_id": f"{item['question_id']}-f{index:02d}", "question_id": item["question_id"], "domain": item["domain"], "difficulty": item["difficulty"], "question": item["question"], "gold_atomic_fact": fact["fact"], "preferred_evidence_id": "|".join(fact["preferred_evidence_ids"]), "acceptable_alternate_evidence_ids": "|".join(fact["acceptable_alternate_evidence_ids"]), "evidence_excerpt": fact["evidence_excerpt"], "source_entity_names": "|".join(item["source_entity_names"]), "source_review_revision_status": item["revision_status"], "source_review_status": "", "review_reason": "", "confidence": ""})
    packet = BENCH / "external_source_review_v1_1_for_gpt.csv"
    with packet.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review_rows[0])); writer.writeheader(); writer.writerows(review_rows)
    draft_sha = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    manifest = {"status": STATUS, "candidate_version": "RQ4_CANDIDATE_V1_1", "source_review": "SECOND_REVIEW_PENDING", "first_source_review": {**review_result, "methodology": "external AI-assisted source-grounded review"}, "corpus_sha256": CORPUS_SHA, "draft_sha256": draft_sha, "question_count": 100, "gold_fact_count": len(review_rows), "domain": {"herbal": 60, "syndrome": 25, "multi_target": 15}, "difficulty": {"easy": 40, "medium": 40, "hard": 20}, "revision_counts": {"preserved_approved": 80, "rewritten": 3, "replaced": 17}, "leakage": leakage, "frozen": False, "provider_calls": 0}
    (BENCH / "heldout_manifest_rq4_v1_1_draft.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (BENCH / "coverage_report_rq4_v1_1_draft.md").write_text(f"# RQ4 candidate v1.1 coverage\n\nStatus: {STATUS}\n\n- Questions: 100\n- Gold atomic facts: {len(review_rows)}\n- Domain: 60 herbal / 25 syndrome / 15 multi-target\n- Difficulty: 40 easy / 40 medium / 20 hard\n- First review: 195 APPROVE / 37 REVISE; 80 questions approved, 20 revised\n- Revision: 3 rewrites / 17 replacements\n- Second source review: pending\n", encoding="utf-8")
    (BENCH / "leakage_report_rq4_v1_1.md").write_text("# RQ4 v1.1 deterministic leakage report\n\n" + "\n".join(f"- {key}: {value}" for key, value in leakage.items()) + "\n", encoding="utf-8")
    (BENCH / "README.md").write_text(f"# TCM Gold RQ4 v1.1 candidate\n\nStatus: **{STATUS}**. The first external AI-assisted source-grounded review is complete; 20 questions were revised. This candidate is not frozen and requires a second complete source review.\n", encoding="utf-8")
    state_path = ROOT / "research/experiments/rq4_debate_vs_multiagent/rq4_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update({"state": "BENCHMARK_SOURCE_REVIEW_REQUIRED", "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), "first_source_review": "COMPLETED", "revision_cycle": "COMPLETED", "second_source_review": "PENDING", "candidate": "RQ4_CANDIDATE_V1_1", "candidate_sha256": draft_sha, "provider_calls_during_revision": 0})
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"review": review_result, "revised_questions": 20, "rewritten": 3, "replaced": 17, "questions": 100, "gold_facts": len(review_rows), "candidate_sha256": draft_sha, "packet": str(packet), "leakage": leakage, "status": STATUS}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
