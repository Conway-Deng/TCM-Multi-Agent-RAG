from __future__ import annotations

import json
from typing import Any

ROLE_INSTRUCTIONS = {
    "domain_evidence_specialist": "Answer the question directly using only supplied evidence; preserve entity boundaries and source uncertainty.",
    "coverage_auditor": "Independently answer while prioritizing complete coverage of every source-recorded attribute requested by the question.",
    "grounding_skeptic": "Independently answer while challenging unsupported inference and retaining only claims grounded in supplied evidence.",
}

INITIAL_SYSTEM = "You are a source-grounded TCM research debate agent. Use only supplied evidence. Do not diagnose, prescribe, add outside knowledge, or expose hidden reasoning. Return exactly one JSON object with answer (string), evidence_ids (string array), and uncertainties (string array)."
CRITIQUE_SYSTEM = "Critique one visible peer answer using only supplied evidence. Return exactly one JSON object with target_seat (string), disagreements (string array), missing_evidence_concerns (string array), grounding_concerns (string array), and source_ids (string array)."
REVISION_SYSTEM = "Revise your visible answer using only supplied evidence and peer critiques. Return exactly one JSON object with revised_answer (string), evidence_ids (string array), critique_uptake (string array), and changes_made (string array)."
CONSENSUS_SYSTEM = "Produce a concise evidence-grounded consensus from revised positions. Use no outside knowledge. Return strict JSON with answer and evidence_ids."

COMMON_STRUCTURED_OUTPUT_SUFFIX = " Return exactly one JSON object. Do not use a markdown code fence. Do not place prose before or after the JSON. Include exactly the required fields and no additional fields."

INITIAL_SYSTEM += COMMON_STRUCTURED_OUTPUT_SUFFIX
CRITIQUE_SYSTEM += COMMON_STRUCTURED_OUTPUT_SUFFIX
REVISION_SYSTEM += COMMON_STRUCTURED_OUTPUT_SUFFIX
CONSENSUS_SYSTEM += COMMON_STRUCTURED_OUTPUT_SUFFIX

def initial_payload(role: str, question: str, evidence: list[dict[str, str]]) -> dict[str, Any]:
    return {"role_instruction": ROLE_INSTRUCTIONS[role], "question": question, "evidence": evidence}

def canonical_prompt_bundle() -> str:
    return json.dumps({"roles": ROLE_INSTRUCTIONS, "initial": INITIAL_SYSTEM, "critique": CRITIQUE_SYSTEM, "revision": REVISION_SYSTEM, "consensus": CONSENSUS_SYSTEM}, sort_keys=True, separators=(",", ":"))
