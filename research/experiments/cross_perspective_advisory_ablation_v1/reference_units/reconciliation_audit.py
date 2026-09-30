"""Human Reconciliation and Audit Structure Infrastructure.

Protocol Anchor: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Schema Version: cpaa1_reference_unit_v1
Study ID: cross-perspective-advisory-ablation-v1

This module implements mechanical, human-only reconciliation support infrastructure
under REFERENCE_UNIT_PROTOCOL_V1.md Sections J, K, and L.

CRITICAL SCIENTIFIC AND ARCHITECTURAL BOUNDARIES:
1. HUMAN-ONLY SCIENTIFIC WORK:
   Formal reference-unit reconciliation is exclusively human semantic work.
   The software performs strictly mechanical tasks:
   - stores reviewer-record references
   - verifies reviewer roles, question IDs, and record bounds
   - maintains administrative audit states
   - preserves Reviewer A / Reviewer B provenance
   - flags EXACT byte/object duplicates only
   - records human-entered completeness attestations
   - logs human-entered additions and unresolved disagreements

2. STRICT PROHIBITIONS ON SOFTWARE INFERENCE:
   The software MUST NOT:
   - decide semantic equivalence
   - match similar units
   - recommend merges or splits
   - decide omission or selection
   - decide whether a target is eligible
   - judge evidence sufficiency
   - invent a new reconciliation unit or rewrite text/qualifiers/rationale
   - adjudicate disagreement
   - calculate final M_q or assign final reference_unit_id
   - build an automatic union or reconciled reference set
   - call any model, API, or external provider

3. A/B INDEPENDENCE AND FORMAL EXECUTION GATE:
   Under frozen protocol Section J, Reviewer A and Reviewer B construct reference
   units independently. Formal reconciliation cannot begin until both submissions
   are cryptographically locked and receipt-hashed (Phase B3+).
   Administrative B2A workspace locks alone do NOT authorize formal reconciliation.
   All formal reconciliation constructors and combination helpers fail closed in Phase B2B.

4. EXACT DUPLICATE != SEMANTIC EQUIVALENCE:
   Exact duplicate flagging is advisory and mechanical only. It only flags records
   with strictly identical serialization. It does not merge, edit, or delete.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from research.experiments.cross_perspective_advisory_ablation_v1.reference_units.annotation_support import (
    ReviewerRole,
    ReviewerRoleMismatchError,
    ReviewerWorkspace,
)
from research.experiments.cross_perspective_advisory_ablation_v1.reference_units.reference_unit_schema import (
    FROZEN_PROTOCOL_BYTE_SHA256,
    PROTOCOL_ID,
    SCHEMA_VERSION,
    STUDY_ID,
    ReferenceUnitRecord,
)

LOCAL_ONLY_NOTICE: Final[str] = (
    "LOCAL-ONLY RESEARCH AUDIT ARTIFACT. "
    "Contains human annotation and reconciliation audit data. "
    "Do not commit or push to remote repository."
)

ALLOWED_RECONCILIATION_STATES: Final[tuple[str, ...]] = (
    "unreviewed",
    "in_review",
    "human_review_complete",
    "unresolved",
    "adjudication_required",
)

ReconciliationState = Literal[
    "unreviewed",
    "in_review",
    "human_review_complete",
    "unresolved",
    "adjudication_required",
]

ALLOWED_NEW_TARGET_STATUSES: Final[tuple[str, ...]] = (
    "pending",
    "accepted",
    "rejected",
)

NewTargetStatus = Literal["pending", "accepted", "rejected"]

ALLOWED_DISAGREEMENT_STATUSES: Final[tuple[str, ...]] = (
    "unresolved",
    "referred_to_adjudication",
    "adjudicated",
    "closed",
)

DisagreementStatus = Literal[
    "unresolved",
    "referred_to_adjudication",
    "adjudicated",
    "closed",
]


class ReconciliationAuditError(Exception):
    """Base error for reconciliation audit failures."""


class ReviewerRecordRefValidationError(ReconciliationAuditError):
    """Raised when a ReviewerRecordRef fails structural or referential validation."""


class FormalReconciliationGateError(ReconciliationAuditError):
    """Raised when formal reconciliation execution is attempted without cryptographic submission receipts."""


class ReconciliationStateError(ReconciliationAuditError):
    """Raised when an invalid state transition or missing attestation is encountered."""


def _require_bool(value: Any, field_name: str) -> bool:
    """Fail-closed validator enforcing that value is an actual bool instance."""
    if type(value) is not bool:
        raise TypeError(
            f"Field '{field_name}' must be of type bool, got {type(value).__name__} ({value!r})"
        )
    return value


def _require_non_empty_str(value: Any, field_name: str) -> str:
    """Fail-closed validator enforcing that value is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Field '{field_name}' must be a non-empty string, got {value!r}"
        )
    return value


@dataclass(frozen=True)
class ReviewerRecordRef:
    """Immutable mechanical reference to a record in a reviewer submission.

    Refers to a record by reviewer role and index without copying,
    rewriting, or interpreting its semantic content.
    """

    reviewer_role: Literal["reviewer_a", "reviewer_b"]
    record_index: int
    question_id: str

    def __post_init__(self) -> None:
        if self.reviewer_role not in ("reviewer_a", "reviewer_b"):
            raise ValueError(
                f"Invalid reviewer_role '{self.reviewer_role}': must be 'reviewer_a' or 'reviewer_b'"
            )
        # Part C.5: Reject bool explicitly since bool is a subclass of int
        if isinstance(self.record_index, bool) or type(self.record_index) is not int:
            raise TypeError(
                f"record_index must be an int, not bool or {type(self.record_index).__name__}"
            )
        if self.record_index < 0:
            raise ValueError(
                f"record_index must be a non-negative int, got {self.record_index}"
            )
        _require_non_empty_str(self.question_id, "question_id")

    def validate_against_workspace(self, workspace: ReviewerWorkspace) -> ReferenceUnitRecord:
        """Mechanically validate this reference against a supplied ReviewerWorkspace.

        Checks:
        1. workspace.reviewer_role matches self.reviewer_role
        2. self.record_index is within bounds of workspace.records
        3. referenced record's question_id matches self.question_id

        Returns the referenced ReferenceUnitRecord.
        """
        if workspace.reviewer_role != self.reviewer_role:
            raise ReviewerRoleMismatchError(
                f"Reference reviewer_role '{self.reviewer_role}' does not match "
                f"workspace reviewer_role '{workspace.reviewer_role}'"
            )
        if not (0 <= self.record_index < len(workspace.records)):
            raise IndexError(
                f"record_index {self.record_index} out of bounds for workspace "
                f"with {len(workspace.records)} records"
            )
        raw_record = workspace.records[self.record_index]
        rec_qid = raw_record.get("question_id") if isinstance(raw_record, dict) else raw_record.question_id
        if rec_qid != self.question_id:
            raise ValueError(
                f"Referenced record question_id '{rec_qid}' does not match "
                f"reference question_id '{self.question_id}'"
            )
        if isinstance(raw_record, ReferenceUnitRecord):
            return raw_record
        return ReferenceUnitRecord.model_validate(raw_record)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewerRecordRef:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for ReviewerRecordRef, got {type(data).__name__}")
        role = data.get("reviewer_role")
        idx = data.get("record_index")
        qid = data.get("question_id")
        return cls(
            reviewer_role=role,  # type: ignore[arg-type]
            record_index=idx,  # type: ignore[arg-type]
            question_id=qid,  # type: ignore[arg-type]
        )


@dataclass
class CompletenessAttestation:
    """Human-entered completeness attestations for question reconciliation.

    PROTOCOL REQUIREMENT (Section K):
    Human reconciliation must verify completeness across both submissions and
    all 8 frozen evidence passages.
    The software MUST NOT set these attestations automatically based on semantic
    inspection. They must be explicitly attested by human reviewers.
    """

    considered_both_submissions: bool = False
    all_8_passages_checked: bool = False
    omitted_targets_examined: bool = False
    new_target_additions_checked_and_logged: bool = False
    methodological_issues_checked: bool = False
    unresolved_methodological_issue_present: bool = False
    human_attestor: str = ""
    attestation_notes: str = ""

    def validate_current_state(self) -> None:
        """Strictly validate current values of mutable completeness attestation fields."""
        _require_bool(self.considered_both_submissions, "considered_both_submissions")
        _require_bool(self.all_8_passages_checked, "all_8_passages_checked")
        _require_bool(self.omitted_targets_examined, "omitted_targets_examined")
        _require_bool(self.new_target_additions_checked_and_logged, "new_target_additions_checked_and_logged")
        _require_bool(self.methodological_issues_checked, "methodological_issues_checked")
        _require_bool(self.unresolved_methodological_issue_present, "unresolved_methodological_issue_present")
        if not isinstance(self.human_attestor, str):
            raise TypeError(f"Field 'human_attestor' must be of type str, got {type(self.human_attestor).__name__}")
        if not isinstance(self.attestation_notes, str):
            raise TypeError(f"Field 'attestation_notes' must be of type str, got {type(self.attestation_notes).__name__}")

    def __post_init__(self) -> None:
        self.validate_current_state()

    def is_complete(self) -> bool:
        """Return True if all required process attestations are confirmed and no unresolved issue exists."""
        self.validate_current_state()
        return (
            self.considered_both_submissions
            and self.all_8_passages_checked
            and self.omitted_targets_examined
            and self.new_target_additions_checked_and_logged
            and self.methodological_issues_checked
            and not self.unresolved_methodological_issue_present
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "considered_both_submissions": self.considered_both_submissions,
            "all_8_passages_checked": self.all_8_passages_checked,
            "omitted_targets_examined": self.omitted_targets_examined,
            "new_target_additions_checked_and_logged": self.new_target_additions_checked_and_logged,
            "methodological_issues_checked": self.methodological_issues_checked,
            "unresolved_methodological_issue_present": self.unresolved_methodological_issue_present,
            "human_attestor": self.human_attestor,
            "attestation_notes": self.attestation_notes,
            "is_complete": self.is_complete(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletenessAttestation:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for CompletenessAttestation, got {type(data).__name__}")
        return cls(
            considered_both_submissions=_require_bool(
                data.get("considered_both_submissions", False), "considered_both_submissions"
            ),
            all_8_passages_checked=_require_bool(
                data.get("all_8_passages_checked", False), "all_8_passages_checked"
            ),
            omitted_targets_examined=_require_bool(
                data.get("omitted_targets_examined", False), "omitted_targets_examined"
            ),
            new_target_additions_checked_and_logged=_require_bool(
                data.get("new_target_additions_checked_and_logged", False),
                "new_target_additions_checked_and_logged",
            ),
            methodological_issues_checked=_require_bool(
                data.get("methodological_issues_checked", False), "methodological_issues_checked"
            ),
            unresolved_methodological_issue_present=_require_bool(
                data.get("unresolved_methodological_issue_present", False),
                "unresolved_methodological_issue_present",
            ),
            human_attestor=str(data.get("human_attestor", "")),
            attestation_notes=str(data.get("attestation_notes", "")),
        )


@dataclass
class NewTargetAuditEntry:
    """Mechanical audit log entry for a new target discovered during reconciliation.

    PROTOCOL REQUIREMENT (Section K):
    Any newly identified target must be recorded as a reconciliation addition,
    supported by frozen evidence, accompanied by relevance/support reasoning,
    and explicitly reviewed and acknowledged by both Reviewer A and Reviewer B.

    The software DOES NOT generate the target, propose wording, choose evidence,
    or decide eligibility. Actual semantic content is human-entered.
    """

    question_id: str
    human_authored_reason: str
    reviewer_a_acknowledged: bool = False
    reviewer_b_acknowledged: bool = False
    supporting_refs: list[ReviewerRecordRef] = field(default_factory=list)
    audit_status: NewTargetStatus = "pending"
    audit_notes: str = ""

    def validate_current_state(self) -> None:
        """Strictly validate current values of mutable new-target audit entry fields."""
        _require_non_empty_str(self.question_id, "question_id")
        _require_non_empty_str(self.human_authored_reason, "human_authored_reason")
        _require_bool(self.reviewer_a_acknowledged, "reviewer_a_acknowledged")
        _require_bool(self.reviewer_b_acknowledged, "reviewer_b_acknowledged")
        if self.audit_status not in ALLOWED_NEW_TARGET_STATUSES:
            raise ValueError(
                f"Invalid audit_status '{self.audit_status}': must be one of {ALLOWED_NEW_TARGET_STATUSES}"
            )
        if not isinstance(self.audit_notes, str):
            raise TypeError(f"Field 'audit_notes' must be of type str, got {type(self.audit_notes).__name__}")
        if not isinstance(self.supporting_refs, list):
            raise TypeError(f"Field 'supporting_refs' must be a list, got {type(self.supporting_refs).__name__}")
        for ref in self.supporting_refs:
            if not isinstance(ref, ReviewerRecordRef):
                raise TypeError(f"Expected ReviewerRecordRef in supporting_refs, got {type(ref).__name__}")
            if ref.question_id != self.question_id:
                raise ValueError(
                    f"Supporting ref question_id '{ref.question_id}' does not match entry question_id '{self.question_id}'"
                )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "question_id": self.question_id,
            "human_authored_reason": self.human_authored_reason,
            "reviewer_a_acknowledged": self.reviewer_a_acknowledged,
            "reviewer_b_acknowledged": self.reviewer_b_acknowledged,
            "supporting_refs": [
                {
                    "reviewer_role": r.reviewer_role,
                    "record_index": r.record_index,
                    "question_id": r.question_id,
                }
                for r in self.supporting_refs
            ],
            "audit_status": self.audit_status,
            "audit_notes": self.audit_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NewTargetAuditEntry:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for NewTargetAuditEntry, got {type(data).__name__}")
        qid = _require_non_empty_str(data.get("question_id"), "question_id")
        reason = data.get("human_authored_reason")
        if not isinstance(reason, str):
            raise TypeError("human_authored_reason must be a string")
        ack_a = _require_bool(data.get("reviewer_a_acknowledged", False), "reviewer_a_acknowledged")
        ack_b = _require_bool(data.get("reviewer_b_acknowledged", False), "reviewer_b_acknowledged")
        status = data.get("audit_status", "pending")
        if status not in ALLOWED_NEW_TARGET_STATUSES:
            raise ValueError(f"Invalid audit_status '{status}': must be one of {ALLOWED_NEW_TARGET_STATUSES}")
        refs_raw = data.get("supporting_refs", [])
        if not isinstance(refs_raw, list):
            raise TypeError("supporting_refs must be a list")
        refs = [ReviewerRecordRef.from_dict(r) for r in refs_raw]
        return cls(
            question_id=qid,
            human_authored_reason=reason,
            reviewer_a_acknowledged=ack_a,
            reviewer_b_acknowledged=ack_b,
            supporting_refs=refs,
            audit_status=status,
            audit_notes=str(data.get("audit_notes", "")),
        )


@dataclass
class UnresolvedDisagreementAuditEntry:
    """Mechanical container for unresolved disagreement between reviewers.

    PROTOCOL REQUIREMENT (Section K):
    Unresolved disagreements go to a prospectively designated third human adjudicator.
    The software DOES NOT adjudicate disagreements, pick winners, or infer resolutions.
    """

    question_id: str
    involved_refs: list[ReviewerRecordRef] = field(default_factory=list)
    human_authored_disagreement_note: str = ""
    status: DisagreementStatus = "unresolved"
    third_adjudicator_required: bool = False
    adjudicator_notes: str = ""

    def validate_current_state(self) -> None:
        """Strictly validate current values of mutable disagreement audit entry fields."""
        _require_non_empty_str(self.question_id, "question_id")
        if not isinstance(self.human_authored_disagreement_note, str):
            raise TypeError(
                f"human_authored_disagreement_note must be a string, got {type(self.human_authored_disagreement_note).__name__}"
            )
        if self.status not in ALLOWED_DISAGREEMENT_STATUSES:
            raise ValueError(
                f"Invalid disagreement status '{self.status}': must be one of {ALLOWED_DISAGREEMENT_STATUSES}"
            )
        _require_bool(self.third_adjudicator_required, "third_adjudicator_required")
        if not isinstance(self.adjudicator_notes, str):
            raise TypeError(f"adjudicator_notes must be a string, got {type(self.adjudicator_notes).__name__}")
        if not isinstance(self.involved_refs, list):
            raise TypeError(f"involved_refs must be a list, got {type(self.involved_refs).__name__}")
        for ref in self.involved_refs:
            if not isinstance(ref, ReviewerRecordRef):
                raise TypeError(f"Expected ReviewerRecordRef in involved_refs, got {type(ref).__name__}")
            if ref.question_id != self.question_id:
                raise ValueError(
                    f"Involved ref question_id '{ref.question_id}' does not match entry question_id '{self.question_id}'"
                )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "question_id": self.question_id,
            "involved_refs": [
                {
                    "reviewer_role": r.reviewer_role,
                    "record_index": r.record_index,
                    "question_id": r.question_id,
                }
                for r in self.involved_refs
            ],
            "human_authored_disagreement_note": self.human_authored_disagreement_note,
            "status": self.status,
            "third_adjudicator_required": self.third_adjudicator_required,
            "adjudicator_notes": self.adjudicator_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnresolvedDisagreementAuditEntry:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for UnresolvedDisagreementAuditEntry, got {type(data).__name__}")
        qid = _require_non_empty_str(data.get("question_id"), "question_id")
        note = data.get("human_authored_disagreement_note", "")
        if not isinstance(note, str):
            raise TypeError("human_authored_disagreement_note must be a string")
        status = data.get("status", "unresolved")
        if status not in ALLOWED_DISAGREEMENT_STATUSES:
            raise ValueError(f"Invalid disagreement status '{status}': must be one of {ALLOWED_DISAGREEMENT_STATUSES}")
        third_adj = _require_bool(data.get("third_adjudicator_required", False), "third_adjudicator_required")
        refs_raw = data.get("involved_refs", [])
        if not isinstance(refs_raw, list):
            raise TypeError("involved_refs must be a list")
        refs = [ReviewerRecordRef.from_dict(r) for r in refs_raw]
        return cls(
            question_id=qid,
            involved_refs=refs,
            human_authored_disagreement_note=note,
            status=status,
            third_adjudicator_required=third_adj,
            adjudicator_notes=str(data.get("adjudicator_notes", "")),
        )


@dataclass
class QuestionReconciliationAudit:
    """Per-question reconciliation audit container.

    Administrative state container for human reconciliation progress on a single question.
    Encodes NO semantic relationship or decision logic.
    """

    question_id: str
    reviewer_a_refs: list[ReviewerRecordRef] = field(default_factory=list)
    reviewer_b_refs: list[ReviewerRecordRef] = field(default_factory=list)
    human_notes: str = ""
    reconciliation_state: ReconciliationState = "unreviewed"
    completeness_attestation: CompletenessAttestation = field(default_factory=CompletenessAttestation)
    unresolved_items: list[UnresolvedDisagreementAuditEntry] = field(default_factory=list)
    addition_log: list[NewTargetAuditEntry] = field(default_factory=list)
    adjudication_required: bool = False
    exact_duplicate_pairs: list[tuple[ReviewerRecordRef, ReviewerRecordRef]] = field(default_factory=list)

    def validate_current_state(self) -> None:
        """Strictly validate current values of mutable question reconciliation audit fields."""
        _require_non_empty_str(self.question_id, "question_id")
        if self.reconciliation_state not in ALLOWED_RECONCILIATION_STATES:
            raise ReconciliationStateError(
                f"Invalid reconciliation_state '{self.reconciliation_state}': must be one of {ALLOWED_RECONCILIATION_STATES}"
            )
        _require_bool(self.adjudication_required, "adjudication_required")
        if not isinstance(self.human_notes, str):
            raise TypeError(f"human_notes must be a string, got {type(self.human_notes).__name__}")
        if not isinstance(self.completeness_attestation, CompletenessAttestation):
            raise TypeError(
                f"completeness_attestation must be CompletenessAttestation, got {type(self.completeness_attestation).__name__}"
            )
        self.completeness_attestation.validate_current_state()

        if not isinstance(self.reviewer_a_refs, list):
            raise TypeError(f"reviewer_a_refs must be a list, got {type(self.reviewer_a_refs).__name__}")
        if not isinstance(self.reviewer_b_refs, list):
            raise TypeError(f"reviewer_b_refs must be a list, got {type(self.reviewer_b_refs).__name__}")
        if not isinstance(self.addition_log, list):
            raise TypeError(f"addition_log must be a list, got {type(self.addition_log).__name__}")
        if not isinstance(self.unresolved_items, list):
            raise TypeError(f"unresolved_items must be a list, got {type(self.unresolved_items).__name__}")
        if not isinstance(self.exact_duplicate_pairs, list):
            raise TypeError(f"exact_duplicate_pairs must be a list, got {type(self.exact_duplicate_pairs).__name__}")

        for entry in self.addition_log:
            if not isinstance(entry, NewTargetAuditEntry):
                raise TypeError(f"Expected NewTargetAuditEntry in addition_log, got {type(entry).__name__}")
            entry.validate_current_state()

        for item in self.unresolved_items:
            if not isinstance(item, UnresolvedDisagreementAuditEntry):
                raise TypeError(f"Expected UnresolvedDisagreementAuditEntry in unresolved_items, got {type(item).__name__}")
            item.validate_current_state()

        self._validate_provenance()

    def __post_init__(self) -> None:
        self.validate_current_state()
        if self.reconciliation_state == "human_review_complete":
            self.validate_ready_for_human_review_complete()

    def _validate_provenance(self) -> None:
        """Validate parent/child question_id and reviewer role provenance consistency."""
        for ref in self.reviewer_a_refs:
            if not isinstance(ref, ReviewerRecordRef):
                raise TypeError(f"Expected ReviewerRecordRef in reviewer_a_refs, got {type(ref).__name__}")
            if ref.reviewer_role != "reviewer_a":
                raise ValueError(f"Ref in reviewer_a_refs has role '{ref.reviewer_role}', must have role 'reviewer_a' (reviewer_role='reviewer_a')")
            if ref.question_id != self.question_id:
                raise ValueError(
                    f"Ref in reviewer_a_refs has question_id '{ref.question_id}', does not match parent question_id '{self.question_id}'"
                )

        for ref in self.reviewer_b_refs:
            if not isinstance(ref, ReviewerRecordRef):
                raise TypeError(f"Expected ReviewerRecordRef in reviewer_b_refs, got {type(ref).__name__}")
            if ref.reviewer_role != "reviewer_b":
                raise ValueError(f"Ref in reviewer_b_refs has role '{ref.reviewer_role}', must have role 'reviewer_b' (reviewer_role='reviewer_b')")
            if ref.question_id != self.question_id:
                raise ValueError(
                    f"Ref in reviewer_b_refs has question_id '{ref.question_id}', does not match parent question_id '{self.question_id}'"
                )

        for entry in self.addition_log:
            if not isinstance(entry, NewTargetAuditEntry):
                raise TypeError(f"Expected NewTargetAuditEntry in addition_log, got {type(entry).__name__}")
            if entry.question_id != self.question_id:
                raise ValueError(
                    f"addition_log entry has question_id '{entry.question_id}', does not match parent question_id '{self.question_id}'"
                )
            for ref in entry.supporting_refs:
                if ref.question_id != self.question_id:
                    raise ValueError(
                        f"supporting_ref has question_id '{ref.question_id}', does not match parent question_id '{self.question_id}'"
                    )

        for entry in self.unresolved_items:
            if not isinstance(entry, UnresolvedDisagreementAuditEntry):
                raise TypeError(f"Expected UnresolvedDisagreementAuditEntry in unresolved_items, got {type(entry).__name__}")
            if entry.question_id != self.question_id:
                raise ValueError(
                    f"unresolved_item has question_id '{entry.question_id}', does not match parent question_id '{self.question_id}'"
                )
            for ref in entry.involved_refs:
                if ref.question_id != self.question_id:
                    raise ValueError(
                        f"involved_ref has question_id '{ref.question_id}', does not match parent question_id '{self.question_id}'"
                    )

        for p in self.exact_duplicate_pairs:
            if not isinstance(p, (tuple, list)) or len(p) != 2:
                raise ValueError("exact_duplicate_pairs entries must be pairs (tuple of 2 refs)")
            ref_a, ref_b = p
            if not isinstance(ref_a, ReviewerRecordRef) or not isinstance(ref_b, ReviewerRecordRef):
                raise TypeError("exact_duplicate_pairs must contain ReviewerRecordRef objects")
            if ref_a.reviewer_role != "reviewer_a":
                raise ValueError(f"first ref must have role 'reviewer_a', got '{ref_a.reviewer_role}'")
            if ref_b.reviewer_role != "reviewer_b":
                raise ValueError(f"second ref must have role 'reviewer_b', got '{ref_b.reviewer_role}'")
            if ref_a.question_id != self.question_id:
                raise ValueError(f"first ref in duplicate pair has question_id '{ref_a.question_id}', does not match parent question_id '{self.question_id}'")
            if ref_b.question_id != self.question_id:
                raise ValueError(f"second ref in duplicate pair has question_id '{ref_b.question_id}', does not match parent question_id '{self.question_id}'")

    def validate_ready_for_human_review_complete(self) -> None:
        """Master fail-closed validator for human_review_complete transition.

        Validates:
        1. Current-state structural validation
        2. Process completeness attestations are all True
        3. unresolved_methodological_issue_present == False
        4. adjudication_required == False
        5. No unresolved or referred_to_adjudication items
        6. Every addition entry has A and B acks, final status (accepted/rejected), and non-empty reason
        7. Provenance and cross-question consistency across all references
        """
        # Task 6: At START of validate_ready_for_human_review_complete: run current-state validation
        try:
            self.validate_current_state()
        except (ValueError, TypeError) as e:
            raise ReconciliationStateError(
                f"Cannot mark question '{self.question_id}' as 'human_review_complete': {e}"
            ) from e

        # 1 & 2. Completeness attestations
        if not self.completeness_attestation.is_complete():
            raise ReconciliationStateError(
                f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                "human completeness attestations are incomplete or unresolved methodological issue is present"
            )
        if self.completeness_attestation.unresolved_methodological_issue_present:
            raise ReconciliationStateError(
                f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                "unresolved methodological issue is present (reported present)"
            )

        # 3. Top-level adjudication flag
        if self.adjudication_required:
            raise ReconciliationStateError(
                f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                "adjudication_required flag is True (adjudication is marked as required)"
            )

        # 4. Disagreement items
        for item in self.unresolved_items:
            if item.status in ("unresolved", "referred_to_adjudication"):
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    f"unresolved disagreements present: item has non-final status '{item.status}'"
                )
            if item.third_adjudicator_required and item.status != "adjudicated":
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    f"third adjudicator required for disagreement but status is '{item.status}'"
                )

        # 5. Addition log items
        for entry in self.addition_log:
            if not entry.human_authored_reason or not entry.human_authored_reason.strip():
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    "addition entry requires non-empty human_authored_reason"
                )
            if not entry.reviewer_a_acknowledged:
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    "addition entry missing Reviewer A acknowledgement (must be acknowledged by Reviewer A)"
                )
            if not entry.reviewer_b_acknowledged:
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    "addition entry missing Reviewer B acknowledgement (must be acknowledged by Reviewer B)"
                )
            if entry.audit_status == "pending":
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    "addition log entries must have final status (accepted/rejected), pending addition blocks"
                )
            if entry.audit_status not in ("accepted", "rejected"):
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    f"addition entry has invalid status '{entry.audit_status}'"
                )

        # 6. Revalidate provenance fail-closed
        try:
            self._validate_provenance()
        except (ValueError, TypeError) as e:
            raise ReconciliationStateError(
                f"Cannot mark question '{self.question_id}' as 'human_review_complete': {e}"
            ) from e

    def set_reconciliation_state(self, state: ReconciliationState) -> None:
        """Update reconciliation administrative state with fail-closed validation."""
        if state not in ALLOWED_RECONCILIATION_STATES:
            raise ReconciliationStateError(
                f"Invalid reconciliation_state '{state}': must be one of {ALLOWED_RECONCILIATION_STATES}"
            )
        if state == "human_review_complete":
            self.validate_ready_for_human_review_complete()
        self.reconciliation_state = state

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        if self.reconciliation_state == "human_review_complete":
            self.validate_ready_for_human_review_complete()
        return {
            "question_id": self.question_id,
            "reviewer_a_refs": [
                {
                    "reviewer_role": r.reviewer_role,
                    "record_index": r.record_index,
                    "question_id": r.question_id,
                }
                for r in self.reviewer_a_refs
            ],
            "reviewer_b_refs": [
                {
                    "reviewer_role": r.reviewer_role,
                    "record_index": r.record_index,
                    "question_id": r.question_id,
                }
                for r in self.reviewer_b_refs
            ],
            "human_notes": self.human_notes,
            "reconciliation_state": self.reconciliation_state,
            "completeness_attestation": self.completeness_attestation.to_dict(),
            "unresolved_items": [item.to_dict() for item in self.unresolved_items],
            "addition_log": [entry.to_dict() for entry in self.addition_log],
            "adjudication_required": self.adjudication_required,
            "exact_duplicate_pairs": [
                (
                    {
                        "reviewer_role": p[0].reviewer_role,
                        "record_index": p[0].record_index,
                        "question_id": p[0].question_id,
                    },
                    {
                        "reviewer_role": p[1].reviewer_role,
                        "record_index": p[1].record_index,
                        "question_id": p[1].question_id,
                    },
                )
                for p in self.exact_duplicate_pairs
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuestionReconciliationAudit:
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict for QuestionReconciliationAudit, got {type(data).__name__}")
        qid = _require_non_empty_str(data.get("question_id"), "question_id")
        state = data.get("reconciliation_state", "unreviewed")
        if state not in ALLOWED_RECONCILIATION_STATES:
            raise ReconciliationStateError(
                f"Invalid reconciliation_state '{state}': must be one of {ALLOWED_RECONCILIATION_STATES}"
            )
        adj_req = _require_bool(data.get("adjudication_required", False), "adjudication_required")

        a_refs_raw = data.get("reviewer_a_refs", [])
        if not isinstance(a_refs_raw, list):
            raise TypeError("reviewer_a_refs must be a list")
        a_refs = [ReviewerRecordRef.from_dict(r) for r in a_refs_raw]

        b_refs_raw = data.get("reviewer_b_refs", [])
        if not isinstance(b_refs_raw, list):
            raise TypeError("reviewer_b_refs must be a list")
        b_refs = [ReviewerRecordRef.from_dict(r) for r in b_refs_raw]

        dup_pairs_raw = data.get("exact_duplicate_pairs", [])
        if not isinstance(dup_pairs_raw, list):
            raise TypeError("exact_duplicate_pairs must be a list")
        dup_pairs = [
            (
                ReviewerRecordRef.from_dict(p[0]),
                ReviewerRecordRef.from_dict(p[1]),
            )
            for p in dup_pairs_raw
        ]

        unresolved_raw = data.get("unresolved_items", [])
        if not isinstance(unresolved_raw, list):
            raise TypeError("unresolved_items must be a list")
        unresolved = [
            UnresolvedDisagreementAuditEntry.from_dict(item)
            for item in unresolved_raw
        ]

        addition_raw = data.get("addition_log", [])
        if not isinstance(addition_raw, list):
            raise TypeError("addition_log must be a list")
        addition = [
            NewTargetAuditEntry.from_dict(entry)
            for entry in addition_raw
        ]

        instance = cls(
            question_id=qid,
            reviewer_a_refs=a_refs,
            reviewer_b_refs=b_refs,
            human_notes=str(data.get("human_notes", "")),
            reconciliation_state=state,
            completeness_attestation=CompletenessAttestation.from_dict(
                data.get("completeness_attestation", {})
            ),
            unresolved_items=unresolved,
            addition_log=addition,
            adjudication_required=adj_req,
            exact_duplicate_pairs=dup_pairs,
        )

        if state == "human_review_complete":
            instance.validate_ready_for_human_review_complete()

        return instance


def find_exact_duplicate_records(
    workspace_a: ReviewerWorkspace,
    workspace_b: ReviewerWorkspace,
    question_id: str | None = None,
) -> list[tuple[ReviewerRecordRef, ReviewerRecordRef]]:
    """Mechanically identify exact, byte-for-byte / model-for-model duplicate records between A and B.

    ADVISORY AND MECHANICAL ONLY:
    Under REFERENCE_UNIT_PROTOCOL_V1.md Section F:
    "Humans decide semantic duplication. Mechanical tools may flag exact matches for review."

    CRITICAL PRINCIPLE: EXACT DUPLICATE != SEMANTIC EQUIVALENCE.
    This function:
    - ONLY flags records whose serialized dictionary representation is strictly identical.
    - DOES NOT perform fuzzy matching, whitespace normalization, case-folding,
      or semantic comparison.
    - NEVER merges, edits, or deletes records.

    FORMAL GATE:
    In Phase B2B, this helper is strictly SYNTHETIC-ONLY. Comparing formal reviewer
    workspaces before cryptographic submission receipts (Phase B3+) is forbidden.
    """
    if getattr(workspace_a, "workspace_kind", None) != "synthetic" or getattr(workspace_b, "workspace_kind", None) != "synthetic":
        raise FormalReconciliationGateError(
            "find_exact_duplicate_records cannot consume formal administrative workspaces or compare formal reviewer workspaces in Phase B2B. "
            "Formal submissions must be cryptographically locked and receipt-hashed before reconciliation comparison."
        )

    if workspace_a.reviewer_role != "reviewer_a":
        raise ReviewerRoleMismatchError("workspace_a must have reviewer_role 'reviewer_a'")
    if workspace_b.reviewer_role != "reviewer_b":
        raise ReviewerRoleMismatchError("workspace_b must have reviewer_role 'reviewer_b'")

    duplicates: list[tuple[ReviewerRecordRef, ReviewerRecordRef]] = []

    records_b_by_q: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for idx_b, raw_b in enumerate(workspace_b.records):
        qid_b = raw_b.get("question_id") if isinstance(raw_b, dict) else raw_b.question_id
        if question_id is not None and qid_b != question_id:
            continue
        dump_b = raw_b if isinstance(raw_b, dict) else raw_b.model_dump(mode="json")
        records_b_by_q.setdefault(qid_b, []).append((idx_b, dump_b))

    for idx_a, raw_a in enumerate(workspace_a.records):
        qid_a = raw_a.get("question_id") if isinstance(raw_a, dict) else raw_a.question_id
        if question_id is not None and qid_a != question_id:
            continue
        dump_a = raw_a if isinstance(raw_a, dict) else raw_a.model_dump(mode="json")
        for idx_b, dump_b in records_b_by_q.get(qid_a, []):
            if dump_a == dump_b:
                ref_a = ReviewerRecordRef(
                    reviewer_role="reviewer_a",
                    record_index=idx_a,
                    question_id=qid_a,
                )
                ref_b = ReviewerRecordRef(
                    reviewer_role="reviewer_b",
                    record_index=idx_b,
                    question_id=qid_a,
                )
                duplicates.append((ref_a, ref_b))

    return duplicates


@dataclass
class ReconciliationAuditWorkspace:
    """Workspace container for human reference-unit reconciliation audit.

    Bound metadata:
    - study_id: cross-perspective-advisory-ablation-v1
    - protocol_id: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
    - protocol_hash: 5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b
    - reviewer_a_role: reviewer_a
    - reviewer_b_role: reviewer_b
    - workspace_kind: synthetic (formal creation fails closed in B2B)
    - question_audits: dict[question_id, QuestionReconciliationAudit]
    - local_only_notice: Local-only notice string

    PRESERVATION AND PURITY:
    - Preserves reviewer origin for every referenced record.
    - Contains NO method to build an automatic union or output a reconciled reference set.
    """

    study_id: str = STUDY_ID
    protocol_id: str = PROTOCOL_ID
    protocol_hash: str = FROZEN_PROTOCOL_BYTE_SHA256
    reviewer_a_role: str = "reviewer_a"
    reviewer_b_role: str = "reviewer_b"
    workspace_kind: str = "synthetic"
    question_audits: dict[str, QuestionReconciliationAudit] = field(default_factory=dict)
    local_only_notice: str = LOCAL_ONLY_NOTICE

    def validate_current_state(self) -> None:
        """Strictly validate current values of mutable workspace fields."""
        # Part G.1: Formal gate on direct dataclass construction
        if self.workspace_kind == "formal":
            raise FormalReconciliationGateError(
                "Formal reconciliation cannot be constructed in Phase B2B. "
                "Formal reconciliation workspace creation is prohibited. "
                "Under frozen protocol Section J, both Reviewer A and Reviewer B submissions "
                "must be cryptographically locked and receipt-hashed (Phase B3+) before "
                "formal reconciliation may be initialized."
            )
        if self.workspace_kind != "synthetic":
            raise ValueError(
                f"Invalid workspace_kind '{self.workspace_kind}': only 'synthetic' is permitted in Phase B2B"
            )

        # Part H: Fixed metadata invariants
        if self.study_id != STUDY_ID:
            raise ValueError(f"Invalid study_id '{self.study_id}': expected '{STUDY_ID}'")
        if self.protocol_id != PROTOCOL_ID:
            raise ValueError(f"Invalid protocol_id '{self.protocol_id}': expected '{PROTOCOL_ID}'")
        if self.protocol_hash != FROZEN_PROTOCOL_BYTE_SHA256:
            raise ValueError(f"Invalid protocol_hash '{self.protocol_hash}': expected '{FROZEN_PROTOCOL_BYTE_SHA256}'")
        if self.reviewer_a_role != "reviewer_a":
            raise ValueError(f"Invalid reviewer_a_role '{self.reviewer_a_role}': expected 'reviewer_a'")
        if self.reviewer_b_role != "reviewer_b":
            raise ValueError(f"Invalid reviewer_b_role '{self.reviewer_b_role}': expected 'reviewer_b'")
        if self.local_only_notice != LOCAL_ONLY_NOTICE:
            raise ValueError(f"Invalid local_only_notice '{self.local_only_notice}': expected '{LOCAL_ONLY_NOTICE}'")

        # Part I: Question map consistency
        if not isinstance(self.question_audits, dict):
            raise TypeError(f"question_audits must be a dictionary, got {type(self.question_audits).__name__}")
        for qid, audit in self.question_audits.items():
            _require_non_empty_str(qid, "question_audits key")
            if not isinstance(audit, QuestionReconciliationAudit):
                raise TypeError(f"Expected QuestionReconciliationAudit for key '{qid}', got {type(audit).__name__}")
            if qid != audit.question_id:
                raise ValueError(f"question_audits key '{qid}' does not match audit.question_id '{audit.question_id}'")
            audit.validate_current_state()

    def __post_init__(self) -> None:
        self.validate_current_state()

    @property
    def questions(self) -> list[str]:
        return list(self.question_audits.keys())

    def get_question_audit(self, question_id: str) -> QuestionReconciliationAudit:
        if question_id not in self.question_audits:
            raise KeyError(f"Question '{question_id}' not found in reconciliation workspace")
        return self.question_audits[question_id]

    @classmethod
    def create_formal_blank(cls, *args: Any, **kwargs: Any) -> Any:
        """Formal execution gate: fails closed in Phase B2B."""
        raise FormalReconciliationGateError(
            "Formal reconciliation cannot begin from administrative B2A workspaces alone. "
            "Under frozen protocol Section J, both Reviewer A and Reviewer B submissions "
            "must be cryptographically locked and receipt-hashed (Phase B3+) before "
            "formal reconciliation may be initialized."
        )

    @classmethod
    def from_formal_workspaces(cls, *args: Any, **kwargs: Any) -> Any:
        """Formal execution gate: fails closed in Phase B2B."""
        raise FormalReconciliationGateError(
            "Formal reconciliation cannot begin from administrative B2A workspaces alone. "
            "Under frozen protocol Section J, both Reviewer A and Reviewer B submissions "
            "must be cryptographically locked and receipt-hashed (Phase B3+) before "
            "formal reconciliation may be initialized."
        )

    @classmethod
    def create_synthetic_blank(
        cls,
        questions: list[str],
        workspace_a: ReviewerWorkspace | None = None,
        workspace_b: ReviewerWorkspace | None = None,
    ) -> ReconciliationAuditWorkspace:
        """Create a synthetic reconciliation audit workspace for test and fixture development.

        Strictly marked workspace_kind = 'synthetic'. Never claims formal authority.
        """
        if not questions:
            raise ValueError("questions list cannot be empty")

        seen: set[str] = set()
        for qid in questions:
            _require_non_empty_str(qid, "question_id")
            if qid in seen:
                raise ValueError(f"Duplicate question ID '{qid}' in questions list")
            seen.add(qid)

        if workspace_a is not None and getattr(workspace_a, "workspace_kind", None) != "synthetic":
            raise TypeError("Cannot bind non-synthetic workspace_a to synthetic reconciliation workspace")
        if workspace_b is not None and getattr(workspace_b, "workspace_kind", None) != "synthetic":
            raise TypeError("Cannot bind non-synthetic workspace_b to synthetic reconciliation workspace")
        if workspace_a is not None and workspace_a.reviewer_role != "reviewer_a":
            raise ReviewerRoleMismatchError("workspace_a must have reviewer_role 'reviewer_a'")
        if workspace_b is not None and workspace_b.reviewer_role != "reviewer_b":
            raise ReviewerRoleMismatchError("workspace_b must have reviewer_role 'reviewer_b'")

        audits: dict[str, QuestionReconciliationAudit] = {}
        for qid in questions:
            q_audit = QuestionReconciliationAudit(question_id=qid)
            if workspace_a is not None:
                for idx, rec in enumerate(workspace_a.records):
                    rec_qid = rec.get("question_id") if isinstance(rec, dict) else rec.question_id
                    if rec_qid == qid:
                        q_audit.reviewer_a_refs.append(
                            ReviewerRecordRef(reviewer_role="reviewer_a", record_index=idx, question_id=qid)
                        )
            if workspace_b is not None:
                for idx, rec in enumerate(workspace_b.records):
                    rec_qid = rec.get("question_id") if isinstance(rec, dict) else rec.question_id
                    if rec_qid == qid:
                        q_audit.reviewer_b_refs.append(
                            ReviewerRecordRef(reviewer_role="reviewer_b", record_index=idx, question_id=qid)
                        )
            audits[qid] = q_audit

        if workspace_a is not None and workspace_b is not None:
            dup_pairs = find_exact_duplicate_records(workspace_a, workspace_b)
            for ref_a, ref_b in dup_pairs:
                if ref_a.question_id in audits:
                    audits[ref_a.question_id].exact_duplicate_pairs.append((ref_a, ref_b))

        return cls(
            workspace_kind="synthetic",
            question_audits=audits,
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        for audit in self.question_audits.values():
            if audit.reconciliation_state == "human_review_complete":
                audit.validate_ready_for_human_review_complete()
        return {
            "study_id": self.study_id,
            "protocol_id": self.protocol_id,
            "protocol_hash": self.protocol_hash,
            "reviewer_a_role": self.reviewer_a_role,
            "reviewer_b_role": self.reviewer_b_role,
            "workspace_kind": self.workspace_kind,
            "local_only_notice": self.local_only_notice,
            "question_audits": {qid: audit.to_dict() for qid, audit in self.question_audits.items()},
        }

    def save_local(self, file_path: Path) -> None:
        """Save synthetic reconciliation audit workspace to local disk."""
        data = self.to_dict()
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReconciliationAuditWorkspace:
        """Deserialize synthetic reconciliation audit workspace with fail-closed validation."""
        if not isinstance(data, dict):
            raise TypeError("Expected dictionary for reconciliation workspace")

        # Part H & G.1: Fail-closed on missing or altered fixed metadata
        if "workspace_kind" not in data:
            raise ValueError("Missing 'workspace_kind' in persisted workspace")
        if data["workspace_kind"] == "formal":
            raise FormalReconciliationGateError(
                "Formal reconciliation cannot be constructed in Phase B2B. "
                "Formal reconciliation workspace creation is prohibited."
            )
        if data["workspace_kind"] != "synthetic":
            raise ValueError(
                f"Invalid workspace_kind '{data['workspace_kind']}': only 'synthetic' is permitted in Phase B2B"
            )

        if data.get("study_id") != STUDY_ID:
            raise ValueError(f"study_id mismatch: {data.get('study_id')} != {STUDY_ID}")
        if data.get("protocol_id") != PROTOCOL_ID:
            raise ValueError(f"protocol_id mismatch: {data.get('protocol_id')} != {PROTOCOL_ID}")
        if data.get("protocol_hash") != FROZEN_PROTOCOL_BYTE_SHA256:
            raise ValueError(f"protocol_hash mismatch: {data.get('protocol_hash')} != {FROZEN_PROTOCOL_BYTE_SHA256}")
        if data.get("reviewer_a_role") != "reviewer_a":
            raise ValueError(f"reviewer_a_role mismatch: {data.get('reviewer_a_role')} != 'reviewer_a'")
        if data.get("reviewer_b_role") != "reviewer_b":
            raise ValueError(f"reviewer_b_role mismatch: {data.get('reviewer_b_role')} != 'reviewer_b'")
        if data.get("local_only_notice") != LOCAL_ONLY_NOTICE:
            raise ValueError("local_only_notice mismatch")

        # Part I & J: Validate question_audits
        raw_audits = data.get("question_audits", {})
        if not isinstance(raw_audits, dict):
            raise TypeError("'question_audits' must be a dictionary")

        audits: dict[str, QuestionReconciliationAudit] = {}
        for qid, audit_dict in raw_audits.items():
            _require_non_empty_str(qid, "question_audits key")
            audit_obj = QuestionReconciliationAudit.from_dict(audit_dict)
            if qid != audit_obj.question_id:
                raise ValueError(f"question_audits key '{qid}' does not match audit.question_id '{audit_obj.question_id}'")
            audits[qid] = audit_obj

        return cls(
            study_id=data.get("study_id", STUDY_ID),
            protocol_id=data.get("protocol_id", PROTOCOL_ID),
            protocol_hash=data.get("protocol_hash", FROZEN_PROTOCOL_BYTE_SHA256),
            reviewer_a_role=data.get("reviewer_a_role", "reviewer_a"),
            reviewer_b_role=data.get("reviewer_b_role", "reviewer_b"),
            workspace_kind=data.get("workspace_kind", "synthetic"),
            question_audits=audits,
            local_only_notice=data.get("local_only_notice", LOCAL_ONLY_NOTICE),
        )

    @classmethod
    def load_synthetic_local(cls, file_path: Path | str) -> ReconciliationAuditWorkspace:
        """Load synthetic reconciliation audit workspace from local disk with fail-closed validation."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
