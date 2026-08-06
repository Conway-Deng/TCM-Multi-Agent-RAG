from __future__ import annotations

import re

from ..schemas import AgentOutput, EvidenceJudgeResult


def _tokens(text: str) -> set[str]:
    latin = re.findall(r"[a-z][a-z-]{2,}", text.casefold())
    cjk = re.findall(r"[\u3400-\u9fff\uac00-\ud7af]", text)
    return set(latin + cjk)


def judge_evidence(agents: list[AgentOutput]) -> EvidenceJudgeResult:
    evidence_by_id = {item.evidence_id: item for agent in agents for item in agent.evidence}
    supported: list[str] = []
    partial: list[str] = []
    unsupported: list[str] = []
    issues: list[str] = []
    considered = 0
    for agent in agents:
        for claim in agent.claims:
            if claim.claim_type in {"abstention_reason", "evidence_limitation", "safety_guidance"}:
                continue
            considered += 1
            cited = [evidence_by_id[item] for item in claim.evidence_ids if item in evidence_by_id]
            missing_ids = [item for item in claim.evidence_ids if item not in evidence_by_id]
            if missing_ids:
                issues.append(f"{claim.claim_id}: missing evidence IDs {', '.join(missing_ids)}")
            if not cited:
                unsupported.append(claim.claim_id)
                continue
            claim_tokens = _tokens(claim.text)
            evidence_tokens = _tokens(" ".join(f"{item.title} {item.snippet}" for item in cited))
            overlap = len(claim_tokens & evidence_tokens) / max(1, min(len(claim_tokens), 12))
            if overlap >= 0.16:
                supported.append(claim.claim_id)
            elif overlap > 0:
                partial.append(claim.claim_id)
                issues.append(f"{claim.claim_id}: cited text has weak semantic overlap")
            else:
                unsupported.append(claim.claim_id)
                issues.append(f"{claim.claim_id}: cited text does not support the claim wording")
    coverage = (len(supported) + 0.5 * len(partial)) / considered if considered else 0.0
    return EvidenceJudgeResult(
        supported_claim_ids=supported,
        partially_supported_claim_ids=partial,
        unsupported_claim_ids=unsupported,
        citation_issues=issues,
        evidence_coverage_score=round(coverage, 3),
        reasoning_summary=(
            "Claims were checked against cited evidence text using a deterministic lexical-semantic overlap baseline; "
            "this is an orchestration metric, not clinical verification."
        ),
    )
