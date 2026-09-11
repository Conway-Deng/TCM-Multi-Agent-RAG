from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Literal


Language = Literal["en", "zh", "ko"]

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
KNOWLEDGE_PATH = DATA_DIR / "tcm_knowledge_base.json"
SOURCES_PATH = DATA_DIR / "tcm_sources.json"

LANGUAGES: tuple[Language, ...] = ("en", "zh", "ko")

FORMULA_WARNING = (
    "Educational example only, not a prescription. Formula choice, ingredients, and dose require "
    "assessment by a qualified TCM practitioner plus clinician/pharmacist review for pregnancy, "
    "allergies, chronic disease, and medicine interactions."
)


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    organization: str
    year: int | None
    url_or_identifier: str
    section: str
    source_type: str
    license_or_usage_note: str
    verification_status: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRecord":
        return cls(
            source_id=str(data["id"]),
            title=str(data["title"]),
            organization=str(data["organization"]),
            year=data.get("year") if isinstance(data.get("year"), int) else None,
            url_or_identifier=str(data.get("url_or_identifier", "")),
            section=str(data.get("section", "")),
            source_type=str(data["source_type"]),
            license_or_usage_note=str(data.get("license_or_usage_note", "")),
            verification_status=str(data.get("verification_status", "needs_review")),
        )


@dataclass(frozen=True)
class KnowledgeEntry:
    entry_id: str
    topic: str
    subtopic: str
    symptoms: dict[Language, tuple[str, ...]]
    keywords: dict[Language, tuple[str, ...]]
    pattern: dict[Language, str]
    rationale: dict[Language, str]
    educational_examples: tuple[dict[str, Any], ...]
    safety_notes: dict[Language, tuple[str, ...]]
    source_ids: tuple[str, ...]
    source_type: str
    evidence_category: str
    tags: tuple[str, ...]
    review_status: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeEntry":
        def lang_tuple(field: str) -> dict[Language, tuple[str, ...]]:
            value = data.get(field, {})
            return {
                language: tuple(str(item) for item in value.get(language, []))
                for language in LANGUAGES
            }

        def lang_str(field: str) -> dict[Language, str]:
            value = data.get(field, {})
            return {
                language: str(value.get(language, value.get("en", "")))
                for language in LANGUAGES
            }

        return cls(
            entry_id=str(data["id"]),
            topic=str(data["topic"]),
            subtopic=str(data["subtopic"]),
            symptoms=lang_tuple("symptoms"),
            keywords=lang_tuple("keywords"),
            pattern=lang_str("pattern"),
            rationale=lang_str("rationale"),
            educational_examples=tuple(dict(item) for item in data.get("educational_examples", [])),
            safety_notes=lang_tuple("safety_notes"),
            source_ids=tuple(str(item) for item in data.get("source_ids", [])),
            source_type=str(data["source_type"]),
            evidence_category=str(data["evidence_category"]),
            tags=tuple(str(item) for item in data.get("tags", [])),
            review_status=str(data.get("review_status", "needs_human_review")),
        )

    def title(self, language: Language = "en") -> str:
        titles = {
            "sleep": {"en": "Sleep-related presentation", "zh": "睡眠相关表现", "ko": "수면 관련 양상"},
            "fatigue": {"en": "Fatigue and low energy", "zh": "疲劳与乏力", "ko": "피로와 기력 저하"},
            "digestion": {"en": "Digestive presentation", "zh": "消化相关表现", "ko": "소화 관련 양상"},
            "stress": {"en": "Stress and constraint symptoms", "zh": "压力与郁滞表现", "ko": "스트레스와 울체 양상"},
            "headache": {"en": "Headache and dizziness", "zh": "头痛与头晕", "ko": "두통과 어지러움"},
            "throat_cough": {"en": "Throat and cough presentation", "zh": "咽喉与咳嗽表现", "ko": "목과 기침 양상"},
            "cold_heat_sweating": {"en": "Cold/heat and sweating signs", "zh": "寒热与出汗表现", "ko": "한열과 땀 양상"},
            "lower_back_tinnitus_deficiency": {"en": "Lower-back and deficiency signs", "zh": "腰酸耳鸣与虚损表现", "ko": "허리·이명·허증 양상"},
        }
        return titles.get(self.topic, {}).get(language, self.topic.replace("_", " ").title())

    def snippet(self, language: Language = "en") -> str:
        prefix = {
            "en": "Local educational TCM evidence: ",
            "zh": "本地中医教学证据提示：",
            "ko": "로컬 한의학 교육 근거: ",
        }[language]
        return prefix + self.rationale[language]

    def all_search_terms(self) -> dict[Language, tuple[str, ...]]:
        terms: dict[Language, tuple[str, ...]] = {}
        for language in LANGUAGES:
            terms[language] = tuple(
                dict.fromkeys(
                    [
                        *self.keywords[language],
                        *self.symptoms[language],
                        self.pattern[language],
                        self.title(language),
                        *self.tags,
                    ]
                )
            )
        return terms


@lru_cache(maxsize=1)
def load_knowledge_base() -> tuple[KnowledgeEntry, ...]:
    data = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    return tuple(KnowledgeEntry.from_dict(item) for item in data)


@lru_cache(maxsize=1)
def load_source_registry() -> dict[str, SourceRecord]:
    data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    return {str(item["id"]): SourceRecord.from_dict(item) for item in data}


KNOWLEDGE_BASE = load_knowledge_base()
SOURCE_REGISTRY = load_source_registry()


def knowledge_base_stats() -> dict[str, int]:
    entries = load_knowledge_base()
    return {
        "entry_count": len(entries),
        "verified_entries": sum(1 for entry in entries if entry.review_status == "verified"),
        "needs_human_review_entries": sum(1 for entry in entries if entry.review_status == "needs_human_review"),
    }
