import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = ROOT / "research/benchmarks/tcm_gold_rq1_confirmatory_v1"
ORIGINAL = BENCH_DIR / "benchmark_confirmatory_v1.jsonl"
CORPUS = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
ORIGINAL_MANIFEST = BENCH_DIR / "heldout_manifest_confirmatory_v1.json"
EXPECTED_CORPUS_SHA = "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"
STATUS = "DRAFT_SOURCE_GROUNDED_CONFIRMATORY_V1_1"

CROSS_REFERENCE_IDS = {
    "tcmc-v1-001", "tcmc-v1-003", "tcmc-v1-004", "tcmc-v1-010",
    "tcmc-v1-015", "tcmc-v1-017", "tcmc-v1-028", "tcmc-v1-033",
    "tcmc-v1-034", "tcmc-v1-052", "tcmc-v1-054", "tcmc-v1-057",
    "tcmc-v1-100",
}
PROMPT_MISMATCH_IDS = {
    "tcmc-v1-002", "tcmc-v1-005", "tcmc-v1-008", "tcmc-v1-009",
    "tcmc-v1-018", "tcmc-v1-020", "tcmc-v1-024", "tcmc-v1-025",
    "tcmc-v1-032", "tcmc-v1-042",
}
REPLACEMENT_CHUNKS = {
    "tcmc-v1-001": "tcmv1-087f35ddca2b4e2e9d4c9973",
    "tcmc-v1-003": "tcmv1-088486c16f33ac27c944fd12",
    "tcmc-v1-004": "tcmv1-0888b73fb28e4884f24be17d",
    "tcmc-v1-010": "tcmv1-088d4942e39a00f1147c84f7",
    "tcmc-v1-015": "tcmv1-089b64165b9b471be80835d0",
    "tcmc-v1-017": "tcmv1-08a62b7c5bc7e12f7fb06354",
    "tcmc-v1-028": "tcmv1-08b482bf505921f4a49e53d5",
    "tcmc-v1-033": "tcmv1-08b7e1f36534d98121f0d06b",
    "tcmc-v1-034": "tcmv1-08c830098027f9ea27645408",
    "tcmc-v1-052": "tcmv1-08ca5bde15b2d04f6e16a065",
    "tcmc-v1-054": "tcmv1-08cab8337490c9aaf10c6dc0",
    "tcmc-v1-057": "tcmv1-08e3693346174c739e3b4534",
    "tcmc-v1-100": "tcmv1-08eaa501ac5acaeb7dd0bc94",
}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def norm(value):
    return " ".join(str(value or "").lower().split())


def evidence(chunk):
    return f"Source entity: {chunk['entity_name']}. Source: {chunk['source_name']}. {chunk['text']}"


def herb_facts(chunk):
    values = chunk["structured_facts"]
    facts = []
    if values.get("properties_english"):
        for label, key in (
            ("traditional properties", "properties_english"),
            ("meridians", "meridians_english"),
            ("traditional class", "class_english"),
        ):
            if values.get(key):
                facts.append({
                    "fact": f"The source records {chunk['entity_name']} {label}: {values[key]}.",
                    "preferred_evidence_ids": [chunk["chunk_id"]],
                    "acceptable_alternate_evidence_ids": [],
                    "evidence_excerpt": evidence(chunk),
                })
        question = f"What traditional properties, meridians, and class are recorded for {chunk['entity_name']}?"
    else:
        for label, key in (("function", "function"), ("indication", "indication"), ("used part", "used_part")):
            if values.get(key):
                facts.append({
                    "fact": f"The source records the {label} of {chunk['entity_name']} as: {values[key]}.",
                    "preferred_evidence_ids": [chunk["chunk_id"]],
                    "acceptable_alternate_evidence_ids": [],
                    "evidence_excerpt": evidence(chunk),
                })
        question = f"What source-recorded functions, indications, and used part are listed for {chunk['entity_name']}?"
    return question, facts


def replacement_item(original, herb):
    question, facts = herb_facts(herb)
    assert len(facts) == 3, f"replacement must support all requested fields: {herb['entity_name']}"
    item = dict(original)
    if original["domain"] == "herbal_medicine":
        item.update(
            question=question,
            gold_facts=facts,
            preferred_evidence_ids=[herb["chunk_id"]],
            acceptable_alternate_evidence_ids=[],
            source_entity_names=[herb["entity_name"]],
        )
    else:
        syndrome_fact = original["gold_facts"][1]
        syndrome_target = original["requested_targets"][1]
        syndrome_name = original["source_entity_names"][1]
        item.update(
            question=(f"How are {herb['entity_name']} and {syndrome_name} represented separately "
                      "in TCM Research Corpus v1, and what evidence is recorded for each?"),
            gold_facts=[facts[0], syndrome_fact],
            preferred_evidence_ids=[herb["chunk_id"], *syndrome_fact["preferred_evidence_ids"]],
            acceptable_alternate_evidence_ids=[],
            requested_targets=[
                {"entity_name": herb["entity_name"], "category": "herbal_medicine", "evidence_ids": [herb["chunk_id"]]},
                syndrome_target,
            ],
            source_entity_names=[herb["entity_name"], syndrome_name],
            unsupported_claim_constraints=[
                f"Do not infer a relationship between {herb['entity_name']} and {syndrome_name}; "
                "none is established by the supplied evidence."
            ],
        )
    item["status"] = STATUS
    return item


def supported_field_question(item):
    entity = item["source_entity_names"][0]
    labels = []
    facts = "\n".join(f["fact"] for f in item["gold_facts"])
    for label in ("function", "indication", "used part"):
        if f"the {label} of {entity}" in facts:
            labels.append(label)
    if not labels:
        for label in ("traditional properties", "meridians", "traditional class"):
            if f"{entity} {label}:" in facts:
                labels.append(label)
    assert labels, f"could not derive supported fields for {item['question_id']}"
    if len(labels) == 1:
        fields = labels[0]
    elif len(labels) == 2:
        fields = f"{labels[0]} and {labels[1]}"
    else:
        fields = f"{', '.join(labels[:-1])}, and {labels[-1]}"
    if labels[0].startswith("traditional") or labels[0] == "meridians":
        return f"What {fields} are recorded for {entity}?"
    return f"What source-recorded {fields} are listed for {entity}?"


def validate_review(packet_path, completed_path):
    with packet_path.open(encoding="utf-8-sig", newline="") as handle:
        packet = list(csv.DictReader(handle))
    with completed_path.open(encoding="utf-8-sig", newline="") as handle:
        completed = list(csv.DictReader(handle))
    content_columns = [
        "question_id", "question", "domain", "difficulty", "canonical_source_entities",
        "gold_fact_index", "gold_atomic_fact", "preferred_evidence_id",
        "acceptable_alternate_evidence_ids", "evidence_excerpt",
    ]
    assert len(packet) == len(completed) == 223
    assert len({(r["question_id"], r["gold_fact_index"]) for r in completed}) == 223
    assert [{k: r[k] for k in content_columns} for r in packet] == [
        {k: r[k] for k in content_columns} for r in completed
    ]
    assert all(r["source_review_status"] in {"APPROVE", "REVISE"} for r in completed)
    by_question = {}
    for row in completed:
        by_question.setdefault(row["question_id"], set()).add(row["source_review_status"])
    resolved = {qid: ("REVISE" if "REVISE" in statuses else "APPROVE") for qid, statuses in by_question.items()}
    assert Counter(resolved.values()) == {"APPROVE": 77, "REVISE": 23}
    assert {qid for qid, status in resolved.items() if status == "REVISE"} == CROSS_REFERENCE_IDS | PROMPT_MISMATCH_IDS
    return completed, resolved


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_candidate(items, corpus, original, original_manifest):
    corpus_by_id = {c["chunk_id"]: c for c in corpus}
    approved = set(x["question_id"] for x in original) - CROSS_REFERENCE_IDS - PROMPT_MISMATCH_IDS
    original_by_id = {x["question_id"]: x for x in original}
    assert len(items) == 100
    assert len({x["question_id"] for x in items}) == 100
    assert len({x["question"] for x in items}) == 100
    assert all(
        {k: x[k] for k in ("question", "domain", "difficulty", "gold_facts", "preferred_evidence_ids", "source_entity_names")}
        == {k: original_by_id[x["question_id"]][k] for k in ("question", "domain", "difficulty", "gold_facts", "preferred_evidence_ids", "source_entity_names")}
        for x in items if x["question_id"] in approved
    )
    assert Counter(x["domain"] for x in items) == {
        "herbal_medicine": 60,
        "syndrome_differentiation": 25,
        "herbal_medicine + syndrome_differentiation": 15,
    }
    assert Counter(x["difficulty"] for x in items) == {"easy": 40, "medium": 40, "hard": 20}
    assert all(set(x["expected_specialists"]) <= {"herbal", "syndrome"} for x in items)
    assert len({tuple(norm(e) for e in x["source_entity_names"]) for x in items}) == 100
    exclusions = set(original_manifest["exclusions"])
    for item in items:
        if item["question_id"] in CROSS_REFERENCE_IDS:
            assert all(norm(entity) not in exclusions for entity in item["source_entity_names"])
        if "+" in item["domain"]:
            assert len(item["requested_targets"]) == 2
            assert item["relationship_gold_status"] == "not_established"
            assert item["unsupported_claim_constraints"]
        for fact in item["gold_facts"]:
            assert fact["fact"] and fact["evidence_excerpt"] and fact["preferred_evidence_ids"]
            assert all(eid in corpus_by_id for eid in fact["preferred_evidence_ids"])
            source_text = " ".join(
                str(corpus_by_id[eid].get("text", "")) for eid in fact["preferred_evidence_ids"]
            ).strip().lower()
            assert not source_text.startswith("source-recorded function: see")
            assert "source-recorded function: see " not in source_text
    for item in items:
        if item["domain"] != "herbal_medicine":
            continue
        question = item["question"].lower()
        facts = " ".join(f["fact"].lower() for f in item["gold_facts"])
        requested = []
        if "function" in question: requested.append("function")
        if "indication" in question: requested.append("indication")
        if "used part" in question: requested.append("used part")
        if "properties" in question: requested.append("traditional properties")
        if "meridian" in question: requested.append("meridians")
        if "class" in question: requested.append("traditional class")
        assert all(label in facts for label in requested), (item["question_id"], requested)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--review-summary", required=True)
    args = parser.parse_args()

    assert hashlib.sha256(CORPUS.read_bytes()).hexdigest() == EXPECTED_CORPUS_SHA
    completed_path = Path(args.review_csv)
    summary_path = Path(args.review_summary)
    completed, resolved = validate_review(BENCH_DIR / "external_source_review_for_gpt.csv", completed_path)
    original = read_jsonl(ORIGINAL)
    corpus = read_jsonl(CORPUS)
    corpus_by_id = {c["chunk_id"]: c for c in corpus}
    original_manifest = json.loads(ORIGINAL_MANIFEST.read_text(encoding="utf-8"))
    original_entities = {norm(e) for item in original for e in item["source_entity_names"]}

    items = []
    revisions = []
    for source_item in original:
        item = json.loads(json.dumps(source_item, ensure_ascii=False))
        qid = item["question_id"]
        if qid in CROSS_REFERENCE_IDS:
            herb = corpus_by_id[REPLACEMENT_CHUNKS[qid]]
            assert norm(herb["entity_name"]) not in original_entities
            old_entities = list(item["source_entity_names"])
            item = replacement_item(item, herb)
            revisions.append({
                "original_question_id": qid,
                "reason": "cross_reference_only_primary_gold",
                "action": "replaced",
                "original_entities": old_entities,
                "replacement_entity_or_question": item["source_entity_names"][0],
                "replacement_question": item["question"],
            })
        elif qid in PROMPT_MISMATCH_IDS:
            old_question = item["question"]
            item["question"] = supported_field_question(item)
            item["status"] = STATUS
            revisions.append({
                "original_question_id": qid,
                "reason": "prompt_gold_completeness_mismatch",
                "action": "rewritten",
                "original_entities": list(item["source_entity_names"]),
                "replacement_entity_or_question": item["question"],
                "original_question": old_question,
                "replacement_question": item["question"],
            })
        else:
            item["status"] = STATUS
        items.append(item)

    validate_candidate(items, corpus, original, original_manifest)
    benchmark_path = BENCH_DIR / "benchmark_confirmatory_v1_1.jsonl"
    benchmark_path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8")

    benchmark_fields = [
        "question_id", "question", "domain", "difficulty", "expected_specialists",
        "source_entity_names", "gold_fact_count", "preferred_evidence_ids", "status",
    ]
    benchmark_rows = []
    for item in items:
        benchmark_rows.append({
            **{key: item.get(key, "") for key in benchmark_fields},
            "expected_specialists": "|".join(item["expected_specialists"]),
            "source_entity_names": "|".join(item["source_entity_names"]),
            "gold_fact_count": len(item["gold_facts"]),
            "preferred_evidence_ids": "|".join(item["preferred_evidence_ids"]),
        })
    write_csv(BENCH_DIR / "benchmark_confirmatory_v1_1.csv", benchmark_rows, benchmark_fields)

    revision_by_id = {r["original_question_id"]: r for r in revisions}
    review_rows = []
    for item in items:
        revision = revision_by_id.get(item["question_id"])
        for index, fact in enumerate(item["gold_facts"], 1):
            review_rows.append({
                "question_id": item["question_id"],
                "question": item["question"],
                "domain": item["domain"],
                "difficulty": item["difficulty"],
                "canonical_source_entities": "|".join(item["source_entity_names"]),
                "gold_fact_index": index,
                "gold_atomic_fact": fact["fact"],
                "preferred_evidence_id": "|".join(fact["preferred_evidence_ids"]),
                "acceptable_alternate_evidence_ids": "|".join(fact["acceptable_alternate_evidence_ids"]),
                "evidence_excerpt": fact["evidence_excerpt"],
                "revision_action": revision["action"] if revision else "unchanged_approved",
                "revision_reason": revision["reason"] if revision else "",
                "source_review_status": "",
                "review_reason": "",
                "confidence": "",
            })
    review_fields = list(review_rows[0])
    write_csv(BENCH_DIR / "review_sheet_confirmatory_v1_1.csv", review_rows, review_fields)
    write_csv(BENCH_DIR / "external_source_review_v1_1_for_gpt.csv", review_rows, review_fields)
    template_fields = ["question_id", "gold_fact_index", "source_review_status", "review_reason", "confidence"]
    write_csv(
        BENCH_DIR / "external_source_review_v1_1_result_template.csv",
        [{"question_id": r["question_id"], "gold_fact_index": r["gold_fact_index"],
          "source_review_status": "", "review_reason": "", "confidence": ""} for r in review_rows],
        template_fields,
    )

    instructions = (
        "# External source-grounded review instructions — confirmatory v1.1\n\n"
        "The reviewer is not validating clinical TCM truth. Check only: **Does the supplied Corpus evidence "
        "directly support the proposed Gold fact, and does the question ask only for content represented by "
        "the complete Gold set?** Use only the supplied question, Gold facts, evidence IDs, and excerpts.\n\n"
        "Allowed statuses: APPROVE, REVISE, REMOVE, UNRESOLVED. Return the unchanged question_id and "
        "gold_fact_index, a short reason, and confidence HIGH, MEDIUM, or LOW. Do not use external medical "
        "knowledge. Cross-reference-only content such as 'See ...' is not acceptable as primary confirmatory Gold.\n"
    )
    (BENCH_DIR / "external_source_review_v1_1_instructions.md").write_text(instructions, encoding="utf-8")
    markdown = instructions + "\n# Review items\n\n"
    for row in review_rows:
        markdown += (
            f"## {row['question_id']} / fact {row['gold_fact_index']}\n\n"
            f"- Question: {row['question']}\n- Domain: {row['domain']}\n- Difficulty: {row['difficulty']}\n"
            f"- Entities: {row['canonical_source_entities']}\n- Revision metadata: {row['revision_action']}"
            f" ({row['revision_reason'] or 'not revised'})\n- Gold fact: {row['gold_atomic_fact']}\n"
            f"- Preferred evidence: {row['preferred_evidence_id']}\n"
            f"- Alternate evidence: {row['acceptable_alternate_evidence_ids'] or 'none'}\n\n"
            f"Evidence excerpt:\n\n{row['evidence_excerpt']}\n\n---\n\n"
        )
    (BENCH_DIR / "external_source_review_v1_1_for_gpt.md").write_text(markdown, encoding="utf-8")

    imported_review = {
        "methodology": "external GPT source-grounded review; not clinical or expert validation",
        "source_draft": "DRAFT_SOURCE_GROUNDED_CONFIRMATORY_V1",
        "question_level_counts": dict(Counter(resolved.values())),
        "row_level_counts": dict(Counter(row["source_review_status"] for row in completed)),
        "rows": completed,
    }
    (BENCH_DIR / "external_source_review_v1_import.json").write_text(
        json.dumps(imported_review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (BENCH_DIR / "external_source_review_v1_summary.md").write_text(
        summary_path.read_text(encoding="utf-8-sig"), encoding="utf-8"
    )

    manifest = {
        "status": STATUS,
        "version": "confirmatory_v1_1",
        "original_draft": {
            "status": "DRAFT_SOURCE_GROUNDED_CONFIRMATORY_V1",
            "benchmark_sha256": hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
        },
        "corpus_sha256": EXPECTED_CORPUS_SHA,
        "question_count": 100,
        "atomic_gold_fact_count": len(review_rows),
        "distributions": {
            "domain": {"herbal": 60, "syndrome": 25, "multi_target": 15},
            "difficulty": {"easy": 40, "medium": 40, "hard": 20},
        },
        "external_source_review_v1": {
            "method": "external GPT source-grounded review",
            "approved_unchanged": 77,
            "revised": 23,
            "cross_reference_only": 13,
            "prompt_gold_completeness_mismatch": 10,
            "remove": 0,
            "unresolved": 0,
        },
        "revisions": revisions,
        "exclusions": original_manifest["exclusions"],
        "leakage_checks": {
            "old_benchmark_entity_overlap": 0,
            "development_entity_overlap": 0,
            "smoke_debug_entity_overlap": 0,
            "duplicate_questions": 0,
            "duplicate_targets": 0,
            "invalid_evidence_ids": 0,
            "cross_reference_only_primary_gold": 0,
            "prompt_gold_completeness_mismatch": 0,
            "unsupported_relationships": 0,
        },
        "source_review": "SECOND_EXTERNAL_REVIEW_PENDING",
        "provider_llm_calls_during_revision": 0,
    }
    (BENCH_DIR / "heldout_manifest_confirmatory_v1_1.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (BENCH_DIR / "coverage_report_confirmatory_v1_1.md").write_text(
        f"# Confirmatory benchmark v1.1 coverage\n\nStatus: {STATUS}\n\n"
        f"- Questions: 100\n- Atomic Gold facts: {len(review_rows)}\n"
        "- Domains: herbal 60, syndrome 25, multi-target 15\n"
        "- Difficulty: easy 40, medium 40, hard 20\n"
        "- External review v1: 77 approved unchanged; 23 revised\n"
        "- Revisions: 13 cross-reference-only replacements; 10 prompt/Gold wording corrections\n"
        "- Leakage and deterministic quality checks: passed\n"
        f"- Corpus SHA-256: `{EXPECTED_CORPUS_SHA}`\n- Second external source review: pending\n",
        encoding="utf-8",
    )
    (BENCH_DIR / "README.md").write_text(
        "# RQ1 confirmatory benchmark\n\n"
        "Current candidate status: DRAFT_SOURCE_GROUNDED_CONFIRMATORY_V1_1. The original v1 draft is preserved. "
        "External source review approved 77 questions and requested 23 benchmark-design revisions. The v1.1 "
        "candidate remains unfrozen and blocked pending a complete second external source-grounded review. "
        "No provider or LLM calls were made during revision.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": STATUS,
        "questions": len(items),
        "gold_facts": len(review_rows),
        "approved_unchanged": 77,
        "revised": len(revisions),
        "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
        "provider_calls": 0,
    }))


if __name__ == "__main__":
    main()
