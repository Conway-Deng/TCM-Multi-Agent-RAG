import math
import sys
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class RawRetrievalItem(StrictResearchModel):
    rank: int = Field(ge=1, le=4)
    retrieval_score: float = Field(ge=0.0, le=1.0)
    score_is_zero: bool
    chunk_id: str = Field(min_length=1)
    corpus_record_ordinal: int = Field(ge=0)
    source_id: str = Field(min_length=1)
    source_record_id: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    doi: str | None = None
    pmcid: str | None = None
    section_or_category: str | None = None
    license_or_access_status: str | None = None
    source_citation_or_version: str | None = None
    review_status: str | None = None
    exact_original_chunk_text: str = Field(min_length=1)
    chunk_text_utf8_sha256: str = Field(min_length=64, max_length=64)
    chunk_record_canonical_sha256: str = Field(min_length=64, max_length=64)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("retrieval_score")
    @classmethod
    def validate_retrieval_score_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError(f"Retrieval score must be finite, got {v}")
        return v

    @model_validator(mode="after")
    def validate_zero_consistency(self) -> "RawRetrievalItem":
        if self.score_is_zero and self.retrieval_score != 0.0:
            raise ValueError(
                f"score_is_zero is True but retrieval_score is non-zero ({self.retrieval_score})"
            )
        if not self.score_is_zero and self.retrieval_score == 0.0:
            raise ValueError(
                "score_is_zero is False but retrieval_score is 0.0"
            )
        return self


class RawRetrievalRecord(StrictResearchModel):
    schema_version: str = "cpaa1_raw_retrieval_v1"
    retrieval_record_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    topic: Topic
    task_type: TaskType
    perspective: Literal["tcm", "western"]
    question_manifest_sha256: str = Field(min_length=64, max_length=64)
    corpus_id: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
    corpus_sha256: str = Field(min_length=64, max_length=64)
    retrieval_algorithm_id: str = "CPAA1-R0-LEXICAL-V1"
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    query_text: str = Field(min_length=1)
    query_text_sha256: str = Field(min_length=64, max_length=64)
    requested_top_k: int = Field(default=4, ge=1, le=4)
    returned_count: int = Field(ge=0, le=4)
    positive_score_count: int = Field(ge=0, le=4)
    zero_score_count: int = Field(ge=0, le=4)
    retrieval_status: str = Field(min_length=1)
    retrieved_at_utc: str = Field(min_length=1)
    implementation_commit: str = Field(min_length=1)
    record_canonical_sha256: str = Field(min_length=64, max_length=64)
    results: list[RawRetrievalItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts_and_ranks(self) -> "RawRetrievalRecord":
        if len(self.results) != self.returned_count:
            raise ValueError(
                f"returned_count ({self.returned_count}) != len(results) ({len(self.results)})"
            )
        pos = sum(1 for r in self.results if not r.score_is_zero)
        zeros = sum(1 for r in self.results if r.score_is_zero)
        if pos != self.positive_score_count:
            raise ValueError(
                f"positive_score_count mismatch: {pos} vs {self.positive_score_count}"
            )
        if zeros != self.zero_score_count:
            raise ValueError(
                f"zero_score_count mismatch: {zeros} vs {self.zero_score_count}"
            )
        ranks = [r.rank for r in self.results]
        if ranks != list(range(1, len(self.results) + 1)):
            raise ValueError(f"Ranks must be 1..{len(self.results)}, got {ranks}")
        chunk_ids = [r.chunk_id for r in self.results]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError(f"Result chunk_ids must be unique, got {chunk_ids}")
        return self


class RetrievalRunManifest(StrictResearchModel):
    schema_version: str = "cpaa1_retrieval_manifest_v1"
    study_id: str = "cross-perspective-advisory-ablation-v1"
    algorithm_id: str = "CPAA1-R0-LEXICAL-V1"
    question_manifest_sha256: str = Field(min_length=64, max_length=64)
    question_count: int = Field(default=48, ge=48, le=48)
    tcm_corpus_sha256: str = Field(min_length=64, max_length=64)
    tcm_record_count: int = Field(default=48, ge=48, le=48)
    tcm_retrieval_output_sha256: str = Field(min_length=64, max_length=64)
    western_corpus_sha256: str = Field(min_length=64, max_length=64)
    western_record_count: int = Field(default=48, ge=48, le=48)
    western_retrieval_output_sha256: str = Field(min_length=64, max_length=64)
    generated_at_utc: str = Field(min_length=1)
    implementation_commit: str = Field(min_length=1)
    contract: dict[str, Any] = Field(default_factory=dict)


class FrozenEvidenceItem(StrictResearchModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    rank: int = Field(ge=1, le=4)
    retrieval_score: float
    score_is_zero: bool
    chunk_id: str = Field(min_length=1)
    corpus_record_ordinal: int = Field(ge=0)
    exact_chunk_text: str = Field(min_length=1)
    chunk_text_sha256: str = Field(min_length=64, max_length=64)
    chunk_record_canonical_sha256: str = Field(min_length=64, max_length=64)
    source_id: str = Field(min_length=1)
    source_record_id: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    doi: str | None = None
    pmcid: str | None = None
    section_or_category: str | None = None
    source_citation_or_version: str | None = None
    license_or_access_status: str | None = None
    review_status: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    support_basis: Literal["verbatim_source_copy"] = "verbatim_source_copy"
    semantic_support_status: Literal["not_assessed"] = "not_assessed"

    @field_validator("retrieval_score")
    @classmethod
    def validate_score_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError(f"Retrieval score must be finite, got {v}")
        return v

    @model_validator(mode="after")
    def validate_zero_consistency(self) -> "FrozenEvidenceItem":
        if self.score_is_zero and self.retrieval_score != 0.0:
            raise ValueError(
                f"score_is_zero is True but retrieval_score is non-zero ({self.retrieval_score})"
            )
        if not self.score_is_zero and self.retrieval_score == 0.0:
            raise ValueError("score_is_zero is False but retrieval_score is 0.0")
        return self


class FrozenEvidencePacket(StrictResearchModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "cpaa1_frozen_packet_v1"
    transformation_contract_id: str = "CPAA1-FROZEN-PACKET-LOSSLESS-V1"
    packet_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    topic: Topic
    task_type: TaskType
    perspective: Literal["tcm", "western"]
    question_manifest_sha256: str = Field(min_length=64, max_length=64)
    retrieval_algorithm_id: str = "CPAA1-R0-LEXICAL-V1"
    retrieval_artifact_sha256: str = Field(min_length=64, max_length=64)
    retrieval_record_id: str = Field(min_length=1)
    retrieval_record_canonical_sha256: str = Field(min_length=64, max_length=64)
    corpus_id: str = Field(min_length=1)
    corpus_version: str = Field(min_length=1)
    corpus_sha256: str = Field(min_length=64, max_length=64)
    evidence_items: tuple[FrozenEvidenceItem, ...] = Field(default_factory=tuple)
    packet_canonical_sha256: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_packet_invariants(self) -> "FrozenEvidencePacket":
        if len(self.evidence_items) != 4:
            raise ValueError(
                f"FrozenEvidencePacket must contain exactly 4 evidence items, got {len(self.evidence_items)}"
            )
        ranks = [item.rank for item in self.evidence_items]
        if ranks != [1, 2, 3, 4]:
            raise ValueError(f"Evidence item ranks must be exactly [1, 2, 3, 4], got {ranks}")
        ev_ids = [item.evidence_id for item in self.evidence_items]
        if len(set(ev_ids)) != len(ev_ids):
            raise ValueError(f"Evidence IDs must be unique within packet, got {ev_ids}")
        chunk_ids = [item.chunk_id for item in self.evidence_items]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError(f"Chunk IDs must be unique within packet, got {chunk_ids}")
        return self


class PacketRunManifest(StrictResearchModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cpaa1_packet_manifest_v1"] = "cpaa1_packet_manifest_v1"
    study_id: Literal["cross-perspective-advisory-ablation-v1"] = "cross-perspective-advisory-ablation-v1"
    amendment_id: Literal["CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1"] = "CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1"
    packet_contract_id: Literal["CPAA1-FROZEN-PACKET-LOSSLESS-V1"] = "CPAA1-FROZEN-PACKET-LOSSLESS-V1"
    serialization_version: Literal["CPAA1-PACKET-SERIALIZATION-V1"] = "CPAA1-PACKET-SERIALIZATION-V1"
    implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    question_manifest_sha256: str = Field(min_length=64, max_length=64)
    tcm_raw_retrieval_byte_sha256: str = Field(min_length=64, max_length=64)
    western_raw_retrieval_byte_sha256: str = Field(min_length=64, max_length=64)
    tcm_corpus_sha256: str = Field(min_length=64, max_length=64)
    western_corpus_sha256: str = Field(min_length=64, max_length=64)
    research_prompt_sha256: dict[str, str]
    tcm_packet_byte_sha256: str = Field(min_length=64, max_length=64)
    western_packet_byte_sha256: str = Field(min_length=64, max_length=64)
    tcm_packet_canonical_aggregate_sha256: str = Field(min_length=64, max_length=64)
    western_packet_canonical_aggregate_sha256: str = Field(min_length=64, max_length=64)
    tcm_packet_count: int = Field(default=48, ge=48, le=48)
    western_packet_count: int = Field(default=48, ge=48, le=48)
    total_packet_count: int = Field(default=96, ge=96, le=96)
    tcm_evidence_item_count: int = Field(default=192, ge=192, le=192)
    western_evidence_item_count: int = Field(default=192, ge=192, le=192)
    total_evidence_item_count: int = Field(default=384, ge=384, le=384)
    integrity_audit_status: Literal["PASS"] = "PASS"
    no_retrieval_attestation: Literal[True] = True
    no_model_provider_attestation: Literal[True] = True
    local_only_packet_jsonls: Literal[True] = True


class PacketFreezeReceipt(StrictResearchModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cpaa1_packet_freeze_receipt_v1"] = "cpaa1_packet_freeze_receipt_v1"
    study_id: Literal["cross-perspective-advisory-ablation-v1"] = "cross-perspective-advisory-ablation-v1"
    amendment_id: Literal["CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1"] = "CPAA1-PACKET-GOVERNANCE-AMENDMENT-V1"
    packet_contract_id: Literal["CPAA1-FROZEN-PACKET-LOSSLESS-V1"] = "CPAA1-FROZEN-PACKET-LOSSLESS-V1"
    serialization_version: Literal["CPAA1-PACKET-SERIALIZATION-V1"] = "CPAA1-PACKET-SERIALIZATION-V1"
    implementation_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    question_manifest_sha256: str = Field(min_length=64, max_length=64)
    tcm_raw_retrieval_byte_sha256: str = Field(min_length=64, max_length=64)
    western_raw_retrieval_byte_sha256: str = Field(min_length=64, max_length=64)
    tcm_corpus_sha256: str = Field(min_length=64, max_length=64)
    western_corpus_sha256: str = Field(min_length=64, max_length=64)
    research_prompt_sha256: dict[str, str]
    tcm_packet_byte_sha256: str = Field(min_length=64, max_length=64)
    western_packet_byte_sha256: str = Field(min_length=64, max_length=64)
    tcm_packet_canonical_aggregate_sha256: str = Field(min_length=64, max_length=64)
    western_packet_canonical_aggregate_sha256: str = Field(min_length=64, max_length=64)
    tcm_packet_count: int = Field(default=48, ge=48, le=48)
    western_packet_count: int = Field(default=48, ge=48, le=48)
    total_packet_count: int = Field(default=96, ge=96, le=96)
    tcm_evidence_item_count: int = Field(default=192, ge=192, le=192)
    western_evidence_item_count: int = Field(default=192, ge=192, le=192)
    total_evidence_item_count: int = Field(default=384, ge=384, le=384)
    integrity_audit_status: Literal["PASS"] = "PASS"
    no_retrieval_attestation: Literal[True] = True
    no_model_provider_attestation: Literal[True] = True
    local_only_packet_jsonls: Literal[True] = True
    manifest_byte_sha256: str = Field(min_length=64, max_length=64)
    manifest_canonical_sha256: str = Field(min_length=64, max_length=64)
