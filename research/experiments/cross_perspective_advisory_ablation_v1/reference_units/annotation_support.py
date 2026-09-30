"""Human Reference-Unit Annotation Support Tooling.

Protocol: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Study: cross-perspective-advisory-ablation-v1

HUMAN-ONLY BOUNDARY SPECIFICATION:
==================================
These tools provide mechanical assistance exclusively for HUMAN reviewers.
They perform zero semantic automation.

CAN:
  - display frozen evidence packets for one question at a time
  - export frozen evidence packets for offline human inspection
  - calculate and validate zero-based half-open Unicode code-point span coordinates
  - validate candidate reference unit IDs, evidence hashes, span coordinates, and schema syntax
  - store, validate, and serialize human-entered records in separate reviewer workspaces

CANNOT AND MUST NOT:
  - write or propose semantic targets / unit_text
  - suggest or recommend spans
  - recommend inclusion or exclusion of evidence
  - judge evidence support or relevance
  - judge duplication or redundancy
  - judge cross-perspective comparability or conflict
  - split or merge units
  - reconcile or adjudicate between reviewers
  - call any LLM / foundation model / provider API
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Final, Literal, Sequence

from .reference_unit_schema import (
    FROZEN_PROTOCOL_BYTE_SHA256,
    PROTOCOL_ID,
    STUDY_ID,
    ReferenceUnitRecord,
    ValidationMode,
)
from .reference_unit_validation import (
    FROZEN_TCM_PACKET_BYTE_SHA256,
    FROZEN_WESTERN_PACKET_BYTE_SHA256,
    FormalPacketAuthorityError,
    FrozenPacketAnchorIndex,
    validate_reference_unit_record,
)

# Explicit boundary constants
HUMAN_ONLY_CAPABILITIES: Final[tuple[str, ...]] = (
    "display_frozen_evidence_packets",
    "export_read_only_evidence_packets",
    "calculate_unicode_span_coordinates",
    "validate_span_coordinates",
    "validate_reference_unit_record_structure",
    "manage_isolated_reviewer_workspaces",
)

HUMAN_ONLY_PROHIBITIONS: Final[tuple[str, ...]] = (
    "propose_unit_text",
    "propose_required_qualifiers",
    "propose_support_rationale",
    "select_evidence_semantically",
    "judge_relevance_or_support",
    "judge_comparability_or_conflict",
    "judge_unit_split_or_merge",
    "reconcile_reviewers",
    "adjudicate_annotations",
    "call_models_or_providers",
)

ReviewerRole = Literal["reviewer_a", "reviewer_b"]


class AmbiguousSpanError(ValueError):
    """Raised when a target substring appears multiple times in exact chunk text."""


class ReviewerRoleMismatchError(ValueError):
    """Raised when an operation is attempted with an incorrect reviewer role."""


class WorkspaceLockedError(PermissionError):
    """Raised when attempting to modify a locked reviewer workspace."""


@dataclass(frozen=True)
class ReadOnlyEvidenceItemView:
    """Read-only view model for a single frozen evidence item."""

    evidence_id: str
    packet_id: str
    perspective: str
    rank: int
    exact_chunk_text: str
    text_length: int  # Length in Unicode code points
    chunk_text_sha256: str
    packet_canonical_sha256: str
    provenance: str = ""
    source_title: str = ""
    source_url: str = ""
    section_or_category: str = ""
    doi: str = ""
    pmcid: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ReadOnlyQuestionView:
    """Read-only view model for one question's frozen evidence packets.

    Presents all 4 TCM and all 4 Western evidence items strictly in frozen R0 rank order.
    Performs no summarization, filtering, or semantic comparison.
    """

    question_id: str
    question_text: str
    topic: str
    tcm_packet_id: str
    tcm_packet_canonical_sha256: str
    western_packet_id: str
    western_packet_canonical_sha256: str
    tcm_items: tuple[ReadOnlyEvidenceItemView, ...]
    western_items: tuple[ReadOnlyEvidenceItemView, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-serializable representation."""
        return {
            "$notice": "LOCAL-ONLY / DO NOT COMMIT - Read-only packet view for human review",
            "question_id": self.question_id,
            "question_text": self.question_text,
            "topic": self.topic,
            "tcm_packet": {
                "packet_id": self.tcm_packet_id,
                "packet_canonical_sha256": self.tcm_packet_canonical_sha256,
                "evidence_items": [item.to_dict() for item in self.tcm_items],
            },
            "western_packet": {
                "packet_id": self.western_packet_id,
                "packet_canonical_sha256": self.western_packet_canonical_sha256,
                "evidence_items": [item.to_dict() for item in self.western_items],
            },
        }

    def to_markdown(self) -> str:
        """Render a clean, unedited Markdown document for human review."""
        lines: list[str] = [
            "<!-- LOCAL-ONLY / DO NOT COMMIT - Read-only packet view for human review -->",
            f"# Question: {self.question_id}",
            "",
            f"**Question Text:** {self.question_text}",
            f"**Topic:** {self.topic}",
            "",
            f"## TCM Evidence Packet (`{self.tcm_packet_id}`)",
            f"*Canonical Self-Hash:* `{self.tcm_packet_canonical_sha256}`",
            "",
        ]

        for item in self.tcm_items:
            lines.extend(
                [
                    f"### TCM Rank {item.rank}: `{item.evidence_id}`",
                    f"- **Length:** {item.text_length} code points",
                    f"- **Chunk SHA256:** `{item.chunk_text_sha256}`",
                    f"- **Source Title:** {item.source_title or 'N/A'}",
                    f"- **Section:** {item.section_or_category or 'N/A'}",
                    f"- **DOI/PMCID:** {item.doi or item.pmcid or 'N/A'}",
                    "",
                    "```text",
                    item.exact_chunk_text,
                    "```",
                    "",
                ]
            )

        lines.extend(
            [
                f"## Western Evidence Packet (`{self.western_packet_id}`)",
                f"*Canonical Self-Hash:* `{self.western_packet_canonical_sha256}`",
                "",
            ]
        )

        for item in self.western_items:
            lines.extend(
                [
                    f"### Western Rank {item.rank}: `{item.evidence_id}`",
                    f"- **Length:** {item.text_length} code points",
                    f"- **Chunk SHA256:** `{item.chunk_text_sha256}`",
                    f"- **Source Title:** {item.source_title or 'N/A'}",
                    f"- **Section:** {item.section_or_category or 'N/A'}",
                    f"- **DOI/PMCID:** {item.doi or item.pmcid or 'N/A'}",
                    "",
                    "```text",
                    item.exact_chunk_text,
                    "```",
                    "",
                ]
            )

        return "\n".join(lines)


class BaseAnnotationViewer:
    """Base class for read-only packet inspection and export."""

    def __init__(self, packet_index: FrozenPacketAnchorIndex) -> None:
        self._index = packet_index

    @property
    def packet_index(self) -> FrozenPacketAnchorIndex:
        return self._index

    def list_questions(self) -> list[str]:
        """Return sorted list of all question IDs in the index."""
        return sorted(self._index.questions)

    def get_question_view(self, question_id: str) -> ReadOnlyQuestionView:
        """Assemble a mechanical read-only view for a single question.

        Raises:
            KeyError: if question_id is not in the index.
            FormalPacketAuthorityError: if question does not have exactly 4 TCM and 4 Western items.
        """
        if question_id not in self._index.questions:
            raise KeyError(f"Unknown question_id: '{question_id}'")

        pkt_map = self._index.get_question_packet_ids(question_id)
        tcm_pid = pkt_map.get("tcm")
        western_pid = pkt_map.get("western")

        if not tcm_pid or not western_pid:
            raise FormalPacketAuthorityError(
                f"Question {question_id} missing stream packet: TCM={tcm_pid}, Western={western_pid}"
            )

        tcm_pkt = self._index.get_packet(tcm_pid)
        western_pkt = self._index.get_packet(western_pid)

        if not tcm_pkt or not western_pkt:
            raise FormalPacketAuthorityError(
                f"Packet metadata missing for {tcm_pid} or {western_pid}"
            )

        # Collect and rank TCM items
        tcm_items: list[ReadOnlyEvidenceItemView] = []
        for ev_id in tcm_pkt.evidence_ids:
            ev_meta = self._index.get_evidence(tcm_pid, ev_id)
            if not ev_meta:
                raise FormalPacketAuthorityError(
                    f"Evidence metadata missing for ({tcm_pid}, {ev_id})"
                )
            tcm_items.append(
                ReadOnlyEvidenceItemView(
                    evidence_id=ev_meta.evidence_id,
                    packet_id=tcm_pid,
                    perspective="tcm",
                    rank=ev_meta.rank,
                    exact_chunk_text=ev_meta.exact_chunk_text,
                    text_length=ev_meta.text_length,
                    chunk_text_sha256=ev_meta.chunk_text_sha256,
                    packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
                    provenance=ev_meta.provenance,
                    source_title=ev_meta.source_title,
                    source_url=ev_meta.source_url,
                    section_or_category=ev_meta.section_or_category,
                    doi=ev_meta.doi,
                    pmcid=ev_meta.pmcid,
                )
            )

        # Collect and rank Western items
        western_items: list[ReadOnlyEvidenceItemView] = []
        for ev_id in western_pkt.evidence_ids:
            ev_meta = self._index.get_evidence(western_pid, ev_id)
            if not ev_meta:
                raise FormalPacketAuthorityError(
                    f"Evidence metadata missing for ({western_pid}, {ev_id})"
                )
            western_items.append(
                ReadOnlyEvidenceItemView(
                    evidence_id=ev_meta.evidence_id,
                    packet_id=western_pid,
                    perspective="western",
                    rank=ev_meta.rank,
                    exact_chunk_text=ev_meta.exact_chunk_text,
                    text_length=ev_meta.text_length,
                    chunk_text_sha256=ev_meta.chunk_text_sha256,
                    packet_canonical_sha256=western_pkt.packet_canonical_sha256,
                    provenance=ev_meta.provenance,
                    source_title=ev_meta.source_title,
                    source_url=ev_meta.source_url,
                    section_or_category=ev_meta.section_or_category,
                    doi=ev_meta.doi,
                    pmcid=ev_meta.pmcid,
                )
            )

        tcm_items.sort(key=lambda it: it.rank)
        western_items.sort(key=lambda it: it.rank)

        if len(tcm_items) != 4 or [it.rank for it in tcm_items] != [1, 2, 3, 4]:
            raise FormalPacketAuthorityError(
                f"TCM packet {tcm_pid} has invalid items/ranks: {[it.rank for it in tcm_items]}"
            )
        if len(western_items) != 4 or [it.rank for it in western_items] != [1, 2, 3, 4]:
            raise FormalPacketAuthorityError(
                f"Western packet {western_pid} has invalid items/ranks: {[it.rank for it in western_items]}"
            )

        question_text = self._index.get_question_text(question_id)
        topic = self._index.get_question_topic(question_id)

        return ReadOnlyQuestionView(
            question_id=question_id,
            question_text=question_text,
            topic=topic,
            tcm_packet_id=tcm_pid,
            tcm_packet_canonical_sha256=tcm_pkt.packet_canonical_sha256,
            western_packet_id=western_pid,
            western_packet_canonical_sha256=western_pkt.packet_canonical_sha256,
            tcm_items=tuple(tcm_items),
            western_items=tuple(western_items),
        )

    def export_question(
        self,
        question_id: str,
        output_dir: Path,
        format: Literal["json", "markdown"] = "json",
    ) -> Path:
        """Export a single question view to a local directory for human review.

        Fail-closed:
          - output_dir must be explicitly provided.
          - destination file must NOT already exist.
        """
        view = self.get_question_view(question_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        if format == "json":
            out_file = output_dir / f"{question_id}.json"
            if out_file.exists():
                raise FileExistsError(f"Export destination already exists: {out_file}")
            out_file.write_text(
                json.dumps(view.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        elif format == "markdown":
            out_file = output_dir / f"{question_id}.md"
            if out_file.exists():
                raise FileExistsError(f"Export destination already exists: {out_file}")
            out_file.write_text(view.to_markdown() + "\n", encoding="utf-8")
        else:
            raise ValueError(f"Unsupported format '{format}', must be 'json' or 'markdown'")

        return out_file

    def export_all_questions(
        self,
        output_dir: Path,
        format: Literal["json", "markdown"] = "json",
    ) -> list[Path]:
        """Export all questions to a new local directory.

        Fail-closed:
          - output_dir must NOT already exist to prevent accidental overwrites.
        """
        if output_dir.exists():
            raise FileExistsError(
                f"Export directory already exists: {output_dir}. "
                "Export requires a new unique local destination directory."
            )

        output_dir.mkdir(parents=True, exist_ok=False)

        # Write top-level local-only readme notice
        notice_file = output_dir / "README_LOCAL_ONLY.txt"
        notice_file.write_text(
            "LOCAL-ONLY HUMAN ANNOTATION EXPORT - DO NOT COMMIT TO VERSION CONTROL\n"
            f"Protocol ID: {PROTOCOL_ID}\n"
            f"Study ID: {STUDY_ID}\n"
            f"Exported At (UTC): {datetime.now(timezone.utc).isoformat()}\n"
            "This directory contains source-derived frozen packet text for human reviewer inspection.\n"
            "Do NOT stage or commit any files from this directory.\n",
            encoding="utf-8",
        )

        exported_paths: list[Path] = [notice_file]
        for qid in self.list_questions():
            exported_paths.append(self.export_question(qid, output_dir, format=format))

        return exported_paths


class FormalAnnotationViewer(BaseAnnotationViewer):
    """Formal study annotation viewer.

    MUST be initialized only with a formally verified FrozenPacketAnchorIndex.
    Guarantees formal packet byte hash authority.
    """

    def __init__(self, packet_index: FrozenPacketAnchorIndex) -> None:
        if not getattr(packet_index, "is_formal_verified", False):
            raise FormalPacketAuthorityError(
                "FormalAnnotationViewer requires a formally verified packet index "
                "loaded via from_repo_root or from_verified_formal_packets. "
                "Use SyntheticAnnotationViewer for unverified/in-memory test fixtures."
            )
        super().__init__(packet_index)

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> FormalAnnotationViewer:
        """Construct formal viewer from default study packet locations under repo root."""
        index = FrozenPacketAnchorIndex.from_repo_root(repo_root)
        return cls(index)

    @classmethod
    def from_verified_formal_packets(
        cls,
        tcm_packet_file: Path,
        western_packet_file: Path,
    ) -> FormalAnnotationViewer:
        """Construct formal viewer from explicit verified formal packet files."""
        index = FrozenPacketAnchorIndex.from_verified_formal_packets(
            tcm_packet_file, western_packet_file
        )
        return cls(index)


class SyntheticAnnotationViewer(BaseAnnotationViewer):
    """Synthetic viewer reserved exclusively for in-memory and synthetic test fixtures."""

    @classmethod
    def from_packet_records(
        cls,
        tcm_records: list[dict[str, Any]],
        western_records: list[dict[str, Any]],
    ) -> SyntheticAnnotationViewer:
        """Construct viewer from in-memory parsed packet records."""
        index = FrozenPacketAnchorIndex.from_packet_records(tcm_records, western_records)
        return cls(index)


# ==============================================================================
# Span Coordinate Helper Functions
# ==============================================================================

def locate_exact_substring(
    exact_chunk_text: str,
    target_substring: str,
) -> list[tuple[int, int]]:
    """Locate all zero-based half-open Unicode code-point offsets of target_substring in exact_chunk_text.

    Purely mechanical string matching:
      - exact substring match
      - no Unicode normalization
      - no whitespace stripping
      - no fuzzy matching
    """
    if not target_substring:
        return []

    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        pos = exact_chunk_text.find(target_substring, start)
        if pos == -1:
            break
        end = pos + len(target_substring)
        matches.append((pos, end))
        start = pos + 1

    return matches


def resolve_unique_span_coordinates(
    exact_chunk_text: str,
    target_substring: str,
) -> tuple[int, int]:
    """Resolve an exact literal substring to its unique [start, end) offsets.

    Raises:
        ValueError: if target_substring is empty or not found.
        AmbiguousSpanError: if target_substring appears more than once in exact_chunk_text.
    """
    if not target_substring:
        raise ValueError("Target substring must be non-empty")

    matches = locate_exact_substring(exact_chunk_text, target_substring)
    if not matches:
        snippet = target_substring[:40] + ("..." if len(target_substring) > 40 else "")
        raise ValueError(f"Target substring not found in chunk text: '{snippet}'")

    if len(matches) > 1:
        raise AmbiguousSpanError(
            f"Target substring appears {len(matches)} times at offsets {matches}. "
            "Reviewer must specify explicit [start, end) coordinates."
        )

    return matches[0]


def validate_span_coordinates(
    exact_chunk_text: str,
    start: int,
    end: int,
) -> tuple[int, int, str]:
    """Validate that [start, end) are valid Unicode code-point coordinates within exact_chunk_text.

    Returns (start, end, exact_chunk_text[start:end]).
    Raises ValueError on out-of-bounds or inverted coordinates.
    """
    text_len = len(exact_chunk_text)
    if start < 0:
        raise ValueError(f"Span start offset ({start}) must be non-negative")
    if end < start:
        raise ValueError(f"Span end offset ({end}) cannot be less than start ({start})")
    if end > text_len:
        raise ValueError(
            f"Span end offset ({end}) exceeds text length ({text_len} Unicode code points)"
        )

    return (start, end, exact_chunk_text[start:end])


# ==============================================================================
# Reviewer Workspace / Submission Containers
# ==============================================================================

@dataclass
class ReviewerWorkspace:
    """Isolated submission container for one human reviewer.

    Records:
      - reviewer role (strictly 'reviewer_a' or 'reviewer_b')
      - protocol ID and frozen byte hash
      - TCM / Western packet frozen byte hashes
      - question IDs
      - annotation state ('blank', 'in_progress', 'submitted_locked')
      - human-entered reference unit records
      - submission lock metadata
    """

    reviewer_role: ReviewerRole
    protocol_id: str
    protocol_byte_sha256: str
    tcm_packet_byte_sha256: str
    western_packet_byte_sha256: str
    study_id: str
    question_ids: tuple[str, ...]
    annotation_state: str = "blank"
    records: list[dict[str, Any]] = field(default_factory=list)
    submission_locked: bool = False
    lock_metadata: dict[str, Any] | None = None

    @classmethod
    def create_blank(
        cls,
        reviewer_role: ReviewerRole,
        question_ids: Sequence[str],
    ) -> ReviewerWorkspace:
        """Create a blank, unpopulated workspace for Reviewer A or Reviewer B.

        Contains zero pre-populated semantic units.
        """
        if reviewer_role not in ("reviewer_a", "reviewer_b"):
            raise ReviewerRoleMismatchError(
                f"Invalid reviewer_role '{reviewer_role}': must be 'reviewer_a' or 'reviewer_b'"
            )

        return cls(
            reviewer_role=reviewer_role,
            protocol_id=PROTOCOL_ID,
            protocol_byte_sha256=FROZEN_PROTOCOL_BYTE_SHA256,
            tcm_packet_byte_sha256=FROZEN_TCM_PACKET_BYTE_SHA256,
            western_packet_byte_sha256=FROZEN_WESTERN_PACKET_BYTE_SHA256,
            study_id=STUDY_ID,
            question_ids=tuple(question_ids),
            annotation_state="blank",
            records=[],
            submission_locked=False,
            lock_metadata=None,
        )

    def add_record(
        self,
        record: ReferenceUnitRecord | dict[str, Any],
        packet_index: FrozenPacketAnchorIndex | None = None,
        mode: ValidationMode = "draft",
    ) -> None:
        """Add a human-entered reference unit record after structural validation.

        Fail-closed:
          - raises WorkspaceLockedError if submission is locked.
          - raises ValueError if record fails schema or mode validation.
        """
        if self.submission_locked:
            raise WorkspaceLockedError("Cannot add record: workspace is locked for submission")

        # Validate structure against schema & protocol rules
        errors = validate_reference_unit_record(record, mode=mode, packet_index=packet_index)
        if errors:
            raise ValueError(f"Record validation failed with {len(errors)} error(s): {errors}")

        rec_dict = record.model_dump() if isinstance(record, ReferenceUnitRecord) else dict(record)
        self.records.append(rec_dict)
        self.annotation_state = "in_progress"

    def lock_submission(self, notes: str = "") -> dict[str, Any]:
        """Lock the workspace to finalize human review.

        No further records may be added once locked.
        """
        self.submission_locked = True
        self.annotation_state = "submitted_locked"
        self.lock_metadata = {
            "locked_at_utc": datetime.now(timezone.utc).isoformat(),
            "record_count": len(self.records),
            "reviewer_role": self.reviewer_role,
            "protocol_byte_sha256": self.protocol_byte_sha256,
            "notes": notes,
        }
        return dict(self.lock_metadata)

    def to_dict(self) -> dict[str, Any]:
        """Serialize workspace to dictionary."""
        return {
            "$notice": (
                "LOCAL-ONLY / DO NOT COMMIT - Isolated human reviewer submission container. "
                "Contains unpublished human annotations."
            ),
            "reviewer_role": self.reviewer_role,
            "protocol_id": self.protocol_id,
            "protocol_byte_sha256": self.protocol_byte_sha256,
            "tcm_packet_byte_sha256": self.tcm_packet_byte_sha256,
            "western_packet_byte_sha256": self.western_packet_byte_sha256,
            "study_id": self.study_id,
            "question_ids": list(self.question_ids),
            "annotation_state": self.annotation_state,
            "submission_locked": self.submission_locked,
            "lock_metadata": self.lock_metadata,
            "record_count": len(self.records),
            "records": self.records,
        }

    def save_local(self, file_path: Path, overwrite: bool = False) -> Path:
        """Save workspace to a local JSON file.

        Fail-closed: fails if file_path exists unless overwrite=True.
        """
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"Workspace file already exists: {file_path}")

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return file_path

    @classmethod
    def load_local(
        cls,
        file_path: Path,
        expected_reviewer: ReviewerRole | None = None,
    ) -> ReviewerWorkspace:
        """Load workspace from a local JSON file with authority and role verification."""
        if not file_path.is_file():
            raise FileNotFoundError(f"Workspace file not found: {file_path}")

        data = json.loads(file_path.read_text(encoding="utf-8"))

        # Verify protocol & packet frozen hashes
        if data.get("protocol_id") != PROTOCOL_ID:
            raise FormalPacketAuthorityError(
                f"Protocol ID mismatch: '{data.get('protocol_id')}' != '{PROTOCOL_ID}'"
            )
        if data.get("protocol_byte_sha256") != FROZEN_PROTOCOL_BYTE_SHA256:
            raise FormalPacketAuthorityError(
                f"Protocol byte SHA mismatch: '{data.get('protocol_byte_sha256')}' != '{FROZEN_PROTOCOL_BYTE_SHA256}'"
            )
        if data.get("tcm_packet_byte_sha256") != FROZEN_TCM_PACKET_BYTE_SHA256:
            raise FormalPacketAuthorityError(
                f"TCM packet byte SHA mismatch: '{data.get('tcm_packet_byte_sha256')}' != '{FROZEN_TCM_PACKET_BYTE_SHA256}'"
            )
        if data.get("western_packet_byte_sha256") != FROZEN_WESTERN_PACKET_BYTE_SHA256:
            raise FormalPacketAuthorityError(
                f"Western packet byte SHA mismatch: '{data.get('western_packet_byte_sha256')}' != '{FROZEN_WESTERN_PACKET_BYTE_SHA256}'"
            )

        role = data.get("reviewer_role")
        if role not in ("reviewer_a", "reviewer_b"):
            raise ReviewerRoleMismatchError(f"Invalid reviewer role in file: '{role}'")

        if expected_reviewer and role != expected_reviewer:
            raise ReviewerRoleMismatchError(
                f"Workspace reviewer '{role}' does not match expected reviewer '{expected_reviewer}'"
            )

        return cls(
            reviewer_role=role,
            protocol_id=data["protocol_id"],
            protocol_byte_sha256=data["protocol_byte_sha256"],
            tcm_packet_byte_sha256=data["tcm_packet_byte_sha256"],
            western_packet_byte_sha256=data["western_packet_byte_sha256"],
            study_id=data.get("study_id", STUDY_ID),
            question_ids=tuple(data.get("question_ids", ())),
            annotation_state=data.get("annotation_state", "blank"),
            records=data.get("records", []),
            submission_locked=bool(data.get("submission_locked", False)),
            lock_metadata=data.get("lock_metadata"),
        )
