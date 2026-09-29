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

# Frozen baseline prompt hashes from prompt_amendment_map_v1.json
EXPECTED_ORIGINAL_PROMPT_HASHES: Final[dict[str, str]] = {
    "evidence_specialist": "0b659434568f2975843f5e338f42e81ec908d389557136621b113d17b44a0d75",
    "coverage_auditor": "ffb22307033e910752e90f9d325372e611802a9a682efb3748e2f2919efedba1",
    "grounding_skeptic": "8e45e6c37b9013e89a9146515e08cc863f5939daf9ba5c68ccb7c8ca7a98e0e7",
    "critic": "9cdf6f9cf157e1da37aa7b28d489af83fbc355e1b46aa761d01d297808835c36",
    "governance": "50bccba1fe344e971a50d5f1382262eb152bbb58bab051d34a46f69231807702",
}

# Frozen amended prompt hashes from prompt_amendment_map_v1.json
EXPECTED_AMENDED_PROMPT_HASHES: Final[dict[str, str]] = {
    "evidence_specialist": "ccfb2380a86f0a1a23873858a26d33e0a2b3c1b0949576151b2f6704dbe0126f",
    "coverage_auditor": "3ec8bb8be6ce3deb0f586b01c533566e9c859137e1da0e8cd46788fc5108c6ed",
    "grounding_skeptic": "79e58a4e11ff8bb0c7d2e15ae27363c0f94a51ff7dcd0f4df1711418162beffa",
    "critic": "251f1590e17f4d5301946e11f597a83e29d3aef713b00f193bd2f90f3f674edb",
    "governance": "154a394ce48e4d17d308149da01a721eef21e3f02c2c10f5fe749d803772f6f9",
}


def sha256_prompt(prompt_text: str) -> str:
    """Compute exact SHA256 over runtime prompt UTF-8 bytes without whitespace normalization."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def verify_baseline_prompt_hash(role: str, prompt_text: str) -> None:
    """Fail-closed guard: verify exact SHA256 match for production baseline prompt before any amendment."""
    expected = EXPECTED_ORIGINAL_PROMPT_HASHES.get(role)
    if not expected:
        raise ValueError(f"Unknown prompt role: {role}")
    actual = sha256_prompt(prompt_text)
    if actual != expected:
        raise AssertionError(
            f"Baseline prompt hash mismatch for {role}! Baseline has drifted: actual {actual} != expected {expected}"
        )


def build_evidence_specialist_prompt(base_prompt: str = EVIDENCE_SPECIALIST_SYSTEM_PROMPT) -> str:
    verify_baseline_prompt_hash("evidence_specialist", base_prompt)
    opening = "You are an Evidence Specialist for a single medical evidence perspective."
    if not base_prompt.startswith(opening):
        raise AssertionError("Baseline Evidence Specialist prompt wording has drifted from expected opening.")
    
    target_old = "Your purpose is to identify the strongest and most useful ALREADY-SUPPORTED claims inside the supplied evidence packet."
    target_new = "Your purpose is to identify the strongest and most useful structurally eligible source-passage entries inside the supplied evidence packet."
    
    if base_prompt.count(target_old) != 1:
        raise AssertionError(f"Expected target sentence exactly once in Evidence Specialist prompt, found {base_prompt.count(target_old)}.")
    
    tail = base_prompt[len(opening):].lstrip()
    if not tail.startswith(target_old):
        raise AssertionError("Expected target sentence immediately following opening in Evidence Specialist prompt.")
    
    tail_amended = target_new + tail[len(target_old):]
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail_amended}"
    return amended


def build_coverage_auditor_prompt(base_prompt: str = COVERAGE_AUDITOR_SYSTEM_PROMPT) -> str:
    verify_baseline_prompt_hash("coverage_auditor", base_prompt)
    opening = "You are a Coverage Auditor for a single medical evidence perspective."
    if not base_prompt.startswith(opening):
        raise AssertionError("Baseline Coverage Auditor prompt wording has drifted from expected opening.")
    
    tail = base_prompt[len(opening):].lstrip()
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail}"
    return amended


def build_grounding_skeptic_prompt(base_prompt: str = GROUNDING_SKEPTIC_SYSTEM_PROMPT) -> str:
    verify_baseline_prompt_hash("grounding_skeptic", base_prompt)
    opening = "You are a Grounding Skeptic for a single medical evidence perspective."
    if not base_prompt.startswith(opening):
        raise AssertionError("Baseline Grounding Skeptic prompt wording has drifted from expected opening.")
    
    target_old = "Inspect claim_text against linked evidence excerpts in provenance to identify overstatement, weak support, ambiguity, partial support, or uncertainty, and flag insufficient claims where appropriate."
    target_new = "Inspect the supplied source passages and linked provenance to identify overstatement risks, limits of support, ambiguity, or uncertainty relevant to the question. Identical claim_text and provenance excerpt establish faithful copying only, not semantic support for an inferred answer. Report concerns through the existing advisory schema; do not rewrite passages or change packet statuses."
    
    if base_prompt.count(target_old) != 1:
        raise AssertionError(f"Expected target sentence exactly once in Grounding Skeptic prompt, found {base_prompt.count(target_old)}.")
    
    tail = base_prompt[len(opening):].lstrip()
    if target_old not in tail:
        raise AssertionError("Target sentence not found in Grounding Skeptic prompt tail.")
    
    tail_amended = tail.replace(target_old, target_new, 1)
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail_amended}"
    return amended


def build_critic_prompt(base_prompt: str = CRITIC_SYSTEM_PROMPT) -> str:
    verify_baseline_prompt_hash("critic", base_prompt)
    opening = "You are a Cross-Perspective Critic for a dual-perspective health QA system comparing TCM (Traditional Chinese Medicine) and Western biomedical perspectives."
    if not base_prompt.startswith(opening):
        raise AssertionError("Baseline Critic prompt wording has drifted from expected opening.")
    
    tail = base_prompt[len(opening):].lstrip()
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail}"
    return amended


def build_governance_prompt(base_prompt: str = GOVERNANCE_SYSTEM_PROMPT) -> str:
    verify_baseline_prompt_hash("governance", base_prompt)
    opening = "You are the governance and synthesis component of a development-only cross-perspective health QA prototype."
    if not base_prompt.startswith(opening):
        raise AssertionError("Baseline Governance prompt wording has drifted from expected opening.")
    
    tail = base_prompt[len(opening):].lstrip()
    amended = f"{opening} {SHARED_RESEARCH_SOURCE_PASSAGE_CONTRACT} {tail}"
    return amended


# Research Prompt Constants
CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT: Final[str] = build_evidence_specialist_prompt()
CPAA1_COVERAGE_AUDITOR_SYSTEM_PROMPT: Final[str] = build_coverage_auditor_prompt()
CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT: Final[str] = build_grounding_skeptic_prompt()
CPAA1_CRITIC_SYSTEM_PROMPT: Final[str] = build_critic_prompt()
CPAA1_GOVERNANCE_SYSTEM_PROMPT: Final[str] = build_governance_prompt()

RESEARCH_SYSTEM_PROMPTS: Final[dict[str, str]] = {
    "evidence_specialist": CPAA1_EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
    "coverage_auditor": CPAA1_COVERAGE_AUDITOR_SYSTEM_PROMPT,
    "grounding_skeptic": CPAA1_GROUNDING_SKEPTIC_SYSTEM_PROMPT,
    "critic": CPAA1_CRITIC_SYSTEM_PROMPT,
    "governance": CPAA1_GOVERNANCE_SYSTEM_PROMPT,
}

# Post-construction validation: verify all amended prompt hashes match expected frozen values
for _role, _prompt_text in RESEARCH_SYSTEM_PROMPTS.items():
    _actual_hash = sha256_prompt(_prompt_text)
    _expected_hash = EXPECTED_AMENDED_PROMPT_HASHES[_role]
    if _actual_hash != _expected_hash:
        raise AssertionError(
            f"Amended prompt hash mismatch for {_role}: actual {_actual_hash} != expected {_expected_hash}"
        )
