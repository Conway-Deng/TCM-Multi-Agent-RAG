from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
from typing import Any, Iterable
import unicodedata

from corpus.v1_models import ResearchChunk


TEXT_KEYS = {"question", "answer", "explanation", "reference_answer", "reference_notes", "stem"}


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-z\u3400-\u9fff\s]", " ", text)).strip()


def _strings(value: Any, key: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from _strings(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child, key)
    elif isinstance(value, str) and (key in TEXT_KEYS or not key):
        if normalize(value):
            yield key or "text", value


def load_benchmark_texts(paths: Iterable[Path]) -> tuple[list[dict[str, str]], set[str]]:
    texts: list[dict[str, str]] = []
    source_ids: set[str] = set()
    for path in paths:
        if not path.exists() or not path.is_file() or path.suffix.casefold() not in {".json", ".jsonl"}:
            continue
        if path.suffix.casefold() == ".jsonl":
            values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            raw = json.loads(path.read_text(encoding="utf-8"))
            values = raw if isinstance(raw, list) else [raw]
        for index, value in enumerate(values):
            if isinstance(value, dict):
                source_ids.update(str(item) for item in value.get("source_ids", []) if item)
                if value.get("source_id"):
                    source_ids.add(str(value["source_id"]))
            for field, text in _strings(value):
                texts.append({"benchmark": str(path), "record": str(index), "field": field, "text": text, "normalized": normalize(text)})
    return texts, source_ids


def _token_set(value: str) -> set[str]:
    return set(re.findall(r"[0-9a-z]+|[\u3400-\u9fff]", normalize(value)))


def check_contamination(chunks: Iterable[ResearchChunk], benchmark_paths: Iterable[Path]) -> dict[str, Any]:
    chunk_values = list(chunks)
    texts, benchmark_source_ids = load_benchmark_texts(benchmark_paths)
    exact_index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in texts:
        exact_index[item["normalized"]].append(item)
    exact: list[dict[str, str]] = []
    high_similarity: list[dict[str, Any]] = []
    source_leakage = sorted({chunk.source_id for chunk in chunk_values} & benchmark_source_ids)
    for chunk in chunk_values:
        chunk_normalized = normalize(chunk.text)
        for item in exact_index.get(chunk_normalized, []):
            exact.append({"chunk_id": chunk.chunk_id, "benchmark": item["benchmark"], "record": item["record"], "field": item["field"]})
        chunk_tokens = _token_set(chunk.text)
        if len(chunk_tokens) < 4:
            continue
        for item in texts:
            benchmark_tokens = _token_set(item["text"])
            if len(benchmark_tokens) < 4:
                continue
            intersection = len(chunk_tokens & benchmark_tokens)
            if intersection < 4:
                continue
            similarity = intersection / len(chunk_tokens | benchmark_tokens)
            containment = intersection / min(len(chunk_tokens), len(benchmark_tokens))
            if similarity >= 0.9 or containment >= 0.95:
                high_similarity.append({
                    "chunk_id": chunk.chunk_id, "benchmark": item["benchmark"], "record": item["record"],
                    "field": item["field"], "token_jaccard": round(similarity, 6), "shorter_text_containment": round(containment, 6),
                })
    return {
        "benchmark_file_count": len({item["benchmark"] for item in texts}),
        "benchmark_text_count": len(texts),
        "exact_text_overlap_count": len(exact), "exact_text_overlaps": exact,
        "high_similarity_overlap_count": len(high_similarity), "high_similarity_overlaps": high_similarity,
        "source_record_leakage_count": len(source_leakage), "source_record_leakage_source_ids": source_leakage,
        "zero_leakage_claimed": False,
        "interpretation": "No zero-leakage claim is made; the checker covers available local benchmark files only.",
    }
