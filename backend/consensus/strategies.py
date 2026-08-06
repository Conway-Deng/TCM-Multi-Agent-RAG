from __future__ import annotations

from .judges import judge_confidence, judge_conflicts, judge_evidence, judge_safety
from .schemas import (
    AgentOutput,
    AgentWeight,
    ConfidenceSummary,
    IntegratedResponse,
    JudgeResults,
)


def _safety_notes(agents: list[AgentOutput]) -> list[str]:
    notes = list(dict.fromkeys(flag for agent in agents for flag in agent.safety_flags))
    if any(agent.urgent for agent in agents):
        notes.insert(0, "Urgent deterministic safety routing takes priority over orchestration output.")
    return notes[:8]


def concatenate(agents: list[AgentOutput]) -> tuple[IntegratedResponse, JudgeResults]:
    summaries = [f"{agent.domain.value} ({agent.source_type.value}): {agent.summary}" for agent in agents]
    limitations = list(dict.fromkeys(item for agent in agents for item in agent.limitations))
    integrated = IntegratedResponse(
        summary="\n\n".join(summaries),
        agreements=[],
        disagreements=[],
        safety_notes=_safety_notes(agents),
        limitations=["Direct combination baseline: agreements and disagreements were not evaluated.", *limitations],
        unresolved_questions=[],
        confidence=ConfidenceSummary(score=0.0, level="low", reason="No consensus confidence is claimed by the concatenate baseline."),
    )
    return integrated, JudgeResults()


def calculate_agent_weights(agents: list[AgentOutput]) -> list[AgentWeight]:
    raw: list[tuple[AgentOutput, float, list[str]]] = []
    for agent in agents:
        evidence_coverage = sum(1 for claim in agent.claims if claim.evidence_ids) / max(1, len(agent.claims))
        evidence_strength = sum(item.relevance_score for item in agent.evidence) / max(1, len(agent.evidence))
        score = 0.15 + evidence_coverage * 0.28 + evidence_strength * 0.24 + min(len(agent.claims), 4) * 0.04
        rationale = [f"evidence coverage {evidence_coverage:.2f}", f"mean relevance {evidence_strength:.2f}"]
        if agent.source_type.value == "fixture":
            score *= 0.45
            rationale.append("0.45 fixture penalty")
        if agent.abstained:
            score *= 0.15
            rationale.append("0.15 abstention penalty")
        if agent.urgent:
            score = min(score, 0.2)
            rationale.append("urgent content excluded from ordinary aggregation")
        if agent.generation_source == "mock_fallback":
            score *= 0.85
            rationale.append("0.85 provider-fallback penalty")
        raw.append((agent, max(0.01, score), rationale))
    total = sum(item[1] for item in raw)
    return [AgentWeight(agent_id=agent.agent_id, weight=round(score / total, 4), rationale=rationale) for agent, score, rationale in raw]


def weighted(agents: list[AgentOutput]) -> tuple[IntegratedResponse, JudgeResults, list[AgentWeight], list[str], list[str]]:
    weights = calculate_agent_weights(agents)
    weight_by_id = {item.agent_id: item.weight for item in weights}
    selected: list[str] = []
    excluded: list[str] = []
    selected_text: list[str] = []
    for agent in agents:
        for claim in agent.claims:
            if agent.abstained or not claim.evidence_ids or weight_by_id[agent.agent_id] < 0.12:
                excluded.append(claim.claim_id)
            else:
                selected.append(claim.claim_id)
                selected_text.append(f"[{agent.domain.value}; weight {weight_by_id[agent.agent_id]:.2f}] {claim.text}")
    evidence = judge_evidence(agents)
    safety = judge_safety(agents)
    conflict = judge_conflicts(agents)
    confidence = judge_confidence(agents, evidence, safety, conflict)
    integrated = IntegratedResponse(
        summary=" ".join(selected_text) if selected_text else "No supported claim passed the deterministic weighted baseline.",
        agreements=conflict.agreements,
        disagreements=[item.description for item in conflict.conflicts],
        safety_notes=_safety_notes(agents),
        limitations=["Deterministic weighted research baseline; fixture data is synthetic and clinically unverified."],
        unresolved_questions=[],
        confidence=ConfidenceSummary(score=confidence.score, level=confidence.level, reason=confidence.reason),
    )
    return integrated, JudgeResults(evidence=evidence, safety=safety, conflict=conflict, confidence=confidence), weights, selected, excluded
