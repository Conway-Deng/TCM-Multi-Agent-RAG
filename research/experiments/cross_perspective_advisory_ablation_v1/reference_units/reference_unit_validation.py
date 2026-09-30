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

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal

from pydantic import ValidationError

from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
    packet_canonical_sha256,
)

from .reference_unit_schema import (
    ALLOWED_ANCHOR_PERSPECTIVES,
    ALLOWED_ANCHOR_ROLES,
    ALLOWED_PERSPECTIVE_SCOPES,
    ALLOWED_REVIEW_STATUSES,
    ALLOWED_SUPPORT_SCOPES,
    ALLOWED_UNIT_TYPES,
    ALLOWED_VALIDATION_MODES,
    FINAL_REFERENCE_UNIT_ID_PATTERN,
    SCHEMA_VERSION,
    STUDY_ID,
    EvidenceAnchor,
    ReferenceUnitRecord,
    ValidationMode,
    parse_final_reference_unit_id,
)

FROZEN_TCM_PACKET_BYTE_SHA256: Final[str] = (
    "7ce35d0d8ea42ebc1b61cf87de858fed5c9b993a6e032435bab88a30e25eef3f"
)
FROZEN_WESTERN_PACKET_BYTE_SHA256: Final[str] = (
    "b5c48507de5467c2c8a5ee031d5d790b1e5ceccd53cf84ca2cd8b70f227555de"
)


class FormalPacketAuthorityError(ValueError):
    """Raised when formal packet file bytes or contents fail frozen authority verification."""


def verify_packet_records_integrity(
    tcm_records: list[dict[str, Any]],
    western_records: list[dict[str, Any]],
) -> None:
    """Verify canonical self-hashes, chunk text hashes, and cardinality for packet records.

    Fail-closed: raises FormalPacketAuthorityError if any integrity check fails.
    """
    all_records = [("tcm", r) for r in tcm_records] + [("western", r) for r in western_records]
    for stream_name, pkt in all_records:
        packet_id = pkt.get("packet_id", "<unknown>")
        # 1. Packet canonical self-hash
        stored_pkt_hash = pkt.get("packet_canonical_sha256")
        if not stored_pkt_hash:
            raise FormalPacketAuthorityError(
                f"Packet {packet_id} missing packet_canonical_sha256"
            )
        recomputed_pkt_hash = packet_canonical_sha256(pkt)
        if recomputed_pkt_hash != stored_pkt_hash:
            raise FormalPacketAuthorityError(
                f"Packet canonical self-hash mismatch for {packet_id}: "
                f"stored '{stored_pkt_hash}' != recomputed '{recomputed_pkt_hash}'"
            )

        # 2. Evidence items cardinality and rank sequence
        items = pkt.get("evidence_items", [])
        if len(items) != 4:
            raise FormalPacketAuthorityError(
                f"Packet {packet_id} expected exactly 4 evidence items, got {len(items)}"
            )
        ranks = [it.get("rank") for it in items]
        if ranks != [1, 2, 3, 4]:
            raise FormalPacketAuthorityError(
                f"Packet {packet_id} invalid rank sequence: {ranks}, expected [1, 2, 3, 4]"
            )

        # 3. Chunk text hash recomputation
        for it in items:
            ev_id = it.get("evidence_id", "<unknown>")
            stored_chunk_hash = it.get("chunk_text_sha256")
            if not stored_chunk_hash:
                raise FormalPacketAuthorityError(
                    f"Evidence {ev_id} in packet {packet_id} missing chunk_text_sha256"
                )
            chunk_text = it.get("exact_chunk_text", "")
            recomputed_chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            if recomputed_chunk_hash != stored_chunk_hash:
                raise FormalPacketAuthorityError(
                    f"Chunk text SHA256 mismatch for evidence {ev_id} in {packet_id}: "
                    f"stored '{stored_chunk_hash}' != recomputed '{recomputed_chunk_hash}'"
                )


@dataclass(frozen=True)
class PacketMetadata:
    """Read-only mechanical index entry for a frozen evidence packet."""
    packet_id: str
    question_id: str
    perspective: str
    packet_canonical_sha256: str
    evidence_ids: tuple[str, ...]
    question_text: str = ""
    topic: str = ""


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
    provenance: str = ""
    source_title: str = ""
    source_url: str = ""
    section_or_category: str = ""
    doi: str = ""
    pmcid: str = ""


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
        """Construct index from parsed packet dictionaries (real or synthetic).

        Always returns an unverified generic FrozenPacketAnchorIndex.
        """
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
            question_text = str(rec.get("question_text", ""))
            topic = str(rec.get("topic", ""))
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
                    provenance=str(item.get("provenance", "")),
                    source_title=str(item.get("source_title", "")),
                    source_url=str(item.get("source_url", "")),
                    section_or_category=str(item.get("section_or_category", "")),
                    doi=str(item.get("doi", "")),
                    pmcid=str(item.get("pmcid", "")),
                )
                evidence_items[(packet_id, ev_id)] = item_meta

            packets[packet_id] = PacketMetadata(
                packet_id=packet_id,
                question_id=question_id,
                perspective=perspective,
                packet_canonical_sha256=packet_sha,
                evidence_ids=tuple(ev_ids),
                question_text=question_text,
                topic=topic,
            )

            questions.add(question_id)
            if question_id not in question_to_packets:
                question_to_packets[question_id] = {}
            question_to_packets[question_id][perspective] = packet_id

            if question_id not in question_to_evidence_ids:
                question_to_evidence_ids[question_id] = set()
            question_to_evidence_ids[question_id].update(ev_ids)

        return FrozenPacketAnchorIndex(
            packets=packets,
            evidence_items=evidence_items,
            question_to_packets=question_to_packets,
            question_to_evidence_ids=question_to_evidence_ids,
            questions=questions,
        )

    @classmethod
    def from_verified_formal_packets(
        cls,
        tcm_packet_file: Path,
        western_packet_file: Path,
    ) -> VerifiedFormalPacketAnchorIndex:
        """Load and mechanically verify actual frozen local packet JSONL files.

        FAIL-CLOSED FORMAL AUTHORITY:
        1. Reads exact file bytes.
        2. Verifies exact byte SHA256 against immutable frozen anchors:
           - TCM: FROZEN_TCM_PACKET_BYTE_SHA256
           - Western: FROZEN_WESTERN_PACKET_BYTE_SHA256
           Caller override or substitution is strictly forbidden.
        3. If either byte hash mismatches: stops / raises FormalPacketAuthorityError.
        4. Parses only after byte verification.
        5. Recomputes packet canonical self-hash for every packet.
        6. Recomputes SHA256 of exact_chunk_text for every evidence item.
        7. Verifies cardinality (exactly 48 packets per stream, 4 items per packet, ranks 1-4).
        8. Returns a structurally distinct, sealed VerifiedFormalPacketAnchorIndex instance.
        """
        if not tcm_packet_file.is_file():
            raise FileNotFoundError(f"TCM packet file not found at {tcm_packet_file}")
        if not western_packet_file.is_file():
            raise FileNotFoundError(f"Western packet file not found at {western_packet_file}")

        # 1. Read exact file bytes first
        tcm_bytes = tcm_packet_file.read_bytes()
        western_bytes = western_packet_file.read_bytes()

        # 2. Before parsing/indexing, verify exact file byte SHA256 against fixed frozen anchors
        tcm_byte_sha = hashlib.sha256(tcm_bytes).hexdigest()
        if tcm_byte_sha != FROZEN_TCM_PACKET_BYTE_SHA256:
            raise FormalPacketAuthorityError(
                f"TCM packet file byte SHA256 mismatch: {tcm_byte_sha} != {FROZEN_TCM_PACKET_BYTE_SHA256}"
            )

        western_byte_sha = hashlib.sha256(western_bytes).hexdigest()
        if western_byte_sha != FROZEN_WESTERN_PACKET_BYTE_SHA256:
            raise FormalPacketAuthorityError(
                f"Western packet file byte SHA256 mismatch: {western_byte_sha} != {FROZEN_WESTERN_PACKET_BYTE_SHA256}"
            )

        # 4. Parse only AFTER byte-anchor verification
        tcm_lines = [
            json.loads(line)
            for line in tcm_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
        western_lines = [
            json.loads(line)
            for line in western_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]

        # 7. Cardinality check (exactly 48 packets per stream)
        if len(tcm_lines) != 48:
            raise FormalPacketAuthorityError(
                f"Expected exactly 48 TCM packets, got {len(tcm_lines)}"
            )
        if len(western_lines) != 48:
            raise FormalPacketAuthorityError(
                f"Expected exactly 48 Western packets, got {len(western_lines)}"
            )

        # 5 & 6. Verify packet canonical self-hashes and chunk text hashes
        verify_packet_records_integrity(tcm_lines, western_lines)

        # 7. Construct sealed VerifiedFormalPacketAnchorIndex directly inside this verified file loader
        raw_index = cls.from_packet_records(tcm_lines, western_lines)

        instance = object.__new__(VerifiedFormalPacketAnchorIndex)

        sealed_packets: MappingProxyType[str, PacketMetadata] = MappingProxyType(raw_index._packets)
        sealed_evidence_items: MappingProxyType[tuple[str, str], EvidenceItemMetadata] = MappingProxyType(
            raw_index._evidence_items
        )

        sealed_q_to_pkts: dict[str, MappingProxyType[str, str]] = {
            k: MappingProxyType(dict(v)) for k, v in raw_index._question_to_packets.items()
        }
        sealed_q_to_ev: dict[str, frozenset[str]] = {
            k: frozenset(v) for k, v in raw_index._question_to_evidence_ids.items()
        }

        object.__setattr__(instance, "_packets", sealed_packets)
        object.__setattr__(instance, "_evidence_items", sealed_evidence_items)
        object.__setattr__(instance, "_question_to_packets", MappingProxyType(sealed_q_to_pkts))
        object.__setattr__(instance, "_question_to_evidence_ids", MappingProxyType(sealed_q_to_ev))
        object.__setattr__(instance, "_questions", frozenset(raw_index._questions))
        object.__setattr__(instance, "_is_sealed", True)
        return instance

    @classmethod
    def from_packet_files(
        cls,
        tcm_packet_file: Path,
        western_packet_file: Path,
    ) -> VerifiedFormalPacketAnchorIndex:
        """Load formal packet JSONL files using verified formal authority."""
        return cls.from_verified_formal_packets(tcm_packet_file, western_packet_file)

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> VerifiedFormalPacketAnchorIndex:
        """Load verified formal index from default study packet paths under repo root."""
        packets_dir = (
            repo_root
            / "research"
            / "experiments"
            / "cross_perspective_advisory_ablation_v1"
            / "packets"
        )
        tcm_file = packets_dir / "tcm_packets.jsonl"
        western_file = packets_dir / "western_packets.jsonl"
        return cls.from_verified_formal_packets(tcm_file, western_file)

    @property
    def is_formal_verified(self) -> bool:
        """Diagnostic check: return True if index is a structurally verified formal index."""
        return type(self) is VerifiedFormalPacketAnchorIndex

    @property
    def packet_count(self) -> int:
        return len(self._packets)

    @property
    def evidence_item_count(self) -> int:
        return len(self._evidence_items)

    @property
    def questions(self) -> set[str]:
        return set(self._questions)

    @property
    def packets(self) -> MappingProxyType[str, PacketMetadata]:
        return MappingProxyType(self._packets)

    @property
    def evidence_items(self) -> MappingProxyType[tuple[str, str], EvidenceItemMetadata]:
        return MappingProxyType(self._evidence_items)

    @property
    def question_to_packets(self) -> MappingProxyType[str, Any]:
        return MappingProxyType(self._question_to_packets)

    @property
    def question_to_evidence_ids(self) -> MappingProxyType[str, Any]:
        return MappingProxyType(self._question_to_evidence_ids)

    def get_question_text(self, question_id: str) -> str:
        """Return question text for a question_id if available."""
        for pid in self.get_question_packet_ids(question_id).values():
            pkt = self.get_packet(pid)
            if pkt and pkt.question_text:
                return pkt.question_text
        return ""

    def get_question_topic(self, question_id: str) -> str:
        """Return topic for a question_id if available."""
        for pid in self.get_question_packet_ids(question_id).values():
            pkt = self.get_packet(pid)
            if pkt and pkt.topic:
                return pkt.topic
        return ""

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


class VerifiedFormalPacketAnchorIndex(FrozenPacketAnchorIndex):
    """Immutable, mechanically sealed index of formally verified study packets.

    THREAT MODEL:
    This seal protects against normal supported Python API misuse and ordinary
    attribute/item mutation in memory.
    It is NOT intended as a hostile same-process Python security sandbox against
    deliberate reflection, object.__setattr__, ctypes, debugger memory edits,
    or source-code modification.
    This is a reproducibility and formal integrity boundary, not a security boundary.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError(
            "VerifiedFormalPacketAnchorIndex is final and cannot be subclassed"
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError(
            "Direct public construction of VerifiedFormalPacketAnchorIndex is forbidden. "
            "Verified formal instances must be loaded through FrozenPacketAnchorIndex.from_repo_root() "
            "or FrozenPacketAnchorIndex.from_verified_formal_packets()."
        )

    @classmethod
    def from_packet_records(cls, *args: Any, **kwargs: Any) -> Any:
        raise TypeError(
            "VerifiedFormalPacketAnchorIndex cannot be constructed from raw packet records. "
            "Use FrozenPacketAnchorIndex.from_packet_records() for generic/synthetic fixtures."
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_is_sealed", False):
            raise AttributeError(
                f"Cannot mutate attribute '{name}' on sealed VerifiedFormalPacketAnchorIndex"
            )
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_is_sealed", False):
            raise AttributeError(
                f"Cannot delete attribute '{name}' on sealed VerifiedFormalPacketAnchorIndex"
            )
        super().__delattr__(name)


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
    mode: ValidationMode = "final_candidate",
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
    Raises ValueError immediately if mode is not in ('draft', 'final_candidate').
    """
    if mode not in ALLOWED_VALIDATION_MODES:
        raise ValueError(
            f"Unsupported validation mode: {mode!r}. Allowed modes are: {sorted(ALLOWED_VALIDATION_MODES)}"
        )

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

    # Perspective Scope and Relational Structural Rules (Task 10 & Section G line 154)
    pertinent_anchors = [
        a for a in rec_obj.evidence_anchors
        if a.anchor_role in ("supporting_span", "contrasting_span") and len(a.spans) > 0
    ]

    # Relational targets require pertinent evidence from BOTH streams (Section G line 154)
    if rec_obj.unit_type == "relationship":
        tcm_pertinent = [a for a in pertinent_anchors if a.perspective == "tcm"]
        western_pertinent = [a for a in pertinent_anchors if a.perspective == "western"]
        if not tcm_pertinent:
            errors.append(
                "unit_type='relationship' requires at least one pertinent supporting/contrasting anchor from TCM"
            )
        if not western_pertinent:
            errors.append(
                "unit_type='relationship' requires at least one pertinent supporting/contrasting anchor from Western"
            )

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
