from __future__ import annotations

from tcm.schemas import TCMConsultResponse

from .schemas import AgentClaim, AgentEvidence, AgentOutput, Domain, SourceType


def normalize_tcm_response(response: TCMConsultResponse, *, latency_ms: int = 0) -> AgentOutput:
    citation_by_id = {citation.source_id: citation for citation in response.citations}
    evidence = []
    for item in response.evidence:
        citations = [citation_by_id[source_id] for source_id in item.source_ids if source_id in citation_by_id]
        verification = "verified" if citations and all(citation.verification_status == "verified" for citation in citations) else "needs_review"
        evidence.append(
            AgentEvidence(
                evidence_id=item.evidence_id,
                title=item.title,
                source=item.source,
                snippet=item.snippet,
                relevance_score=item.relevance_score,
                source_type=item.source_type,
                verification_status=verification,
            )
        )
    claims = [
        AgentClaim(
            claim_id=f"tcm::{claim.claim_id}",
            text=claim.text,
            evidence_ids=list(claim.evidence_ids),
            confidence=response.confidence.score,
            claim_type=claim.claim_type,
        )
        for claim in response.claims
    ]
    safety_flags = list(response.safety_notes)
    if response.urgent and "deterministic_tcm_urgent_rule" not in safety_flags:
        safety_flags.insert(0, "deterministic_tcm_urgent_rule")
    metadata = {
        "scope_status": response.scope_status,
        "retrieval_method": response.retrieval_method,
        "candidate_count": response.candidate_count,
        "meaningful_match_count": response.meaningful_match_count,
        "top_relevance_score": response.top_relevance_score,
        "response_language": response.response_language,
        "llm_error": response.llm_error,
        "citations": [citation.model_dump() for citation in response.citations],
    }
    return AgentOutput(
        agent_id="tcm_agent",
        domain=Domain.TCM,
        source_type=SourceType.LOCAL_RAG,
        experimental=True,
        summary=response.summary,
        claims=claims,
        evidence=evidence,
        confidence=response.confidence.score,
        limitations=list(response.limitations),
        safety_flags=safety_flags,
        urgent=response.urgent,
        abstained=response.abstained,
        scope_status=response.scope_status,
        generation_source=response.generation_source,
        model=response.llm_model,
        latency_ms=latency_ms,
        metadata=metadata,
    )
