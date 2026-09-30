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
from typing import Any

import pytest

from research.experiments.cross_perspective_advisory_ablation_v1.reference_units import (
    CALIBRATION_CASE_COVERAGE,
    CALIBRATION_CASE_IDS,
    CALIBRATION_DESIGN_ID,
    CALIBRATION_EVIDENCE_ID_PREFIX,
    CALIBRATION_PACKET_ID_PREFIX,
    FROZEN_PROTOCOL_BYTE_SHA256,
    PROTOCOL_ID,
    STUDY_ID,
    CalibrationCase,
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
    CalibrationPacket,
    CalibrationReviewerWorkspace,
    CalibrationStateError,
    EvidenceAnchor,
    EvidenceSpan,
    ReferenceUnitRecord,
    check_formal_material_separation,
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

    # Use first word of chunk text as target substring
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


# ==============================================================================
# SECTION A: CASE MANIFEST TESTS (Tests 1 to 5)
# ==============================================================================

def test_a01_exactly_eight_planned_case_ids_accepted():
    """Test 1: exactly 8 planned CAL-2CC IDs are accepted in fixture pack."""
    pack = _make_neutral_fixture_pack()
    assert tuple(sorted(pack.cases.keys())) == tuple(sorted(CALIBRATION_CASE_IDS))
    assert len(pack.cases) == 8


def test_a02_missing_case_rejected():
    """Test 2: missing any planned case ID causes validation failure."""
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
    # Mismatch key and case_id
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
    # Specific check for CAL-2CC-05 conflict tag
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
    # Drop one item from TCM packet
    pack.cases["CAL-2CC-01"].tcm_packet.evidence_items.pop()
    with pytest.raises(ValueError, match="Packet must contain exactly 4 evidence items"):
        pack.validate_current_state()


def test_b09_rank_outside_1_to_4_rejected():
    """Test 9: evidence item with rank outside 1..4 is rejected."""
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
    with pytest.raises(ValueError, match="evidence_items ranks must be \\[1, 2, 3, 4\\]"):
        pack.validate_current_state()


def test_b11_evidence_item_chunk_sha256_mismatch_rejected():
    """Test 11: chunk_text_sha256 mismatch is rejected."""
    with pytest.raises(ValueError, match="chunk_text_sha256 mismatch"):
        CalibrationEvidenceItem(
            evidence_id="cal2cc:ev:CAL-2CC-01:tcm:1",
            rank=1,
            exact_chunk_text="Text content",
            chunk_text_sha256="wrong_hash" * 4,
        )


def test_b12_synthetic_id_namespace_enforced_packet_prefix():
    """Test 12: packet ID missing cal2cc:packet: prefix is rejected."""
    with pytest.raises(CalibrationGateError, match="must start with 'cal2cc:packet:'"):
        CalibrationPacket(
            packet_id="other:packet:CAL-2CC-01:tcm",
            perspective="tcm",
            case_id="CAL-2CC-01",
            evidence_items=[],
        )


def test_b13_synthetic_id_namespace_enforced_evidence_prefix():
    """Test 13: evidence ID missing cal2cc:ev: prefix is rejected."""
    with pytest.raises(CalibrationGateError, match="must start with 'cal2cc:ev:'"):
        CalibrationEvidenceItem(
            evidence_id="other:ev:CAL-2CC-01:tcm:1",
            rank=1,
            exact_chunk_text="Neutral text",
            chunk_text_sha256=_make_sha256("Neutral text"),
        )


def test_b14_formal_packet_id_rejected():
    """Test 14: formal study packet ID prefixes are rejected."""
    pack = _make_neutral_fixture_pack(frozen=False)
    pack.cases["CAL-2CC-01"].tcm_packet.packet_id = "cpaa1:packet:tcm:syn_q_01"
    with pytest.raises(CalibrationGateError, match="reuses formal packet prefix"):
        pack.validate_current_state()


def test_b15_formal_evidence_id_rejected():
    """Test 15: formal study evidence ID prefixes are rejected."""
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
# SECTION C: FIXTURE HASH TESTS (Tests 21 to 23)
# ==============================================================================

def test_c21_deterministic_canonical_fixture_hash():
    """Test 21: fixture pack hash is deterministic across identical reconstructions."""
    pack1 = _make_neutral_fixture_pack()
    pack2 = _make_neutral_fixture_pack()
    assert pack1.fixture_pack_canonical_sha256 is not None
    assert pack1.fixture_pack_canonical_sha256 == pack2.fixture_pack_canonical_sha256


def test_c22_fixture_self_hash_verification():
    """Test 22: frozen fixture pack validates its own recorded self-hash."""
    pack = _make_neutral_fixture_pack()
    pack.validate_current_state()
    # Check that computing hash matches recorded
    assert pack.compute_canonical_sha256() == pack.fixture_pack_canonical_sha256


def test_c23_tampered_text_fails_fixture_hash_verification():
    """Test 23: tampering with question text invalidates recorded fixture pack hash."""
    pack = _make_neutral_fixture_pack()
    orig_hash = pack.fixture_pack_canonical_sha256
    # Mutate question text after freeze
    pack.cases["CAL-2CC-01"].question_text = "Tampered question text?"
    with pytest.raises(ValueError, match="fixture_pack_canonical_sha256 mismatch"):
        pack.validate_current_state()


# ==============================================================================
# SECTION D: REVIEWER SUBMISSION AND LOCK TESTS (Tests 24 to 32)
# ==============================================================================

def test_d24_reviewer_role_separation_enforced():
    """Test 24: invalid reviewer role is rejected upon workspace creation."""
    pack = _make_neutral_fixture_pack()
    with pytest.raises(ValueError, match="reviewer_role must be 'reviewer_a' or 'reviewer_b'"):
        CalibrationReviewerWorkspace.create_blank("invalid_role", pack)  # type: ignore[arg-type]


def test_d25_workspace_requires_all_eight_cases():
    """Test 25: reviewer workspace initializes with exactly 8 planned cases."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    assert tuple(sorted(ws.cases.keys())) == tuple(sorted(CALIBRATION_CASE_IDS))


def test_d26_incomplete_case_blocks_lock():
    """Test 26: incomplete cases block submission locking."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    # Only complete 7 cases
    for cid in CALIBRATION_CASE_IDS[:-1]:
        ws.set_no_supportable_unit_reason(cid, "Reason")
        ws.set_case_complete(cid, True)
    with pytest.raises(CalibrationLockError, match="is not marked annotation_complete"):
        ws.lock_submission()


def test_d27_zero_unit_case_with_reason_allows_lock():
    """Test 27: zero-unit case accompanied by human reason allows locking."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Examined all passages; no supportable units found.")
        ws.set_case_complete(cid, True)
    snapshot = ws.lock_submission()
    assert snapshot.submission_hash is not None
    assert ws.is_locked is True


def test_d28_zero_unit_case_without_reason_blocks_lock():
    """Test 28: case marked complete without units or reason blocks locking."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_case_complete(cid, True)
    with pytest.raises(CalibrationLockError, match="has neither reference units nor no_supportable_unit_reason"):
        ws.lock_submission()


def test_d29_structurally_invalid_record_blocks_lock():
    """Test 29: structurally invalid record with out-of-bounds span blocks record addition or lock."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    # Attempt to add record with span past chunk length
    rec = _make_valid_test_record("CAL-2CC-01", pack)
    rec.evidence_anchors[0].spans[0].end = 99999
    with pytest.raises(ValueError, match="exceeds text length"):
        ws.add_record("CAL-2CC-01", rec)


def test_d30_valid_lock_produces_deterministic_snapshot_hash():
    """Test 30: locked submission produces a deterministic canonical hash."""
    pack = _make_neutral_fixture_pack()
    ws = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws.set_no_supportable_unit_reason(cid, "Valid reason")
        ws.set_case_complete(cid, True)
    snap = ws.lock_submission()
    assert len(snap.submission_hash) == 64
    assert snap.validate_current_state() is None


def test_d31_locked_snapshot_is_immutable_against_record_addition():
    """Test 31: adding records or changing reasons in a locked workspace is prohibited."""
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


def test_d32_amendment_requires_incremented_submission_version():
    """Test 32: amending a locked workspace produces a new workspace with submission_version+1."""
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
# SECTION E: A/B COMPARISON GATE TESTS (Tests 33 to 41)
# ==============================================================================

def test_e33_comparison_view_a_only_blocked():
    """Test 33: comparison view cannot be constructed with Reviewer A alone."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Reason A")
        ws_a.set_case_complete(cid, True)
    snap_a = ws_a.lock_submission()

    with pytest.raises(CalibrationComparisonGateError):
        CalibrationComparisonView.from_locked_submissions(snap_a, None)  # type: ignore[arg-type]


def test_e34_comparison_view_b_only_blocked():
    """Test 34: comparison view cannot be constructed with Reviewer B alone."""
    pack = _make_neutral_fixture_pack()
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_b.set_no_supportable_unit_reason(cid, "Reason B")
        ws_b.set_case_complete(cid, True)
    snap_b = ws_b.lock_submission()

    with pytest.raises(CalibrationComparisonGateError):
        CalibrationComparisonView.from_locked_submissions(None, snap_b)  # type: ignore[arg-type]


def test_e35_unlocked_workspace_cannot_construct_comparison_view():
    """Test 35: unlocked workspace cannot supply a submission to comparison view."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)
    with pytest.raises(CalibrationComparisonGateError):
        CalibrationComparisonView.from_locked_submissions(ws_a, ws_b)  # type: ignore[arg-type]


def test_e36_mismatched_fixture_hashes_blocked():
    """Test 36: mismatched fixture pack hashes between A and B block comparison."""
    pack1 = _make_neutral_fixture_pack()
    pack2 = _make_neutral_fixture_pack(frozen=False)
    # Modify pack2 question text to change its hash
    pack2.cases["CAL-2CC-01"].question_text = "Different question text?"
    pack2.freeze()

    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack1)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack2)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Reason A")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Reason B")
        ws_b.set_case_complete(cid, True)
    snap_a = ws_a.lock_submission()
    snap_b = ws_b.lock_submission()

    with pytest.raises(CalibrationComparisonGateError, match="Fixture pack hash mismatch"):
        CalibrationComparisonView.from_locked_submissions(snap_a, snap_b)


def test_e37_wrong_roles_blocked():
    """Test 37: both submissions having role reviewer_a is blocked."""
    pack = _make_neutral_fixture_pack()
    ws_a1 = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_a2 = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a1.set_no_supportable_unit_reason(cid, "Reason A1")
        ws_a1.set_case_complete(cid, True)
        ws_a2.set_no_supportable_unit_reason(cid, "Reason A2")
        ws_a2.set_case_complete(cid, True)
    snap_a1 = ws_a1.lock_submission()
    snap_a2 = ws_a2.lock_submission()

    with pytest.raises(CalibrationComparisonGateError, match="Expected reviewer_b role"):
        CalibrationComparisonView.from_locked_submissions(snap_a1, snap_a2)


def test_e38_dual_valid_locked_snapshots_allowed():
    """Test 38: valid locked Reviewer A and B submissions successfully construct view."""
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
    summary = view.get_case_summary("CAL-2CC-01")
    assert summary["reviewer_a_has_no_unit_reason"] is True
    assert summary["reviewer_b_has_no_unit_reason"] is True


def test_e39_comparison_view_has_no_semantic_matching_methods():
    """Test 39: comparison view exposes zero semantic alignment or similarity methods."""
    assert not hasattr(CalibrationComparisonView, "semantic_match")
    assert not hasattr(CalibrationComparisonView, "calculate_similarity")
    assert not hasattr(CalibrationComparisonView, "auto_align")


def test_e40_comparison_view_has_no_auto_union_or_final_set_methods():
    """Test 40: comparison view exposes zero auto-union, merge, or answer-key methods."""
    assert not hasattr(CalibrationComparisonView, "auto_union")
    assert not hasattr(CalibrationComparisonView, "merge_records")
    assert not hasattr(CalibrationComparisonView, "generate_answer_key")


def test_e41_exact_record_duplicates_flagged_mechanically():
    """Test 41: identical records between A and B are flagged mechanically."""
    pack = _make_neutral_fixture_pack()
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", pack)

    rec = _make_valid_test_record("CAL-2CC-01", pack)
    ws_a.add_record("CAL-2CC-01", rec)
    ws_b.add_record("CAL-2CC-01", rec)

    for cid in CALIBRATION_CASE_IDS:
        if cid != "CAL-2CC-01":
            ws_a.set_no_supportable_unit_reason(cid, "None")
            ws_b.set_no_supportable_unit_reason(cid, "None")
        ws_a.set_case_complete(cid, True)
        ws_b.set_case_complete(cid, True)

    view = CalibrationComparisonView.from_locked_submissions(ws_a.lock_submission(), ws_b.lock_submission())
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
            reviewer_a_position="Include qualifier",
            reviewer_b_position="Omit qualifier",
            ambiguity_classification="C_UNRECOGNIZED",  # type: ignore[arg-type]
        )


def test_f43_open_disagreement_blocks_completion():
    """Test 43: open disagreement in log reports has_open_disagreements=True."""
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

def _make_valid_dual_locked_submissions(fixture_pack: CalibrationFixturePack):
    ws_a = CalibrationReviewerWorkspace.create_blank("reviewer_a", fixture_pack)
    ws_b = CalibrationReviewerWorkspace.create_blank("reviewer_b", fixture_pack)
    for cid in CALIBRATION_CASE_IDS:
        ws_a.set_no_supportable_unit_reason(cid, "Examined; no supportable units.")
        ws_a.set_case_complete(cid, True)
        ws_b.set_no_supportable_unit_reason(cid, "Examined; no supportable units.")
        ws_b.set_case_complete(cid, True)
    return ws_a.lock_submission(), ws_b.lock_submission()


def test_g49_calibration_ready_for_formal_annotation_defaults_false():
    """Test 49: calibration_ready_for_formal_annotation defaults to False."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = CalibrationDisagreementLog(fixture_pack_hash=pack.fixture_pack_canonical_sha256)  # type: ignore[arg-type]
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
    d_log = CalibrationDisagreementLog(fixture_pack_hash=pack.fixture_pack_canonical_sha256)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reviewer_a_submission must be CalibrationLockedSubmission"):
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
    d_log = CalibrationDisagreementLog(
        fixture_pack_hash=pack.fixture_pack_canonical_sha256,  # type: ignore[arg-type]
        entries=[open_entry],
    )
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
    d_log = CalibrationDisagreementLog(
        fixture_pack_hash=pack.fixture_pack_canonical_sha256,  # type: ignore[arg-type]
        entries=[entry],
    )
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
    d_log = CalibrationDisagreementLog(fixture_pack_hash=pack.fixture_pack_canonical_sha256)  # type: ignore[arg-type]

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
    d_log = CalibrationDisagreementLog(fixture_pack_hash=pack.fixture_pack_canonical_sha256)  # type: ignore[arg-type]

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
    """Test 55: checklist has no agreement percentage or denominator calculation logic."""
    assert not hasattr(CalibrationCompletionChecklist, "calculate_agreement_percentage")
    assert not hasattr(CalibrationCompletionChecklist, "agreement_threshold")
    assert not hasattr(CalibrationCompletionChecklist, "preferred_denominator")


# ==============================================================================
# SECTION H: CURRENT-STATE VALIDATION AND MUTATION DEFENSE TESTS (Tests 56 to 63)
# ==============================================================================

def test_h56_post_construction_string_bool_rejected():
    """Test 56: mutating a boolean field to truthy string 'false' is rejected by validate_current_state."""
    pack = _make_neutral_fixture_pack()
    pack.human_authorship_attested = "false"  # type: ignore[assignment]
    with pytest.raises(TypeError, match="must be of type bool"):
        pack.validate_current_state()


def test_h57_post_construction_numeric_bool_rejected():
    """Test 57: mutating a boolean field to numeric 1 is rejected by validate_current_state."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Qualifier",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="A_CASE_LEVEL",
    )
    entry.clarification_refreeze_attested = 1  # type: ignore[assignment]
    with pytest.raises(TypeError, match="must be of type bool"):
        entry.validate_current_state()


def test_h58_post_construction_invalid_disagreement_status_rejected():
    """Test 58: mutating status to invalid string 'bogus' is rejected."""
    entry = CalibrationDisagreementEntry(
        calibration_case_id="CAL-2CC-01",
        disagreement_id="DIS-01",
        decision_category="Qualifier",
        reviewer_a_position="A",
        reviewer_b_position="B",
        ambiguity_classification="A_CASE_LEVEL",
    )
    entry.status = "bogus"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Invalid status 'bogus'"):
        entry.validate_current_state()


def test_h59_direct_construction_resolved_disagreement_without_rationale_fails():
    """Test 59: directly constructing DisagreementEntry with status='resolved' without rationale fails."""
    with pytest.raises(ValueError, match="human_resolution"):
        CalibrationDisagreementEntry(
            calibration_case_id="CAL-2CC-01",
            disagreement_id="DIS-01",
            decision_category="Qualifier",
            reviewer_a_position="A",
            reviewer_b_position="B",
            ambiguity_classification="A_CASE_LEVEL",
            status="resolved",
        )


def test_h60_direct_construction_ready_true_checklist_without_prereqs_fails():
    """Test 60: directly constructing checklist with ready=True without satisfied prereqs fails."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = CalibrationDisagreementLog(fixture_pack_hash=pack.fixture_pack_canonical_sha256)  # type: ignore[arg-type]

    with pytest.raises(CalibrationCompletionError):
        CalibrationCompletionChecklist(
            fixture_pack=pack,
            reviewer_a_submission=sub_a,
            reviewer_b_submission=sub_b,
            disagreement_log=d_log,
            calibration_ready_for_formal_annotation=True,  # Direct constructor bypass attempt!
        )


def test_h61_mutated_locked_snapshot_fails_serialization():
    """Test 61: snapshot mutated after construction fails to_dict()."""
    pack = _make_neutral_fixture_pack()
    sub_a, _ = _make_valid_dual_locked_submissions(pack)
    # Bypassing frozen dataclass using object.__setattr__ to simulate memory corruption
    object.__setattr__(sub_a, "submission_version", 0)
    with pytest.raises(ValueError, match="submission_version"):
        sub_a.to_dict()


def test_h62_mutated_completed_checklist_fails_serialization():
    """Test 62: checklist mutated after completion fails to_dict()."""
    pack = _make_neutral_fixture_pack()
    sub_a, sub_b = _make_valid_dual_locked_submissions(pack)
    d_log = CalibrationDisagreementLog(fixture_pack_hash=pack.fixture_pack_canonical_sha256)  # type: ignore[arg-type]

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
    # Formal packet prefix
    with pytest.raises(CalibrationGateError, match="reuses formal packet prefix"):
        check_formal_material_separation(
            case_ids=["CAL-2CC-01"],
            packet_ids=["packet:tcm:q01"],
            evidence_ids=["cal2cc:ev:CAL-2CC-01:tcm:1"],
        )
    # Formal evidence prefix
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
