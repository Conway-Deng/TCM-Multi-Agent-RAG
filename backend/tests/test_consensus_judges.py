from __future__ import annotations

from consensus.judges import judge_confidence, judge_conflicts, judge_evidence, judge_safety
from consensus.schemas import AgentClaim, AgentEvidence, AgentOutput


def agent(*, source_type: str = "local_rag", urgent: bool = False, unsupported: bool = False, conflict: bool = False) -> AgentOutput:
    limitations = ["Synthetic fixture for orchestration testing only."] if source_type == "fixture" else ["Not a diagnosis."]
    claim = AgentClaim(
        claim_id="claim_unsupported" if unsupported else "claim_supported",
        text="This synthetic fixture asserts a confirmed diagnosis." if conflict else "Sleep symptoms require more clinical context.",
        evidence_ids=[] if unsupported or conflict else ["e1"],
        confidence=0.8,
    )
    return AgentOutput(
        agent_id="fixture" if source_type == "fixture" else "tcm",
        domain="western" if source_type == "fixture" else "tcm",
        source_type=source_type,
        summary="Educational summary; not a diagnosis.",
        claims=[claim],
        evidence=[] if not claim.evidence_ids else [AgentEvidence(evidence_id="e1", title="Sleep context", source="local", snippet="Sleep symptoms require more clinical context.", relevance_score=0.8)],
        confidence=0.8,
        limitations=limitations,
        urgent=urgent,
        scope_status="safety_critical" if urgent else "supported",
        safety_flags=["deterministic_tcm_urgent_rule"] if urgent else [],
        metadata={"fixture_case_id": "deliberate_conflict"} if conflict else {},
    )


def test_unsupported_claim_is_detected() -> None:
    result = judge_evidence([agent(unsupported=True)])
    assert result.unsupported_claim_ids == ["claim_unsupported"]
    assert result.evidence_coverage_score == 0


def test_deterministic_urgent_signal_is_preserved() -> None:
    result = judge_safety([agent(urgent=True)])
    assert result.urgent is True
    assert "authoritative" in result.reasoning_summary


def test_conflict_judge_does_not_call_complementary_domains_a_contradiction() -> None:
    result = judge_conflicts([agent(), agent(source_type="fixture")])
    assert not any(item.type == "direct" for item in result.conflicts)
    assert result.complementary_points


def test_deliberate_direct_conflict_is_detected() -> None:
    result = judge_conflicts([agent(), agent(source_type="fixture", conflict=True)])
    assert any(item.type == "direct" for item in result.conflicts)


def test_confidence_reduced_by_fixture_unsupported_conflict_and_fallback() -> None:
    agents = [agent(), agent(source_type="fixture", conflict=True)]
    evidence = judge_evidence(agents)
    safety = judge_safety(agents)
    conflict = judge_conflicts(agents)
    confidence = judge_confidence(agents, evidence, safety, conflict, model_failure_count=1)
    assert confidence.score < 0.5
    assert any("fixture" in item for item in confidence.penalties)
    assert any("model-call" in item for item in confidence.penalties)
