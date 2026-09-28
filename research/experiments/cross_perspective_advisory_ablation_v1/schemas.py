import sys
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from backend.cross_perspective.schemas import (
        ActivePerspectiveName,
        AssessmentIssue,
        CriticExecutionStatus,
        CrossPerspectiveAnswer,
        CrossPerspectiveCritique,
        CrossPerspectiveDraft,
        CrossPerspectiveRelation,
        CrossPerspectiveRelationType,
        EvidenceReference,
        ModelCallEvent,
        PerspectiveAgentAssessment,
        PerspectiveClaim,
        PerspectiveEvidencePacket,
        PerspectiveFailure,
        ProvenanceRecord,
        SourceMapEntry,
    )
except ModuleNotFoundError:
    from cross_perspective.schemas import (
        ActivePerspectiveName,
        AssessmentIssue,
        CriticExecutionStatus,
        CrossPerspectiveAnswer,
        CrossPerspectiveCritique,
        CrossPerspectiveDraft,
        CrossPerspectiveRelation,
        CrossPerspectiveRelationType,
        EvidenceReference,
        ModelCallEvent,
        PerspectiveAgentAssessment,
        PerspectiveClaim,
        PerspectiveEvidencePacket,
        PerspectiveFailure,
        ProvenanceRecord,
        SourceMapEntry,
    )



Topic = Literal["cough", "dyspepsia_digestive_symptoms", "headache", "constipation"]
TaskType = Literal["evidence_description", "cross_perspective_synthesis", "boundary_uncertainty"]
ConditionName = Literal["G0", "G1", "G2", "G3"]
ClaimSupportRating = Literal["supported", "partially_supported", "unsupported", "contradicted"]


class StrictResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionCandidate(StrictResearchModel):
    candidate_id: str = Field(min_length=1)
    topic: Topic
    task_type: TaskType
    question_text: str = Field(min_length=5)
    source_notes: str = ""


class SelectedQuestion(StrictResearchModel):
    question_id: str = Field(min_length=1)
    topic: Topic
    task_type: TaskType
    question_text: str = Field(min_length=5)
    selection_order: int = Field(ge=1, le=48)
    frozen_timestamp: str = Field(min_length=1)
    selection_metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceUnit(StrictResearchModel):
    unit_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    topic: Topic
    statement: str = Field(min_length=5)
    perspective_target: Literal["tcm", "western", "cross_perspective", "limitation"]
    required: bool = True


class EvidenceRetrievalRecord(StrictResearchModel):
    perspective: ActivePerspectiveName
    query: str = Field(min_length=1)
    strategy: str = "R0"
    top_k: int = Field(default=4, ge=1)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_source_ids: list[str] = Field(default_factory=list)
    corpus_sha256: str = Field(min_length=64, max_length=64)
    retrieval_hash: str = Field(min_length=64, max_length=64)


class EvidenceFreezeRecord(StrictResearchModel):
    question_id: str = Field(min_length=1)
    tcm_retrieval: EvidenceRetrievalRecord
    western_retrieval: EvidenceRetrievalRecord
    retrieval_timestamp: str = Field(min_length=1)
    freeze_hash: str = Field(min_length=64, max_length=64)


class PacketPair(StrictResearchModel):
    question_id: str = Field(min_length=1)
    tcm_packet: PerspectiveEvidencePacket
    western_packet: PerspectiveEvidencePacket
    pair_hash: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_perspectives(self) -> "PacketPair":
        if self.tcm_packet.perspective != "tcm":
            raise ValueError("tcm_packet perspective must be 'tcm'")
        if self.western_packet.perspective != "western":
            raise ValueError("western_packet perspective must be 'western'")
        return self


class AdvisoryFreezeRecord(StrictResearchModel):
    question_id: str = Field(min_length=1)
    evidence_pair_hash: str = Field(min_length=64, max_length=64)
    tcm_assessments: list[PerspectiveAgentAssessment] = Field(default_factory=list)
    western_assessments: list[PerspectiveAgentAssessment] = Field(default_factory=list)
    failed_roles: list[str] = Field(default_factory=list)
    provider_events: list[ModelCallEvent] = Field(default_factory=list)
    freeze_hash: str = Field(min_length=64, max_length=64)


class CriticFreezeRecord(StrictResearchModel):
    question_id: str = Field(min_length=1)
    evidence_pair_hash: str = Field(min_length=64, max_length=64)
    advisory_freeze_hash: str = Field(min_length=64, max_length=64)
    critic_status: CriticExecutionStatus
    critique: CrossPerspectiveCritique | None = None
    failed_roles: list[str] = Field(default_factory=list)
    provider_events: list[ModelCallEvent] = Field(default_factory=list)
    critic_model: str = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
    freeze_hash: str = Field(min_length=64, max_length=64)


class ConditionCell(StrictResearchModel):
    cell_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    topic: Topic
    task_type: TaskType
    condition: ConditionName
    repetition: Literal[1, 2]


class ProviderAttempt(StrictResearchModel):
    role: str = Field(min_length=1)
    attempt: int = Field(ge=1, le=2)
    provider: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    reported_model: str | None = None
    success: bool
    latency_ms: float = Field(ge=0)
    http_status: int | None = None
    failure_class: str | None = None
    error_summary: str | None = None
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)


class BlindedAnswerRecord(StrictResearchModel):
    blind_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    topic: Topic
    task_type: TaskType
    overall_summary: str = Field(default="")
    overall_supporting_claim_ids: list[str] = Field(default_factory=list)
    perspectives: dict[str, Any] = Field(default_factory=dict)
    agreements: list[dict[str, Any]] = Field(default_factory=list)
    differences_or_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    source_map: list[dict[str, Any]] = Field(default_factory=list)
    is_terminal_failure: bool = False
    failure_reason: str | None = None


class BlindKeyRecord(StrictResearchModel):
    blind_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    condition: ConditionName
    repetition: Literal[1, 2]
    cell_id: str = Field(min_length=1)


class ScoredClaim(StrictResearchModel):
    claim_id: str | None = None
    claim_statement: str = Field(min_length=1)
    perspective: str = Field(min_length=1)
    rating: ClaimSupportRating
    evidence_grounding_verified: bool
    rationale: str = ""


class HumanScoringRecord(StrictResearchModel):
    evaluator_id: str = Field(min_length=1)
    blind_id: str = Field(min_length=1)
    is_structurally_usable: bool
    has_substantive_content: bool
    scored_claims: list[ScoredClaim] = Field(default_factory=list)
    reference_units_total_m_q: int = Field(ge=1)
    reference_units_fully_conveyed: int = Field(ge=0)
    all_substantive_claims_fully_supported: bool
    primary_usable_grounded_coverage_yield: float = Field(ge=0.0, le=1.0)
    secondary_metrics: dict[str, Any] = Field(default_factory=dict)
    is_explicitly_uncertain: bool = False
    uncertainty_notes: str | None = None
    scoring_timestamp: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_yield_gate(self) -> "HumanScoringRecord":
        if self.reference_units_fully_conveyed > self.reference_units_total_m_q:
            raise ValueError("conveyed reference units cannot exceed total reference units M_q")
        passes_gate = (
            self.is_structurally_usable
            and self.has_substantive_content
            and self.all_substantive_claims_fully_supported
        )
        expected_score = (
            round(self.reference_units_fully_conveyed / self.reference_units_total_m_q, 6)
            if passes_gate
            else 0.0
        )
        if abs(self.primary_usable_grounded_coverage_yield - expected_score) > 1e-5:
            raise ValueError(
                f"primary_usable_grounded_coverage_yield ({self.primary_usable_grounded_coverage_yield}) "
                f"does not match gate calculation ({expected_score})"
            )
        return self


class AuditRecord(StrictResearchModel):
    auditor_id: str = Field(min_length=1)
    blind_id: str = Field(min_length=1)
    is_structurally_usable: bool
    has_substantive_content: bool
    scored_claims: list[ScoredClaim] = Field(default_factory=list)
    reference_units_total_m_q: int = Field(ge=1)
    reference_units_fully_conveyed: int = Field(ge=0)
    all_substantive_claims_fully_supported: bool
    primary_usable_grounded_coverage_yield: float = Field(ge=0.0, le=1.0)
    audit_timestamp: str = Field(min_length=1)
    audit_notes: str | None = None

    @model_validator(mode="after")
    def validate_yield_gate(self) -> "AuditRecord":
        passes_gate = (
            self.is_structurally_usable
            and self.has_substantive_content
            and self.all_substantive_claims_fully_supported
        )
        expected_score = (
            round(self.reference_units_fully_conveyed / self.reference_units_total_m_q, 6)
            if passes_gate
            else 0.0
        )
        if abs(self.primary_usable_grounded_coverage_yield - expected_score) > 1e-5:
            raise ValueError(
                f"audited primary_usable_grounded_coverage_yield ({self.primary_usable_grounded_coverage_yield}) "
                f"does not match gate calculation ({expected_score})"
            )
        return self


class AuditReconciliationRecord(StrictResearchModel):
    blind_id: str = Field(min_length=1)
    reviewer_a_score: float = Field(ge=0.0, le=1.0)
    reviewer_b_score: float = Field(ge=0.0, le=1.0)
    reconciled_score: float = Field(ge=0.0, le=1.0)
    score_changed_by_reconciliation: bool
    score_absolute_delta: float = Field(ge=0.0)
    reconciliation_notes: str | None = None


class AuditSampleSummary(StrictResearchModel):
    total_audit_questions: int = Field(default=12, ge=12, le=12)
    total_audit_outputs: int = Field(default=96, ge=96, le=96)
    reconciled_outputs_changed_count: int = Field(ge=0)
    reconciled_outputs_changed_fraction: float = Field(ge=0.0, le=1.0)
    full_second_review_required: bool
    audit_status: Literal["PASSED_AUDIT_GATE", "FULL_SECOND_REVIEW_REQUIRED"]


class QuestionScore(StrictResearchModel):
    question_id: str = Field(min_length=1)
    topic: Topic
    task_type: TaskType
    condition_scores: dict[ConditionName, float]


class SecondaryComparisonResult(StrictResearchModel):
    contrast: str = Field(min_length=1)
    mean_difference: float
    ci_lower_95: float
    ci_upper_95: float
    is_exploratory: bool = True


class AnalysisRecord(StrictResearchModel):
    study_id: str = "cross-perspective-advisory-ablation-v1"
    sample_size_questions: int = Field(default=48, ge=48, le=48)
    total_cells: int = Field(default=384, ge=384, le=384)
    primary_comparison_name: str = "G3 - G0"
    g0_mean: float = Field(ge=0.0, le=1.0)
    g3_mean: float = Field(ge=0.0, le=1.0)
    primary_mean_difference: float
    bootstrap_95_ci_lower: float
    bootstrap_95_ci_upper: float
    bootstrap_resamples: int = Field(default=20000, ge=1)
    bootstrap_seed: int
    stratified: bool = True
    secondary_comparisons: list[SecondaryComparisonResult] = Field(default_factory=list)
    secondary_component_metrics: dict[str, Any] = Field(default_factory=dict)
