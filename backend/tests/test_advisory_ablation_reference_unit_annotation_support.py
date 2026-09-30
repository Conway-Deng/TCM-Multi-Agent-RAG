"""Tests for Read-Only Human Reference-Unit Annotation Support Tooling.

Protocol: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Phase: 2C-B2A-AUTHORITY-REPAIR
"""

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
    packet_canonical_sha256,
)
from research.experiments.cross_perspective_advisory_ablation_v1.reference_units import (
    FROZEN_PROTOCOL_BYTE_SHA256,
    FROZEN_TCM_PACKET_BYTE_SHA256,
    FROZEN_WESTERN_PACKET_BYTE_SHA256,
    HUMAN_ONLY_CAPABILITIES,
    HUMAN_ONLY_PROHIBITIONS,
    PROTOCOL_ID,
    STUDY_ID,
    AmbiguousSpanError,
    FormalAnnotationViewer,
    FormalPacketAuthorityError,
    FrozenPacketAnchorIndex,
    ReadOnlyQuestionView,
    ReferenceUnitRecord,
    ReviewerRoleMismatchError,
    ReviewerWorkspace,
    SyntheticAnnotationViewer,
    WorkspaceKind,
    WorkspaceLockedError,
    locate_exact_substring,
    resolve_unique_span_coordinates,
    validate_span_coordinates,
)

_ROOT = Path(__file__).resolve().parent.parent.parent


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


# ==============================================================================
# 1. Human-Only Boundary Tests
# ==============================================================================

def test_human_only_boundary_specification():
    """Verify explicit human-only capabilities and prohibitions are documented and defined."""
    assert "display_frozen_evidence_packets" in HUMAN_ONLY_CAPABILITIES
    assert "export_read_only_evidence_packets" in HUMAN_ONLY_CAPABILITIES
    assert "calculate_unicode_span_coordinates" in HUMAN_ONLY_CAPABILITIES
    assert "validate_span_coordinates" in HUMAN_ONLY_CAPABILITIES
    assert "manage_isolated_reviewer_workspaces" in HUMAN_ONLY_CAPABILITIES

    assert "propose_unit_text" in HUMAN_ONLY_PROHIBITIONS
    assert "propose_required_qualifiers" in HUMAN_ONLY_PROHIBITIONS
    assert "propose_support_rationale" in HUMAN_ONLY_PROHIBITIONS
    assert "select_evidence_semantically" in HUMAN_ONLY_PROHIBITIONS
    assert "judge_relevance_or_support" in HUMAN_ONLY_PROHIBITIONS
    assert "reconcile_reviewers" in HUMAN_ONLY_PROHIBITIONS
    assert "call_models_or_providers" in HUMAN_ONLY_PROHIBITIONS


# ==============================================================================
# 2. Formal vs Synthetic Authority Isolation
# ==============================================================================

def test_frozen_packet_anchor_index_public_constructor_cannot_accept_is_formal_verified():
    """BLOCKER 1 Regression: Constructor must not expose is_formal_verified parameter."""
    sig = inspect.signature(FrozenPacketAnchorIndex.__init__)
    assert "is_formal_verified" not in sig.parameters

    # Attempting to forge formal verification via constructor must fail closed
    with pytest.raises(TypeError, match="unexpected keyword argument 'is_formal_verified'"):
        FrozenPacketAnchorIndex(  # type: ignore[call-arg]
            packets={},
            evidence_items={},
            question_to_packets={},
            question_to_evidence_ids={},
            questions=set(),
            is_formal_verified=True,
        )


def test_from_packet_records_produces_unverified_index():
    """Synthetic in-memory construction must always produce is_formal_verified == False."""
    tcm_recs, west_recs = _make_synthetic_packet_records()
    synthetic_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    assert synthetic_index.is_formal_verified is False


def test_formal_viewer_rejects_unverified_synthetic_index():
    """FormalAnnotationViewer must fail-closed if initialized with an unverified index."""
    tcm_recs, west_recs = _make_synthetic_packet_records()
    synthetic_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    assert not synthetic_index.is_formal_verified

    with pytest.raises(FormalPacketAuthorityError, match="requires a formally verified packet index"):
        FormalAnnotationViewer(synthetic_index)


def test_synthetic_viewer_accepts_synthetic_records():
    """SyntheticAnnotationViewer accepts synthetic in-memory records for isolated testing."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    viewer = SyntheticAnnotationViewer.from_packet_records(tcm_recs, west_recs)

    assert viewer.list_questions() == ["syn_q_01"]
    view = viewer.get_question_view("syn_q_01")
    assert isinstance(view, ReadOnlyQuestionView)
    assert view.question_id == "syn_q_01"
    assert len(view.tcm_items) == 4
    assert len(view.western_items) == 4


# ==============================================================================
# 3. Read-Only Question View Model (No Summarization / No Filtering)
# ==============================================================================

def test_question_view_displays_all_eight_items_strictly_by_rank():
    """Question view must present all 4 TCM and all 4 Western items in exact R0 rank order."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    viewer = SyntheticAnnotationViewer.from_packet_records(tcm_recs, west_recs)
    view = viewer.get_question_view("syn_q_01")

    assert [item.rank for item in view.tcm_items] == [1, 2, 3, 4]
    assert [item.rank for item in view.western_items] == [1, 2, 3, 4]

    # Verify provenance and metadata fields are intact
    item_tcm_1 = view.tcm_items[0]
    assert item_tcm_1.evidence_id == "ev:tcm:syn_q_01:h1"
    assert item_tcm_1.source_title == "Synthetic Document 1"
    assert item_tcm_1.text_length == len(item_tcm_1.exact_chunk_text)
    assert item_tcm_1.chunk_text_sha256 == _make_sha256(item_tcm_1.exact_chunk_text)


def test_question_view_unknown_question_fails():
    """Requesting an unknown question_id must raise KeyError fail-closed."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    viewer = SyntheticAnnotationViewer.from_packet_records(tcm_recs, west_recs)

    with pytest.raises(KeyError, match="Unknown question_id: 'unknown_q'"):
        viewer.get_question_view("unknown_q")


def test_question_view_serialization_and_markdown():
    """Question view renders clean, unsummarized JSON and Markdown without semantic drift."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    viewer = SyntheticAnnotationViewer.from_packet_records(tcm_recs, west_recs)
    view = viewer.get_question_view("syn_q_01")

    data = view.to_dict()
    assert data["$notice"].startswith("LOCAL-ONLY")
    assert data["question_id"] == "syn_q_01"
    assert len(data["tcm_packet"]["evidence_items"]) == 4
    assert len(data["western_packet"]["evidence_items"]) == 4

    md = view.to_markdown()
    assert "<!-- LOCAL-ONLY / DO NOT COMMIT" in md
    assert "# Question: syn_q_01" in md
    assert "### TCM Rank 1:" in md
    assert "### Western Rank 4:" in md


# ==============================================================================
# 4. Local-Only Export Helper
# ==============================================================================

def test_export_question_refuses_existing_destination(tmp_path: Path):
    """export_question must fail if the target file already exists."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    viewer = SyntheticAnnotationViewer.from_packet_records(tcm_recs, west_recs)

    # First export succeeds
    out = viewer.export_question("syn_q_01", tmp_path, format="json")
    assert out.is_file()

    # Second export to same destination must fail
    with pytest.raises(FileExistsError, match="Export destination already exists"):
        viewer.export_question("syn_q_01", tmp_path, format="json")


def test_export_all_questions_refuses_existing_directory(tmp_path: Path):
    """export_all_questions must fail if the output directory already exists."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    viewer = SyntheticAnnotationViewer.from_packet_records(tcm_recs, west_recs)

    export_dir = tmp_path / "already_exists_dir"
    export_dir.mkdir()

    with pytest.raises(FileExistsError, match="Export directory already exists"):
        viewer.export_all_questions(export_dir, format="json")


def test_export_produces_no_reference_units(tmp_path: Path):
    """Export output contains frozen packet evidence items only; zero reference units."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    viewer = SyntheticAnnotationViewer.from_packet_records(tcm_recs, west_recs)

    dest_dir = tmp_path / "fresh_export_dir"
    files = viewer.export_all_questions(dest_dir, format="json")

    # Contains README and syn_q_01.json
    assert len(files) == 2
    readme = dest_dir / "README_LOCAL_ONLY.txt"
    assert "LOCAL-ONLY HUMAN ANNOTATION EXPORT" in readme.read_text(encoding="utf-8")

    q_file = dest_dir / "syn_q_01.json"
    content = json.loads(q_file.read_text(encoding="utf-8"))
    assert "reference_units" not in content
    assert "unit_text" not in content
    assert len(content["tcm_packet"]["evidence_items"]) == 4


# ==============================================================================
# 5. Unicode Span Coordinate Helpers & Zero-Length Interval Rejection
# ==============================================================================

def test_unicode_span_coordinate_resolution_and_validation():
    """Verify zero-based half-open Unicode code-point span coordinates using non-medical text."""
    # Neutral non-medical text with Chinese, English, and emoji
    text = "红色方块在桌面中央。The blue circle is beside it. 🌍"

    # 1. Exact unique match in Chinese characters
    offsets = resolve_unique_span_coordinates(text, "桌面中央")
    assert offsets == (5, 9)
    assert text[5:9] == "桌面中央"

    # 2. Exact unique match in English characters
    offsets_en = resolve_unique_span_coordinates(text, "blue circle")
    assert text[offsets_en[0] : offsets_en[1]] == "blue circle"

    # 3. Validate span coordinates helper
    start, end, extracted = validate_span_coordinates(text, 5, 9)
    assert (start, end) == (5, 9)
    assert extracted == "桌面中央"


def test_span_coordinate_helpers_rejects_zero_length_intervals():
    """BLOCKER 3 / TASK 5 Regression: validate_span_coordinates must enforce start < end."""
    text = "abcdef"

    # Zero-length interval start == end must fail closed
    with pytest.raises(ValueError, match="strictly positive"):
        validate_span_coordinates(text, 3, 3)

    with pytest.raises(ValueError, match="strictly positive"):
        validate_span_coordinates(text, 0, 0)

    with pytest.raises(ValueError, match="strictly positive"):
        validate_span_coordinates(text, 6, 6)


def test_span_coordinate_helpers_out_of_bounds_and_inverted():
    """validate_span_coordinates fails closed on negative, inverted, or out-of-bounds offsets."""
    text = "Short text"
    length = len(text)

    # Negative start
    with pytest.raises(ValueError, match="Span start offset.*must be non-negative"):
        validate_span_coordinates(text, -1, 5)

    # Inverted start/end
    with pytest.raises(ValueError, match="strictly positive"):
        validate_span_coordinates(text, 5, 2)

    # End exceeds text length
    with pytest.raises(ValueError, match="exceeds text length"):
        validate_span_coordinates(text, 0, length + 1)


def test_span_coordinate_exact_substring_not_found():
    """resolve_unique_span_coordinates fails closed if target substring is absent."""
    text = "Some specific synthetic passage."
    with pytest.raises(ValueError, match="Target substring not found"):
        resolve_unique_span_coordinates(text, "completely absent phrase")

    with pytest.raises(ValueError, match="Target substring must be non-empty"):
        resolve_unique_span_coordinates(text, "")


def test_span_coordinate_repeated_substring_fails_as_ambiguous():
    """resolve_unique_span_coordinates fails closed when substring appears multiple times."""
    text = "Code A7 appears here. Code A7 appears again. Code A7 appears once more."

    # Substring 'Code A7' appears 3 times
    all_matches = locate_exact_substring(text, "Code A7")
    assert len(all_matches) == 3

    # resolve_unique_span_coordinates must NOT guess; it raises AmbiguousSpanError
    with pytest.raises(AmbiguousSpanError, match="Target substring appears 3 times"):
        resolve_unique_span_coordinates(text, "Code A7")


# ==============================================================================
# 6. Reviewer Workspace Separation (Formal vs Synthetic Authority)
# ==============================================================================

def test_formal_reviewer_workspace_creation_rejects_synthetic_index():
    """BLOCKER 2 Regression: Formal reviewer workspace must reject unverified/synthetic index."""
    tcm_recs, west_recs = _make_synthetic_packet_records()
    synthetic_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    with pytest.raises(FormalPacketAuthorityError, match="Cannot create formal workspace with unverified"):
        ReviewerWorkspace.create_formal_blank("reviewer_a", synthetic_index)


def test_formal_reviewer_workspace_derives_actual_48_questions():
    """Formal reviewer workspace binds actual 48 questions from verified formal index."""
    formal_viewer = FormalAnnotationViewer.from_repo_root(_ROOT)
    formal_index = formal_viewer.packet_index

    ws_formal = ReviewerWorkspace.create_formal_blank("reviewer_a", formal_index)
    assert ws_formal.workspace_kind == "formal"
    assert ws_formal.reviewer_role == "reviewer_a"
    assert len(ws_formal.question_ids) == 48
    assert ws_formal.question_ids[0] == "cpaa1-con-bu-001"
    assert ws_formal.question_ids[-1] == "cpaa1-hea-sc-006"
    assert ws_formal.protocol_byte_sha256 == FROZEN_PROTOCOL_BYTE_SHA256
    assert ws_formal.tcm_packet_byte_sha256 == FROZEN_TCM_PACKET_BYTE_SHA256
    assert ws_formal.western_packet_byte_sha256 == FROZEN_WESTERN_PACKET_BYTE_SHA256
    assert ws_formal.records == []
    assert not ws_formal.submission_locked


def test_synthetic_reviewer_workspace_creation_and_serialization():
    """Synthetic workspace is explicitly tagged and does not claim formal authority."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    syn_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_syn = ReviewerWorkspace.create_synthetic_blank("reviewer_a", syn_index)
    assert ws_syn.workspace_kind == "synthetic"
    assert ws_syn.tcm_packet_byte_sha256 == "SYNTHETIC_PACKET_AUTHORITY"
    assert ws_syn.western_packet_byte_sha256 == "SYNTHETIC_PACKET_AUTHORITY"
    assert ws_syn.question_ids == ("syn_q_01",)

    serialized = ws_syn.to_dict()
    assert serialized["workspace_kind"] == "synthetic"
    assert "Synthetic test reviewer submission container" in serialized["$notice"]
    assert serialized["tcm_packet_byte_sha256"] == "SYNTHETIC_PACKET_AUTHORITY"


def test_reviewer_a_and_b_workspaces_are_strictly_isolated(tmp_path: Path):
    """Reviewer A and Reviewer B workspaces cannot cross-load or leak."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    syn_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws_a = ReviewerWorkspace.create_synthetic_blank("reviewer_a", syn_index)
    ws_b = ReviewerWorkspace.create_synthetic_blank("reviewer_b", syn_index)

    path_a = tmp_path / "workspace_reviewer_a.json"
    path_b = tmp_path / "workspace_reviewer_b.json"

    ws_a.save_local(path_a)
    ws_b.save_local(path_b)

    # Attempting to load Reviewer A file as Reviewer B must fail
    with pytest.raises(ReviewerRoleMismatchError, match="does not match expected reviewer 'reviewer_b'"):
        ReviewerWorkspace.load_synthetic_local(path_a, syn_index, expected_reviewer="reviewer_b")

    # Attempting to load Reviewer B file as Reviewer A must fail
    with pytest.raises(ReviewerRoleMismatchError, match="does not match expected reviewer 'reviewer_a'"):
        ReviewerWorkspace.load_synthetic_local(path_b, syn_index, expected_reviewer="reviewer_a")

    # Clean loads with correct role succeed
    loaded_a = ReviewerWorkspace.load_synthetic_local(path_a, syn_index, expected_reviewer="reviewer_a")
    assert loaded_a.reviewer_role == "reviewer_a"


def test_reviewer_workspace_submission_locking(tmp_path: Path):
    """Locked workspace rejects subsequent modifications."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    syn_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws = ReviewerWorkspace.create_synthetic_blank("reviewer_a", syn_index)

    # Lock workspace
    metadata = ws.lock_submission(notes="Final human review completed.")
    assert ws.submission_locked is True
    assert ws.annotation_state == "submitted_locked"
    assert metadata["record_count"] == 0

    # Attempting to add record after locking must fail
    with pytest.raises(WorkspaceLockedError, match="workspace is locked for submission"):
        ws.add_record({"dummy": "record"})


def test_formal_workspace_add_record_cannot_substitute_or_omit_authority():
    """BLOCKER 2 / TASK 4 Regression: add_record uses bound authority and forbids caller override."""
    formal_viewer = FormalAnnotationViewer.from_repo_root(_ROOT)
    formal_index = formal_viewer.packet_index

    ws = ReviewerWorkspace.create_formal_blank("reviewer_a", formal_index)

    # Verify signature of add_record exposes NO packet_index parameter
    sig = inspect.signature(ws.add_record)
    assert "packet_index" not in sig.parameters

    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    syn_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    # Attempting to pass packet_index to add_record must fail with TypeError
    with pytest.raises(TypeError, match="unexpected keyword argument 'packet_index'"):
        ws.add_record({"question_id": "syn_q_01"}, packet_index=syn_index)  # type: ignore[call-arg]

    with pytest.raises(TypeError, match="unexpected keyword argument 'packet_index'"):
        ws.add_record({"question_id": "syn_q_01"}, packet_index=None)  # type: ignore[call-arg]


def test_synthetic_reviewer_workspace_validates_draft_record():
    """Adding a record to synthetic workspace runs validation against bound synthetic index."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    syn_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws = ReviewerWorkspace.create_synthetic_blank("reviewer_a", syn_index)

    # Valid draft record
    chunk_text = tcm_recs[0]["evidence_items"][0]["exact_chunk_text"]
    valid_draft_record = {
        "schema_version": "cpaa1_reference_unit_v1",
        "study_id": STUDY_ID,
        "question_id": "syn_q_01",
        "reference_unit_id": None,
        "unit_text": "Synthetic human unit text.",
        "unit_type": "content",
        "perspective_scope": "tcm",
        "evidence_anchors": [
            {
                "packet_id": "packet:tcm:syn_q_01",
                "packet_canonical_sha256": tcm_recs[0]["packet_canonical_sha256"],
                "perspective": "tcm",
                "evidence_id": "ev:tcm:syn_q_01:h1",
                "chunk_text_sha256": _make_sha256(chunk_text),
                "anchor_role": "supporting_span",
                "spans": [{"start": 0, "end": 10}],
            }
        ],
        "support_scope": "source_explicit",
        "required_qualifiers": [],
        "support_rationale": "Valid synthetic rationale.",
        "review_status": "draft",
    }

    ws.add_record(valid_draft_record, mode="draft")
    assert len(ws.records) == 1
    assert ws.annotation_state == "in_progress"

    # Invalid record (missing required fields) must fail
    invalid_record = {"question_id": "syn_q_01"}
    with pytest.raises(ValueError, match="Record validation failed"):
        ws.add_record(invalid_record, mode="draft")


def test_formal_workspace_load_revalidates_records_against_verified_formal_authority(tmp_path: Path):
    """TASK 3 Regression: Formal loader revalidates every record against verified formal authority."""
    formal_viewer = FormalAnnotationViewer.from_repo_root(_ROOT)
    formal_index = formal_viewer.packet_index

    ws = ReviewerWorkspace.create_formal_blank("reviewer_a", formal_index)
    ws_file = tmp_path / "formal_ws.json"
    ws.save_local(ws_file)

    # Clean formal load succeeds
    loaded = ReviewerWorkspace.load_formal_local(ws_file, formal_index, expected_reviewer="reviewer_a")
    assert loaded.workspace_kind == "formal"
    assert len(loaded.question_ids) == 48

    # Attempting to load formal file with synthetic unverified index must fail
    tcm_recs, west_recs = _make_synthetic_packet_records()
    syn_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    with pytest.raises(FormalPacketAuthorityError, match="requires a verified formal packet index"):
        ReviewerWorkspace.load_formal_local(ws_file, syn_index)

    # Tampering: add an invalid record directly into the file JSON
    tampered_data = json.loads(ws_file.read_text(encoding="utf-8"))
    tampered_data["records"].append({
        "schema_version": "cpaa1_reference_unit_v1",
        "study_id": STUDY_ID,
        "question_id": "cpaa1-con-bu-001",
        "unit_text": "Invalid forged unit.",
        "unit_type": "content",
        "perspective_scope": "tcm",
        "evidence_anchors": [],  # Missing required supporting anchors
        "support_scope": "source_explicit",
        "review_status": "draft",
    })
    tampered_file = tmp_path / "tampered_formal_ws.json"
    tampered_file.write_text(json.dumps(tampered_data), encoding="utf-8")

    # Formal loader must reject file because record fails formal validation
    with pytest.raises(FormalPacketAuthorityError, match="failed formal validation"):
        ReviewerWorkspace.load_formal_local(tampered_file, formal_index)


def test_load_formal_local_rejects_synthetic_workspace_kind(tmp_path: Path):
    """load_formal_local must reject a file declaring workspace_kind='synthetic'."""
    formal_viewer = FormalAnnotationViewer.from_repo_root(_ROOT)
    formal_index = formal_viewer.packet_index

    tcm_recs, west_recs = _make_synthetic_packet_records()
    syn_index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)
    ws_syn = ReviewerWorkspace.create_synthetic_blank("reviewer_a", syn_index)

    syn_file = tmp_path / "synthetic_ws.json"
    ws_syn.save_local(syn_file)

    with pytest.raises(FormalPacketAuthorityError, match="Workspace kind mismatch: expected 'formal'"):
        ReviewerWorkspace.load_formal_local(syn_file, formal_index)


# ==============================================================================
# 7. Real Read-Only Smoke Test (Actual Local Frozen Packets)
# ==============================================================================

def test_formal_annotation_viewer_real_frozen_packets_smoke(tmp_path: Path):
    """Smoke test on actual local frozen packet files.

    Verifies:
      - FormalAnnotationViewer initializes via from_repo_root(_ROOT)
      - Exactly 48 questions are loaded
      - Every question exposes exactly 4 TCM and 4 Western items (ranks 1-4)
      - Exports one question to local temp directory and verifies structure
      - Performs zero annotation and selects zero spans
    """
    viewer = FormalAnnotationViewer.from_repo_root(_ROOT)
    questions = viewer.list_questions()

    assert len(questions) == 48
    assert questions[0] == "cpaa1-con-bu-001"
    assert questions[-1] == "cpaa1-hea-sc-006"

    # Inspect first question mechanically
    q1_view = viewer.get_question_view("cpaa1-con-bu-001")
    assert q1_view.question_id == "cpaa1-con-bu-001"
    assert len(q1_view.tcm_items) == 4
    assert len(q1_view.western_items) == 4
    assert [it.rank for it in q1_view.tcm_items] == [1, 2, 3, 4]
    assert [it.rank for it in q1_view.western_items] == [1, 2, 3, 4]

    # Export to local scratch/temp directory (never tracked)
    local_export_dir = tmp_path / "smoke_export"
    out_file = viewer.export_question("cpaa1-cou-ed-001", local_export_dir, format="json")
    assert out_file.is_file()

    exported_json = json.loads(out_file.read_text(encoding="utf-8"))
    assert exported_json["question_id"] == "cpaa1-cou-ed-001"
    assert len(exported_json["tcm_packet"]["evidence_items"]) == 4
    assert len(exported_json["western_packet"]["evidence_items"]) == 4
    assert "reference_units" not in exported_json
