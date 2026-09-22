from __future__ import annotations

import json

from providers import build_llm_provider
from providers.base import LLMProvider

from .model_calls import StructuredCallResult, StructuredModelCallFailure, call_structured_model
from .schemas import (
    CrossPerspectiveAnswer,
    CrossPerspectiveDraft,
    EvidenceReference,
    OVERALL_NO_CLAIM_SUMMARY,
    PerspectiveClaim,
    PerspectiveEvidencePacket,
    SourceMapEntry,
    TCM_NO_CLAIM_SUMMARY,
    TCM_UNAVAILABLE_SUMMARY,
    WESTERN_NO_CLAIM_SUMMARY,
    WESTERN_UNAVAILABLE_SUMMARY,
)


GOVERNANCE_MODEL = "XingChenAGI/Xing4.0-29B"
GOVERNANCE_TIMEOUT_SECONDS = 90.0
GOVERNANCE_MAX_TOKENS = 2400
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
  "uncertainty": []
}'''
GOVERNANCE_SYSTEM_PROMPT = (
    "You are the governance and synthesis component of a development-only cross-perspective health QA prototype. "
    "Use only the supplied evidence packets. Never introduce substantive medical claims absent from those packets. "
    "Keep TCM traditional-framework interpretations distinct from Western biomedical interpretations; never imply that their mechanisms are equivalent. "
    "Agreement between perspectives is not proof. Preserve disagreement, insufficient evidence, uncertainty, missing information, and unavailable perspectives. "
    "The packet interpretation field is presentation text, not evidence. Only non-insufficient claims with linked provenance may support substantive final statements. "
    "Insufficient claims cannot support agreements or substantive statements. "
    "Overall summaries, perspective summaries, agreements, and differences must cite the exact non-insufficient claim IDs that support them. "
    "Deterministic status statements when no usable claim exists or a perspective is unavailable: "
    f'TCM unavailable: "{TCM_UNAVAILABLE_SUMMARY}"; '
    f'Western unavailable: "{WESTERN_UNAVAILABLE_SUMMARY}"; '
    f'TCM available but no usable claim: "{TCM_NO_CLAIM_SUMMARY}"; '
    f'Western available but no usable claim: "{WESTERN_NO_CLAIM_SUMMARY}"; '
    f'overall answer without usable claims: "{OVERALL_NO_CLAIM_SUMMARY}". '
    "Return exactly one JSON object with these seven top-level keys and no others: overall_summary, overall_supporting_claim_ids, perspectives, agreements, differences_or_conflicts, evidence_gaps, uncertainty. "
    "TCM and Western must never appear as top-level keys; they may appear only as perspectives.tcm and perspectives.western. "
    "Output minified JSON: no indentation, no pretty printing, no Markdown, and no prose outside JSON. "
    "Compactness rules: "
    "overall_summary: maximum 2 concise sentences. "
    "perspectives.tcm.summary: maximum 2 concise sentences. "
    "perspectives.western.summary: maximum 2 concise sentences. "
    "agreements: include only clearly evidence-supported agreements, maximum 2 entries, use [] if none are necessary. "
    "differences_or_conflicts: include only clearly evidence-supported differences/conflicts, maximum 2 entries, use [] if none are necessary. "
    "evidence_gaps: maximum 3 items, each item one short sentence. "
    "uncertainty: maximum 3 items, each item one short sentence. "
    "Supported claim IDs: use the smallest sufficient subset of usable claim IDs; do not enumerate every usable claim merely because it exists. "
    "Never invent claim IDs or citations, and never upgrade possible or partial support into certainty. "
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


def build_deterministic_source_map(
    draft: CrossPerspectiveDraft,
    packets: dict[str, PerspectiveEvidencePacket],
) -> list[SourceMapEntry]:
    claims_by_perspective = {
        name: {claim.claim_id: claim for claim in packet.claims}
        for name, packet in packets.items()
    }
    all_claim_ids = {
        claim_id
        for perspective_claims in claims_by_perspective.values()
        for claim_id in perspective_claims
    }
    if len(all_claim_ids) != sum(len(items) for items in claims_by_perspective.values()):
        raise GovernanceContractError("claim IDs must be unique across perspectives")

    claim_to_perspective: dict[str, str] = {}
    claim_by_id: dict[str, PerspectiveClaim] = {}
    for name, p_claims in claims_by_perspective.items():
        for claim_id, claim in p_claims.items():
            claim_to_perspective[claim_id] = name
            claim_by_id[claim_id] = claim

    usable_by_perspective = {
        name: {
            claim_id
            for claim_id, claim in perspective_claims.items()
            if packets[name].available and claim.support_status != "insufficient"
        }
        for name, perspective_claims in claims_by_perspective.items()
    }

    def collect_refs(claim_ids: list[str]) -> list[EvidenceReference]:
        seen_pairs: set[tuple[str, str]] = set()
        refs: list[EvidenceReference] = []
        for cid in claim_ids:
            claim = claim_by_id[cid]
            for ref in claim.evidence_refs:
                pair = (ref.source_id, ref.chunk_id)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    refs.append(EvidenceReference(source_id=ref.source_id, chunk_id=ref.chunk_id))
        if not refs:
            raise GovernanceContractError(f"no evidence references found for claims: {claim_ids}")
        return refs

    entries: list[SourceMapEntry] = []

    # 1. Overall summary
    overall_ids = draft.overall_supporting_claim_ids
    if len(overall_ids) != len(set(overall_ids)):
        raise GovernanceContractError("overall supporting claim IDs must be unique")
    for cid in overall_ids:
        if cid not in claim_by_id:
            raise GovernanceContractError(f"overall summary references unknown claim ID: {cid}")
        p = claim_to_perspective[cid]
        if cid not in usable_by_perspective.get(p, set()):
            raise GovernanceContractError(f"overall summary references insufficient or unavailable claim: {cid}")

    for p in ("tcm", "western"):
        p_ids = [cid for cid in overall_ids if claim_to_perspective[cid] == p]
        if p_ids:
            entries.append(
                SourceMapEntry(
                    final_claim_or_statement=draft.overall_summary,
                    perspective=p,
                    claim_ids=p_ids,
                    evidence_refs=collect_refs(p_ids),
                )
            )

    # 2. Perspective summaries
    for p in ("tcm", "western"):
        summary = getattr(draft.perspectives, p)
        if summary.supported_claim_ids:
            p_ids = list(summary.supported_claim_ids)
            if len(p_ids) != len(set(p_ids)):
                raise GovernanceContractError(f"{p} summary supported claim IDs must be unique")
            for cid in p_ids:
                if cid not in claim_by_id:
                    raise GovernanceContractError(f"unknown {p} claim ID: {cid}")
                if claim_to_perspective[cid] != p:
                    raise GovernanceContractError(f"wrong-perspective claim ID in {p} summary: {cid}")
                if cid not in usable_by_perspective.get(p, set()):
                    raise GovernanceContractError(f"insufficient or unavailable claim listed as supported: {cid}")
            entries.append(
                SourceMapEntry(
                    final_claim_or_statement=summary.summary,
                    perspective=p,
                    claim_ids=p_ids,
                    evidence_refs=collect_refs(p_ids),
                )
            )

    # 3. Agreements
    for agreement in draft.agreements:
        if not agreement.supporting_claim_ids:
            raise GovernanceContractError("agreement must declare supporting claim IDs")
        if len(agreement.supporting_claim_ids) != len(set(agreement.supporting_claim_ids)):
            raise GovernanceContractError("agreement claim IDs must be unique")
        for cid in agreement.supporting_claim_ids:
            if cid not in claim_by_id:
                raise GovernanceContractError(f"agreement references an unknown claim ID: {cid}")
            p = claim_to_perspective[cid]
            if cid not in usable_by_perspective.get(p, set()):
                raise GovernanceContractError(f"agreement cannot use an insufficient claim: {cid}")
        tcm_ids = [cid for cid in agreement.supporting_claim_ids if claim_to_perspective[cid] == "tcm"]
        western_ids = [cid for cid in agreement.supporting_claim_ids if claim_to_perspective[cid] == "western"]
        if not tcm_ids or not western_ids:
            raise GovernanceContractError("agreement must be supported by both perspectives")
        entries.append(
            SourceMapEntry(
                final_claim_or_statement=agreement.statement,
                perspective="tcm",
                claim_ids=tcm_ids,
                evidence_refs=collect_refs(tcm_ids),
            )
        )
        entries.append(
            SourceMapEntry(
                final_claim_or_statement=agreement.statement,
                perspective="western",
                claim_ids=western_ids,
                evidence_refs=collect_refs(western_ids),
            )
        )

    # 4. Differences / conflicts
    for difference in draft.differences_or_conflicts:
        if not difference.tcm_claim_ids or not difference.western_claim_ids:
            raise GovernanceContractError("difference/conflict must name claims from both perspectives")
        if len(difference.tcm_claim_ids) != len(set(difference.tcm_claim_ids)):
            raise GovernanceContractError("difference TCM claim IDs must be unique")
        if len(difference.western_claim_ids) != len(set(difference.western_claim_ids)):
            raise GovernanceContractError("difference Western claim IDs must be unique")
        for cid in difference.tcm_claim_ids:
            if cid not in claim_by_id:
                raise GovernanceContractError(f"difference references an unknown TCM claim ID: {cid}")
            if claim_to_perspective[cid] != "tcm":
                raise GovernanceContractError(f"wrong-perspective claim ID in difference TCM claim IDs: {cid}")
            if cid not in usable_by_perspective.get("tcm", set()):
                raise GovernanceContractError(f"difference cannot use an insufficient TCM claim: {cid}")
        for cid in difference.western_claim_ids:
            if cid not in claim_by_id:
                raise GovernanceContractError(f"difference references an unknown Western claim ID: {cid}")
            if claim_to_perspective[cid] != "western":
                raise GovernanceContractError(f"wrong-perspective claim ID in difference Western claim IDs: {cid}")
            if cid not in usable_by_perspective.get("western", set()):
                raise GovernanceContractError(f"difference cannot use an insufficient Western claim: {cid}")
        entries.append(
            SourceMapEntry(
                final_claim_or_statement=difference.statement,
                perspective="tcm",
                claim_ids=list(difference.tcm_claim_ids),
                evidence_refs=collect_refs(difference.tcm_claim_ids),
            )
        )
        entries.append(
            SourceMapEntry(
                final_claim_or_statement=difference.statement,
                perspective="western",
                claim_ids=list(difference.western_claim_ids),
                evidence_refs=collect_refs(difference.western_claim_ids),
            )
        )

    return entries


class CrossPerspectiveGovernanceAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or build_llm_provider(
            GOVERNANCE_MODEL,
            timeout_override=GOVERNANCE_TIMEOUT_SECONDS,
            max_tokens_override=GOVERNANCE_MAX_TOKENS,
            thinking_behavior="omit",
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
            "overall_supporting_claim_ids must be non-empty whenever any usable claim exists. "
            "Deterministic status statements when no usable claim exists or a perspective is unavailable: "
            f'TCM unavailable: "{TCM_UNAVAILABLE_SUMMARY}"; '
            f'Western unavailable: "{WESTERN_UNAVAILABLE_SUMMARY}"; '
            f'TCM available but no usable claim: "{TCM_NO_CLAIM_SUMMARY}"; '
            f'Western available but no usable claim: "{WESTERN_NO_CLAIM_SUMMARY}"; '
            f'overall answer without usable claims: "{OVERALL_NO_CLAIM_SUMMARY}". '
            "Emit exactly these seven top-level keys: overall_summary, overall_supporting_claim_ids, perspectives, agreements, differences_or_conflicts, evidence_gaps, uncertainty. "
            "Never emit tcm or western at the top level; nest them only under perspectives. "
            "Output minified JSON: no indentation, no pretty printing, no Markdown, and no prose outside JSON. "
            "Compactness rules: "
            "overall_summary: maximum 2 concise sentences. "
            "perspectives.tcm.summary: maximum 2 concise sentences. "
            "perspectives.western.summary: maximum 2 concise sentences. "
            "agreements: include only clearly evidence-supported agreements, maximum 2 entries, use [] if none are necessary. "
            "differences_or_conflicts: include only clearly evidence-supported differences/conflicts, maximum 2 entries, use [] if none are necessary. "
            "evidence_gaps: maximum 3 items, each item one short sentence. "
            "uncertainty: maximum 3 items, each item one short sentence. "
            "Supported claim IDs: use the smallest sufficient subset of usable claim IDs; do not enumerate every usable claim merely because it exists. "
            "Structural template (shape only; replace placeholders with exact supplied IDs and preserve required empty lists when no entries apply):\n"
            f"{GOVERNANCE_STRUCTURAL_TEMPLATE}\n"
            "Return the CrossPerspectiveDraft JSON contract. Every supported_claim_id must exist in the supplied packets. "
            "Both tcm and western perspective summaries are required; mark unavailable perspectives unavailable and do not reconstruct them."
        )
        result = await call_structured_model(
            provider=self.provider,
            role="governance",
            response_model=CrossPerspectiveDraft,
            system=GOVERNANCE_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=GOVERNANCE_MAX_TOKENS,
        )
        draft = result.value
        assert isinstance(draft, CrossPerspectiveDraft)
        try:
            source_map = build_deterministic_source_map(draft, packets)
            answer = CrossPerspectiveAnswer(
                overall_summary=draft.overall_summary,
                overall_supporting_claim_ids=draft.overall_supporting_claim_ids,
                perspectives=draft.perspectives,
                agreements=draft.agreements,
                differences_or_conflicts=draft.differences_or_conflicts,
                evidence_gaps=draft.evidence_gaps,
                uncertainty=draft.uncertainty,
                source_map=source_map,
            )
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
        return StructuredCallResult(value=answer, events=result.events)
