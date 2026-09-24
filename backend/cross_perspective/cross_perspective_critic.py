from __future__ import annotations

import json
from typing import Any

from providers import build_llm_provider
from providers.base import LLMProvider

from .model_calls import StructuredCallResult, StructuredModelCallFailure, call_structured_model
from .schemas import (
    ActivePerspectiveName,
    CRITIC_CANONICAL_STATEMENTS,
    CriticDraft,
    CriticExecutionStatus,
    CriticRelationDraft,
    CrossPerspectiveCritique,
    CrossPerspectiveRelation,
    CrossPerspectiveRelationType,
    PerspectiveAgentAssessment,
    PerspectiveEvidencePacket,
)


CRITIC_MODEL = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
CRITIC_TIMEOUT_SECONDS = 240.0
CRITIC_MAX_TOKENS = 1400
CRITIC_THINKING_BEHAVIOR = "send_false"

CRITIC_STRUCTURAL_TEMPLATE = '''{
  "relations": []
}'''

CRITIC_SYSTEM_PROMPT = (
    "You are a Cross-Perspective Critic for a dual-perspective health QA system comparing TCM (Traditional Chinese Medicine) "
    "and Western biomedical perspectives. "
    "Your purpose is to identify evidence-grounded cross-perspective relations between TCM and Western evidence claims. "
    "Compare the usable claims from each perspective and their local advisory audit signals. "
    "Identify cross-perspective relations of exactly three types: "
    "1. possible_agreement: both perspectives present evidence supporting compatible conclusions on the question. "
    "2. possible_difference_or_conflict: perspectives present differing, divergent, or conflicting conclusions or mechanisms. "
    "3. not_directly_comparable: perspective claims address distinct aspects of the condition/question and cannot be directly equated or contrasted. "
    "Rules: "
    "- Use only the supplied packets and projected advisory signals. Do not use outside medical knowledge. "
    "- You MUST cite exact claim IDs from the supplied evidence packets. "
    "- Every relation MUST cite at least one TCM claim ID (tcm_claim_ids) and at least one Western claim ID (western_claim_ids). "
    "- Every relation must remain anchored to usable claim IDs from BOTH perspectives. "
    "- Only claims with support_status != 'insufficient' may be cited in relations. "
    "- For each relation, output ONLY relation_type, tcm_claim_ids, and western_claim_ids. "
    "- Do NOT output or generate a 'statement' field or any prose fields. Python will generate the display statement deterministically. "
    "- relation_type must still reflect the relationship between the cited claim sets. "
    "- relation_type is an advisory semantic judgment, not evidence. "
    "- Similar wording is NOT automatically agreement. "
    "- Different frameworks are NOT automatically conflict. "
    "- Do not force a relation when none is clearly supported. relations may be []. "
    "- Advisory signals are not evidence. A local advisor's agreement or disagreement is not evidence. "
    "- Maximum 4 relations total. If no clear cross-perspective relations exist, return 'relations': []. "
    "- You MUST NOT invent claims, medical facts, mechanisms, citations, or evidence. "
    "- Do not expose chain-of-thought. Return only the required JSON object conforming to the schema. "
    "Do not include markdown codeblocks or prose outside JSON."
)


class CriticValidationError(ValueError):
    """The Critic produced relations violating deterministic grounding or schema rules."""


def build_critic_payload(
    *,
    question: str,
    packets: dict[str, PerspectiveEvidencePacket],
    assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]],
) -> dict[str, Any]:
    """Build compact deterministic payload for the Cross-Perspective Critic.

    Critic evidence packet 'claims' must include ONLY claims where support_status != 'insufficient'.
    Insufficient claims and their text are never exposed to the Critic.
    Downstream advisory safety projection: an issue description may be passed downstream
    ONLY IF:
    1. issue.claim_ids is non-empty AND
    2. EVERY referenced issue claim exists in that perspective packet AND
    3. EVERY referenced issue claim has support_status != "insufficient".
    Otherwise pass ONLY issue_type and claim_ids, omitting description.
    """
    tcm_packet = packets["tcm"]
    western_packet = packets["western"]

    def _project_claims(packet: PerspectiveEvidencePacket) -> list[dict[str, Any]]:
        return [
            {
                "claim_id": c.claim_id,
                "claim_text": c.claim_text,
                "support_status": c.support_status,
                "claim_kind": c.claim_kind,
            }
            for c in packet.claims
            if c.support_status != "insufficient"
        ]

    def _project_assessments(perspective: ActivePerspectiveName) -> list[dict[str, Any]]:
        packet = packets.get(perspective)
        packet_claims = {c.claim_id: c for c in packet.claims} if packet else {}
        result: list[dict[str, Any]] = []
        for a in assessments.get(perspective, []):
            issues_proj: list[dict[str, Any]] = []
            for issue in a.issues:
                is_usable_anchored = (
                    len(issue.claim_ids) > 0
                    and all(cid in packet_claims for cid in issue.claim_ids)
                    and all(packet_claims[cid].support_status != "insufficient" for cid in issue.claim_ids)
                )
                if is_usable_anchored:
                    issues_proj.append({
                        "issue_type": issue.issue_type,
                        "description": issue.description,
                        "claim_ids": list(issue.claim_ids),
                    })
                else:
                    issues_proj.append({
                        "issue_type": issue.issue_type,
                        "claim_ids": list(issue.claim_ids),
                    })
            result.append({
                "role": a.role,
                "referenced_claim_ids": list(a.referenced_claim_ids),
                "issues": issues_proj,
            })
        return result

    return {
        "question": question,
        "evidence_packets": {
            "tcm": {
                "available": tcm_packet.available,
                "execution_status": tcm_packet.execution_status,
                "claims": _project_claims(tcm_packet),
                "uncertainty": list(tcm_packet.uncertainty),
                "missing_information": list(tcm_packet.missing_information),
                "limitations": list(tcm_packet.limitations),
            },
            "western": {
                "available": western_packet.available,
                "execution_status": western_packet.execution_status,
                "claims": _project_claims(western_packet),
                "uncertainty": list(western_packet.uncertainty),
                "missing_information": list(western_packet.missing_information),
                "limitations": list(western_packet.limitations),
            },
        },
        "perspective_assessments": {
            "tcm": _project_assessments("tcm"),
            "western": _project_assessments("western"),
        },
    }


def build_critic_user_prompt(
    *,
    question: str,
    payload: dict[str, Any],
) -> str:
    return (
        f"Question:\n{question}\n\n"
        f"Cross-Perspective Evidence & Local Advisory Input (JSON):\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Return exactly one JSON object with 'relations'.\n"
        f"Structural template:\n{CRITIC_STRUCTURAL_TEMPLATE}\n\n"
        "Relation Object Contract:\n"
        "If a relation exists, every relation MUST be a JSON object with exactly:\n"
        "- relation_type\n"
        "- tcm_claim_ids\n"
        "- western_claim_ids\n\n"
        "Do NOT include a 'statement' field or any prose fields. Python will generate the display statement deterministically.\n\n"
        "relation_type must be exactly one of:\n"
        "- possible_agreement\n"
        "- possible_difference_or_conflict\n"
        "- not_directly_comparable\n\n"
        "tcm_claim_ids:\n"
        "- non-empty JSON array\n"
        "- 1 to 4 items\n"
        "- copy exact IDs from the supplied TCM packet\n\n"
        "western_claim_ids:\n"
        "- non-empty JSON array\n"
        "- 1 to 4 items\n"
        "- copy exact IDs from the supplied Western packet\n\n"
        "Semantic Grounding & Advisory Rules:\n"
        "- relation_type must accurately reflect the semantic relationship between the cited TCM claim IDs and Western claim IDs.\n"
        "- relation_type is an advisory semantic judgment, not evidence.\n"
        "- Do not force a relation when none is clearly supported. relations: [] remains valid.\n"
        "- Maximum 4 relations total. If no clear cross-perspective relations exist, return: {\"relations\": []}\n"
        "- Use usable claims only (support_status != 'insufficient').\n"
        "- Do not cite claims with support_status == 'insufficient'.\n"
        "- Never create, abbreviate, normalize, or rewrite claim IDs.\n"
        "- Do NOT show or use invented claim IDs."
    )


def validate_critic_critique(
    critique: CrossPerspectiveCritique,
    *,
    tcm_packet: PerspectiveEvidencePacket,
    western_packet: PerspectiveEvidencePacket,
) -> None:
    """Validate that a Cross-Perspective Critique strictly references valid non-insufficient claims."""
    if len(critique.relations) > 4:
        raise CriticValidationError("Critique exceeded the maximum allowed 4 relations.")

    tcm_claim_map = {c.claim_id: c for c in tcm_packet.claims}
    western_claim_map = {c.claim_id: c for c in western_packet.claims}

    allowed_relation_types: set[CrossPerspectiveRelationType] = {
        "possible_agreement",
        "possible_difference_or_conflict",
        "not_directly_comparable",
    }

    seen_relations: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()

    for idx, rel in enumerate(critique.relations):
        if rel.relation_type not in allowed_relation_types:
            raise CriticValidationError(
                f"Relation [{idx}] has invalid relation_type {rel.relation_type!r}."
            )
        expected_statement = CRITIC_CANONICAL_STATEMENTS.get(rel.relation_type)
        if rel.statement != expected_statement:
            raise CriticValidationError(
                f"Relation [{idx}] statement is non-canonical. Expected: {expected_statement!r}, got: {rel.statement!r}"
            )

        # TCM claim IDs validation
        if not rel.tcm_claim_ids:
            raise CriticValidationError(f"Relation [{idx}] must contain at least one tcm_claim_id.")
        if len(rel.tcm_claim_ids) > 4:
            raise CriticValidationError(f"Relation [{idx}] exceeds maximum 4 tcm_claim_ids.")
        if len(rel.tcm_claim_ids) != len(set(rel.tcm_claim_ids)):
            raise CriticValidationError(f"Relation [{idx}] contains duplicate tcm_claim_ids.")
        for cid in rel.tcm_claim_ids:
            if cid not in tcm_claim_map:
                raise CriticValidationError(
                    f"Relation [{idx}] references non-existent TCM claim ID {cid!r}."
                )
            if tcm_claim_map[cid].support_status == "insufficient":
                raise CriticValidationError(
                    f"Relation [{idx}] references TCM claim ID {cid!r} with support_status 'insufficient'."
                )

        # Western claim IDs validation
        if not rel.western_claim_ids:
            raise CriticValidationError(f"Relation [{idx}] must contain at least one western_claim_id.")
        if len(rel.western_claim_ids) > 4:
            raise CriticValidationError(f"Relation [{idx}] exceeds maximum 4 western_claim_ids.")
        if len(rel.western_claim_ids) != len(set(rel.western_claim_ids)):
            raise CriticValidationError(f"Relation [{idx}] contains duplicate western_claim_ids.")
        for cid in rel.western_claim_ids:
            if cid not in western_claim_map:
                raise CriticValidationError(
                    f"Relation [{idx}] references non-existent Western claim ID {cid!r}."
                )
            if western_claim_map[cid].support_status == "insufficient":
                raise CriticValidationError(
                    f"Relation [{idx}] references Western claim ID {cid!r} with support_status 'insufficient'."
                )

        # Deduplication check
        rel_key = (
            rel.relation_type,
            tuple(sorted(rel.tcm_claim_ids)),
            tuple(sorted(rel.western_claim_ids)),
        )
        if rel_key in seen_relations:
            raise CriticValidationError(f"Relation [{idx}] is a duplicate of a previous relation.")
        seen_relations.add(rel_key)


def check_critic_preconditions(
    *,
    packets: dict[str, PerspectiveEvidencePacket],
    assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]],
) -> tuple[bool, CriticExecutionStatus]:
    """Check whether Critic execution preconditions are met.

    Returns:
        (is_ready, status)
        - If packets are not available or lack usable claims: (False, "not_applicable")
        - If assessments are missing for either perspective: (False, "skipped_insufficient_assessments")
        - If all preconditions met: (True, "completed")
    """
    tcm_packet = packets.get("tcm")
    western_packet = packets.get("western")

    if not (tcm_packet and tcm_packet.available and western_packet and western_packet.available):
        return False, "not_applicable"

    if (
        tcm_packet.execution_status in {"unavailable", "not_selected"}
        or western_packet.execution_status in {"unavailable", "not_selected"}
    ):
        return False, "not_applicable"

    tcm_usable = sum(1 for c in tcm_packet.claims if c.support_status != "insufficient")
    western_usable = sum(1 for c in western_packet.claims if c.support_status != "insufficient")

    if tcm_usable == 0 or western_usable == 0:
        return False, "not_applicable"

    tcm_assessments = assessments.get("tcm", [])
    western_assessments = assessments.get("western", [])

    if len(tcm_assessments) == 0 or len(western_assessments) == 0:
        return False, "skipped_insufficient_assessments"

    return True, "completed"


class CrossPerspectiveCriticAgent:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or build_llm_provider(
            CRITIC_MODEL,
            timeout_override=CRITIC_TIMEOUT_SECONDS,
            max_tokens_override=CRITIC_MAX_TOKENS,
            thinking_behavior=CRITIC_THINKING_BEHAVIOR,
        )
        self.last_draft: CriticDraft | None = None

    async def critique(
        self,
        *,
        question: str,
        packets: dict[str, PerspectiveEvidencePacket],
        assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]],
    ) -> StructuredCallResult:
        payload = build_critic_payload(
            question=question,
            packets=packets,
            assessments=assessments,
        )
        prompt = build_critic_user_prompt(question=question, payload=payload)
        result = await call_structured_model(
            provider=self.provider,
            role="cross_perspective_critic",
            perspective=None,
            response_model=CriticDraft,
            system=CRITIC_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=CRITIC_MAX_TOKENS,
        )
        draft = result.value
        assert isinstance(draft, CriticDraft)
        self.last_draft = draft

        # Deterministically materialize final CrossPerspectiveCritique with canonical statements
        materialized_relations = [
            CrossPerspectiveRelation(
                relation_type=rel.relation_type,
                statement=CRITIC_CANONICAL_STATEMENTS[rel.relation_type],
                tcm_claim_ids=list(rel.tcm_claim_ids),
                western_claim_ids=list(rel.western_claim_ids),
            )
            for rel in draft.relations
        ]
        critique = CrossPerspectiveCritique(relations=materialized_relations)

        try:
            validate_critic_critique(
                critique,
                tcm_packet=packets["tcm"],
                western_packet=packets["western"],
            )
        except CriticValidationError as exc:
            event = result.events[-1].model_copy(
                update={
                    "success": False,
                    "failure_class": "semantic",
                    "error_summary": f"Critic output failed validation: {exc}",
                }
            )
            raise StructuredModelCallFailure(str(exc), events=[*result.events[:-1], event]) from exc

        return StructuredCallResult(value=critique, events=result.events)
