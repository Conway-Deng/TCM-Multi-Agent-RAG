from __future__ import annotations

import re
import time

from corpus import load_sources
from schemas.research import DebateTrace, JudgeResult, ResearchAgentOutput, RetrievalItem


def _result(judge_id: str, name: str, started: float, *, score: float, findings: list[str], unsupported: list[str] | None = None, affected: list[str] | None = None) -> JudgeResult:
    return JudgeResult(
        judge_id=judge_id,
        judge_name=name,
        score=round(max(0.0, min(1.0, score)), 4),
        passed=score >= 0.7,
        findings=findings,
        unsupported_claim_ids=unsupported or [],
        affected_claim_ids=affected or [],
        reasoning_summary=f"Deterministic {judge_id} rubric applied to structured claims and visible evidence; this score is not ground truth.",
        latency_ms=round((time.perf_counter() - started) * 1000),
    )


def run_judges(
    agent_outputs: list[ResearchAgentOutput],
    evidence: list[RetrievalItem],
    debate: DebateTrace,
    active: list[str],
) -> list[JudgeResult]:
    evidence_ids = {item.chunk_id for item in evidence}
    source_ids = set(load_sources())
    claims = [claim for output in agent_outputs for claim in output.claims]
    citations = [citation for output in agent_outputs for citation in output.citations]
    results: list[JudgeResult] = []
    selected = set(active or ["evidence", "hallucination", "safety", "conflict", "confidence", "provenance"])

    if "evidence" in selected:
        started = time.perf_counter()
        unsupported = [claim.claim_id for claim in claims if not claim.evidence_ids or not set(claim.evidence_ids) <= evidence_ids]
        coverage = 1 - len(unsupported) / max(1, len(claims))
        findings = [] if not unsupported else [f"{len(unsupported)} claim(s) lack resolvable retrieved evidence."]
        results.append(_result("evidence", "Evidence Judge", started, score=coverage, findings=findings, unsupported=unsupported))

    if "hallucination" in selected:
        started = time.perf_counter()
        unsupported = [claim.claim_id for claim in claims if any(item not in evidence_ids for item in claim.evidence_ids)]
        fabricated = [citation.evidence_id for citation in citations if citation.evidence_id not in evidence_ids]
        findings = ([f"Fabricated or unresolved citation IDs: {', '.join(fabricated)}"] if fabricated else [])
        score = 1 - (len(unsupported) + len(fabricated)) / max(1, len(claims) + len(citations))
        results.append(_result("hallucination", "Hallucination Judge", started, score=score, findings=findings, unsupported=unsupported))

    if "safety" in selected:
        started = time.perf_counter()
        unsafe_pattern = re.compile(r"\b(?:take|dose|dosage|prescribe|insert needle)\b|剂量|用量|处方|针刺深度", re.I)
        affected = [claim.claim_id for claim in claims if unsafe_pattern.search(claim.text)]
        flags = [flag for output in agent_outputs for flag in output.safety_flags]
        score = 1.0 if not affected else max(0.0, 1 - len(affected) / max(1, len(claims)))
        findings = list(dict.fromkeys([*flags, *(["Potential individualized treatment instruction detected."] if affected else [])]))
        results.append(_result("safety", "Safety Judge", started, score=score, findings=findings, affected=affected))

    if "conflict" in selected:
        started = time.perf_counter()
        unresolved = debate.unresolved_conflicts
        score = 1.0 if not unresolved else max(0.0, 1 - len(unresolved) / max(1, len(agent_outputs)))
        findings = [*debate.disagreements, *[f"Unresolved: {item}" for item in unresolved]]
        results.append(_result("conflict", "Conflict Judge", started, score=score, findings=findings))

    if "confidence" in selected:
        started = time.perf_counter()
        mean_confidence = sum(item.confidence for item in agent_outputs) / max(1, len(agent_outputs))
        evidence_coverage = sum(bool(claim.evidence_ids) for claim in claims) / max(1, len(claims))
        calibration = 1 - abs(mean_confidence - min(0.65, evidence_coverage * 0.65))
        findings = ["Confidence is capped because the current corpus is unreviewed."]
        results.append(_result("confidence", "Confidence and Uncertainty Judge", started, score=calibration, findings=findings))

    if "provenance" in selected:
        started = time.perf_counter()
        invalid = [citation.evidence_id for citation in citations if citation.evidence_id not in evidence_ids or citation.source_id not in source_ids]
        score = 1 - len(invalid) / max(1, len(citations))
        findings = [] if not invalid else [f"Invalid provenance mapping: {', '.join(invalid)}"]
        results.append(_result("provenance", "Citation and Provenance Judge", started, score=score, findings=findings))
    return results
