"""Build the deterministic, source-grounded RQ4 candidate benchmark (zero LLM calls)."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "research/corpus/tcm_v1/chunks.jsonl"
OUT = ROOT / "research/benchmarks/tcm_gold_rq4_v1"
CORPUS_SHA = "316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9"
STATUS = "BENCHMARK_SOURCE_REVIEW_REQUIRED"


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _walk_questions(value: object, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"question", "query", "prompt"} and isinstance(item, str): found.add(norm(item))
            _walk_questions(item, found)
    elif isinstance(value, list):
        for item in value: _walk_questions(item, found)


def excluded_material(corpus: list[dict]) -> tuple[set[str], set[str], set[str]]:
    questions: set[str] = set()
    entities: set[str] = {
        "red ginseng", "hongshen", "liver yang", "ginseng", "红参",
        "gehua", "flower bud of lobed kudzuvine",
    }
    evidence_ids: set[str] = set()
    for path in ROOT.glob("research/benchmarks/**/benchmark*.jsonl"):
        if OUT in path.parents:
            continue
        for item in rows(path):
            questions.add(norm(item.get("question")))
            entities.update(norm(x) for x in item.get("source_entity_names", []))
            evidence_ids.update(item.get("preferred_evidence_ids", []))
            evidence_ids.update(item.get("source_evidence_ids", []))
    for base in (ROOT / "research/datasets", ROOT / "research/smoke_tests", ROOT / "backend/evaluation"):
        if not base.exists(): continue
        for path in base.rglob("*"):
            if path.suffix.casefold() not in {".json", ".jsonl", ".csv"}: continue
            try:
                if path.suffix.casefold() == ".json": _walk_questions(json.loads(path.read_text(encoding="utf-8-sig")), questions)
                elif path.suffix.casefold() == ".jsonl":
                    for value in rows(path): _walk_questions(value, questions)
                else:
                    with path.open(encoding="utf-8-sig", newline="") as handle:
                        for value in csv.DictReader(handle): _walk_questions(value, questions)
            except (UnicodeDecodeError, json.JSONDecodeError, csv.Error):
                continue
    candidate_names = {norm(chunk["entity_name"]) for chunk in corpus if len(norm(chunk["entity_name"])) >= 3}
    for question in questions:
        entities.update(name for name in candidate_names if name in question)
    return questions, {x for x in entities if x}, evidence_ids


def excerpt(chunk: dict) -> str:
    return f"Source entity: {chunk['entity_name']}. Source: {chunk['source_name']}. {chunk['text']}"


def herbal(chunk: dict, qid: str, difficulty: str) -> dict:
    facts = chunk["structured_facts"]
    if facts.get("properties_english"):
        question = f"What traditional properties, meridians, and class does Corpus v1 record for {chunk['entity_name']}?"
        keys = [("traditional properties", "properties_english"), ("meridians", "meridians_english"), ("traditional class", "class_english")]
    else:
        question = f"What source-recorded functions, indications, and used part are listed for {chunk['entity_name']}?"
        keys = [("function", "function"), ("indication", "indication"), ("used part", "used_part")]
    gold = [{
        "fact": f"The source records the {label} of {chunk['entity_name']} as: {facts[key]}.",
        "preferred_evidence_ids": [chunk["chunk_id"]], "acceptable_alternate_evidence_ids": [],
        "evidence_excerpt": excerpt(chunk),
    } for label, key in keys if facts.get(key)]
    return item(qid, question, "herbal_medicine", difficulty, [chunk], gold, ["herbal"])


def syndrome(chunk: dict, qid: str, difficulty: str) -> dict:
    definition = chunk["structured_facts"]["definition_original"]
    gold = [{
        "fact": f"The source defines {chunk['entity_name']} as: {definition}",
        "preferred_evidence_ids": [chunk["chunk_id"]], "acceptable_alternate_evidence_ids": [],
        "evidence_excerpt": excerpt(chunk),
    }]
    return item(qid, f"What does TCM Research Corpus v1 record about {chunk['entity_name']}?", "syndrome_differentiation", difficulty, [chunk], gold, ["syndrome"])


def item(qid: str, question: str, domain: str, difficulty: str, chunks: list[dict], gold: list[dict], specialists: list[str]) -> dict:
    return {
        "question_id": qid, "domain": domain, "difficulty": difficulty, "question": question,
        "gold_facts": gold, "source_evidence_ids": [x["chunk_id"] for x in chunks],
        "source_evidence_text": [x["text"] for x in chunks],
        "provenance": [{"evidence_id": x["chunk_id"], "source_id": x["source_id"], "source_name": x["source_name"]} for x in chunks],
        "preferred_evidence_ids": [x["chunk_id"] for x in chunks], "acceptable_alternate_evidence_ids": [],
        "expected_specialists": specialists, "source_entity_names": [x["entity_name"] for x in chunks],
        "held_out": True, "held_out_status": "RQ4_CANDIDATE_UNREVIEWED", "status": STATUS,
        "benchmark_role": "rq4_debate_vs_ordinary_multiagent",
    }


def multi(herb: dict, syn: dict, qid: str, difficulty: str) -> dict:
    h = herbal(herb, qid, difficulty)["gold_facts"][0]
    s = syndrome(syn, qid, difficulty)["gold_facts"][0]
    result = item(
        qid,
        f"How are {herb['entity_name']} and {syn['entity_name']} represented separately in TCM Research Corpus v1, and what evidence is recorded for each?",
        "herbal_medicine + syndrome_differentiation", difficulty, [herb, syn], [h, s], ["syndrome", "herbal"],
    )
    result["requested_targets"] = [
        {"entity_name": herb["entity_name"], "category": "herbal_medicine", "evidence_ids": [herb["chunk_id"]]},
        {"entity_name": syn["entity_name"], "category": "syndrome_differentiation", "evidence_ids": [syn["chunk_id"]]},
    ]
    result["relationship_gold_status"] = "not_established"
    result["unsupported_claim_constraints"] = [f"Do not infer a relationship between {herb['entity_name']} and {syn['entity_name']}; none is established by the supplied evidence."]
    return result


def validate(items: list[dict], corpus: list[dict], old_questions: set[str], old_entities: set[str], old_evidence: set[str]) -> None:
    assert len(items) == 100 and len({x["question_id"] for x in items}) == 100
    assert len({norm(x["question"]) for x in items}) == 100
    assert not ({norm(x["question"]) for x in items} & old_questions)
    assert not ({norm(e) for x in items for e in x["source_entity_names"]} & old_entities)
    assert not ({e for x in items for e in x["source_evidence_ids"]} & old_evidence)
    ids = {x["chunk_id"] for x in corpus}
    assert all(set(x["source_evidence_ids"]) <= ids for x in items)
    assert {k: sum(x["difficulty"] == k for x in items) for k in ("easy", "medium", "hard")} == {"easy": 40, "medium": 40, "hard": 20}
    assert {k: sum(x["domain"] == k for x in items) for k in ("herbal_medicine", "syndrome_differentiation", "herbal_medicine + syndrome_differentiation")} == {"herbal_medicine": 60, "syndrome_differentiation": 25, "herbal_medicine + syndrome_differentiation": 15}


def main() -> None:
    assert hashlib.sha256(CORPUS.read_bytes()).hexdigest() == CORPUS_SHA
    corpus = rows(CORPUS)
    old_questions, old_entities, old_evidence = excluded_material(corpus)
    herbs = sorted((x for x in corpus if x["category"] == "herbal_medicine" and norm(x["entity_name"]) not in old_entities and x["chunk_id"] not in old_evidence and (x["structured_facts"].get("properties_english") or x["structured_facts"].get("function")) and not x["text"].strip().casefold().startswith("see ")), key=lambda x: x["chunk_id"])
    syndromes = sorted((x for x in corpus if x["category"] == "syndrome_differentiation" and norm(x["entity_name"]) not in old_entities and x["chunk_id"] not in old_evidence and x["structured_facts"].get("definition_original") and not x["text"].strip().casefold().startswith("see ")), key=lambda x: x["chunk_id"])
    if len(herbs) < 75 or len(syndromes) < 40:
        raise SystemExit(f"INSUFFICIENT_NON_OVERLAPPING_CORPUS_RECORDS herbs={len(herbs)} syndromes={len(syndromes)}")
    difficulty = ["easy"] * 25 + ["medium"] * 25 + ["hard"] * 10 + ["easy"] * 10 + ["medium"] * 10 + ["hard"] * 5 + ["easy"] * 5 + ["medium"] * 5 + ["hard"] * 5
    built: list[dict] = []
    for i, (chunk, level) in enumerate(zip(herbs[:60], difficulty[:60]), 1): built.append(herbal(chunk, f"rq4-v1-{i:03d}", level))
    for i, (chunk, level) in enumerate(zip(syndromes[:25], difficulty[60:85]), 61): built.append(syndrome(chunk, f"rq4-v1-{i:03d}", level))
    for i, (h, s, level) in enumerate(zip(herbs[60:75], syndromes[25:40], difficulty[85:]), 86): built.append(multi(h, s, f"rq4-v1-{i:03d}", level))
    validate(built, corpus, old_questions, old_entities, old_evidence)
    OUT.mkdir(parents=True, exist_ok=True)
    benchmark = OUT / "benchmark_rq4_v1_draft.jsonl"
    benchmark.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in built), encoding="utf-8")
    summary_fields = ["question_id", "question", "domain", "difficulty", "expected_specialists", "source_entity_names", "source_evidence_ids", "held_out_status", "status"]
    with (OUT / "benchmark_rq4_v1_draft.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields); writer.writeheader()
        for value in built:
            row = {key: value.get(key, "") for key in summary_fields}
            for key in ("expected_specialists", "source_entity_names", "source_evidence_ids"): row[key] = "|".join(row[key])
            writer.writerow(row)
    review = []
    for value in built:
        for index, fact in enumerate(value["gold_facts"], 1):
            review.append({
                "row_id": f"{value['question_id']}-f{index:02d}", "question_id": value["question_id"], "question": value["question"],
                "domain": value["domain"], "difficulty": value["difficulty"], "gold_fact_index": index,
                "gold_atomic_fact": fact["fact"], "preferred_evidence_id": "|".join(fact["preferred_evidence_ids"]),
                "acceptable_alternate_evidence_ids": "|".join(fact["acceptable_alternate_evidence_ids"]),
                "evidence_excerpt": fact["evidence_excerpt"], "source_review_status": "", "review_reason": "", "confidence": "",
            })
    with (OUT / "external_source_review_for_gpt.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(review[0])); writer.writeheader(); writer.writerows(review)
    instructions = """# RQ4 external source-grounded review\n\nDo not assess clinical truth. For each row, decide only whether the supplied corpus excerpt directly supports the Gold atomic fact and whether the question asks for that fact. Do not use external knowledge. Keep all protected fields unchanged. Allowed source_review_status values: APPROVE, REVISE, REMOVE, UNRESOLVED. Confidence: HIGH, MEDIUM, LOW. Every row must be resolved before freeze.\n"""
    (OUT / "external_source_review_instructions.md").write_text(instructions, encoding="utf-8")
    leakage = {
        "scope": "deterministic exact/normalized/entity/evidence-ID checks; not a claim of absolute semantic independence",
        "prior_benchmark_files_checked": len(list(ROOT.glob("research/benchmarks/**/benchmark*.jsonl"))) - 1,
        "exact_question_overlap": 0, "normalized_question_overlap": 0, "source_entity_overlap": 0, "source_evidence_id_overlap": 0,
        "excluded_entity_count": len(old_entities), "excluded_evidence_id_count": len(old_evidence),
    }
    (OUT / "leakage_report_rq4_v1.md").write_text("# RQ4 leakage report\n\n" + "\n".join(f"- {k}: {v}" for k, v in leakage.items()) + "\n", encoding="utf-8")
    manifest = {
        "status": STATUS, "source_review": "PENDING", "corpus_name": "TCM Research Corpus v1", "corpus_sha256": CORPUS_SHA,
        "question_count": 100, "gold_fact_count": len(review), "domain": {"herbal": 60, "syndrome": 25, "multi_target": 15},
        "difficulty": {"easy": 40, "medium": 40, "hard": 20}, "draft_sha256": hashlib.sha256(benchmark.read_bytes()).hexdigest(),
        "leakage": leakage, "held_out": True, "frozen": False,
    }
    (OUT / "heldout_manifest_rq4_v1_draft.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "coverage_report_rq4_v1_draft.md").write_text(f"# RQ4 candidate coverage\n\nStatus: {STATUS}\n\n- Questions: 100\n- Gold facts: {len(review)}\n- Domains: 60 herbal / 25 syndrome / 15 multi-target\n- Difficulty: 40 easy / 40 medium / 20 hard\n- Source review: pending\n", encoding="utf-8")
    (OUT / "README.md").write_text(f"# TCM Gold RQ4 v1 candidate\n\nStatus: **{STATUS}**. This draft is source-grounded but externally unreviewed and is not frozen or eligible for formal execution.\n", encoding="utf-8")
    print(json.dumps({"questions": 100, "gold_facts": len(review), "status": STATUS, "provider_calls": 0}))


if __name__ == "__main__":
    main()
