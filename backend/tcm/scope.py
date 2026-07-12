from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from .language import detect_language
from .schemas import ResponseLanguage, ScopeStatus


SCOPE_RULES_PATH = Path(__file__).resolve().parents[1] / "data" / "tcm_scope_rules.json"


@dataclass(frozen=True)
class ScopeDecision:
    status: ScopeStatus
    reason: str
    matched_group: str = ""
    matched_term: str = ""
    clarifying_questions: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def load_scope_rules() -> dict[str, Any]:
    return json.loads(SCOPE_RULES_PATH.read_text(encoding="utf-8"))


def _contains_any(text: str, terms: list[str]) -> tuple[bool, str]:
    normalised = text.casefold()
    for term in terms:
        if not term:
            continue
        term_norm = term.casefold()
        if re.fullmatch(r"[a-z][a-z-]*", term_norm):
            if re.search(rf"\b{re.escape(term_norm)}\b", normalised):
                return True, term
            continue
        if term_norm in normalised:
            return True, term
    return False, ""


def _word_count(text: str) -> int:
    latin = re.findall(r"[A-Za-z]+", text)
    cjk = re.findall(r"[\u3400-\u9fff\uac00-\ud7af]", text)
    return len(latin) + len(cjk)


def classify_scope(question: str) -> ScopeDecision:
    rules = load_scope_rules()
    language = detect_language(question)

    insufficient = rules.get("insufficient_information", {}).get("phrases", {})
    matched, term = _contains_any(question, insufficient.get(language, []) + insufficient.get("en", []))
    if matched and _word_count(question) <= 12:
        return ScopeDecision(
            status="insufficient_information",
            reason="The question is too general for evidence-grounded TCM retrieval.",
            matched_group="insufficient_information",
            matched_term=term,
            clarifying_questions=_clarifying_questions(language),
        )

    for group in rules.get("out_of_scope", []):
        terms = group.get("keywords", {}).get(language, []) + group.get("keywords", {}).get("en", [])
        matched, term = _contains_any(question, terms)
        if matched:
            return ScopeDecision(
                status="out_of_scope",
                reason=str(group.get("label", {}).get("en", group.get("id", "out_of_scope"))),
                matched_group=str(group.get("id", "out_of_scope")),
                matched_term=term,
            )

    for group in rules.get("supported_topic_groups", []):
        terms = group.get("keywords", {}).get(language, []) + group.get("keywords", {}).get("en", [])
        matched, term = _contains_any(question, terms)
        if matched:
            return ScopeDecision(
                status="supported",
                reason=str(group.get("label", {}).get("en", group.get("id", "supported"))),
                matched_group=str(group.get("id", "supported")),
                matched_term=term,
            )

    if _word_count(question) <= 10:
        return ScopeDecision(
            status="insufficient_information",
            reason="The question lacks enough symptom detail for the supported TCM-RAG scope.",
            matched_group="insufficient_information",
            clarifying_questions=_clarifying_questions(language),
        )

    return ScopeDecision(
        status="evidence_insufficient",
        reason="The question may be health-related, but it does not match the current limited TCM-RAG scope.",
        matched_group="unsupported_by_scope_keywords",
    )


def _clarifying_questions(language: ResponseLanguage) -> tuple[str, ...]:
    questions = {
        "en": (
            "What are the main symptoms you notice?",
            "When did they start and are they changing?",
            "Do you have fever, severe pain, breathing difficulty, fainting, bleeding, pregnancy, major illness, or current medication use?",
        ),
        "zh": (
            "最主要的不适是什么？",
            "大概从什么时候开始，最近是在加重还是缓解？",
            "是否有发热、剧痛、呼吸困难、晕厥、出血、妊娠、重大疾病或正在用药？",
        ),
        "ko": (
            "가장 주된 불편감은 무엇인가요?",
            "언제 시작되었고 최근 악화되거나 완화되고 있나요?",
            "발열, 심한 통증, 호흡곤란, 실신, 출혈, 임신, 중증 질환, 복용 중인 약이 있나요?",
        ),
    }
    return questions[language]
