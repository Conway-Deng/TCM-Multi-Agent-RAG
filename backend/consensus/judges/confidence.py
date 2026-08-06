from __future__ import annotations

from ..schemas import (
    AgentOutput,
    ConfidenceJudgeResult,
    ConflictJudgeResult,
    EvidenceJudgeResult,
    SafetyJudgeResult,
)


def judge_confidence(
    agents: list[AgentOutput],
    evidence: EvidenceJudgeResult,
    safety: SafetyJudgeResult,
    conflict: ConflictJudgeResult,
    *,
    model_failure_count: int = 0,
) -> ConfidenceJudgeResult:
    score = 0.78
    penalties: list[str] = []
    score -= (1 - evidence.evidence_coverage_score) * 0.32
    if evidence.unsupported_claim_ids:
        penalty = min(0.25, len(evidence.unsupported_claim_ids) * 0.08)
        score -= penalty
        penalties.append(f"{len(evidence.unsupported_claim_ids)} unsupported claim(s)")
    if any(agent.source_type.value == "fixture" for agent in agents):
        score -= 0.16
        penalties.append("synthetic Western fixture used")
    if any(agent.abstained for agent in agents):
        score -= 0.12
        penalties.append("one or more agents abstained")
    if any(agent.generation_source == "mock_fallback" for agent in agents):
        score -= 0.08
        penalties.append("domain-agent provider fallback")
    if conflict.conflicts:
        score -= min(0.22, conflict.conflict_score * 0.22)
        penalties.append("unresolved conflict")
    if safety.urgent:
        score = min(score, 0.55)
        penalties.append("urgent safety context limits consensus confidence")
    if model_failure_count:
        score -= min(0.2, model_failure_count * 0.04)
        penalties.append(f"{model_failure_count} model-call failure(s)")
    score = round(max(0.05, min(0.9, score)), 3)
    level = "high" if score >= 0.75 else "medium" if score >= 0.45 else "low"
    reason = "Confidence is derived from evidence support, provenance, abstention, conflicts, safety, and model reliability—not from averaging agent self-ratings."
    return ConfidenceJudgeResult(score=score, level=level, reason=reason, penalties=penalties)
