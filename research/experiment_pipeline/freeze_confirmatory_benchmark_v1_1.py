import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCH_DIR = ROOT / "research/benchmarks/tcm_gold_rq1_confirmatory_v1"
CANDIDATE = BENCH_DIR / "benchmark_confirmatory_v1_1.jsonl"
PACKET = BENCH_DIR / "external_source_review_v1_1_for_gpt.csv"
CORPUS = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
HELDOUT = BENCH_DIR / "heldout_manifest_confirmatory_v1_1.json"
PROTOCOL = ROOT / "research/experiments/rq1_c1_vs_c2/confirmatory_protocol/protocol.md"
ANALYSIS_PLAN = ROOT / "research/experiments/rq1_c1_vs_c2/confirmatory_protocol/analysis_plan.json"
EXPECTED_CANDIDATE_SHA = "f938ec9b3e3d31c0f04983951dc6de2c6edc7b411bdd3f0501f0e8e12e23559e"
EXPECTED_CORPUS_SHA = "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"
FROZEN_STATUS = "FROZEN_SOURCE_GROUNDED_RQ1_CONFIRMATORY_V1_1"
VERSION = "RQ1_CONFIRMATORY_V1_1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def norm(value):
    return " ".join(str(value or "").lower().split())


def strict_review_import(review_path):
    with PACKET.open(encoding="utf-8-sig", newline="") as handle:
        packet = list(csv.DictReader(handle))
    with review_path.open(encoding="utf-8-sig", newline="") as handle:
        review = list(csv.DictReader(handle))
    content_columns = [
        "question_id", "question", "domain", "difficulty", "canonical_source_entities",
        "gold_fact_index", "gold_atomic_fact", "preferred_evidence_id",
        "acceptable_alternate_evidence_ids", "evidence_excerpt",
    ]
    assert len(packet) == len(review) == 223
    packet_keys = {(row["question_id"], row["gold_fact_index"]) for row in packet}
    review_keys = {(row["question_id"], row["gold_fact_index"]) for row in review}
    assert len(packet_keys) == len(review_keys) == 223
    assert packet_keys == review_keys
    by_key = {(row["question_id"], row["gold_fact_index"]): row for row in review}
    for packet_row in packet:
        returned = by_key[(packet_row["question_id"], packet_row["gold_fact_index"])]
        assert all(packet_row[column] == returned[column] for column in content_columns)
    assert Counter(row["source_review_status"] for row in review) == {"APPROVE": 223}
    assert Counter(row["confidence"] for row in review) == {"HIGH": 223}
    grouped = defaultdict(list)
    for row in review:
        grouped[row["question_id"]].append(row)
    assert len(grouped) == 100
    assert all(all(row["source_review_status"] == "APPROVE" for row in rows) for rows in grouped.values())
    return review


def deterministic_validation(items, corpus, heldout):
    corpus_by_id = {chunk["chunk_id"]: chunk for chunk in corpus}
    assert len(items) == 100
    assert len({item["question_id"] for item in items}) == 100
    assert len({item["question"] for item in items}) == 100
    assert len({tuple(norm(e) for e in item["source_entity_names"]) for item in items}) == 100
    assert Counter(item["domain"] for item in items) == {
        "herbal_medicine": 60,
        "syndrome_differentiation": 25,
        "herbal_medicine + syndrome_differentiation": 15,
    }
    assert Counter(item["difficulty"] for item in items) == {"easy": 40, "medium": 40, "hard": 20}
    assert sum(len(item["gold_facts"]) for item in items) == 223
    assert all(set(item["expected_specialists"]) <= {"herbal", "syndrome"} for item in items)
    excluded = set(heldout["exclusions"])
    assert not {norm(e) for item in items for e in item["source_entity_names"]} & excluded
    for item in items:
        assert item["question_id"].startswith("tcmc-v1-")
        assert item["question"].strip().endswith("?")
        if "+" in item["domain"]:
            assert item["expected_specialists"] == ["syndrome", "herbal"]
            assert len(item["requested_targets"]) == 2
            assert item["relationship_gold_status"] == "not_established"
            assert item["unsupported_claim_constraints"]
        for fact in item["gold_facts"]:
            assert fact["fact"] and fact["preferred_evidence_ids"] and fact["evidence_excerpt"]
            assert all(evidence_id in corpus_by_id for evidence_id in fact["preferred_evidence_ids"])
            assert " source-recorded function: see " not in f" {fact['evidence_excerpt'].lower()} "
            assert " source-recorded indication: see " not in f" {fact['evidence_excerpt'].lower()} "
    for item in items:
        if item["domain"] != "herbal_medicine":
            continue
        question = item["question"].lower()
        facts = " ".join(fact["fact"].lower() for fact in item["gold_facts"])
        requested = []
        if "function" in question: requested.append("function")
        if "indication" in question: requested.append("indication")
        if "used part" in question: requested.append("used part")
        if "properties" in question: requested.append("traditional properties")
        if "meridian" in question: requested.append("meridians")
        if "class" in question: requested.append("traditional class")
        assert requested and all(field in facts for field in requested)
    assert all(value == 0 for value in heldout["leakage_checks"].values())


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", required=True)
    parser.add_argument("--review-summary", required=True)
    parser.add_argument("--source-git-revision", required=True)
    args = parser.parse_args()
    review_path = Path(args.review_csv)
    summary_path = Path(args.review_summary)

    assert sha(CANDIDATE) == EXPECTED_CANDIDATE_SHA
    assert sha(CORPUS) == EXPECTED_CORPUS_SHA
    review = strict_review_import(review_path)
    candidate = read_jsonl(CANDIDATE)
    corpus = read_jsonl(CORPUS)
    heldout = json.loads(HELDOUT.read_text(encoding="utf-8"))
    deterministic_validation(candidate, corpus, heldout)

    frozen = json.loads(json.dumps(candidate, ensure_ascii=False))
    for item in frozen:
        item["status"] = FROZEN_STATUS
    frozen_jsonl = BENCH_DIR / "benchmark_confirmatory_v1_1_frozen.jsonl"
    frozen_jsonl.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in frozen), encoding="utf-8")
    immutable_fields = (
        "question_id", "question", "domain", "difficulty", "gold_facts", "preferred_evidence_ids",
        "acceptable_alternate_evidence_ids", "expected_specialists", "source_entity_names",
    )
    assert all(
        {field: source.get(field) for field in immutable_fields}
        == {field: target.get(field) for field in immutable_fields}
        for source, target in zip(candidate, frozen)
    )

    fields = [
        "question_id", "question", "domain", "difficulty", "expected_specialists",
        "source_entity_names", "gold_fact_count", "preferred_evidence_ids", "status",
    ]
    rows = []
    for item in frozen:
        rows.append({
            "question_id": item["question_id"],
            "question": item["question"],
            "domain": item["domain"],
            "difficulty": item["difficulty"],
            "expected_specialists": "|".join(item["expected_specialists"]),
            "source_entity_names": "|".join(item["source_entity_names"]),
            "gold_fact_count": len(item["gold_facts"]),
            "preferred_evidence_ids": "|".join(item["preferred_evidence_ids"]),
            "status": FROZEN_STATUS,
        })
    write_csv(BENCH_DIR / "benchmark_confirmatory_v1_1_frozen.csv", rows, fields)

    final_review_csv = BENCH_DIR / "external_source_review_v1_1_final_completed.csv"
    write_csv(final_review_csv, review, list(review[0]))
    (BENCH_DIR / "external_source_review_v1_1_final_summary.md").write_text(
        summary_path.read_text(encoding="utf-8-sig"), encoding="utf-8"
    )
    review_record = {
        "benchmark_version": VERSION,
        "candidate_benchmark_sha256": EXPECTED_CANDIDATE_SHA,
        "method": "external GPT source-grounded review",
        "scope": "source grounding and benchmark design only; not clinical or TCM expert validation",
        "questions": 100,
        "atomic_gold_facts": 223,
        "question_level": {"APPROVE": 100, "REVISE": 0, "REMOVE": 0, "UNRESOLVED": 0},
        "row_level": {"APPROVE": 223, "REVISE": 0, "REMOVE": 0, "UNRESOLVED": 0},
        "confidence": {"HIGH": 223, "MEDIUM": 0, "LOW": 0},
        "completed_csv_sha256": sha(final_review_csv),
    }
    (BENCH_DIR / "final_source_review_record_v1_1.json").write_text(
        json.dumps(review_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    frozen_heldout = json.loads(json.dumps(heldout, ensure_ascii=False))
    frozen_heldout["status"] = FROZEN_STATUS
    frozen_heldout["source_review"] = "APPROVED_100_OF_100_SECOND_EXTERNAL_REVIEW"
    frozen_heldout["freeze_invariant"] = (
        "Questions, Gold facts, evidence IDs, evidence excerpts, entities, domains, difficulties, and specialist "
        "assignments must not change during the formal confirmatory experiment."
    )
    frozen_heldout_path = BENCH_DIR / "heldout_manifest_confirmatory_v1_1_frozen.json"
    frozen_heldout_path.write_text(json.dumps(frozen_heldout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    frozen_sha = sha(frozen_jsonl)
    freeze_timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    freeze_manifest = {
        "benchmark_version": VERSION,
        "status": FROZEN_STATUS,
        "freeze_timestamp_utc": freeze_timestamp,
        "source_git_revision": args.source_git_revision,
        "question_count": 100,
        "atomic_gold_fact_count": 223,
        "domain_distribution": {"herbal": 60, "syndrome": 25, "multi_target": 15},
        "difficulty_distribution": {"easy": 40, "medium": 40, "hard": 20},
        "corpus_version": "TCM Research Corpus v1",
        "corpus_chunk_count": 4461,
        "corpus_sha256": EXPECTED_CORPUS_SHA,
        "candidate_benchmark_sha256": EXPECTED_CANDIDATE_SHA,
        "final_benchmark_sha256": frozen_sha,
        "heldout_manifest_sha256": sha(frozen_heldout_path),
        "external_source_review": {
            "result": "APPROVED",
            "questions_approved": 100,
            "atomic_gold_facts_approved": 223,
            "confidence": "HIGH_ALL_ROWS",
            "method": "external GPT source-grounded review",
            "clinical_or_tcm_expert_validation": "NOT_PERFORMED",
        },
        "gold_interpretation": "SOURCE-GROUNDED_REFERENCE_NOT_CLINICAL_TRUTH",
        "formal_experiment_protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "formal_experiment_protocol_sha256": sha(PROTOCOL),
        "analysis_plan": str(ANALYSIS_PLAN.relative_to(ROOT)).replace("\\", "/"),
        "analysis_plan_sha256": sha(ANALYSIS_PLAN),
        "formal_provider_runs_before_freeze": 0,
        "freeze_invariant": (
            "No benchmark question, Gold fact, evidence mapping, or protocol analysis threshold may be changed "
            "after this freeze or in response to formal outputs."
        ),
    }
    freeze_manifest_path = BENCH_DIR / "freeze_manifest_confirmatory_v1_1.json"
    freeze_manifest_path.write_text(json.dumps(freeze_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (BENCH_DIR / "coverage_report_confirmatory_v1_1_frozen.md").write_text(
        f"# Frozen RQ1 confirmatory benchmark v1.1\n\nStatus: {FROZEN_STATUS}\n\n"
        "- Questions: 100\n- Atomic Gold facts: 223\n"
        "- Domains: herbal 60, syndrome 25, multi-target 15\n"
        "- Difficulty: easy 40, medium 40, hard 20\n"
        "- Second external source review: 100/100 questions and 223/223 Gold facts APPROVE, all HIGH confidence\n"
        "- Deterministic leakage, evidence, schema, target, and relationship validation: passed\n"
        f"- Corpus SHA-256: `{EXPECTED_CORPUS_SHA}`\n- Frozen benchmark SHA-256: `{frozen_sha}`\n\n"
        "Gold is a source-grounded reference, not clinical truth or TCM expert ground truth.\n",
        encoding="utf-8",
    )
    (BENCH_DIR / "README.md").write_text(
        "# RQ1 confirmatory benchmark\n\n"
        f"Current status: `{FROZEN_STATUS}`. The frozen benchmark is `benchmark_confirmatory_v1_1_frozen.jsonl`. "
        "The full audit trail is preserved: original v1 draft, first external review, 23 revisions, v1.1 "
        "candidate, second external review, and final freeze. The final review approved 100/100 questions and "
        "223/223 atomic Gold facts at HIGH confidence. This is source-grounded reference Gold, not clinical "
        "truth or medical/TCM expert validation. No provider runs occurred before freeze.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": FROZEN_STATUS,
        "questions": 100,
        "atomic_gold_facts": 223,
        "final_benchmark_sha256": frozen_sha,
        "corpus_sha256": EXPECTED_CORPUS_SHA,
        "provider_calls": 0,
    }))


if __name__ == "__main__":
    main()
