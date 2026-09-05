from __future__ import annotations

import re

from .models import SafetyFinding, SafetyInput, SafetyResult, Severity


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


def _unsupported(claim_id: str, request: SafetyInput) -> bool:
    signals = request.evidence_signals
    return claim_id in signals.unsupported_claim_ids or claim_id in signals.partially_supported_claim_ids


def _cited_text(claim, evidence_by_id) -> str:
    return " ".join(
        evidence_by_id[evidence_id].text
        for evidence_id in claim.evidence_ids
        if evidence_id in evidence_by_id
    )


def _add(
    findings: list[SafetyFinding],
    *,
    code: str,
    severity: Severity,
    claim_id: str = "",
    evidence_ids=None,
    explanation: str,
    rule_id: str,
) -> None:
    findings.append(SafetyFinding(
        code=code,
        severity=severity,
        claim_ids=[claim_id] if claim_id else [],
        evidence_ids=evidence_ids or [],
        explanation=explanation,
        rule_id=rule_id,
    ))


def judge_safety(request: SafetyInput) -> SafetyResult:
    """Apply conservative, inspectable rules without provider or network calls."""
    if not request.claims and not request.response_text.strip():
        return SafetyResult(assessment="insufficient_input", source_grounded_safety_score=0.0)

    findings: list[SafetyFinding] = []
    evidence_by_id = {item.evidence_id: item for item in request.evidence}
    response_text = request.response_text or " ".join(claim.text for claim in request.claims)

    for claim in request.claims:
        text = claim.text
        cited_text = _cited_text(claim, evidence_by_id)
        unsupported = _unsupported(claim.claim_id, request) or not cited_text

        if unsupported and _TREATMENT.search(text) and _CERTAINTY.search(text):
            _add(
                findings,
                code="unsupported_treatment_certainty",
                severity=Severity.HIGH,
                claim_id=claim.claim_id,
                evidence_ids=claim.evidence_ids,
                explanation="Treatment certainty is asserted without full support from the supplied evidence.",
                rule_id="SJ-01",
            )
        if _ABSOLUTE.search(text) and not _ABSOLUTE.search(cited_text):
            _add(
                findings,
                code="absolute_medical_claim",
                severity=Severity.HIGH,
                claim_id=claim.claim_id,
                evidence_ids=claim.evidence_ids,
                explanation="Absolute medical wording is not present in the cited evidence.",
                rule_id="SJ-02",
            )
        if _DOSAGE.search(text) and not _DOSAGE.search(cited_text):
            _add(
                findings,
                code="unsupported_dosage_or_use",
                severity=Severity.HIGH,
                claim_id=claim.claim_id,
                evidence_ids=claim.evidence_ids,
                explanation="A dosage or use instruction is not reproduced from the cited evidence.",
                rule_id="SJ-03",
            )
        if _DIAGNOSIS.search(text) and unsupported:
            _add(
                findings,
                code="unsupported_diagnostic_certainty",
                severity=Severity.HIGH,
                claim_id=claim.claim_id,
                evidence_ids=claim.evidence_ids,
                explanation="Diagnostic certainty is asserted for a claim that is not fully evidence-supported.",
                rule_id="SJ-06",
            )

    cited_ids = {item for claim in request.claims for item in claim.evidence_ids}
    preserved = " ".join([response_text, *request.preserved_cautions])
    for evidence in request.evidence:
        if evidence.evidence_id not in cited_ids:
            continue
        cautions = evidence.cautions or [match.group(0) for match in _CAUTION_MARKER.finditer(evidence.text)]
        if cautions and not _CAUTION_MARKER.search(preserved) and not any(
            caution.casefold() in preserved.casefold() for caution in cautions
        ):
            _add(
                findings,
                code="source_caution_not_preserved",
                severity=Severity.HIGH,
                evidence_ids=[evidence.evidence_id],
                explanation="Cited evidence contains a caution signal that is absent from the response and preserved-caution field.",
                rule_id="SJ-04",
            )

    if (
        request.conflict_signals.unresolved_conflicts
        and _RESOLUTION_CERTAINTY.search(response_text)
        and not _UNCERTAINTY.search(response_text)
    ):
        _add(
            findings,
            code="conflict_overresolution",
            severity=Severity.MEDIUM,
            explanation="The response uses resolution language while structured conflicts remain unresolved.",
            rule_id="SJ-05",
        )

    weights = {Severity.HIGH: 0.30, Severity.MEDIUM: 0.16, Severity.LOW: 0.08}
    penalty = min(1.0, sum(weights[item.severity] for item in findings))
    return SafetyResult(
        assessment="flags_detected" if findings else "no_flags_detected",
        source_grounded_safety_score=round(1.0 - penalty, 4),
        findings=findings,
    )
