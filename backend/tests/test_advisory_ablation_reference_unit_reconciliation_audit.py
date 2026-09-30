"""Unit tests for human reconciliation and audit infrastructure (Phase 2C-B2B).

Protocol: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Schema: cpaa1_reference_unit_v1
Study: cross-perspective-advisory-ablation-v1

These tests use ONLY neutral, non-medical synthetic records and fixtures.
Real packet prose is strictly forbidden.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
    packet_canonical_sha256,
)
from research.experiments.cross_perspective_advisory_ablation_v1.reference_units import (
    FROZEN_PROTOCOL_BYTE_SHA256,
    LOCAL_ONLY_NOTICE,
    PROTOCOL_ID,
    STUDY_ID,
    CompletenessAttestation,
    EvidenceAnchor,
    EvidenceSpan,
    FormalReconciliationGateError,
    FrozenPacketAnchorIndex,
    NewTargetAuditEntry,
    QuestionReconciliationAudit,
    ReconciliationAuditWorkspace,
    ReconciliationStateError,
    ReferenceUnitRecord,
    ReviewerRecordRef,
    ReviewerRoleMismatchError,
    ReviewerWorkspace,
    UnresolvedDisagreementAuditEntry,
    find_exact_duplicate_records,
)


def _make_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_synthetic_packet_records(
    question_id: str = "syn_q_01",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Construct minimal synthetic non-medical packet records for unit testing."""
    tcm_items = []
    for r in range(1, 5):
        text = f"Synthetic evidence text item rank {r} for question {question_id}."
        tcm_items.append(
            {
                "evidence_id": f"ev:tcm:{question_id}:h{r}",
                "rank": r,
                "exact_chunk_text": text,
                "chunk_text_sha256": _make_sha256(text),
                "provenance": f"syn_tcm_doc_{r}.txt",
                "source_title": f"Synthetic Document {r}",
                "source_url": f"https://example.com/syn/tcm/{r}",
                "section_or_category": "Section A",
                "doi": f"10.1000/syn.tcm.{r}",
                "pmcid": f"PMC{10000 + r}",
            }
        )

    tcm_packet = {
        "schema_version": "cpaa1_frozen_packet_v1",
        "transformation_contract_id": "CPAA1-FROZEN-PACKET-LOSSLESS-V1",
        "task_type": "cross_perspective_advisory_ablation_v1",
        "topic": "synthetic_topic",
        "question_id": question_id,
        "question_text": f"Synthetic test question for {question_id}?",
        "perspective": "tcm",
        "packet_id": f"packet:tcm:{question_id}",
        "evidence_items": tcm_items,
        "candidate_id": "cand_tcm",
        "corpus_id": "c_tcm",
        "corpus_version": "v1",
        "corpus_sha256": "0" * 64,
        "retrieval_record_id": "rr_tcm",
        "retrieval_record_canonical_sha256": "0" * 64,
        "retrieval_artifact_sha256": "0" * 64,
        "retrieval_algorithm_id": "dense",
        "question_manifest_sha256": "0" * 64,
    }
    tcm_packet["packet_canonical_sha256"] = packet_canonical_sha256(tcm_packet)

    western_items = []
    for r in range(1, 5):
        text = f"Synthetic Western evidence text item rank {r} for question {question_id}."
        western_items.append(
            {
                "evidence_id": f"ev:western:{question_id}:h{r}",
                "rank": r,
                "exact_chunk_text": text,
                "chunk_text_sha256": _make_sha256(text),
                "provenance": f"syn_west_doc_{r}.txt",
                "source_title": f"Synthetic Document {r}",
                "source_url": f"https://example.com/syn/west/{r}",
                "section_or_category": "Section B",
                "doi": f"10.1000/syn.west.{r}",
                "pmcid": f"PMC{20000 + r}",
            }
        )

    western_packet = {
        "schema_version": "cpaa1_frozen_packet_v1",
        "transformation_contract_id": "CPAA1-FROZEN-PACKET-LOSSLESS-V1",
        "task_type": "cross_perspective_advisory_ablation_v1",
        "topic": "synthetic_topic",
        "question_id": question_id,
        "question_text": f"Synthetic test question for {question_id}?",
        "perspective": "western",
        "packet_id": f"packet:western:{question_id}",
        "evidence_items": western_items,
        "candidate_id": "cand_west",
        "corpus_id": "c_west",
        "corpus_version": "v1",
        "corpus_sha256": "0" * 64,
        "retrieval_record_id": "rr_west",
        "retrieval_record_canonical_sha256": "0" * 64,
        "retrieval_artifact_sha256": "0" * 64,
        "retrieval_algorithm_id": "dense",
        "question_manifest_sha256": "0" * 64,
    }
    western_packet["packet_canonical_sha256"] = packet_canonical_sha256(western_packet)

    return [tcm_packet], [western_packet]


def _make_sample_record(
    question_id: str = "syn_q_01",
    unit_text: str = "Synthetic target text",
    perspective: str = "tcm",
    qualifiers: list[str] | None = None,
    index: FrozenPacketAnchorIndex | None = None,
) -> ReferenceUnitRecord:
    pkt_id = f"packet:{perspective}:{question_id}"
    ev_id = f"ev:{perspective}:{question_id}:h1"
    text = (
        f"Synthetic evidence text item rank 1 for question {question_id}."
        if perspective == "tcm"
        else f"Synthetic Western evidence text item rank 1 for question {question_id}."
    )
    if index is not None:
        pkt = index.get_packet(pkt_id)
        packet_sha = pkt.packet_canonical_sha256 if pkt else "0" * 64
        ev = index.get_evidence(pkt_id, ev_id)
        chunk_sha = ev.chunk_text_sha256 if ev else _make_sha256(text)
    else:
        packet_sha = "0" * 64
        chunk_sha = _make_sha256(text)

    return ReferenceUnitRecord(
        question_id=question_id,
        unit_text=unit_text,
        unit_type="content",
        perspective_scope=perspective,  # type: ignore[arg-type]
        evidence_anchors=[
            EvidenceAnchor(
                packet_id=pkt_id,
                packet_canonical_sha256=packet_sha,
                perspective=perspective,  # type: ignore[arg-type]
                evidence_id=ev_id,
                chunk_text_sha256=chunk_sha,
                anchor_role="supporting_span",
                spans=[EvidenceSpan(start=0, end=9)],
            )
        ],
        support_scope="source_explicit",
        required_qualifiers=qualifiers or [],
        support_rationale="Synthetic human justification for testing.",
    )


def _make_fully_attested_audit(question_id: str = "syn_q_01") -> QuestionReconciliationAudit:
    """Helper creating a QuestionReconciliationAudit with all process attestations satisfied."""
    q_audit = QuestionReconciliationAudit(question_id=question_id)
    q_audit.completeness_attestation.considered_both_submissions = True
    q_audit.completeness_attestation.all_8_passages_checked = True
    q_audit.completeness_attestation.omitted_targets_examined = True
    q_audit.completeness_attestation.new_target_additions_checked_and_logged = True
    q_audit.completeness_attestation.methodological_issues_checked = True
    q_audit.completeness_attestation.unresolved_methodological_issue_present = False
    return q_audit


# ==============================================================================
# BASE STRUCTURAL TESTS: ReviewerRecordRef & Invariants
# ==============================================================================


def test_reviewer_record_ref_initialization_and_validation():
    """ReviewerRecordRef validates role, index, and question_id."""
    ref_a = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    assert ref_a.reviewer_role == "reviewer_a"
    assert ref_a.record_index == 0
    assert ref_a.question_id == "syn_q_01"

    # Immutable & hashable
    assert hash(ref_a) is not None
    with pytest.raises(AttributeError):
        ref_a.record_index = 1  # type: ignore[misc]

    # Validate against workspace
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    rec = _make_sample_record("syn_q_01", "Synthetic target A", index=index)
    ws_a.add_record(rec)

    validated_rec = ref_a.validate_against_workspace(ws_a)
    assert validated_rec.unit_text == "Synthetic target A"


def test_reviewer_record_ref_invalid_role_fails():
    """Invalid reviewer role fails construction and workspace validation."""
    with pytest.raises(ValueError, match="Invalid reviewer_role"):
        ReviewerRecordRef(reviewer_role="reviewer_c", record_index=0, question_id="syn_q_01")  # type: ignore[arg-type]

    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)
    ws_b.add_record(_make_sample_record("syn_q_01", index=index))

    ref_a = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    with pytest.raises(ReviewerRoleMismatchError, match="does not match workspace reviewer_role"):
        ref_a.validate_against_workspace(ws_b)


def test_reviewer_record_ref_rejects_bool_or_negative_record_index():
    """Part C item 5: ReviewerRecordRef rejects bool and negative indices."""
    with pytest.raises(TypeError, match="must be an int, not bool"):
        ReviewerRecordRef(reviewer_role="reviewer_a", record_index=True, question_id="syn_q_01")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be an int, not bool"):
        ReviewerRecordRef(reviewer_role="reviewer_a", record_index=False, question_id="syn_q_01")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="must be a non-negative int"):
        ReviewerRecordRef(reviewer_role="reviewer_a", record_index=-1, question_id="syn_q_01")


def test_reconciliation_workspace_starts_blank_and_unreviewed():
    """Reconciliation workspace starts blank and in unreviewed state."""
    questions = ["syn_q_01", "syn_q_02"]
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(questions)

    assert ws.workspace_kind == "synthetic"
    assert ws.study_id == STUDY_ID
    assert ws.protocol_id == PROTOCOL_ID
    assert ws.protocol_hash == FROZEN_PROTOCOL_BYTE_SHA256
    assert ws.reviewer_a_role == "reviewer_a"
    assert ws.reviewer_b_role == "reviewer_b"
    assert ws.local_only_notice == LOCAL_ONLY_NOTICE
    assert ws.questions == questions

    for qid in questions:
        q_audit = ws.get_question_audit(qid)
        assert q_audit.question_id == qid
        assert q_audit.reconciliation_state == "unreviewed"
        assert len(q_audit.reviewer_a_refs) == 0
        assert len(q_audit.reviewer_b_refs) == 0
        assert q_audit.completeness_attestation.is_complete() is False
        assert len(q_audit.unresolved_items) == 0
        assert len(q_audit.addition_log) == 0
        assert q_audit.adjudication_required is False


def test_no_automatic_semantic_inference_methods():
    """Scientific boundary: workspace exposes no semantic matching methods."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    for forbidden_method in (
        "infer_semantic_matches",
        "recommend_merges",
        "recommend_splits",
        "decide_omissions",
        "calculate_similarity",
        "build_union",
        "build_final_reference_units",
        "calculate_final_mq",
        "assign_reference_unit_ids",
        "export_reconciled_units",
    ):
        assert not hasattr(ws, forbidden_method)


# ==============================================================================
# CATEGORY A: COMPLETENESS SEMANTICS (Tests 1 to 5)
# ==============================================================================


def test_a1_methodological_issues_checked_and_none_present_can_complete():
    """Test 1: methodological issues checked + none present can complete."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    assert q_audit.completeness_attestation.is_complete() is True
    q_audit.set_reconciliation_state("human_review_complete")
    assert q_audit.reconciliation_state == "human_review_complete"


def test_a2_methodological_issues_checked_false_blocks_completion():
    """Test 2: methodological_issues_checked=False blocks completion."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.completeness_attestation.methodological_issues_checked = False
    assert q_audit.completeness_attestation.is_complete() is False

    with pytest.raises(ReconciliationStateError, match="human completeness attestations are incomplete"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_a3_unresolved_methodological_issue_present_true_blocks_completion():
    """Test 3: unresolved_methodological_issue_present=True blocks completion."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.completeness_attestation.unresolved_methodological_issue_present = True
    assert q_audit.completeness_attestation.is_complete() is False

    with pytest.raises(ReconciliationStateError, match="unresolved methodological issue is present"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_a4_new_target_additions_process_checked_with_zero_additions_can_complete():
    """Test 4: new-target-additions process checked with zero additions can complete."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    assert len(q_audit.addition_log) == 0
    assert q_audit.completeness_attestation.new_target_additions_checked_and_logged is True
    q_audit.set_reconciliation_state("human_review_complete")
    assert q_audit.reconciliation_state == "human_review_complete"


def test_a5_process_check_field_false_blocks_completion():
    """Test 5: process-check field false blocks completion."""
    for field_name in (
        "considered_both_submissions",
        "all_8_passages_checked",
        "omitted_targets_examined",
        "new_target_additions_checked_and_logged",
    ):
        q_audit = _make_fully_attested_audit("syn_q_01")
        setattr(q_audit.completeness_attestation, field_name, False)
        assert q_audit.completeness_attestation.is_complete() is False
        with pytest.raises(ReconciliationStateError, match="human completeness attestations are incomplete"):
            q_audit.set_reconciliation_state("human_review_complete")


# ==============================================================================
# CATEGORY B: STRICT BOOL INPUTS (Tests 6 to 9)
# ==============================================================================


def test_b6_false_string_cannot_become_true_for_completeness_bool():
    """Test 6: 'false' string cannot become True for completeness bool."""
    with pytest.raises(TypeError, match="must be of type bool"):
        CompletenessAttestation(considered_both_submissions="false")  # type: ignore[arg-type]

    raw = {
        "considered_both_submissions": "false",
        "all_8_passages_checked": True,
        "omitted_targets_examined": True,
        "new_target_additions_checked_and_logged": True,
        "methodological_issues_checked": True,
        "unresolved_methodological_issue_present": False,
    }
    with pytest.raises(TypeError, match="must be of type bool"):
        CompletenessAttestation.from_dict(raw)


def test_b7_numeric_zero_and_one_rejected_where_bool_required():
    """Test 7: numeric 0/1 rejected where bool required."""
    with pytest.raises(TypeError, match="must be of type bool"):
        CompletenessAttestation(considered_both_submissions=1)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be of type bool"):
        CompletenessAttestation(considered_both_submissions=0)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be of type bool"):
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="Valid reason",
            reviewer_a_acknowledged=1,  # type: ignore[arg-type]
        )


def test_b8_malformed_acknowledgement_bool_rejected():
    """Test 8: malformed acknowledgement bool rejected."""
    with pytest.raises(TypeError, match="must be of type bool"):
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="Valid reason",
            reviewer_a_acknowledged="true",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="must be of type bool"):
        NewTargetAuditEntry.from_dict(
            {
                "question_id": "syn_q_01",
                "human_authored_reason": "Valid reason",
                "reviewer_a_acknowledged": "false",
                "reviewer_b_acknowledged": True,
                "audit_status": "accepted",
                "audit_notes": "",
                "supporting_refs": [],
            }
        )


def test_b9_malformed_adjudication_required_bool_rejected():
    """Test 9: malformed adjudication_required bool rejected."""
    with pytest.raises(TypeError, match="must be of type bool"):
        QuestionReconciliationAudit(question_id="syn_q_01", adjudication_required="false")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="must be of type bool"):
        QuestionReconciliationAudit.from_dict(
            {"question_id": "syn_q_01", "adjudication_required": "true"}
        )

    with pytest.raises(TypeError, match="must be of type bool"):
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Dispute",
            third_adjudicator_required="true",  # type: ignore[arg-type]
        )


# ==============================================================================
# CATEGORY C: STATES (Tests 10 to 14)
# ==============================================================================


def test_c10_direct_reconciliation_state_merge_rejected():
    """Test 10: direct reconciliation_state='merge' rejected."""
    with pytest.raises(ReconciliationStateError, match="Invalid reconciliation_state"):
        QuestionReconciliationAudit(question_id="syn_q_01", reconciliation_state="merge")  # type: ignore[arg-type]

    q_audit = QuestionReconciliationAudit(question_id="syn_q_01")
    with pytest.raises(ReconciliationStateError, match="Invalid reconciliation_state"):
        q_audit.set_reconciliation_state("merge")  # type: ignore[arg-type]


def test_c11_from_dict_reconciliation_state_merge_rejected():
    """Test 11: from_dict reconciliation_state='merge' rejected."""
    data = {
        "question_id": "syn_q_01",
        "reconciliation_state": "merge",
    }
    with pytest.raises(ReconciliationStateError, match="Invalid reconciliation_state"):
        QuestionReconciliationAudit.from_dict(data)


def test_c12_load_synthetic_local_reconciliation_state_merge_rejected(tmp_path: Path):
    """Test 12: load_synthetic_local reconciliation_state='merge' rejected."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    out_file = tmp_path / "corrupted_state_audit.json"
    ws.save_local(out_file)

    payload = json.loads(out_file.read_text(encoding="utf-8"))
    payload["question_audits"]["syn_q_01"]["reconciliation_state"] = "merge"
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(ReconciliationStateError, match="Invalid reconciliation_state"):
        ReconciliationAuditWorkspace.load_synthetic_local(out_file)


def test_c13_invalid_addition_audit_status_rejected():
    """Test 13: invalid addition audit_status rejected."""
    with pytest.raises(ValueError, match="Invalid audit_status"):
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="Valid reason",
            audit_status="approved",  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="Invalid audit_status"):
        NewTargetAuditEntry.from_dict(
            {
                "question_id": "syn_q_01",
                "human_authored_reason": "Valid reason",
                "audit_status": "in_review",
            }
        )


def test_c14_invalid_disagreement_status_rejected():
    """Test 14: invalid disagreement status rejected."""
    with pytest.raises(ValueError, match="Invalid disagreement status"):
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Dispute",
            status="resolved",  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="Invalid disagreement status"):
        UnresolvedDisagreementAuditEntry.from_dict(
            {
                "question_id": "syn_q_01",
                "human_authored_disagreement_note": "Dispute",
                "status": "pending_decision",
            }
        )


# ==============================================================================
# CATEGORY D: DISAGREEMENT GATE (Tests 15 to 19)
# ==============================================================================


def test_d15_unresolved_blocks_completion():
    """Test 15: unresolved blocks completion."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.unresolved_items.append(
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Pending dispute",
            status="unresolved",
        )
    )
    with pytest.raises(ReconciliationStateError, match="unresolved disagreements"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_d16_referred_to_adjudication_blocks_even_if_top_level_flag_false():
    """Test 16: referred_to_adjudication blocks even if top-level flag false."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.adjudication_required = False
    q_audit.unresolved_items.append(
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Referred dispute",
            status="referred_to_adjudication",
        )
    )
    with pytest.raises(ReconciliationStateError, match="unresolved disagreements"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_d17_adjudication_required_true_blocks():
    """Test 17: adjudication_required=True blocks."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.adjudication_required = True
    with pytest.raises(ReconciliationStateError, match="adjudication is marked as required"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_d18_adjudicated_can_be_non_blocking():
    """Test 18: adjudicated can be non-blocking."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.unresolved_items.append(
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Resolved by third adjudicator",
            status="adjudicated",
        )
    )
    q_audit.set_reconciliation_state("human_review_complete")
    assert q_audit.reconciliation_state == "human_review_complete"


def test_d19_closed_can_be_non_blocking():
    """Test 19: closed can be non-blocking."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.unresolved_items.append(
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Dispute withdrawn by reviewer",
            status="closed",
        )
    )
    q_audit.set_reconciliation_state("human_review_complete")
    assert q_audit.reconciliation_state == "human_review_complete"


# ==============================================================================
# CATEGORY E: ADDITION GATE (Tests 20 to 25)
# ==============================================================================


def test_e20_pending_addition_blocks():
    """Test 20: pending addition blocks."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.addition_log.append(
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="New candidate target found",
            reviewer_a_acknowledged=True,
            reviewer_b_acknowledged=True,
            audit_status="pending",
        )
    )
    with pytest.raises(ReconciliationStateError, match="addition log entries must have final status"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_e21_missing_reviewer_a_ack_blocks():
    """Test 21: missing Reviewer A ack blocks."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.addition_log.append(
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="New candidate target found",
            reviewer_a_acknowledged=False,
            reviewer_b_acknowledged=True,
            audit_status="accepted",
        )
    )
    with pytest.raises(ReconciliationStateError, match="must be acknowledged by Reviewer A"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_e22_missing_reviewer_b_ack_blocks():
    """Test 22: missing Reviewer B ack blocks."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.addition_log.append(
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="New candidate target found",
            reviewer_a_acknowledged=True,
            reviewer_b_acknowledged=False,
            audit_status="accepted",
        )
    )
    with pytest.raises(ReconciliationStateError, match="must be acknowledged by Reviewer B"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_e23_accepted_addition_with_both_acks_may_pass():
    """Test 23: accepted + both acks may pass."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.addition_log.append(
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="Both reviewers agreed this boundary was omitted from initial drafts.",
            reviewer_a_acknowledged=True,
            reviewer_b_acknowledged=True,
            audit_status="accepted",
        )
    )
    q_audit.set_reconciliation_state("human_review_complete")
    assert q_audit.reconciliation_state == "human_review_complete"


def test_e24_rejected_addition_with_both_acks_may_pass():
    """Test 24: rejected + both acks may pass."""
    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.addition_log.append(
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="Candidate considered and rejected as non-substantive.",
            reviewer_a_acknowledged=True,
            reviewer_b_acknowledged=True,
            audit_status="rejected",
        )
    )
    q_audit.set_reconciliation_state("human_review_complete")
    assert q_audit.reconciliation_state == "human_review_complete"


def test_e25_empty_human_authored_reason_rejected():
    """Test 25: empty human_authored_reason rejected."""
    with pytest.raises(ValueError, match="must be a non-empty string"):
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="",
        )

    with pytest.raises(ValueError, match="must be a non-empty string"):
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="   ",
        )

    with pytest.raises(ValueError, match="must be a non-empty string"):
        NewTargetAuditEntry.from_dict(
            {
                "question_id": "syn_q_01",
                "human_authored_reason": "",
            }
        )


# ==============================================================================
# CATEGORY F: PROVENANCE (Tests 26 to 33)
# ==============================================================================


def test_f26_reviewer_a_refs_containing_reviewer_b_ref_rejected():
    """Test 26: reviewer_a_refs containing reviewer_b ref rejected/blocks."""
    ref_b = ReviewerRecordRef(reviewer_role="reviewer_b", record_index=0, question_id="syn_q_01")
    with pytest.raises(ValueError, match="reviewer_a"):
        QuestionReconciliationAudit(question_id="syn_q_01", reviewer_a_refs=[ref_b])

    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.reviewer_a_refs.append(ref_b)
    with pytest.raises(ReconciliationStateError, match="reviewer_a"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_f27_reviewer_b_refs_containing_reviewer_a_ref_rejected():
    """Test 27: reviewer_b_refs containing reviewer_a ref rejected/blocks."""
    ref_a = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    with pytest.raises(ValueError, match="reviewer_b"):
        QuestionReconciliationAudit(question_id="syn_q_01", reviewer_b_refs=[ref_a])

    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.reviewer_b_refs.append(ref_a)
    with pytest.raises(ReconciliationStateError, match="reviewer_b"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_f28_cross_question_reviewer_ref_rejected():
    """Test 28: cross-question reviewer ref rejected/blocks."""
    ref_q2 = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_02")
    with pytest.raises(ValueError, match="does not match parent question_id"):
        QuestionReconciliationAudit(question_id="syn_q_01", reviewer_a_refs=[ref_q2])

    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.reviewer_a_refs.append(ref_q2)
    with pytest.raises(ReconciliationStateError, match="does not match parent question_id"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_f29_cross_question_addition_entry_rejected():
    """Test 29: cross-question addition entry rejected/blocks."""
    entry_q2 = NewTargetAuditEntry(
        question_id="syn_q_02",
        human_authored_reason="Valid reason",
        reviewer_a_acknowledged=True,
        reviewer_b_acknowledged=True,
        audit_status="accepted",
    )
    with pytest.raises(ValueError, match="addition.*question_id"):
        QuestionReconciliationAudit(question_id="syn_q_01", addition_log=[entry_q2])

    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.addition_log.append(entry_q2)
    with pytest.raises(ReconciliationStateError, match="addition.*question_id"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_f30_cross_question_supporting_ref_rejected():
    """Test 30: cross-question supporting ref rejected/blocks."""
    ref_q2 = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_02")
    with pytest.raises(ValueError, match="Supporting ref.*question_id"):
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="Valid reason",
            supporting_refs=[ref_q2],
        )


def test_f31_cross_question_unresolved_entry_rejected():
    """Test 31: cross-question unresolved entry rejected/blocks."""
    dispute_q2 = UnresolvedDisagreementAuditEntry(
        question_id="syn_q_02",
        human_authored_disagreement_note="Dispute note",
        status="adjudicated",
    )
    with pytest.raises(ValueError, match="unresolved_item has question_id"):
        QuestionReconciliationAudit(question_id="syn_q_01", unresolved_items=[dispute_q2])

    q_audit = _make_fully_attested_audit("syn_q_01")
    q_audit.unresolved_items.append(dispute_q2)
    with pytest.raises(ReconciliationStateError, match="unresolved_item has question_id"):
        q_audit.set_reconciliation_state("human_review_complete")


def test_f32_cross_question_involved_ref_rejected():
    """Test 32: cross-question involved ref rejected/blocks."""
    ref_q2 = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_02")
    with pytest.raises(ValueError, match="Involved ref.*question_id"):
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Dispute note",
            involved_refs=[ref_q2],
        )


def test_f33_malformed_exact_duplicate_pair_roles_questions_rejected():
    """Test 33: malformed exact duplicate pair roles/questions rejected/blocks."""
    ref_a = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    ref_a2 = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=1, question_id="syn_q_01")
    ref_b = ReviewerRecordRef(reviewer_role="reviewer_b", record_index=0, question_id="syn_q_01")
    ref_b_q2 = ReviewerRecordRef(reviewer_role="reviewer_b", record_index=0, question_id="syn_q_02")

    # Invalid pair: first ref not reviewer_a
    with pytest.raises(ValueError, match="first ref must have role 'reviewer_a'"):
        QuestionReconciliationAudit(question_id="syn_q_01", exact_duplicate_pairs=[(ref_b, ref_b)])

    # Invalid pair: second ref not reviewer_b
    with pytest.raises(ValueError, match="second ref must have role 'reviewer_b'"):
        QuestionReconciliationAudit(question_id="syn_q_01", exact_duplicate_pairs=[(ref_a, ref_a2)])

    # Invalid pair: cross-question ref
    with pytest.raises(ValueError, match="does not match parent question_id"):
        QuestionReconciliationAudit(question_id="syn_q_01", exact_duplicate_pairs=[(ref_a, ref_b_q2)])


# ==============================================================================
# CATEGORY G: FORMAL GATE (Tests 34 to 38)
# ==============================================================================


def test_g34_create_formal_blank_still_raises():
    """Test 34: create_formal_blank still raises."""
    with pytest.raises(FormalReconciliationGateError, match="Formal reconciliation cannot begin"):
        ReconciliationAuditWorkspace.create_formal_blank()


def test_g35_from_formal_workspaces_still_raises():
    """Test 35: from_formal_workspaces still raises."""
    with pytest.raises(FormalReconciliationGateError, match="Formal reconciliation cannot begin"):
        ReconciliationAuditWorkspace.from_formal_workspaces()


def test_g36_direct_reconciliation_audit_workspace_formal_raises():
    """Test 36: direct ReconciliationAuditWorkspace(workspace_kind="formal") raises."""
    with pytest.raises(FormalReconciliationGateError, match="Formal reconciliation workspace creation is prohibited"):
        ReconciliationAuditWorkspace(workspace_kind="formal")  # type: ignore[arg-type]


def test_g37_find_exact_duplicate_records_formal_raises_and_does_not_compare():
    """Test 37: find_exact_duplicate_records(formal A, formal B) raises and does not compare."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    class FormalWorkspaceStub:
        workspace_kind = "formal"
        reviewer_role = "reviewer_a"
        records = [object()]

    with pytest.raises(FormalReconciliationGateError, match="cannot consume formal administrative workspaces"):
        find_exact_duplicate_records(FormalWorkspaceStub(), ws_b)  # type: ignore[arg-type]

    class FormalWorkspaceStubB:
        workspace_kind = "formal"
        reviewer_role = "reviewer_b"
        records = [object()]

    with pytest.raises(FormalReconciliationGateError, match="cannot consume formal administrative workspaces"):
        find_exact_duplicate_records(ws_a, FormalWorkspaceStubB())  # type: ignore[arg-type]


def test_g38_create_synthetic_blank_rejects_formal_workspace_binding():
    """Test 38: create_synthetic_blank rejects formal workspace binding."""
    class FormalStub:
        workspace_kind = "formal"
        reviewer_role = "reviewer_a"

    with pytest.raises(TypeError, match="Cannot bind non-synthetic"):
        ReconciliationAuditWorkspace.create_synthetic_blank(
            ["syn_q_01"], workspace_a=FormalStub()  # type: ignore[arg-type]
        )


# ==============================================================================
# CATEGORY H: FIXED WORKSPACE METADATA (Tests 39 to 45)
# ==============================================================================


def test_h39_altered_study_id_fails():
    """Test 39: altered study_id fails load/construction."""
    with pytest.raises(ValueError, match="study_id"):
        ReconciliationAuditWorkspace(study_id="corrupted_study")

    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    data = ws.to_dict()
    data["study_id"] = "corrupted_study"
    with pytest.raises(ValueError, match="study_id"):
        ReconciliationAuditWorkspace.from_dict(data)


def test_h40_altered_protocol_id_fails():
    """Test 40: altered protocol_id fails."""
    with pytest.raises(ValueError, match="protocol_id"):
        ReconciliationAuditWorkspace(protocol_id="corrupted_protocol")

    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    data = ws.to_dict()
    data["protocol_id"] = "corrupted_protocol"
    with pytest.raises(ValueError, match="protocol_id"):
        ReconciliationAuditWorkspace.from_dict(data)


def test_h41_altered_protocol_hash_fails():
    """Test 41: altered protocol_hash fails."""
    with pytest.raises(ValueError, match="protocol_hash"):
        ReconciliationAuditWorkspace(protocol_hash="0" * 64)

    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    data = ws.to_dict()
    data["protocol_hash"] = "0" * 64
    with pytest.raises(ValueError, match="protocol_hash"):
        ReconciliationAuditWorkspace.from_dict(data)


def test_h42_altered_reviewer_a_role_fails():
    """Test 42: altered reviewer_a_role fails."""
    with pytest.raises(ValueError, match="reviewer_a_role"):
        ReconciliationAuditWorkspace(reviewer_a_role="reviewer_x")  # type: ignore[arg-type]

    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    data = ws.to_dict()
    data["reviewer_a_role"] = "reviewer_x"
    with pytest.raises(ValueError, match="reviewer_a_role"):
        ReconciliationAuditWorkspace.from_dict(data)


def test_h43_altered_reviewer_b_role_fails():
    """Test 43: altered reviewer_b_role fails."""
    with pytest.raises(ValueError, match="reviewer_b_role"):
        ReconciliationAuditWorkspace(reviewer_b_role="reviewer_y")  # type: ignore[arg-type]

    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    data = ws.to_dict()
    data["reviewer_b_role"] = "reviewer_y"
    with pytest.raises(ValueError, match="reviewer_b_role"):
        ReconciliationAuditWorkspace.from_dict(data)


def test_h44_altered_local_only_notice_fails():
    """Test 44: altered local_only_notice fails."""
    with pytest.raises(ValueError, match="local_only_notice"):
        ReconciliationAuditWorkspace(local_only_notice="Altered notice")

    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    data = ws.to_dict()
    data["local_only_notice"] = "Altered notice"
    with pytest.raises(ValueError, match="local_only_notice"):
        ReconciliationAuditWorkspace.from_dict(data)


def test_h45_non_synthetic_workspace_kind_fails():
    """Test 45: non-synthetic workspace_kind fails."""
    with pytest.raises(FormalReconciliationGateError):
        ReconciliationAuditWorkspace(workspace_kind="formal")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="workspace_kind"):
        ReconciliationAuditWorkspace(workspace_kind="invalid_kind")  # type: ignore[arg-type]


# ==============================================================================
# CATEGORY I: QUESTION MAP (Tests 46 to 49)
# ==============================================================================


def test_i46_empty_question_list_rejected():
    """Test 46: empty question list rejected."""
    with pytest.raises(ValueError, match="questions list cannot be empty"):
        ReconciliationAuditWorkspace.create_synthetic_blank([])


def test_i47_duplicate_question_ids_rejected():
    """Test 47: duplicate question IDs rejected."""
    with pytest.raises(ValueError, match="Duplicate question"):
        ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01", "syn_q_01"])


def test_i48_empty_question_id_rejected():
    """Test 48: empty question ID rejected."""
    with pytest.raises(ValueError, match="must be a non-empty string"):
        ReconciliationAuditWorkspace.create_synthetic_blank([""])

    with pytest.raises(ValueError, match="must be a non-empty string"):
        ReconciliationAuditWorkspace.create_synthetic_blank(["   "])

    with pytest.raises(ValueError, match="must be a non-empty string"):
        QuestionReconciliationAudit(question_id="")


def test_i49_question_audits_dict_key_not_equal_to_audit_question_id_rejected():
    """Test 49: question_audits dict key != audit.question_id rejected."""
    q_audit = QuestionReconciliationAudit(question_id="syn_q_01")
    with pytest.raises(ValueError, match="does not match audit.question_id"):
        ReconciliationAuditWorkspace(
            question_audits={"syn_q_02": q_audit},
        )


# ==============================================================================
# CATEGORY J: EXACT DUPLICATES (Tests 50 to 54)
# ==============================================================================


def test_j50_exact_identical_synthetic_records_flagged():
    """Test 50: exact-identical synthetic records flagged."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Exact shared target", index=index)
    rec_b = _make_sample_record("syn_q_01", "Exact shared target", index=index)

    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    dups = find_exact_duplicate_records(ws_a, ws_b)
    assert len(dups) == 1
    ref_a, ref_b = dups[0]
    assert ref_a.reviewer_role == "reviewer_a"
    assert ref_a.record_index == 0
    assert ref_b.reviewer_role == "reviewer_b"
    assert ref_b.record_index == 0


def test_j51_punctuation_difference_not_flagged():
    """Test 51: punctuation difference not flagged."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Exact shared target", index=index)
    rec_b = _make_sample_record("syn_q_01", "Exact shared target.", index=index)  # period

    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    assert len(find_exact_duplicate_records(ws_a, ws_b)) == 0


def test_j52_whitespace_difference_not_flagged():
    """Test 52: whitespace difference not flagged."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Exact shared target", index=index)
    rec_b = _make_sample_record("syn_q_01", "Exact shared target ", index=index)  # trailing space

    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    assert len(find_exact_duplicate_records(ws_a, ws_b)) == 0


def test_j53_case_difference_not_flagged():
    """Test 53: case difference not flagged."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Exact shared target", index=index)
    rec_b = _make_sample_record("syn_q_01", "exact shared target", index=index)  # lower case

    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    assert len(find_exact_duplicate_records(ws_a, ws_b)) == 0


def test_j54_duplicate_check_does_not_mutate_reviewer_records():
    """Test 54: duplicate check does not mutate reviewer records."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Target identical", index=index)
    rec_b = _make_sample_record("syn_q_01", "Target identical", index=index)
    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    ws_recon = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"], ws_a, ws_b)
    q_audit = ws_recon.get_question_audit("syn_q_01")

    assert len(q_audit.exact_duplicate_pairs) == 1
    assert len(ws_a.records) == 1
    assert len(ws_b.records) == 1
    rec_text_a = ws_a.records[0]["unit_text"] if isinstance(ws_a.records[0], dict) else ws_a.records[0].unit_text
    rec_text_b = ws_b.records[0]["unit_text"] if isinstance(ws_b.records[0], dict) else ws_b.records[0].unit_text
    assert rec_text_a == "Target identical"
    assert rec_text_b == "Target identical"


# ==============================================================================
# CATEGORY K: DESERIALIZATION (Tests 55 to 56)
# ==============================================================================


def test_k55_round_trip_valid_synthetic_audit_succeeds(tmp_path: Path):
    """Test 55: round-trip valid synthetic audit succeeds."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    q_audit = ws.get_question_audit("syn_q_01")
    q_audit.human_notes = "Human reconciliation notes for syn_q_01"
    q_audit.completeness_attestation.considered_both_submissions = True
    q_audit.completeness_attestation.all_8_passages_checked = True
    q_audit.completeness_attestation.omitted_targets_examined = True
    q_audit.completeness_attestation.new_target_additions_checked_and_logged = True
    q_audit.completeness_attestation.methodological_issues_checked = True
    q_audit.completeness_attestation.unresolved_methodological_issue_present = False

    q_audit.reviewer_a_refs.append(
        ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    )
    q_audit.reviewer_b_refs.append(
        ReviewerRecordRef(reviewer_role="reviewer_b", record_index=0, question_id="syn_q_01")
    )
    q_audit.addition_log.append(
        NewTargetAuditEntry(
            question_id="syn_q_01",
            human_authored_reason="Discovered additional scope requirement",
            reviewer_a_acknowledged=True,
            reviewer_b_acknowledged=True,
            audit_status="accepted",
        )
    )
    q_audit.unresolved_items.append(
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Resolved by agreement",
            status="closed",
        )
    )
    q_audit.set_reconciliation_state("human_review_complete")

    out_file = tmp_path / "synthetic_reconciliation_audit.json"
    ws.save_local(out_file)

    loaded = ReconciliationAuditWorkspace.load_synthetic_local(out_file)
    assert loaded.workspace_kind == "synthetic"
    assert loaded.study_id == STUDY_ID
    assert loaded.protocol_id == PROTOCOL_ID
    assert loaded.protocol_hash == FROZEN_PROTOCOL_BYTE_SHA256
    assert loaded.local_only_notice == LOCAL_ONLY_NOTICE

    loaded_audit = loaded.get_question_audit("syn_q_01")
    assert loaded_audit.reconciliation_state == "human_review_complete"
    assert loaded_audit.human_notes == "Human reconciliation notes for syn_q_01"
    assert loaded_audit.completeness_attestation.is_complete() is True
    assert len(loaded_audit.reviewer_a_refs) == 1
    assert len(loaded_audit.reviewer_b_refs) == 1
    assert len(loaded_audit.addition_log) == 1
    assert loaded_audit.addition_log[0].audit_status == "accepted"
    assert len(loaded_audit.unresolved_items) == 1
    assert loaded_audit.unresolved_items[0].status == "closed"


def test_k56_malformed_bool_status_metadata_cannot_enter_through_json_load(tmp_path: Path):
    """Test 56: malformed bool/status/metadata cannot enter through JSON load."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    out_file = tmp_path / "test_malformed_audit.json"
    ws.save_local(out_file)
    base_payload = json.loads(out_file.read_text(encoding="utf-8"))

    # 1. Malformed bool ("true" as string)
    payload1 = copy.deepcopy(base_payload)
    payload1["question_audits"]["syn_q_01"]["completeness_attestation"]["all_8_passages_checked"] = "true"
    out_file.write_text(json.dumps(payload1), encoding="utf-8")
    with pytest.raises(TypeError, match="must be of type bool"):
        ReconciliationAuditWorkspace.load_synthetic_local(out_file)

    # 2. Malformed status ("merge")
    payload2 = copy.deepcopy(base_payload)
    payload2["question_audits"]["syn_q_01"]["reconciliation_state"] = "merge"
    out_file.write_text(json.dumps(payload2), encoding="utf-8")
    with pytest.raises(ReconciliationStateError, match="Invalid reconciliation_state"):
        ReconciliationAuditWorkspace.load_synthetic_local(out_file)

    # 3. Malformed metadata (altered protocol_hash)
    payload3 = copy.deepcopy(base_payload)
    payload3["protocol_hash"] = "badhash"
    out_file.write_text(json.dumps(payload3), encoding="utf-8")
    with pytest.raises(ValueError, match="protocol_hash"):
        ReconciliationAuditWorkspace.load_synthetic_local(out_file)

    # 4. Inconsistent human_review_complete state loaded without required attestations
    payload4 = copy.deepcopy(base_payload)
    payload4["question_audits"]["syn_q_01"]["reconciliation_state"] = "human_review_complete"
    out_file.write_text(json.dumps(payload4), encoding="utf-8")
    with pytest.raises(ReconciliationStateError):
        ReconciliationAuditWorkspace.load_synthetic_local(out_file)
