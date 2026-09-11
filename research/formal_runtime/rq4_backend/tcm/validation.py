from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
LANGUAGES = ("en", "zh", "ko")
ALLOWED_EVIDENCE_CATEGORIES = {
    "traditional_theory",
    "terminology_or_educational",
    "educational_textbook_summary",
    "modern_clinical_evidence",
    "safety_information",
}
ALLOWED_REVIEW_STATUS = {"verified", "needs_human_review"}
ALLOWED_SOURCE_VERIFICATION = {"verified", "needs_review"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_knowledge_files(data_dir: Path = DATA_DIR) -> list[str]:
    errors: list[str] = []
    kb_path = data_dir / "tcm_knowledge_base.json"
    sources_path = data_dir / "tcm_sources.json"
    scope_path = data_dir / "tcm_scope_rules.json"

    for path in (kb_path, sources_path, scope_path):
        if not path.exists():
            errors.append(f"missing file: {path.name}")

    if errors:
        return errors

    entries = _load_json(kb_path)
    sources = _load_json(sources_path)
    scope_rules = _load_json(scope_path)

    if not isinstance(entries, list) or not entries:
        errors.append("tcm_knowledge_base.json must contain a non-empty list")
        entries = []
    if not isinstance(sources, list) or not sources:
        errors.append("tcm_sources.json must contain a non-empty list")
        sources = []
    if not isinstance(scope_rules, dict):
        errors.append("tcm_scope_rules.json must contain an object")
        scope_rules = {}

    source_ids = [item.get("id") for item in sources if isinstance(item, dict)]
    for source_id, count in Counter(source_ids).items():
        if count > 1:
            errors.append(f"duplicate source id: {source_id}")
    known_source_ids = {str(item) for item in source_ids if item}

    required_source_fields = ["id", "title", "organization", "source_type", "verification_status"]
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source record is not an object")
            continue
        for field in required_source_fields:
            if not str(source.get(field, "")).strip():
                errors.append(f"source {source.get('id', '<missing>')} missing {field}")
        if source.get("verification_status") not in ALLOWED_SOURCE_VERIFICATION:
            errors.append(f"source {source.get('id', '<missing>')} has invalid verification_status")

    entry_ids = [item.get("id") for item in entries if isinstance(item, dict)]
    for entry_id, count in Counter(entry_ids).items():
        if count > 1:
            errors.append(f"duplicate knowledge entry id: {entry_id}")

    required_entry_fields = [
        "id",
        "topic",
        "subtopic",
        "symptoms",
        "keywords",
        "pattern",
        "rationale",
        "source_ids",
        "source_type",
        "evidence_category",
        "tags",
        "review_status",
    ]
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("knowledge entry is not an object")
            continue
        entry_id = str(entry.get("id", "<missing>"))
        for field in required_entry_fields:
            if field not in entry or entry.get(field) in ("", [], {}, None):
                errors.append(f"entry {entry_id} missing or empty {field}")
        if entry.get("evidence_category") not in ALLOWED_EVIDENCE_CATEGORIES:
            errors.append(f"entry {entry_id} has unsupported evidence_category")
        if entry.get("review_status") not in ALLOWED_REVIEW_STATUS:
            errors.append(f"entry {entry_id} has invalid review_status")
        for lang_field in ("symptoms", "keywords", "pattern", "rationale", "safety_notes"):
            value = entry.get(lang_field, {})
            if not isinstance(value, dict):
                errors.append(f"entry {entry_id} field {lang_field} must be a language map")
                continue
            for language in LANGUAGES:
                if language not in value:
                    errors.append(f"entry {entry_id} field {lang_field} missing language {language}")
                elif lang_field in {"symptoms", "keywords", "safety_notes"}:
                    if not isinstance(value[language], list):
                        errors.append(f"entry {entry_id} field {lang_field}.{language} must be a list")
                    elif lang_field != "safety_notes" and not value[language]:
                        errors.append(f"entry {entry_id} field {lang_field}.{language} is empty")
                elif not str(value[language]).strip():
                    errors.append(f"entry {entry_id} field {lang_field}.{language} is empty")
        for source_id in entry.get("source_ids", []):
            if source_id not in known_source_ids:
                errors.append(f"entry {entry_id} references missing source id: {source_id}")

    if not scope_rules.get("supported_topic_groups"):
        errors.append("scope rules must define supported_topic_groups")
    if not scope_rules.get("out_of_scope"):
        errors.append("scope rules must define out_of_scope")
    if not scope_rules.get("safety_critical"):
        errors.append("scope rules must define safety_critical")

    return errors


def main() -> int:
    errors = validate_knowledge_files()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("TCM knowledge files are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
