from __future__ import annotations

from consensus.schemas import AgentClaim, AgentEvidence, AgentOutput
from consensus.strategies import calculate_agent_weights, concatenate, weighted


def make_agent(agent_id: str, source_type: str = "local_rag", *, abstained: bool = False) -> AgentOutput:
    limitation = ["Synthetic fixture for orchestration testing only."] if source_type == "fixture" else []
    return AgentOutput(
        agent_id=agent_id,
        domain="western" if source_type == "fixture" else "tcm",
        source_type=source_type,
        summary=f"{agent_id} summary",
        claims=[AgentClaim(claim_id=f"{agent_id}_claim", text="Sleep symptoms require context", evidence_ids=[f"{agent_id}_e1"], confidence=0.8)],
        evidence=[AgentEvidence(evidence_id=f"{agent_id}_e1", title="Sleep context", source="local", snippet="Sleep symptoms require context", relevance_score=0.8)],
        confidence=0.8,
        limitations=limitation,
        abstained=abstained,
    )


def test_concatenate_does_not_invent_consensus() -> None:
    integrated, judges = concatenate([make_agent("a"), make_agent("b", "fixture")])
    assert integrated.agreements == []
    assert integrated.disagreements == []
    assert "not evaluated" in integrated.limitations[0]
    assert judges.evidence is None


def test_weighted_strategy_is_deterministic() -> None:
    agents = [make_agent("a"), make_agent("b", "fixture")]
    first = weighted(agents)
    second = weighted(agents)
    assert first[2] == second[2]
    assert first[3] == second[3]


def test_fixture_receives_weight_penalty() -> None:
    weights = {item.agent_id: item.weight for item in calculate_agent_weights([make_agent("live"), make_agent("fixture", "fixture")])}
    assert weights["fixture"] < weights["live"]


def test_abstained_agent_does_not_dominate() -> None:
    weights = {item.agent_id: item.weight for item in calculate_agent_weights([make_agent("active"), make_agent("abstained", abstained=True)])}
    assert weights["abstained"] < weights["active"]
