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
   All formal reconciliation constructors fail closed in Phase B2B.

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


class ReconciliationAuditError(Exception):
    """Base error for reconciliation audit failures."""


class ReviewerRecordRefValidationError(ReconciliationAuditError):
    """Raised when a ReviewerRecordRef fails structural or referential validation."""


class FormalReconciliationGateError(ReconciliationAuditError):
    """Raised when formal reconciliation execution is attempted without cryptographic submission receipts."""


class ReconciliationStateError(ReconciliationAuditError):
    """Raised when an invalid state transition or missing attestation is encountered."""


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
        if self.record_index < 0:
            raise ValueError(
                f"record_index must be non-negative integer, got {self.record_index}"
            )
        if not self.question_id:
            raise ValueError("question_id must be a non-empty string")

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
    new_targets_logged: bool = False
    methodological_issues_identified: bool = False
    human_attestor: str = ""
    attestation_notes: str = ""

    def is_complete(self) -> bool:
        """Return True if all 5 required human completeness attestations have been confirmed."""
        return (
            self.considered_both_submissions
            and self.all_8_passages_checked
            and self.omitted_targets_examined
            and self.new_targets_logged
            and self.methodological_issues_identified
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "considered_both_submissions": self.considered_both_submissions,
            "all_8_passages_checked": self.all_8_passages_checked,
            "omitted_targets_examined": self.omitted_targets_examined,
            "new_targets_logged": self.new_targets_logged,
            "methodological_issues_identified": self.methodological_issues_identified,
            "human_attestor": self.human_attestor,
            "attestation_notes": self.attestation_notes,
            "is_complete": self.is_complete(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompletenessAttestation:
        return cls(
            considered_both_submissions=bool(data.get("considered_both_submissions", False)),
            all_8_passages_checked=bool(data.get("all_8_passages_checked", False)),
            omitted_targets_examined=bool(data.get("omitted_targets_examined", False)),
            new_targets_logged=bool(data.get("new_targets_logged", False)),
            methodological_issues_identified=bool(data.get("methodological_issues_identified", False)),
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
    audit_status: Literal["pending", "accepted", "rejected"] = "pending"
    audit_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
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
        refs = [
            ReviewerRecordRef(
                reviewer_role=r["reviewer_role"],
                record_index=r["record_index"],
                question_id=r["question_id"],
            )
            for r in data.get("supporting_refs", [])
        ]
        return cls(
            question_id=str(data["question_id"]),
            human_authored_reason=str(data.get("human_authored_reason", "")),
            reviewer_a_acknowledged=bool(data.get("reviewer_a_acknowledged", False)),
            reviewer_b_acknowledged=bool(data.get("reviewer_b_acknowledged", False)),
            supporting_refs=refs,
            audit_status=data.get("audit_status", "pending"),
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
    status: Literal["unresolved", "referred_to_adjudication", "adjudicated", "closed"] = "unresolved"
    third_adjudicator_required: bool = False
    adjudicator_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
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
        refs = [
            ReviewerRecordRef(
                reviewer_role=r["reviewer_role"],
                record_index=r["record_index"],
                question_id=r["question_id"],
            )
            for r in data.get("involved_refs", [])
        ]
        return cls(
            question_id=str(data["question_id"]),
            involved_refs=refs,
            human_authored_disagreement_note=str(data.get("human_authored_disagreement_note", "")),
            status=data.get("status", "unresolved"),
            third_adjudicator_required=bool(data.get("third_adjudicator_required", False)),
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

    def set_reconciliation_state(self, state: ReconciliationState) -> None:
        """Update reconciliation administrative state with fail-closed validation."""
        if state not in ALLOWED_RECONCILIATION_STATES:
            raise ReconciliationStateError(
                f"Invalid reconciliation_state '{state}': must be one of {ALLOWED_RECONCILIATION_STATES}"
            )
        if state == "human_review_complete":
            if not self.completeness_attestation.is_complete():
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    "human completeness attestations are incomplete"
                )
            if self.adjudication_required or any(item.status == "unresolved" for item in self.unresolved_items):
                raise ReconciliationStateError(
                    f"Cannot mark question '{self.question_id}' as 'human_review_complete': "
                    "unresolved disagreements or adjudication requirements remain"
                )
        self.reconciliation_state = state

    def to_dict(self) -> dict[str, Any]:
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
        a_refs = [
            ReviewerRecordRef(
                reviewer_role=r["reviewer_role"],
                record_index=r["record_index"],
                question_id=r["question_id"],
            )
            for r in data.get("reviewer_a_refs", [])
        ]
        b_refs = [
            ReviewerRecordRef(
                reviewer_role=r["reviewer_role"],
                record_index=r["record_index"],
                question_id=r["question_id"],
            )
            for r in data.get("reviewer_b_refs", [])
        ]
        dup_pairs = [
            (
                ReviewerRecordRef(
                    reviewer_role=p[0]["reviewer_role"],
                    record_index=p[0]["record_index"],
                    question_id=p[0]["question_id"],
                ),
                ReviewerRecordRef(
                    reviewer_role=p[1]["reviewer_role"],
                    record_index=p[1]["record_index"],
                    question_id=p[1]["question_id"],
                ),
            )
            for p in data.get("exact_duplicate_pairs", [])
        ]
        return cls(
            question_id=str(data["question_id"]),
            reviewer_a_refs=a_refs,
            reviewer_b_refs=b_refs,
            human_notes=str(data.get("human_notes", "")),
            reconciliation_state=data.get("reconciliation_state", "unreviewed"),
            completeness_attestation=CompletenessAttestation.from_dict(
                data.get("completeness_attestation", {})
            ),
            unresolved_items=[
                UnresolvedDisagreementAuditEntry.from_dict(item)
                for item in data.get("unresolved_items", [])
            ],
            addition_log=[
                NewTargetAuditEntry.from_dict(entry)
                for entry in data.get("addition_log", [])
            ],
            adjudication_required=bool(data.get("adjudication_required", False)),
            exact_duplicate_pairs=dup_pairs,
        )


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
    """
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
        if workspace_a is not None and workspace_a.workspace_kind != "synthetic":
            raise TypeError("Cannot bind non-synthetic workspace_a to synthetic reconciliation workspace")
        if workspace_b is not None and workspace_b.workspace_kind != "synthetic":
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
    def load_synthetic_local(cls, file_path: Path) -> ReconciliationAuditWorkspace:
        """Load synthetic reconciliation audit workspace from local disk."""
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if data.get("workspace_kind") != "synthetic":
            raise TypeError("load_synthetic_local only loads workspaces with workspace_kind 'synthetic'")
        audits = {
            qid: QuestionReconciliationAudit.from_dict(audit_dict)
            for qid, audit_dict in data.get("question_audits", {}).items()
        }
        return cls(
            study_id=data.get("study_id", STUDY_ID),
            protocol_id=data.get("protocol_id", PROTOCOL_ID),
            protocol_hash=data.get("protocol_hash", FROZEN_PROTOCOL_BYTE_SHA256),
            reviewer_a_role=data.get("reviewer_a_role", "reviewer_a"),
            reviewer_b_role=data.get("reviewer_b_role", "reviewer_b"),
            workspace_kind="synthetic",
            question_audits=audits,
            local_only_notice=data.get("local_only_notice", LOCAL_ONLY_NOTICE),
        )
