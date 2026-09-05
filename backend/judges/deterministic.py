from __future__ import annotations

from dataclasses import dataclass
import re
import time

from corpus import load_sources
from schemas.research import (
    ConfidenceSignalContribution,
    ConfidenceSignalPenalty,
    ConflictStatus,
    DebateTrace,
    EvidenceConfidenceSummary,
    EvidenceSupportSummary,
    EvidenceSupportedCautionAssessment,
    JudgeResult,
    ResearchAgentOutput,
    RetrievalItem,
    SourceGroundedSafetyFinding,
)


_TREATMENT = re.compile(r"\b(?:herb|formula|treatment|remedy|acupuncture)\b|中药|方剂|治疗|针灸", re.IGNORECASE)
_CERTAINTY = re.compile(r"\b(?:guarantee(?:d|s)?|definitely|certainly|will cure|cures?)\b|保证|必然|一定(?:能|会)|根治", re.IGNORECASE)
_ABSOLUTE = re.compile(r"\b(?:always|never|completely safe|no side effects?|risk[- ]free)\b|绝对安全|无副作用|永远|从不", re.IGNORECASE)
_DOSAGE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:mg|g|ml|tablets?|capsules?|drops?)\b|"
    r"\b(?:take|use|consume|administer)\b.{0,24}\b(?:daily|twice|three times|before bed)\b|"
    r"(?:服用|使用|煎服).{0,16}(?:每日|每天|每次|一次|两次|三次|克|毫升|粒))",
    re.IGNORECASE,
)
_DIAGNOSIS = re.compile(
    r"\b(?:you (?:definitely )?have|this confirms?|confirmed diagnosis|is diagnostic of)\b|"
    r"(?:你|您)(?:就是|患有)|确诊(?:为)?|可以诊断为",
    re.IGNORECASE,
)
_CAUTION_MARKER = re.compile(
    r"\b(?:caution|warning|contraindicat|toxic|toxicity|pregnan|interaction|avoid|do not use)\w*\b|"
    r"注意|警告|禁忌|毒性|有毒|孕妇|相互作用|慎用|忌用",
    re.IGNORECASE,
)
_RESOLUTION_CERTAINTY = re.compile(
    r"\b(?:therefore|clearly|conclusively|the correct (?:answer|view)|settles? the conflict)\b|"
    r"因此可以确定|显然|唯一正确|冲突已经解决",
    re.IGNORECASE,
)
_UNCERTAINTY = re.compile(
    r"\b(?:uncertain|unresolved|conflicting|may|might|cannot determine|insufficient)\b|"
    r"不确定|尚未解决|证据冲突|可能|无法确定|证据不足",
    re.IGNORECASE,
)

_POSITIVE_WEIGHTS = {
    "evidence_coverage": 0.35,
    "citation_coverage": 0.20,
    "retrieval_sufficiency": 0.25,
    "verified_evidence_ratio": 0.10,
    "agent_agreement_score": 0.10,
}


@dataclass(frozen=True)
class IntegratedJudgeBundle:
    judge_outputs: list[JudgeResult]
    evidence_support: EvidenceSupportSummary
    safety_assessment: EvidenceSupportedCautionAssessment
    conflict_status: ConflictStatus
    evidence_confidence: EvidenceConfidenceSummary


def _result(
    judge_id: str,
    name: str,
    started: float,
    *,
    score: float,
    findings: list[str],
    unsupported: list[str] | None = None,
    affected: list[str] | None = None,
    version: str = "1.0.0",
) -> JudgeResult:
    return JudgeResult(
        judge_id=judge_id,
        judge_name=name,
        judge_version=version,
        score=round(max(0.0, min(1.0, score)), 4),
        passed=score >= 0.7,
        findings=findings,
        unsupported_claim_ids=unsupported or [],
        affected_claim_ids=affected or [],
        reasoning_summary=f"Deterministic {judge_id} rubric applied to structured claims and visible evidence.",
        latency_ms=round((time.perf_counter() - started) * 1000),
    )


def _retrieval_signal(item: RetrievalItem) -> float:
    for value in (item.rerank_score, item.semantic_score, item.lexical_score):
        if value is not None and value > 0:
            return max(0.0, min(1.0, float(value)))
    return 0.0


def _evidence_support(
    agent_outputs: list[ResearchAgentOutput],
    evidence: list[RetrievalItem],
) -> EvidenceSupportSummary:
    evidence_ids = {item.chunk_id for item in evidence}
    evidence_by_id = {item.chunk_id: item for item in evidence}
    claims = [(output, claim) for output in agent_outputs for claim in output.claims]
    supported: list[str] = []
    unsupported: list[str] = []
    missing_citations: list[str] = []
    cited_claim_count = 0
    used_ids: set[str] = set()

    for output, claim in claims:
        claim_ids = set(claim.evidence_ids)
        resolvable = bool(claim_ids) and claim_ids <= evidence_ids
        if resolvable:
            supported.append(claim.claim_id)
            used_ids.update(claim_ids)
        else:
            unsupported.append(claim.claim_id)
        output_citation_ids = {citation.evidence_id for citation in output.citations}
        missing = claim_ids - output_citation_ids
        missing.update(claim_ids - evidence_ids)
        missing_citations.extend(f"{claim.claim_id}:{item}" for item in sorted(missing))
        if resolvable and claim_ids <= output_citation_ids:
            cited_claim_count += 1

    eligible = len(claims)
    coverage = len(supported) / max(1, eligible)
    citation_coverage = cited_claim_count / max(1, eligible)
    used_evidence = [evidence_by_id[item] for item in used_ids if item in evidence_by_id]
    retrieval_sufficiency = (
        sum(_retrieval_signal(item) for item in used_evidence) / len(used_evidence)
        if used_evidence else 0.0
    )
    verified = sum(
        str(item.source_metadata.get("review_status") or item.source_metadata.get("verification_status") or "").casefold() == "verified"
        for item in used_evidence
    )
    verified_ratio = verified / len(used_evidence) if used_evidence else 0.0
    return EvidenceSupportSummary(
        eligible_claim_count=eligible,
        supported_claim_ids=supported,
        partially_supported_claim_ids=[],
        unsupported_claim_ids=unsupported,
        missing_citation_ids=list(dict.fromkeys(missing_citations)),
        evidence_coverage=round(coverage, 4),
        citation_coverage=round(citation_coverage, 4),
        retrieval_sufficiency=round(retrieval_sufficiency, 4),
        verified_evidence_ratio=round(verified_ratio, 4),
    )


def _conflict_status(agent_outputs: list[ResearchAgentOutput], debate: DebateTrace) -> tuple[ConflictStatus, float]:
    active_count = sum(not output.abstained for output in agent_outputs)
    conflict_score = min(1.0, len(debate.unresolved_conflicts) / max(1, len(agent_outputs)))
    agreement_score = (
        min(1.0, len(debate.agreements) / max(1, active_count - 1))
        if active_count >= 2 else 0.0
    )
    return ConflictStatus(
        has_unresolved_conflict=bool(debate.unresolved_conflicts),
        conflict_score=round(conflict_score, 4),
        agreements=list(debate.agreements),
        disagreements=list(debate.disagreements),
        unresolved_conflicts=list(debate.unresolved_conflicts),
    ), round(agreement_score, 4)


def _structured_cautions(item: RetrievalItem) -> list[str]:
    value = item.source_metadata.get("cautions") or item.source_metadata.get("safety_tags") or []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(entry) for entry in value if str(entry).strip()]
    return []


def _safety_assessment(
    agent_outputs: list[ResearchAgentOutput],
    evidence: list[RetrievalItem],
    evidence_support: EvidenceSupportSummary,
    conflict_status: ConflictStatus,
    response_text: str,
) -> EvidenceSupportedCautionAssessment:
    claims = [claim for output in agent_outputs for claim in output.claims]
    if not claims and not response_text.strip():
        return EvidenceSupportedCautionAssessment()

    findings: list[SourceGroundedSafetyFinding] = []
    evidence_by_id = {item.chunk_id: item for item in evidence}
    unsupported_ids = set(evidence_support.unsupported_claim_ids) | set(evidence_support.partially_supported_claim_ids)

    def add(code: str, severity: str, rule_id: str, explanation: str, *, claim_ids=None, evidence_ids=None) -> None:
        findings.append(SourceGroundedSafetyFinding(
            code=code,
            severity=severity,
            rule_id=rule_id,
            explanation=explanation,
            claim_ids=claim_ids or [],
            evidence_ids=evidence_ids or [],
        ))

    for claim in claims:
        cited = [evidence_by_id[item] for item in claim.evidence_ids if item in evidence_by_id]
        cited_text = " ".join(item.chunk_text for item in cited)
        unsupported = claim.claim_id in unsupported_ids or not cited_text
        if unsupported and _TREATMENT.search(claim.text) and _CERTAINTY.search(claim.text):
            add(
                "unsupported_treatment_certainty", "high", "SJ-01",
                "Treatment certainty is asserted without full support from the supplied evidence.",
                claim_ids=[claim.claim_id], evidence_ids=claim.evidence_ids,
            )
        if _ABSOLUTE.search(claim.text) and not _ABSOLUTE.search(cited_text):
            add(
                "absolute_medical_claim", "high", "SJ-02",
                "Absolute wording is not present in the cited evidence.",
                claim_ids=[claim.claim_id], evidence_ids=claim.evidence_ids,
            )
        if _DOSAGE.search(claim.text) and not _DOSAGE.search(cited_text):
            add(
                "unsupported_dosage_or_use", "high", "SJ-03",
                "A dosage or use instruction is not reproduced from the cited evidence.",
                claim_ids=[claim.claim_id], evidence_ids=claim.evidence_ids,
            )
        if _DIAGNOSIS.search(claim.text) and unsupported:
            add(
                "unsupported_diagnostic_certainty", "high", "SJ-06",
                "Diagnostic certainty is asserted for a claim that is not fully evidence-supported.",
                claim_ids=[claim.claim_id], evidence_ids=claim.evidence_ids,
            )

    cited_ids = {item for claim in claims for item in claim.evidence_ids}
    preserved_cautions = [flag for output in agent_outputs for flag in output.safety_flags]
    preserved = " ".join([response_text, *preserved_cautions])
    for item in evidence:
        if item.chunk_id not in cited_ids:
            continue
        cautions = _structured_cautions(item) or [match.group(0) for match in _CAUTION_MARKER.finditer(item.chunk_text)]
        if cautions and not _CAUTION_MARKER.search(preserved) and not any(
            caution.casefold() in preserved.casefold() for caution in cautions
        ):
            add(
                "source_caution_not_preserved", "high", "SJ-04",
                "Cited evidence contains a caution signal absent from the response and preserved caution fields.",
                evidence_ids=[item.chunk_id],
            )

    if (
        conflict_status.unresolved_conflicts
        and _RESOLUTION_CERTAINTY.search(response_text)
        and not _UNCERTAINTY.search(response_text)
    ):
        add(
            "conflict_overresolution", "medium", "SJ-05",
            "The response uses resolution language while structured conflicts remain unresolved.",
        )

    severity_weights = {"high": 0.30, "medium": 0.16, "low": 0.08}
    penalty = min(1.0, sum(severity_weights[item.severity] for item in findings))
    return EvidenceSupportedCautionAssessment(
        assessment="flags_detected" if findings else "no_flags_detected",
        source_grounded_safety_score=round(1.0 - penalty, 4),
        findings=findings,
    )


def _contribution(name: str, value: float) -> ConfidenceSignalContribution:
    weight = _POSITIVE_WEIGHTS[name]
    return ConfidenceSignalContribution(
        signal=name,
        observed_value=round(value, 4),
        weight=weight,
        contribution=round(value * weight, 4),
    )


def _penalty(name: str, value: float, maximum: float) -> ConfidenceSignalPenalty:
    return ConfidenceSignalPenalty(
        signal=name,
        observed_value=round(value, 4),
        maximum_penalty=maximum,
        applied_penalty=round(value * maximum, 4),
    )


def _evidence_confidence(
    evidence_support: EvidenceSupportSummary,
    conflict_status: ConflictStatus,
    agreement_score: float,
    safety: EvidenceSupportedCautionAssessment,
    *,
    active_agent_count: int,
    abstained_agent_count: int,
    model_failure_count: int,
) -> EvidenceConfidenceSummary:
    unsupported_rate = min(
        1.0,
        len(set(evidence_support.unsupported_claim_ids)) / max(1, evidence_support.eligible_claim_count),
    )
    abstention_rate = abstained_agent_count / max(1, active_agent_count)
    model_failure_rate = min(1.0, model_failure_count / max(1, active_agent_count))
    contributions = [
        _contribution("evidence_coverage", evidence_support.evidence_coverage),
        _contribution("citation_coverage", evidence_support.citation_coverage),
        _contribution("retrieval_sufficiency", evidence_support.retrieval_sufficiency),
        _contribution("verified_evidence_ratio", evidence_support.verified_evidence_ratio),
        _contribution("agent_agreement_score", agreement_score),
    ]
    penalties = [
        _penalty("unsupported_claim_rate", unsupported_rate, 0.30),
        _penalty("unresolved_conflict", conflict_status.conflict_score, 0.18),
        _penalty("agent_abstention", abstention_rate, 0.10),
        _penalty("model_failure", model_failure_rate, 0.07),
    ]
    high_count = sum(item.severity == "high" for item in safety.findings)
    medium_count = sum(item.severity == "medium" for item in safety.findings)
    safety_signal = min(1.0, high_count * 0.50 + medium_count * 0.25)
    penalties.append(_penalty("source_grounded_safety_flags", safety_signal, 0.25))

    score = sum(item.contribution for item in contributions) - sum(item.applied_penalty for item in penalties)
    score = min(score, 0.90)
    caps: list[str] = []
    if evidence_support.eligible_claim_count == 0:
        score = 0.0
        caps.append("no eligible claims: score set to 0")
    if unsupported_rate > 0:
        score = min(score, 0.69)
        caps.append("unsupported claims present: capped at 0.69")
    if evidence_support.retrieval_sufficiency < 0.40:
        score = min(score, 0.49)
        caps.append("retrieval/evidence sufficiency below 0.40: capped at 0.49")
    if conflict_status.unresolved_conflicts and conflict_status.conflict_score >= 0.50:
        score = min(score, 0.59)
        caps.append("material unresolved conflict: capped at 0.59")
    if high_count:
        score = min(score, 0.39)
        caps.append("high source-grounded safety flag present: capped at 0.39")
    score = round(max(0.0, score), 4)
    band = "strong" if score >= 0.75 else "moderate" if score >= 0.55 else "limited" if score >= 0.30 else "insufficient"
    weak = [item.signal for item in contributions if item.observed_value < 0.50]
    if unsupported_rate:
        weak.append("unsupported claims")
    if conflict_status.unresolved_conflicts:
        weak.append("unresolved conflict")
    return EvidenceConfidenceSummary(
        score=score,
        band=band,
        signal_contributions=contributions,
        penalties=penalties,
        caps_applied=caps,
        missing_or_weak_signals=list(dict.fromkeys(weak)),
    )


def run_integrated_judges(
    agent_outputs: list[ResearchAgentOutput],
    evidence: list[RetrievalItem],
    debate: DebateTrace,
    active: list[str],
    *,
    response_text: str,
    model_failure_count: int = 0,
) -> IntegratedJudgeBundle:
    evidence_ids = {item.chunk_id for item in evidence}
    source_ids = set(load_sources())
    claims = [claim for output in agent_outputs for claim in output.claims]
    citations = [citation for output in agent_outputs for citation in output.citations]
    selected = set(active or ["evidence", "hallucination", "safety", "conflict", "confidence", "provenance"])

    evidence_support = _evidence_support(agent_outputs, evidence)
    conflict_status, agreement_score = _conflict_status(agent_outputs, debate)
    safety = _safety_assessment(agent_outputs, evidence, evidence_support, conflict_status, response_text)
    confidence = _evidence_confidence(
        evidence_support,
        conflict_status,
        agreement_score,
        safety,
        active_agent_count=len(agent_outputs),
        abstained_agent_count=sum(output.abstained for output in agent_outputs),
        model_failure_count=model_failure_count,
    )

    results: list[JudgeResult] = []
    if "evidence" in selected:
        started = time.perf_counter()
        findings = [] if not evidence_support.unsupported_claim_ids else [
            f"{len(evidence_support.unsupported_claim_ids)} claim(s) lack resolvable retrieved evidence."
        ]
        results.append(_result(
            "evidence", "Evidence Judge", started,
            score=evidence_support.evidence_coverage,
            findings=findings,
            unsupported=evidence_support.unsupported_claim_ids,
        ))
    if "hallucination" in selected:
        started = time.perf_counter()
        fabricated = [citation.evidence_id for citation in citations if citation.evidence_id not in evidence_ids]
        unsupported = [claim.claim_id for claim in claims if any(item not in evidence_ids for item in claim.evidence_ids)]
        findings = [f"Fabricated or unresolved citation IDs: {', '.join(fabricated)}"] if fabricated else []
        score = 1 - (len(unsupported) + len(fabricated)) / max(1, len(claims) + len(citations))
        results.append(_result("hallucination", "Hallucination Judge", started, score=score, findings=findings, unsupported=unsupported))
    if "safety" in selected:
        started = time.perf_counter()
        inherited = [flag for output in agent_outputs for flag in output.safety_flags]
        affected = list(dict.fromkeys(claim_id for item in safety.findings for claim_id in item.claim_ids))
        findings = list(dict.fromkeys([*inherited, *(item.explanation for item in safety.findings)]))
        results.append(_result(
            "safety", "Source-Grounded Safety Judge", started,
            score=safety.source_grounded_safety_score,
            findings=findings,
            affected=affected,
            version="safejudge-deterministic-v0.1",
        ))
    if "conflict" in selected:
        started = time.perf_counter()
        findings = [*debate.disagreements, *[f"Unresolved: {item}" for item in debate.unresolved_conflicts]]
        results.append(_result(
            "conflict", "Conflict Judge", started,
            score=1.0 - conflict_status.conflict_score,
            findings=findings,
        ))
    if "confidence" in selected:
        started = time.perf_counter()
        results.append(_result(
            "confidence", "Evidence Confidence Judge", started,
            score=confidence.score,
            findings=[confidence.interpretation, *confidence.caps_applied],
            version="confidence-deterministic-v0.1",
        ))
    if "provenance" in selected:
        started = time.perf_counter()
        invalid = [
            citation.evidence_id
            for citation in citations
            if citation.evidence_id not in evidence_ids or citation.source_id not in source_ids
        ]
        score = 1 - len(invalid) / max(1, len(citations))
        findings = [] if not invalid else [f"Invalid provenance mapping: {', '.join(invalid)}"]
        results.append(_result("provenance", "Citation and Provenance Judge", started, score=score, findings=findings))

    return IntegratedJudgeBundle(
        judge_outputs=results,
        evidence_support=evidence_support,
        safety_assessment=safety,
        conflict_status=conflict_status,
        evidence_confidence=confidence,
    )


def run_judges(
    agent_outputs: list[ResearchAgentOutput],
    evidence: list[RetrievalItem],
    debate: DebateTrace,
    active: list[str],
) -> list[JudgeResult]:
    """Backward-compatible legacy list output for callers that do not need typed fields."""
    response_text = " ".join(claim.text for output in agent_outputs for claim in output.claims)
    return run_integrated_judges(
        agent_outputs,
        evidence,
        debate,
        active,
        response_text=response_text,
    ).judge_outputs
