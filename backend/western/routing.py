from __future__ import annotations

from dataclasses import dataclass
import re

from .schemas import WesternTopic


TOPIC_PATTERNS: dict[WesternTopic, tuple[str, ...]] = {
    WesternTopic.COUGH: (r"\bcough\b", r"\bcoughing\b"),
    WesternTopic.DYSPEPSIA: (
        r"\bdyspepsia\b", r"\bindigestion\b", r"\bfunctional dyspepsia\b", r"\bdigestive symptoms?\b",
    ),
    WesternTopic.HEADACHE: (r"\bheadaches?\b", r"\bmigraines?\b"),
    WesternTopic.CONSTIPATION: (r"\bconstipation\b", r"\bconstipated\b"),
}


@dataclass(frozen=True)
class WesternScopeDecision:
    supported: bool
    topic: WesternTopic | None
    matched_topics: tuple[WesternTopic, ...]
    reason: str


def route_western_scope(question: str) -> WesternScopeDecision:
    normalized = question.casefold()
    matches = tuple(
        topic for topic, patterns in TOPIC_PATTERNS.items()
        if any(re.search(pattern, normalized) for pattern in patterns)
    )
    if len(matches) == 1:
        return WesternScopeDecision(True, matches[0], matches, "Question matches one supported Western pilot topic.")
    if not matches:
        return WesternScopeDecision(
            False,
            None,
            (),
            "The Western pilot covers only cough, dyspepsia/digestive symptoms, headache/migraine, and constipation.",
        )
    return WesternScopeDecision(
        False,
        None,
        matches,
        "The Phase 1B baseline handles one pilot topic per request; this question matches multiple topics.",
    )
