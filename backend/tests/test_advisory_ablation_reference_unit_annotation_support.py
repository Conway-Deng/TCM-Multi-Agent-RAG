"""Tests for Read-Only Human Reference-Unit Annotation Support Tooling.

Protocol: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Phase: 2C-B2A
"""

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
        text = f"Synthetic TCM evidence chunk rank {r} for question {question_id}."
        tcm_items.append(
            {
                "evidence_id": f"ev:tcm:{question_id}:h{r}",
                "rank": r,
                "exact_chunk_text": text,
                "chunk_text_sha256": _make_sha256(text),
                "provenance": f"syn_tcm_doc_{r}.txt",
                "source_title": f"Synthetic TCM Source {r}",
                "source_url": f"https://example.com/syn/tcm/{r}",
                "section_or_category": "Discussion",
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
        text = f"Synthetic Western evidence chunk rank {r} for question {question_id}."
        western_items.append(
            {
                "evidence_id": f"ev:western:{question_id}:h{r}",
                "rank": r,
                "exact_chunk_text": text,
                "chunk_text_sha256": _make_sha256(text),
                "provenance": f"syn_west_doc_{r}.txt",
                "source_title": f"Synthetic Western Source {r}",
                "source_url": f"https://example.com/syn/west/{r}",
                "section_or_category": "Results",
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
    assert item_tcm_1.source_title == "Synthetic TCM Source 1"
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
# 5. Unicode Span Coordinate Helpers
# ==============================================================================

def test_unicode_span_coordinate_resolution_and_validation():
    """Verify zero-based half-open Unicode code-point span coordinates."""
    # Text with multi-byte Chinese characters, English, and emojis
    text = "患者出现恶寒发热症状。Symptoms include fever and chills. 🌡️"

    # 1. Exact unique match in Chinese text
    offsets = resolve_unique_span_coordinates(text, "恶寒发热")
    assert offsets == (4, 8)
    assert text[4:8] == "恶寒发热"

    # 2. Exact unique match in English text
    offsets_en = resolve_unique_span_coordinates(text, "fever and chills")
    assert text[offsets_en[0] : offsets_en[1]] == "fever and chills"

    # 3. Validate span coordinates helper
    start, end, extracted = validate_span_coordinates(text, 4, 8)
    assert (start, end) == (4, 8)
    assert extracted == "恶寒发热"


def test_span_coordinate_helpers_out_of_bounds_and_inverted():
    """validate_span_coordinates fails closed on negative, inverted, or out-of-bounds offsets."""
    text = "Short text"
    length = len(text)

    # Negative start
    with pytest.raises(ValueError, match="Span start offset.*must be non-negative"):
        validate_span_coordinates(text, -1, 5)

    # Inverted start/end
    with pytest.raises(ValueError, match="cannot be less than start"):
        validate_span_coordinates(text, 5, 2)

    # End exceeds text length
    with pytest.raises(ValueError, match="exceeds text length"):
        validate_span_coordinates(text, 0, length + 1)


def test_span_coordinate_exact_substring_not_found():
    """resolve_unique_span_coordinates fails closed if target substring is absent."""
    text = "Some specific medical passage."
    with pytest.raises(ValueError, match="Target substring not found"):
        resolve_unique_span_coordinates(text, "completely absent phrase")

    with pytest.raises(ValueError, match="Target substring must be non-empty"):
        resolve_unique_span_coordinates(text, "")


def test_span_coordinate_repeated_substring_fails_as_ambiguous():
    """resolve_unique_span_coordinates fails closed when substring appears multiple times."""
    text = "First dose at 10mg. Maintenance dose at 10mg. Final dose at 10mg."

    # Substring '10mg' appears 3 times
    all_matches = locate_exact_substring(text, "10mg")
    assert len(all_matches) == 3

    # resolve_unique_span_coordinates must NOT guess; it raises AmbiguousSpanError
    with pytest.raises(AmbiguousSpanError, match="Target substring appears 3 times"):
        resolve_unique_span_coordinates(text, "10mg")


# ==============================================================================
# 6. Reviewer Workspace / Submission Containers
# ==============================================================================

def test_blank_reviewer_workspace_contains_no_semantic_units():
    """Blank workspace initializes with zero records and correct metadata."""
    ws_a = ReviewerWorkspace.create_blank("reviewer_a", ["syn_q_01"])
    assert ws_a.reviewer_role == "reviewer_a"
    assert ws_a.protocol_id == PROTOCOL_ID
    assert ws_a.protocol_byte_sha256 == FROZEN_PROTOCOL_BYTE_SHA256
    assert ws_a.tcm_packet_byte_sha256 == FROZEN_TCM_PACKET_BYTE_SHA256
    assert ws_a.western_packet_byte_sha256 == FROZEN_WESTERN_PACKET_BYTE_SHA256
    assert ws_a.annotation_state == "blank"
    assert ws_a.records == []
    assert not ws_a.submission_locked


def test_reviewer_a_and_b_workspaces_are_strictly_isolated(tmp_path: Path):
    """Reviewer A and Reviewer B workspaces cannot cross-load or leak."""
    ws_a = ReviewerWorkspace.create_blank("reviewer_a", ["syn_q_01"])
    ws_b = ReviewerWorkspace.create_blank("reviewer_b", ["syn_q_01"])

    path_a = tmp_path / "workspace_reviewer_a.json"
    path_b = tmp_path / "workspace_reviewer_b.json"

    ws_a.save_local(path_a)
    ws_b.save_local(path_b)

    # Attempting to load Reviewer A file as Reviewer B must fail
    with pytest.raises(ReviewerRoleMismatchError, match="does not match expected reviewer 'reviewer_b'"):
        ReviewerWorkspace.load_local(path_a, expected_reviewer="reviewer_b")

    # Attempting to load Reviewer B file as Reviewer A must fail
    with pytest.raises(ReviewerRoleMismatchError, match="does not match expected reviewer 'reviewer_a'"):
        ReviewerWorkspace.load_local(path_b, expected_reviewer="reviewer_a")

    # Clean loads with correct role succeed
    loaded_a = ReviewerWorkspace.load_local(path_a, expected_reviewer="reviewer_a")
    assert loaded_a.reviewer_role == "reviewer_a"


def test_reviewer_workspace_submission_locking(tmp_path: Path):
    """Locked workspace rejects subsequent modifications."""
    ws = ReviewerWorkspace.create_blank("reviewer_a", ["syn_q_01"])

    # Lock workspace
    metadata = ws.lock_submission(notes="Final human review completed.")
    assert ws.submission_locked is True
    assert ws.annotation_state == "submitted_locked"
    assert metadata["record_count"] == 0

    # Attempting to add record after locking must fail
    with pytest.raises(WorkspaceLockedError, match="workspace is locked for submission"):
        ws.add_record({"dummy": "record"})


def test_reviewer_workspace_validates_draft_record():
    """Adding a record to workspace runs structural validation."""
    tcm_recs, west_recs = _make_synthetic_packet_records("syn_q_01")
    index = FrozenPacketAnchorIndex.from_packet_records(tcm_recs, west_recs)

    ws = ReviewerWorkspace.create_blank("reviewer_a", ["syn_q_01"])

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

    ws.add_record(valid_draft_record, packet_index=index, mode="draft")
    assert len(ws.records) == 1
    assert ws.annotation_state == "in_progress"

    # Invalid record (missing required fields) must fail
    invalid_record = {"question_id": "syn_q_01"}
    with pytest.raises(ValueError, match="Record validation failed"):
        ws.add_record(invalid_record, packet_index=index, mode="draft")


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
