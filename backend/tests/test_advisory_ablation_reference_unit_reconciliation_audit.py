"""Unit tests for human reconciliation and audit infrastructure (Phase 2C-B2B).

Protocol: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Schema: cpaa1_reference_unit_v1
Study: cross-perspective-advisory-ablation-v1

These tests use ONLY neutral, non-medical synthetic records and fixtures.
Real packet prose is strictly forbidden.
"""

from __future__ import annotations

import hashlib
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


# ==============================================================================
# TASK 3: ReviewerRecordRef Tests
# ==============================================================================


def test_reviewer_record_ref_initialization_and_validation():
    """Task 3: ReviewerRecordRef validates role, index, and question_id."""
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
    """Task 3: Invalid reviewer role fails construction and workspace validation."""
    with pytest.raises(ValueError, match="Invalid reviewer_role"):
        ReviewerRecordRef(reviewer_role="reviewer_c", record_index=0, question_id="syn_q_01")  # type: ignore[arg-type]

    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)
    ws_b.add_record(_make_sample_record("syn_q_01", index=index))

    ref_a = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    with pytest.raises(ReviewerRoleMismatchError, match="does not match workspace reviewer_role"):
        ref_a.validate_against_workspace(ws_b)


def test_reviewer_record_ref_out_of_range_index_fails():
    """Task 3: Negative or out-of-range record index fails."""
    with pytest.raises(ValueError, match="record_index must be non-negative"):
        ReviewerRecordRef(reviewer_role="reviewer_a", record_index=-1, question_id="syn_q_01")

    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)

    ref_a = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    with pytest.raises(IndexError, match="out of bounds"):
        ref_a.validate_against_workspace(ws_a)


def test_reviewer_record_ref_question_mismatch_fails():
    """Task 3: Question mismatch between reference and workspace record fails."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_a.add_record(_make_sample_record("syn_q_01", index=index))

    ref_mismatch = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_99")
    with pytest.raises(ValueError, match="does not match reference question_id"):
        ref_mismatch.validate_against_workspace(ws_a)


def test_synthetic_ab_record_refs_remain_distinct():
    """Task 3: A and B record references remain distinct and preserve provenance."""
    ref_a = ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01")
    ref_b = ReviewerRecordRef(reviewer_role="reviewer_b", record_index=0, question_id="syn_q_01")
    assert ref_a != ref_b
    assert ref_a.reviewer_role == "reviewer_a"
    assert ref_b.reviewer_role == "reviewer_b"


# ==============================================================================
# TASK 4, 5, 6, 7: ReconciliationAuditWorkspace Tests
# ==============================================================================


def test_reconciliation_workspace_starts_blank_and_unreviewed():
    """Task 4 & 5: Reconciliation workspace starts blank and in unreviewed state."""
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


def test_no_automatic_semantic_matching_or_inferred_relations():
    """Task 4 & Scientific Boundary: Prohibit semantic inference and non-administrative states."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    q_audit = ws.get_question_audit("syn_q_01")

    # Forbidden semantic states must fail validation
    forbidden_states = ["equivalent", "merge", "split", "better", "keep_a", "keep_b"]
    for state in forbidden_states:
        with pytest.raises(ReconciliationStateError, match="Invalid reconciliation_state"):
            q_audit.set_reconciliation_state(state)  # type: ignore[arg-type]

    # Workspace exposes NO semantic inference methods
    for forbidden_method in (
        "infer_semantic_matches",
        "recommend_merges",
        "recommend_splits",
        "decide_omissions",
        "calculate_similarity",
    ):
        assert not hasattr(ws, forbidden_method)


def test_no_automatic_union_or_final_reference_set():
    """Task 5 & Scientific Boundary: Prohibit automatic union or final set generation."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    for forbidden_method in (
        "build_union",
        "build_final_reference_units",
        "calculate_final_mq",
        "assign_reference_unit_ids",
        "export_reconciled_units",
    ):
        assert not hasattr(ws, forbidden_method)


def test_synthetic_workspace_is_clearly_non_formal():
    """Task 7: Synthetic reconciliation workspace is marked synthetic and cannot bind non-synthetic."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    assert ws.workspace_kind == "synthetic"

    class FakeFormalWorkspace:
        workspace_kind = "formal"
        reviewer_role = "reviewer_a"

    with pytest.raises(TypeError, match="Cannot bind non-synthetic"):
        ReconciliationAuditWorkspace.create_synthetic_blank(
            ["syn_q_01"], workspace_a=FakeFormalWorkspace()  # type: ignore[arg-type]
        )


def test_formal_reconciliation_constructor_fails_closed():
    """Task 6: Formal reconciliation constructor fails closed in Phase B2B."""
    with pytest.raises(FormalReconciliationGateError, match="cannot begin from administrative B2A workspaces alone"):
        ReconciliationAuditWorkspace.create_formal_blank()

    with pytest.raises(FormalReconciliationGateError, match="cannot begin from administrative B2A workspaces alone"):
        ReconciliationAuditWorkspace.from_formal_workspaces()


# ==============================================================================
# TASK 8: Exact Duplicate Detection Tests
# ==============================================================================


def test_exact_identical_records_mechanically_flagged():
    """Task 8: Mechanically flag exact byte-for-byte / model-for-model duplicate records."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Exact shared substantive target", index=index)
    rec_b = _make_sample_record("syn_q_01", "Exact shared substantive target", index=index)

    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    dups = find_exact_duplicate_records(ws_a, ws_b)
    assert len(dups) == 1
    ref_a, ref_b = dups[0]
    assert ref_a.reviewer_role == "reviewer_a"
    assert ref_a.record_index == 0
    assert ref_b.reviewer_role == "reviewer_b"
    assert ref_b.record_index == 0


def test_near_identical_records_not_flagged():
    """Task 8: Near-identical records (punctuation / phrasing) are strictly NOT flagged."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Exact shared substantive target", index=index)
    rec_b = _make_sample_record("syn_q_01", "Exact shared substantive target.", index=index)  # trailing dot

    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    dups = find_exact_duplicate_records(ws_a, ws_b)
    assert len(dups) == 0


def test_normalized_whitespace_case_different_records_not_flagged():
    """Task 8: Records with case or whitespace differences are NOT treated as exact duplicates."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Exact shared substantive target", index=index)
    rec_b = _make_sample_record("syn_q_01", "exact shared substantive target", index=index)  # lowercase

    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    assert len(find_exact_duplicate_records(ws_a, ws_b)) == 0

    # Test whitespace difference
    ws_b2 = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)
    rec_b2 = _make_sample_record("syn_q_01", "Exact shared substantive target ", index=index)  # trailing space
    ws_b2.add_record(rec_b2)

    assert len(find_exact_duplicate_records(ws_a, ws_b2)) == 0


def test_exact_duplicate_flag_does_not_mutate_reviewer_records():
    """Task 8: Exact duplicate flagging is non-destructive and advisory only."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", index)

    rec_a = _make_sample_record("syn_q_01", "Target identical", index=index)
    rec_b = _make_sample_record("syn_q_01", "Target identical", index=index)
    ws_a.add_record(rec_a)
    ws_b.add_record(rec_b)

    # Bind to reconciliation workspace
    ws_recon = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"], ws_a, ws_b)
    q_audit = ws_recon.get_question_audit("syn_q_01")

    # Duplicate was mechanically flagged
    assert len(q_audit.exact_duplicate_pairs) == 1

    # But neither workspace was mutated
    assert len(ws_a.records) == 1
    assert len(ws_b.records) == 1
    rec_text_a = ws_a.records[0]["unit_text"] if isinstance(ws_a.records[0], dict) else ws_a.records[0].unit_text
    rec_text_b = ws_b.records[0]["unit_text"] if isinstance(ws_b.records[0], dict) else ws_b.records[0].unit_text
    assert rec_text_a == "Target identical"
    assert rec_text_b == "Target identical"


# ==============================================================================
# TASK 9, 10, 11: Attestations, New Targets, and Adjudication Tests
# ==============================================================================


def test_completeness_attestations_are_human_entered():
    """Task 9: Completeness attestations start False and must be set by humans."""
    att = CompletenessAttestation()
    assert att.is_complete() is False

    att.considered_both_submissions = True
    assert att.is_complete() is False

    att.all_8_passages_checked = True
    att.omitted_targets_examined = True
    att.new_targets_logged = True
    assert att.is_complete() is False

    att.methodological_issues_identified = True
    assert att.is_complete() is True


def test_human_review_complete_fails_if_required_attestations_absent():
    """Task 9: Transition to human_review_complete requires complete attestations and no unresolved items."""
    q_audit = QuestionReconciliationAudit(question_id="syn_q_01")

    # Incomplete attestations
    with pytest.raises(ReconciliationStateError, match="human completeness attestations are incomplete"):
        q_audit.set_reconciliation_state("human_review_complete")

    # Fulfill all 5 completeness attestations
    q_audit.completeness_attestation.considered_both_submissions = True
    q_audit.completeness_attestation.all_8_passages_checked = True
    q_audit.completeness_attestation.omitted_targets_examined = True
    q_audit.completeness_attestation.new_targets_logged = True
    q_audit.completeness_attestation.methodological_issues_identified = True

    # But unresolved items present
    q_audit.unresolved_items.append(
        UnresolvedDisagreementAuditEntry(
            question_id="syn_q_01",
            human_authored_disagreement_note="Dispute over scope",
            status="unresolved",
        )
    )
    with pytest.raises(ReconciliationStateError, match="unresolved disagreements or adjudication"):
        q_audit.set_reconciliation_state("human_review_complete")

    # Mark unresolved item adjudicated
    q_audit.unresolved_items[0].status = "adjudicated"
    q_audit.set_reconciliation_state("human_review_complete")
    assert q_audit.reconciliation_state == "human_review_complete"


def test_new_target_log_remains_blank_unless_human_enters_it():
    """Task 10: New-target addition log is blank unless explicitly entered by human."""
    q_audit = QuestionReconciliationAudit(question_id="syn_q_01")
    assert len(q_audit.addition_log) == 0

    entry = NewTargetAuditEntry(
        question_id="syn_q_01",
        human_authored_reason="Human reviewers discovered unaddressed limitation during passage audit.",
        reviewer_a_acknowledged=True,
        reviewer_b_acknowledged=True,
        audit_status="accepted",
        audit_notes="Both reviewers agreed this boundary was omitted from initial drafts.",
    )
    q_audit.addition_log.append(entry)
    assert len(q_audit.addition_log) == 1
    assert q_audit.addition_log[0].reviewer_a_acknowledged is True
    assert q_audit.addition_log[0].reviewer_b_acknowledged is True


def test_unresolved_structure_does_not_adjudicate():
    """Task 11: Unresolved container records dispute without software deciding resolution."""
    entry = UnresolvedDisagreementAuditEntry(
        question_id="syn_q_01",
        involved_refs=[
            ReviewerRecordRef(reviewer_role="reviewer_a", record_index=0, question_id="syn_q_01"),
            ReviewerRecordRef(reviewer_role="reviewer_b", record_index=0, question_id="syn_q_01"),
        ],
        human_authored_disagreement_note="Reviewer A decomposed into 2 units; Reviewer B kept as 1 compound relational unit.",
        status="referred_to_adjudication",
        third_adjudicator_required=True,
    )
    assert entry.status == "referred_to_adjudication"
    assert entry.third_adjudicator_required is True
    # Container has no auto-resolve method
    assert not hasattr(entry, "resolve_dispute")
    assert not hasattr(entry, "pick_winner")


# ==============================================================================
# TASK 13: Local Serialization and Notice
# ==============================================================================


def test_serialization_and_local_only_notice(tmp_path: Path):
    """Task 13: Serialization round-trip preserves local-only notice and all audit structures."""
    ws = ReconciliationAuditWorkspace.create_synthetic_blank(["syn_q_01"])
    q_audit = ws.get_question_audit("syn_q_01")
    q_audit.human_notes = "Human reconciliation notes for syn_q_01"
    q_audit.completeness_attestation.considered_both_submissions = True

    out_file = tmp_path / "synthetic_reconciliation_audit.json"
    ws.save_local(out_file)

    loaded = ReconciliationAuditWorkspace.load_synthetic_local(out_file)
    assert loaded.workspace_kind == "synthetic"
    assert loaded.local_only_notice == LOCAL_ONLY_NOTICE
    loaded_audit = loaded.get_question_audit("syn_q_01")
    assert loaded_audit.human_notes == "Human reconciliation notes for syn_q_01"
    assert loaded_audit.completeness_attestation.considered_both_submissions is True
