from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from .models import WesternKnowledgeChunk, WesternSourceRecord


BENCHMARK_NAME = "MediRAG-West Pilot Benchmark v0.1"
BENCHMARK_VERSION = "western-pilot-v0.1-draft"
VALID_TOPICS = (
    "cough",
    "dyspepsia_digestive_symptoms",
    "headache",
    "constipation",
)
VALID_QUESTION_TYPES = (
    "direct_evidence",
    "paraphrased_retrieval",
    "multi_source_synthesis",
    "difficult_or_insufficient",
)
VALID_ANSWERABILITY = ("supported", "partially_supported", "insufficient")
EXPECTED_PER_TOPIC = {
    "direct_evidence": 4,
    "paraphrased_retrieval": 3,
    "multi_source_synthesis": 3,
    "difficult_or_insufficient": 2,
}
REQUIRED_FIELDS = {
    "case_id",
    "topic",
    "question",
    "question_type",
    "answerability",
    "gold_source_ids",
    "gold_chunk_ids",
    "optional_secondary_chunk_ids",
    "expected_evidence_points",
    "annotation_notes",
}
ABSOLUTE_ABSENCE_PATTERNS = (
    re.compile(r"\bno (?:medical|scientific|published|clinical) evidence exists\b", re.IGNORECASE),
    re.compile(r"\bthere is no evidence\b", re.IGNORECASE),
    re.compile(r"\bno evidence exists\b", re.IGNORECASE),
)
IDENTIFIER_PATTERN = re.compile(
    r"\b(?:west-pmc-[a-z0-9-]+|PMC\d+|10\.\d{4,9}/\S+)\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.casefold())


def _normal_question(value: str) -> str:
    return " ".join(_tokens(value))


def load_benchmark(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    cases: list[dict[str, Any]] = []
    errors: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                errors.append(f"line {line_number}: empty JSONL record")
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: malformed JSONL ({exc.msg})")
                continue
            if not isinstance(value, dict):
                errors.append(f"line {line_number}: benchmark record must be an object")
                continue
            cases.append(value)
    return cases, errors


def validate_benchmark(
    cases: list[dict[str, Any]],
    sources: dict[str, WesternSourceRecord],
    chunks: Iterable[WesternKnowledgeChunk],
    *,
    parse_errors: list[str] | None = None,
) -> dict[str, Any]:
    errors = list(parse_errors or [])
    warnings: list[str] = []
    chunks_by_id = {item.chunk_id: item for item in chunks}
    ids: Counter[str] = Counter()
    questions: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    answerability_counts: Counter[str] = Counter()
    topic_type_counts: dict[str, Counter[str]] = defaultdict(Counter)
    topic_answerability_counts: dict[str, Counter[str]] = defaultdict(Counter)
    source_case_counts: Counter[str] = Counter()
    chunk_case_counts: Counter[str] = Counter()

    if len(cases) != 48:
        errors.append(f"benchmark must contain exactly 48 cases; found {len(cases)}")

    for index, case in enumerate(cases, start=1):
        label = str(case.get("case_id") or f"record-{index}")
        missing = sorted(REQUIRED_FIELDS - set(case))
        if missing:
            errors.append(f"{label}: missing required fields {missing}")
        case_id = str(case.get("case_id", "")).strip()
        question = str(case.get("question", "")).strip()
        topic = str(case.get("topic", ""))
        question_type = str(case.get("question_type", ""))
        answerability = str(case.get("answerability", ""))
        ids[case_id] += 1
        questions[_normal_question(question)] += 1
        topic_counts[topic] += 1
        type_counts[question_type] += 1
        answerability_counts[answerability] += 1
        topic_type_counts[topic][question_type] += 1
        topic_answerability_counts[topic][answerability] += 1
        if not case_id:
            errors.append(f"record {index}: empty case_id")
        if not question:
            errors.append(f"{label}: empty question")
        if topic not in VALID_TOPICS:
            errors.append(f"{label}: invalid topic {topic!r}")
        if question_type not in VALID_QUESTION_TYPES:
            errors.append(f"{label}: invalid question_type {question_type!r}")
        if answerability not in VALID_ANSWERABILITY:
            errors.append(f"{label}: invalid answerability {answerability!r}")

        primary_ids = list(case.get("gold_chunk_ids") or [])
        secondary_ids = list(case.get("optional_secondary_chunk_ids") or [])
        source_ids = list(case.get("gold_source_ids") or [])
        evidence_points = list(case.get("expected_evidence_points") or [])
        notes = str(case.get("annotation_notes", ""))
        if answerability == "supported" and not primary_ids:
            errors.append(f"{label}: supported case has no primary gold evidence")
        if evidence_points and not (primary_ids or secondary_ids):
            errors.append(f"{label}: expected evidence points have no supporting gold evidence")
        if answerability == "insufficient" and not re.search(r"insufficient within the current pilot corpus", notes, re.IGNORECASE):
            errors.append(f"{label}: insufficient case must use corpus-bounded insufficiency wording")
        if answerability == "insufficient" and any(pattern.search(notes) for pattern in ABSOLUTE_ABSENCE_PATTERNS):
            errors.append(f"{label}: insufficiency annotation falsely claims literature-wide absence")

        case_sources: set[str] = set()
        for source_id in source_ids:
            if source_id not in sources:
                errors.append(f"{label}: unknown source_id {source_id}")
            else:
                case_sources.add(source_id)
        for chunk_id in primary_ids + secondary_ids:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                errors.append(f"{label}: unknown chunk_id {chunk_id}")
                continue
            case_sources.add(chunk.source_id)
            if chunk_id in primary_ids and chunk.source_id not in source_ids:
                errors.append(
                    f"{label}: chunk/source mismatch; primary {chunk_id} belongs to {chunk.source_id} "
                    "but that source is not declared"
                )
            if topic in VALID_TOPICS and topic not in chunk.topics:
                errors.append(f"{label}: gold chunk {chunk_id} is outside topic {topic}")
        for source_id in set(source_ids):
            if not any(chunks_by_id.get(chunk_id) and chunks_by_id[chunk_id].source_id == source_id for chunk_id in primary_ids):
                errors.append(f"{label}: declared primary source {source_id} has no primary gold chunk")
        if question_type == "multi_source_synthesis" and len(case_sources) < 2:
            warnings.append(f"{label}: multi_source_synthesis uses fewer than two sources")
        if len(primary_ids) > 4:
            warnings.append(f"{label}: unusually large primary gold set ({len(primary_ids)})")
        if len(secondary_ids) > 4:
            warnings.append(f"{label}: unusually large secondary gold set ({len(secondary_ids)})")
        for source_id in case_sources:
            source_case_counts[source_id] += 1
        for chunk_id in set(primary_ids + secondary_ids):
            if chunk_id in chunks_by_id:
                chunk_case_counts[chunk_id] += 1

    for value, count in ids.items():
        if value and count > 1:
            errors.append(f"duplicate case_id {value}")
    for value, count in questions.items():
        if value and count > 1:
            errors.append(f"duplicate question {value!r}")
    for topic in VALID_TOPICS:
        if topic_counts[topic] != 12:
            errors.append(f"topic {topic} must contain 12 cases; found {topic_counts[topic]}")
        for question_type, expected in EXPECTED_PER_TOPIC.items():
            actual = topic_type_counts[topic][question_type]
            if actual != expected:
                errors.append(
                    f"topic {topic} question_type {question_type} must contain {expected}; found {actual}"
                )
        used_sources = {source_id for source_id in source_case_counts if sources.get(source_id) and topic in sources[source_id].topics}
        if len(used_sources) < 3:
            warnings.append(f"topic {topic}: weak source diversity ({len(used_sources)} sources)")
    for source_id, count in source_case_counts.items():
        if count > 10:
            warnings.append(f"excessive source reuse: {source_id} appears in {count} cases")
    for chunk_id, count in chunk_case_counts.items():
        if count > 4:
            warnings.append(f"excessive chunk reuse: {chunk_id} appears in {count} cases")

    return {
        "status": "PASS" if not errors else "FAIL",
        "hard_error_count": len(errors),
        "hard_errors": errors,
        "warning_count": len(warnings),
        "warnings": warnings,
        "case_count": len(cases),
        "topic_counts": {topic: topic_counts[topic] for topic in VALID_TOPICS},
        "question_type_counts": {item: type_counts[item] for item in VALID_QUESTION_TYPES},
        "answerability_counts": {item: answerability_counts[item] for item in VALID_ANSWERABILITY},
        "per_topic_question_type_counts": {
            topic: {item: topic_type_counts[topic][item] for item in VALID_QUESTION_TYPES}
            for topic in VALID_TOPICS
        },
        "per_topic_answerability_counts": {
            topic: {item: topic_answerability_counts[topic][item] for item in VALID_ANSWERABILITY}
            for topic in VALID_TOPICS
        },
    }


def leakage_audit(
    cases: list[dict[str, Any]],
    sources: dict[str, WesternSourceRecord],
    chunks: Iterable[WesternKnowledgeChunk],
) -> dict[str, Any]:
    chunks_by_id = {item.chunk_id: item for item in chunks}
    suspicious: list[dict[str, Any]] = []
    for case in cases:
        question = str(case["question"])
        question_tokens = _tokens(question)
        question_set = set(question_tokens)
        reasons: list[str] = []
        if IDENTIFIER_PATTERN.search(question):
            reasons.append("identifier_or_bibliographic_leakage")
        candidate_ids = list(case.get("gold_chunk_ids") or []) + list(case.get("optional_secondary_chunk_ids") or [])
        candidate_sources = {
            chunks_by_id[item].source_id for item in candidate_ids if item in chunks_by_id
        } | set(case.get("gold_source_ids") or [])
        for source_id in candidate_sources:
            source = sources.get(source_id)
            if source is None:
                continue
            title_tokens = set(_tokens(source.title))
            if title_tokens and len(question_set & title_tokens) / len(title_tokens) >= 0.7:
                reasons.append(f"high_article_title_overlap:{source_id}")
        for chunk_id in candidate_ids:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            chunk_tokens = _tokens(chunk.text)
            windows = {
                tuple(chunk_tokens[index:index + 10])
                for index in range(max(0, len(chunk_tokens) - 9))
            }
            if len(question_tokens) >= 10 and any(tuple(question_tokens[index:index + 10]) in windows for index in range(len(question_tokens) - 9)):
                reasons.append(f"near_verbatim_10_token_overlap:{chunk_id}")
            section_tokens = _tokens(chunk.section.split(">")[-1])
            if len(section_tokens) >= 3 and " ".join(section_tokens) in _normal_question(question):
                reasons.append(f"exact_section_heading_overlap:{chunk_id}")
        if reasons:
            suspicious.append({"case_id": case["case_id"], "reasons": sorted(set(reasons))})
    return {
        "status": "PASS" if not suspicious else "REVIEW",
        "case_count": len(cases),
        "suspicious_case_count": len(suspicious),
        "suspicious_cases": suspicious,
        "diagnostics": {
            "identifier_patterns": "source/chunk IDs, PMCID, and DOI",
            "title_overlap_threshold": 0.7,
            "near_verbatim_threshold": "exact contiguous 10-token overlap",
            "section_heading_rule": "exact normalized heading of at least three tokens",
        },
    }


def coverage_audit(
    cases: list[dict[str, Any]],
    sources: dict[str, WesternSourceRecord],
    chunks: Iterable[WesternKnowledgeChunk],
) -> dict[str, Any]:
    chunks_by_id = {item.chunk_id: item for item in chunks}
    source_cases: dict[str, set[str]] = defaultdict(set)
    primary_chunk_cases: dict[str, set[str]] = defaultdict(set)
    secondary_chunk_cases: dict[str, set[str]] = defaultdict(set)
    topic_sources: dict[str, set[str]] = defaultdict(set)
    topic_primary_chunks: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        case_id = case["case_id"]
        topic = case["topic"]
        primary = list(case.get("gold_chunk_ids") or [])
        secondary = list(case.get("optional_secondary_chunk_ids") or [])
        for chunk_id in primary:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            primary_chunk_cases[chunk_id].add(case_id)
            source_cases[chunk.source_id].add(case_id)
            topic_sources[topic].add(chunk.source_id)
            topic_primary_chunks[topic].add(chunk_id)
        for chunk_id in secondary:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            secondary_chunk_cases[chunk_id].add(case_id)
            source_cases[chunk.source_id].add(case_id)
            topic_sources[topic].add(chunk.source_id)
    covered_sources = set(source_cases)
    primary_chunks = set(primary_chunk_cases)
    all_chunks = primary_chunks | set(secondary_chunk_cases)
    most_reused_source = max(source_cases, key=lambda item: (len(source_cases[item]), item)) if source_cases else None
    all_chunk_cases = {
        chunk_id: primary_chunk_cases.get(chunk_id, set()) | secondary_chunk_cases.get(chunk_id, set())
        for chunk_id in all_chunks
    }
    most_reused_chunk = max(all_chunk_cases, key=lambda item: (len(all_chunk_cases[item]), item)) if all_chunk_cases else None
    return {
        "distinct_gold_sources": len(covered_sources),
        "corpus_source_count": len(sources),
        "source_coverage_percent": round(100 * len(covered_sources) / max(1, len(sources)), 6),
        "distinct_primary_gold_chunks": len(primary_chunks),
        "distinct_primary_or_secondary_gold_chunks": len(all_chunks),
        "corpus_chunk_count": len(chunks_by_id),
        "source_case_counts": {item: len(source_cases[item]) for item in sorted(source_cases)},
        "primary_chunk_case_counts": {item: len(primary_chunk_cases[item]) for item in sorted(primary_chunk_cases)},
        "secondary_chunk_case_counts": {item: len(secondary_chunk_cases[item]) for item in sorted(secondary_chunk_cases)},
        "most_reused_source": {
            "source_id": most_reused_source,
            "case_count": len(source_cases[most_reused_source]) if most_reused_source else 0,
        },
        "most_reused_chunk": {
            "chunk_id": most_reused_chunk,
            "case_count": len(all_chunk_cases[most_reused_chunk]) if most_reused_chunk else 0,
        },
        "per_topic": {
            topic: {
                "source_count": len(topic_sources[topic]),
                "source_ids": sorted(topic_sources[topic]),
                "primary_gold_chunk_count": len(topic_primary_chunks[topic]),
            }
            for topic in VALID_TOPICS
        },
    }
