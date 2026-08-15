from __future__ import annotations

import re

from schemas.research import PlannerOutput, RunState
from tcm.language import detect_language
from tcm.safety import check_emergency
from tcm.scope import classify_scope


SUBDOMAIN_TERMS: dict[str, tuple[str, ...]] = {
    "syndrome": ("syndrome", "pattern", "辨证", "证型", "症状", "증후", "변증", "insomnia", "fatigue", "失眠", "乏力"),
    "herbal": ("herb", "formula", "中药", "草药", "方剂", "한약", "약초"),
    "acupuncture": ("acupuncture", "meridian", "point", "针灸", "经络", "穴位", "침", "경락"),
    "constitution": ("constitution", "体质", "체질"),
    "dietary": ("diet", "food", "dietary", "食疗", "饮食", "食物", "식이", "음식"),
    "lifestyle": ("sleep", "routine", "exercise", "season", "yangsheng", "睡眠", "作息", "运动", "养生", "수면", "생활"),
}


AGENT_BY_SUBDOMAIN = {
    "syndrome": "syndrome",
    "herbal": "herbal",
    "acupuncture": "acupuncture_meridian",
    "constitution": "constitution",
    "dietary": "dietary_therapy",
    "lifestyle": "lifestyle_yangsheng",
}


class QueryPlannerAgent:
    agent_id = "query_planner"
    version = "1.0.0"

    def plan(self, question: str) -> PlannerOutput:
        normalized = re.sub(r"\s+", " ", question).strip()
        language = detect_language(normalized)
        emergency = check_emergency(normalized)
        scope = classify_scope(normalized)
        subdomains = [name for name, terms in SUBDOMAIN_TERMS.items() if any(term.casefold() in normalized.casefold() for term in terms)]
        if not subdomains and scope.status == "supported":
            subdomains = ["syndrome"]
        state = RunState.SAFETY_CRITICAL if emergency.urgent else RunState(scope.status)
        if state == RunState.EVIDENCE_INSUFFICIENT and subdomains:
            state = RunState.SUPPORTED
        educational_terms = ("explain", "concept", "theory", "teaching", "educational", "解释", "概念", "理论", "教学", "설명", "개념", "이론", "교육")
        if state == RunState.INSUFFICIENT_INFORMATION and subdomains and any(term in normalized.casefold() for term in educational_terms):
            state = RunState.SUPPORTED
        missing: list[str] = []
        if state == RunState.INSUFFICIENT_INFORMATION:
            missing = list(scope.clarifying_questions)
        required = list(dict.fromkeys(AGENT_BY_SUBDOMAIN[item] for item in subdomains))
        return PlannerOutput(
            normalized_question=normalized,
            language=language,
            intent="tcm_educational_question" if state == RunState.SUPPORTED else state.value,
            subdomains=subdomains,
            required_agents=required,
            missing_context=missing,
            retrieval_filters={"topics": subdomains},
            safety_critical=emergency.urgent,
            scope_state=state,
            reasoning_summary=(
                f"Deterministic routing selected {', '.join(subdomains) or 'no specialist domain'}; "
                f"scope={state.value}. This is a classification summary, not private chain-of-thought."
            ),
        )
