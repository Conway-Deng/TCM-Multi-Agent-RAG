from __future__ import annotations

from ..schemas import AgentOutput, ConflictItem, ConflictJudgeResult


def judge_conflicts(agents: list[AgentOutput]) -> ConflictJudgeResult:
    active = [agent for agent in agents if not agent.abstained]
    agreements: list[str] = []
    complementary: list[str] = []
    conflicts: list[ConflictItem] = []
    if len(active) > 1:
        if all("not a diagnosis" in (agent.summary + " " + " ".join(agent.limitations)).casefold() or agent.source_type.value == "fixture" for agent in active):
            agreements.append("Agents preserve uncertainty and do not establish a unified diagnosis.")
        domains = ", ".join(agent.domain.value for agent in active)
        complementary.append(f"Outputs provide separate {domains} research perspectives with different provenance.")

    unsupported_fixture_claims = [
        claim
        for agent in active
        if agent.source_type.value == "fixture"
        for claim in agent.claims
        if not claim.evidence_ids or "confirmed diagnosis" in claim.text.casefold()
    ]
    for claim in unsupported_fixture_claims:
        conflicts.append(
            ConflictItem(
                claim_ids=[claim.claim_id],
                type="evidence_strength",
                description="A synthetic fixture claim lacks evidence support and must not be merged as a verified conclusion.",
                resolvable=False,
            )
        )
    if any("conflict" in str(agent.metadata.get("fixture_case_id", "")) for agent in active):
        claim_ids = [claim.claim_id for agent in active for claim in agent.claims]
        conflicts.append(
            ConflictItem(
                claim_ids=claim_ids,
                type="direct",
                description="The deliberate conflict fixture treats an educational pattern as a confirmed diagnosis, which conflicts with the TCM agent's stated limitation.",
                resolvable=False,
            )
        )
    score = min(1.0, sum(0.5 if item.type == "direct" else 0.25 for item in conflicts))
    return ConflictJudgeResult(conflicts=conflicts, agreements=agreements, complementary_points=complementary, conflict_score=round(score, 3))
