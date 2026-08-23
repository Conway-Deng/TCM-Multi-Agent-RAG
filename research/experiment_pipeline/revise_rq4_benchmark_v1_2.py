"""Import RQ4 v1.1 review two and build the source-reviewable v1.2 candidate.

The revision is deterministic and local-only. It preserves all 83 approved
questions and replaces only the 17 questions whose targets were duplicated or
reused. This module must never call an LLM or provider.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from build_rq4_benchmark import CORPUS_SHA, ROOT, excluded_material, herbal, multi, rows, syndrome


BENCH = ROOT / "research/benchmarks/tcm_gold_rq4_v1"
RQ4 = ROOT / "research/experiments/rq4_debate_vs_multiagent"
CORPUS = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
REVIEW = Path("D:/browsers_downloads/rq4_v1_1_second_review_completed.csv")
REVIEW_SUMMARY = Path("D:/browsers_downloads/rq4_v1_1_second_review_summary.md")
STATUS = "DRAFT_SOURCE_GROUNDED_RQ4_V1_2"
STATE = "BENCHMARK_SOURCE_REVIEW_REQUIRED"

REPLACE_IDS = {
    "rq4-v1-001", "rq4-v1-004", "rq4-v1-007", "rq4-v1-008", "rq4-v1-015",
    "rq4-v1-018", "rq4-v1-026", "rq4-v1-044", "rq4-v1-045", "rq4-v1-048",
    "rq4-v1-050", "rq4-v1-051", "rq4-v1-055", "rq4-v1-057", "rq4-v1-086",
    "rq4-v1-088", "rq4-v1-097",
}
MULTI_REPLACE_IDS = {"rq4-v1-086", "rq4-v1-088", "rq4-v1-097"}
DUPLICATED_WITH = {
    "rq4-v1-001": "rq4-v1-003", "rq4-v1-004": "rq4-v1-005",
    "rq4-v1-007": "rq4-v1-006", "rq4-v1-008": "rq4-v1-009",
    "rq4-v1-015": "rq4-v1-010", "rq4-v1-018": "rq4-v1-012",
    "rq4-v1-026": "rq4-v1-013", "rq4-v1-044": "rq4-v1-014",
    "rq4-v1-045": "rq4-v1-017", "rq4-v1-048": "rq4-v1-020",
    "rq4-v1-050": "rq4-v1-022", "rq4-v1-051": "rq4-v1-023",
    "rq4-v1-055": "rq4-v1-024", "rq4-v1-057": "rq4-v1-025",
    "rq4-v1-086": "rq4-v1-027", "rq4-v1-088": "rq4-v1-028",
    "rq4-v1-097": "rq4-v1-030",
}
PROTECTED_REVIEW_FIELDS = {
    "row_id", "question_id", "domain", "difficulty", "question", "gold_atomic_fact",
    "preferred_evidence_id", "acceptable_alternate_evidence_ids", "evidence_excerpt",
    "source_entity_names", "source_review_revision_status",
}
REVIEW_FIELDS = {"source_review_status", "review_reason", "confidence"}
VALID_REVIEW = {"APPROVE", "REVISE", "REMOVE", "UNRESOLVED"}


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = "".join(character if character.isalnum() else " " for character in text)
    return " ".join(text.split())


def normalize_entity(value: object) -> str:
    return normalize_text(value)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_second_review(expected: list[dict[str, str]], completed: list[dict[str, str]]) -> dict[str, Any]:
    if len(expected) != 232 or len(completed) != 232:
        raise RuntimeError(f"SECOND_REVIEW_ROW_COUNT_MISMATCH:expected={len(expected)} completed={len(completed)}")
    expected_ids = [row.get("row_id", "") for row in expected]
    completed_ids = [row.get("row_id", "") for row in completed]
    if len(set(expected_ids)) != 232 or len(set(completed_ids)) != 232 or set(expected_ids) != set(completed_ids):
        raise RuntimeError("SECOND_REVIEW_ROW_ID_SET_MISMATCH")
    if set(expected[0]) != set(completed[0]):
        raise RuntimeError("SECOND_REVIEW_COLUMN_SET_MISMATCH")
    expected_by_id = {row["row_id"]: row for row in expected}
    protected = set(expected[0]) - REVIEW_FIELDS
    if not PROTECTED_REVIEW_FIELDS <= protected:
        raise RuntimeError("SECOND_REVIEW_PACKET_MISSING_PROTECTED_FIELDS")
    for row in completed:
        original = expected_by_id[row["row_id"]]
        changed = [field for field in protected if row.get(field, "") != original.get(field, "")]
        if changed:
            raise RuntimeError(f"SECOND_REVIEW_PROTECTED_FIELD_CHANGED:{row['row_id']}:{','.join(sorted(changed))}")
        if row.get("source_review_status") not in VALID_REVIEW:
            raise RuntimeError(f"SECOND_REVIEW_INVALID_STATUS:{row['row_id']}")
    counts = Counter(row["source_review_status"] for row in completed)
    by_question: dict[str, list[str]] = defaultdict(list)
    for row in completed:
        by_question[row["question_id"]].append(row["source_review_status"])
    affected = {
        qid for qid, labels in by_question.items()
        if any(label != "APPROVE" for label in labels)
    }
    result = {
        "rows": len(completed),
        "unique_row_ids": len(set(completed_ids)),
        "questions": len(by_question),
        "status_counts": dict(counts),
        "approved_questions": len(by_question) - len(affected),
        "questions_requiring_revision": len(affected),
        "revised_question_ids": sorted(affected),
        "protected_fields_unchanged": True,
    }
    if counts != Counter({"APPROVE": 187, "REVISE": 45}):
        raise RuntimeError(f"SECOND_REVIEW_EXPECTED_COUNTS_MISMATCH:{result}")
    if len(by_question) != 100 or len(by_question) - len(affected) != 83 or affected != REPLACE_IDS:
        raise RuntimeError(f"SECOND_REVIEW_QUESTION_SET_MISMATCH:{result}")
    return result


def _walk_reserved(value: object, questions: set[str], entities: set[str], evidence: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_norm = key.casefold()
            if key_norm in {"question", "query", "prompt"} and isinstance(item, str):
                questions.add(normalize_text(item))
            if key_norm in {"entity_name", "source_entity_names", "entity_names"}:
                values = item if isinstance(item, list) else [item]
                entities.update(normalize_entity(entry) for entry in values if isinstance(entry, str))
            if key_norm in {
                "chunk_id", "evidence_id", "evidence_ids", "source_evidence_ids",
                "preferred_evidence_ids", "acceptable_alternate_evidence_ids",
            }:
                values = item if isinstance(item, list) else [item]
                evidence.update(entry for entry in values if isinstance(entry, str) and entry.startswith("tcmv1-"))
            _walk_reserved(item, questions, entities, evidence)
    elif isinstance(value, list):
        for item in value:
            _walk_reserved(item, questions, entities, evidence)
    elif isinstance(value, str):
        evidence.update(re.findall(r"tcmv1-[0-9a-f]{24}", value))


def _development_reserved() -> tuple[set[str], set[str], set[str]]:
    questions: set[str] = set()
    entities: set[str] = set()
    evidence: set[str] = set()
    for base in (ROOT / "research/datasets", ROOT / "research/smoke_tests", ROOT / "backend/evaluation"):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix.casefold() not in {".json", ".jsonl", ".csv"}:
                continue
            try:
                if path.suffix.casefold() == ".csv":
                    values: Iterable[object] = _read_csv(path)
                elif path.suffix.casefold() == ".jsonl":
                    values = rows(path)
                else:
                    values = [json.loads(path.read_text(encoding="utf-8-sig"))]
                for value in values:
                    _walk_reserved(value, questions, entities, evidence)
            except (UnicodeDecodeError, json.JSONDecodeError, csv.Error):
                continue
    return questions, entities, evidence


def _requested_fields(item: dict[str, Any], component_index: int) -> str:
    if item["domain"] == "syndrome_differentiation" or (
        item["domain"].startswith("herbal_medicine +") and component_index == 1
    ):
        return "definition"
    question = normalize_text(item["question"])
    if "traditional properties" in question:
        return "traditional_properties|meridians|traditional_class"
    if "used part" in question:
        return "function|indication|used_part"
    return "function|indication"


def component_signatures(item: dict[str, Any]) -> list[str]:
    signatures = []
    for index, (entity, evidence_id) in enumerate(zip(item["source_entity_names"], item["source_evidence_ids"])):
        category = "syndrome_differentiation" if (
            item["domain"] == "syndrome_differentiation" or
            (item["domain"].startswith("herbal_medicine +") and index == 1)
        ) else "herbal_medicine"
        signatures.append("::".join((category, normalize_entity(entity), _requested_fields(item, index), evidence_id)))
    return signatures


def _reserve_chunk(chunk: dict[str, Any], reserved_entities: set[str], reserved_evidence: set[str]) -> None:
    reserved_entities.add(normalize_entity(chunk["entity_name"]))
    reserved_entities.update(normalize_entity(alias) for alias in chunk.get("aliases", []) if alias)
    reserved_evidence.add(chunk["chunk_id"])


def _is_cross_reference(value: object) -> bool:
    return bool(re.match(r"(?i)^\s*see\b", str(value or "")))


def _substantive_herb(chunk: dict[str, Any]) -> bool:
    facts = chunk.get("structured_facts", {})
    if chunk.get("category") != "herbal_medicine" or not chunk.get("source_name") or not chunk.get("text", "").strip():
        return False
    if chunk["text"].strip().casefold().startswith("see "):
        return False
    if facts.get("properties_english"):
        values = [facts.get("properties_english"), facts.get("meridians_english"), facts.get("class_english")]
    else:
        values = [facts.get("function"), facts.get("indication"), facts.get("used_part")]
    return all(value and not _is_cross_reference(value) for value in values)


def _substantive_syndrome(chunk: dict[str, Any]) -> bool:
    definition = chunk.get("structured_facts", {}).get("definition_original")
    return bool(
        chunk.get("category") == "syndrome_differentiation"
        and chunk.get("source_name") and chunk.get("text", "").strip()
        and definition and not _is_cross_reference(definition)
        and not chunk["text"].strip().casefold().startswith("see ")
    )


def _next_chunk(
    candidates: list[dict[str, Any]],
    reserved_entities: set[str],
    reserved_evidence: set[str],
) -> dict[str, Any]:
    for chunk in candidates:
        names = {normalize_entity(chunk["entity_name"])} | {
            normalize_entity(alias) for alias in chunk.get("aliases", []) if alias
        }
        if chunk["chunk_id"] in reserved_evidence or names & reserved_entities:
            continue
        _reserve_chunk(chunk, reserved_entities, reserved_evidence)
        return chunk
    raise RuntimeError("NO_GENUINELY_UNUSED_SUBSTANTIVE_CORPUS_TARGET_AVAILABLE")


def _make_reserved(
    corpus: list[dict[str, Any]],
    original: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> tuple[set[str], set[str], set[str], set[str], dict[str, int]]:
    questions, entities, evidence = excluded_material(corpus)
    dev_questions, dev_entities, dev_evidence = _development_reserved()
    questions |= {normalize_text(value) for value in dev_questions}
    entities |= {normalize_entity(value) for value in dev_entities}
    evidence |= dev_evidence
    signatures: set[str] = set()
    corpus_by_id = {chunk["chunk_id"]: chunk for chunk in corpus}
    # All old RQ4 targets remain reserved, including the targets now being replaced.
    for item in original + current:
        questions.add(normalize_text(item["question"]))
        for entity in item["source_entity_names"]:
            entities.add(normalize_entity(entity))
        for evidence_id in item["source_evidence_ids"]:
            evidence.add(evidence_id)
            if evidence_id in corpus_by_id:
                _reserve_chunk(corpus_by_id[evidence_id], entities, evidence)
        signatures.update(component_signatures(item))
    counts = {
        "reserved_question_normalized": len(questions),
        "reserved_entities": len(entities),
        "reserved_evidence_ids": len(evidence),
        "reserved_gold_targets": len(signatures),
    }
    return questions, entities, evidence, signatures, counts


def _review_reason(review: list[dict[str, str]], qid: str) -> str:
    return " ".join(dict.fromkeys(row["review_reason"] for row in review if row["question_id"] == qid and row["review_reason"]))


def _replacement_note(qid: str) -> str:
    kind = "multi-target component evidence reuse" if qid in MULTI_REPLACE_IDS else "exact intra-benchmark duplication"
    return f"Replaced after second source review to repair {kind}; selected under mutable global reservation and source-quality guards."


def _changed_without_revision_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key not in {"revision_status", "revision_note"}}


def _duplicate_audit(
    items: list[dict[str, Any]],
    approved_ids: set[str],
    replacement_ids: set[str],
    external_questions: set[str],
    external_entities: set[str],
    external_evidence: set[str],
) -> dict[str, Any]:
    def conflicts(values: Iterable[tuple[str, str]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for value, qid in values:
            grouped[value].append(qid)
        return [
            {"value": value, "question_ids": sorted(set(qids))}
            for value, qids in sorted(grouped.items()) if value and len(set(qids)) > 1
        ]

    exact = conflicts((item["question"], item["question_id"]) for item in items)
    normalized = conflicts((normalize_text(item["question"]), item["question_id"]) for item in items)
    entity = conflicts((normalize_entity(entity), item["question_id"]) for item in items for entity in item["source_entity_names"])
    evidence = conflicts((evidence_id, item["question_id"]) for item in items for evidence_id in item["source_evidence_ids"])
    signatures = conflicts((signature.rsplit("::", 1)[0], item["question_id"]) for item in items for signature in component_signatures(item))
    replacement_items = [item for item in items if item["question_id"] in replacement_ids]
    replacement_questions = {normalize_text(item["question"]) for item in replacement_items}
    replacement_entities = {normalize_entity(entity) for item in replacement_items for entity in item["source_entity_names"]}
    replacement_evidence = {evidence_id for item in replacement_items for evidence_id in item["source_evidence_ids"]}
    approved_items = [item for item in items if item["question_id"] in approved_ids]
    approved_entities = {normalize_entity(entity) for item in approved_items for entity in item["source_entity_names"]}
    approved_evidence = {evidence_id for item in approved_items for evidence_id in item["source_evidence_ids"]}
    return {
        "question_count": len(items),
        "unique_question_ids": len({item["question_id"] for item in items}),
        "unique_normalized_questions": len({normalize_text(item["question"]) for item in items}),
        "raw_question_duplicates": exact,
        "normalized_question_duplicates": normalized,
        "entity_material_target_conflicts": entity,
        "evidence_id_conflicts": evidence,
        "gold_target_signature_conflicts": signatures,
        "replacement_to_approved_entity_overlap": sorted(replacement_entities & approved_entities),
        "replacement_to_approved_evidence_overlap": sorted(replacement_evidence & approved_evidence),
        "replacement_to_external_question_overlap": sorted(replacement_questions & external_questions),
        "replacement_to_external_entity_overlap": sorted(replacement_entities & external_entities),
        "replacement_to_external_evidence_overlap": sorted(replacement_evidence & external_evidence),
        "replacement_to_replacement_entity_conflicts": conflicts(
            (normalize_entity(entity), item["question_id"]) for item in replacement_items for entity in item["source_entity_names"]
        ),
        "replacement_to_replacement_evidence_conflicts": conflicts(
            (evidence_id, item["question_id"]) for item in replacement_items for evidence_id in item["source_evidence_ids"]
        ),
        "deterministic_limitation": (
            "Exact, normalized-text, entity/alias, evidence-ID, requested-field, and deterministic Gold-target signatures "
            "are checked. This does not prove semantic independence beyond those deterministic representations."
        ),
    }


def _assert_clean_audit(audit: dict[str, Any]) -> None:
    conflict_keys = {
        "raw_question_duplicates", "normalized_question_duplicates", "entity_material_target_conflicts",
        "evidence_id_conflicts", "gold_target_signature_conflicts", "replacement_to_approved_entity_overlap",
        "replacement_to_approved_evidence_overlap", "replacement_to_external_question_overlap",
        "replacement_to_external_entity_overlap", "replacement_to_external_evidence_overlap",
        "replacement_to_replacement_entity_conflicts", "replacement_to_replacement_evidence_conflicts",
    }
    failures = {key: audit[key] for key in conflict_keys if audit.get(key)}
    if failures:
        raise RuntimeError(f"V1_2_DUPLICATE_OR_LEAKAGE_CONFLICT:{json.dumps(failures, ensure_ascii=False)}")


def validate_candidate(
    items: list[dict[str, Any]],
    old_items: list[dict[str, Any]],
    corpus: list[dict[str, Any]],
    audit: dict[str, Any],
) -> dict[str, Any]:
    old_by_id = {item["question_id"]: item for item in old_items}
    new_by_id = {item["question_id"]: item for item in items}
    approved_ids = set(old_by_id) - REPLACE_IDS
    if len(items) != 100 or len(new_by_id) != 100:
        raise RuntimeError("V1_2_COUNT_OR_ID_MISMATCH")
    if set(old_by_id) != set(new_by_id):
        raise RuntimeError("V1_2_QUESTION_ID_SET_CHANGED")
    if Counter(item["domain"] for item in items) != Counter({
        "herbal_medicine": 60, "syndrome_differentiation": 25,
        "herbal_medicine + syndrome_differentiation": 15,
    }):
        raise RuntimeError("V1_2_DOMAIN_DISTRIBUTION_MISMATCH")
    if Counter(item["difficulty"] for item in items) != Counter({"easy": 40, "medium": 40, "hard": 20}):
        raise RuntimeError("V1_2_DIFFICULTY_DISTRIBUTION_MISMATCH")
    for qid in approved_ids:
        if new_by_id[qid] != old_by_id[qid]:
            raise RuntimeError(f"V1_2_APPROVED_QUESTION_CHANGED:{qid}")
    changed = {qid for qid in old_by_id if new_by_id[qid] != old_by_id[qid]}
    if changed != REPLACE_IDS:
        raise RuntimeError(f"V1_2_CHANGED_QUESTION_SET_MISMATCH:{sorted(changed ^ REPLACE_IDS)}")
    for qid in REPLACE_IDS:
        old = old_by_id[qid]
        new = new_by_id[qid]
        if set(old["source_evidence_ids"]) & set(new["source_evidence_ids"]):
            raise RuntimeError(f"V1_2_REPLACEMENT_REUSED_OLD_EVIDENCE:{qid}")
        if {normalize_entity(value) for value in old["source_entity_names"]} & {
            normalize_entity(value) for value in new["source_entity_names"]
        }:
            raise RuntimeError(f"V1_2_REPLACEMENT_REUSED_OLD_ENTITY:{qid}")
    valid_ids = {chunk["chunk_id"] for chunk in corpus}
    corpus_by_id = {chunk["chunk_id"]: chunk for chunk in corpus}
    prompt_gold_mismatches: list[str] = []
    for item in items:
        if item.get("held_out") is not True or not item.get("gold_facts") or not item.get("question", "").strip():
            raise RuntimeError(f"V1_2_INVALID_ITEM:{item['question_id']}")
        if not set(item["source_evidence_ids"]) <= valid_ids:
            raise RuntimeError(f"V1_2_INVALID_EVIDENCE:{item['question_id']}")
        for fact in item["gold_facts"]:
            if not fact.get("fact", "").strip() or not fact.get("evidence_excerpt", "").strip():
                raise RuntimeError(f"V1_2_EMPTY_GOLD:{item['question_id']}")
            if not set(fact.get("preferred_evidence_ids", [])) <= valid_ids:
                raise RuntimeError(f"V1_2_INVALID_GOLD_EVIDENCE:{item['question_id']}")
            if _is_cross_reference(fact["fact"].split(":", 1)[-1]):
                raise RuntimeError(f"V1_2_CROSS_REFERENCE_GOLD:{item['question_id']}")
            if not any(
                corpus_by_id[evidence_id]["text"] in fact["evidence_excerpt"]
                for evidence_id in fact["preferred_evidence_ids"]
            ):
                raise RuntimeError(f"V1_2_GOLD_EXCERPT_NOT_FROM_PREFERRED_EVIDENCE:{item['question_id']}")
        question = normalize_text(item["question"])
        facts = [normalize_text(fact["fact"]) for fact in item["gold_facts"]]
        if item["domain"] == "herbal_medicine":
            if "traditional properties" in question:
                expected_labels = ("traditional properties", "meridians", "traditional class")
            elif "used part" in question:
                expected_labels = ("function", "indication", "used part")
            else:
                expected_labels = ("function", "indication")
            if any(not any(label in fact for fact in facts) for label in expected_labels):
                prompt_gold_mismatches.append(item["question_id"])
        elif item["domain"] == "syndrome_differentiation":
            if len(facts) != 1 or normalize_entity(item["source_entity_names"][0]) not in facts[0]:
                prompt_gold_mismatches.append(item["question_id"])
        elif len(facts) != 2 or len(item["source_entity_names"]) != 2 or any(
            not any(normalize_entity(entity) in fact for fact in facts)
            for entity in item["source_entity_names"]
        ):
            prompt_gold_mismatches.append(item["question_id"])
    if prompt_gold_mismatches:
        raise RuntimeError(f"V1_2_PROMPT_GOLD_MISMATCH:{','.join(prompt_gold_mismatches)}")
    _assert_clean_audit(audit)
    return {
        "approved_questions_unchanged": len(approved_ids),
        "changed_question_ids": sorted(changed),
        "valid_source_evidence": True,
        "cross_reference_issues": 0,
        "prompt_gold_mismatches": 0,
    }


def _write_csv(path: Path, values: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def main(review_path: Path = REVIEW) -> dict[str, Any]:
    if hashlib.sha256(CORPUS.read_bytes()).hexdigest() != CORPUS_SHA:
        raise RuntimeError("CORPUS_HASH_MISMATCH")
    expected_review = _read_csv(BENCH / "external_source_review_v1_1_for_gpt.csv")
    completed_review = _read_csv(review_path)
    review_result = validate_second_review(expected_review, completed_review)

    original = rows(BENCH / "benchmark_rq4_v1_draft.jsonl")
    current = rows(BENCH / "benchmark_rq4_v1_1_draft.jsonl")
    corpus = rows(CORPUS)
    current_by_id = {item["question_id"]: item for item in current}
    external_questions, external_entities, external_evidence = excluded_material(corpus)
    dev_questions, dev_entities, dev_evidence = _development_reserved()
    external_questions |= {normalize_text(value) for value in dev_questions}
    external_entities |= {normalize_entity(value) for value in dev_entities}
    external_evidence |= dev_evidence
    reserved_questions, reserved_entities, reserved_evidence, reserved_signatures, reserved_counts = _make_reserved(
        corpus, original, current
    )
    herbs = sorted((chunk for chunk in corpus if _substantive_herb(chunk)), key=lambda chunk: chunk["chunk_id"])
    syndromes = sorted((chunk for chunk in corpus if _substantive_syndrome(chunk)), key=lambda chunk: chunk["chunk_id"])

    revised: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for item in current:
        qid = item["question_id"]
        if qid not in REPLACE_IDS:
            revised.append(json.loads(json.dumps(item, ensure_ascii=False)))
            continue
        herb_chunk = _next_chunk(herbs, reserved_entities, reserved_evidence)
        if qid in MULTI_REPLACE_IDS:
            syndrome_chunk = _next_chunk(syndromes, reserved_entities, reserved_evidence)
            value = multi(herb_chunk, syndrome_chunk, qid, item["difficulty"])
        else:
            value = herbal(herb_chunk, qid, item["difficulty"])
        value["revision_status"] = "REPLACED_AFTER_SECOND_SOURCE_REVIEW"
        value["revision_note"] = _replacement_note(qid)
        normalized_question = normalize_text(value["question"])
        signatures = component_signatures(value)
        if normalized_question in reserved_questions:
            raise RuntimeError(f"V1_2_RESERVED_QUESTION_COLLISION:{qid}")
        if set(signatures) & reserved_signatures:
            raise RuntimeError(f"V1_2_RESERVED_GOLD_SIGNATURE_COLLISION:{qid}")
        # Reserve the complete selected replacement before selecting the next one.
        reserved_questions.add(normalized_question)
        reserved_signatures.update(signatures)
        ledger.append({
            "question_id": qid,
            "previous_duplicated_or_reused_target": "|".join(item["source_entity_names"]),
            "duplicated_or_reused_with_question_id": DUPLICATED_WITH[qid],
            "old_entity": "|".join(item["source_entity_names"]),
            "old_evidence_ids": "|".join(item["source_evidence_ids"]),
            "replacement_entity": "|".join(value["source_entity_names"]),
            "replacement_evidence_ids": "|".join(value["source_evidence_ids"]),
            "replacement_gold_signature": "||".join(signatures),
            "domain": value["domain"],
            "difficulty": value["difficulty"],
            "uniqueness_checks_performed": "global_reserved_question|entity_alias|evidence_id|gold_target|all_vs_all",
            "source_quality_checks": "nonempty_source|complete_requested_fields|not_cross_reference|direct_corpus_derivation",
            "why_genuinely_unused": "Absent from all global reserved sets at selection and reserved immediately before the next selection.",
            "second_round_review_reason": _review_reason(completed_review, qid),
            "final_action": "REPLACE_WITH_UNUSED_SUBSTANTIVE_CORPUS_TARGET",
        })
        revised.append(value)

    approved_ids = set(current_by_id) - REPLACE_IDS
    audit = _duplicate_audit(
        revised, approved_ids, REPLACE_IDS,
        {normalize_text(value) for value in external_questions},
        {normalize_entity(value) for value in external_entities},
        external_evidence,
    )
    validation = validate_candidate(revised, current, corpus, audit)

    revision_dir = BENCH / "revision_v1_2"
    revision_dir.mkdir(parents=True, exist_ok=True)
    (revision_dir / "second_round_review_imported.csv").write_bytes(review_path.read_bytes())
    if REVIEW_SUMMARY.exists():
        (revision_dir / "second_round_review_summary.md").write_text(REVIEW_SUMMARY.read_text(encoding="utf-8-sig"), encoding="utf-8")
    _write_csv(revision_dir / "second_review_revision_ledger.csv", ledger)

    jsonl_path = BENCH / "benchmark_rq4_v1_2_draft.jsonl"
    jsonl_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in revised), encoding="utf-8")
    summary_rows = []
    for item in revised:
        summary_rows.append({
            "question_id": item["question_id"], "question": item["question"], "domain": item["domain"],
            "difficulty": item["difficulty"], "expected_specialists": "|".join(item["expected_specialists"]),
            "source_entity_names": "|".join(item["source_entity_names"]),
            "source_evidence_ids": "|".join(item["source_evidence_ids"]),
            "revision_status": item.get("revision_status", ""), "held_out_status": item["held_out_status"],
            "status": item["status"],
        })
    _write_csv(BENCH / "benchmark_rq4_v1_2_draft.csv", summary_rows)

    review_rows = []
    for item in revised:
        origin = "replaced_after_second_review" if item["question_id"] in REPLACE_IDS else "unchanged_from_v1_1"
        for index, fact in enumerate(item["gold_facts"], 1):
            review_rows.append({
                "row_id": f"{item['question_id']}-f{index:02d}", "question_id": item["question_id"],
                "domain": item["domain"], "difficulty": item["difficulty"], "question": item["question"],
                "gold_fact_index": index,
                "gold_atomic_fact": fact["fact"], "preferred_evidence_id": "|".join(fact["preferred_evidence_ids"]),
                "acceptable_alternate_evidence_ids": "|".join(fact["acceptable_alternate_evidence_ids"]),
                "evidence_excerpt": fact["evidence_excerpt"], "source_entity_names": "|".join(item["source_entity_names"]),
                "revision_origin": origin, "source_review_status": "", "review_reason": "", "confidence": "",
            })
    packet = BENCH / "external_source_review_v1_2_for_gpt.csv"
    _write_csv(packet, review_rows)
    candidate_sha = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    gold_count = len(review_rows)

    audit.update({
        "status": "PASS", "reserved_set_counts_before_selection": reserved_counts,
        "approved_questions_checked": 83, "replacement_questions_checked": 17,
        "provider_calls": 0,
    })
    (BENCH / "duplicate_audit_rq4_v1_2.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit_lines = [
        "# RQ4 v1.2 duplicate audit", "", "Status: **PASS**", "",
        f"- Questions / unique IDs / unique normalized text: 100 / 100 / {audit['unique_normalized_questions']}",
        "- Raw question duplicates: 0", "- Normalized question duplicates: 0",
        "- Entity/material target conflicts: 0", "- Evidence-ID conflicts: 0",
        "- Gold target signature conflicts: 0", "- Replacement-to-approved conflicts: 0",
        "- Replacement-to-replacement conflicts: 0", "- RQ1/development/smoke deterministic overlaps: 0",
        f"- Deterministic limitation: {audit['deterministic_limitation']}",
    ]
    (BENCH / "duplicate_audit_rq4_v1_2.md").write_text("\n".join(audit_lines) + "\n", encoding="utf-8")
    leakage = {
        "intra_benchmark_exact_duplicates": 0, "normalized_duplicates": 0,
        "entity_material_target_conflicts": 0, "evidence_id_conflicts": 0,
        "rq1_overlap": 0, "development_smoke_overlap": 0,
        "deterministic_limitation": audit["deterministic_limitation"],
    }
    (BENCH / "leakage_report_rq4_v1_2.md").write_text(
        "# RQ4 v1.2 deterministic duplicate/leakage report\n\n" +
        "\n".join(f"- {key}: {value}" for key, value in leakage.items()) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "status": STATUS, "candidate_version": "RQ4_CANDIDATE_V1_2", "candidate_sha256": candidate_sha,
        "corpus_name": "TCM Research Corpus v1", "corpus_sha256": CORPUS_SHA,
        "question_count": 100, "gold_fact_count": gold_count,
        "domain": {"herbal": 60, "syndrome": 25, "multi_target": 15},
        "difficulty": {"easy": 40, "medium": 40, "hard": 20},
        "held_out": True, "frozen": False, "provider_calls": 0,
        "source_review": {
            "first_external_review": "COMPLETED", "first_revision": "COMPLETED",
            "second_external_review": "COMPLETED", "second_revision": "COMPLETED",
            "final_external_review": "PENDING",
        },
        "second_review": review_result, "revision": {"preserved_unchanged": 83, "replaced": 17},
        "validation": validation, "duplicate_audit": "PASS",
    }
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (BENCH / "heldout_manifest_rq4_v1_2_draft.json").write_text(manifest_text, encoding="utf-8")
    (BENCH / "candidate_manifest_rq4_v1_2.json").write_text(manifest_text, encoding="utf-8")
    (BENCH / "coverage_report_rq4_v1_2_draft.md").write_text(
        f"# RQ4 candidate v1.2 coverage\n\nStatus: {STATUS}\n\n"
        f"- Questions: 100\n- Gold atomic facts: {gold_count}\n"
        "- Domain: 60 herbal / 25 syndrome / 15 multi-target\n"
        "- Difficulty: 40 easy / 40 medium / 20 hard\n"
        "- Approved v1.1 questions preserved unchanged: 83\n- Replacements after second review: 17\n"
        "- Deterministic duplicate/leakage audit: PASS\n- Final external source review: pending\n"
        "- Frozen: no\n- Provider calls: 0\n",
        encoding="utf-8",
    )
    (BENCH / "README.md").write_text(
        f"# TCM Gold RQ4 v1.2 candidate\n\nStatus: **{STATUS}**. The second external review and second revision are complete. "
        "The 83 approved v1.1 questions are unchanged, 17 duplicate/reused targets were replaced, and deterministic duplicate/leakage checks pass. "
        "This candidate is not frozen and requires one final complete external source-grounded review.\n",
        encoding="utf-8",
    )
    state_path = RQ4 / "rq4_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update({
        "state": STATE, "previous_state": "BENCHMARK_REVISION_REQUIRED",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "first_source_review": "COMPLETED", "first_revision": "COMPLETED",
        "second_source_review": "COMPLETED", "second_revision": "COMPLETED",
        "final_source_review": "PENDING", "candidate": "RQ4_CANDIDATE_V1_2",
        "candidate_sha256": candidate_sha, "provider_calls_during_second_revision": 0,
    })
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "review": review_result, "questions": 100, "gold_facts": gold_count,
        "preserved_unchanged": 83, "replaced": 17, "candidate_sha256": candidate_sha,
        "duplicate_audit": "PASS", "packet": str(packet), "state": STATE, "provider_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
