from __future__ import annotations

import json

from providers import build_llm_provider
from providers.base import LLMProvider

from .model_calls import StructuredCallResult, StructuredModelCallFailure, call_structured_model
from .schemas import (
    CrossPerspectiveAnswer,
    OVERALL_NO_CLAIM_SUMMARY,
    PerspectiveEvidencePacket,
    TCM_NO_CLAIM_SUMMARY,
    TCM_UNAVAILABLE_SUMMARY,
    WESTERN_NO_CLAIM_SUMMARY,
    WESTERN_UNAVAILABLE_SUMMARY,
)


GOVERNANCE_MODEL = "Qwen/Qwen3-8B"
GOVERNANCE_TIMEOUT_SECONDS = 90.0
GOVERNANCE_MAX_TOKENS = 1800
GOVERNANCE_STRUCTURAL_TEMPLATE = '''{
  "overall_summary": "...",
  "overall_supporting_claim_ids": [],
  "perspectives": {
    "tcm": {
      "available": true,
      "summary": "...",
      "supported_claim_ids": []
    },
    "western": {
      "available": true,
      "summary": "...",
      "supported_claim_ids": []
    }
  },
  "agreements": [],
  "differences_or_conflicts": [],
  "evidence_gaps": [],
  "uncertainty": [],
  "source_map": []
}'''
GOVERNANCE_SYSTEM_PROMPT = (
    "You are the governance and synthesis component of a development-only cross-perspective health QA prototype. "
    "Use only the supplied evidence packets. Never introduce substantive medical claims absent from those packets. "
    "Keep TCM traditional-framework interpretations distinct from Western biomedical interpretations; never imply that their mechanisms are equivalent. "
    "Agreement between perspectives is not proof. Preserve disagreement, insufficient evidence, uncertainty, missing information, and unavailable perspectives. "
    "The packet interpretation field is presentation text, not evidence. Only non-insufficient claims with linked provenance may support substantive final statements. "
    "Insufficient claims cannot support agreements or source-mapped final claims. "
    "Overall summaries and perspective summaries must cite the exact non-insufficient claim IDs that support them. "
    "If no usable claim exists for a perspective or overall answer, use the deterministic unavailable status statement rather than a substantive assertion. "
    "Return exactly one JSON object with these eight top-level keys and no others: overall_summary, overall_supporting_claim_ids, perspectives, agreements, differences_or_conflicts, evidence_gaps, uncertainty, source_map. "
    "TCM and Western must never appear as top-level keys; they may appear only as perspectives.tcm and perspectives.western. "
    "source_map is a top-level array, never nested inside a perspective. Emit every field even when its value is an empty list. "
    "Use this structural template only as a shape guide; replace IDs only with exact IDs supplied in the evidence packets and never copy placeholder IDs:\n"
    f"{GOVERNANCE_STRUCTURAL_TEMPLATE}\n"
    "Each source_map entry must contain exactly final_claim_or_statement, perspective, claim_ids, and evidence_refs. "
    "Each evidence_refs item contains exact source_id and chunk_id only; title is optional and evidence excerpts must not be copied. "
    "Keep summaries concise, use the smallest sufficient subset of usable claims, do not enumerate every claim unless necessary, and do not repeat excerpts. "
    "Agreements and differences_or_conflicts may be empty when none are evidence-supported. Output JSON only, with no Markdown fences or prose outside the object. "
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

    usable_by_perspective = {
        name: {
            claim_id
            for claim_id, claim in perspective_claims.items()
            if packets[name].available and claim.support_status != "insufficient"
        }
        for name, perspective_claims in claims_by_perspective.items()
    }
    if len(all_claim_ids) != sum(len(items) for items in claims_by_perspective.values()):
        raise GovernanceContractError("claim IDs must be unique across perspectives")

    for name in ("tcm", "western"):
        packet = packets[name]
        summary = getattr(answer.perspectives, name)
        usable_ids = usable_by_perspective[name]
        if summary.available != packet.available:
            raise GovernanceContractError(f"{name} availability does not match its evidence packet")
        if not packet.available:
            if summary.supported_claim_ids:
                raise GovernanceContractError(f"unavailable {name} summary cannot cite supported claims")
            expected = TCM_UNAVAILABLE_SUMMARY if name == "tcm" else WESTERN_UNAVAILABLE_SUMMARY
            if summary.summary != expected:
                raise GovernanceContractError(f"unavailable {name} summary must use the deterministic status statement")
        elif usable_ids:
            if not summary.supported_claim_ids:
                raise GovernanceContractError(f"available {name} summary must cite usable claims")
        else:
            if summary.supported_claim_ids:
                raise GovernanceContractError(
                    f"{name} summary cannot cite claims when no usable (non-insufficient) claims exist"
                )
            expected = TCM_NO_CLAIM_SUMMARY if name == "tcm" else WESTERN_NO_CLAIM_SUMMARY
            if summary.summary != expected:
                raise GovernanceContractError(f"{name} summary must use the deterministic no-claim status statement")
        for claim_id in summary.supported_claim_ids:
            claim = claims_by_perspective[name].get(claim_id)
            if claim is None:
                raise GovernanceContractError(f"unknown {name} claim ID: {claim_id}")
            if claim_id not in usable_ids:
                raise GovernanceContractError(f"insufficient or unavailable claim listed as supported: {claim_id}")

    for agreement in answer.agreements:
        if not agreement.supporting_claim_ids:
            raise GovernanceContractError("agreement must declare supporting claim IDs")
        if not set(agreement.supporting_claim_ids).issubset(all_claim_ids):
            raise GovernanceContractError("agreement references an unknown claim ID")
        if not set(agreement.supporting_claim_ids).issubset(
            usable_by_perspective["tcm"] | usable_by_perspective["western"]
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
                and len(mapping.claim_ids) == len(expected_ids)
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
        if not set(difference.tcm_claim_ids).issubset(usable_by_perspective["tcm"]):
            raise GovernanceContractError("difference cannot use an insufficient TCM claim")
        if not set(difference.western_claim_ids).issubset(usable_by_perspective["western"]):
            raise GovernanceContractError("difference cannot use an insufficient Western claim")
        for perspective, expected_ids in (
            ("tcm", set(difference.tcm_claim_ids)),
            ("western", set(difference.western_claim_ids)),
        ):
            if not any(
                mapping.final_claim_or_statement == difference.statement
                and mapping.perspective == perspective
                and len(mapping.claim_ids) == len(expected_ids)
                and set(mapping.claim_ids) == expected_ids
                for mapping in answer.source_map
            ):
                raise GovernanceContractError("difference requires matching source-map support from both perspectives")

    for mapping in answer.source_map:
        perspective_claims = claims_by_perspective[mapping.perspective]
        if len(mapping.claim_ids) != len(set(mapping.claim_ids)):
            raise GovernanceContractError("source map claim IDs must be unique")
        if not set(mapping.claim_ids).issubset(perspective_claims):
            raise GovernanceContractError("source map references an unknown claim ID")
        if not set(mapping.claim_ids).issubset(usable_by_perspective[mapping.perspective]):
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
        for claim_id in mapping.claim_ids:
            claim_pairs = {
                (ref.source_id, ref.chunk_id)
                for ref in perspective_claims[claim_id].evidence_refs
            }
            if not claim_pairs.intersection(mapping_pairs):
                raise GovernanceContractError(
                    f"source map lacks evidence coverage for claim {claim_id}"
                )

    overall_ids = answer.overall_supporting_claim_ids
    all_usable = {
        claim_id: perspective
        for perspective, claim_ids in usable_by_perspective.items()
        for claim_id in claim_ids
    }
    if all_usable:
        if not overall_ids:
            raise GovernanceContractError("overall summary must cite usable claims")
        if len(overall_ids) != len(set(overall_ids)):
            raise GovernanceContractError("overall supporting claim IDs must be unique")
        if not set(overall_ids).issubset(all_usable):
            raise GovernanceContractError("overall summary references an unknown, insufficient, or unavailable claim")
        for perspective in sorted({all_usable[claim_id] for claim_id in overall_ids}):
            expected_ids = {claim_id for claim_id in overall_ids if all_usable[claim_id] == perspective}
            if not any(
                mapping.final_claim_or_statement == answer.overall_summary
                and mapping.perspective == perspective
                and len(mapping.claim_ids) == len(expected_ids)
                and set(mapping.claim_ids) == expected_ids
                for mapping in answer.source_map
            ):
                raise GovernanceContractError(
                    "overall summary requires matching source-map support for every represented perspective"
                )
    elif overall_ids:
        raise GovernanceContractError("overall supporting claim IDs must be empty when no usable claims exist")
    elif answer.overall_summary != OVERALL_NO_CLAIM_SUMMARY:
        raise GovernanceContractError("overall summary must use the deterministic no-claim status statement")

    for name in ("tcm", "western"):
        summary = getattr(answer.perspectives, name)
        if summary.supported_claim_ids and not any(
            mapping.final_claim_or_statement == summary.summary
            and mapping.perspective == name
            and len(mapping.claim_ids) == len(summary.supported_claim_ids)
            and set(mapping.claim_ids) == set(summary.supported_claim_ids)
            for mapping in answer.source_map
        ):
            raise GovernanceContractError(f"{name} summary requires matching source-map support")


class CrossPerspectiveGovernanceAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or build_llm_provider(
            GOVERNANCE_MODEL,
            timeout_override=GOVERNANCE_TIMEOUT_SECONDS,
            max_tokens_override=GOVERNANCE_MAX_TOKENS,
            thinking_behavior="send_false",
        )

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
            "overall_supporting_claim_ids must be non-empty whenever any usable claim exists, and overall_summary must have exact source-map entries for every represented perspective. "
            "When no usable claim exists, use the deterministic no-claim status statement. "
            "Emit exactly these eight top-level keys: overall_summary, overall_supporting_claim_ids, perspectives, agreements, differences_or_conflicts, evidence_gaps, uncertainty, source_map. "
            "Never emit tcm or western at the top level; nest them only under perspectives. source_map is a top-level array. "
            "Structural template (shape only; replace placeholders with exact supplied IDs and keep all empty lists):\n"
            f"{GOVERNANCE_STRUCTURAL_TEMPLATE}\n"
            "Each source_map entry has final_claim_or_statement, perspective, claim_ids, and evidence_refs; each evidence_refs item uses exact source_id and chunk_id, with no copied excerpts. "
            "Keep the output compact: concise summaries, smallest sufficient claim subset, no repeated excerpts, no prose outside JSON, and no Markdown fences. "
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
            max_tokens=GOVERNANCE_MAX_TOKENS,
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
