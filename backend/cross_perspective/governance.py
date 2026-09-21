from __future__ import annotations

import json

from providers import build_llm_provider
from providers.base import LLMProvider

from .model_calls import StructuredCallResult, StructuredModelCallFailure, call_structured_model
from .schemas import CrossPerspectiveAnswer, PerspectiveEvidencePacket


GOVERNANCE_MODEL = "Qwen/Qwen3-8B"
GOVERNANCE_SYSTEM_PROMPT = (
    "You are the governance and synthesis component of a development-only cross-perspective health QA prototype. "
    "Use only the supplied evidence packets. Never introduce substantive medical claims absent from those packets. "
    "Keep TCM traditional-framework interpretations distinct from Western biomedical interpretations; never imply that their mechanisms are equivalent. "
    "Agreement between perspectives is not proof. Preserve disagreement, insufficient evidence, uncertainty, missing information, and unavailable perspectives. "
    "Never invent claim IDs, source IDs, chunk IDs, or citations, and never upgrade possible or partial support into certainty. "
    "Do not expose chain-of-thought. Return only concise structured JSON matching the requested contract."
)


class GovernanceContractError(RuntimeError):
    pass


def validate_governance_grounding(
    answer: CrossPerspectiveAnswer,
    packets: dict[str, PerspectiveEvidencePacket],
) -> None:
    claims_by_perspective = {
        name: {claim.claim_id: claim for claim in packet.claims}
        for name, packet in packets.items()
    }
    all_claim_ids = {
        claim_id
        for perspective_claims in claims_by_perspective.values()
        for claim_id in perspective_claims
    }

    for name in ("tcm", "western"):
        packet = packets[name]
        summary = getattr(answer.perspectives, name)
        if summary.available != packet.available:
            raise GovernanceContractError(f"{name} availability does not match its evidence packet")
        for claim_id in summary.supported_claim_ids:
            claim = claims_by_perspective[name].get(claim_id)
            if claim is None:
                raise GovernanceContractError(f"unknown {name} claim ID: {claim_id}")
            if claim.support_status == "insufficient":
                raise GovernanceContractError(f"insufficient claim listed as supported: {claim_id}")

    for agreement in answer.agreements:
        if not set(agreement.supporting_claim_ids).issubset(all_claim_ids):
            raise GovernanceContractError("agreement references an unknown claim ID")
        if agreement.supporting_claim_ids:
            has_tcm = any(item in claims_by_perspective["tcm"] for item in agreement.supporting_claim_ids)
            has_western = any(item in claims_by_perspective["western"] for item in agreement.supporting_claim_ids)
            if not (has_tcm and has_western):
                raise GovernanceContractError("agreement must be supported by both perspectives")

    for difference in answer.differences_or_conflicts:
        if not set(difference.tcm_claim_ids).issubset(claims_by_perspective["tcm"]):
            raise GovernanceContractError("difference references an unknown TCM claim ID")
        if not set(difference.western_claim_ids).issubset(claims_by_perspective["western"]):
            raise GovernanceContractError("difference references an unknown Western claim ID")

    for mapping in answer.source_map:
        perspective_claims = claims_by_perspective[mapping.perspective]
        if not set(mapping.claim_ids).issubset(perspective_claims):
            raise GovernanceContractError("source map references an unknown claim ID")
        linked_refs = [
            ref
            for claim_id in mapping.claim_ids
            for ref in perspective_claims[claim_id].evidence_refs
        ]
        linked_sources = {ref.source_id for ref in linked_refs}
        linked_chunks = {ref.chunk_id for ref in linked_refs}
        if not set(mapping.source_ids).issubset(linked_sources):
            raise GovernanceContractError("source map contains a source ID not linked to its claims")
        if not set(mapping.chunk_ids).issubset(linked_chunks):
            raise GovernanceContractError("source map contains a chunk ID not linked to its claims")


class CrossPerspectiveGovernanceAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or build_llm_provider(GOVERNANCE_MODEL, thinking_behavior="send_false")

    async def synthesize(
        self,
        *,
        question: str,
        packets: dict[str, PerspectiveEvidencePacket],
    ) -> StructuredCallResult:
        packet_payload = {name: packet.model_dump(mode="json") for name, packet in packets.items()}
        prompt = (
            f"Original question:\n{question}\n\n"
            f"Evidence packets:\n{json.dumps(packet_payload, ensure_ascii=False, sort_keys=True)}\n\n"
            "Return the CrossPerspectiveAnswer JSON contract. Every supported_claim_id and every source-map ID must exist in the supplied packets. "
            "A source-map entry must include claim_ids and only their linked source_ids and chunk_ids. "
            "Both tcm and western perspective summaries are required; mark unavailable perspectives unavailable and do not reconstruct them."
        )
        result = await call_structured_model(
            provider=self.provider,
            role="governance",
            response_model=CrossPerspectiveAnswer,
            system=GOVERNANCE_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=1800,
        )
        answer = result.value
        assert isinstance(answer, CrossPerspectiveAnswer)
        try:
            validate_governance_grounding(answer, packets)
        except GovernanceContractError as exc:
            # This is a semantic contract failure. It is never retried or substituted.
            event = result.events[-1].model_copy(
                update={
                    "success": False,
                    "failure_class": "semantic",
                    "error_summary": "Governance output failed evidence-grounding validation.",
                }
            )
            raise StructuredModelCallFailure(str(exc), events=[*result.events[:-1], event]) from exc
        return result
