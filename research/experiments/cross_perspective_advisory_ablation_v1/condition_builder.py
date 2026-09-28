import json
import sys
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from backend.cross_perspective.governance import (
        GOVERNANCE_STRUCTURAL_TEMPLATE,
        GOVERNANCE_SYSTEM_PROMPT,
        build_governance_advisory_context,
        build_governance_payload,
    )
    from backend.cross_perspective.schemas import (
        ActivePerspectiveName,
        CrossPerspectiveCritique,
        PerspectiveAgentAssessment,
        PerspectiveEvidencePacket,
        OVERALL_NO_CLAIM_SUMMARY,
        TCM_NO_CLAIM_SUMMARY,
        TCM_UNAVAILABLE_SUMMARY,
        WESTERN_NO_CLAIM_SUMMARY,
        WESTERN_UNAVAILABLE_SUMMARY,
    )
except ModuleNotFoundError:
    from cross_perspective.governance import (
        GOVERNANCE_STRUCTURAL_TEMPLATE,
        GOVERNANCE_SYSTEM_PROMPT,
        build_governance_advisory_context,
        build_governance_payload,
    )
    from cross_perspective.schemas import (
        ActivePerspectiveName,
        CrossPerspectiveCritique,
        PerspectiveAgentAssessment,
        PerspectiveEvidencePacket,
        OVERALL_NO_CLAIM_SUMMARY,
        TCM_NO_CLAIM_SUMMARY,
        TCM_UNAVAILABLE_SUMMARY,
        WESTERN_NO_CLAIM_SUMMARY,
        WESTERN_UNAVAILABLE_SUMMARY,
    )

from .schemas import ConditionName



def build_governance_advisory_for_condition(
    condition: ConditionName,
    *,
    assessments: Mapping[ActivePerspectiveName, list[PerspectiveAgentAssessment]] | None = None,
    critique: CrossPerspectiveCritique | None = None,
    packets: Mapping[str, PerspectiveEvidencePacket] | None = None,
) -> dict[str, Any]:
    """Construct the exact Section B advisory context visible to Governance for a condition.

    Matrix:
    - G0: NO local-advisory (assessments={}), NO Critic (critique=None)
    - G1: FROZEN local-advisory, NO Critic (critique=None)
    - G2: NO local-advisory (assessments={}), FROZEN Critic
    - G3: FROZEN local-advisory, FROZEN Critic

    This function relies exclusively on the frozen Patch 3 build_governance_advisory_context.
    """
    if condition == "G0":
        visible_assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]] = {}
        visible_critique: CrossPerspectiveCritique | None = None
    elif condition == "G1":
        visible_assessments = dict(assessments or {})
        visible_critique = None
    elif condition == "G2":
        visible_assessments = {}
        visible_critique = critique
    elif condition == "G3":
        visible_assessments = dict(assessments or {})
        visible_critique = critique
    else:
        raise ValueError(f"Unknown condition: {condition}")

    return build_governance_advisory_context(
        visible_assessments,
        visible_critique,
        packets=packets,
    )


def build_governance_visible_payload(
    condition: ConditionName,
    *,
    packets: dict[str, PerspectiveEvidencePacket],
    assessments: Mapping[ActivePerspectiveName, list[PerspectiveAgentAssessment]] | None = None,
    critique: CrossPerspectiveCritique | None = None,
) -> dict[str, Any]:
    """Build the complete Governance input payload (Section A + Section B) for a condition.

    - Section A (Primary Evidence): built via frozen Patch 3 build_governance_payload
    - Section B (Advisory Context): built via build_governance_advisory_for_condition
    """
    section_a = build_governance_payload(packets)
    section_b = build_governance_advisory_for_condition(
        condition,
        assessments=assessments,
        critique=critique,
        packets=packets,
    )
    return {
        "perspective_packets": section_a,
        "advisory_context": section_b,
    }


def build_governance_prompt_for_condition(
    question: str,
    condition: ConditionName,
    *,
    packets: dict[str, PerspectiveEvidencePacket],
    assessments: Mapping[ActivePerspectiveName, list[PerspectiveAgentAssessment]] | None = None,
    critique: CrossPerspectiveCritique | None = None,
) -> str:
    """Build the exact Governance user prompt for a condition.

    CRITICAL RULES:
    1. The prompt template text is 100% invariant across G0, G1, G2, G3.
    2. Only the serialized contents of Section B change based on advisory visibility.
    3. The condition label ('G0', 'G1', 'G2', 'G3') must NEVER appear in the prompt.
    4. Matches frozen Patch 3 CrossPerspectiveGovernanceAgent.synthesize user prompt contract.
    """
    payload = build_governance_visible_payload(
        condition,
        packets=packets,
        assessments=assessments,
        critique=critique,
    )
    packet_payload = payload["perspective_packets"]
    advisory_context = payload["advisory_context"]

    prompt = (
        f"Original question:\n{question}\n\n"
        f"=== SECTION A: EVIDENCE PACKETS (PRIMARY EVIDENCE) ===\n"
        f"{json.dumps(packet_payload, ensure_ascii=False, sort_keys=True)}\n\n"
        f"=== SECTION B: ADVISORY CONTEXT (CONTROLLED ADVISORY SIGNALS ONLY - NOT EVIDENCE) ===\n"
        f"{json.dumps(advisory_context, ensure_ascii=False, sort_keys=True)}\n\n"
        "The packet interpretation field is not evidence and is intentionally omitted from this payload. "
        "Claims were pre-associated with provenance by the evidence pathways. "
        'A "usable claim" is defined structurally as a supplied packet claim with support_status != "insufficient". '
        'Only claims with support_status != "insufficient" may support substantive synthesis. '
        "Claims with support_status == 'insufficient': "
        "cannot support substantive synthesis, cannot be copied or paraphrased as substantive evidence, "
        "must not be used to introduce content about another perspective, and must not be used indirectly through advisory context to support a final statement. "
        "Insufficient claims must not be copied, paraphrased, or used to supply content to overall_summary, perspective summaries, agreements, differences/conflicts, evidence_gaps, or uncertainty. "
        "Limited direct relevance, limited applicability, uncertainty, coverage gaps, or weak case-specific fit do NOT make a usable claim disappear or become unusable. "
        "Advisory signals in Section B are attention guides, NOT evidence, and cannot be cited in supported_claim_ids. "
        "Advisory context cannot remove, invalidate, downgrade, or upgrade a packet claim. "
        "Advisory context cannot upgrade a packet claim's support_status. "
        'Advisory issue_type="coverage_gap" does NOT redefine packet claims as unusable. '
        "If advisory guidance conflicts with packet evidence, packet evidence wins. "
        "Agreement between advisory agents is not evidence. Critic statements are not evidence. "
        "The Critic canonical statement contains no substantive evidence content. "
        "Use relation_type and cited IDs only as advisory navigation. "
        "Any substantive difference/conflict wording in final Governance output must be derived independently from Section A packet claims. "
        "Do not copy the canonical statement as evidence. Do not infer medical content from it. "
        "Missing advisory roles must not be hallucinated or reconstructed. Critic absence or failure must be tolerated. "
        "Final substantive statements must still resolve to usable Section A claim IDs. "
        "Citation and source-map materialization is handled deterministically outside the model. "
        "The Judge must reference exact supplied claim IDs from Section A and must not invent evidence, claims, or outside medical knowledge. "
        "overall_supporting_claim_ids must be non-empty whenever any usable claim exists. "
        "Every substantive evidence statement in overall_summary must be supported by the smallest sufficient subset of exact usable Section A claim IDs. "
        "If overall_summary describes substantive evidence from BOTH TCM and Western perspectives, overall_supporting_claim_ids must include the needed claim IDs from BOTH perspectives. "
        "Operational rules for each perspective summary (perspectives.tcm and perspectives.western): "
        "IF >=1 usable packet claim exists for that perspective: "
        "1. Perspective status remains available (available: true). "
        "2. Summarize only what the packet evidence actually discusses or supports. "
        "3. If the summary mentions substantive packet content, supported_claim_ids MUST cite the smallest sufficient subset of those exact usable claim IDs. "
        "4. If direct case relevance is weak, indirect, or limited, say so in the summary, evidence_gaps, or uncertainty. "
        "5. DO NOT leave supported_claim_ids empty merely because direct relevance is limited. "
        "IF literally zero usable packet claims exist (zero claims with support_status != \"insufficient\"): "
        "1. Use the deterministic no-claim status statement. "
        "2. supported_claim_ids must be []. "
        "Differences/Conflicts Format Rules: "
        "Every element in differences_or_conflicts MUST be a JSON object matching the DifferenceOrConflict schema: "
        '{"statement": "...", "tcm_claim_ids": ["exact TCM claim IDs"], "western_claim_ids": ["exact Western claim IDs"]}. '
        'Do NOT output ["relation_type", "statement"] or any list/tuple format. '
        "Do NOT copy the Critic relation object directly. The Critic schema and Governance DifferenceOrConflict schema are DIFFERENT contracts. "
        "Critic relation_type is advisory metadata. Governance must not place relation_type inside differences_or_conflicts unless the existing Governance schema already contains such a field. "
        "If advisory Critic output is useful, Governance must independently express a properly evidence-supported DifferenceOrConflict object using the Governance schema. "
        "If no packet-grounded difference/conflict is necessary, return []. "
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
        "Rules for evidence_gaps and uncertainty: "
        "Every evidence_gaps and uncertainty item must be grounded only in usable Section A claims, packet.missing_information, packet.limitations, and packet.uncertainty. "
        "For evidence_gaps: describe WHAT is missing; do not erase information that is already present; do not contradict overall_summary, perspectives.tcm.summary, or perspectives.western.summary. "
        "For uncertainty: describe WHY confidence/applicability is limited; do not restate available evidence as absent; do not contradict the summaries. "
        "Do not convert 'evidence is educational / indirect / incomplete' into 'the perspective provides no information / no insight' when usable claims exist. "
        "Distinguish explicitly between: (1) no evidence exists, and (2) evidence exists but is insufficient for clinical or case-specific confirmation. "
        "If a perspective has usable claims describing case-related evidence, do NOT say 'no insight', 'no information', or 'no evidence is provided' unless the packet literally supports that absence. "
        "evidence_gaps: maximum 3 items, each item one short sentence. "
        "uncertainty: maximum 3 items, each item one short sentence. "
        "Supported claim IDs: use the smallest sufficient subset of usable claim IDs from Section A; do not enumerate every usable claim merely because it exists. "
        "Structural template (shape only; replace placeholders with exact supplied IDs and preserve required empty lists when no entries apply):\n"
        f"{GOVERNANCE_STRUCTURAL_TEMPLATE}\n"
        "Return the CrossPerspectiveDraft JSON contract. Every supported_claim_id must exist in Section A evidence packets. "
        "Both tcm and western perspective summaries are required; mark unavailable perspectives unavailable and do not reconstruct them."
    )

    # Hard safety check: ensure no condition label leaked into the prompt
    for c_label in ("G0", "G1", "G2", "G3"):
        # We check word boundary or clear appearance
        if f"Condition {c_label}" in prompt or f"condition {c_label}" in prompt:
            raise RuntimeError(f"Condition leakage detected in prompt: {c_label}")

    return prompt
