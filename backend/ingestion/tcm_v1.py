from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Iterable
import unicodedata

import yaml

from corpus.v1_models import CanonicalSourceRecord, NormalizedRecord, ResearchChunk
from ingestion.tabular import read_tabular


ALLOWED_CATEGORIES = {
    "syndrome_differentiation", "tcm_symptoms", "herbal_medicine", "prescriptions_formulae",
    "acupuncture", "meridian_theory", "constitution_analysis", "safety_contraindications_toxicity",
    "general_tcm_concepts",
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).replace("\x00", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalized_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", normalize_text(value).casefold())


def intact_text(value: Any) -> bool:
    text = normalize_text(value)
    return bool(text) and "\ufffd" not in text and "���" not in text


def compact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, raw in value.items():
        if isinstance(raw, dict):
            nested = compact_mapping(raw)
            if nested:
                compact[key] = nested
        elif isinstance(raw, list):
            items = [normalize_text(item) for item in raw if normalize_text(item)]
            if items:
                compact[key] = list(dict.fromkeys(items))
        else:
            text = normalize_text(raw)
            if text:
                compact[key] = text
    return compact


def split_aliases(*values: Any) -> list[str]:
    aliases: list[str] = []
    for value in values:
        for item in re.split(r"[|;,/]+", normalize_text(value)):
            item = item.strip()
            if item and intact_text(item) and item not in aliases:
                aliases.append(item)
    return aliases


def _source(config: dict[str, Any], source_id: str) -> dict[str, Any]:
    try:
        return next(item for item in config["sources"] if item["source_id"] == source_id)
    except StopIteration as exc:
        raise ValueError(f"Unknown configured source: {source_id}") from exc


def _base_record(config: dict[str, Any], source_id: str, source_record_id: str, **values: Any) -> NormalizedRecord:
    source = _source(config, source_id)
    return NormalizedRecord(
        source_id=source_id,
        source_name=source["source_name"],
        source_record_id=source_record_id,
        source_version=source.get("source_version"),
        source_url=source["official_url"],
        source_title=source["source_title"],
        source_citation=source["source_citation"],
        source_license_status=source["license_status"],
        source_access_date=source["access_date"],
        expert_review_claimed_by_source=source.get("expert_review_claimed"),
        ingestion_timestamp=config["ingestion_timestamp"],
        corpus_version=config["corpus_version"],
        **values,
    )


def _external_ids(row: dict[str, Any], names: Iterable[str]) -> dict[str, str]:
    return {name: normalize_text(row.get(name)) for name in names if normalize_text(row.get(name))}


def import_symmap_herbs(path: Path, config: dict[str, Any], source_id: str) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    for row in read_tabular(path):
        if normalize_text(row.get("Suppress")) not in {"", "0"}:
            continue
        record_id = normalize_text(row.get("Herb_id"))
        names = [row.get("English_name"), row.get("Pinyin_name"), row.get("Latin_name"), row.get("Chinese_name")]
        entity_name = next((normalize_text(item) for item in names if intact_text(item)), "")
        facts = compact_mapping({
            "chinese_name_original": row.get("Chinese_name"), "pinyin_name": row.get("Pinyin_name"),
            "latin_name": row.get("Latin_name"), "english_name": row.get("English_name"),
            "properties_chinese_original": row.get("Properties_Chinese"), "properties_english": row.get("Properties_English"),
            "meridians_chinese_original": row.get("Meridians_Chinese"), "meridians_english": row.get("Meridians_English"),
            "class_chinese_original": row.get("Class_Chinese"), "class_english": row.get("Class_English"),
            "use_part": row.get("UsePart"),
            "external_ids": _external_ids(row, ["TCMID_id", "TCM-ID_id", "TCMSP_id", "HERBDB_ID", "Link_herb_id"]),
        })
        evidence_fields = ["properties_english", "meridians_english", "class_english", "use_part"]
        if not record_id or not entity_name or not any(facts.get(field) for field in evidence_fields):
            continue
        aliases = split_aliases(*names, row.get("Alias"))
        aliases = [item for item in aliases if normalized_key(item) != normalized_key(entity_name)]
        text_parts = [f"Herb: {entity_name}."]
        labels = [("Pinyin", row.get("Pinyin_name")), ("Latin name", row.get("Latin_name")),
                  ("Traditional properties", row.get("Properties_English")), ("Meridians", row.get("Meridians_English")),
                  ("Traditional class", row.get("Class_English")), ("Used part", row.get("UsePart"))]
        text_parts.extend(f"{label}: {normalize_text(value)}." for label, value in labels if intact_text(value))
        history = ["Imported deterministic source fields from the official SymMap v2 SMHB workbook.",
                   "Whitespace and Unicode were normalized; no factual claim was generated."]
        if any("\ufffd" in normalize_text(value) or "���" in normalize_text(value) for value in row.values()):
            history.append("Corrupted upstream text was preserved in structured facts and omitted from retrieval text.")
        records.append(_base_record(
            config, source_id, f"SMHB{int(record_id):05d}" if record_id.isdigit() else record_id,
            category="herbal_medicine", subcategory="herb", entity_type="herb", entity_name=entity_name,
            aliases=aliases, language="en", source_text=None, structured_facts=facts,
            review_status="source_claimed_review", transformation_history=history, original_record=dict(row),
        ))
    return records


def import_symmap_syndromes(path: Path, config: dict[str, Any], source_id: str) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    for row in read_tabular(path):
        if normalize_text(row.get("Suppress")) not in {"", "0"}:
            continue
        record_id = normalize_text(row.get("Syndrome_id"))
        names = [row.get("Syndrome_English"), row.get("Syndrome_PinYin"), row.get("Syndrome_name")]
        entity_name = next((normalize_text(item) for item in names if intact_text(item)), "")
        if not record_id or not entity_name:
            continue
        raw_type = normalize_text(row.get("Type"))
        is_symptom = "symptom" in raw_type.casefold()
        category = "tcm_symptoms" if is_symptom else "syndrome_differentiation"
        entity_type = "tcm_symptom" if is_symptom else "syndrome"
        facts = compact_mapping({
            "chinese_name_original": row.get("Syndrome_name"), "english_name": row.get("Syndrome_English"),
            "pinyin_name": row.get("Syndrome_PinYin"), "definition_original": row.get("Syndrome_definition"),
            "source_type": raw_type, "versions": split_aliases(row.get("Version")),
        })
        text_parts = [f"{entity_type.replace('_', ' ').title()}: {entity_name}."]
        if intact_text(row.get("Syndrome_PinYin")):
            text_parts.append(f"Pinyin: {normalize_text(row.get('Syndrome_PinYin'))}.")
        if intact_text(row.get("Syndrome_definition")):
            text_parts.append(f"Source definition: {normalize_text(row.get('Syndrome_definition'))}")
        history = ["Imported deterministic source fields from the official SymMap v2 SMSY workbook.",
                   "Whitespace and Unicode were normalized; no factual claim was generated."]
        if not intact_text(row.get("Syndrome_definition")) and normalize_text(row.get("Syndrome_definition")):
            history.append("Corrupted upstream definition was preserved in structured facts and omitted from retrieval text.")
        records.append(_base_record(
            config, source_id, f"SMSY{int(record_id):05d}" if record_id.isdigit() else record_id,
            category=category, subcategory=raw_type or None, entity_type=entity_type, entity_name=entity_name,
            aliases=[item for item in split_aliases(*names) if normalized_key(item) != normalized_key(entity_name)],
            language="en", source_text=normalize_text(row.get("Syndrome_definition")) or None,
            structured_facts=facts, review_status="source_claimed_review", transformation_history=history,
            original_record=dict(row),
        ))
    return records


def import_tcmbank_herbs(path: Path, config: dict[str, Any], source_id: str) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    for row in read_tabular(path):
        record_id = normalize_text(row.get("TCMBank_ID"))
        names = [row.get("TCM_name_en"), row.get("level2_name"), row.get("Herb_pinyin_name"), row.get("Herb_latin_name"), row.get("TCM_name")]
        entity_name = next((normalize_text(item) for item in names if intact_text(item)), "")
        facts = compact_mapping({
            "chinese_name_original": row.get("TCM_name"), "english_name": row.get("TCM_name_en"),
            "pinyin_name": row.get("Herb_pinyin_name"), "latin_name": row.get("Herb_latin_name"),
            "properties": row.get("Properties"), "meridians": row.get("Meridians"), "used_part": row.get("UsePart"),
            "function": row.get("Function"), "indication": row.get("Indication"), "toxicity": row.get("Toxicity"),
            "clinical_manifestations": row.get("Clinical_manifestations"),
            "therapeutic_class_en": row.get("Therapeutic_en_class"), "therapeutic_class_cn_original": row.get("Therapeutic_cn_class"),
            "external_ids": _external_ids(row, ["TCMID_id", "TCM_ID_id", "SymMap_id", "TCMSP_id", "Herb_ID"]),
        })
        evidence_fields = ["properties", "meridians", "used_part", "function", "indication", "toxicity", "clinical_manifestations", "therapeutic_class_en"]
        if not record_id or not entity_name or not any(facts.get(field) for field in evidence_fields):
            continue
        labels = [("Pinyin", row.get("Herb_pinyin_name")), ("Latin name", row.get("Herb_latin_name")),
                  ("Traditional properties", row.get("Properties")), ("Meridians", row.get("Meridians")),
                  ("Used part", row.get("UsePart")), ("Source-recorded function", row.get("Function")),
                  ("Source-recorded indication", row.get("Indication")), ("Source-recorded toxicity", row.get("Toxicity")),
                  ("Clinical manifestations", row.get("Clinical_manifestations")), ("Therapeutic class", row.get("Therapeutic_en_class"))]
        text_parts = [f"Herb: {entity_name}."]
        text_parts.extend(f"{label}: {normalize_text(value)}." for label, value in labels if intact_text(value))
        history = ["Imported deterministic source fields from the official TCMBank herb workbook.",
                   "Whitespace and Unicode were normalized; no factual claim was generated."]
        if any("\ufffd" in normalize_text(value) or "���" in normalize_text(value) for value in row.values()):
            history.append("Corrupted upstream text was preserved in structured facts and omitted from retrieval text.")
        records.append(_base_record(
            config, source_id, record_id, category="herbal_medicine", subcategory="herb", entity_type="herb",
            entity_name=entity_name,
            aliases=[item for item in split_aliases(*names) if normalized_key(item) != normalized_key(entity_name)],
            language="en", source_text=None, structured_facts=facts,
            review_status="needs_human_review", transformation_history=history, original_record=dict(row),
        ))
    return records


IMPORTERS: dict[str, Callable[[Path, dict[str, Any], str], list[NormalizedRecord]]] = {
    "symmap_herbs": import_symmap_herbs,
    "symmap_syndromes": import_symmap_syndromes,
    "tcmbank_herbs": import_tcmbank_herbs,
}


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Corpus config must contain a mapping.")
    return config


def source_audit_records(config: dict[str, Any]) -> list[CanonicalSourceRecord]:
    return [CanonicalSourceRecord.model_validate(item["audit"]) for item in config["sources"]]


def import_configured_sources(config: dict[str, Any], project_root: Path) -> tuple[list[NormalizedRecord], dict[str, Any]]:
    records: list[NormalizedRecord] = []
    missing: list[dict[str, str]] = []
    input_counts: Counter[str] = Counter()
    imported_counts: Counter[str] = Counter()
    excluded_counts: Counter[str] = Counter()
    for source in config["sources"]:
        for dataset in source.get("datasets", []):
            path = project_root / dataset["path"]
            if not path.exists():
                missing.append({"source_id": source["source_id"], "path": str(path), "instruction": dataset["manual_instruction"]})
                continue
            importer = IMPORTERS[dataset["importer"]]
            raw_count = sum(1 for _ in read_tabular(path))
            values = importer(path, config, source["source_id"])
            input_counts[source["source_id"]] += raw_count
            imported_counts[source["source_id"]] += len(values)
            excluded_counts[source["source_id"]] += raw_count - len(values)
            records.extend(values)
    return records, {
        "raw_record_count_by_source": dict(input_counts),
        "imported_record_count_by_source": dict(imported_counts),
        "excluded_record_count_by_source": dict(excluded_counts),
        "missing_inputs": missing,
    }


def _record_fingerprint(record: NormalizedRecord) -> str:
    value = {"source_id": record.source_id, "entity_type": record.entity_type, "entity_name": normalized_key(record.entity_name), "facts": record.structured_facts}
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def deduplicate_and_flag(records: list[NormalizedRecord]) -> tuple[list[NormalizedRecord], dict[str, Any]]:
    kept: list[NormalizedRecord] = []
    exact_seen: dict[str, str] = {}
    exact_removed: list[dict[str, str]] = []
    entity_groups: dict[tuple[str, str], list[NormalizedRecord]] = defaultdict(list)
    for record in records:
        fingerprint = _record_fingerprint(record)
        if fingerprint in exact_seen:
            exact_removed.append({"record": f"{record.source_id}:{record.source_record_id}", "duplicate_of": exact_seen[fingerprint]})
            continue
        exact_seen[fingerprint] = f"{record.source_id}:{record.source_record_id}"
        kept.append(record)
        keys = {normalized_key(record.entity_name), *(normalized_key(alias) for alias in record.aliases)} - {""}
        for key in sorted(keys):
            entity_groups[(record.entity_type, key)].append(record)

    alias_groups: list[dict[str, Any]] = []
    near_duplicate_groups: list[dict[str, Any]] = []
    conflict_groups: list[dict[str, Any]] = []
    processed_groups: set[tuple[str, ...]] = set()
    conflict_fields = {"properties", "properties_english", "meridians", "meridians_english", "toxicity", "function", "indication", "definition_original"}
    for (entity_type, key), group in entity_groups.items():
        identities = tuple(sorted(f"{item.source_id}:{item.source_record_id}" for item in group))
        if len(group) < 2 or identities in processed_groups:
            continue
        processed_groups.add(identities)
        alias_groups.append({"entity_type": entity_type, "normalized_alias": key, "records": list(identities)})
        texts = {
            f"{item.source_id}:{item.source_record_id}": set(re.findall(r"[0-9a-z\u3400-\u9fff]+", json.dumps(
                {"name": item.entity_name, "facts": item.structured_facts}, ensure_ascii=False, sort_keys=True
            ).casefold()))
            for item in group
        }
        similar_pairs: list[dict[str, Any]] = []
        text_items = list(texts.items())
        for left_index, (left_id, left_tokens) in enumerate(text_items):
            for right_id, right_tokens in text_items[left_index + 1:]:
                union = left_tokens | right_tokens
                similarity = len(left_tokens & right_tokens) / len(union) if union else 0.0
                if similarity >= 0.85:
                    similar_pairs.append({"left": left_id, "right": right_id, "token_jaccard": round(similarity, 6)})
        if similar_pairs:
            near_duplicate_groups.append({"entity_type": entity_type, "normalized_alias": key, "pairs": similar_pairs})
        conflicts: list[str] = []
        for field in sorted(conflict_fields):
            values = {normalize_text(item.structured_facts.get(field)) for item in group if intact_text(item.structured_facts.get(field))}
            if len(values) > 1:
                conflicts.append(field)
        if conflicts:
            group_id = "conflict-" + hashlib.sha256("|".join(identities).encode("utf-8")).hexdigest()[:12]
            for item in group:
                if group_id not in item.conflict_group_ids:
                    item.conflict_group_ids.append(group_id)
            conflict_groups.append({"conflict_group_id": group_id, "records": list(identities), "conflicting_fields": conflicts})
    for record in kept:
        record.conflict_group_ids.sort()
    return kept, {
        "raw_normalized_count": len(records),
        "normalized_count": len(kept),
        "exact_duplicates_removed": len(exact_removed),
        "exact_duplicate_records": exact_removed,
        "alias_equivalent_groups": len(alias_groups),
        "alias_groups": alias_groups,
        "near_duplicates_flagged": len(near_duplicate_groups),
        "near_duplicate_groups": near_duplicate_groups,
        "conflicts_preserved": len(conflict_groups),
        "conflict_groups": conflict_groups,
    }


def deterministic_chunk_id(record: NormalizedRecord, text: str) -> str:
    canonical = json.dumps({
        "source_id": record.source_id, "source_record_id": record.source_record_id, "category": record.category,
        "entity_type": record.entity_type, "entity_name": record.entity_name, "text": normalize_text(text),
        "structured_facts": record.structured_facts,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "tcmv1-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def record_to_chunk(record: NormalizedRecord) -> ResearchChunk:
    text_parts = [f"{record.entity_type.replace('_', ' ').title()}: {record.entity_name}."]
    display_fields = [
        ("Pinyin", "pinyin_name"), ("Latin name", "latin_name"), ("Traditional properties", "properties"),
        ("Traditional properties", "properties_english"), ("Meridians", "meridians"), ("Meridians", "meridians_english"),
        ("Traditional class", "class_english"), ("Used part", "used_part"), ("Used part", "use_part"),
        ("Source-recorded function", "function"), ("Source-recorded indication", "indication"),
        ("Source-recorded toxicity", "toxicity"), ("Clinical manifestations", "clinical_manifestations"),
        ("Source definition", "definition_original"),
    ]
    seen_values: set[tuple[str, str]] = set()
    for label, key in display_fields:
        value = record.structured_facts.get(key)
        if intact_text(value) and (label, normalize_text(value)) not in seen_values:
            seen_values.add((label, normalize_text(value)))
            text_parts.append(f"{label}: {normalize_text(value)}.")
    if len(text_parts) == 1 and intact_text(record.source_text):
        text_parts.append(f"Source text: {normalize_text(record.source_text)}")
    text = " ".join(text_parts)
    return ResearchChunk(
        chunk_id=deterministic_chunk_id(record, text),
        **record.model_dump(exclude={"source_text", "original_record"}),
        text=text,
    )


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(project_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_manifest(config: dict[str, Any], project_root: Path, records: list[NormalizedRecord], chunks: list[ResearchChunk], import_report: dict[str, Any], dedup_report: dict[str, Any]) -> dict[str, Any]:
    source_files: list[dict[str, Any]] = []
    for source in config["sources"]:
        for dataset in source.get("datasets", []):
            path = project_root / dataset["path"]
            if path.exists():
                source_files.append({"source_id": source["source_id"], "path": dataset["path"], "sha256": file_hash(path), "bytes": path.stat().st_size})
    return {
        "schema_version": "1.0.0", "corpus_name": config["corpus_name"], "corpus_version": config["corpus_version"],
        "build_timestamp": datetime.now(timezone.utc).isoformat(), "deterministic_ingestion_timestamp": config["ingestion_timestamp"],
        "git_commit": git_commit(project_root), "transformation_code": "backend.ingestion.tcm_v1",
        "source_versions": {item["source_id"]: item.get("source_version") for item in config["sources"]},
        "source_files": source_files, "source_count": len({item.source_id for item in records}),
        "raw_record_count": sum(import_report["raw_record_count_by_source"].values()), "normalized_record_count": len(records),
        "relation_count": sum(bool(item.relation_type) for item in records), "chunk_count": len(chunks),
        "chunks_per_category": dict(Counter(item.category for item in chunks)),
        "chunks_per_source": dict(Counter(item.source_id for item in chunks)),
        "language_distribution": dict(Counter(item.language for item in chunks)),
        "deduplication": {key: value for key, value in dedup_report.items() if key not in {"alias_groups", "conflict_groups", "exact_duplicate_records", "near_duplicate_groups"}},
        "configuration": {"config_path": "research/corpus/configs/tcm_v1.yaml", "remote_embeddings_built": False},
        "excluded_sources": config.get("excluded_sources", []), "known_limitations": config.get("known_limitations", []),
        "redistribution_note": "Restricted-source raw, normalized, and chunk data are local-only and gitignored pending rights clearance.",
    }


def write_jsonl(path: Path, values: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            data = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
            handle.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")
