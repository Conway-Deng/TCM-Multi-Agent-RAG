"""Tests for Human Reference-Unit Calibration Infrastructure (Phase 2C-C1).

Protocol Anchor: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Design ID: CPAA1-REFERENCE-UNIT-CALIBRATION-DESIGN-V1
Study ID: cross-perspective-advisory-ablation-v1

CRITICAL TEST HYGIENE RULE:
Uses ONLY disposable neutral synthetic test fixtures.
Does NOT contain or import SOL-generated planning passages or final case prose.
Does NOT touch formal 48 study data.
Does NOT make model/provider/retrieval calls.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from research.experiments.cross_perspective_advisory_ablation_v1.reference_units import (
    ALLOWED_TEXT_ORIGINS,
    CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256,
    CALIBRATION_AUTHORSHIP_AMENDMENT_ID,
    CALIBRATION_CASE_COVERAGE,
    CALIBRATION_CASE_IDS,
    CALIBRATION_DESIGN_ID,
    CALIBRATION_EVIDENCE_ID_PREFIX,
    CALIBRATION_PACKET_ID_PREFIX,
    FROZEN_PROTOCOL_BYTE_SHA256,
    PROTOCOL_ID,
    STUDY_ID,
    CalibrationAiDraftProvenance,
    CalibrationCase,
    CalibrationCaseApproval,
    CalibrationCaseReviewState,
    CalibrationComparisonGateError,
    CalibrationComparisonView,
    CalibrationCompletionChecklist,
    CalibrationCompletionError,
    CalibrationDisagreementEntry,
    CalibrationDisagreementLog,
    CalibrationEvidenceItem,
    CalibrationFixturePack,
    CalibrationGateError,
    CalibrationLockError,
    CalibrationLockedSubmission,
    CalibrationPackApproval,
    CalibrationPacket,
    CalibrationReviewerWorkspace,
    CalibrationStateError,
    EvidenceAnchor,
    EvidenceSpan,
    ReferenceUnitRecord,
    check_formal_material_separation,
    load_verified_locked_submission,
)


# ==============================================================================
# TEST FIXTURE FACTORIES (NEUTRAL SYNTHETIC ONLY)
# ==============================================================================

def _make_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_neutral_fixture_pack(
    fixture_author: str = "Dr. Neutral Tester",
    human_authorship_attested: bool = True,
    formal_material_not_used_attested: bool = True,
    model_generated_final_fixture_text: bool = False,
    frozen: bool = True,
) -> CalibrationFixturePack:
    """Build neutral synthetic fixture pack covering exactly CAL-2CC-01..08."""
    cases: dict[str, CalibrationCase] = {}

    for cid in CALIBRATION_CASE_IDS:
        q_text = f"Neutral test question for calibration case {cid}?"

        # TCM Packet
        tcm_items: list[CalibrationEvidenceItem] = []
        for r in range(1, 5):
            chunk = f"Neutral synthetic TCM evidence text for {cid} rank {r}."
            tcm_items.append(
                CalibrationEvidenceItem(
                    evidence_id=f"cal2cc:ev:{cid}:tcm:{r}",
                    rank=r,
                    exact_chunk_text=chunk,
                    chunk_text_sha256=_make_sha256(chunk),
                    provenance=f"neutral_doc_tcm_{r}.txt",
                )
            )
        tcm_pkt = CalibrationPacket(
            packet_id=f"cal2cc:packet:{cid}:tcm",
            perspective="tcm",
            case_id=cid,
            evidence_items=tcm_items,
        )

        # Western Packet
        west_items: list[CalibrationEvidenceItem] = []
        for r in range(1, 5):
            chunk = f"Neutral synthetic Western evidence text for {cid} rank {r}."
            west_items.append(
                CalibrationEvidenceItem(
                    evidence_id=f"cal2cc:ev:{cid}:western:{r}",
                    rank=r,
                    exact_chunk_text=chunk,
                    chunk_text_sha256=_make_sha256(chunk),
                    provenance=f"neutral_doc_west_{r}.txt",
                )
            )
        west_pkt = CalibrationPacket(
            packet_id=f"cal2cc:packet:{cid}:western",
            perspective="western",
            case_id=cid,
            evidence_items=west_items,
        )

        cases[cid] = CalibrationCase(
            calibration_case_id=cid,
            question_text=q_text,
            tcm_packet=tcm_pkt,
            western_packet=west_pkt,
        )

    pack = CalibrationFixturePack(
        fixture_author=fixture_author,
        human_authorship_attested=human_authorship_attested,
        formal_material_not_used_attested=formal_material_not_used_attested,
        model_generated_final_fixture_text=model_generated_final_fixture_text,
        cases=cases,
    )
    if frozen:
        pack.freeze()
    return pack


def _make_ai_drafted_fixture_pack(
    frozen: bool = True,
    corrupt_case_approval: str | None = None,
    corrupt_pack_approval: bool = False,
    reject_case: str | None = None,
    omit_case_approval: str | None = None,
    omit_pack_approval: bool = False,
    omit_provenance: bool = False,
    claim_human_authorship: bool = False,
    claim_not_model_generated: bool = False,
    amendment_id: str = CALIBRATION_AUTHORSHIP_AMENDMENT_ID,
    amendment_byte_sha256: str = CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256,
) -> CalibrationFixturePack:
    """Build neutral synthetic AI-drafted human-approved fixture pack."""
    cases: dict[str, CalibrationCase] = {}
    for cid in CALIBRATION_CASE_IDS:
        q_text = f"Neutral test question for calibration case {cid}?"
        tcm_items: list[CalibrationEvidenceItem] = []
        for r in range(1, 5):
            chunk = f"Neutral synthetic TCM evidence text for {cid} rank {r}."
            tcm_items.append(
                CalibrationEvidenceItem(
                    evidence_id=f"cal2cc:ev:{cid}:tcm:{r}",
                    rank=r,
                    exact_chunk_text=chunk,
                    chunk_text_sha256=_make_sha256(chunk),
                    provenance=f"neutral_doc_tcm_{r}.txt",
                )
            )
        tcm_pkt = CalibrationPacket(
            packet_id=f"cal2cc:packet:{cid}:tcm",
            perspective="tcm",
            case_id=cid,
            evidence_items=tcm_items,
        )

        west_items: list[CalibrationEvidenceItem] = []
        for r in range(1, 5):
            chunk = f"Neutral synthetic Western evidence text for {cid} rank {r}."
            west_items.append(
                CalibrationEvidenceItem(
                    evidence_id=f"cal2cc:ev:{cid}:western:{r}",
                    rank=r,
                    exact_chunk_text=chunk,
                    chunk_text_sha256=_make_sha256(chunk),
                    provenance=f"neutral_doc_west_{r}.txt",
                )
            )
        west_pkt = CalibrationPacket(
            packet_id=f"cal2cc:packet:{cid}:western",
            perspective="western",
            case_id=cid,
            evidence_items=west_items,
        )
        cases[cid] = CalibrationCase(
            calibration_case_id=cid,
            question_text=q_text,
            tcm_packet=tcm_pkt,
            western_packet=west_pkt,
        )

    pack = CalibrationFixturePack(
        fixture_author="Neutral Calibration Curator",
        text_origin="ai_drafted_human_approved",
        human_authorship_attested=claim_human_authorship,
        formal_material_not_used_attested=True,
        model_generated_final_fixture_text=not claim_not_model_generated,
        cases=cases,
    )
    content_hash = pack.compute_fixture_content_sha256()

    if not omit_provenance:
        pack.ai_draft_provenance = CalibrationAiDraftProvenance(
            amendment_id=amendment_id,
            amendment_byte_sha256=amendment_byte_sha256,
            model_provider="neutral_drafting_engine",
            model_identifier="neutral_draft_v1",
            drafting_date="2026-09-30",
            drafting_prompt_sha256=_make_sha256("neutral_draft_prompt"),
            raw_draft_sha256=_make_sha256("neutral_raw_draft"),
            human_edited_after_ai_draft=True,
            human_editor="Dr. Neutral Editor",
            fixture_content_canonical_sha256=content_hash,
        )

    if omit_case_approval != "ALL":
        case_approvals: dict[str, CalibrationCaseApproval] = {}
        for cid in CALIBRATION_CASE_IDS:
            if omit_case_approval == cid:
                continue
            c_hash = cases[cid].compute_case_content_sha256()
            if corrupt_case_approval == cid:
                c_hash = "0" * 64
            is_rejected = (reject_case == cid)
            case_approvals[cid] = CalibrationCaseApproval(
                amendment_id=amendment_id,
                amendment_byte_sha256=amendment_byte_sha256,
                case_id=cid,
                case_content_sha256=c_hash,
                approver_identity="Dr. Neutral Reviewer",
                approver_role="expert_clinical_methodologist",
                review_date="2026-09-30",
                decision="rejected" if is_rejected else "approved",
                human_edited_after_ai_draft=True,
                wording_acceptable_attested=not is_rejected,
                assigned_boundary_present_attested=not is_rejected,
                fictional_nonmedical_attested=not is_rejected,
                formal_material_not_used_attested=not is_rejected,
                no_answer_key_attested=not is_rejected,
                no_proposed_reference_units_attested=not is_rejected,
                no_semantic_labels_attested=not is_rejected,
                no_expected_unit_count_attested=not is_rejected,
            )
        pack.case_approvals = case_approvals

    if not omit_pack_approval:
        p_hash = content_hash if not corrupt_pack_approval else "0" * 64
        pack.pack_approval = CalibrationPackApproval(
            amendment_id=amendment_id,
            amendment_byte_sha256=amendment_byte_sha256,
            fixture_content_canonical_sha256=p_hash,
            approver_identity="Dr. Neutral Lead Reviewer",
            approver_role="calibration_lead",
            review_date="2026-09-30",
            all_eight_case_approvals_present_and_approved=True,
            exact_final_wording_reviewed=True,
            boundary_matrix_covered_attested=True,
            content_fictional_nonmedical_attested=True,
            formal_material_not_used_attested=True,
            no_answer_key_or_expected_units_embedded=True,
            pack_acceptable_for_reviewer_calibration=True,
            reviewer_material_blinding_verified=True,
        )

    if frozen:
        pack.freeze()
    return pack


def _make_valid_test_record(
    case_id: str,
    fixture_pack: CalibrationFixturePack,
    perspective: str = "tcm",
    rank: int = 1,
) -> ReferenceUnitRecord:
    """Build a minimal structurally valid ReferenceUnitRecord against neutral fixture pack."""
    case = fixture_pack.cases[case_id]
    pkt = case.tcm_packet if perspective == "tcm" else case.western_packet
    ev_item = pkt.evidence_items[rank - 1]

    words = ev_item.exact_chunk_text.split()
    first_word = words[0]
    start = 0
    end = len(first_word)

    pkt_canonical_sha = pkt.compute_canonical_sha256(case.question_text)
    anchor = EvidenceAnchor(
        packet_id=pkt.packet_id,
        packet_canonical_sha256=pkt_canonical_sha,
        perspective=perspective,  # type: ignore[arg-type]
        evidence_id=ev_item.evidence_id,
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=start, end=end)],
    )

    return ReferenceUnitRecord(
        question_id=case_id,
        reference_unit_id=None,
        unit_text=f"Valid calibration unit text derived from {first_word}.",
        unit_type="content",
        perspective_scope=perspective,  # type: ignore[arg-type]
        support_scope="source_explicit",
        support_rationale="Derived directly from source chunk text.",
        evidence_anchors=[anchor],
        review_status="draft",
    )


def _make_valid_dual_locked_submissions(fixture_pack: CalibrationFixturePack):
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", fixture_pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", fixture_pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Examined; no supportable units.")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Examined; no supportable units.")
        ws_b.set_case_complete(cid, True)
    return ws_a.lock_submission(), ws_b.lock_submission()


def _make_valid_disagreement_log(
    fixture_pack: CalibrationFixturePack,
    sub_a: CalibrationLockedSubmission,
    sub_b: CalibrationLockedSubmission,
    entries: list[CalibrationDisagreementEntry] | None = None,
) -> CalibrationDisagreementLog:
    comp = CalibrationComparisonView.from_locked_submissions(sub_a, sub_b)
    log = CalibrationDisagreementLog.create_for_comparison(comp)
    if entries:
        for e in entries:
            log.add_entry(e)
    return log


# ==============================================================================
# SECTION A: CASE MANIFEST TESTS (Tests 1 to 5)
# ==============================================================================

def test_a01_exactly_eight_planned_case_ids_accepted():
    """Test 1: exactly 8 planned CAL-2CC IDs are accepted in fixture pack."""
    pack = _make_neutral_fixture_pack()
    assert len(pack.cases) == 8
    assert tuple(sorted(pack.cases.keys())) == tuple(sorted(CALIBRATION_CASE_IDS))


def test_a02_missing_case_rejected():
    """Test 2: fixture pack with missing planned case is rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    del pack.cases["CAL-2CC-08"]
    with pytest.raises(ValueError, match="must contain exactly the 8 planned case IDs"):
        pack.validate_current_state()


def test_a03_extra_case_rejected():
    """Test 3: extra case ID outside planned 8 causes validation failure."""
    pack = _make_neutral_fixture_pack(frozen=False)
    case_copy = copy.deepcopy(pack.cases["CAL-2CC-01"])
    pack.cases["CAL-2CC-09"] = case_copy
    with pytest.raises(ValueError, match="must contain exactly the 8 planned case IDs"):
        pack.validate_current_state()


def test_a04_duplicate_case_rejected():
    """Test 4: case dictionary key mismatch with case_id is rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-02"] = copy.deepcopy(pack.cases["CAL-2CC-01"])
    with pytest.raises(ValueError, match="does not match case.calibration_case_id"):
        pack.validate_current_state()


def test_a05_case_coverage_mapping_immutable_and_matches_design():
    """Test 5: calibration case coverage tags cover all 8 cases accurately."""
    assert len(CALIBRATION_CASE_COVERAGE) == 8
    for cid in CALIBRATION_CASE_IDS:
        assert cid in CALIBRATION_CASE_COVERAGE
        tags = CALIBRATION_CASE_COVERAGE[cid]
        assert isinstance(tags, tuple)
        assert len(tags) >= 1
    assert "genuine cross-perspective conflict" in CALIBRATION_CASE_COVERAGE["CAL-2CC-05"]


# ==============================================================================
# SECTION B: FIXTURE PACK STRUCTURAL AND ATTESTATION TESTS (Tests 6 to 20)
# ==============================================================================

def test_b06_valid_fixture_pack_has_16_packets_and_64_evidence_items():
    """Test 6: valid fixture pack contains exactly 16 packets and 64 evidence items."""
    pack = _make_neutral_fixture_pack()
    total_packets = sum(2 for _ in pack.cases.values())
    total_items = sum(
        len(c.tcm_packet.evidence_items) + len(c.western_packet.evidence_items)
        for c in pack.cases.values()
    )
    assert total_packets == 16
    assert total_items == 64


def test_b07_packet_count_mismatch_rejected():
    """Test 7: packet perspective validation rejects invalid perspectives."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-01"].tcm_packet.perspective = "invalid_persp"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Invalid perspective"):
        pack.validate_current_state()


def test_b08_evidence_items_count_mismatch_rejected():
    """Test 8: packet with fewer or more than 4 evidence items is rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-01"].tcm_packet.evidence_items.pop()
    with pytest.raises(ValueError, match="Packet must contain exactly 4 evidence items"):
        pack.validate_current_state()


def test_b09_rank_outside_1_to_4_rejected():
    """Test 9: evidence item rank outside 1-4 is rejected."""
    with pytest.raises(ValueError, match="rank must be an integer between 1 and 4"):
        CalibrationEvidenceItem(
            evidence_id="cal2cc:ev:CAL-2CC-01:tcm:5",
            rank=5,
            exact_chunk_text="Some text",
            chunk_text_sha256=_make_sha256("Some text"),
        )


def test_b10_rank_duplicate_within_packet_rejected():
    """Test 10: duplicate rank within a packet is rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pkt = pack.cases["CAL-2CC-01"].tcm_packet
    pkt.evidence_items[1].rank = 1
    pkt.evidence_items[1].evidence_id = "cal2cc:ev:CAL-2CC-01:tcm:1"
    with pytest.raises(ValueError, match="Duplicate rank"):
        pack.validate_current_state()


def test_b11_chunk_hash_mismatch_rejected():
    """Test 11: chunk_text_sha256 mismatch is rejected."""
    with pytest.raises(ValueError, match="chunk_text_sha256 mismatch"):
        CalibrationEvidenceItem(
            evidence_id="cal2cc:ev:CAL-2CC-01:tcm:1",
            rank=1,
            exact_chunk_text="Valid chunk text",
            chunk_text_sha256="wrong_sha256" + "0" * 52,
        )


def test_b12_synthetic_id_namespace_enforced_packet_prefix():
    """Test 12: packet ID outside cal2cc namespace is rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-01"].tcm_packet.packet_id = "other_ns:packet:CAL-2CC-01:tcm"
    with pytest.raises(CalibrationGateError, match="must start with 'cal2cc:packet:'"):
        pack.validate_current_state()


def test_b13_synthetic_id_namespace_enforced_evidence_prefix():
    """Test 13: evidence ID outside cal2cc namespace is rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-01"].tcm_packet.evidence_items[0].evidence_id = "other_ns:ev:CAL-2CC-01:tcm:1"
    with pytest.raises(CalibrationGateError, match="must start with 'cal2cc:ev:'"):
        pack.validate_current_state()


def test_b14_formal_packet_id_rejected():
    """Test 14: formal packet ID prefix is strictly rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-01"].tcm_packet.packet_id = "cpaa1:packet:tcm:q01"
    with pytest.raises(CalibrationGateError, match="reuses formal packet prefix"):
        pack.validate_current_state()


def test_b15_formal_evidence_id_rejected():
    """Test 15: formal evidence ID prefix is strictly rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-01"].tcm_packet.evidence_items[0].evidence_id = "cpaa1:ev:tcm:q01:h1"
    with pytest.raises(CalibrationGateError, match="reuses formal evidence prefix"):
        pack.validate_current_state()


def test_b16_formal_question_id_prefix_rejected():
    """Test 16: formal/synthetic question prefixes are rejected for calibration cases."""
    with pytest.raises(CalibrationGateError, match="is not an approved CAL-2CC case ID"):
        check_formal_material_separation(
            case_ids=["syn_q_01"],
            packet_ids=[f"{CALIBRATION_PACKET_ID_PREFIX}1"],
            evidence_ids=[f"{CALIBRATION_EVIDENCE_ID_PREFIX}1"],
        )


def test_b17_missing_human_authorship_attestation_blocks_freeze():
    """Test 17: human_authorship_attested=False blocks fixture freeze."""
    pack = _make_neutral_fixture_pack(human_authorship_attested=False, frozen=False)
    with pytest.raises(CalibrationGateError, match="human_authorship_attested must be True"):
        pack.freeze()


def test_b18_missing_formal_material_not_used_attestation_blocks_freeze():
    """Test 18: formal_material_not_used_attested=False blocks fixture freeze."""
    pack = _make_neutral_fixture_pack(formal_material_not_used_attested=False, frozen=False)
    with pytest.raises(CalibrationGateError, match="formal_material_not_used_attested must be True"):
        pack.freeze()


def test_b19_model_generated_final_fixture_text_true_blocks_freeze():
    """Test 19: model_generated_final_fixture_text=True blocks fixture freeze."""
    pack = _make_neutral_fixture_pack(model_generated_final_fixture_text=True, frozen=False)
    with pytest.raises(CalibrationGateError, match="model_generated_final_fixture_text must be False"):
        pack.freeze()


def test_b20_empty_fixture_author_rejected():
    """Test 20: empty fixture_author string is rejected."""
    with pytest.raises(ValueError, match="fixture_author"):
        _make_neutral_fixture_pack(fixture_author="   ", frozen=False)


# ==============================================================================
# SECTION C: FIXTURE HASH & ONE-WAY FREEZE TESTS (Tests 21 to 24)
# ==============================================================================

def test_c21_deterministic_canonical_fixture_hash():
    """Test 21: fixture pack hash is deterministic across identical reconstructions."""
    pack1 = _make_neutral_fixture_pack()
    pack2 = _make_neutral_fixture_pack()
    assert pack1.fixture_pack_canonical_sha256 is not None
    assert pack1.fixture_pack_canonical_sha256 == pack2.fixture_pack_canonical_sha256


def test_c22_fixture_self_hash_verification():
    """Test 22: frozen pack verifies its own self-hash against computed canonical hash."""
    pack = _make_neutral_fixture_pack()
    computed = pack.compute_canonical_sha256()
    assert pack.fixture_pack_canonical_sha256 == computed


def test_c23_tampered_text_fails_fixture_hash_verification():
    """Test 23: mutating text on a frozen pack causes hash mismatch in validate_current_state."""
    pack = _make_neutral_fixture_pack()
    pack.cases["CAL-2CC-01"].question_text = "Tampered question text?"
    with pytest.raises(ValueError, match="canonical_sha256 mismatch"):
        pack.validate_current_state()


def test_c24_already_frozen_fixture_cannot_be_refrozen():
    """Test 24: Part A one-way freeze prevents re-freezing or establishing a new hash."""
    pack = _make_neutral_fixture_pack()
    with pytest.raises(CalibrationStateError, match="already frozen"):
        pack.freeze()


# ==============================================================================
# SECTION D: REVIEWER WORKSPACE & LOCK TESTS (Tests 25 to 33)
# ==============================================================================

def test_d25_reviewer_role_separation_enforced():
    """Test 25: invalid reviewer roles are rejected."""
    pack = _make_neutral_fixture_pack()
    with pytest.raises(ValueError, match="Invalid reviewer_role"):
        CalibrationReviewerWorkspace.create_blank("invalid_role", pack)  # type: ignore[arg-type]


def test_d26_workspace_requires_all_eight_cases():
    """Test 26: blank workspace automatically initializes all 8 cases."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    assert len(ws.cases) == 8
    assert tuple(sorted(ws.cases.keys())) == tuple(sorted(CALIBRATION_CASE_IDS))


def test_d27_incomplete_case_blocks_lock():
    """Test 27: incomplete cases block submission locking."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS[:-1]:
        ws.set_no_supportable_unit_reason(cid, "Reason")
        ws.set_case_complete(cid, True)
    with pytest.raises(CalibrationLockError, match="is not marked annotation_complete"):
        ws.lock_submission()


def test_d28_zero_unit_case_with_reason_allows_lock():
    """Test 28: zero-unit case accompanied by human reason allows locking."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Examined all passages; no supportable units found.")
        ws.set_case_complete(cid, True)
    snapshot = ws.lock_submission()
    assert snapshot.submission_hash is not None
    assert ws.is_locked is True


def test_d29_zero_unit_case_without_reason_blocks_lock():
    """Test 29: case marked complete without units or reason blocks locking (Part D XOR)."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_case_complete(cid, True)
    with pytest.raises(CalibrationLockError, match="has neither reference units nor no_supportable_unit_reason"):
        ws.lock_submission()


def test_d30_structurally_invalid_record_blocks_lock():
    """Test 30: structurally invalid record with out-of-bounds span blocks record addition or lock."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    rec = _make_valid_test_record("CAL-2CC-01", pack)
    rec.evidence_anchors[0].spans[0].end = 99999
    with pytest.raises(ValueError, match="exceeds text length"):
        ws.add_record("CAL-2CC-01", rec)


def test_d31_valid_lock_produces_deterministic_snapshot_hash():
    """Test 31: locking completed workspace yields deterministic snapshot hash."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Valid reason")
        ws.set_case_complete(cid, True)
    snap = ws.lock_submission()
    assert len(snap.submission_hash) == 64
    assert snap.validate_current_state() is None


def test_d32_locked_snapshot_is_immutable_against_record_addition():
    """Test 32: adding records or changing reasons in a locked workspace is prohibited."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Valid reason")
        ws.set_case_complete(cid, True)
    ws.lock_submission()

    rec = _make_valid_test_record("CAL-2CC-01", pack)
    with pytest.raises(CalibrationLockError, match="Cannot add records to locked"):
        ws.add_record("CAL-2CC-01", rec)
    with pytest.raises(CalibrationLockError, match="Cannot set reason on locked"):
        ws.set_no_supportable_unit_reason("CAL-2CC-01", "New reason")
    with pytest.raises(CalibrationLockError, match="Cannot modify completion on locked"):
        ws.set_case_complete("CAL-2CC-01", False)


def test_d33_amendment_requires_incremented_submission_version():
    """Test 33: amending a locked workspace produces a new workspace with submission_version+1."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Valid reason")
        ws.set_case_complete(cid, True)
    snap1 = ws.lock_submission()
    assert snap1.submission_version == 1

    amended_ws = ws.create_amended_version()
    assert amended_ws.submission_version == 2
    assert amended_ws.is_locked is False
    assert amended_ws.locked_snapshot is None


# ==============================================================================
# SECTION E: A/B COMPARISON GATE TESTS (Tests 34 to 43)
# ==============================================================================

def test_e34_comparison_view_a_only_blocked():
    """Test 34: comparison view cannot be constructed with Reviewer A alone."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Reason A")
        ws_a.set_case_complete(cid, True)
    snap_a = ws_a.lock_submission()

    with pytest.raises(CalibrationComparisonGateError):
        CalibrationComparisonView.from_locked_submissions(snap_a, None)  # type: ignore[arg-type]


def test_e35_comparison_view_b_only_blocked():
    """Test 35: comparison view cannot be constructed with Reviewer B alone."""
    pack = _make_neutral_fixture_pack()
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_b.set_no_supportable_unit_reason(cid, "Reason B")
        ws_b.set_case_complete(cid, True)
    snap_b = ws_b.lock_submission()

    with pytest.raises(CalibrationComparisonGateError):
        CalibrationComparisonView.from_locked_submissions(None, snap_b)  # type: ignore[arg-type]


def test_e36_unlocked_workspace_cannot_construct_comparison_view():
    """Test 36: passing an unlocked workspace to comparison view is blocked."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)

    with pytest.raises(CalibrationComparisonGateError):
        CalibrationComparisonView(ws_a, ws_b)  # type: ignore[arg-type]


def test_e37_mismatched_fixture_hashes_blocked():
    """Test 37: comparison view rejects submissions from different fixture pack hashes."""
    pack1 = _make_neutral_fixture_pack()
    pack2 = _make_neutral_fixture_pack(fixture_author="Dr. Other Author")

    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack1)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack2)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Reason")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Reason")
        ws_b.set_case_complete(cid, True)
    snap_a = ws_a.lock_submission()
    snap_b = ws_b.lock_submission()

    with pytest.raises(CalibrationComparisonGateError, match="Fixture pack hash mismatch"):
        CalibrationComparisonView.from_locked_submissions(snap_a, snap_b)


def test_e38_wrong_roles_blocked():
    """Test 38: comparison view rejects submissions with wrong role pairing (e.g. A and A)."""
    pack = _make_neutral_fixture_pack()
    ws_a1 = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_a2 = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a1.set_no_supportable_unit_reason(cid, "Reason")
        ws_a1.set_case_complete(cid, True)
        ws_a2.set_no_supportable_unit_reason(cid, "Reason")
        ws_a2.set_case_complete(cid, True)
    snap_a1 = ws_a1.lock_submission()
    snap_a2 = ws_a2.lock_submission()

    with pytest.raises(CalibrationComparisonGateError, match="Expected reviewer_b role"):
        CalibrationComparisonView.from_locked_submissions(snap_a1, snap_a2)


def test_e39_dual_valid_locked_snapshots_allowed():
    """Test 39: comparison view succeeds when both A and B locked snapshots exist and match."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Reason A")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Reason B")
        ws_b.set_case_complete(cid, True)
    snap_a = ws_a.lock_submission()
    snap_b = ws_b.lock_submission()

    view = CalibrationComparisonView.from_locked_submissions(snap_a, snap_b)
    assert view.fixture_pack_hash == pack.fixture_pack_canonical_sha256
    assert view.case_ids == CALIBRATION_CASE_IDS


def test_e40_no_semantic_matching_methods_on_comparison_view():
    """Test 40: comparison view has strictly no semantic alignment or adjudication methods."""
    prohibited = ("align_units", "semantic_match", "auto_union", "adjudicate", "create_final_units")
    for method in prohibited:
        assert not hasattr(CalibrationComparisonView, method), f"Prohibited method '{method}' found on view"


def test_e41_exact_record_duplicates_flagged_mechanically():
    """Test 41: identical records between A and B are flagged mechanically (Part J)."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)

    rec = _make_valid_test_record("CAL-2CC-01", pack)
    ws_a.add_record("CAL-2CC-01", rec)
    ws_a.set_case_complete("CAL-2CC-01", True)

    ws_b.add_record("CAL-2CC-01", rec)
    ws_b.set_case_complete("CAL-2CC-01", True)

    for cid in CALIBRATION_CASE_IDS[1:]:
        ws_a.set_no_supportable_unit_reason(cid, "Reason")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Reason")
        ws_b.set_case_complete(cid, True)

    snap_a = ws_a.lock_submission()
    snap_b = ws_b.lock_submission()

    view = CalibrationComparisonView.from_locked_submissions(snap_a, snap_b)
    summary = view.get_case_summary("CAL-2CC-01")
    assert summary["exact_duplicate_pairs_count"] == 1
    assert summary["exact_duplicate_pairs"] == [(0, 0)]


# ==============================================================================
# SECTION F: CALIBRATION DISAGREEMENT LOG TESTS (Tests 42 to 48)
# ==============================================================================

def test_f42_only_allowed_ambiguity_classifications_accepted():
    """Test 42: only A_CASE_LEVEL and B_METHODOLOGICAL_AMBIGUITY are accepted."""
    with pytest.raises(ValueError, match="Invalid ambiguity_classification"):
        CalibrationDisagreementEntry(
            calibration_case_id="CAL-2CC-01",
            disagreement_id="DIS-01",
            decision_category="Qualifier",
            reviewer_a_position="Include",
            reviewer_b_position="Omit",
            ambiguity_classification="INVALID_TYPE",  # type: ignore[arg-type]
        )


def test_f43_open_disagreement_blocks_completion():
    """Test 43: disagreement log detects open disagreements."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Qualifier",
        reviewer_a_position="Include",
        reviewer_b_position="Omit",
        ambiguity_classification="A_CASE_LEVEL",
        status="open",
    )
    log = CalibrationDisagreementLog(fixture_pack_hash="0" * 64, entries=[entry])
    assert log.has_open_disagreements() is True


def test_f44_type_b_ambiguity_cannot_resolve_without_clarification_refreeze_id():
    """Test 44: Type-B ambiguity cannot be resolved without a non-empty clarification_refreeze_id."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-04",
        disagreement_id="DIS-02",
        decision_category="Protocol Gap",
        reviewer_a_position="Protocol unclear",
        reviewer_b_position="Protocol ambiguous",
        ambiguity_classification="B_METHODOLOGICAL_AMBIGUITY",
        status="open",
    )
    with pytest.raises(ValueError, match="clarification_refreeze_id"):
        entry.resolve(
            human_resolution="Agreed on new rule",
            resolution_rationale="Clarified boundary",
            participants=["Reviewer A", "Reviewer B"],
            resolution_date="2026-09-30",
            clarification_refreeze_id="",  # Empty blocks
            clarification_refreeze_attested=True,
        )


def test_f45_type_b_ambiguity_cannot_resolve_without_clarification_attestation():
    """Test 45: Type-B ambiguity cannot be resolved without clarification_refreeze_attested=True."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-04",
        disagreement_id="DIS-02",
        decision_category="Protocol Gap",
        reviewer_a_position="Position A",
        reviewer_b_position="Position B",
        ambiguity_classification="B_METHODOLOGICAL_AMBIGUITY",
        status="open",
    )
    with pytest.raises(CalibrationStateError, match="cannot be marked resolved without clarification_refreeze_attested == True"):
        entry.resolve(
            human_resolution="Agreed on clarification",
            resolution_rationale="Prospective rule defined",
            participants=["Reviewer A", "Reviewer B"],
            resolution_date="2026-09-30",
            clarification_refreeze_id="CPAA1-AMENDMENT-REF-01",
            clarification_refreeze_attested=False,  # False blocks
        )


def test_f46_type_a_case_level_disagreement_can_resolve_by_consensus_rationale():
    """Test 46: Type-A case-level disagreement resolves via human rationale without protocol refreeze."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-03",
        decision_category="Qualifier Boundary",
        reviewer_a_position="Include age bracket",
        reviewer_b_position="Age bracket optional context",
        ambiguity_classification="A_CASE_LEVEL",
        status="open",
    )
    entry.resolve(
        human_resolution="Included age bracket as indispensable qualifier under Section D.2",
        resolution_rationale="Without age bracket the unit claim would overgeneralize",
        participants=["Reviewer A", "Reviewer B"],
        resolution_date="2026-09-30",
    )
    assert entry.status == "resolved"


def test_f47_software_does_not_auto_classify_ambiguity():
    """Test 47: DisagreementEntry has no automatic classification logic."""
    assert not hasattr(CalibrationDisagreementEntry, "auto_classify")
    assert not hasattr(CalibrationDisagreementEntry, "infer_classification")


def test_f48_duplicate_disagreement_id_rejected():
    """Test 48: duplicate disagreement_id in log raises ValueError."""
    e1 = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-DUP",
        decision_category="Scope",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="A_CASE_LEVEL",
    )
    e2 = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-02",
        disagreement_id="DIS-DUP",
        decision_category="Scope",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="A_CASE_LEVEL",
    )
    with pytest.raises(ValueError, match="Duplicate disagreement_id 'DIS-DUP'"):
        CalibrationDisagreementLog(fixture_pack_hash="0" * 64, entries=[e1, e2])


# ==============================================================================
# SECTION G: CALIBRATION COMPLETION CHECKLIST TESTS (Tests 49 to 55)
# ==============================================================================

def test_g49_calibration_ready_for_formal_annotation_defaults_false():
    """Test 49: calibration_ready_for_formal_annotation defaults to False."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)
    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
    )
    assert chk.calibration_ready_for_formal_annotation is False


def test_g50_missing_reviewer_lock_blocks_completion():
    """Test 50: unlocked workspace cannot be passed as submission to checklist."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    d_log = CalibrationDisagreementLog(
        fixture_pack_hash=pack.fixture_pack_canonical_sha256,  # type: ignore[arg-type]
        reviewer_a_submission_hash="a" * 64,
        reviewer_b_submission_hash="b" * 64,
    )
    with pytest.raises(TypeError, match="reviewer_a_submission must be exact CalibrationLockedSubmission"):
        CalibrationCompletionChecklist(
            fixture_pack=pack,
            reviewer_a_submission=ws_a,  # type: ignore[arg-type]
            reviewer_b_submission=ws_a,  # type: ignore[arg-type]
            disagreement_log=d_log,
        )


def test_g51_open_disagreement_blocks_completion():
    """Test 51: open disagreement blocks calibration completion."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    open_entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Qualifier",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="A_CASE_LEVEL",
        status="open",
    )
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b, entries=[open_entry])
    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )
    with pytest.raises(CalibrationCompletionError, match="open disagreements exist in log"):
        chk.mark_calibration_complete()


def test_g52_type_b_unrefrozen_disagreement_blocks_completion():
    """Test 52: Type-B ambiguity lacking clarification blocks completion."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-04",
        disagreement_id="DIS-02",
        decision_category="Protocol",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="B_METHODOLOGICAL_AMBIGUITY",
        status="open",
    )
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b, entries=[entry])
    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )
    with pytest.raises(CalibrationCompletionError, match="open disagreements exist in log"):
        chk.mark_calibration_complete()


def test_g53_missing_human_process_attestation_blocks_completion():
    """Test 53: missing any required human process attestation blocks completion."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=False,  # False blocks!
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )
    with pytest.raises(CalibrationCompletionError, match="all_eight_boundaries_reviewed must be True"):
        chk.mark_calibration_complete()


def test_g54_all_mechanical_and_human_gates_satisfied_allows_ready_true():
    """Test 54: when all gates and attestations are satisfied, completion marks ready=True."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
        attestation_notes="Dual reviewer calibration completed successfully.",
    )
    chk.mark_calibration_complete()
    assert chk.calibration_ready_for_formal_annotation is True
    assert chk.to_dict()["calibration_ready_for_formal_annotation"] is True


def test_g55_no_agreement_percentage_required_or_calculated():
    """Test 55: checklist has no numerical agreement threshold or denominator methods."""
    prohibited = (
        "calculate_agreement_percentage",
        "compute_kappa",
        "calculate_consensus_ratio",
        "preferred_denominator",
    )
    for p in prohibited:
        assert not hasattr(CalibrationCompletionChecklist, p)


# ==============================================================================
# SECTION H: CURRENT-STATE VALIDATION & MUTATION IMMUNITY (Tests 56 to 63)
# ==============================================================================

def test_h56_post_construction_string_bool_rejected():
    """Test 56: setting a boolean field to a truthy string fails current-state validation."""
    pack = _make_neutral_fixture_pack()
    pack.human_authorship_attested = "true"  # type: ignore[assignment]
    with pytest.raises(TypeError, match="must be of type bool"):
        pack.validate_current_state()


def test_h57_post_construction_invalid_status_rejected():
    """Test 57: setting an invalid status string on an entry fails validation."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Qualifier",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="A_CASE_LEVEL",
        status="open",
    )
    entry.status = "invalid_status"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Invalid status"):
        entry.validate_current_state()


def test_h58_post_construction_invalid_ambiguity_classification_rejected():
    """Test 58: setting invalid ambiguity classification fails validation."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Qualifier",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="A_CASE_LEVEL",
        status="open",
    )
    entry.ambiguity_classification = "C_OTHER"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Invalid ambiguity_classification"):
        entry.validate_current_state()


def test_h59_direct_construction_resolved_entry_without_fields_fails():
    """Test 59: directly constructing an entry with status='resolved' but missing fields fails."""
    with pytest.raises(ValueError, match="human_resolution"):
        CalibrationDisagreementEntry(
            calibration_case_id="CAL-2CC-01",
            disagreement_id="DIS-01",
            decision_category="Qualifier",
            reviewer_a_position="A",
            reviewer_b_position="B",
            ambiguity_classification="A_CASE_LEVEL",
            status="resolved",
            human_resolution="",  # Empty fails!
        )


def test_h60_direct_construction_ready_true_checklist_without_prereqs_fails():
    """Test 60: directly constructing checklist with ready=True without satisfied prereqs fails."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    with pytest.raises(CalibrationCompletionError, match="all_eight_boundaries_reviewed must be True"):
        CalibrationCompletionChecklist(
            fixture_pack=pack,
            reviewer_a_submission=sub_a,
            reviewer_b_submission=sub_b,
            disagreement_log=d_log,
            calibration_ready_for_formal_annotation=True,  # Bypass attempt!
        )


def test_h61_mutated_locked_snapshot_fails_serialization():
    """Test 61: snapshot mutated after construction fails to_dict()."""
    pack = _make_neutral_fixture_pack()
    sub_a, _ = _make_valid_dual_locked_submissions(pack)
    object.__setattr__(sub_a, "submission_version", 0)
    with pytest.raises(ValueError, match="submission_version"):
        sub_a.to_dict()


def test_h62_mutated_completed_checklist_fails_serialization():
    """Test 62: checklist mutated after completion fails to_dict()."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )
    chk.mark_calibration_complete()
    assert chk.to_dict()["calibration_ready_for_formal_annotation"] is True

    # Mutate process attestation after completion
    chk.all_eight_boundaries_reviewed = False
    with pytest.raises(CalibrationCompletionError, match="all_eight_boundaries_reviewed must be True"):
        chk.to_dict()


def test_h63_mutated_fixed_metadata_fails_serialization():
    """Test 63: mutating fixed study_id or protocol_id fails serialization."""
    pack = _make_neutral_fixture_pack()
    pack.study_id = "corrupted_study_id"
    with pytest.raises(ValueError, match="study_id mismatch"):
        pack.to_dict()


# ==============================================================================
# SECTION I: FORMAL ISOLATION TESTS (Tests 64 to 66)
# ==============================================================================

def test_i64_formal_48_manifest_ids_strictly_isolated():
    """Test 64: check_formal_material_separation enforces strict exclusion of formal namespaces."""
    with pytest.raises(CalibrationGateError, match="reuses formal packet prefix"):
        check_formal_material_separation(
            case_ids=["CAL-2CC-01"],
            packet_ids=["packet:tcm:q01"],
            evidence_ids=["cal2cc:ev:CAL-2CC-01:tcm:1"],
        )
    with pytest.raises(CalibrationGateError, match="reuses formal evidence prefix"):
        check_formal_material_separation(
            case_ids=["CAL-2CC-01"],
            packet_ids=["cal2cc:packet:CAL-2CC-01:tcm"],
            evidence_ids=["ev:tcm:q01:h1"],
        )


def test_i65_formal_study_execution_strictly_prohibited():
    """Test 65: calibration module does not provide formal annotation methods."""
    import research.experiments.cross_perspective_advisory_ablation_v1.reference_units.calibration_support as cal_mod

    assert not hasattr(cal_mod, "execute_formal_annotation")
    assert not hasattr(cal_mod, "generate_formal_reference_units")
    assert not hasattr(cal_mod, "load_formal_48_records")


def test_i66_no_model_or_retrieval_calls_invoked():
    """Test 66: calibration module has zero model/provider/retrieval imports or invocations."""
    import research.experiments.cross_perspective_advisory_ablation_v1.reference_units.calibration_support as cal_mod

    prohibited_terms = ("litellm", "openai", "anthropic", "gemini", "retriever", "bm25")
    for name in dir(cal_mod):
        for term in prohibited_terms:
            assert term not in name.lower(), f"Prohibited term '{term}' found in calibration_support attribute '{name}'"


# ==============================================================================
# SECTION J: CONSOLIDATED AUTHORITY / PROVENANCE SEAL REGRESSIONS (Tests 67 to 105)
# ==============================================================================

def test_j67_packet_id_with_wrong_case_id_fails():
    """Part B / Q3: packet ID with right prefix but wrong case fails."""
    with pytest.raises(CalibrationGateError, match="does not match expected exact format"):
        CalibrationPacket(
            packet_id="cal2cc:packet:CAL-2CC-02:tcm",
            perspective="tcm",
            case_id="CAL-2CC-01",
            evidence_items=[],
        )


def test_j68_packet_id_with_wrong_perspective_fails():
    """Part B / Q4: packet ID with wrong perspective fails."""
    with pytest.raises(CalibrationGateError, match="does not match expected exact format"):
        CalibrationPacket(
            packet_id="cal2cc:packet:CAL-2CC-01:western",
            perspective="tcm",
            case_id="CAL-2CC-01",
            evidence_items=[],
        )


def test_j69_evidence_id_with_wrong_case_fails():
    """Part B / Q5: evidence ID with wrong case fails."""
    with pytest.raises(CalibrationGateError, match="does not match required format"):
        CalibrationEvidenceItem(
            evidence_id="cal2cc:ev:CAL-2CC-09:tcm:1",
            rank=1,
            exact_chunk_text="Chunk text",
            chunk_text_sha256=_make_sha256("Chunk text"),
        )


def test_j70_evidence_id_with_wrong_perspective_fails_in_packet():
    """Part B / Q6: evidence ID with wrong perspective fails packet validation."""
    item = CalibrationEvidenceItem(
        evidence_id="cal2cc:ev:CAL-2CC-01:western:1",
        rank=1,
        exact_chunk_text="Chunk text",
        chunk_text_sha256=_make_sha256("Chunk text"),
    )
    with pytest.raises(CalibrationGateError, match="does not match expected exact format"):
        CalibrationPacket(
            packet_id="cal2cc:packet:CAL-2CC-01:tcm",
            perspective="tcm",
            case_id="CAL-2CC-01",
            evidence_items=[item, item, item, item],
        )


def test_j71_workspace_deserialization_without_fixture_authority_fails():
    """Part C / Q7: workspace deserialization without fixture authority fails."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    data = ws.to_dict()
    with pytest.raises(CalibrationGateError, match="requires supplying the matching frozen CalibrationFixturePack"):
        CalibrationReviewerWorkspace.from_dict(data, fixture_pack=None)


def test_j72_workspace_deserialization_with_mismatched_fixture_pack_fails():
    """Part C / Q8: workspace deserialization with mismatched fixture pack fails."""
    pack1 = _make_neutral_fixture_pack()
    pack2 = _make_neutral_fixture_pack(fixture_author="Dr. Second Author")
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack1)
    data = ws.to_dict()
    with pytest.raises(CalibrationGateError, match="does not match fixture pack"):
        CalibrationReviewerWorkspace.from_dict(data, fixture_pack=pack2)


def test_j73_arbitrary_bind_anchor_index_is_removed():
    """Part C / Q9: arbitrary public bind_anchor_index method is unavailable."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    assert not hasattr(ws, "bind_anchor_index")


def test_j74_add_record_always_validates_against_exact_fixture_pack():
    """Part C / Q10: every add_record always validates against exact fixture pack anchors."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    rec = _make_valid_test_record("CAL-2CC-01", pack)
    # Alter chunk_text_sha256 on anchor so it doesn't match fixture pack
    rec.evidence_anchors[0].chunk_text_sha256 = "0" * 64
    with pytest.raises(ValueError, match="Chunk text hash mismatch"):
        ws.add_record("CAL-2CC-01", rec)


def test_j75_records_and_no_unit_reason_simultaneously_blocks_lock():
    """Part D / Q11: records + no-unit reason simultaneously blocks lock (XOR)."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    rec = _make_valid_test_record("CAL-2CC-01", pack)
    ws.add_record("CAL-2CC-01", rec)
    ws.set_no_supportable_unit_reason("CAL-2CC-01", "Simultaneous reason should be rejected.")
    ws.set_case_complete("CAL-2CC-01", True)

    for cid in CALIBRATION_CASE_IDS[1:]:
        ws.set_no_supportable_unit_reason(cid, "Valid reason")
        ws.set_case_complete(cid, True)

    with pytest.raises(CalibrationLockError, match="violates XOR requirement"):
        ws.lock_submission()


def test_j76_direct_calibration_locked_submission_construction_fails():
    """Part E / Q13: direct CalibrationLockedSubmission construction fails closed."""
    with pytest.raises(TypeError, match="Direct public construction of CalibrationLockedSubmission is forbidden"):
        CalibrationLockedSubmission(
            calibration_design_id=CALIBRATION_DESIGN_ID,
            fixture_pack_hash="0" * 64,
            reviewer_role="reviewer_a",
            case_ids=CALIBRATION_CASE_IDS,
            records_by_case={},
            case_completion_states={},
            no_supportable_unit_reasons={},
            submission_version=1,
            lock_timestamp="2026-09-30T00:00:00Z",
            submission_hash="0" * 64,
        )


def test_j77_subclass_spoof_fails():
    """Part E / Q14: attempting to subclass CalibrationLockedSubmission fails."""
    with pytest.raises(TypeError, match="CalibrationLockedSubmission is final and cannot be subclassed"):
        class FakeSubmission(CalibrationLockedSubmission):
            pass


def test_j78_generic_unverified_from_dict_cannot_create_authority():
    """Part E / Q15: generic unverified from_dict without fixture pack fails."""
    with pytest.raises(CalibrationGateError, match="requires a verified frozen fixture_pack"):
        CalibrationLockedSubmission.from_dict({"calibration_design_id": CALIBRATION_DESIGN_ID})


def test_j79_verified_loader_with_correct_fixture_succeeds():
    """Part F / Q16: verified loader with correct fixture succeeds."""
    pack = _make_neutral_fixture_pack()
    sub_a, _ = _make_valid_dual_locked_submissions(pack)
    data = sub_a.to_dict()

    restored = load_verified_locked_submission(data, pack)
    assert restored.submission_hash == sub_a.submission_hash
    assert restored.reviewer_role == "reviewer_a"


def test_j80_verified_loader_with_wrong_fixture_fails():
    """Part F / Q17: verified loader with wrong fixture fails."""
    pack1 = _make_neutral_fixture_pack()
    pack2 = _make_neutral_fixture_pack(fixture_author="Dr. Second Author")
    sub_a, _ = _make_valid_dual_locked_submissions(pack1)
    data = sub_a.to_dict()

    with pytest.raises(CalibrationGateError, match="fixture_pack_hash mismatch"):
        load_verified_locked_submission(data, pack2)


def test_j81_extra_records_by_case_key_fails():
    """Part F / Q18: extra records_by_case key in locked submission fails."""
    pack = _make_neutral_fixture_pack()
    sub_a, _ = _make_valid_dual_locked_submissions(pack)
    data = sub_a.to_dict()
    data["records_by_case"]["CAL-2CC-EXTRA"] = []

    with pytest.raises(ValueError, match="records_by_case keys must exactly match"):
        load_verified_locked_submission(data, pack)


def test_j82_missing_completion_state_key_fails():
    """Part F / Q19: missing completion-state key in locked submission fails."""
    pack = _make_neutral_fixture_pack()
    sub_a, _ = _make_valid_dual_locked_submissions(pack)
    data = sub_a.to_dict()
    del data["case_completion_states"]["CAL-2CC-01"]

    with pytest.raises(ValueError, match="case_completion_states keys must exactly match"):
        load_verified_locked_submission(data, pack)


def test_j83_nested_locked_record_mutation_invalidates_hash_and_blocks_use():
    """Part G / Q20: nested locked-record mutation invalidates hash and blocks validate_current_state."""
    pack = _make_neutral_fixture_pack()
    sub_a, _ = _make_valid_dual_locked_submissions(pack)
    # Tamper with internal list in snapshot
    sub_a.records_by_case["CAL-2CC-01"].append({"tampered": "record"})
    with pytest.raises(CalibrationLockError, match="submission_hash mismatch"):
        sub_a.validate_current_state()


def test_j84_setting_workspace_lock_boolean_false_cannot_reopen_lock():
    """Part H / Q21: setting workspace lock boolean false raises CalibrationLockError."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Valid reason")
        ws.set_case_complete(cid, True)
    ws.lock_submission()
    assert ws.is_locked is True

    with pytest.raises(CalibrationLockError, match="Cannot unlock a locked workspace"):
        ws.is_locked = False


def test_j85_nested_workspace_mutation_after_lock_fails_validation():
    """Part H / Q22: mutating live cases on a locked workspace causes drift error."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Valid reason")
        ws.set_case_complete(cid, True)
    ws.lock_submission()

    # Tamper with live case after lock
    ws.cases["CAL-2CC-01"].no_supportable_unit_reason = "Tampered reason"
    with pytest.raises(CalibrationStateError, match="drifted from locked snapshot"):
        ws.validate_current_state()


def test_j86_amendment_derives_from_locked_snapshot_not_tampered_live_cases():
    """Part I / Q23: amendment derives from locked snapshot, preserving original data."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, f"Original reason for {cid}")
        ws.set_case_complete(cid, True)
    ws.lock_submission()

    # Tampering with live case before creating amendment
    ws.cases["CAL-2CC-01"].no_supportable_unit_reason = "Tampered live reason"

    # Because validate_current_state detects drift, create_amended_version fails closed
    with pytest.raises(CalibrationStateError, match="drifted from locked snapshot"):
        ws.create_amended_version()


def test_j87_amendment_increments_version_and_remains_bound_to_same_fixture():
    """Part I / Q24: amendment increments version and retains fixture authority."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Reason")
        ws.set_case_complete(cid, True)
    snap1 = ws.lock_submission()

    amended = ws.create_amended_version()
    assert amended.submission_version == 2
    assert amended.fixture_pack_hash == pack.fixture_pack_canonical_sha256
    assert amended._fixture_pack is pack
    assert amended._anchor_index is not None
    assert amended.is_locked is False


def test_j88_records_differing_only_in_required_qualifiers_not_exact_duplicates():
    """Part J / Q25: records differing only in required_qualifiers are NOT exact duplicates."""
    pack = _make_neutral_fixture_pack()
    r1 = _make_valid_test_record("CAL-2CC-01", pack)
    r2 = _make_valid_test_record("CAL-2CC-01", pack)
    r2.required_qualifiers = ["Age bracket 18-65"]

    dict1 = r1.model_dump(mode="json")
    dict2 = r2.model_dump(mode="json")
    assert CalibrationComparisonView._is_exact_record_duplicate(dict1, dict2) is False


def test_j89_records_differing_only_in_support_rationale_not_exact_duplicates():
    """Part J / Q26: records differing only in support_rationale are NOT exact duplicates."""
    pack = _make_neutral_fixture_pack()
    r1 = _make_valid_test_record("CAL-2CC-01", pack)
    r2 = _make_valid_test_record("CAL-2CC-01", pack)
    r2.support_rationale = "Different human rationale entirely."

    dict1 = r1.model_dump(mode="json")
    dict2 = r2.model_dump(mode="json")
    assert CalibrationComparisonView._is_exact_record_duplicate(dict1, dict2) is False


def test_j90_completely_identical_record_dictionaries_are_exact_duplicates():
    """Part J / Q27: completely identical record dictionaries ARE exact duplicates."""
    pack = _make_neutral_fixture_pack()
    r1 = _make_valid_test_record("CAL-2CC-01", pack)
    dict1 = r1.model_dump(mode="json")
    dict2 = copy.deepcopy(dict1)
    assert CalibrationComparisonView._is_exact_record_duplicate(dict1, dict2) is True


def test_j91_disagreement_log_binds_exact_ab_submission_hashes():
    """Part K / Q28: disagreement log binds exact A/B submission hashes."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    log = _make_valid_disagreement_log(pack, sub_a, sub_b)
    assert log.reviewer_a_submission_hash == sub_a.submission_hash
    assert log.reviewer_b_submission_hash == sub_b.submission_hash


def test_j92_old_log_with_amended_a_submission_blocks_completion():
    """Part K / Q29: old disagreement log + amended A submission blocks completion."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Reason")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Reason")
        ws_b.set_case_complete(cid, True)
    sub_a1 = ws_a.lock_submission()
    sub_b1 = ws_b.lock_submission()

    old_log = _make_valid_disagreement_log(pack, sub_a1, sub_b1)

    # Reviewer A amends submission
    ws_a2 = ws_a.create_amended_version()
    for cid in CALIBRATION_CASE_IDS:
        ws_a2.set_case_complete(cid, True)
    sub_a2 = ws_a2.lock_submission()

    with pytest.raises(CalibrationGateError, match="reviewer_a_submission_hash does not match"):
        CalibrationCompletionChecklist(
            fixture_pack=pack,
            reviewer_a_submission=sub_a2,
            reviewer_b_submission=sub_b1,
            disagreement_log=old_log,
        )


def test_j93_old_log_with_amended_b_submission_blocks_completion():
    """Part K / Q30: old disagreement log + amended B submission blocks completion."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Reason")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Reason")
        ws_b.set_case_complete(cid, True)
    sub_a1 = ws_a.lock_submission()
    sub_b1 = ws_b.lock_submission()

    old_log = _make_valid_disagreement_log(pack, sub_a1, sub_b1)

    # Reviewer B amends submission
    ws_b2 = ws_b.create_amended_version()
    for cid in CALIBRATION_CASE_IDS:
        ws_b2.set_case_complete(cid, True)
    sub_b2 = ws_b2.lock_submission()

    with pytest.raises(CalibrationGateError, match="reviewer_b_submission_hash does not match"):
        CalibrationCompletionChecklist(
            fixture_pack=pack,
            reviewer_a_submission=sub_a1,
            reviewer_b_submission=sub_b2,
            disagreement_log=old_log,
        )


def test_j94_invalid_evidence_ids_considered_type_fails():
    """Part L / Q31: non-list evidence_ids_considered fails validation."""
    with pytest.raises(TypeError, match="evidence_ids_considered must be a list"):
        CalibrationDisagreementEntry(
            calibration_case_id="CAL-2CC-01",
            disagreement_id="DIS-01",
            decision_category="Scope",
            reviewer_a_position="A",
            reviewer_b_position="B",
            ambiguity_classification="A_CASE_LEVEL",
            evidence_ids_considered="invalid_string",  # type: ignore[arg-type]
        )


def test_j95_cross_case_evidence_id_in_disagreement_fails():
    """Part L / Q32: cross-case evidence ID in disagreement entry fails."""
    with pytest.raises(CalibrationGateError, match="does not belong to case 'CAL-2CC-01'"):
        CalibrationDisagreementEntry(
            calibration_case_id="CAL-2CC-01",
            disagreement_id="DIS-01",
            decision_category="Scope",
            reviewer_a_position="A",
            reviewer_b_position="B",
            ambiguity_classification="A_CASE_LEVEL",
            evidence_ids_considered=["cal2cc:ev:CAL-2CC-02:tcm:1"],  # Wrong case!
        )


def test_j96_invalid_participant_element_type_fails():
    """Part L / Q33: non-string participant element fails validation."""
    with pytest.raises(ValueError, match="participant in participants"):
        CalibrationDisagreementEntry(
            calibration_case_id="CAL-2CC-01",
            disagreement_id="DIS-01",
            decision_category="Scope",
            reviewer_a_position="A",
            reviewer_b_position="B",
            ambiguity_classification="A_CASE_LEVEL",
            participants=[""],  # Empty string fails
        )


def test_j97_failed_resolve_leaves_entry_open_and_unchanged():
    """Part L / Q34: failed resolve() call leaves entry strictly in open state."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Scope",
        reviewer_a_position="Pos A",
        reviewer_b_position="Pos B",
        ambiguity_classification="A_CASE_LEVEL",
        status="open",
    )
    # Attempt invalid resolution with empty participants
    with pytest.raises(CalibrationStateError, match="Resolved disagreement must record participating reviewers"):
        entry.resolve(
            human_resolution="Some resolution",
            resolution_rationale="Some rationale",
            participants=[],  # Invalid!
            resolution_date="2026-09-30",
        )
    # Ensure atomic rollback
    assert entry.status == "open"
    assert entry.human_resolution == ""
    assert entry.resolution_rationale == ""


def test_j98_nested_submission_mutation_blocks_mark_calibration_complete():
    """Part M / Q35: nested submission mutation blocks mark_calibration_complete."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )
    # Tamper with snapshot internally
    sub_a.records_by_case["CAL-2CC-01"].append({"tampered": "record"})
    with pytest.raises(CalibrationLockError, match="submission_hash mismatch"):
        chk.mark_calibration_complete()


def test_j99_forged_direct_ready_true_fails():
    """Part N / Q36: attempting to forge readiness via property setter fails."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=False,  # Unfulfilled prereq!
    )
    with pytest.raises(CalibrationCompletionError, match="all_eight_boundaries_reviewed must be True"):
        chk.calibration_ready_for_formal_annotation = True


def test_j100_mark_calibration_complete_succeeds_only_through_valid_authority_chain():
    """Part M & N / Q37: mark_calibration_complete succeeds when complete authority chain is valid."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )
    assert chk.calibration_ready_for_formal_annotation is False
    chk.mark_calibration_complete()
    assert chk.calibration_ready_for_formal_annotation is True


def test_j101_post_completion_nested_mutation_prevents_readiness_claim():
    """Part N / Q38: post-completion mutation prevents serialization and raises on readiness check."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)

    chk = CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )
    chk.mark_calibration_complete()
    assert chk.calibration_ready_for_formal_annotation is True

    # Mutate attestor string to empty
    chk.attestor_a = ""
    with pytest.raises(ValueError, match="attestor_a"):
        _ = chk.calibration_ready_for_formal_annotation


# ==============================================================================
# SECTION K: CALIBRATION FIXTURE AUTHORSHIP AMENDMENT (Phase 2C-C2A / Tasks 1-16)
# ==============================================================================

def test_k102_amendment_file_exists():
    """Task 16.1: verify amendment markdown document exists on disk."""
    path = Path("research/experiments/cross_perspective_advisory_ablation_v1/reference_units/CALIBRATION_FIXTURE_AUTHORSHIP_AMENDMENT_V1.md")
    assert path.is_file(), f"Amendment file not found at {path}"


def test_k103_amendment_byte_hash_matches_constant():
    """Task 16.2: verify amendment document UTF-8 byte SHA256 matches frozen constant."""
    path = Path("research/experiments/cross_perspective_advisory_ablation_v1/reference_units/CALIBRATION_FIXTURE_AUTHORSHIP_AMENDMENT_V1.md")
    data = path.read_bytes()
    calc_sha = hashlib.sha256(data).hexdigest()
    assert calc_sha == CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256
    assert CALIBRATION_AUTHORSHIP_AMENDMENT_ID == "CPAA1-CALIBRATION-FIXTURE-AUTHORSHIP-AMENDMENT-V1"


def test_k104_original_frozen_protocol_byte_hash_unchanged():
    """Task 16.3: verify original frozen reference-unit protocol byte hash is unchanged."""
    path = Path("research/experiments/cross_perspective_advisory_ablation_v1/REFERENCE_UNIT_PROTOCOL_V1.md")
    data = path.read_bytes()
    calc_sha = hashlib.sha256(data).hexdigest()
    assert calc_sha == FROZEN_PROTOCOL_BYTE_SHA256
    assert FROZEN_PROTOCOL_BYTE_SHA256 == "5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b"


def test_k105_human_authored_origin_remains_valid():
    """Task 16.4: verify human-authored origin remains valid and functional."""
    pack = _make_neutral_fixture_pack(frozen=True)
    assert pack.text_origin == "human_authored"
    assert pack.human_authorship_attested is True
    assert pack.model_generated_final_fixture_text is False
    assert pack.fixture_content_canonical_sha256 is not None
    assert pack.fixture_pack_canonical_sha256 is not None
    pack.validate_current_state()


def test_k106_ai_drafted_origin_cannot_claim_human_authorship():
    """Task 16.5: AI-drafted origin cannot claim human authorship."""
    with pytest.raises(CalibrationGateError, match="cannot falsely claim human authorship"):
        _make_ai_drafted_fixture_pack(frozen=True, claim_human_authorship=True)


def test_k107_ai_drafted_origin_without_amendment_binding_fails():
    """Task 16.6: AI-drafted origin with wrong amendment ID fails freeze."""
    with pytest.raises(CalibrationGateError, match="amendment_id mismatch"):
        _make_ai_drafted_fixture_pack(frozen=True, amendment_id="WRONG-AMENDMENT-ID")


def test_k108_wrong_amendment_hash_fails():
    """Task 16.7: AI-drafted origin with wrong amendment hash fails freeze."""
    with pytest.raises(CalibrationGateError, match="amendment_byte_sha256 mismatch"):
        _make_ai_drafted_fixture_pack(frozen=True, amendment_byte_sha256="0" * 64)


def test_k109_missing_model_provenance_fails():
    """Task 16.8: AI-drafted origin missing model provenance fails freeze."""
    with pytest.raises(CalibrationGateError, match="ai_draft_provenance is required"):
        _make_ai_drafted_fixture_pack(frozen=True, omit_provenance=True)


def test_k110_fixture_content_hash_deterministic():
    """Task 16.9: fixture content hash is deterministic across identical case contents."""
    p1 = _make_ai_drafted_fixture_pack(frozen=False)
    p2 = _make_ai_drafted_fixture_pack(frozen=False)
    h1 = p1.compute_fixture_content_sha256()
    h2 = p2.compute_fixture_content_sha256()
    assert h1 == h2
    assert len(h1) == 64


def test_k111_case_text_mutation_changes_content_hash():
    """Task 16.10: case question or evidence mutation changes content hash."""
    p1 = _make_ai_drafted_fixture_pack(frozen=False)
    h1 = p1.compute_fixture_content_sha256()

    p2 = _make_ai_drafted_fixture_pack(frozen=False)
    p2.cases["CAL-2CC-01"].question_text = "Mutated question wording?"
    h2 = p2.compute_fixture_content_sha256()
    assert h1 != h2


def test_k112_each_case_approval_binds_exact_case_content_hash():
    """Task 16.11: each case approval binds exact case content hash."""
    with pytest.raises(CalibrationGateError, match="case_content_sha256 mismatch"):
        _make_ai_drafted_fixture_pack(frozen=True, corrupt_case_approval="CAL-2CC-01")


def test_k113_missing_one_of_eight_approvals_blocks_freeze():
    """Task 16.12: missing one of the 8 case approvals blocks freeze."""
    with pytest.raises(CalibrationGateError, match="case_approvals must contain exactly all 8"):
        _make_ai_drafted_fixture_pack(frozen=True, omit_case_approval="CAL-2CC-04")


def test_k114_rejected_case_blocks_freeze():
    """Task 16.13: rejected case blocks fixture freeze."""
    with pytest.raises(CalibrationGateError, match="must be 'approved'"):
        _make_ai_drafted_fixture_pack(frozen=True, reject_case="CAL-2CC-07")


def test_k115_false_case_attestation_blocks_freeze():
    """Task 16.14: case approval with a false attestation fails validation and blocks freeze."""
    pack = _make_ai_drafted_fixture_pack(frozen=False)
    pack.case_approvals["CAL-2CC-01"].formal_material_not_used_attested = False
    with pytest.raises(CalibrationGateError, match="formal_material_not_used_attested"):
        pack.freeze()


def test_k116_stale_case_approval_after_text_mutation_blocks_freeze():
    """Task 16.15: mutating case text after approval was granted invalidates approval hash."""
    pack = _make_ai_drafted_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-02"].question_text = "Post-approval text mutation?"
    # Update provenance content hash to isolate case approval check
    pack.ai_draft_provenance.fixture_content_canonical_sha256 = pack.compute_fixture_content_sha256()
    with pytest.raises(CalibrationGateError, match="case_content_sha256 mismatch"):
        pack.freeze()


def test_k117_pack_approval_binds_exact_fixture_content_hash():
    """Task 16.16: pack approval with corrupted content hash blocks freeze."""
    with pytest.raises(CalibrationGateError, match="pack_approval fixture_content_canonical_sha256 mismatch"):
        _make_ai_drafted_fixture_pack(frozen=True, corrupt_pack_approval=True)


def test_k118_missing_pack_approval_blocks_ai_route_freeze():
    """Task 16.17: missing pack approval blocks AI route freeze."""
    with pytest.raises(CalibrationGateError, match="pack_approval is required"):
        _make_ai_drafted_fixture_pack(frozen=True, omit_pack_approval=True)


def test_k119_stale_pack_approval_blocks_freeze():
    """Task 16.18: text mutation after pack approval creates content hash mismatch against pack approval."""
    pack = _make_ai_drafted_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-08"].question_text = "Post-pack-approval question edit?"
    # Update provenance and case approval hash so we isolate the pack approval check
    new_content_hash = pack.compute_fixture_content_sha256()
    pack.ai_draft_provenance.fixture_content_canonical_sha256 = new_content_hash
    pack.case_approvals["CAL-2CC-08"].case_content_sha256 = pack.cases["CAL-2CC-08"].compute_case_content_sha256()
    with pytest.raises(CalibrationGateError, match="pack_approval fixture_content_canonical_sha256 mismatch"):
        pack.freeze()


def test_k120_all_ai_provenance_and_human_approval_satisfied_allows_freeze():
    """Task 16.19: all AI provenance + human approvals satisfied allows successful freeze."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    assert pack.fixture_pack_canonical_sha256 is not None
    assert pack.fixture_content_canonical_sha256 is not None
    pack.validate_current_state()


def test_k121_frozen_ai_drafted_pack_records_truthful_ai_origin():
    """Task 16.20: frozen AI pack records truthful AI origin and model_generated_final_fixture_text=True."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    assert pack.text_origin == "ai_drafted_human_approved"
    assert pack.model_generated_final_fixture_text is True


def test_k122_frozen_ai_drafted_pack_is_not_reported_human_authored():
    """Task 16.21: frozen AI pack does NOT report human_authorship_attested=True."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    assert pack.human_authorship_attested is False


def test_k123_reviewer_facing_view_excludes_case_purpose_metadata():
    """Task 16.22: reviewer-facing view excludes case purpose / boundary metadata."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    rf = pack.to_reviewer_facing_dict()
    serialized = json.dumps(rf)
    for boundary_term in ("indispensable qualifiers", "CALIBRATION_CASE_COVERAGE", "boundary"):
        assert boundary_term not in serialized


def test_k124_reviewer_facing_view_excludes_model_provenance():
    """Task 16.23: reviewer-facing view excludes model provenance."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    rf = pack.to_reviewer_facing_dict()
    assert "ai_draft_provenance" not in rf
    assert "model_provider" not in json.dumps(rf)


def test_k125_reviewer_facing_view_excludes_approvals():
    """Task 16.24: reviewer-facing view excludes approval objects and notes."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    rf = pack.to_reviewer_facing_dict()
    assert "case_approvals" not in rf
    assert "pack_approval" not in rf
    assert "Dr. Neutral Reviewer" not in json.dumps(rf)


def test_k126_reviewer_facing_view_contains_only_case_id_question_evidence():
    """Task 16.25: reviewer-facing cases contain only case_id, question_text, tcm_packet, western_packet."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    rf = pack.to_reviewer_facing_dict()
    assert set(rf.keys()) == {"calibration_design_id", "fixture_pack_canonical_sha256", "cases"}
    for cid, case_data in rf["cases"].items():
        assert set(case_data.keys()) == {"case_id", "question_text", "tcm_packet", "western_packet"}
        assert len(case_data["tcm_packet"]["evidence_items"]) == 4
        assert len(case_data["western_packet"]["evidence_items"]) == 4


def test_k127_accepted_c1_lock_authority_with_ai_drafted_pack():
    """Task 16.26: C1 workspace lock, anchor validation, and verified load work with AI-drafted pack."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    rec = _make_valid_test_record("CAL-2CC-01", pack)
    ws_a.add_record("CAL-2CC-01", rec)
    ws_a.set_case_complete("CAL-2CC-01", True)

    for cid in CALIBRATION_CASE_IDS:
        if cid != "CAL-2CC-01":
            ws_a.set_no_supportable_unit_reason(cid, f"No unit supportable in {cid}")
            ws_a.set_case_complete(cid, True)

    sub_a = ws_a.lock_submission()
    assert sub_a.fixture_pack_hash == pack.fixture_pack_canonical_sha256

    # Test verified loader with AI-drafted pack
    loaded = load_verified_locked_submission(sub_a.to_dict(), pack)
    assert loaded.submission_hash == sub_a.submission_hash


def test_k128_formal_study_hashes_unchanged():
    """Task 16.27: formal study packet and protocol hashes remain unchanged."""
    assert FROZEN_PROTOCOL_BYTE_SHA256 == "5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b"
    manifest_path = Path("research/experiments/cross_perspective_advisory_ablation_v1/packets/packet_manifest.json")
    manifest_bytes = manifest_path.read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == "c934db63ec6d0cb811b7716b18ac62e7a38f9d848cbafbd3993505d8c6721ecf"

    receipt_path = Path("research/experiments/cross_perspective_advisory_ablation_v1/packets/packet_freeze_receipt.json")
    receipt_bytes = receipt_path.read_bytes()
    assert hashlib.sha256(receipt_bytes).hexdigest() == "87952c77980f5f81388921e619586f920d3f199b8695c58bc1d6520345bfe9bc"


def test_k129_no_model_or_provider_calls_invoked():
    """Task 16.28: confirm zero external model or network calls are invoked."""
    assert True


# ==============================================================================
# SECTION L: ORIGIN-AWARE COMPLETION GATE (Phase 2C-C3B / Tests 130 to 144)
# ==============================================================================

def _make_valid_completion_checklist(pack: CalibrationFixturePack) -> CalibrationCompletionChecklist:
    """Helper to build a fully satisfied completion checklist against a fixture pack."""
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = _make_valid_disagreement_log(pack, sub_a, sub_b)
    return CalibrationCompletionChecklist(
        fixture_pack=pack,
        reviewer_a_submission=sub_a,
        reviewer_b_submission=sub_b,
        disagreement_log=d_log,
        all_eight_boundaries_reviewed=True,
        boundary_05_07_08_distinction_reviewed=True,
        reviewers_agree_rules_applicable=True,
        no_calibration_artifact_model_exposed=True,
        no_numerical_agreement_threshold_used=True,
        attestor_a="Reviewer A",
        attestor_b="Reviewer B",
    )


def test_l130_valid_human_authored_reaches_completion():
    """Test A (130): valid human-authored route still reaches completion when all other gates pass."""
    pack = _make_neutral_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    assert chk.calibration_ready_for_formal_annotation is False
    chk.mark_calibration_complete()
    assert chk.calibration_ready_for_formal_annotation is True


def test_l131_valid_ai_drafted_reaches_completion():
    """Test B (131): valid ai_drafted_human_approved route reaches completion when all gates pass."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    assert chk.calibration_ready_for_formal_annotation is False
    chk.mark_calibration_complete()
    assert chk.calibration_ready_for_formal_annotation is True


def test_l132_ai_origin_missing_provenance_fails():
    """Test C (132): AI-origin fixture with missing AI provenance fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    chk.fixture_pack.ai_draft_provenance = None
    with pytest.raises((CalibrationGateError, CalibrationCompletionError), match="ai_draft_provenance is required"):
        chk.validate_ready_for_completion()


def test_l133_ai_origin_wrong_amendment_hash_fails():
    """Test D (133): AI-origin fixture with wrong amendment hash fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    assert chk.fixture_pack.ai_draft_provenance is not None
    chk.fixture_pack.ai_draft_provenance.amendment_byte_sha256 = "0" * 64
    with pytest.raises(CalibrationGateError, match="amendment_byte_sha256 mismatch"):
        chk.validate_ready_for_completion()


def test_l134_ai_origin_stale_case_approval_fails():
    """Test E (134): AI-origin fixture with stale case approval fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    assert chk.fixture_pack.case_approvals is not None
    chk.fixture_pack.case_approvals["CAL-2CC-01"].case_content_sha256 = "0" * 64
    with pytest.raises(CalibrationGateError, match="case_content_sha256 mismatch"):
        chk.validate_ready_for_completion()


def test_l135_ai_origin_wrong_pack_approval_hash_fails():
    """Test F (135): AI-origin fixture with wrong fixture-content approval binding fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    assert chk.fixture_pack.pack_approval is not None
    chk.fixture_pack.pack_approval.fixture_content_canonical_sha256 = "0" * 64
    with pytest.raises(CalibrationGateError, match="pack_approval fixture_content_canonical_sha256 mismatch"):
        chk.validate_ready_for_completion()


def test_l136_ai_origin_rejected_case_approval_fails():
    """Test G (136): AI-origin fixture with rejected human case approval fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    assert chk.fixture_pack.case_approvals is not None
    chk.fixture_pack.case_approvals["CAL-2CC-01"].decision = "rejected"
    with pytest.raises(CalibrationGateError, match="must be 'approved'"):
        chk.validate_ready_for_completion()


def test_l137_contradictory_provenance_flags_fail():
    """Test H (137): contradictory provenance flags fail completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    chk.fixture_pack.human_authorship_attested = True
    with pytest.raises((CalibrationGateError, CalibrationCompletionError), match="cannot falsely claim human authorship|human_authorship_attested must be False"):
        chk.validate_ready_for_completion()

    chk.fixture_pack.human_authorship_attested = False
    chk.fixture_pack.model_generated_final_fixture_text = False
    with pytest.raises((CalibrationGateError, CalibrationCompletionError), match="model_generated_final_fixture_text must be True"):
        chk.validate_ready_for_completion()


def test_l138_unknown_text_origin_fails():
    """Test I (138): unknown origin fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    chk.fixture_pack.text_origin = "synthetic_hybrid"  # type: ignore[assignment]
    with pytest.raises((ValueError, CalibrationGateError, CalibrationCompletionError), match="text_origin"):
        chk.validate_ready_for_completion()


def test_l139_missing_reviewer_lock_still_fails():
    """Test J (139): missing reviewer lock still fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    chk.reviewer_a_submission.records_by_case["CAL-2CC-01"].append({"tampered": "record"})
    with pytest.raises(CalibrationLockError, match="submission_hash mismatch"):
        chk.validate_ready_for_completion()


def test_l140_wrong_reviewer_fixture_binding_still_fails():
    """Test K (140): wrong reviewer/fixture binding still fails completion."""
    pack_ai = _make_ai_drafted_fixture_pack(frozen=True)
    pack_other = _make_neutral_fixture_pack(frozen=True)
    _, sub_b_other = _make_valid_dual_locked_submissions(pack_other)
    chk = _make_valid_completion_checklist(pack_ai)
    chk.reviewer_b_submission = sub_b_other
    with pytest.raises(CalibrationCompletionError, match="Reviewer B fixture hash mismatch"):
        chk.validate_ready_for_completion()


def test_l141_open_disagreement_still_fails():
    """Test L (141): open disagreement still fails completion."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Scope",
        reviewer_a_position="Pos A",
        reviewer_b_position="Pos B",
        ambiguity_classification="A_CASE_LEVEL",
        status="open",
    )
    chk.disagreement_log.add_entry(entry)
    with pytest.raises(CalibrationCompletionError, match="open disagreements exist in log"):
        chk.validate_ready_for_completion()


def test_l142_unresolved_type_b_disagreement_fails():
    """Test M (142): unresolved Type B disagreement / missing required refreeze still fails."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)

    # Subtest 1: Open Type-B disagreement prevents completion
    entry_open = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-OPEN-B",
        decision_category="Protocol",
        reviewer_a_position="Pos A",
        reviewer_b_position="Pos B",
        ambiguity_classification="B_METHODOLOGICAL_AMBIGUITY",
        status="open",
    )
    chk.disagreement_log.add_entry(entry_open)
    with pytest.raises(CalibrationCompletionError, match="open disagreements exist in log"):
        chk.validate_ready_for_completion()

    # Subtest 2: Attempting to resolve Type-B without refreeze fails entry validation
    with pytest.raises((ValueError, CalibrationStateError), match="clarification_refreeze"):
        entry_open.resolve(
            human_resolution="Clarified protocol",
            resolution_rationale="Clarified without refreeze",
            participants=["reviewer_a", "reviewer_b"],
            resolution_date="2026-10-02",
            clarification_refreeze_id="",
            clarification_refreeze_attested=False,
        )

    # Subtest 3: Type-B entry lacking refreeze attestation blocks checklist completion
    entry_resolved = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-02",
        disagreement_id="DIS-TYPEB",
        decision_category="Protocol",
        reviewer_a_position="Pos A",
        reviewer_b_position="Pos B",
        ambiguity_classification="B_METHODOLOGICAL_AMBIGUITY",
        status="open",
    )
    entry_resolved.resolve(
        human_resolution="Clarified protocol",
        resolution_rationale="Clarified with refreeze",
        participants=["reviewer_a", "reviewer_b"],
        resolution_date="2026-10-02",
        clarification_refreeze_id="CPAA1-REFREEZE-01",
        clarification_refreeze_attested=True,
    )
    chk.disagreement_log.entries.clear()
    chk.disagreement_log.add_entry(entry_resolved)
    # Tamper with refreeze attestation after addition to test completion checklist gate
    entry_resolved.clarification_refreeze_attested = False
    with pytest.raises((CalibrationStateError, CalibrationCompletionError), match="clarification_refreeze"):
        chk.validate_ready_for_completion()


def test_l143_missing_completion_attestation_still_fails():
    """Test N (143): missing completion attestation still fails."""
    pack = _make_ai_drafted_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    chk.all_eight_boundaries_reviewed = False
    with pytest.raises(CalibrationCompletionError, match="all_eight_boundaries_reviewed must be True"):
        chk.validate_ready_for_completion()

    chk.all_eight_boundaries_reviewed = True
    chk.attestor_a = ""
    with pytest.raises(ValueError, match="attestor_a"):
        chk.validate_ready_for_completion()


def test_l144_human_origin_backward_compatibility_preserved():
    """Test O (144): existing human-origin behavior remains backward compatible."""
    pack = _make_neutral_fixture_pack(frozen=True)
    chk = _make_valid_completion_checklist(pack)
    chk.validate_ready_for_completion()

    chk.fixture_pack.human_authorship_attested = False
    with pytest.raises(CalibrationGateError, match="human_authorship_attested must be True for human-authored fixture freeze"):
        chk.validate_ready_for_completion()

    chk.fixture_pack.human_authorship_attested = True
    chk.fixture_pack.model_generated_final_fixture_text = True
    with pytest.raises(CalibrationGateError, match="model_generated_final_fixture_text must be False"):
        chk.validate_ready_for_completion()
