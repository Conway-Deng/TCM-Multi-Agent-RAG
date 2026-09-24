from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from providers import build_llm_provider
from providers.base import LLMProvider

from .model_calls import StructuredCallResult, StructuredModelCallFailure, call_structured_model
from .schemas import (
    ActivePerspectiveName,
    AgentRole,
    ModelCallEvent,
    PerspectiveAgentAssessment,
    PerspectiveEvidencePacket,
)


EVIDENCE_SPECIALIST_MODEL = "Qwen/Qwen3-8B"
COVERAGE_AUDITOR_MODEL = "THUDM/GLM-4-9B-0414"
GROUNDING_SKEPTIC_MODEL = "THUDM/GLM-Z1-9B-0414"
ADVISORY_MAX_TOKENS = 1024

def build_advisory_structural_template(
    perspective: ActivePerspectiveName,
    role: AgentRole,
) -> str:
    return f'''{{
  "perspective": "{perspective}",
  "role": "{role}",
  "assessment_summary": "Concise summary up to two sentences.",
  "referenced_claim_ids": [],
  "issues": []
}}'''


EVIDENCE_SPECIALIST_SYSTEM_PROMPT = (
    "You are an Evidence Specialist for a single medical evidence perspective. "
    "Your purpose is to identify the strongest and most useful ALREADY-SUPPORTED claims inside the supplied evidence packet. "
    "Identify which supplied claims are most useful for answering the question. "
    "Select only existing claim IDs with support_status != 'insufficient'. "
    "Prefer the smallest sufficient subset of claims. Preserve uncertainty and avoid redundant claim selection. "
    "You MUST NOT invent missing medical facts, add new claims, change support_status, retrieve new evidence, "
    "infer unsupported mechanisms, or treat your own prose as evidence. "
    "PERSPECTIVE-LOCAL BOUNDARY: Evaluate only this perspective packet. Evaluate only the assigned perspective. "
    "Do not evaluate whether the other perspective is present or missing, and do not evaluate whether the other perspective is correct, incorrect, or adequately addressed. "
    "Cross-perspective comparison is outside this role. "
    "If a claim inside the assigned packet contains text about another perspective, that cross-perspective text remains OUT OF SCOPE. "
    "Do not assess whether another perspective is: present, missing, supported, unsupported, correct, incorrect, "
    "adequately addressed, clinically valid, or incomplete. "
    "Do not create an issue whose substantive description evaluates the other perspective. "
    "A cross-perspective sentence appearing inside an assigned packet does NOT authorize cross-perspective analysis. "
    "Cross-perspective comparison belongs only to the Cross-Perspective Critic and Governance. "
    "Return JSON only conforming to the schema. Maximum 2 concise sentences for assessment_summary. Maximum 4 issues."
)

COVERAGE_AUDITOR_SYSTEM_PROMPT = (
    "You are a Coverage Auditor for a single medical evidence perspective. "
    "Your purpose is to inspect whether the available packet contains useful claims that may be overlooked or redundantly represented. "
    "Identify potentially omitted usable claims, visible redundancy, and visible coverage gaps inside the supplied packet. "
    "IMPORTANT: 'coverage gap' means a gap detectable from within the supplied packet, NOT from external medical knowledge. "
    "You MUST NOT use outside medical knowledge to declare missing content or invent missing medical facts. "
    "PERSPECTIVE-LOCAL BOUNDARY: Evaluate only this perspective packet. Evaluate only the assigned perspective. "
    "Do not evaluate whether the other perspective is present or missing, and do not evaluate whether the other perspective is correct, incorrect, or adequately addressed. "
    "Cross-perspective comparison is outside this role. "
    "If a claim inside the assigned packet contains text about another perspective, that cross-perspective text remains OUT OF SCOPE. "
    "Do not assess whether another perspective is: present, missing, supported, unsupported, correct, incorrect, "
    "adequately addressed, clinically valid, or incomplete. "
    "Do not create an issue whose substantive description evaluates the other perspective. "
    "A cross-perspective sentence appearing inside an assigned packet does NOT authorize cross-perspective analysis. "
    "Cross-perspective comparison belongs only to the Cross-Perspective Critic and Governance. "
    "Return JSON only conforming to the schema. Maximum 2 concise sentences for assessment_summary. Maximum 4 issues."
)

GROUNDING_SKEPTIC_SYSTEM_PROMPT = (
    "You are a Grounding Skeptic for a single medical evidence perspective. "
    "Your purpose is to challenge weak or overstated claim-to-evidence relationships. "
    "Inspect claim_text against linked evidence excerpts in provenance to identify overstatement, weak support, "
    "ambiguity, partial support, or uncertainty, and flag insufficient claims where appropriate. "
    "You MUST NOT determine absolute clinical truth, introduce external medical knowledge, replace evidence, "
    "rewrite claims, or invent citations. "
    "PERSPECTIVE-LOCAL BOUNDARY: Evaluate only this perspective packet. Evaluate only the assigned perspective. "
    "Do not evaluate whether the other perspective is present or missing, and do not evaluate whether the other perspective is correct, incorrect, or adequately addressed. "
    "Cross-perspective comparison is outside this role. "
    "If a claim inside the assigned packet contains text about another perspective, that cross-perspective text remains OUT OF SCOPE. "
    "Do not assess whether another perspective is: present, missing, supported, unsupported, correct, incorrect, "
    "adequately addressed, clinically valid, or incomplete. "
    "Do not create an issue whose substantive description evaluates the other perspective. "
    "A cross-perspective sentence appearing inside an assigned packet does NOT authorize cross-perspective analysis. "
    "Cross-perspective comparison belongs only to the Cross-Perspective Critic and Governance. "
    "Return JSON only conforming to the schema. Maximum 2 concise sentences for assessment_summary. Maximum 4 issues."
)

SYSTEM_PROMPTS: dict[AgentRole, str] = {
    "evidence_specialist": EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
    "coverage_auditor": COVERAGE_AUDITOR_SYSTEM_PROMPT,
    "grounding_skeptic": GROUNDING_SKEPTIC_SYSTEM_PROMPT,
}


class PerspectiveAssessmentError(ValueError):
    """The model produced an assessment violating deterministic grounding/schema rules."""


def build_advisory_payload(packet: PerspectiveEvidencePacket) -> dict[str, Any]:
    """Build a deterministic compact projection of ONE existing PerspectiveEvidencePacket."""
    return {
        "perspective": packet.perspective,
        "available": packet.available,
        "execution_status": packet.execution_status,
        "claims": [
            {
                "claim_id": c.claim_id,
                "claim_text": c.claim_text,
                "support_status": c.support_status,
                "claim_kind": c.claim_kind,
                "evidence_refs": [
                    {"source_id": ref.source_id, "chunk_id": ref.chunk_id}
                    for ref in c.evidence_refs
                ],
            }
            for c in packet.claims
        ],
        "provenance": [
            {
                "source_id": p.source_id,
                "chunk_id": p.chunk_id,
                "title": p.title,
                "excerpt": p.excerpt,
            }
            for p in packet.provenance
        ],
        "uncertainty": list(packet.uncertainty),
        "missing_information": list(packet.missing_information),
        "limitations": list(packet.limitations),
    }


def validate_perspective_assessment(
    assessment: PerspectiveAgentAssessment,
    *,
    packet: PerspectiveEvidencePacket,
    expected_role: AgentRole,
) -> None:
    """Validate that an advisory assessment strictly conforms to packet claims and roles."""
    if assessment.perspective != packet.perspective:
        raise PerspectiveAssessmentError(
            f"Assessment perspective {assessment.perspective!r} did not match packet perspective {packet.perspective!r}."
        )
    if assessment.role != expected_role:
        raise PerspectiveAssessmentError(
            f"Assessment role {assessment.role!r} did not match expected role {expected_role!r}."
        )

    packet_claim_map = {c.claim_id: c for c in packet.claims}

    # 3. referenced_claim_ids validation
    if len(assessment.referenced_claim_ids) != len(set(assessment.referenced_claim_ids)):
        raise PerspectiveAssessmentError("referenced_claim_ids must not contain duplicates.")
    for cid in assessment.referenced_claim_ids:
        if cid not in packet_claim_map:
            raise PerspectiveAssessmentError(
                f"referenced_claim_id {cid!r} is not an existing claim in the {packet.perspective} packet."
            )
        if packet_claim_map[cid].support_status == "insufficient":
            raise PerspectiveAssessmentError(
                f"referenced_claim_id {cid!r} has insufficient support_status and cannot be selected as a supported reference."
            )

    # 4. issues validation
    if len(assessment.issues) > 4:
        raise PerspectiveAssessmentError("Assessment exceeded the maximum allowed 4 issues.")
    for issue in assessment.issues:
        if len(issue.claim_ids) != len(set(issue.claim_ids)):
            raise PerspectiveAssessmentError(
                f"Issue claim_ids contains duplicate entries: {issue.claim_ids}"
            )
        for cid in issue.claim_ids:
            if cid not in packet_claim_map:
                raise PerspectiveAssessmentError(
                    f"Issue claim_id {cid!r} is not an existing claim in the {packet.perspective} packet."
                )


def build_advisory_user_prompt(
    *,
    role: AgentRole,
    perspective: ActivePerspectiveName,
    question: str,
    payload: dict[str, Any],
) -> str:
    structural_template = build_advisory_structural_template(
        perspective=perspective,
        role=role,
    )
    return (
        f"Question:\n{question}\n\n"
        f"Perspective: {perspective}\n"
        f"Role: {role}\n\n"
        f"Fixed Evidence Packet (JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "Return exactly one JSON object with: perspective, role, assessment_summary, referenced_claim_ids, and issues.\n"
        f"Structural template:\n{structural_template}\n\n"
        "Claim ID Rules:\n"
        "Any value placed in:\n"
        "- referenced_claim_ids\n"
        "- issues[*].claim_ids\n"
        "must be copied exactly from claim_id values that appear in the supplied packet.\n"
        "Never create, abbreviate, normalize, or rewrite claim IDs.\n\n"
        "Perspective Boundary Rules:\n"
        "- Evaluate only the assigned perspective.\n"
        "- If a claim inside the assigned packet contains text about another perspective, that cross-perspective text remains OUT OF SCOPE.\n"
        "- Do not assess whether another perspective is present, missing, supported, unsupported, correct, incorrect, adequately addressed, clinically valid, or incomplete.\n"
        "- Do not create an issue whose substantive description evaluates the other perspective.\n\n"
        "Issues Format Rules:\n"
        'The "issues" field MUST be a JSON array. Maximum 4 issues.\n'
        'If there are no issues: "issues": []\n'
        "If issues exist, EVERY element MUST be a JSON object with EXACTLY:\n"
        "{\n"
        '  "issue_type": "...",\n'
        '  "description": "...",\n'
        '  "claim_ids": []\n'
        "}\n\n"
        "issue_type MUST be exactly one of:\n"
        "- coverage_gap\n"
        "- grounding_risk\n"
        "- support_ambiguity\n"
        "- redundancy\n"
        "- uncertainty\n"
        "- other\n\n"
        "description:\n"
        "- non-empty concise string\n\n"
        "claim_ids:\n"
        "- JSON array of exact claim IDs copied from the supplied packet\n"
        "- use [] if the issue is not tied to a specific supplied claim\n"
        "- never put free-form text in claim_ids\n"
        "- never invent a claim ID\n\n"
        "Do NOT return issues as plain strings.\n"
        "Invalid:\n"
        '"issues": [\n'
        '  "Some coverage concern."\n'
        "]\n\n"
        "Valid:\n"
        '"issues": [\n'
        "  {\n"
        '    "issue_type": "coverage_gap",\n'
        '    "description": "Some supplied evidence is not represented by a usable claim.",\n'
        '    "claim_ids": []\n'
        "  }\n"
        "]"
    )



@dataclass(frozen=True)
class AdvisoryRunResult:
    assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]]
    events: list[ModelCallEvent]
    latency_by_role: dict[str, float]
    failed_roles: list[str]


class PerspectiveAdvisorySuite:
    def __init__(
        self,
        *,
        evidence_specialist_provider: LLMProvider | None = None,
        coverage_auditor_provider: LLMProvider | None = None,
        grounding_skeptic_provider: LLMProvider | None = None,
        providers: dict[AgentRole, LLMProvider] | None = None,
    ) -> None:
        self.providers: dict[AgentRole, LLMProvider] = {
            "evidence_specialist": evidence_specialist_provider
            or build_llm_provider(EVIDENCE_SPECIALIST_MODEL, thinking_behavior="send_false"),
            "coverage_auditor": coverage_auditor_provider
            or build_llm_provider(COVERAGE_AUDITOR_MODEL, thinking_behavior="omit"),
            "grounding_skeptic": grounding_skeptic_provider
            or build_llm_provider(GROUNDING_SKEPTIC_MODEL, thinking_behavior="send_false"),
        }
        if providers:
            self.providers.update(providers)

    async def _run_role(
        self,
        *,
        role: AgentRole,
        perspective: ActivePerspectiveName,
        packet: PerspectiveEvidencePacket,
        question: str,
    ) -> tuple[PerspectiveAgentAssessment | None, list[ModelCallEvent], float, str | None]:
        system_prompt = SYSTEM_PROMPTS[role]
        payload = build_advisory_payload(packet)
        prompt = build_advisory_user_prompt(
            role=role,
            perspective=perspective,
            question=question,
            payload=payload,
        )
        provider = self.providers[role]
        started = perf_counter()
        try:
            call_result = await call_structured_model(
                provider=provider,
                role=role,
                perspective=perspective,
                response_model=PerspectiveAgentAssessment,
                system=system_prompt,
                prompt=prompt,
                max_tokens=ADVISORY_MAX_TOKENS,
            )
            assessment = call_result.value
            assert isinstance(assessment, PerspectiveAgentAssessment)
            validate_perspective_assessment(assessment, packet=packet, expected_role=role)
            latency_ms = round((perf_counter() - started) * 1000, 3)
            return assessment, call_result.events, latency_ms, None
        except Exception as exc:
            latency_ms = round((perf_counter() - started) * 1000, 3)
            failed_role = f"{perspective}:{role}"
            if isinstance(exc, StructuredModelCallFailure):
                return None, exc.events, latency_ms, failed_role
            if isinstance(exc, PerspectiveAssessmentError):
                failed_events: list[ModelCallEvent] = []
                if "call_result" in locals() and call_result.events:
                    for i, ev in enumerate(call_result.events):
                        if i == len(call_result.events) - 1:
                            failed_events.append(
                                ev.model_copy(
                                    update={
                                        "success": False,
                                        "failure_class": "semantic",
                                        "error_summary": str(exc),
                                    }
                                )
                            )
                        else:
                            failed_events.append(ev)
                else:
                    failed_events.append(
                        ModelCallEvent(
                            role=role,
                            attempt=1,
                            provider=provider.name,
                            requested_model=provider.model,
                            success=False,
                            latency_ms=latency_ms,
                            failure_class="semantic",
                            error_summary=str(exc),
                            perspective=perspective,
                        )
                    )
                return None, failed_events, latency_ms, failed_role
            failed_events = [
                ModelCallEvent(
                    role=role,
                    attempt=1,
                    provider=provider.name,
                    requested_model=provider.model,
                    success=False,
                    latency_ms=latency_ms,
                    failure_class="unexpected",
                    error_summary=str(exc),
                    perspective=perspective,
                )
            ]
            return None, failed_events, latency_ms, failed_role

    async def analyze(
        self,
        question: str,
        packets: dict[ActivePerspectiveName, PerspectiveEvidencePacket],
    ) -> AdvisoryRunResult:
        tasks = []
        task_descriptors: list[tuple[ActivePerspectiveName, AgentRole]] = []
        for perspective in ("tcm", "western"):
            packet = packets.get(perspective)
            if packet is None:
                continue
            if packet.execution_status == "not_selected" or not packet.available:
                continue
            if len(packet.claims) == 0:
                continue
            for role in ("evidence_specialist", "coverage_auditor", "grounding_skeptic"):
                tasks.append(
                    self._run_role(
                        role=role,
                        perspective=perspective,
                        packet=packet,
                        question=question,
                    )
                )
                task_descriptors.append((perspective, role))

        assessments: dict[ActivePerspectiveName, list[PerspectiveAgentAssessment]] = {
            "tcm": [],
            "western": [],
        }
        events: list[ModelCallEvent] = []
        latency_by_role: dict[str, float] = {}
        failed_roles: list[str] = []

        if not tasks:
            return AdvisoryRunResult(
                assessments=assessments,
                events=events,
                latency_by_role=latency_by_role,
                failed_roles=failed_roles,
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (perspective, role), res in zip(task_descriptors, results, strict=True):
            role_key = f"{perspective}:{role}"
            if isinstance(res, BaseException):
                failed_roles.append(role_key)
                latency_by_role[role_key] = 0.0
                events.append(
                    ModelCallEvent(
                        role=role,
                        attempt=1,
                        provider=self.providers[role].name,
                        requested_model=self.providers[role].model,
                        success=False,
                        latency_ms=0.0,
                        failure_class="unexpected",
                        error_summary=str(res),
                        perspective=perspective,
                    )
                )
                continue
            assessment, role_events, latency_ms, failed_role = res
            events.extend(role_events)
            latency_by_role[role_key] = latency_ms
            if assessment is not None:
                assessments[perspective].append(assessment)
            if failed_role is not None:
                failed_roles.append(failed_role)

        return AdvisoryRunResult(
            assessments=assessments,
            events=events,
            latency_by_role=latency_by_role,
            failed_roles=failed_roles,
        )
