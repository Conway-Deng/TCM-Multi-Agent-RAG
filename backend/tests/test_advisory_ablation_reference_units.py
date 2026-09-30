"""Unit and Structural Integration Tests for Advisory Ablation Reference-Unit Infrastructure.

Protocol Anchor: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Schema Version: cpaa1_reference_unit_v1
Study ID: cross-perspective-advisory-ablation-v1

These tests use HUMAN-WRITTEN SYNTHETIC fixtures for semantic-looking test cases.
No actual study reference units or medical evidence text are embedded in these tests.

Real packet tests are strictly limited to a read-only mechanical smoke test that
verifies the anchor index loads and indexes the frozen packet JSONLs correctly.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from research.experiments.cross_perspective_advisory_ablation_v1.reference_units import (
    ALLOWED_ANCHOR_PERSPECTIVES,
    ALLOWED_ANCHOR_ROLES,
    ALLOWED_PERSPECTIVE_SCOPES,
    ALLOWED_REVIEW_STATUSES,
    ALLOWED_SUPPORT_SCOPES,
    ALLOWED_UNIT_TYPES,
    ALLOWED_VALIDATION_MODES,
    FINAL_REFERENCE_UNIT_ID_PATTERN,
    FROZEN_PROTOCOL_BYTE_SHA256,
    FROZEN_TCM_PACKET_BYTE_SHA256,
    FROZEN_WESTERN_PACKET_BYTE_SHA256,
    FormalPacketAuthorityError,
    PROTOCOL_ID,
    SCHEMA_VERSION,
    STUDY_ID,
    EvidenceAnchor,
    EvidenceItemMetadata,
    EvidenceSpan,
    FrozenPacketAnchorIndex,
    PacketMetadata,
    ReferenceUnitRecord,
    format_final_reference_unit_id,
    parse_final_reference_unit_id,
    validate_evidence_anchor,
    validate_reference_unit_record,
    verify_packet_records_integrity,
)


# ==============================================================================
# Synthetic Fixture Helpers (Non-Medical, Synthetic Data Only)
# ==============================================================================

def _make_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_synthetic_packet_records() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create synthetic in-memory TCM and Western packets for testing."""
    tcm_records = []
    western_records = []

    for q_idx in range(1, 3):  # 2 synthetic questions: syn_q_01, syn_q_02
        qid = f"syn_q_{q_idx:02d}"

        # TCM packet
        tcm_pkt_id = f"packet:tcm:{qid}"
        tcm_items = []
        for r in range(1, 5):
            ev_id = f"ev:tcm:{qid}:h{r}"
            text = f"Synthetic TCM evidence chunk {r} with unicode text: 证据内容_{r}"
            tcm_items.append({
                "evidence_id": ev_id,
                "rank": r,
                "chunk_text_sha256": _make_sha256(text),
                "exact_chunk_text": text,
            })
        tcm_records.append({
            "packet_id": tcm_pkt_id,
            "question_id": qid,
            "perspective": "tcm",
            "packet_canonical_sha256": _make_sha256(f"tcm_packet_canonical_{qid}"),
            "evidence_items": tcm_items,
        })

        # Western packet
        western_pkt_id = f"packet:western:{qid}"
        western_items = []
        for r in range(1, 5):
            ev_id = f"ev:western:{qid}:h{r}"
            text = f"Synthetic Western evidence chunk {r} with unicode text: EvidenceContent_{r}"
            western_items.append({
                "evidence_id": ev_id,
                "rank": r,
                "chunk_text_sha256": _make_sha256(text),
                "exact_chunk_text": text,
            })
        western_records.append({
            "packet_id": western_pkt_id,
            "question_id": qid,
            "perspective": "western",
            "packet_canonical_sha256": _make_sha256(f"western_packet_canonical_{qid}"),
            "evidence_items": western_items,
        })

    return tcm_records, western_records


@pytest.fixture
def synthetic_index() -> FrozenPacketAnchorIndex:
    tcm_recs, western_recs = _make_synthetic_packet_records()
    return FrozenPacketAnchorIndex.from_packet_records(tcm_recs, western_recs)


# ==============================================================================
# 1. Protocol Constants and Enum Tests
# ==============================================================================

def test_protocol_constants_and_enums():
    assert SCHEMA_VERSION == "cpaa1_reference_unit_v1"
    assert STUDY_ID == "cross-perspective-advisory-ablation-v1"
    assert PROTOCOL_ID == "CPAA1-REFERENCE-UNIT-PROTOCOL-V1"
    assert (
        FROZEN_PROTOCOL_BYTE_SHA256
        == "5ab2f681e605f3bc75ef6e91fa8d864a102aa60e6b14efdda132448845dcb46b"
    )

    assert ALLOWED_UNIT_TYPES == {"content", "relationship", "limitation", "evidence_gap"}
    assert ALLOWED_PERSPECTIVE_SCOPES == {"tcm", "western", "both"}
    assert ALLOWED_ANCHOR_PERSPECTIVES == {"tcm", "western"}
    assert ALLOWED_ANCHOR_ROLES == {"supporting_span", "contrasting_span", "scope_audit"}
    assert ALLOWED_SUPPORT_SCOPES == {
        "source_explicit",
        "cross_span_synthesis",
        "packet_bounded_absence",
    }
    assert ALLOWED_REVIEW_STATUSES == {"draft", "disputed", "reconciled"}


# ==============================================================================
# 2. EvidenceSpan Model Tests
# ==============================================================================

def test_evidence_span_validation():
    # Valid span
    span = EvidenceSpan(start=0, end=15)
    assert span.start == 0
    assert span.end == 15

    # Negative start fails
    with pytest.raises(ValidationError, match="non-negative"):
        EvidenceSpan(start=-1, end=10)

    # start == end fails (must be non-empty interval)
    with pytest.raises(ValidationError, match="strictly less than"):
        EvidenceSpan(start=5, end=5)

    # start > end fails
    with pytest.raises(ValidationError, match="strictly less than"):
        EvidenceSpan(start=10, end=5)

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        EvidenceSpan(start=0, end=5, extra="invalid")


# ==============================================================================
# 3. EvidenceAnchor Model Tests
# ==============================================================================

def test_evidence_anchor_role_and_spans():
    pkt_hash = "a" * 64
    txt_hash = "b" * 64

    # supporting_span with span is valid
    anchor_supp = EvidenceAnchor(
        packet_id="pkt:1",
        packet_canonical_sha256=pkt_hash,
        perspective="tcm",
        evidence_id="ev:1",
        chunk_text_sha256=txt_hash,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=5)],
    )
    assert len(anchor_supp.spans) == 1

    # supporting_span with empty spans fails
    with pytest.raises(ValidationError, match="cannot be empty"):
        EvidenceAnchor(
            packet_id="pkt:1",
            packet_canonical_sha256=pkt_hash,
            perspective="tcm",
            evidence_id="ev:1",
            chunk_text_sha256=txt_hash,
            anchor_role="supporting_span",
            spans=[],
        )

    # contrasting_span with empty spans fails
    with pytest.raises(ValidationError, match="cannot be empty"):
        EvidenceAnchor(
            packet_id="pkt:1",
            packet_canonical_sha256=pkt_hash,
            perspective="western",
            evidence_id="ev:1",
            chunk_text_sha256=txt_hash,
            anchor_role="contrasting_span",
            spans=[],
        )

    # scope_audit with empty spans is VALID (per Section G)
    anchor_audit = EvidenceAnchor(
        packet_id="pkt:1",
        packet_canonical_sha256=pkt_hash,
        perspective="western",
        evidence_id="ev:1",
        chunk_text_sha256=txt_hash,
        anchor_role="scope_audit",
        spans=[],
    )
    assert len(anchor_audit.spans) == 0

    # Invalid hash format fails
    with pytest.raises(ValidationError, match="64-character lowercase hex"):
        EvidenceAnchor(
            packet_id="pkt:1",
            packet_canonical_sha256="g" * 64,
            perspective="tcm",
            evidence_id="ev:1",
            chunk_text_sha256=txt_hash,
            anchor_role="supporting_span",
            spans=[EvidenceSpan(start=0, end=5)],
        )


# ==============================================================================
# 4. Final Reference Unit ID Formatting and Parsing Tests
# ==============================================================================

def test_final_reference_unit_id_formatting_and_parsing():
    fid = format_final_reference_unit_id("q_01", 1)
    assert fid == "cpaa1:ru:q_01:001"

    fid999 = format_final_reference_unit_id("q_01", 999)
    assert fid999 == "cpaa1:ru:q_01:999"

    with pytest.raises(ValueError, match="between 1 and 999"):
        format_final_reference_unit_id("q_01", 0)

    with pytest.raises(ValueError, match="between 1 and 999"):
        format_final_reference_unit_id("q_01", 1000)

    parsed = parse_final_reference_unit_id("cpaa1:ru:q_01:001")
    assert parsed == ("q_01", 1)

    parsed_dash = parse_final_reference_unit_id("cpaa1:ru:q-alpha_02:042")
    assert parsed_dash == ("q-alpha_02", 42)

    assert parse_final_reference_unit_id("invalid_id") is None
    assert parse_final_reference_unit_id("cpaa1:ru:q_01:1") is None  # Needs 3 digits
    assert parse_final_reference_unit_id("cpaa1:ru:q_01:0001") is None


# ==============================================================================
# 5. Synthetic TCM-Only Content Unit Tests (Draft and Final Candidate)
# ==============================================================================

def test_synthetic_tcm_content_unit(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    assert tcm_pkt is not None
    ev_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    assert ev_item is not None

    anchor = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=10)],
    )

    # 1. Draft mode: unassigned ID and draft status is valid
    draft_rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id=None,
        unit_text="Synthetic proposition for TCM indication.",
        unit_type="content",
        perspective_scope="tcm",
        evidence_anchors=[anchor],
        support_scope="source_explicit",
        required_qualifiers=["mild_cases_only"],
        support_rationale="Synthetic rationale explaining direct support from chunk 1.",
        review_status="draft",
    )
    draft_errors = validate_reference_unit_record(
        draft_rec, mode="draft", packet_index=synthetic_index
    )
    assert not draft_errors

    # 2. Final candidate mode: fails if review_status is draft
    cand_errors = validate_reference_unit_record(
        draft_rec, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("review_status='reconciled'" in e for e in cand_errors)
    assert any("reference_unit_id" in e for e in cand_errors)

    # 3. Final candidate mode: valid when reconciled and assigned final ID
    final_rec = draft_rec.model_copy(
        update={
            "review_status": "reconciled",
            "reference_unit_id": "cpaa1:ru:syn_q_01:001",
        }
    )
    final_errors = validate_reference_unit_record(
        final_rec, mode="final_candidate", packet_index=synthetic_index
    )
    assert not final_errors


# ==============================================================================
# 6. Synthetic Western-Only Content Unit Tests
# ==============================================================================

def test_synthetic_western_content_unit(synthetic_index: FrozenPacketAnchorIndex):
    west_pkt = synthetic_index.get_packet("packet:western:syn_q_01")
    assert west_pkt is not None
    ev_item = synthetic_index.get_evidence("packet:western:syn_q_01", "ev:western:syn_q_01:h1")
    assert ev_item is not None

    anchor = EvidenceAnchor(
        packet_id="packet:western:syn_q_01",
        packet_canonical_sha256=west_pkt.packet_canonical_sha256,
        perspective="western",
        evidence_id="ev:western:syn_q_01:h1",
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=5, end=20)],
    )

    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:002",
        unit_text="Synthetic Western trial finding on outcome X.",
        unit_type="content",
        perspective_scope="western",
        evidence_anchors=[anchor],
        support_scope="source_explicit",
        required_qualifiers=["adult_population"],
        support_rationale="Synthetic rationale explaining Western trial finding.",
        review_status="reconciled",
    )
    errors = validate_reference_unit_record(
        rec, mode="final_candidate", packet_index=synthetic_index
    )
    assert not errors


# ==============================================================================
# 7. Synthetic Both-Perspective Relationship Unit Tests (Task 10)
# ==============================================================================

def test_synthetic_both_perspective_relationship_unit(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    west_pkt = synthetic_index.get_packet("packet:western:syn_q_01")
    assert tcm_pkt and west_pkt

    ev_tcm = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    ev_west = synthetic_index.get_evidence("packet:western:syn_q_01", "ev:western:syn_q_01:h1")
    assert ev_tcm and ev_west

    anchor_tcm = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_tcm.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=10)],
    )
    anchor_west = EvidenceAnchor(
        packet_id="packet:western:syn_q_01",
        packet_canonical_sha256=west_pkt.packet_canonical_sha256,
        perspective="western",
        evidence_id="ev:western:syn_q_01:h1",
        chunk_text_sha256=ev_west.chunk_text_sha256,
        anchor_role="contrasting_span",
        spans=[EvidenceSpan(start=0, end=10)],
    )

    # Valid: has both TCM and Western pertinent anchors
    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:003",
        unit_text="Synthetic relational comparison between TCM concept and Western trial outcome.",
        unit_type="relationship",
        perspective_scope="both",
        evidence_anchors=[anchor_tcm, anchor_west],
        support_scope="cross_span_synthesis",
        required_qualifiers=[],
        support_rationale="Synthetic rationale synthesizing TCM and Western perspectives.",
        review_status="reconciled",
    )
    assert not validate_reference_unit_record(
        rec, mode="final_candidate", packet_index=synthetic_index
    )

    # Missing Western anchor fails perspective_scope='both' check
    rec_missing_west = rec.model_copy(update={"evidence_anchors": [anchor_tcm]})
    errs = validate_reference_unit_record(
        rec_missing_west, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("at least one pertinent supporting/contrasting anchor from Western" in e for e in errs)

    # Missing TCM anchor fails perspective_scope='both' check
    rec_missing_tcm = rec.model_copy(update={"evidence_anchors": [anchor_west]})
    errs2 = validate_reference_unit_record(
        rec_missing_tcm, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("at least one pertinent supporting/contrasting anchor from TCM" in e for e in errs2)


# ==============================================================================
# 8. Scope Audit Anchors in Single-Perspective Units (Task 10)
# ==============================================================================

def test_scope_audit_anchor_in_single_perspective_unit(synthetic_index: FrozenPacketAnchorIndex):
    """Confirm Western scope_audit anchors in a TCM-scope unit are NOT rejected."""
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    west_pkt = synthetic_index.get_packet("packet:western:syn_q_01")
    ev_tcm = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    ev_west = synthetic_index.get_evidence("packet:western:syn_q_01", "ev:western:syn_q_01:h1")
    assert tcm_pkt and west_pkt and ev_tcm and ev_west

    anchor_tcm = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_tcm.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=10)],
    )
    anchor_west_audit = EvidenceAnchor(
        packet_id="packet:western:syn_q_01",
        packet_canonical_sha256=west_pkt.packet_canonical_sha256,
        perspective="western",
        evidence_id="ev:western:syn_q_01:h1",
        chunk_text_sha256=ev_west.chunk_text_sha256,
        anchor_role="scope_audit",
        spans=[],
    )

    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:004",
        unit_text="Synthetic TCM-specific proposition with Western scope audit.",
        unit_type="content",
        perspective_scope="tcm",
        evidence_anchors=[anchor_tcm, anchor_west_audit],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="TCM content established with explicit audit of Western silence.",
        review_status="reconciled",
    )
    errors = validate_reference_unit_record(
        rec, mode="final_candidate", packet_index=synthetic_index
    )
    assert not errors, f"Unexpected errors: {errors}"


# ==============================================================================
# 9. Packet Bounded Absence Structural Rules (Task 11)
# ==============================================================================

def test_packet_bounded_absence_structural_rules(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    west_pkt = synthetic_index.get_packet("packet:western:syn_q_01")
    assert tcm_pkt and west_pkt

    # Build all 8 scope_audit anchors (4 TCM + 4 Western)
    all_audit_anchors = []
    for r in range(1, 5):
        ev_id = f"ev:tcm:syn_q_01:h{r}"
        ev_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", ev_id)
        assert ev_item
        all_audit_anchors.append(
            EvidenceAnchor(
                packet_id="packet:tcm:syn_q_01",
                packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
                perspective="tcm",
                evidence_id=ev_id,
                chunk_text_sha256=ev_item.chunk_text_sha256,
                anchor_role="scope_audit",
                spans=[],
            )
        )
    for r in range(1, 5):
        ev_id = f"ev:western:syn_q_01:h{r}"
        ev_item = synthetic_index.get_evidence("packet:western:syn_q_01", ev_id)
        assert ev_item
        all_audit_anchors.append(
            EvidenceAnchor(
                packet_id="packet:western:syn_q_01",
                packet_canonical_sha256=west_pkt.packet_canonical_sha256,
                perspective="western",
                evidence_id=ev_id,
                chunk_text_sha256=ev_item.chunk_text_sha256,
                anchor_role="scope_audit",
                spans=[],
            )
        )

    # 1. Valid: unit_type='evidence_gap', support_scope='packet_bounded_absence', all 8 anchors
    rec_gap = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:005",
        unit_text="Synthetic gap: evidence does not report adverse effect incidence.",
        unit_type="evidence_gap",
        perspective_scope="both",
        evidence_anchors=all_audit_anchors,
        support_scope="packet_bounded_absence",
        required_qualifiers=[],
        support_rationale="Inspected all 8 hits; no passage reports adverse effect incidence.",
        review_status="reconciled",
    )
    assert not validate_reference_unit_record(
        rec_gap, mode="final_candidate", packet_index=synthetic_index
    )

    # 2. Valid: unit_type='limitation' is also permitted with packet_bounded_absence
    rec_lim = rec_gap.model_copy(update={"unit_type": "limitation"})
    assert not validate_reference_unit_record(
        rec_lim, mode="final_candidate", packet_index=synthetic_index
    )

    # 3. Invalid: unit_type='content' is NOT permitted with packet_bounded_absence
    rec_bad_type = rec_gap.model_copy(update={"unit_type": "content"})
    errs = validate_reference_unit_record(
        rec_bad_type, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("permitted only when unit_type is 'evidence_gap' or 'limitation'" in e for e in errs)

    # 4. Invalid: missing 1 of the 8 required scope_audit anchors
    rec_missing_audit = rec_gap.model_copy(update={"evidence_anchors": all_audit_anchors[:7]})
    errs_missing = validate_reference_unit_record(
        rec_missing_audit, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("scope_audit coverage of all 8 evidence IDs" in e for e in errs_missing)


# ==============================================================================
# 10. Anchor Mismatch and Coordinate Bounds Tests (Task 8 & 15)
# ==============================================================================

def test_anchor_coordinate_and_hash_mismatches(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    assert tcm_pkt is not None
    ev_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    assert ev_item is not None

    # Coordinate out of bounds
    text_len = ev_item.text_length
    anchor_out_of_bounds = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=text_len + 10)],
    )
    errs = validate_evidence_anchor(anchor_out_of_bounds, packet_index=synthetic_index)
    assert any("exceeds text length" in e for e in errs)

    # Packet hash mismatch
    anchor_bad_pkt_hash = anchor_out_of_bounds.model_copy(
        update={
            "spans": [EvidenceSpan(start=0, end=5)],
            "packet_canonical_sha256": "0" * 64,
        }
    )
    errs_pkt = validate_evidence_anchor(anchor_bad_pkt_hash, packet_index=synthetic_index)
    assert any("Packet hash mismatch" in e for e in errs_pkt)

    # Chunk text hash mismatch
    anchor_bad_txt_hash = anchor_bad_pkt_hash.model_copy(
        update={
            "packet_canonical_sha256": tcm_pkt.packet_canonical_sha256,
            "chunk_text_sha256": "1" * 64,
        }
    )
    errs_txt = validate_evidence_anchor(anchor_bad_txt_hash, packet_index=synthetic_index)
    assert any("Chunk text hash mismatch" in e for e in errs_txt)

    # Unknown evidence ID
    anchor_bad_ev_id = anchor_bad_pkt_hash.model_copy(
        update={
            "packet_canonical_sha256": tcm_pkt.packet_canonical_sha256,
            "evidence_id": "ev:tcm:syn_q_01:nonexistent",
        }
    )
    errs_ev = validate_evidence_anchor(anchor_bad_ev_id, packet_index=synthetic_index)
    assert any("not found in packet" in e for e in errs_ev)

    # Perspective mismatch
    anchor_bad_persp = anchor_bad_pkt_hash.model_copy(
        update={
            "packet_canonical_sha256": tcm_pkt.packet_canonical_sha256,
            "perspective": "western",  # packet is tcm
        }
    )
    errs_persp = validate_evidence_anchor(anchor_bad_persp, packet_index=synthetic_index)
    assert any("Perspective mismatch" in e for e in errs_persp)


# ==============================================================================
# 11. Final Reference ID Format and Question Matching Tests (Task 5)
# ==============================================================================

def test_final_id_question_matching(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    ev_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    assert tcm_pkt and ev_item

    anchor = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=10)],
    )

    # Mismatched question_id: record is syn_q_01, ID says syn_q_02
    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_02:001",
        unit_text="Synthetic unit text.",
        unit_type="content",
        perspective_scope="tcm",
        evidence_anchors=[anchor],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="Synthetic rationale.",
        review_status="reconciled",
    )
    errs = validate_reference_unit_record(
        rec, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("Mismatched question_id in reference_unit_id" in e for e in errs)


# ==============================================================================
# 12. Multiple Spans per Anchor Test
# ==============================================================================

def test_multiple_spans_per_anchor(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    ev_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    assert tcm_pkt and ev_item

    anchor = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[
            EvidenceSpan(start=0, end=5),
            EvidenceSpan(start=10, end=20),
        ],
    )
    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:001",
        unit_text="Synthetic multi-span target.",
        unit_type="content",
        perspective_scope="tcm",
        evidence_anchors=[anchor],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="Synthetic multi-span rationale.",
        review_status="reconciled",
    )
    assert not validate_reference_unit_record(
        rec, mode="final_candidate", packet_index=synthetic_index
    )


# ==============================================================================
# 13. Source Explicit Requires Supporting Span (Task 12)
# ==============================================================================

def test_source_explicit_requires_supporting_span(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    ev_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    assert tcm_pkt and ev_item

    # Anchor with only contrasting_span in source_explicit record
    anchor_contrast = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="contrasting_span",
        spans=[EvidenceSpan(start=0, end=10)],
    )
    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:001",
        unit_text="Synthetic unit text.",
        unit_type="content",
        perspective_scope="tcm",
        evidence_anchors=[anchor_contrast],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="Synthetic rationale.",
        review_status="reconciled",
    )
    errs = validate_reference_unit_record(
        rec, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("requires at least one anchor with anchor_role='supporting_span'" in e for e in errs)


# ==============================================================================
# 14. Blank Templates Rejection by Final Candidate Validator (Task 6)
# ==============================================================================

def test_blank_templates_fail_final_candidate_validation():
    templates_dir = (
        _ROOT
        / "research"
        / "experiments"
        / "cross_perspective_advisory_ablation_v1"
        / "reference_units"
        / "templates"
    )

    rec_tmpl_file = templates_dir / "reference_unit_record.template.json"
    assert rec_tmpl_file.is_file()
    rec_data = json.loads(rec_tmpl_file.read_text(encoding="utf-8"))
    # Template has $comment, so strip it before model validation
    clean_data = {k: v for k, v in rec_data.items() if not k.startswith("$")}
    # Validate against final candidate mode
    errs = validate_reference_unit_record(clean_data, mode="final_candidate")
    assert len(errs) > 0, "Blank template must NOT pass final candidate validation!"
    assert any("review_status='reconciled'" in e for e in errs)
    assert any("reference_unit_id" in e for e in errs)

    # Check Reviewer A and B templates
    for name in ("reviewer_A_submission.template.jsonl", "reviewer_B_submission.template.jsonl"):
        tmpl_file = templates_dir / name
        assert tmpl_file.is_file()
        line = tmpl_file.read_text(encoding="utf-8").strip()
        data = json.loads(line)
        clean_row = {k: v for k, v in data.items() if not k.startswith("$")}
        row_errs = validate_reference_unit_record(clean_row, mode="final_candidate")
        assert len(row_errs) > 0, f"Template {name} must NOT pass final candidate validation!"


# ==============================================================================
# 15. Real Frozen Packet Read-Only Smoke Test (Task 16)
# ==============================================================================

def test_real_frozen_packet_anchor_index_smoke():
    """Read-only smoke test loading the actual local frozen packet JSONL files.

    Verifies that the mechanical anchor index parses and indexes all 96 real packets
    and 384 evidence items without modifying files, generating units, selecting spans,
    or outputting medical prose.
    """
    packets_dir = (
        _ROOT
        / "research"
        / "experiments"
        / "cross_perspective_advisory_ablation_v1"
        / "packets"
    )
    tcm_file = packets_dir / "tcm_packets.jsonl"
    western_file = packets_dir / "western_packets.jsonl"

    assert tcm_file.is_file(), "Real TCM packet JSONL missing"
    assert western_file.is_file(), "Real Western packet JSONL missing"

    index = FrozenPacketAnchorIndex.from_packet_files(tcm_file, western_file)

    # 48 TCM + 48 Western = 96 total packets
    assert index.packet_count == 96
    # 192 TCM + 192 Western = 384 total evidence items
    assert index.evidence_item_count == 384
    # 48 distinct questions
    assert len(index.questions) == 48

    for qid in index.questions:
        q_packets = index.get_question_packet_ids(qid)
        assert "tcm" in q_packets, f"Question {qid} missing TCM packet"
        assert "western" in q_packets, f"Question {qid} missing Western packet"

        q_ev_ids = index.get_question_evidence_ids(qid)
        assert len(q_ev_ids) == 8, f"Question {qid} expected 8 evidence items, got {len(q_ev_ids)}"

        for ev_id in q_ev_ids:
            # Check both packets to locate item
            tcm_pid = q_packets["tcm"]
            west_pid = q_packets["western"]
            item = index.get_evidence(tcm_pid, ev_id) or index.get_evidence(west_pid, ev_id)
            assert item is not None
            assert len(item.chunk_text_sha256) == 64
            assert item.text_length > 0


# ==============================================================================
# 16. Unicode Code Point Offset Boundary Test (Task 3 & 7)
# ==============================================================================

def test_unicode_code_point_offsets():
    """Verify that span offsets are measured in Unicode code points, not bytes or code units."""
    # "Hello 世界 🌍" -> 10 Unicode code points, but 17 UTF-8 bytes
    unicode_text = "Hello 世界 🌍"
    code_point_len = len(unicode_text)
    assert code_point_len == 10
    utf8_byte_len = len(unicode_text.encode("utf-8"))
    assert utf8_byte_len == 17

    tcm_records = [{
        "packet_id": "packet:tcm:syn_unicode_01",
        "question_id": "syn_unicode_01",
        "perspective": "tcm",
        "packet_canonical_sha256": "0" * 64,
        "evidence_items": [{
            "evidence_id": "ev:tcm:syn_unicode_01:h1",
            "rank": 1,
            "chunk_text_sha256": _make_sha256(unicode_text),
            "exact_chunk_text": unicode_text,
        }],
    }]
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_records, [])

    # Span [0, 10] matches exact code point length: VALID
    anchor_valid = EvidenceAnchor(
        packet_id="packet:tcm:syn_unicode_01",
        packet_canonical_sha256="0" * 64,
        perspective="tcm",
        evidence_id="ev:tcm:syn_unicode_01:h1",
        chunk_text_sha256=_make_sha256(unicode_text),
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=10)],
    )
    assert not validate_evidence_anchor(anchor_valid, packet_index=index)

    # Span [0, 11] exceeds code point length (even though 11 < 17 byte length): OUT OF BOUNDS
    anchor_invalid = anchor_valid.model_copy(
        update={"spans": [EvidenceSpan(start=0, end=11)]}
    )
    errs = validate_evidence_anchor(anchor_invalid, packet_index=index)
    assert any("exceeds text length 10" in e for e in errs)


# ==============================================================================
# 17. Unknown Question ID and Cross Span Synthesis Checks (Task 9 & 12)
# ==============================================================================

def test_unknown_question_id_and_cross_span_synthesis(synthetic_index: FrozenPacketAnchorIndex):
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    ev_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    assert tcm_pkt and ev_item

    anchor = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=ev_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=5)],
    )

    # Unknown question_id
    rec_unknown_q = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="unknown_question_id_999",
        reference_unit_id="cpaa1:ru:unknown_question_id_999:001",
        unit_text="Synthetic text.",
        unit_type="content",
        perspective_scope="tcm",
        evidence_anchors=[anchor],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="Synthetic rationale.",
        review_status="reconciled",
    )
    errs_q = validate_reference_unit_record(
        rec_unknown_q, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("not present in study question set" in e for e in errs_q)

    # cross_span_synthesis with empty support_rationale
    rec_cross = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:001",
        unit_text="Synthetic text.",
        unit_type="content",
        perspective_scope="tcm",
        evidence_anchors=[anchor],
        support_scope="cross_span_synthesis",
        required_qualifiers=[],
        support_rationale="   ",  # empty
        review_status="reconciled",
    )
    errs_cross = validate_reference_unit_record(
        rec_cross, mode="final_candidate", packet_index=synthetic_index
    )
    assert any("requires a non-empty support_rationale" in e for e in errs_cross)


# ==============================================================================
# 18. Formal Packet Authority and Verification (Task 5 Tests A, B, C, D)
# ==============================================================================

def test_formal_authority_rejects_altered_packet_bytes(tmp_path: Path):
    """Test A: Formal authority rejects altered packet bytes even if embedded stored hash fields are unchanged."""
    # Use synthetic path-double files for destructive testing without touching real packets
    tcm_double = tmp_path / "tampered_tcm_packets.jsonl"
    western_double = tmp_path / "western_packets.jsonl"

    # Write synthetic content
    tcm_double.write_bytes(b'{"tampered": "bytes"}\n')
    western_double.write_bytes(b'{"western": "bytes"}\n')

    # Calling formal verified loader must reject altered bytes fail-closed
    with pytest.raises(FormalPacketAuthorityError, match="TCM packet file byte SHA256 mismatch"):
        FrozenPacketAnchorIndex.from_verified_formal_packets(tcm_double, western_double)


def test_formal_authority_exploit_rejection_internal_consistency_insufficient(tmp_path: Path):
    """TASK 4 Exploit Regression: Internal consistency is not sufficient for formal authority.

    Proves that even when an attacker creates a completely internally-consistent packet file
    (where chunk hashes, packet canonical self-hashes, and line formats all match perfectly)
    and attempts to supply the altered file SHA or load it via the formal loader:
    1. The formal loader API exposes NO parameter allowing the caller to supply/override expected hashes.
    2. The formal loader rejects the altered files because their byte hashes do not equal
       the fixed frozen anchors (FROZEN_TCM_PACKET_BYTE_SHA256 / FROZEN_WESTERN_PACKET_BYTE_SHA256).
    """
    import inspect
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
        packet_canonical_sha256,
    )

    # 1. Verify that formal loader signature exposes ZERO override parameters
    sig = inspect.signature(FrozenPacketAnchorIndex.from_verified_formal_packets)
    assert list(sig.parameters.keys()) == ["tcm_packet_file", "western_packet_file"]

    # 2. Build internally-consistent altered packet files
    tcm_records, western_records = _make_synthetic_packet_records()
    for pkt in tcm_records + western_records:
        for it in pkt["evidence_items"]:
            it["chunk_text_sha256"] = _make_sha256(it["exact_chunk_text"])
        pkt["packet_canonical_sha256"] = packet_canonical_sha256(pkt)

    tcm_path_double = tmp_path / "altered_tcm_packets.jsonl"
    western_path_double = tmp_path / "altered_western_packets.jsonl"

    tcm_path_double.write_text(
        "\n".join(json.dumps(r) for r in tcm_records) + "\n", encoding="utf-8"
    )
    western_path_double.write_text(
        "\n".join(json.dumps(r) for r in western_records) + "\n", encoding="utf-8"
    )

    altered_tcm_byte_sha = hashlib.sha256(tcm_path_double.read_bytes()).hexdigest()

    # Verify files are internally consistent (generic record integrity check passes)
    verify_packet_records_integrity(tcm_records, western_records)

    # 3. Attempting to pass expected hashes to the formal loader fails at Python call level
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        FrozenPacketAnchorIndex.from_verified_formal_packets(
            tcm_path_double,
            western_path_double,
            expected_tcm_byte_sha256=altered_tcm_byte_sha,  # type: ignore[call-arg]
        )

    # 4. Attempting to use the formal loader rejects altered files fail-closed
    with pytest.raises(FormalPacketAuthorityError, match="TCM packet file byte SHA256 mismatch"):
        FrozenPacketAnchorIndex.from_verified_formal_packets(tcm_path_double, western_path_double)

    # Also confirm Western mismatch if TCM were real
    packets_dir = _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    real_tcm = packets_dir / "tcm_packets.jsonl"
    with pytest.raises(FormalPacketAuthorityError, match="Western packet file byte SHA256 mismatch"):
        FrozenPacketAnchorIndex.from_verified_formal_packets(real_tcm, western_path_double)


def test_formal_verified_loader_accepts_real_frozen_packets():
    """Test B: Formal verified loader accepts the real frozen packet files."""
    packets_dir = _ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    tcm_file = packets_dir / "tcm_packets.jsonl"
    western_file = packets_dir / "western_packets.jsonl"

    index = FrozenPacketAnchorIndex.from_verified_formal_packets(tcm_file, western_file)
    assert index.packet_count == 96
    assert index.evidence_item_count == 384
    assert len(index.questions) == 48

    # Also test from_repo_root routes to verified formal loader
    repo_index = FrozenPacketAnchorIndex.from_repo_root(_ROOT)
    assert repo_index.packet_count == 96


def test_packet_canonical_hash_mismatch_rejected():
    """Test C: Packet canonical hash mismatch is rejected."""
    tcm_records, western_records = _make_synthetic_packet_records()
    # Corrupt packet_canonical_sha256 on a record
    tcm_records[0]["packet_canonical_sha256"] = "0" * 64

    with pytest.raises(FormalPacketAuthorityError, match="Packet canonical self-hash mismatch"):
        verify_packet_records_integrity(tcm_records, western_records)


def test_exact_chunk_text_chunk_hash_mismatch_rejected():
    """Test D: exact_chunk_text / chunk_text_sha256 mismatch is rejected."""
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
        packet_canonical_sha256,
    )

    tcm_records, western_records = _make_synthetic_packet_records()
    # Tamper exact_chunk_text without updating chunk_text_sha256
    tcm_records[0]["evidence_items"][0]["exact_chunk_text"] = "Tampered text that no longer matches hash"
    # Update packet self-hash so step 5 passes and step 6 (chunk text check) is specifically tested
    tcm_records[0]["packet_canonical_sha256"] = packet_canonical_sha256(tcm_records[0])

    with pytest.raises(FormalPacketAuthorityError, match="Chunk text SHA256 mismatch"):
        verify_packet_records_integrity(tcm_records, western_records)


# ==============================================================================
# 19. Relationship Dual-Stream Pertinent Anchor Requirement (Task 5 Tests E, F, G)
# ==============================================================================

def test_relationship_tcm_only_pertinent_anchor_fails(synthetic_index: FrozenPacketAnchorIndex):
    """Test E: relationship + TCM-only pertinent anchor fails."""
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    tcm_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    assert tcm_pkt and tcm_item

    tcm_anchor = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=tcm_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=5)],
    )

    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:001",
        unit_text="Synthetic relational proposition across streams.",
        unit_type="relationship",
        perspective_scope="both",
        evidence_anchors=[tcm_anchor],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="Synthetic rationale for relationship.",
        review_status="reconciled",
    )

    errs = validate_reference_unit_record(rec, mode="final_candidate", packet_index=synthetic_index)
    assert any("unit_type='relationship' requires at least one pertinent supporting/contrasting anchor from Western" in e for e in errs)


def test_relationship_western_only_pertinent_anchor_fails(synthetic_index: FrozenPacketAnchorIndex):
    """Test F: relationship + Western-only pertinent anchor fails."""
    west_pkt = synthetic_index.get_packet("packet:western:syn_q_01")
    west_item = synthetic_index.get_evidence("packet:western:syn_q_01", "ev:western:syn_q_01:h1")
    assert west_pkt and west_item

    west_anchor = EvidenceAnchor(
        packet_id="packet:western:syn_q_01",
        packet_canonical_sha256=west_pkt.packet_canonical_sha256,
        perspective="western",
        evidence_id="ev:western:syn_q_01:h1",
        chunk_text_sha256=west_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=5)],
    )

    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:001",
        unit_text="Synthetic relational proposition across streams.",
        unit_type="relationship",
        perspective_scope="both",
        evidence_anchors=[west_anchor],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="Synthetic rationale for relationship.",
        review_status="reconciled",
    )

    errs = validate_reference_unit_record(rec, mode="final_candidate", packet_index=synthetic_index)
    assert any("unit_type='relationship' requires at least one pertinent supporting/contrasting anchor from TCM" in e for e in errs)


def test_relationship_with_dual_stream_pertinent_anchors_passes(synthetic_index: FrozenPacketAnchorIndex):
    """Test G: relationship with pertinent anchors from both streams passes when all other rules satisfied."""
    tcm_pkt = synthetic_index.get_packet("packet:tcm:syn_q_01")
    tcm_item = synthetic_index.get_evidence("packet:tcm:syn_q_01", "ev:tcm:syn_q_01:h1")
    west_pkt = synthetic_index.get_packet("packet:western:syn_q_01")
    west_item = synthetic_index.get_evidence("packet:western:syn_q_01", "ev:western:syn_q_01:h1")
    assert tcm_pkt and tcm_item and west_pkt and west_item

    tcm_anchor = EvidenceAnchor(
        packet_id="packet:tcm:syn_q_01",
        packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
        perspective="tcm",
        evidence_id="ev:tcm:syn_q_01:h1",
        chunk_text_sha256=tcm_item.chunk_text_sha256,
        anchor_role="supporting_span",
        spans=[EvidenceSpan(start=0, end=5)],
    )
    west_anchor = EvidenceAnchor(
        packet_id="packet:western:syn_q_01",
        packet_canonical_sha256=west_pkt.packet_canonical_sha256,
        perspective="western",
        evidence_id="ev:western:syn_q_01:h1",
        chunk_text_sha256=west_item.chunk_text_sha256,
        anchor_role="contrasting_span",
        spans=[EvidenceSpan(start=0, end=5)],
    )

    rec = ReferenceUnitRecord(
        schema_version="cpaa1_reference_unit_v1",
        study_id="cross-perspective-advisory-ablation-v1",
        question_id="syn_q_01",
        reference_unit_id="cpaa1:ru:syn_q_01:001",
        unit_text="Synthetic relational proposition contrasting TCM and Western findings.",
        unit_type="relationship",
        perspective_scope="both",
        evidence_anchors=[tcm_anchor, west_anchor],
        support_scope="source_explicit",
        required_qualifiers=[],
        support_rationale="Valid synthetic comparison rationale.",
        review_status="reconciled",
    )

    errs = validate_reference_unit_record(rec, mode="final_candidate", packet_index=synthetic_index)
    assert errs == []


# ==============================================================================
# 20. Validation Mode Fail-Closed Dispatch (Task 5 Tests H, I)
# ==============================================================================

def test_validation_mode_invalid_mode_fails():
    """Test H: mode='invalid_mode' fails immediately."""
    rec_dict = {"dummy": "record"}
    with pytest.raises(ValueError, match="Unsupported validation mode: 'invalid_mode'"):
        validate_reference_unit_record(rec_dict, mode="invalid_mode")  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_mode", ["final", "production", "", None, "draft_candidate", "reconciled"])
def test_validation_mode_other_unsupported_modes_fail_closed(bad_mode: Any):
    """Test I: any other unsupported mode fails closed immediately."""
    rec_dict = {"dummy": "record"}
    with pytest.raises(ValueError, match="Unsupported validation mode"):
        validate_reference_unit_record(rec_dict, mode=bad_mode)  # type: ignore[arg-type]
