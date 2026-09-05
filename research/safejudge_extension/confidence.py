from __future__ import annotations

from .models import ConfidenceInput, ConfidencePenalty, ConfidenceResult, ScoreComponent, Severity


_POSITIVE_WEIGHTS = {
    "evidence_coverage": 0.35,
    "citation_coverage": 0.20,
    "retrieval_sufficiency": 0.25,
    "verified_evidence_ratio": 0.10,
    "agent_agreement_score": 0.10,
}


def _component(name: str, value: float) -> ScoreComponent:
    weight = _POSITIVE_WEIGHTS[name]
    return ScoreComponent(
        signal=name,
        observed_value=round(value, 4),
        weight=weight,
        contribution=round(value * weight, 4),
    )


def _penalty(name: str, value: float, maximum: float) -> ConfidencePenalty:
    return ConfidencePenalty(
        signal=name,
        observed_value=round(value, 4),
        maximum_penalty=maximum,
        applied_penalty=round(value * maximum, 4),
    )


def judge_confidence(request: ConfidenceInput) -> ConfidenceResult:
    """Compute evidence confidence from observable signals, never agent self-ratings."""
    evidence = request.evidence_signals
    conflict = request.conflict_signals
    unsupported_rate = min(
        1.0,
        len(set(evidence.unsupported_claim_ids)) / max(1, evidence.eligible_claim_count),
    )
    abstention_rate = request.abstained_agent_count / max(1, request.active_agent_count)
    model_failure_rate = min(1.0, request.model_failure_count / max(1, request.active_agent_count))

    components = [
        _component("evidence_coverage", evidence.evidence_coverage),
        _component("citation_coverage", evidence.citation_coverage),
        _component("retrieval_sufficiency", evidence.retrieval_sufficiency),
        _component("verified_evidence_ratio", evidence.verified_evidence_ratio),
        _component("agent_agreement_score", conflict.agent_agreement_score),
    ]
    penalties = [
        _penalty("unsupported_claim_rate", unsupported_rate, 0.30),
        _penalty("unresolved_conflict", conflict.conflict_score, 0.18),
        _penalty("agent_abstention", abstention_rate, 0.10),
        _penalty("model_failure", model_failure_rate, 0.07),
    ]

    high_safety_count = 0
    medium_safety_count = 0
    if request.safety_result:
        high_safety_count = sum(item.severity == Severity.HIGH for item in request.safety_result.findings)
        medium_safety_count = sum(item.severity == Severity.MEDIUM for item in request.safety_result.findings)
    safety_signal = min(1.0, high_safety_count * 0.5 + medium_safety_count * 0.25)
    penalties.append(_penalty("source_grounded_safety_flags", safety_signal, 0.25))

    score = sum(item.contribution for item in components) - sum(item.applied_penalty for item in penalties)
    caps: list[str] = []
    score = min(score, 0.90)
    if evidence.eligible_claim_count == 0:
        score = 0.0
        caps.append("no eligible claims: score set to 0")
    if unsupported_rate > 0:
        score = min(score, 0.69)
        caps.append("unsupported claims present: capped at 0.69")
    if evidence.retrieval_sufficiency < 0.40:
        score = min(score, 0.49)
        caps.append("retrieval/evidence sufficiency below 0.40: capped at 0.49")
    if conflict.unresolved_conflicts and conflict.conflict_score >= 0.50:
        score = min(score, 0.59)
        caps.append("material unresolved conflict: capped at 0.59")
    if high_safety_count:
        score = min(score, 0.39)
        caps.append("high source-grounded safety flag present: capped at 0.39")
    score = round(max(0.0, score), 4)

    band = (
        "strong" if score >= 0.75 else
        "moderate" if score >= 0.55 else
        "limited" if score >= 0.30 else
        "insufficient"
    )
    weak = [item.signal for item in components if item.observed_value < 0.50]
    if unsupported_rate:
        weak.append("unsupported claims")
    if conflict.unresolved_conflicts:
        weak.append("unresolved conflict")
    return ConfidenceResult(
        evidence_confidence=score,
        band=band,
        positive_components=components,
        penalties=penalties,
        caps_applied=caps,
        missing_or_weak_signals=list(dict.fromkeys(weak)),
    )
