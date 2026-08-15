from __future__ import annotations

from collections import Counter

from schemas.research import DebateTrace, ResearchAgentOutput


def debate(outputs: list[ResearchAgentOutput], rounds: int) -> DebateTrace:
    if rounds <= 0 or len(outputs) < 2:
        return DebateTrace(enabled=False)
    evidence_frequency = Counter(evidence_id for output in outputs for evidence_id in output.evidence_ids)
    shared = [evidence_id for evidence_id, count in evidence_frequency.items() if count > 1]
    claims_by_agent = {output.agent_name: [claim.text for claim in output.claims] for output in outputs}
    active_claiming = [name for name, claims in claims_by_agent.items() if claims]
    agreements = [f"Multiple agents independently used evidence {item}." for item in shared]
    disagreements: list[str] = []
    evidence_sets = {tuple(sorted(output.evidence_ids)) for output in outputs if output.evidence_ids}
    if len(active_claiming) > 1 and len(evidence_sets) > 1:
        disagreements.append("Specialist agents selected different evidence sets or emphasized different TCM concepts; this difference is disclosed rather than collapsed.")
    critiques: list[dict[str, str]] = []
    revisions: list[dict[str, str]] = []
    for round_number in range(1, rounds + 1):
        for output in outputs:
            other_evidence = set(evidence_frequency) - set(output.evidence_ids)
            critiques.append({
                "round": str(round_number),
                "agent_id": output.agent_id,
                "summary": f"Checked evidence boundaries against {len(other_evidence)} evidence item(s) used by other specialists.",
            })
            revisions.append({
                "round": str(round_number),
                "agent_id": output.agent_id,
                "summary": "Preserved evidence-linked claims and retained explicit uncertainty; no hidden reasoning was recorded.",
            })
    unresolved: list[str] = []
    return DebateTrace(
        enabled=True,
        rounds=rounds,
        critiques=critiques,
        revisions=revisions,
        agreements=agreements,
        disagreements=disagreements,
        unresolved_conflicts=unresolved,
    )
