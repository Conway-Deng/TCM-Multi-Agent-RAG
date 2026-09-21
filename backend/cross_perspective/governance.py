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
    "The packet interpretation field is presentation text, not evidence. Only non-insufficient claims with linked provenance may support substantive final statements. "
    "Insufficient claims cannot support agreements or source-mapped final claims. "
    "Never invent claim IDs, source IDs, chunk IDs, or citations, and never upgrade possible or partial support into certainty. "
    "Do not expose chain-of-thought. Return only concise structured JSON matching the requested contract."
)


class GovernanceContractError(RuntimeError):
    pass


def build_governance_payload(
    packets: dict[str, PerspectiveEvidencePacket],
) -> dict[str, dict[str, object]]:
    """Return the packet fields the governance model is allowed to use.

    ``interpretation`` remains in the full packet and trace, but is deliberately
    omitted here because it may contain unverified presentation text.
    """
    payload: dict[str, dict[str, object]] = {}
    for name, packet in packets.items():
        payload[name] = {
            "perspective": packet.perspective,
            "available": packet.available,
            "execution_status": packet.execution_status,
            "claims": [claim.model_dump(mode="json") for claim in packet.claims],
            "uncertainty": list(packet.uncertainty),
            "missing_information": list(packet.missing_information),
            "limitations": list(packet.limitations),
            "provenance": [item.model_dump(mode="json") for item in packet.provenance],
            "failure": packet.failure.model_dump(mode="json") if packet.failure else None,
        }
    return payload


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

    supported_by_perspective = {
        name: {
            claim_id
            for claim_id, claim in perspective_claims.items()
            if claim.support_status != "insufficient"
        }
        for name, perspective_claims in claims_by_perspective.items()
    }
    if len(all_claim_ids) != sum(len(items) for items in claims_by_perspective.values()):
        raise GovernanceContractError("claim IDs must be unique across perspectives")

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
        if not summary.available and summary.supported_claim_ids:
            raise GovernanceContractError(f"unavailable {name} summary cannot cite supported claims")
        if not summary.available and summary.summary.casefold().find("unavailable") == -1 and summary.summary.casefold().find("not selected") == -1:
            raise GovernanceContractError(f"unavailable {name} summary must state that it is unavailable")

    for agreement in answer.agreements:
        if not agreement.supporting_claim_ids:
            raise GovernanceContractError("agreement must declare supporting claim IDs")
        if not set(agreement.supporting_claim_ids).issubset(all_claim_ids):
            raise GovernanceContractError("agreement references an unknown claim ID")
        if not set(agreement.supporting_claim_ids).issubset(
            supported_by_perspective["tcm"] | supported_by_perspective["western"]
        ):
            raise GovernanceContractError("agreement cannot use an insufficient claim")
        tcm_ids = {item for item in agreement.supporting_claim_ids if item in claims_by_perspective["tcm"]}
        western_ids = {item for item in agreement.supporting_claim_ids if item in claims_by_perspective["western"]}
        if not tcm_ids or not western_ids:
            raise GovernanceContractError("agreement must be supported by both perspectives")
        for perspective, expected_ids in (("tcm", tcm_ids), ("western", western_ids)):
            if not any(
                mapping.final_claim_or_statement == agreement.statement
                and mapping.perspective == perspective
                and set(mapping.claim_ids) == expected_ids
                for mapping in answer.source_map
            ):
                raise GovernanceContractError("agreement requires matching source-map support from both perspectives")

    for difference in answer.differences_or_conflicts:
        if not difference.tcm_claim_ids or not difference.western_claim_ids:
            raise GovernanceContractError("difference/conflict must name claims from both perspectives")
        if not set(difference.tcm_claim_ids).issubset(claims_by_perspective["tcm"]):
            raise GovernanceContractError("difference references an unknown TCM claim ID")
        if not set(difference.western_claim_ids).issubset(claims_by_perspective["western"]):
            raise GovernanceContractError("difference references an unknown Western claim ID")
        if not set(difference.tcm_claim_ids).issubset(supported_by_perspective["tcm"]):
            raise GovernanceContractError("difference cannot use an insufficient TCM claim")
        if not set(difference.western_claim_ids).issubset(supported_by_perspective["western"]):
            raise GovernanceContractError("difference cannot use an insufficient Western claim")
        for perspective, expected_ids in (
            ("tcm", set(difference.tcm_claim_ids)),
            ("western", set(difference.western_claim_ids)),
        ):
            if not any(
                mapping.final_claim_or_statement == difference.statement
                and mapping.perspective == perspective
                and set(mapping.claim_ids) == expected_ids
                for mapping in answer.source_map
            ):
                raise GovernanceContractError("difference requires matching source-map support from both perspectives")

    for mapping in answer.source_map:
        perspective_claims = claims_by_perspective[mapping.perspective]
        if not set(mapping.claim_ids).issubset(perspective_claims):
            raise GovernanceContractError("source map references an unknown claim ID")
        if not set(mapping.claim_ids).issubset(supported_by_perspective[mapping.perspective]):
            raise GovernanceContractError("source map cannot reference an insufficient claim")
        linked_refs = [
            ref
            for claim_id in mapping.claim_ids
            for ref in perspective_claims[claim_id].evidence_refs
        ]
        linked_pairs = {(ref.source_id, ref.chunk_id) for ref in linked_refs}
        mapping_pairs = {(ref.source_id, ref.chunk_id) for ref in mapping.evidence_refs}
        if not mapping_pairs.issubset(linked_pairs):
            raise GovernanceContractError("source map contains a source/chunk pair not linked to its claims")

    for name in ("tcm", "western"):
        summary = getattr(answer.perspectives, name)
        if summary.supported_claim_ids and not any(
            mapping.final_claim_or_statement == summary.summary
            and mapping.perspective == name
            and set(mapping.claim_ids) == set(summary.supported_claim_ids)
            for mapping in answer.source_map
        ):
            raise GovernanceContractError(f"{name} summary requires matching source-map support")


class CrossPerspectiveGovernanceAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or build_llm_provider(GOVERNANCE_MODEL, thinking_behavior="send_false")

    async def synthesize(
        self,
        *,
        question: str,
        packets: dict[str, PerspectiveEvidencePacket],
    ) -> StructuredCallResult:
        packet_payload = build_governance_payload(packets)
        prompt = (
            f"Original question:\n{question}\n\n"
            f"Evidence packets:\n{json.dumps(packet_payload, ensure_ascii=False, sort_keys=True)}\n\n"
            "The packet interpretation field is not evidence and is intentionally omitted from this payload. "
            "Only non-insufficient claims with linked provenance may support substantive final statements. "
            "Return the CrossPerspectiveAnswer JSON contract. Every supported_claim_id and every source-map ID must exist in the supplied packets. "
            "A source-map entry must include exact evidence_refs pairs linked to its claim_ids. "
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
