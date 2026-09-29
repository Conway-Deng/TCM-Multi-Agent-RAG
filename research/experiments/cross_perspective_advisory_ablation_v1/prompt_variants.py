from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Final

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.cross_perspective.cross_perspective_critic import CRITIC_SYSTEM_PROMPT
from backend.cross_perspective.governance import GOVERNANCE_SYSTEM_PROMPT
from backend.cross_perspective.perspective_agents import (
    COVERAGE_AUDITOR_SYSTEM_PROMPT,
    EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
    GROUNDING_SKEPTIC_SYSTEM_PROMPT,
)

# Shared Research Source-Passage Clarification (enacted exactly once across all 5 roles)
SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT: Final[str] = (
    'RESEARCH SOURCE-PASSAGE CONTRACT: Entries with claim_kind="source_excerpt" are verbatim '
    'source-passage containers and may contain multiple propositions. Their claim_id identifies a '
    'passage occurrence, not an atomic semantic claim. For these entries, legacy support_status="supported" '
    'means only that the passage was faithfully copied from and linked to the supplied frozen evidence. '
    'It does not mean that every proposition was semantically verified, that any generated statement is '
    'entailed, that the passage is clinically correct, or that human grounding review occurred. '
    '"Usable" means structurally eligible for consideration, not relevant or semantically certified. '
    'Assess what the passage actually supports for the assigned task; do not treat its status or citation '
    'presence as independent entailment certification. Retain the existing exact-ID rules and do not change packet statuses.'
)


def _build_evidence_specialist_prompt() -> str:
    opening = "You are an Evidence Specialist for a single medical evidence perspective."
    if not EVIDENCE_SPECIALIST_SYSTEM_PROMPT.startswith(opening):
        raise AssertionError("Baseline Evidence Specialist prompt wording has drifted from expected opening.")
    
    target_old = "Your purpose is to identify the strongest and most useful ALREADY-SUPPORTED claims inside the supplied evidence packet."
    target_new = "Your purpose is to identify the strongest and most useful structurally eligible source-passage entries inside the supplied evidence packet."
    
    if EVIDENCE_SPECIALIST_SYSTEM_PROMPT.count(target_old) != 1:
        raise AssertionError(f"Expected target sentence exactly once in Evidence Specialist prompt, found {EVIDENCE_SPECIALIST_SYSTEM_PROMPT.count(target_old)}.")
    
    tail = EVIDENCE_SPECIALIST_SYSTEM_PROMPT[len(opening):].lstrip()
    if not tail.startswith(target_old):
        raise AssertionError("Expected target sentence immediately following opening in Evidence Specialist prompt.")
    
    tail_amended = target_new + tail[len(target_old):]
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail_amended}"
    return amended


def _build_coverage_auditor_prompt() -> str:
    opening = "You are a Coverage Auditor for a single medical evidence perspective."
    if not COVERAGE_AUDITOR_SYSTEM_PROMPT.startswith(opening):
        raise AssertionError("Baseline Coverage Auditor prompt wording has drifted from expected opening.")
    
    tail = COVERAGE_AUDITOR_SYSTEM_PROMPT[len(opening):].lstrip()
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail}"
    return amended


def _build_grounding_skeptic_prompt() -> str:
    opening = "You are a Grounding Skeptic for a single medical evidence perspective."
    if not GROUNDING_SKEPTIC_SYSTEM_PROMPT.startswith(opening):
        raise AssertionError("Baseline Grounding Skeptic prompt wording has drifted from expected opening.")
    
    target_old = "Inspect claim_text against linked evidence excerpts in provenance to identify overstatement, weak support, ambiguity, partial support, or uncertainty, and flag insufficient claims where appropriate."
    target_new = "Inspect the supplied source passages and linked provenance to identify overstatement risks, limits of support, ambiguity, or uncertainty relevant to the question. Identical claim_text and provenance excerpt establish faithful copying only, not semantic support for an inferred answer. Report concerns through the existing advisory schema; do not rewrite passages or change packet statuses."
    
    if GROUNDING_SKEPTIC_SYSTEM_PROMPT.count(target_old) != 1:
        raise AssertionError(f"Expected target sentence exactly once in Grounding Skeptic prompt, found {GROUNDING_SKEPTIC_SYSTEM_PROMPT.count(target_old)}.")
    
    tail = GROUNDING_SKEPTIC_SYSTEM_PROMPT[len(opening):].lstrip()
    if target_old not in tail:
        raise AssertionError("Target sentence not found in Grounding Skeptic prompt tail.")
    
    tail_amended = tail.replace(target_old, target_new, 1)
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail_amended}"
    return amended


def _build_critic_prompt() -> str:
    opening = "You are a Cross-Perspective Critic for a dual-perspective health QA system comparing TCM (Traditional Chinese Medicine) and Western biomedical perspectives."
    if not CRITIC_SYSTEM_PROMPT.startswith(opening):
        raise AssertionError("Baseline Critic prompt wording has drifted from expected opening.")
    
    tail = CRITIC_SYSTEM_PROMPT[len(opening):].lstrip()
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail}"
    return amended


def _build_governance_prompt() -> str:
    opening = "You are the governance and synthesis component of a development-only cross-perspective health QA prototype."
    if not GOVERNANCE_SYSTEM_PROMPT.startswith(opening):
        raise AssertionError("Baseline Governance prompt wording has drifted from expected opening.")
    
    tail = GOVERNANCE_SYSTEM_PROMPT[len(opening):].lstrip()
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail}"
    return amended


# Research Prompt Constants
CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT: Final[str] = _build_evidence_specialist_prompt()
CPAA1_COVERAGE_AUDITOR_SYSTEM_PROMPT: Final[str] = _build_coverage_auditor_prompt()
CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT: Final[str] = _build_grounding_skeptic_prompt()
CPAA1_CRITIC_SYSTEM_PROMPT: Final[str] = _build_critic_prompt()
CPAA1_GOVERNANCE_SYSTEM_PROMPT: Final[str] = _build_governance_prompt()

RESEARCH_SYSTEM_PROMPTS: Final[dict[str, str]] = {
    "evidence_specialist": CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
    "coverage_auditor": CPAA1_COVERAGE_AUDITOR_SYSTEM_PROMPT,
    "grounding_skeptic": CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT,
    "critic": CPAA1_CRITIC_SYSTEM_PROMPT,
    "governance": CPAA1_GOVERNANCE_SYSTEM_PROMPT,
}


def sha256_prompt(prompt_text: str) -> str:
    """Compute exact SHA256 over runtime prompt UTF-8 bytes without whitespace normalization."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
