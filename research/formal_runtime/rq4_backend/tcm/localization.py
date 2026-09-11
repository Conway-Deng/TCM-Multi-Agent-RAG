from __future__ import annotations

from typing import Any, Literal

from .knowledge_base import FORMULA_WARNING, LANGUAGES, KnowledgeEntry


Language = Literal["en", "zh", "ko"]


FORMULA_WARNINGS: dict[Language, str] = {
    "en": FORMULA_WARNING,
    "zh": "仅供教学示例，并非处方。具体方剂、药味和剂量需要由合格中医师评估，并结合妊娠、过敏、慢性病和用药相互作用进行专业审查。",
    "ko": "교육용 예시일 뿐 처방이 아닙니다. 처방 선택, 구성 약재, 용량은 자격 있는 한의사 평가와 임신, 알레르기, 만성질환, 약물 상호작용 검토가 필요합니다.",
}

SOURCE_TYPES: dict[str, dict[Language, str]] = {
    "terminology_standard": {
        "en": "Terminology standard",
        "zh": "术语标准",
        "ko": "용어 표준",
    },
    "educational_textbook_summary": {
        "en": "Educational textbook summary",
        "zh": "教学资料摘要",
        "ko": "교육 자료 요약",
    },
    "safety_information": {
        "en": "Safety information",
        "zh": "安全信息",
        "ko": "안전 정보",
    },
}


def source_type_label(source_type: str, language: Language) -> str:
    return SOURCE_TYPES.get(source_type, {}).get(language, source_type.replace("_", " "))


def localized_entry_display(entry: KnowledgeEntry) -> dict[Language, dict[str, str]]:
    return {
        language: {
            "title": entry.title(language),
            "pattern": entry.pattern[language],
            "rationale": entry.rationale[language],
            "snippet": entry.snippet(language),
            "source_type": source_type_label(entry.source_type, language),
        }
        for language in LANGUAGES
    }


def localized_formula_display(entry: KnowledgeEntry, formula: dict[str, Any]) -> dict[Language, dict[str, str]]:
    return {
        language: {
            "name": str(formula.get("name", {}).get(language, formula.get("name", {}).get("en", ""))),
            "purpose": str(formula.get("description", {}).get(language, formula.get("description", {}).get("en", ""))),
            "safety_warning": str(formula.get("warning", {}).get(language, FORMULA_WARNINGS[language])),
        }
        for language in LANGUAGES
    }


def localized_entry_safety(entry: KnowledgeEntry, language: Language) -> str:
    notes = entry.safety_notes.get(language, ())
    return notes[0] if notes else ""


def localization_coverage(entries: tuple[KnowledgeEntry, ...] | None = None) -> dict[str, Any]:
    from .knowledge_base import KNOWLEDGE_BASE

    entries = entries or KNOWLEDGE_BASE
    missing_zh = []
    missing_ko = []
    for entry in entries:
        if not entry.pattern["zh"] or not entry.rationale["zh"]:
            missing_zh.append(entry.entry_id)
        if not entry.pattern["ko"] or not entry.rationale["ko"]:
            missing_ko.append(entry.entry_id)
    return {
        "entries": len(entries),
        "missing_zh": missing_zh,
        "missing_ko": missing_ko,
    }
