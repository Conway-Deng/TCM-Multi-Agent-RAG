from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


def _unit_interval(name: str, value: float) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be within [0, 1]")


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(kw_only=True)
class ClaimRecord:
    claim_id: str
    text: str
    evidence_ids: list[str] = field(default_factory=list)
    claim_type: str = "educational"

    def __post_init__(self) -> None:
        if not self.claim_id or not self.text:
            raise ValueError("claim_id and text must be non-empty")


@dataclass(kw_only=True)
class EvidenceRecord:
    evidence_id: str
    text: str
    relevance_score: float = 0.0
    verification_status: str = "needs_review"
    cautions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.text:
            raise ValueError("evidence_id and text must be non-empty")
        _unit_interval("relevance_score", self.relevance_score)


@dataclass(kw_only=True)
class EvidenceSignals:
    eligible_claim_count: int = 0
    evidence_coverage: float = 0.0
    citation_coverage: float = 0.0
    retrieval_sufficiency: float = 0.0
    verified_evidence_ratio: float = 0.0
    unsupported_claim_ids: list[str] = field(default_factory=list)
    partially_supported_claim_ids: list[str] = field(default_factory=list)
    missing_citation_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.eligible_claim_count < 0:
            raise ValueError("eligible_claim_count cannot be negative")
        for name in ("evidence_coverage", "citation_coverage", "retrieval_sufficiency", "verified_evidence_ratio"):
            _unit_interval(name, getattr(self, name))


@dataclass(kw_only=True)
class ConflictSignals:
    unresolved_conflicts: list[str] = field(default_factory=list)
    conflict_score: float = 0.0
    agent_agreement_score: float = 0.0

    def __post_init__(self) -> None:
        _unit_interval("conflict_score", self.conflict_score)
        _unit_interval("agent_agreement_score", self.agent_agreement_score)


@dataclass(kw_only=True)
class SafetyInput:
    response_text: str = ""
    claims: list[ClaimRecord] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    evidence_signals: EvidenceSignals = field(default_factory=EvidenceSignals)
    conflict_signals: ConflictSignals = field(default_factory=ConflictSignals)
    preserved_cautions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        claim_ids = [item.claim_id for item in self.claims]
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("claim_id values must be unique")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence_id values must be unique")


@dataclass(kw_only=True)
class SafetyFinding:
    code: Literal[
        "unsupported_treatment_certainty",
        "absolute_medical_claim",
        "unsupported_dosage_or_use",
        "source_caution_not_preserved",
        "conflict_overresolution",
        "unsupported_diagnostic_certainty",
    ]
    severity: Severity
    explanation: str
    rule_id: str
    claim_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class SafetyResult:
    assessment: Literal["no_flags_detected", "flags_detected", "insufficient_input"]
    source_grounded_safety_score: float
    findings: list[SafetyFinding] = field(default_factory=list)
    judge_version: str = "safejudge-deterministic-v0.1"
    deterministic: bool = True
    interpretation: str = "Source-grounded safety flags and an evidence-supported caution assessment only."

    def __post_init__(self) -> None:
        _unit_interval("source_grounded_safety_score", self.source_grounded_safety_score)


@dataclass(kw_only=True)
class ConfidenceInput:
    evidence_signals: EvidenceSignals
    conflict_signals: ConflictSignals = field(default_factory=ConflictSignals)
    safety_result: SafetyResult | None = None
    active_agent_count: int = 1
    abstained_agent_count: int = 0
    model_failure_count: int = 0

    def __post_init__(self) -> None:
        if min(self.active_agent_count, self.abstained_agent_count, self.model_failure_count) < 0:
            raise ValueError("agent and failure counts cannot be negative")
        if self.abstained_agent_count > self.active_agent_count:
            raise ValueError("abstained_agent_count cannot exceed active_agent_count")


@dataclass(kw_only=True)
class ScoreComponent:
    signal: str
    observed_value: float
    weight: float
    contribution: float

    def __post_init__(self) -> None:
        for name in ("observed_value", "weight", "contribution"):
            _unit_interval(name, getattr(self, name))


@dataclass(kw_only=True)
class ConfidencePenalty:
    signal: str
    observed_value: float
    maximum_penalty: float
    applied_penalty: float

    def __post_init__(self) -> None:
        for name in ("observed_value", "maximum_penalty", "applied_penalty"):
            _unit_interval(name, getattr(self, name))


@dataclass(kw_only=True)
class ConfidenceResult:
    evidence_confidence: float
    band: Literal["insufficient", "limited", "moderate", "strong"]
    positive_components: list[ScoreComponent]
    penalties: list[ConfidencePenalty]
    caps_applied: list[str] = field(default_factory=list)
    missing_or_weak_signals: list[str] = field(default_factory=list)
    judge_version: str = "confidence-deterministic-v0.1"
    deterministic: bool = True
    interpretation: str = "Evidence confidence expressed as a response reliability indicator derived from observable evidence signals."

    def __post_init__(self) -> None:
        _unit_interval("evidence_confidence", self.evidence_confidence)
