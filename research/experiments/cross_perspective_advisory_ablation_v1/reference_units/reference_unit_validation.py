"""Mechanical Structural Validators and Frozen Packet Index.

Protocol Anchor: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Schema Version: cpaa1_reference_unit_v1
Study ID: cross-perspective-advisory-ablation-v1

This module implements mechanical, read-only structural validation for human
reference units, evidence anchors, and frozen packet index lookups.

CRITICAL ARCHITECTURAL BOUNDARY:
This module does NOT evaluate semantic support, relevance, clinical accuracy,
comparability, decomposition quality, or dispute adjudication.
All semantic evaluations are exclusively performed by human reviewers.
Mechanical validators verify only:
- schema conformity
- identifier and hash integrity
- span coordinate bounds
- structural protocol relationships (e.g. scope_audit coverage for packet_bounded_absence)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from .reference_unit_schema import (
    ALLOWED_ANCHOR_PERSPECTIVES,
    ALLOWED_ANCHOR_ROLES,
    ALLOWED_PERSPECTIVE_SCOPES,
    ALLOWED_REVIEW_STATUSES,
    ALLOWED_SUPPORT_SCOPES,
    ALLOWED_UNIT_TYPES,
    FINAL_REFERENCE_UNIT_ID_PATTERN,
    SCHEMA_VERSION,
    STUDY_ID,
    EvidenceAnchor,
    ReferenceUnitRecord,
    parse_final_reference_unit_id,
)


@dataclass(frozen=True)
class PacketMetadata:
    """Read-only mechanical index entry for a frozen evidence packet."""
    packet_id: str
    question_id: str
    perspective: str
    packet_canonical_sha256: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceItemMetadata:
    """Read-only mechanical index entry for an evidence item within a packet."""
    evidence_id: str
    packet_id: str
    question_id: str
    perspective: str
    rank: int
    chunk_text_sha256: str
    text_length: int  # Length in Unicode code points
    exact_chunk_text: str  # In-memory text retained solely for span coordinate boundary validation


class FrozenPacketAnchorIndex:
    """Read-only mechanical index of frozen packets and evidence items.

    This index is NOT a semantic retrieval index or search tool.
    It performs no filtering, ranking, scoring, or candidate generation.
    It exists strictly to verify:
    - does a referenced packet exist?
    - does the packet self-hash match?
    - does an evidence_id belong to that packet and question?
    - does the chunk_text_sha256 match?
    - do span [start, end] coordinates lie within the text length?
    """

    def __init__(
        self,
        packets: dict[str, PacketMetadata],
        evidence_items: dict[tuple[str, str], EvidenceItemMetadata],
        question_to_packets: dict[str, dict[str, str]],
        question_to_evidence_ids: dict[str, set[str]],
        questions: set[str],
    ) -> None:
        self._packets = packets
        self._evidence_items = evidence_items
        self._question_to_packets = question_to_packets
        self._question_to_evidence_ids = question_to_evidence_ids
        self._questions = questions

    @classmethod
    def from_packet_records(
        cls,
        tcm_records: list[dict[str, Any]],
        western_records: list[dict[str, Any]],
    ) -> FrozenPacketAnchorIndex:
        """Construct index from parsed packet dictionaries (real or synthetic)."""
        packets: dict[str, PacketMetadata] = {}
        evidence_items: dict[tuple[str, str], EvidenceItemMetadata] = {}
        question_to_packets: dict[str, dict[str, str]] = {}
        question_to_evidence_ids: dict[str, set[str]] = {}
        questions: set[str] = set()

        for rec in tcm_records + western_records:
            packet_id = str(rec["packet_id"])
            question_id = str(rec["question_id"])
            perspective = str(rec["perspective"])
            packet_sha = str(rec["packet_canonical_sha256"])
            raw_items = rec.get("evidence_items", [])

            ev_ids: list[str] = []
            for item in raw_items:
                ev_id = str(item["evidence_id"])
                ev_ids.append(ev_id)
                chunk_sha = str(item["chunk_text_sha256"])
                exact_text = str(item.get("exact_chunk_text", ""))
                rank = int(item.get("rank", 0))

                item_meta = EvidenceItemMetadata(
                    evidence_id=ev_id,
                    packet_id=packet_id,
                    question_id=question_id,
                    perspective=perspective,
                    rank=rank,
                    chunk_text_sha256=chunk_sha,
                    text_length=len(exact_text),
                    exact_chunk_text=exact_text,
                )
                evidence_items[(packet_id, ev_id)] = item_meta

            packets[packet_id] = PacketMetadata(
                packet_id=packet_id,
                question_id=question_id,
                perspective=perspective,
                packet_canonical_sha256=packet_sha,
                evidence_ids=tuple(ev_ids),
            )

            questions.add(question_id)
            if question_id not in question_to_packets:
                question_to_packets[question_id] = {}
            question_to_packets[question_id][perspective] = packet_id

            if question_id not in question_to_evidence_ids:
                question_to_evidence_ids[question_id] = set()
            question_to_evidence_ids[question_id].update(ev_ids)

        return cls(
            packets=packets,
            evidence_items=evidence_items,
            question_to_packets=question_to_packets,
            question_to_evidence_ids=question_to_evidence_ids,
            questions=questions,
        )

    @classmethod
    def from_packet_files(
        cls,
        tcm_packet_file: Path,
        western_packet_file: Path,
    ) -> FrozenPacketAnchorIndex:
        """Load and mechanically index actual frozen local packet JSONL files."""
        if not tcm_packet_file.is_file():
            raise FileNotFoundError(f"TCM packet file not found at {tcm_packet_file}")
        if not western_packet_file.is_file():
            raise FileNotFoundError(f"Western packet file not found at {western_packet_file}")

        tcm_lines = [
            json.loads(line)
            for line in tcm_packet_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        western_lines = [
            json.loads(line)
            for line in western_packet_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls.from_packet_records(tcm_lines, western_lines)

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> FrozenPacketAnchorIndex:
        """Load index from default study packet paths under repo root."""
        packets_dir = (
            repo_root
            / "research"
            / "experiments"
            / "cross_perspective_advisory_ablation_v1"
            / "packets"
        )
        tcm_file = packets_dir / "tcm_packets.jsonl"
        western_file = packets_dir / "western_packets.jsonl"
        return cls.from_packet_files(tcm_file, western_file)

    @property
    def packet_count(self) -> int:
        return len(self._packets)

    @property
    def evidence_item_count(self) -> int:
        return len(self._evidence_items)

    @property
    def questions(self) -> set[str]:
        return set(self._questions)

    def has_packet(self, packet_id: str) -> bool:
        return packet_id in self._packets

    def get_packet(self, packet_id: str) -> PacketMetadata | None:
        return self._packets.get(packet_id)

    def has_evidence(self, packet_id: str, evidence_id: str) -> bool:
        return (packet_id, evidence_id) in self._evidence_items

    def get_evidence(self, packet_id: str, evidence_id: str) -> EvidenceItemMetadata | None:
        return self._evidence_items.get((packet_id, evidence_id))

    def get_question_evidence_ids(self, question_id: str) -> set[str]:
        return set(self._question_to_evidence_ids.get(question_id, set()))

    def get_question_packet_ids(self, question_id: str) -> dict[str, str]:
        return dict(self._question_to_packets.get(question_id, {}))


def validate_evidence_anchor(
    anchor: EvidenceAnchor | dict[str, Any],
    packet_index: FrozenPacketAnchorIndex | None = None,
) -> list[str]:
    """Mechanically validate an evidence anchor object against protocol rules.

    Returns a list of structural error strings (empty list indicates valid anchor).
    """
    errors: list[str] = []

    if isinstance(anchor, dict):
        try:
            anchor_obj = EvidenceAnchor.model_validate(anchor)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                errors.append(f"Anchor schema validation error at {loc}: {err['msg']}")
            return errors
    elif isinstance(anchor, EvidenceAnchor):
        anchor_obj = anchor
    else:
        errors.append(f"Expected EvidenceAnchor or dict, got {type(anchor).__name__}")
        return errors

    # Role and spans structural requirements
    if anchor_obj.anchor_role in ("supporting_span", "contrasting_span"):
        if not anchor_obj.spans:
            errors.append(
                f"Anchor role '{anchor_obj.anchor_role}' requires at least one span (cannot be empty)"
            )
    elif anchor_obj.anchor_role == "scope_audit":
        # Section G: scope_audit anchors may have empty spans
        pass

    # Span coordinates: 0 <= start < end
    for i, s in enumerate(anchor_obj.spans):
        if s.start < 0:
            errors.append(f"Span {i} start coordinate cannot be negative, got {s.start}")
        if s.start >= s.end:
            errors.append(
                f"Span {i} start coordinate ({s.start}) must be strictly less than end ({s.end})"
            )

    # If packet_index is available, mechanically verify against frozen packet bytes
    if packet_index is not None:
        packet_meta = packet_index.get_packet(anchor_obj.packet_id)
        if packet_meta is None:
            errors.append(
                f"Anchor packet_id '{anchor_obj.packet_id}' not found in frozen packet index"
            )
            return errors

        if packet_meta.perspective != anchor_obj.perspective:
            errors.append(
                f"Perspective mismatch: anchor perspective '{anchor_obj.perspective}' "
                f"does not match packet perspective '{packet_meta.perspective}'"
            )

        if packet_meta.packet_canonical_sha256 != anchor_obj.packet_canonical_sha256:
            errors.append(
                f"Packet hash mismatch for '{anchor_obj.packet_id}': anchor has "
                f"'{anchor_obj.packet_canonical_sha256}', frozen index has '{packet_meta.packet_canonical_sha256}'"
            )

        ev_meta = packet_index.get_evidence(anchor_obj.packet_id, anchor_obj.evidence_id)
        if ev_meta is None:
            errors.append(
                f"Evidence ID '{anchor_obj.evidence_id}' not found in packet '{anchor_obj.packet_id}'"
            )
            return errors

        if ev_meta.chunk_text_sha256 != anchor_obj.chunk_text_sha256:
            errors.append(
                f"Chunk text hash mismatch for evidence '{anchor_obj.evidence_id}': anchor has "
                f"'{anchor_obj.chunk_text_sha256}', frozen index has '{ev_meta.chunk_text_sha256}'"
            )

        # Coordinate bounds check against actual Unicode code-point length
        for i, s in enumerate(anchor_obj.spans):
            if s.end > ev_meta.text_length:
                errors.append(
                    f"Span {i} coordinate out of bounds for evidence '{anchor_obj.evidence_id}': "
                    f"[{s.start}, {s.end}] exceeds text length {ev_meta.text_length}"
                )

    return errors


def validate_reference_unit_record(
    record: ReferenceUnitRecord | dict[str, Any],
    mode: Literal["draft", "final_candidate"] = "final_candidate",
    packet_index: FrozenPacketAnchorIndex | None = None,
    question_manifest_ids: set[str] | None = None,
) -> list[str]:
    """Mechanically validate a reference-unit record according to the frozen protocol.

    Validation Modes:
    - 'draft': Permits unfinalized administrative states (draft/disputed status,
      unassigned reference_unit_id, ongoing reviewer annotations).
    - 'final_candidate': Requires reconciled status, deterministic final ID, non-empty
      substantive unit text, non-empty support rationale, and complete structural anchors.

    Returns a list of structural error strings (empty list indicates valid record).
    """
    errors: list[str] = []

    if isinstance(record, dict):
        try:
            rec_obj = ReferenceUnitRecord.model_validate(record)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"])
                errors.append(f"Record schema validation error at {loc}: {err['msg']}")
            return errors
    elif isinstance(record, ReferenceUnitRecord):
        rec_obj = record
    else:
        errors.append(f"Expected ReferenceUnitRecord or dict, got {type(record).__name__}")
        return errors

    # Constants & enums checks
    if rec_obj.schema_version != SCHEMA_VERSION:
        errors.append(f"Invalid schema_version '{rec_obj.schema_version}', expected '{SCHEMA_VERSION}'")
    if rec_obj.study_id != STUDY_ID:
        errors.append(f"Invalid study_id '{rec_obj.study_id}', expected '{STUDY_ID}'")
    if rec_obj.unit_type not in ALLOWED_UNIT_TYPES:
        errors.append(f"Invalid unit_type '{rec_obj.unit_type}', allowed: {sorted(ALLOWED_UNIT_TYPES)}")
    if rec_obj.perspective_scope not in ALLOWED_PERSPECTIVE_SCOPES:
        errors.append(
            f"Invalid perspective_scope '{rec_obj.perspective_scope}', allowed: {sorted(ALLOWED_PERSPECTIVE_SCOPES)}"
        )
    if rec_obj.support_scope not in ALLOWED_SUPPORT_SCOPES:
        errors.append(
            f"Invalid support_scope '{rec_obj.support_scope}', allowed: {sorted(ALLOWED_SUPPORT_SCOPES)}"
        )
    if rec_obj.review_status not in ALLOWED_REVIEW_STATUSES:
        errors.append(
            f"Invalid review_status '{rec_obj.review_status}', allowed: {sorted(ALLOWED_REVIEW_STATUSES)}"
        )

    # Question ID existence check
    valid_qids = question_manifest_ids or (packet_index.questions if packet_index else None)
    if valid_qids is not None and rec_obj.question_id not in valid_qids:
        errors.append(f"Unknown question_id '{rec_obj.question_id}' not present in study question set")

    # Mode-specific requirements
    if mode == "final_candidate":
        if rec_obj.review_status != "reconciled":
            errors.append(
                f"Final candidate record must have review_status='reconciled', got '{rec_obj.review_status}'"
            )

        if not rec_obj.reference_unit_id:
            errors.append("Final candidate record must have a non-empty reference_unit_id")
        else:
            parsed = parse_final_reference_unit_id(rec_obj.reference_unit_id)
            if parsed is None:
                errors.append(
                    f"Invalid final reference_unit_id format '{rec_obj.reference_unit_id}'. "
                    f"Must match 'cpaa1:ru:<question_id>:<three-digit ordinal>'"
                )
            else:
                qid_in_id, _ = parsed
                if qid_in_id != rec_obj.question_id:
                    errors.append(
                        f"Mismatched question_id in reference_unit_id: ID contains '{qid_in_id}', "
                        f"record question_id is '{rec_obj.question_id}'"
                    )

        if not rec_obj.unit_text.strip():
            errors.append("Final candidate record must have non-empty unit_text")
        if not rec_obj.support_rationale.strip():
            errors.append("Final candidate record must have non-empty support_rationale")
        if not rec_obj.evidence_anchors:
            errors.append("Final candidate record must have at least one evidence anchor")

    elif mode == "draft":
        # In draft mode, reference_unit_id is optional. If provided in final format, verify qid match.
        if rec_obj.reference_unit_id:
            parsed = parse_final_reference_unit_id(rec_obj.reference_unit_id)
            if parsed is not None:
                qid_in_id, _ = parsed
                if qid_in_id != rec_obj.question_id:
                    errors.append(
                        f"Mismatched question_id in reference_unit_id: ID contains '{qid_in_id}', "
                        f"record question_id is '{rec_obj.question_id}'"
                    )

    # Validate individual anchors
    for idx, anchor in enumerate(rec_obj.evidence_anchors):
        anchor_errors = validate_evidence_anchor(anchor, packet_index=packet_index)
        for ae in anchor_errors:
            errors.append(f"Anchor {idx} ({anchor.evidence_id}): {ae}")

        # Check anchor-to-question correspondence when packet_index is available
        if packet_index is not None:
            pkt_meta = packet_index.get_packet(anchor.packet_id)
            if pkt_meta is not None and pkt_meta.question_id != rec_obj.question_id:
                errors.append(
                    f"Anchor {idx} packet '{anchor.packet_id}' belongs to question '{pkt_meta.question_id}', "
                    f"not record question_id '{rec_obj.question_id}'"
                )

    # Perspective Scope Structural Rules (Task 10)
    pertinent_anchors = [
        a for a in rec_obj.evidence_anchors
        if a.anchor_role in ("supporting_span", "contrasting_span") and len(a.spans) > 0
    ]

    if rec_obj.perspective_scope == "both":
        if rec_obj.support_scope == "packet_bounded_absence":
            tcm_anchors = [a for a in rec_obj.evidence_anchors if a.perspective == "tcm"]
            western_anchors = [a for a in rec_obj.evidence_anchors if a.perspective == "western"]
            if not tcm_anchors:
                errors.append(
                    "perspective_scope='both' with packet_bounded_absence requires anchors from TCM"
                )
            if not western_anchors:
                errors.append(
                    "perspective_scope='both' with packet_bounded_absence requires anchors from Western"
                )
        else:
            tcm_pertinent = [a for a in pertinent_anchors if a.perspective == "tcm"]
            western_pertinent = [a for a in pertinent_anchors if a.perspective == "western"]
            if not tcm_pertinent:
                errors.append(
                    "perspective_scope='both' requires at least one pertinent supporting/contrasting anchor from TCM"
                )
            if not western_pertinent:
                errors.append(
                    "perspective_scope='both' requires at least one pertinent supporting/contrasting anchor from Western"
                )

    elif rec_obj.perspective_scope == "tcm":
        tcm_pertinent = [a for a in pertinent_anchors if a.perspective == "tcm"]
        if not tcm_pertinent and rec_obj.support_scope != "packet_bounded_absence":
            errors.append(
                "perspective_scope='tcm' requires at least one pertinent supporting/contrasting anchor from TCM"
            )
        # Note: Western scope_audit anchors are NOT rejected (e.g. scope audit of Western gap).

    elif rec_obj.perspective_scope == "western":
        western_pertinent = [a for a in pertinent_anchors if a.perspective == "western"]
        if not western_pertinent and rec_obj.support_scope != "packet_bounded_absence":
            errors.append(
                "perspective_scope='western' requires at least one pertinent supporting/contrasting anchor from Western"
            )
        # Note: TCM scope_audit anchors are NOT rejected.

    # Support Scope Structural Rules (Task 11 & Task 12)
    if rec_obj.support_scope == "packet_bounded_absence":
        # Task 11: packet_bounded_absence is permitted only when unit_type is evidence_gap or limitation
        if rec_obj.unit_type not in ("evidence_gap", "limitation"):
            errors.append(
                f"support_scope='packet_bounded_absence' is permitted only when unit_type is 'evidence_gap' "
                f"or 'limitation', got '{rec_obj.unit_type}'"
            )

        # Require scope_audit coverage of all 8 frozen evidence IDs for that question
        audit_anchors = [a for a in rec_obj.evidence_anchors if a.anchor_role == "scope_audit"]
        audit_ev_ids = [a.evidence_id for a in audit_anchors]
        unique_audit_ev_ids = set(audit_ev_ids)

        if len(audit_ev_ids) != len(unique_audit_ev_ids):
            errors.append("packet_bounded_absence anchors must have unique evidence IDs (no duplicates)")

        if packet_index is not None:
            expected_ev_ids = packet_index.get_question_evidence_ids(rec_obj.question_id)
            if len(expected_ev_ids) == 8:
                missing = expected_ev_ids - unique_audit_ev_ids
                if missing:
                    errors.append(
                        f"packet_bounded_absence requires scope_audit coverage of all 8 evidence IDs for question "
                        f"'{rec_obj.question_id}'. Missing {len(missing)} IDs: {sorted(missing)}"
                    )
            else:
                if len(unique_audit_ev_ids) < 8:
                    errors.append(
                        f"packet_bounded_absence requires scope_audit coverage of all 8 evidence IDs (4 TCM, 4 Western), "
                        f"got {len(unique_audit_ev_ids)}"
                    )
        else:
            # If no packet index, verify at least 8 unique scope_audit anchors with 4 TCM and 4 Western
            tcm_audit = [a for a in audit_anchors if a.perspective == "tcm"]
            western_audit = [a for a in audit_anchors if a.perspective == "western"]
            if len(tcm_audit) < 4 or len(western_audit) < 4:
                errors.append(
                    f"packet_bounded_absence requires 8 scope_audit anchors (4 TCM, 4 Western), "
                    f"got {len(tcm_audit)} TCM and {len(western_audit)} Western"
                )

        if not rec_obj.support_rationale.strip():
            errors.append("packet_bounded_absence requires a non-empty support_rationale")

    elif rec_obj.support_scope == "source_explicit":
        supporting_anchors = [a for a in rec_obj.evidence_anchors if a.anchor_role == "supporting_span"]
        if not supporting_anchors:
            errors.append(
                "support_scope='source_explicit' requires at least one anchor with anchor_role='supporting_span'"
            )

    elif rec_obj.support_scope == "cross_span_synthesis":
        if not rec_obj.support_rationale.strip():
            errors.append("support_scope='cross_span_synthesis' requires a non-empty support_rationale")
        if not pertinent_anchors:
            errors.append(
                "support_scope='cross_span_synthesis' requires at least one pertinent anchor with spans"
            )

    return errors
