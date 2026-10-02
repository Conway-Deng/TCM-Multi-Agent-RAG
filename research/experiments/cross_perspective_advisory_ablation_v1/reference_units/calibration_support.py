"""Mechanical Calibration Infrastructure for Human Reference-Unit Annotation.

Protocol Anchor: CPAA1-REFERENCE-UNIT-PROTOCOL-V1
Calibration Design ID: CPAA1-REFERENCE-UNIT-CALIBRATION-DESIGN-V1
Study ID: cross-perspective-advisory-ablation-v1

CRITICAL ARCHITECTURAL BOUNDARY:
This module contains ZERO semantic reference-unit automation, ZERO answer keys,
and ZERO final calibration fixture text.
Model-drafted case wording is NOT calibration material.
Final calibration text will be authored separately by a HUMAN.
This module implements only:
- design metadata and constants
- blank structures and fixture pack schema
- formal-material separation checks
- deterministic fixture pack and submission hashing
- reviewer workspace isolation and mechanical lock snapshotting
- A/B comparison gatekeeper
- disagreement log with strict Type-A / Type-B ambiguity handling
- fail-closed completion checklist and stop conditions
- strict current-state revalidation across all mutable objects
- one-way lock and freeze semantics
- sealed authority types and verified loaders
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Literal, Sequence

from .reference_unit_schema import (
    FROZEN_PROTOCOL_BYTE_SHA256,
    PROTOCOL_ID,
    STUDY_ID,
    ReferenceUnitRecord,
)
from .reference_unit_validation import (
    EvidenceItemMetadata,
    FrozenPacketAnchorIndex,
    PacketMetadata,
    validate_reference_unit_record,
)

# ==============================================================================
# CALIBRATION CONSTANTS / IDENTIFIERS (Task 2 & Phase 2C-C1 Seal)
# ==============================================================================

CALIBRATION_DESIGN_ID: Final[str] = "CPAA1-REFERENCE-UNIT-CALIBRATION-DESIGN-V1"

CALIBRATION_CASE_IDS: Final[tuple[str, ...]] = (
    "CAL-2CC-01",
    "CAL-2CC-02",
    "CAL-2CC-03",
    "CAL-2CC-04",
    "CAL-2CC-05",
    "CAL-2CC-06",
    "CAL-2CC-07",
    "CAL-2CC-08",
)

CALIBRATION_CASE_COVERAGE: Final[dict[str, tuple[str, ...]]] = {
    "CAL-2CC-01": ("indispensable qualifiers", "source-explicit support"),
    "CAL-2CC-02": ("decomposition", "limitation anti-double-counting"),
    "CAL-2CC-03": ("repeated evidence", "deduplication"),
    "CAL-2CC-04": ("cross-perspective agreement", "relational-versus-constituent counting", "cross-span synthesis"),
    "CAL-2CC-05": ("genuine cross-perspective conflict",),
    "CAL-2CC-06": ("non-comparability", "incompatible/unspecified scope"),
    "CAL-2CC-07": ("no relevant information", "packet-bounded absence", "scope audit"),
    "CAL-2CC-08": ("relevant but insufficient information", "distinguishing insufficient information from absence/conflict"),
}

CALIBRATION_PACKET_ID_PREFIX: Final[str] = "cal2cc:packet:"
CALIBRATION_EVIDENCE_ID_PREFIX: Final[str] = "cal2cc:ev:"

CALIBRATION_PACKET_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^cal2cc:packet:(CAL-2CC-0[1-8]):(tcm|western)$"
)
CALIBRATION_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^cal2cc:ev:(CAL-2CC-0[1-8]):(tcm|western):([1-4])$"
)

CALIBRATION_AUTHORSHIP_AMENDMENT_ID: Final[str] = (
    "CPAA1-CALIBRATION-FIXTURE-AUTHORSHIP-AMENDMENT-V1"
)
CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256: Final[str] = (
    "9de5635eaf62a6346789f7be1f291c0e88d6d8f8b3266daaa45a942a66c98dfa"
)

TextOrigin = Literal["human_authored", "ai_drafted_human_approved"]
ALLOWED_TEXT_ORIGINS: Final[set[str]] = {
    "human_authored",
    "ai_drafted_human_approved",
}

ALLOWED_REVIEWER_ROLES: Final[set[str]] = {"reviewer_a", "reviewer_b"}
ALLOWED_PERSPECTIVES: Final[set[str]] = {"tcm", "western"}
ALLOWED_AMBIGUITY_CLASSIFICATIONS: Final[set[str]] = {
    "A_CASE_LEVEL",
    "B_METHODOLOGICAL_AMBIGUITY",
}
ALLOWED_DISAGREEMENT_STATUSES: Final[set[str]] = {"open", "resolved"}

LOCAL_ONLY_NOTICE: Final[str] = (
    "LOCAL-ONLY CALIBRATION ARTIFACT — NOT FOR MODEL ACCESS OR PRODUCTION PACKET EMBEDDING"
)

# Private seal token for authoritative locked submission construction
_CALIBRATION_LOCKED_SUBMISSION_SEAL_TOKEN: Final[object] = object()


# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class CalibrationError(Exception):
    """Base error for calibration failures."""


class CalibrationGateError(CalibrationError):
    """Raised when a calibration mechanical or authority gate is violated."""


class CalibrationComparisonGateError(CalibrationError):
    """Raised when calibration comparison view is blocked prior to dual locked submissions."""


class CalibrationLockError(CalibrationError):
    """Raised when a calibration reviewer submission cannot be locked."""


class CalibrationCompletionError(CalibrationError):
    """Raised when calibration completion prerequisites or attestations are incomplete."""


class CalibrationStateError(CalibrationError):
    """Raised when invalid state or state transition is encountered."""


# ==============================================================================
# VALIDATION / HASHING HELPERS (Task 6 & 15)
# ==============================================================================

def canonical_json_dumps(obj: Any) -> str:
    """Format object as deterministic canonical JSON text matching CPAA1 standard.

    Uses sort_keys=True, compact separators=(',', ':'), ensure_ascii=False, allow_nan=False.
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def compute_canonical_sha256(obj: Any) -> str:
    """Compute deterministic SHA256 of canonical JSON text encoded in UTF-8."""
    canonical_text = canonical_json_dumps(obj)
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def _require_bool(value: Any, field_name: str) -> bool:
    """Fail-closed validator enforcing that value is an actual bool instance."""
    if type(value) is not bool:
        raise TypeError(
            f"Field '{field_name}' must be of type bool, got {type(value).__name__} ({value!r})"
        )
    return value


def _require_non_empty_str(value: Any, field_name: str) -> str:
    """Fail-closed validator enforcing that value is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Field '{field_name}' must be a non-empty string, got {value!r}"
        )
    return value


def _require_sha256_hex(value: Any, field_name: str) -> str:
    """Fail-closed validator enforcing that value is a 64-character lowercase hex string."""
    if not isinstance(value, str) or len(value) != 64 or not all(c in "0123456789abcdef" for c in value.lower()):
        raise ValueError(
            f"Field '{field_name}' must be a 64-character SHA256 hex string, got {value!r}"
        )
    return value


# ==============================================================================
# FORMAL-MATERIAL SEPARATION CHECK (Task 5 & Part O)
# ==============================================================================

def check_formal_material_separation(
    case_ids: Sequence[str] = (),
    packet_ids: Sequence[str] = (),
    evidence_ids: Sequence[str] = (),
    question_texts: Sequence[str] = (),
) -> None:
    """Mechanically verify that calibration items do not reuse formal study identifiers or text."""
    for pid in packet_ids:
        if (
            pid.startswith("cpaa1:packet:")
            or pid.startswith("packet:tcm:")
            or pid.startswith("packet:western:")
        ):
            raise CalibrationGateError(f"Packet ID '{pid}' reuses formal packet prefix")

    for eid in evidence_ids:
        if (
            eid.startswith("cpaa1:ev:")
            or eid.startswith("ev:tcm:")
            or eid.startswith("ev:western:")
        ):
            raise CalibrationGateError(f"Evidence ID '{eid}' reuses formal evidence prefix")

    for cid in case_ids:
        if cid not in CALIBRATION_CASE_IDS:
            raise CalibrationGateError(f"Case ID '{cid}' is not an approved CAL-2CC case ID")
        if cid.startswith("syn_") or cid.startswith("cpaa1:"):
            raise CalibrationGateError(f"Case ID '{cid}' reuses formal/synthetic study prefix")

    # Formal question manifest check
    q_manifest_path = Path(__file__).resolve().parent.parent / "question_manifest.jsonl"
    if q_manifest_path.exists():
        try:
            lines = [l.strip() for l in q_manifest_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            formal_q_texts = set()
            formal_q_ids = set()
            for line in lines:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    if "question_text" in obj and isinstance(obj["question_text"], str):
                        formal_q_texts.add(obj["question_text"])
                    if "question_id" in obj and isinstance(obj["question_id"], str):
                        formal_q_ids.add(obj["question_id"])
            for cid in case_ids:
                if cid in formal_q_ids:
                    raise CalibrationGateError(f"Calibration case_id '{cid}' matches formal study question ID")
            for qt in question_texts:
                if qt in formal_q_texts:
                    raise CalibrationGateError(
                        "Calibration question text matches formal study question text exactly"
                    )
        except CalibrationGateError:
            raise
        except Exception as e:
            raise CalibrationGateError(f"Failed to read/parse formal question manifest at {q_manifest_path}: {e}") from e

    # Formal packet manifest check
    p_manifest_path = Path(__file__).resolve().parent.parent / "packets" / "packet_manifest.json"
    if p_manifest_path.exists():
        try:
            p_data = json.loads(p_manifest_path.read_text(encoding="utf-8"))
            if not isinstance(p_data, dict):
                raise CalibrationGateError(f"Formal packet manifest at {p_manifest_path} must be a JSON dict")
        except CalibrationGateError:
            raise
        except Exception as e:
            raise CalibrationGateError(f"Failed to read/parse formal packet manifest at {p_manifest_path}: {e}") from e


# ==============================================================================
# HUMAN-AUTHORED FIXTURE PACK SCHEMA (Task 3, 4, 6 & Part B)
# ==============================================================================

@dataclass
class CalibrationEvidenceItem:
    """Individual synthetic evidence item in a calibration packet."""

    evidence_id: str
    rank: int
    exact_chunk_text: str
    chunk_text_sha256: str
    provenance: str = ""
    source_title: str = ""
    source_url: str = ""
    section_or_category: str = ""
    doi: str = ""
    pmcid: str = ""

    def validate_current_state(self) -> None:
        if type(self.rank) is not int or self.rank < 1 or self.rank > 4:
            raise ValueError(f"rank must be an integer between 1 and 4, got {self.rank!r}")
        _require_non_empty_str(self.evidence_id, "evidence_id")
        if (
            self.evidence_id.startswith("cpaa1:ev:")
            or self.evidence_id.startswith("ev:tcm:")
            or self.evidence_id.startswith("ev:western:")
        ):
            raise CalibrationGateError(f"Calibration evidence_id '{self.evidence_id}' reuses formal evidence prefix")

        m = CALIBRATION_EVIDENCE_ID_PATTERN.match(self.evidence_id)
        if not m:
            raise CalibrationGateError(
                f"evidence_id '{self.evidence_id}' does not match required format 'cal2cc:ev:CAL-2CC-XX:<perspective>:<rank>' "
                f"(must start with '{CALIBRATION_EVIDENCE_ID_PREFIX}')"
            )
        cid_part, persp_part, rank_part = m.group(1), m.group(2), int(m.group(3))
        if self.rank != rank_part:
            raise CalibrationGateError(
                f"evidence_id rank '{rank_part}' does not match item.rank '{self.rank}'"
            )

        _require_non_empty_str(self.exact_chunk_text, "exact_chunk_text")
        expected_sha = hashlib.sha256(self.exact_chunk_text.encode("utf-8")).hexdigest()
        if self.chunk_text_sha256 != expected_sha:
            raise ValueError(
                f"chunk_text_sha256 mismatch for '{self.evidence_id}': "
                f"expected '{expected_sha}', got '{self.chunk_text_sha256}'"
            )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "evidence_id": self.evidence_id,
            "rank": self.rank,
            "exact_chunk_text": self.exact_chunk_text,
            "chunk_text_sha256": self.chunk_text_sha256,
            "provenance": self.provenance,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "section_or_category": self.section_or_category,
            "doi": self.doi,
            "pmcid": self.pmcid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationEvidenceItem:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationEvidenceItem")
        return cls(
            evidence_id=data.get("evidence_id", ""),
            rank=data.get("rank", 0),
            exact_chunk_text=data.get("exact_chunk_text", ""),
            chunk_text_sha256=data.get("chunk_text_sha256", ""),
            provenance=data.get("provenance", ""),
            source_title=data.get("source_title", ""),
            source_url=data.get("source_url", ""),
            section_or_category=data.get("section_or_category", ""),
            doi=data.get("doi", ""),
            pmcid=data.get("pmcid", ""),
        )


@dataclass
class CalibrationPacket:
    """Perspective-specific calibration packet containing exactly 4 evidence items."""

    packet_id: str
    perspective: Literal["tcm", "western"]
    case_id: str
    evidence_items: list[CalibrationEvidenceItem] = field(default_factory=list)

    def validate_current_state(self) -> None:
        _require_non_empty_str(self.packet_id, "packet_id")
        if (
            self.packet_id.startswith("cpaa1:packet:")
            or self.packet_id.startswith("packet:tcm:")
            or self.packet_id.startswith("packet:western:")
        ):
            raise CalibrationGateError(f"Calibration packet_id '{self.packet_id}' reuses formal packet prefix")
        if self.perspective not in ALLOWED_PERSPECTIVES:
            raise ValueError(f"Invalid perspective '{self.perspective}': must be 'tcm' or 'western'")
        if self.case_id not in CALIBRATION_CASE_IDS:
            raise ValueError(f"Invalid case_id '{self.case_id}': must be one of {CALIBRATION_CASE_IDS}")

        expected_pkt_id = f"cal2cc:packet:{self.case_id}:{self.perspective}"
        if self.packet_id != expected_pkt_id:
            raise CalibrationGateError(
                f"packet_id '{self.packet_id}' does not match expected exact format '{expected_pkt_id}' "
                f"(must start with '{CALIBRATION_PACKET_ID_PREFIX}')"
            )

        if not isinstance(self.evidence_items, list):
            raise TypeError("evidence_items must be a list")
        if len(self.evidence_items) != 4:
            raise ValueError(f"Packet must contain exactly 4 evidence items, got {len(self.evidence_items)}")

        ranks: list[int] = []
        eids: set[str] = set()
        for item in self.evidence_items:
            if not isinstance(item, CalibrationEvidenceItem):
                raise TypeError(f"Expected CalibrationEvidenceItem, got {type(item).__name__}")
            item.validate_current_state()
            if item.rank in ranks:
                raise ValueError(f"Duplicate rank {item.rank} in packet {self.packet_id}")
            ranks.append(item.rank)
            expected_eid = f"cal2cc:ev:{self.case_id}:{self.perspective}:{item.rank}"
            if item.evidence_id != expected_eid:
                raise CalibrationGateError(
                    f"packet '{self.packet_id}' evidence_id '{item.evidence_id}' does not match expected exact format '{expected_eid}'"
                )
            if item.evidence_id in eids:
                raise CalibrationGateError(f"Duplicate evidence_id '{item.evidence_id}' in packet '{self.packet_id}'")
            eids.add(item.evidence_id)

        if sorted(ranks) != [1, 2, 3, 4]:
            raise ValueError(f"evidence_items ranks must be [1, 2, 3, 4] with no duplicates, got {sorted(ranks)}")

    def __post_init__(self) -> None:
        self.validate_current_state()

    def compute_canonical_sha256(self, question_text: str = "", topic: str = "calibration_case") -> str:
        d = {
            "packet_id": self.packet_id,
            "question_id": self.case_id,
            "perspective": self.perspective,
            "question_text": question_text,
            "topic": topic,
            "evidence_items": [item.to_dict() for item in self.evidence_items],
        }
        return compute_canonical_sha256(d)

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "packet_id": self.packet_id,
            "perspective": self.perspective,
            "case_id": self.case_id,
            "evidence_items": [item.to_dict() for item in self.evidence_items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationPacket:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationPacket")
        items_raw = data.get("evidence_items", [])
        if not isinstance(items_raw, list):
            raise TypeError("evidence_items must be a list")
        return cls(
            packet_id=data.get("packet_id", ""),
            perspective=data.get("perspective", "tcm"),
            case_id=data.get("case_id", ""),
            evidence_items=[CalibrationEvidenceItem.from_dict(it) for it in items_raw],
        )


@dataclass
class CalibrationCase:
    """One of the 8 calibration challenge cases with dual TCM/Western packets."""

    calibration_case_id: str
    question_text: str
    tcm_packet: CalibrationPacket
    western_packet: CalibrationPacket

    def validate_current_state(self) -> None:
        if self.calibration_case_id not in CALIBRATION_CASE_IDS:
            raise ValueError(
                f"Invalid calibration_case_id '{self.calibration_case_id}': must be one of {CALIBRATION_CASE_IDS}"
            )
        _require_non_empty_str(self.question_text, "question_text")
        if not isinstance(self.tcm_packet, CalibrationPacket):
            raise TypeError("tcm_packet must be a CalibrationPacket")
        if not isinstance(self.western_packet, CalibrationPacket):
            raise TypeError("western_packet must be a CalibrationPacket")
        self.tcm_packet.validate_current_state()
        self.western_packet.validate_current_state()
        if self.tcm_packet.perspective != "tcm":
            raise ValueError(f"tcm_packet perspective must be 'tcm', got '{self.tcm_packet.perspective}'")
        if self.western_packet.perspective != "western":
            raise ValueError(f"western_packet perspective must be 'western', got '{self.western_packet.perspective}'")
        if self.tcm_packet.case_id != self.calibration_case_id:
            raise ValueError(
                f"tcm_packet case_id '{self.tcm_packet.case_id}' does not match case '{self.calibration_case_id}'"
            )
        if self.western_packet.case_id != self.calibration_case_id:
            raise ValueError(
                f"western_packet case_id '{self.western_packet.case_id}' does not match case '{self.calibration_case_id}'"
            )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def compute_case_content_sha256(self) -> str:
        d = {
            "calibration_case_id": self.calibration_case_id,
            "question_text": self.question_text,
            "tcm_packet": self.tcm_packet.to_dict(),
            "western_packet": self.western_packet.to_dict(),
        }
        return compute_canonical_sha256(d)

    def to_reviewer_facing_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "case_id": self.calibration_case_id,
            "question_text": self.question_text,
            "tcm_packet": self.tcm_packet.to_dict(),
            "western_packet": self.western_packet.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "calibration_case_id": self.calibration_case_id,
            "question_text": self.question_text,
            "tcm_packet": self.tcm_packet.to_dict(),
            "western_packet": self.western_packet.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationCase:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationCase")
        tcm_data = data.get("tcm_packet")
        western_data = data.get("western_packet")
        if not isinstance(tcm_data, dict) or not isinstance(western_data, dict):
            raise TypeError("tcm_packet and western_packet must be dictionaries")
        return cls(
            calibration_case_id=data.get("calibration_case_id", ""),
            question_text=data.get("question_text", ""),
            tcm_packet=CalibrationPacket.from_dict(tcm_data),
            western_packet=CalibrationPacket.from_dict(western_data),
        )


@dataclass
class CalibrationAiDraftProvenance:
    """Provenance record for AI-drafted calibration case candidate text."""

    amendment_id: str
    amendment_byte_sha256: str
    model_provider: str
    model_identifier: str
    drafting_date: str
    drafting_prompt_sha256: str
    raw_draft_sha256: str
    human_edited_after_ai_draft: bool
    human_editor: str
    fixture_content_canonical_sha256: str

    def validate_current_state(self) -> None:
        if self.amendment_id != CALIBRATION_AUTHORSHIP_AMENDMENT_ID:
            raise CalibrationGateError(
                f"amendment_id mismatch: '{self.amendment_id}' != '{CALIBRATION_AUTHORSHIP_AMENDMENT_ID}'"
            )
        if self.amendment_byte_sha256 != CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256:
            raise CalibrationGateError(
                f"amendment_byte_sha256 mismatch: '{self.amendment_byte_sha256}' != '{CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256}'"
            )
        _require_non_empty_str(self.model_provider, "model_provider")
        _require_non_empty_str(self.model_identifier, "model_identifier")
        _require_non_empty_str(self.drafting_date, "drafting_date")
        _require_sha256_hex(self.drafting_prompt_sha256, "drafting_prompt_sha256")
        _require_sha256_hex(self.raw_draft_sha256, "raw_draft_sha256")
        _require_bool(self.human_edited_after_ai_draft, "human_edited_after_ai_draft")
        _require_non_empty_str(self.human_editor, "human_editor")
        _require_sha256_hex(self.fixture_content_canonical_sha256, "fixture_content_canonical_sha256")

    def __post_init__(self) -> None:
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "amendment_id": self.amendment_id,
            "amendment_byte_sha256": self.amendment_byte_sha256,
            "model_provider": self.model_provider,
            "model_identifier": self.model_identifier,
            "drafting_date": self.drafting_date,
            "drafting_prompt_sha256": self.drafting_prompt_sha256,
            "raw_draft_sha256": self.raw_draft_sha256,
            "human_edited_after_ai_draft": self.human_edited_after_ai_draft,
            "human_editor": self.human_editor,
            "fixture_content_canonical_sha256": self.fixture_content_canonical_sha256,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationAiDraftProvenance:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationAiDraftProvenance")
        return cls(
            amendment_id=data.get("amendment_id", ""),
            amendment_byte_sha256=data.get("amendment_byte_sha256", ""),
            model_provider=data.get("model_provider", ""),
            model_identifier=data.get("model_identifier", ""),
            drafting_date=data.get("drafting_date", ""),
            drafting_prompt_sha256=data.get("drafting_prompt_sha256", ""),
            raw_draft_sha256=data.get("raw_draft_sha256", ""),
            human_edited_after_ai_draft=data.get("human_edited_after_ai_draft", False),
            human_editor=data.get("human_editor", ""),
            fixture_content_canonical_sha256=data.get("fixture_content_canonical_sha256", ""),
        )


@dataclass
class CalibrationCaseApproval:
    """Human review and approval record for an individual calibration challenge case."""

    amendment_id: str
    amendment_byte_sha256: str
    case_id: str
    case_content_sha256: str
    approver_identity: str
    approver_role: str
    review_date: str
    decision: Literal["approved", "rejected"]
    human_edited_after_ai_draft: bool
    wording_acceptable_attested: bool
    assigned_boundary_present_attested: bool
    fictional_nonmedical_attested: bool
    formal_material_not_used_attested: bool
    no_answer_key_attested: bool
    no_proposed_reference_units_attested: bool
    no_semantic_labels_attested: bool
    no_expected_unit_count_attested: bool
    approval_notes: str = ""

    def validate_current_state(self) -> None:
        if self.amendment_id != CALIBRATION_AUTHORSHIP_AMENDMENT_ID:
            raise CalibrationGateError(
                f"amendment_id mismatch: '{self.amendment_id}' != '{CALIBRATION_AUTHORSHIP_AMENDMENT_ID}'"
            )
        if self.amendment_byte_sha256 != CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256:
            raise CalibrationGateError(
                f"amendment_byte_sha256 mismatch: '{self.amendment_byte_sha256}' != '{CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256}'"
            )
        if self.case_id not in CALIBRATION_CASE_IDS:
            raise ValueError(f"case_id '{self.case_id}' must be one of {CALIBRATION_CASE_IDS}")
        _require_sha256_hex(self.case_content_sha256, "case_content_sha256")
        _require_non_empty_str(self.approver_identity, "approver_identity")
        _require_non_empty_str(self.approver_role, "approver_role")
        _require_non_empty_str(self.review_date, "review_date")
        if self.decision not in ("approved", "rejected"):
            raise ValueError(f"decision must be 'approved' or 'rejected', got '{self.decision}'")
        _require_bool(self.human_edited_after_ai_draft, "human_edited_after_ai_draft")
        _require_bool(self.wording_acceptable_attested, "wording_acceptable_attested")
        _require_bool(self.assigned_boundary_present_attested, "assigned_boundary_present_attested")
        _require_bool(self.fictional_nonmedical_attested, "fictional_nonmedical_attested")
        _require_bool(self.formal_material_not_used_attested, "formal_material_not_used_attested")
        _require_bool(self.no_answer_key_attested, "no_answer_key_attested")
        _require_bool(self.no_proposed_reference_units_attested, "no_proposed_reference_units_attested")
        _require_bool(self.no_semantic_labels_attested, "no_semantic_labels_attested")
        _require_bool(self.no_expected_unit_count_attested, "no_expected_unit_count_attested")

        if self.decision == "approved":
            attestation_map = {
                "wording_acceptable_attested": self.wording_acceptable_attested,
                "assigned_boundary_present_attested": self.assigned_boundary_present_attested,
                "fictional_nonmedical_attested": self.fictional_nonmedical_attested,
                "formal_material_not_used_attested": self.formal_material_not_used_attested,
                "no_answer_key_attested": self.no_answer_key_attested,
                "no_proposed_reference_units_attested": self.no_proposed_reference_units_attested,
                "no_semantic_labels_attested": self.no_semantic_labels_attested,
                "no_expected_unit_count_attested": self.no_expected_unit_count_attested,
            }
            for att_name, att_val in attestation_map.items():
                if att_val is not True:
                    raise CalibrationGateError(
                        f"Case '{self.case_id}' approval decision is 'approved' but '{att_name}' is False"
                    )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "amendment_id": self.amendment_id,
            "amendment_byte_sha256": self.amendment_byte_sha256,
            "case_id": self.case_id,
            "case_content_sha256": self.case_content_sha256,
            "approver_identity": self.approver_identity,
            "approver_role": self.approver_role,
            "review_date": self.review_date,
            "decision": self.decision,
            "human_edited_after_ai_draft": self.human_edited_after_ai_draft,
            "wording_acceptable_attested": self.wording_acceptable_attested,
            "assigned_boundary_present_attested": self.assigned_boundary_present_attested,
            "fictional_nonmedical_attested": self.fictional_nonmedical_attested,
            "formal_material_not_used_attested": self.formal_material_not_used_attested,
            "no_answer_key_attested": self.no_answer_key_attested,
            "no_proposed_reference_units_attested": self.no_proposed_reference_units_attested,
            "no_semantic_labels_attested": self.no_semantic_labels_attested,
            "no_expected_unit_count_attested": self.no_expected_unit_count_attested,
            "approval_notes": self.approval_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationCaseApproval:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationCaseApproval")
        return cls(
            amendment_id=data.get("amendment_id", ""),
            amendment_byte_sha256=data.get("amendment_byte_sha256", ""),
            case_id=data.get("case_id", ""),
            case_content_sha256=data.get("case_content_sha256", ""),
            approver_identity=data.get("approver_identity", ""),
            approver_role=data.get("approver_role", ""),
            review_date=data.get("review_date", ""),
            decision=data.get("decision", "rejected"),
            human_edited_after_ai_draft=data.get("human_edited_after_ai_draft", False),
            wording_acceptable_attested=data.get("wording_acceptable_attested", False),
            assigned_boundary_present_attested=data.get("assigned_boundary_present_attested", False),
            fictional_nonmedical_attested=data.get("fictional_nonmedical_attested", False),
            formal_material_not_used_attested=data.get("formal_material_not_used_attested", False),
            no_answer_key_attested=data.get("no_answer_key_attested", False),
            no_proposed_reference_units_attested=data.get("no_proposed_reference_units_attested", False),
            no_semantic_labels_attested=data.get("no_semantic_labels_attested", False),
            no_expected_unit_count_attested=data.get("no_expected_unit_count_attested", False),
            approval_notes=data.get("approval_notes", ""),
        )


@dataclass
class CalibrationPackApproval:
    """Pack-level human review and approval record for AI-drafted calibration fixture pack."""

    amendment_id: str
    amendment_byte_sha256: str
    fixture_content_canonical_sha256: str
    approver_identity: str
    approver_role: str
    review_date: str
    all_eight_case_approvals_present_and_approved: bool
    exact_final_wording_reviewed: bool
    boundary_matrix_covered_attested: bool
    content_fictional_nonmedical_attested: bool
    formal_material_not_used_attested: bool
    no_answer_key_or_expected_units_embedded: bool
    pack_acceptable_for_reviewer_calibration: bool
    reviewer_material_blinding_verified: bool
    pack_approval_notes: str = ""

    def validate_current_state(self) -> None:
        if self.amendment_id != CALIBRATION_AUTHORSHIP_AMENDMENT_ID:
            raise CalibrationGateError(
                f"amendment_id mismatch: '{self.amendment_id}' != '{CALIBRATION_AUTHORSHIP_AMENDMENT_ID}'"
            )
        if self.amendment_byte_sha256 != CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256:
            raise CalibrationGateError(
                f"amendment_byte_sha256 mismatch: '{self.amendment_byte_sha256}' != '{CALIBRATION_AUTHORSHIP_AMENDMENT_BYTE_SHA256}'"
            )
        _require_sha256_hex(self.fixture_content_canonical_sha256, "fixture_content_canonical_sha256")
        _require_non_empty_str(self.approver_identity, "approver_identity")
        _require_non_empty_str(self.approver_role, "approver_role")
        _require_non_empty_str(self.review_date, "review_date")

        _require_bool(
            self.all_eight_case_approvals_present_and_approved,
            "all_eight_case_approvals_present_and_approved",
        )
        _require_bool(self.exact_final_wording_reviewed, "exact_final_wording_reviewed")
        _require_bool(
            self.boundary_matrix_covered_attested,
            "boundary_matrix_covered_attested",
        )
        _require_bool(
            self.content_fictional_nonmedical_attested,
            "content_fictional_nonmedical_attested",
        )
        _require_bool(
            self.formal_material_not_used_attested,
            "formal_material_not_used_attested",
        )
        _require_bool(
            self.no_answer_key_or_expected_units_embedded,
            "no_answer_key_or_expected_units_embedded",
        )
        _require_bool(
            self.pack_acceptable_for_reviewer_calibration,
            "pack_acceptable_for_reviewer_calibration",
        )
        _require_bool(
            self.reviewer_material_blinding_verified,
            "reviewer_material_blinding_verified",
        )

        attestation_map = {
            "all_eight_case_approvals_present_and_approved": self.all_eight_case_approvals_present_and_approved,
            "exact_final_wording_reviewed": self.exact_final_wording_reviewed,
            "boundary_matrix_covered_attested": self.boundary_matrix_covered_attested,
            "content_fictional_nonmedical_attested": self.content_fictional_nonmedical_attested,
            "formal_material_not_used_attested": self.formal_material_not_used_attested,
            "no_answer_key_or_expected_units_embedded": self.no_answer_key_or_expected_units_embedded,
            "pack_acceptable_for_reviewer_calibration": self.pack_acceptable_for_reviewer_calibration,
            "reviewer_material_blinding_verified": self.reviewer_material_blinding_verified,
        }
        for att_name, att_val in attestation_map.items():
            if att_val is not True:
                raise CalibrationGateError(f"Pack approval attestation '{att_name}' must be True")

    def __post_init__(self) -> None:
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "amendment_id": self.amendment_id,
            "amendment_byte_sha256": self.amendment_byte_sha256,
            "fixture_content_canonical_sha256": self.fixture_content_canonical_sha256,
            "approver_identity": self.approver_identity,
            "approver_role": self.approver_role,
            "review_date": self.review_date,
            "all_eight_case_approvals_present_and_approved": self.all_eight_case_approvals_present_and_approved,
            "exact_final_wording_reviewed": self.exact_final_wording_reviewed,
            "boundary_matrix_covered_attested": self.boundary_matrix_covered_attested,
            "content_fictional_nonmedical_attested": self.content_fictional_nonmedical_attested,
            "formal_material_not_used_attested": self.formal_material_not_used_attested,
            "no_answer_key_or_expected_units_embedded": self.no_answer_key_or_expected_units_embedded,
            "pack_acceptable_for_reviewer_calibration": self.pack_acceptable_for_reviewer_calibration,
            "reviewer_material_blinding_verified": self.reviewer_material_blinding_verified,
            "pack_approval_notes": self.pack_approval_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationPackApproval:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationPackApproval")
        return cls(
            amendment_id=data.get("amendment_id", ""),
            amendment_byte_sha256=data.get("amendment_byte_sha256", ""),
            fixture_content_canonical_sha256=data.get("fixture_content_canonical_sha256", ""),
            approver_identity=data.get("approver_identity", ""),
            approver_role=data.get("approver_role", ""),
            review_date=data.get("review_date", ""),
            all_eight_case_approvals_present_and_approved=data.get(
                "all_eight_case_approvals_present_and_approved", False
            ),
            exact_final_wording_reviewed=data.get("exact_final_wording_reviewed", False),
            boundary_matrix_covered_attested=data.get("boundary_matrix_covered_attested", False),
            content_fictional_nonmedical_attested=data.get(
                "content_fictional_nonmedical_attested", False
            ),
            formal_material_not_used_attested=data.get("formal_material_not_used_attested", False),
            no_answer_key_or_expected_units_embedded=data.get(
                "no_answer_key_or_expected_units_embedded", False
            ),
            pack_acceptable_for_reviewer_calibration=data.get(
                "pack_acceptable_for_reviewer_calibration", False
            ),
            reviewer_material_blinding_verified=data.get(
                "reviewer_material_blinding_verified", False
            ),
            pack_approval_notes=data.get("pack_approval_notes", ""),
        )


@dataclass
class CalibrationFixturePack:
    """Fixture pack containing exactly 8 calibration challenge cases."""

    fixture_author: str
    human_authorship_attested: bool
    formal_material_not_used_attested: bool
    model_generated_final_fixture_text: bool
    cases: dict[str, CalibrationCase]
    text_origin: TextOrigin = "human_authored"
    ai_draft_provenance: CalibrationAiDraftProvenance | None = None
    case_approvals: dict[str, CalibrationCaseApproval] | None = None
    pack_approval: CalibrationPackApproval | None = None
    calibration_design_id: str = CALIBRATION_DESIGN_ID
    study_id: str = STUDY_ID
    protocol_id: str = PROTOCOL_ID
    protocol_hash: str = FROZEN_PROTOCOL_BYTE_SHA256
    fixture_content_canonical_sha256: str | None = None
    fixture_pack_canonical_sha256: str | None = None

    def compute_fixture_content_sha256(self) -> str:
        d = {
            "study_id": self.study_id,
            "calibration_design_id": self.calibration_design_id,
            "cases": {
                cid: {
                    "calibration_case_id": case.calibration_case_id,
                    "question_text": case.question_text,
                    "tcm_packet": case.tcm_packet.to_dict(),
                    "western_packet": case.western_packet.to_dict(),
                }
                for cid, case in sorted(self.cases.items())
            },
        }
        return compute_canonical_sha256(d)

    def to_reviewer_facing_dict(self) -> dict[str, Any]:
        """Reviewer-facing representation containing only case ID, question, and evidence."""
        self.validate_current_state()
        return {
            "calibration_design_id": self.calibration_design_id,
            "fixture_pack_canonical_sha256": self.fixture_pack_canonical_sha256,
            "cases": {
                cid: case.to_reviewer_facing_dict()
                for cid, case in sorted(self.cases.items())
            },
        }

    def validate_current_state(self) -> None:
        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )
        if self.study_id != STUDY_ID:
            raise ValueError(f"study_id mismatch: '{self.study_id}' != '{STUDY_ID}'")
        if self.protocol_id != PROTOCOL_ID:
            raise ValueError(f"protocol_id mismatch: '{self.protocol_id}' != '{PROTOCOL_ID}'")
        if self.protocol_hash != FROZEN_PROTOCOL_BYTE_SHA256:
            raise ValueError(f"protocol_hash mismatch: '{self.protocol_hash}' != '{FROZEN_PROTOCOL_BYTE_SHA256}'")

        if not isinstance(self.fixture_author, str):
            raise TypeError(f"fixture_author must be a str, got {type(self.fixture_author).__name__}")
        _require_non_empty_str(self.fixture_author, "fixture_author")
        _require_bool(self.human_authorship_attested, "human_authorship_attested")
        _require_bool(self.formal_material_not_used_attested, "formal_material_not_used_attested")
        _require_bool(self.model_generated_final_fixture_text, "model_generated_final_fixture_text")

        if self.text_origin not in ALLOWED_TEXT_ORIGINS:
            raise ValueError(f"Invalid text_origin '{self.text_origin}': must be one of {ALLOWED_TEXT_ORIGINS}")

        if not isinstance(self.cases, dict):
            raise TypeError("cases must be a dictionary")

        if tuple(sorted(self.cases.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
            raise ValueError(
                f"CalibrationFixturePack must contain exactly the 8 planned case IDs {CALIBRATION_CASE_IDS}, "
                f"got {tuple(sorted(self.cases.keys()))}"
            )

        packet_ids: list[str] = []
        evidence_ids: list[str] = []
        question_texts: list[str] = []

        for cid, case in self.cases.items():
            if not isinstance(case, CalibrationCase):
                raise TypeError(f"Expected CalibrationCase for key '{cid}', got {type(case).__name__}")
            if cid != case.calibration_case_id:
                raise ValueError(f"Key '{cid}' does not match case.calibration_case_id '{case.calibration_case_id}'")
            case.validate_current_state()
            question_texts.append(case.question_text)
            packet_ids.extend([case.tcm_packet.packet_id, case.western_packet.packet_id])
            for ev in case.tcm_packet.evidence_items + case.western_packet.evidence_items:
                evidence_ids.append(ev.evidence_id)

        if len(packet_ids) != 16:
            raise ValueError(f"Expected 16 packets, got {len(packet_ids)}")
        if len(evidence_ids) != 64:
            raise ValueError(f"Expected 64 evidence items, got {len(evidence_ids)}")

        # Uniqueness checks across the full fixture pack
        if len(set(packet_ids)) != 16:
            raise CalibrationGateError("Duplicate packet_id detected in fixture pack")
        if len(set(evidence_ids)) != 64:
            raise CalibrationGateError("Duplicate evidence_id detected across fixture pack")

        # Formal material separation check (Task 5 & Part O)
        check_formal_material_separation(
            case_ids=list(self.cases.keys()),
            packet_ids=packet_ids,
            evidence_ids=evidence_ids,
            question_texts=question_texts,
        )

        # Integrity checks when frozen or content hash is populated
        expected_content_hash = self.compute_fixture_content_sha256()
        if self.fixture_content_canonical_sha256 is not None:
            if self.fixture_content_canonical_sha256 != expected_content_hash:
                raise ValueError(
                    f"fixture_content_canonical_sha256 mismatch: recorded '{self.fixture_content_canonical_sha256}' "
                    f"!= computed '{expected_content_hash}'"
                )

        if self.fixture_pack_canonical_sha256 is not None:
            if self.fixture_content_canonical_sha256 is None:
                raise CalibrationGateError("Frozen fixture pack must have fixture_content_canonical_sha256")
            if not self.formal_material_not_used_attested:
                raise CalibrationGateError("formal_material_not_used_attested must be True for calibration fixture freeze")

            if self.text_origin == "human_authored":
                if not self.human_authorship_attested:
                    raise CalibrationGateError("human_authorship_attested must be True for human-authored fixture freeze")
                if self.model_generated_final_fixture_text is not False:
                    raise CalibrationGateError(
                        "model_generated_final_fixture_text must be False; model text cannot be frozen as human-authored"
                    )
            elif self.text_origin == "ai_drafted_human_approved":
                if self.human_authorship_attested is not False:
                    raise CalibrationGateError(
                        "human_authorship_attested must be False for AI-drafted fixture pack; cannot falsely claim human authorship"
                    )
                if self.model_generated_final_fixture_text is not True:
                    raise CalibrationGateError(
                        "model_generated_final_fixture_text must be True for AI-drafted fixture pack"
                    )

                if self.ai_draft_provenance is None:
                    raise CalibrationGateError("ai_draft_provenance is required for frozen ai_drafted_human_approved pack")
                self.ai_draft_provenance.validate_current_state()
                if self.ai_draft_provenance.fixture_content_canonical_sha256 != expected_content_hash:
                    raise CalibrationGateError("ai_draft_provenance fixture_content_canonical_sha256 mismatch")

                if not isinstance(self.case_approvals, dict):
                    raise CalibrationGateError("case_approvals required for frozen ai_drafted_human_approved pack")
                if tuple(sorted(self.case_approvals.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
                    raise CalibrationGateError("case_approvals must contain all 8 cases")
                for cid in CALIBRATION_CASE_IDS:
                    app = self.case_approvals.get(cid)
                    if not isinstance(app, CalibrationCaseApproval):
                        raise CalibrationGateError(f"case_approvals['{cid}'] must be CalibrationCaseApproval")
                    app.validate_current_state()
                    if app.decision != "approved":
                        raise CalibrationGateError(f"Case '{cid}' approval decision must be 'approved'")
                    if app.case_content_sha256 != self.cases[cid].compute_case_content_sha256():
                        raise CalibrationGateError(f"Case '{cid}' approval case_content_sha256 mismatch")

                if self.pack_approval is None:
                    raise CalibrationGateError("pack_approval is required for frozen ai_drafted_human_approved pack")
                self.pack_approval.validate_current_state()
                if self.pack_approval.fixture_content_canonical_sha256 != expected_content_hash:
                    raise CalibrationGateError("pack_approval fixture_content_canonical_sha256 mismatch")

            expected_hash = self.compute_canonical_sha256()
            if self.fixture_pack_canonical_sha256 != expected_hash:
                raise ValueError(
                    f"fixture_pack_canonical_sha256 mismatch: recorded '{self.fixture_pack_canonical_sha256}' "
                    f"!= computed '{expected_hash}'"
                )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def _to_dict_unhashed(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "calibration_design_id": self.calibration_design_id,
            "study_id": self.study_id,
            "protocol_id": self.protocol_id,
            "protocol_hash": self.protocol_hash,
            "fixture_author": self.fixture_author,
            "text_origin": self.text_origin,
            "human_authorship_attested": self.human_authorship_attested,
            "formal_material_not_used_attested": self.formal_material_not_used_attested,
            "model_generated_final_fixture_text": self.model_generated_final_fixture_text,
            "fixture_content_canonical_sha256": self.fixture_content_canonical_sha256,
            "cases": {cid: case.to_dict() for cid, case in sorted(self.cases.items())},
        }
        if self.ai_draft_provenance is not None:
            data["ai_draft_provenance"] = self.ai_draft_provenance.to_dict()
        else:
            data["ai_draft_provenance"] = None

        if self.case_approvals is not None:
            data["case_approvals"] = {
                cid: app.to_dict() for cid, app in sorted(self.case_approvals.items())
            }
        else:
            data["case_approvals"] = None

        if self.pack_approval is not None:
            data["pack_approval"] = self.pack_approval.to_dict()
        else:
            data["pack_approval"] = None

        return data

    def compute_canonical_sha256(self) -> str:
        data = self._to_dict_unhashed()
        return compute_canonical_sha256(data)

    def freeze(self) -> None:
        """Freeze and compute deterministic fixture-content and fixture-pack hashes.

        One-way operation: once frozen, calling freeze() again is forbidden
        and fails closed with CalibrationStateError.
        """
        if self.fixture_pack_canonical_sha256 is not None:
            raise CalibrationStateError(
                "CalibrationFixturePack is already frozen; fixture freeze is strictly one-way"
            )

        if self.text_origin not in ALLOWED_TEXT_ORIGINS:
            raise ValueError(f"Invalid text_origin '{self.text_origin}': must be one of {ALLOWED_TEXT_ORIGINS}")

        _require_non_empty_str(self.fixture_author, "fixture_author")
        _require_bool(self.human_authorship_attested, "human_authorship_attested")
        _require_bool(self.formal_material_not_used_attested, "formal_material_not_used_attested")
        _require_bool(self.model_generated_final_fixture_text, "model_generated_final_fixture_text")

        if not self.formal_material_not_used_attested:
            raise CalibrationGateError("formal_material_not_used_attested must be True for calibration fixture freeze")

        content_hash = self.compute_fixture_content_sha256()
        self.fixture_content_canonical_sha256 = content_hash

        if self.text_origin == "human_authored":
            if not self.human_authorship_attested:
                raise CalibrationGateError("human_authorship_attested must be True for human-authored fixture freeze")
            if self.model_generated_final_fixture_text is not False:
                raise CalibrationGateError(
                    "model_generated_final_fixture_text must be False; model text cannot be frozen as human-authored"
                )
        elif self.text_origin == "ai_drafted_human_approved":
            if self.human_authorship_attested is not False:
                raise CalibrationGateError(
                    "human_authorship_attested must be False for AI-drafted fixture pack; cannot falsely claim human authorship"
                )
            if self.model_generated_final_fixture_text is not True:
                raise CalibrationGateError(
                    "model_generated_final_fixture_text must be True for AI-drafted fixture pack"
                )

            if self.ai_draft_provenance is None:
                raise CalibrationGateError("ai_draft_provenance is required for ai_drafted_human_approved fixture freeze")
            self.ai_draft_provenance.validate_current_state()
            if self.ai_draft_provenance.fixture_content_canonical_sha256 != content_hash:
                raise CalibrationGateError(
                    f"ai_draft_provenance fixture_content_canonical_sha256 mismatch: "
                    f"'{self.ai_draft_provenance.fixture_content_canonical_sha256}' != '{content_hash}'"
                )

            if not isinstance(self.case_approvals, dict):
                raise CalibrationGateError("case_approvals must be a dictionary of all 8 case approvals")
            if tuple(sorted(self.case_approvals.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
                raise CalibrationGateError(
                    f"case_approvals must contain exactly all 8 case IDs {CALIBRATION_CASE_IDS}, "
                    f"got {tuple(sorted(self.case_approvals.keys()))}"
                )
            for cid in CALIBRATION_CASE_IDS:
                app = self.case_approvals.get(cid)
                if not isinstance(app, CalibrationCaseApproval):
                    raise CalibrationGateError(f"case_approvals['{cid}'] must be a CalibrationCaseApproval")
                app.validate_current_state()
                if app.decision != "approved":
                    raise CalibrationGateError(
                        f"Case '{cid}' approval decision is '{app.decision}'; all 8 cases must be 'approved' to freeze"
                    )
                case_content_hash = self.cases[cid].compute_case_content_sha256()
                if app.case_content_sha256 != case_content_hash:
                    raise CalibrationGateError(
                        f"Case '{cid}' approval case_content_sha256 mismatch: "
                        f"'{app.case_content_sha256}' != '{case_content_hash}'"
                    )

            if self.pack_approval is None:
                raise CalibrationGateError("pack_approval is required for ai_drafted_human_approved fixture freeze")
            self.pack_approval.validate_current_state()
            if self.pack_approval.fixture_content_canonical_sha256 != content_hash:
                raise CalibrationGateError(
                    f"pack_approval fixture_content_canonical_sha256 mismatch: "
                    f"'{self.pack_approval.fixture_content_canonical_sha256}' != '{content_hash}'"
                )

        if not isinstance(self.cases, dict):
            raise TypeError("cases must be a dictionary")
        if tuple(sorted(self.cases.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
            raise ValueError(f"CalibrationFixturePack must contain all 8 case IDs, got {tuple(sorted(self.cases.keys()))}")

        packet_ids: list[str] = []
        evidence_ids: list[str] = []
        question_texts: list[str] = []
        for cid, case in self.cases.items():
            case.validate_current_state()
            question_texts.append(case.question_text)
            packet_ids.extend([case.tcm_packet.packet_id, case.western_packet.packet_id])
            for ev in case.tcm_packet.evidence_items + case.western_packet.evidence_items:
                evidence_ids.append(ev.evidence_id)

        if len(set(packet_ids)) != 16:
            raise CalibrationGateError("Duplicate packet_id detected in fixture pack")
        if len(set(evidence_ids)) != 64:
            raise CalibrationGateError("Duplicate evidence_id detected across fixture pack")

        check_formal_material_separation(
            case_ids=list(self.cases.keys()),
            packet_ids=packet_ids,
            evidence_ids=evidence_ids,
            question_texts=question_texts,
        )

        self.fixture_pack_canonical_sha256 = self.compute_canonical_sha256()
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        data = self._to_dict_unhashed()
        data["fixture_pack_canonical_sha256"] = self.fixture_pack_canonical_sha256
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationFixturePack:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationFixturePack")
        cases_raw = data.get("cases", {})
        if not isinstance(cases_raw, dict):
            raise TypeError("cases must be a dictionary")
        cases = {cid: CalibrationCase.from_dict(c_data) for cid, c_data in cases_raw.items()}

        prov_raw = data.get("ai_draft_provenance")
        prov = CalibrationAiDraftProvenance.from_dict(prov_raw) if prov_raw is not None else None

        case_apps_raw = data.get("case_approvals")
        case_apps = (
            {cid: CalibrationCaseApproval.from_dict(ca_data) for cid, ca_data in case_apps_raw.items()}
            if case_apps_raw is not None
            else None
        )

        pack_app_raw = data.get("pack_approval")
        pack_app = CalibrationPackApproval.from_dict(pack_app_raw) if pack_app_raw is not None else None

        return cls(
            calibration_design_id=data.get("calibration_design_id", CALIBRATION_DESIGN_ID),
            study_id=data.get("study_id", STUDY_ID),
            protocol_id=data.get("protocol_id", PROTOCOL_ID),
            protocol_hash=data.get("protocol_hash", FROZEN_PROTOCOL_BYTE_SHA256),
            fixture_author=data.get("fixture_author", ""),
            text_origin=data.get("text_origin", "human_authored"),
            human_authorship_attested=data.get("human_authorship_attested", False),
            formal_material_not_used_attested=data.get("formal_material_not_used_attested", False),
            model_generated_final_fixture_text=data.get("model_generated_final_fixture_text", False),
            cases=cases,
            ai_draft_provenance=prov,
            case_approvals=case_apps,
            pack_approval=pack_app,
            fixture_content_canonical_sha256=data.get("fixture_content_canonical_sha256"),
            fixture_pack_canonical_sha256=data.get("fixture_pack_canonical_sha256"),
        )

    def to_packet_anchor_index(self) -> FrozenPacketAnchorIndex:
        """Construct synthetic FrozenPacketAnchorIndex from the 16 calibration packets."""
        tcm_records: list[dict[str, Any]] = []
        western_records: list[dict[str, Any]] = []

        for cid in CALIBRATION_CASE_IDS:
            case = self.cases[cid]
            # TCM
            tcm_dict = {
                "packet_id": case.tcm_packet.packet_id,
                "question_id": case.calibration_case_id,
                "perspective": "tcm",
                "question_text": case.question_text,
                "topic": "calibration_case",
                "evidence_items": [item.to_dict() for item in case.tcm_packet.evidence_items],
            }
            tcm_dict["packet_canonical_sha256"] = compute_canonical_sha256(tcm_dict)
            tcm_records.append(tcm_dict)

            # Western
            west_dict = {
                "packet_id": case.western_packet.packet_id,
                "question_id": case.calibration_case_id,
                "perspective": "western",
                "question_text": case.question_text,
                "topic": "calibration_case",
                "evidence_items": [item.to_dict() for item in case.western_packet.evidence_items],
            }
            west_dict["packet_canonical_sha256"] = compute_canonical_sha256(west_dict)
            western_records.append(west_dict)

        return FrozenPacketAnchorIndex.from_packet_records(tcm_records, western_records)


# ==============================================================================
# CALIBRATION CASE REVIEW STATE
# ==============================================================================

@dataclass
class CalibrationCaseReviewState:
    """Annotation state for a single calibration case within a reviewer workspace."""

    case_id: str
    annotation_complete: bool = False
    records: list[dict[str, Any]] = field(default_factory=list)
    no_supportable_unit_reason: str = ""

    def validate_current_state(self) -> None:
        if self.case_id not in CALIBRATION_CASE_IDS:
            raise ValueError(f"Invalid case_id '{self.case_id}': must be one of {CALIBRATION_CASE_IDS}")
        _require_bool(self.annotation_complete, "annotation_complete")
        if not isinstance(self.records, list):
            raise TypeError("records must be a list")
        if not isinstance(self.no_supportable_unit_reason, str):
            raise TypeError("no_supportable_unit_reason must be a str")

        # Validate that each record is dict and matches case_id
        for rec in self.records:
            if not isinstance(rec, dict):
                raise TypeError("Record in CalibrationCaseReviewState must be a dict")
            rec_qid = rec.get("question_id")
            if rec_qid != self.case_id:
                raise ValueError(
                    f"Record question_id '{rec_qid}' does not match case_id '{self.case_id}'"
                )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "case_id": self.case_id,
            "annotation_complete": self.annotation_complete,
            "records": copy.deepcopy(self.records),
            "no_supportable_unit_reason": self.no_supportable_unit_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationCaseReviewState:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationCaseReviewState")
        recs_raw = data.get("records", [])
        if not isinstance(recs_raw, list):
            raise TypeError("records must be a list")
        return cls(
            case_id=data.get("case_id", ""),
            annotation_complete=data.get("annotation_complete", False),
            records=copy.deepcopy(recs_raw),
            no_supportable_unit_reason=data.get("no_supportable_unit_reason", ""),
        )


# ==============================================================================
# CALIBRATION SUBMISSION LOCK + HASH (Task 8 & 9, Part E, F, G)
# ==============================================================================

class CalibrationLockedSubmission:
    """Immutable, mechanically sealed snapshot of a locked calibration reviewer submission.

    This is an AUTHORITY object. Direct public instantiation and subclassing are forbidden.
    Instances must be created via CalibrationReviewerWorkspace.lock_submission() or
    load_verified_locked_submission().
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("CalibrationLockedSubmission is final and cannot be subclassed")

    def __init__(
        self,
        *,
        calibration_design_id: str,
        fixture_pack_hash: str,
        reviewer_role: Literal["reviewer_a", "reviewer_b"],
        case_ids: tuple[str, ...],
        records_by_case: dict[str, list[dict[str, Any]]],
        case_completion_states: dict[str, bool],
        no_supportable_unit_reasons: dict[str, str],
        submission_version: int,
        lock_timestamp: str,
        submission_hash: str,
        _seal_token: object = None,
    ) -> None:
        if _seal_token is not _CALIBRATION_LOCKED_SUBMISSION_SEAL_TOKEN:
            raise TypeError(
                "Direct public construction of CalibrationLockedSubmission is forbidden. "
                "Instances must be created via CalibrationReviewerWorkspace.lock_submission() "
                "or load_verified_locked_submission()."
            )
        self.calibration_design_id = calibration_design_id
        self.fixture_pack_hash = fixture_pack_hash
        self.reviewer_role = reviewer_role
        self.case_ids = tuple(case_ids)
        self.records_by_case = records_by_case
        self.case_completion_states = case_completion_states
        self.no_supportable_unit_reasons = no_supportable_unit_reasons
        self.submission_version = submission_version
        self.lock_timestamp = lock_timestamp
        self.submission_hash = submission_hash
        self.validate_current_state()

    def validate_current_state(self) -> None:
        if type(self) is not CalibrationLockedSubmission:
            raise TypeError("Object must be an exact CalibrationLockedSubmission")

        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )
        _require_non_empty_str(self.fixture_pack_hash, "fixture_pack_hash")
        if self.reviewer_role not in ALLOWED_REVIEWER_ROLES:
            raise ValueError(f"reviewer_role must be 'reviewer_a' or 'reviewer_b', got '{self.reviewer_role}'")
        if tuple(self.case_ids) != CALIBRATION_CASE_IDS:
            raise ValueError(f"case_ids must exactly match {CALIBRATION_CASE_IDS}, got {self.case_ids}")
        if type(self.submission_version) is not int or self.submission_version < 1:
            raise ValueError(f"submission_version must be an integer >= 1, got {self.submission_version!r}")
        _require_non_empty_str(self.lock_timestamp, "lock_timestamp")
        _require_non_empty_str(self.submission_hash, "submission_hash")

        if not isinstance(self.records_by_case, dict):
            raise TypeError("records_by_case must be a dictionary")
        if tuple(sorted(self.records_by_case.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
            raise ValueError(f"records_by_case keys must exactly match {CALIBRATION_CASE_IDS}")

        if not isinstance(self.case_completion_states, dict):
            raise TypeError("case_completion_states must be a dictionary")
        if tuple(sorted(self.case_completion_states.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
            raise ValueError(f"case_completion_states keys must exactly match {CALIBRATION_CASE_IDS}")

        if not isinstance(self.no_supportable_unit_reasons, dict):
            raise TypeError("no_supportable_unit_reasons must be a dictionary")
        if tuple(sorted(self.no_supportable_unit_reasons.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
            raise ValueError(f"no_supportable_unit_reasons keys must exactly match {CALIBRATION_CASE_IDS}")

        # Deep hash verification (Part G)
        expected_hash = compute_canonical_sha256(self._to_dict_unhashed())
        if self.submission_hash != expected_hash:
            raise CalibrationLockError(
                f"submission_hash mismatch: recorded '{self.submission_hash}' != computed '{expected_hash}'"
            )

        # Deep mechanical gate requirements (Task 9 & Part D, G)
        for cid in CALIBRATION_CASE_IDS:
            comp = self.case_completion_states.get(cid)
            _require_bool(comp, f"case_completion_states[{cid}]")
            if comp is not True:
                raise CalibrationLockError(f"Case '{cid}' is not marked annotation_complete in locked submission")
            recs = self.records_by_case.get(cid)
            if not isinstance(recs, list):
                raise TypeError(f"records_by_case[{cid}] must be a list")
            for r in recs:
                if not isinstance(r, dict):
                    raise TypeError(f"Record in case '{cid}' must be a dict")
                if r.get("question_id") != cid:
                    raise ValueError(f"Record question_id '{r.get('question_id')}' does not match case '{cid}'")
            reason = self.no_supportable_unit_reasons.get(cid)
            if not isinstance(reason, str):
                raise TypeError(f"no_supportable_unit_reasons[{cid}] must be a str")

            has_records = len(recs) > 0
            has_reason = bool(reason.strip())
            # XOR requirement (Part D)
            if (has_records and has_reason) or (not has_records and not has_reason):
                raise CalibrationLockError(
                    f"Case '{cid}' in locked submission has neither reference units nor no_supportable_unit_reason "
                    f"(or has both); violates XOR requirement."
                )

    def _to_dict_unhashed(self) -> dict[str, Any]:
        return {
            "calibration_design_id": self.calibration_design_id,
            "fixture_pack_hash": self.fixture_pack_hash,
            "reviewer_role": self.reviewer_role,
            "case_ids": list(self.case_ids),
            "records_by_case": {k: copy.deepcopy(self.records_by_case[k]) for k in sorted(self.records_by_case.keys())},
            "case_completion_states": {
                k: self.case_completion_states[k] for k in sorted(self.case_completion_states.keys())
            },
            "no_supportable_unit_reasons": {
                k: self.no_supportable_unit_reasons[k] for k in sorted(self.no_supportable_unit_reasons.keys())
            },
            "submission_version": self.submission_version,
            "lock_timestamp": self.lock_timestamp,
        }

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        data = self._to_dict_unhashed()
        data["submission_hash"] = self.submission_hash
        return data

    @classmethod
    def load_verified(
        cls,
        data: dict[str, Any],
        fixture_pack: CalibrationFixturePack,
    ) -> CalibrationLockedSubmission:
        return load_verified_locked_submission(data, fixture_pack)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        fixture_pack: CalibrationFixturePack | None = None,
    ) -> CalibrationLockedSubmission:
        if fixture_pack is None:
            raise CalibrationGateError(
                "CalibrationLockedSubmission.from_dict requires a verified frozen fixture_pack; "
                "use load_verified_locked_submission(data, fixture_pack) or pass fixture_pack"
            )
        return load_verified_locked_submission(data, fixture_pack)


def load_verified_locked_submission(
    data: dict[str, Any],
    fixture_pack: CalibrationFixturePack,
) -> CalibrationLockedSubmission:
    """Verify serialized locked submission against exact frozen fixture pack authority (Part F)."""
    if not isinstance(fixture_pack, CalibrationFixturePack):
        raise TypeError(f"fixture_pack must be CalibrationFixturePack, got {type(fixture_pack).__name__}")
    fixture_pack.validate_current_state()
    if fixture_pack.fixture_pack_canonical_sha256 is None:
        raise CalibrationGateError("fixture_pack must be frozen with a canonical SHA256")
    if not isinstance(data, dict):
        raise TypeError("Expected dict for locked submission data")

    design_id = data.get("calibration_design_id")
    if design_id != CALIBRATION_DESIGN_ID:
        raise CalibrationGateError(f"calibration_design_id mismatch: '{design_id}' != '{CALIBRATION_DESIGN_ID}'")

    f_hash = data.get("fixture_pack_hash")
    if f_hash != fixture_pack.fixture_pack_canonical_sha256:
        raise CalibrationGateError(
            f"fixture_pack_hash mismatch: submission recorded '{f_hash}' != fixture pack '{fixture_pack.fixture_pack_canonical_sha256}'"
        )

    role = data.get("reviewer_role")
    if role not in ALLOWED_REVIEWER_ROLES:
        raise ValueError(f"Invalid reviewer_role: {role!r}")

    case_ids = data.get("case_ids")
    if not isinstance(case_ids, (list, tuple)) or tuple(case_ids) != CALIBRATION_CASE_IDS:
        raise ValueError(f"case_ids must exactly match {CALIBRATION_CASE_IDS}, got {case_ids}")

    records_by_case = data.get("records_by_case")
    if not isinstance(records_by_case, dict):
        raise TypeError("records_by_case must be a dictionary")
    if tuple(sorted(records_by_case.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
        raise ValueError(f"records_by_case keys must exactly match {CALIBRATION_CASE_IDS}")

    case_comp = data.get("case_completion_states")
    if not isinstance(case_comp, dict):
        raise TypeError("case_completion_states must be a dictionary")
    if tuple(sorted(case_comp.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
        raise ValueError(f"case_completion_states keys must exactly match {CALIBRATION_CASE_IDS}")

    no_reasons = data.get("no_supportable_unit_reasons")
    if not isinstance(no_reasons, dict):
        raise TypeError("no_supportable_unit_reasons must be a dictionary")
    if tuple(sorted(no_reasons.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
        raise ValueError(f"no_supportable_unit_reasons keys must exactly match {CALIBRATION_CASE_IDS}")

    sub_version = data.get("submission_version")
    if type(sub_version) is not int or sub_version < 1:
        raise ValueError(f"submission_version must be int >= 1, got {sub_version!r}")

    lock_ts = data.get("lock_timestamp")
    _require_non_empty_str(lock_ts, "lock_timestamp")

    anchor_index = fixture_pack.to_packet_anchor_index()
    for cid in CALIBRATION_CASE_IDS:
        comp = case_comp[cid]
        _require_bool(comp, f"case_completion_states[{cid}]")
        if comp is not True:
            raise CalibrationLockError(f"Case '{cid}' is not marked complete in locked submission")

        recs = records_by_case[cid]
        if not isinstance(recs, list):
            raise TypeError(f"records_by_case[{cid}] must be a list")
        reason = no_reasons[cid]
        if not isinstance(reason, str):
            raise TypeError(f"no_supportable_unit_reasons[{cid}] must be a str")

        has_records = len(recs) > 0
        has_reason = bool(reason.strip())
        if (has_records and has_reason) or (not has_records and not has_reason):
            raise CalibrationLockError(
                f"Case '{cid}' has neither reference units nor no_supportable_unit_reason "
                f"(or has both); violates XOR requirement."
            )

        for rec in recs:
            if not isinstance(rec, dict):
                raise TypeError(f"Record in case '{cid}' must be a dict")
            rec_qid = rec.get("question_id")
            if rec_qid != cid:
                raise ValueError(f"Record question_id '{rec_qid}' does not match case '{cid}'")
            errors = validate_reference_unit_record(rec, mode="draft", packet_index=anchor_index)
            if errors:
                raise CalibrationLockError(
                    f"Locked record validation failed for case '{cid}': {'; '.join(errors)}"
                )
            anchors = rec.get("evidence_anchors", [])
            check_formal_material_separation(
                case_ids=[cid],
                packet_ids=[a.get("packet_id", "") for a in anchors if isinstance(a, dict)],
                evidence_ids=[a.get("evidence_id", "") for a in anchors if isinstance(a, dict)],
            )

    sub_hash = data.get("submission_hash")
    _require_non_empty_str(sub_hash, "submission_hash")
    unhashed = {
        "calibration_design_id": design_id,
        "fixture_pack_hash": f_hash,
        "reviewer_role": role,
        "case_ids": list(CALIBRATION_CASE_IDS),
        "records_by_case": {k: copy.deepcopy(records_by_case[k]) for k in sorted(records_by_case.keys())},
        "case_completion_states": {k: case_comp[k] for k in sorted(case_comp.keys())},
        "no_supportable_unit_reasons": {k: no_reasons[k] for k in sorted(no_reasons.keys())},
        "submission_version": sub_version,
        "lock_timestamp": lock_ts,
    }
    expected_hash = compute_canonical_sha256(unhashed)
    if sub_hash != expected_hash:
        raise CalibrationLockError(
            f"submission_hash mismatch: recorded '{sub_hash}' != computed '{expected_hash}'"
        )

    return CalibrationLockedSubmission(
        calibration_design_id=design_id,
        fixture_pack_hash=f_hash,
        reviewer_role=role,
        case_ids=tuple(CALIBRATION_CASE_IDS),
        records_by_case=records_by_case,
        case_completion_states=case_comp,
        no_supportable_unit_reasons=no_reasons,
        submission_version=sub_version,
        lock_timestamp=lock_ts,
        submission_hash=sub_hash,
        _seal_token=_CALIBRATION_LOCKED_SUBMISSION_SEAL_TOKEN,
    )


# ==============================================================================
# CALIBRATION REVIEWER WORKSPACES (Task 7, 8, 9 & Part C, H, I)
# ==============================================================================

class CalibrationReviewerWorkspace:
    """Isolated working environment for a single calibration reviewer.

    Carries private runtime fixture authority derived from a valid frozen CalibrationFixturePack.
    """

    def __init__(
        self,
        reviewer_role: Literal["reviewer_a", "reviewer_b"],
        fixture_pack_hash: str,
        cases: dict[str, CalibrationCaseReviewState],
        calibration_design_id: str = CALIBRATION_DESIGN_ID,
        workspace_kind: str = "calibration",
        submission_version: int = 1,
        locked_snapshot: CalibrationLockedSubmission | None = None,
        _fixture_pack: CalibrationFixturePack | None = None,
        _anchor_index: FrozenPacketAnchorIndex | None = None,
    ) -> None:
        if _fixture_pack is None or _anchor_index is None:
            raise CalibrationGateError(
                "CalibrationReviewerWorkspace requires private fixture authority; "
                "create via CalibrationReviewerWorkspace.create_blank() or from_dict(data, fixture_pack)"
            )
        self.reviewer_role = reviewer_role
        self.fixture_pack_hash = fixture_pack_hash
        self.cases = cases
        self.calibration_design_id = calibration_design_id
        self.workspace_kind = workspace_kind
        self.submission_version = submission_version
        self.locked_snapshot = locked_snapshot
        self._fixture_pack = _fixture_pack
        self._anchor_index = _anchor_index
        self.validate_current_state()

    @property
    def is_locked(self) -> bool:
        """Lock state is derived from presence of an authoritative locked snapshot (Part H)."""
        return self.locked_snapshot is not None

    @is_locked.setter
    def is_locked(self, val: Any) -> None:
        if self.locked_snapshot is not None and not val:
            raise CalibrationLockError("Cannot unlock a locked workspace; workspace lock state is strictly one-way")
        if self.locked_snapshot is None and val:
            raise CalibrationLockError(
                "Cannot mark workspace locked without an authoritative locked snapshot; use lock_submission()"
            )

    def validate_current_state(self) -> None:
        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )
        if self.workspace_kind != "calibration":
            raise ValueError(f"workspace_kind must be 'calibration', got '{self.workspace_kind}'")
        if self.reviewer_role not in ALLOWED_REVIEWER_ROLES:
            raise ValueError(f"Invalid reviewer_role '{self.reviewer_role}': must be 'reviewer_a' or 'reviewer_b'")
        _require_non_empty_str(self.fixture_pack_hash, "fixture_pack_hash")
        if type(self.submission_version) is not int or self.submission_version < 1:
            raise ValueError(f"submission_version must be int >= 1, got {self.submission_version!r}")

        if tuple(sorted(self.cases.keys())) != tuple(sorted(CALIBRATION_CASE_IDS)):
            raise ValueError(
                f"Workspace must contain all 8 cases {CALIBRATION_CASE_IDS}, got {tuple(sorted(self.cases.keys()))}"
            )

        for cid, state in self.cases.items():
            if not isinstance(state, CalibrationCaseReviewState):
                raise TypeError(f"Expected CalibrationCaseReviewState for key '{cid}', got {type(state).__name__}")
            if cid != state.case_id:
                raise ValueError(f"Key '{cid}' does not match state.case_id '{state.case_id}'")
            state.validate_current_state()

        if self.locked_snapshot is not None:
            if type(self.locked_snapshot) is not CalibrationLockedSubmission:
                raise TypeError("locked_snapshot must be exact CalibrationLockedSubmission")
            self.locked_snapshot.validate_current_state()
            if self.locked_snapshot.fixture_pack_hash != self.fixture_pack_hash:
                raise CalibrationLockError("locked_snapshot fixture_pack_hash does not match workspace")
            if self.locked_snapshot.reviewer_role != self.reviewer_role:
                raise CalibrationLockError("locked_snapshot reviewer_role does not match workspace")
            if self.locked_snapshot.submission_version != self.submission_version:
                raise CalibrationLockError("locked_snapshot submission_version does not match workspace")

            # Check that live workspace cases are mechanically consistent with locked snapshot (Part H)
            for cid in CALIBRATION_CASE_IDS:
                c_state = self.cases[cid]
                snap_recs = self.locked_snapshot.records_by_case[cid]
                snap_reason = self.locked_snapshot.no_supportable_unit_reasons[cid]
                snap_comp = self.locked_snapshot.case_completion_states[cid]
                if canonical_json_dumps(c_state.records) != canonical_json_dumps(snap_recs):
                    raise CalibrationStateError(
                        f"Workspace case '{cid}' records have drifted from locked snapshot"
                    )
                if c_state.no_supportable_unit_reason != snap_reason:
                    raise CalibrationStateError(
                        f"Workspace case '{cid}' reason has drifted from locked snapshot"
                    )
                if c_state.annotation_complete != snap_comp:
                    raise CalibrationStateError(
                        f"Workspace case '{cid}' completion state has drifted from locked snapshot"
                    )

    @classmethod
    def create_blank(
        cls,
        reviewer_role: Literal["reviewer_a", "reviewer_b"],
        fixture_pack: CalibrationFixturePack,
    ) -> CalibrationReviewerWorkspace:
        fixture_pack.validate_current_state()
        if fixture_pack.fixture_pack_canonical_sha256 is None:
            raise CalibrationGateError("Cannot create reviewer workspace from unfrozen fixture pack")
        index = fixture_pack.to_packet_anchor_index()
        cases = {
            cid: CalibrationCaseReviewState(case_id=cid)
            for cid in CALIBRATION_CASE_IDS
        }
        return cls(
            reviewer_role=reviewer_role,
            fixture_pack_hash=fixture_pack.fixture_pack_canonical_sha256,
            cases=cases,
            calibration_design_id=CALIBRATION_DESIGN_ID,
            workspace_kind="calibration",
            submission_version=1,
            locked_snapshot=None,
            _fixture_pack=fixture_pack,
            _anchor_index=index,
        )

    def get_reviewer_facing_case(self, case_id: str) -> dict[str, Any]:
        """Retrieve reviewer-facing material for a specific case (blinds purpose/metadata)."""
        if case_id not in self.cases:
            raise KeyError(f"Case '{case_id}' not found in workspace")
        return self._fixture_pack.cases[case_id].to_reviewer_facing_dict()

    def get_reviewer_facing_fixture_pack(self) -> dict[str, Any]:
        """Retrieve reviewer-facing representation of the entire fixture pack."""
        return self._fixture_pack.to_reviewer_facing_dict()

    def add_record(self, case_id: str, record: dict[str, Any] | ReferenceUnitRecord) -> None:
        if self.is_locked:
            raise CalibrationLockError("Cannot add records to locked calibration workspace")
        if case_id not in self.cases:
            raise KeyError(f"Case '{case_id}' not found in workspace")

        rec_dict = (
            record.model_dump(mode="json")
            if isinstance(record, ReferenceUnitRecord)
            else copy.deepcopy(record)
        )

        rec_qid = rec_dict.get("question_id", "")
        if rec_qid != case_id:
            raise ValueError(f"Record question_id '{rec_qid}' does not match case_id '{case_id}'")

        # Mandatory validation against verified anchor index derived from fixture authority (Part C)
        errors = validate_reference_unit_record(rec_dict, mode="draft", packet_index=self._anchor_index)
        if errors:
            raise ValueError(f"Record validation failed: {'; '.join(errors)}")

        anchors = rec_dict.get("evidence_anchors", [])
        check_formal_material_separation(
            case_ids=[case_id],
            packet_ids=[a.get("packet_id", "") for a in anchors if isinstance(a, dict)],
            evidence_ids=[a.get("evidence_id", "") for a in anchors if isinstance(a, dict)],
        )

        self.cases[case_id].records.append(rec_dict)

    def set_no_supportable_unit_reason(self, case_id: str, reason: str) -> None:
        if self.is_locked:
            raise CalibrationLockError("Cannot set reason on locked calibration workspace")
        if case_id not in self.cases:
            raise KeyError(f"Case '{case_id}' not found in workspace")
        self.cases[case_id].no_supportable_unit_reason = reason

    def set_case_complete(self, case_id: str, complete: bool = True) -> None:
        if self.is_locked:
            raise CalibrationLockError("Cannot modify completion on locked calibration workspace")
        if case_id not in self.cases:
            raise KeyError(f"Case '{case_id}' not found in workspace")
        _require_bool(complete, "complete")
        self.cases[case_id].annotation_complete = complete
        self.cases[case_id].validate_current_state()

    def lock_submission(self) -> CalibrationLockedSubmission:
        if self.is_locked:
            assert self.locked_snapshot is not None
            return self.locked_snapshot

        self.validate_current_state()

        # Gate requirements (Task 9 & Part D)
        for cid in CALIBRATION_CASE_IDS:
            c_state = self.cases[cid]
            if not c_state.annotation_complete:
                raise CalibrationLockError(f"Cannot lock: case '{cid}' is not marked annotation_complete")
            has_records = len(c_state.records) > 0
            has_reason = bool(c_state.no_supportable_unit_reason.strip())
            # XOR requirement (Part D)
            if (has_records and has_reason) or (not has_records and not has_reason):
                raise CalibrationLockError(
                    f"Cannot lock: case '{cid}' has neither reference units nor no_supportable_unit_reason "
                    f"(or has both); violates XOR requirement."
                )

            # Mandatory validation of all records against verified anchor index (Part C)
            for rec in c_state.records:
                errors = validate_reference_unit_record(rec, mode="draft", packet_index=self._anchor_index)
                if errors:
                    raise CalibrationLockError(
                        f"Cannot lock: record validation failed for case '{cid}': {'; '.join(errors)}"
                    )
                anchors = rec.get("evidence_anchors", [])
                check_formal_material_separation(
                    case_ids=[cid],
                    packet_ids=[a.get("packet_id", "") for a in anchors if isinstance(a, dict)],
                    evidence_ids=[a.get("evidence_id", "") for a in anchors if isinstance(a, dict)],
                )

        records_by_case = {cid: copy.deepcopy(self.cases[cid].records) for cid in CALIBRATION_CASE_IDS}
        completion_states = {cid: self.cases[cid].annotation_complete for cid in CALIBRATION_CASE_IDS}
        no_unit_reasons = {cid: self.cases[cid].no_supportable_unit_reason for cid in CALIBRATION_CASE_IDS}
        now_iso = datetime.now(timezone.utc).isoformat()

        unhashed = {
            "calibration_design_id": self.calibration_design_id,
            "fixture_pack_hash": self.fixture_pack_hash,
            "reviewer_role": self.reviewer_role,
            "case_ids": list(CALIBRATION_CASE_IDS),
            "records_by_case": {k: records_by_case[k] for k in sorted(records_by_case.keys())},
            "case_completion_states": {k: completion_states[k] for k in sorted(completion_states.keys())},
            "no_supportable_unit_reasons": {k: no_unit_reasons[k] for k in sorted(no_unit_reasons.keys())},
            "submission_version": self.submission_version,
            "lock_timestamp": now_iso,
        }
        sub_hash = compute_canonical_sha256(unhashed)

        snapshot = CalibrationLockedSubmission(
            calibration_design_id=self.calibration_design_id,
            fixture_pack_hash=self.fixture_pack_hash,
            reviewer_role=self.reviewer_role,
            case_ids=CALIBRATION_CASE_IDS,
            records_by_case=records_by_case,
            case_completion_states=completion_states,
            no_supportable_unit_reasons=no_unit_reasons,
            submission_version=self.submission_version,
            lock_timestamp=now_iso,
            submission_hash=sub_hash,
            _seal_token=_CALIBRATION_LOCKED_SUBMISSION_SEAL_TOKEN,
        )

        self.locked_snapshot = snapshot
        return snapshot

    def create_amended_version(self) -> CalibrationReviewerWorkspace:
        """Derive an amendment from the authoritative locked snapshot (Part I)."""
        if not self.is_locked or self.locked_snapshot is None:
            raise CalibrationLockError("Cannot create amended version from an unlocked workspace")
        self.validate_current_state()

        new_cases = {
            cid: CalibrationCaseReviewState(
                case_id=cid,
                annotation_complete=False,
                records=copy.deepcopy(self.locked_snapshot.records_by_case[cid]),
                no_supportable_unit_reason=self.locked_snapshot.no_supportable_unit_reasons[cid],
            )
            for cid in CALIBRATION_CASE_IDS
        }
        return CalibrationReviewerWorkspace(
            reviewer_role=self.reviewer_role,
            fixture_pack_hash=self.fixture_pack_hash,
            cases=new_cases,
            calibration_design_id=self.calibration_design_id,
            workspace_kind="calibration",
            submission_version=self.submission_version + 1,
            locked_snapshot=None,
            _fixture_pack=self._fixture_pack,
            _anchor_index=self._anchor_index,
        )

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "calibration_design_id": self.calibration_design_id,
            "workspace_kind": self.workspace_kind,
            "reviewer_role": self.reviewer_role,
            "fixture_pack_hash": self.fixture_pack_hash,
            "submission_version": self.submission_version,
            "is_locked": self.is_locked,
            "locked_snapshot": self.locked_snapshot.to_dict() if self.locked_snapshot is not None else None,
            "cases": {cid: state.to_dict() for cid, state in sorted(self.cases.items())},
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        fixture_pack: CalibrationFixturePack | None = None,
    ) -> CalibrationReviewerWorkspace:
        if fixture_pack is None:
            raise CalibrationGateError(
                "Deserializing CalibrationReviewerWorkspace requires supplying the matching frozen CalibrationFixturePack"
            )
        if not isinstance(fixture_pack, CalibrationFixturePack):
            raise TypeError(f"fixture_pack must be CalibrationFixturePack, got {type(fixture_pack).__name__}")
        fixture_pack.validate_current_state()
        if fixture_pack.fixture_pack_canonical_sha256 is None:
            raise CalibrationGateError("Cannot deserialize reviewer workspace against unfrozen fixture pack")

        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationReviewerWorkspace")

        f_hash = data.get("fixture_pack_hash")
        if f_hash != fixture_pack.fixture_pack_canonical_sha256:
            raise CalibrationGateError(
                f"fixture_pack_hash in data '{f_hash}' does not match fixture pack '{fixture_pack.fixture_pack_canonical_sha256}'"
            )

        cases_raw = data.get("cases", {})
        if not isinstance(cases_raw, dict):
            raise TypeError("cases must be a dictionary")
        cases = {cid: CalibrationCaseReviewState.from_dict(c_data) for cid, c_data in cases_raw.items()}

        snap_raw = data.get("locked_snapshot")
        snap = None
        if snap_raw is not None:
            snap = load_verified_locked_submission(snap_raw, fixture_pack)

        return cls(
            reviewer_role=data.get("reviewer_role", "reviewer_a"),
            fixture_pack_hash=f_hash,
            cases=cases,
            calibration_design_id=data.get("calibration_design_id", CALIBRATION_DESIGN_ID),
            workspace_kind=data.get("workspace_kind", "calibration"),
            submission_version=data.get("submission_version", 1),
            locked_snapshot=snap,
            _fixture_pack=fixture_pack,
            _anchor_index=fixture_pack.to_packet_anchor_index(),
        )


# ==============================================================================
# A/B COMPARISON GATE (Task 10 & Part J)
# ==============================================================================

class CalibrationComparisonView:
    """Read-only gatekeeper view for comparing Reviewer A and B calibration records.

    Constructed ONLY when both submissions are locked, hashes verify, and roles match.
    Strictly NO automated semantic alignment, merging, or answer-key generation.
    """

    def __init__(
        self,
        reviewer_a_submission: CalibrationLockedSubmission,
        reviewer_b_submission: CalibrationLockedSubmission,
    ) -> None:
        self.reviewer_a_submission = reviewer_a_submission
        self.reviewer_b_submission = reviewer_b_submission
        self.validate_current_state()

    def validate_current_state(self) -> None:
        if type(self.reviewer_a_submission) is not CalibrationLockedSubmission:
            raise CalibrationComparisonGateError(
                f"reviewer_a_submission must be exact CalibrationLockedSubmission, got {type(self.reviewer_a_submission).__name__}"
            )
        if type(self.reviewer_b_submission) is not CalibrationLockedSubmission:
            raise CalibrationComparisonGateError(
                f"reviewer_b_submission must be exact CalibrationLockedSubmission, got {type(self.reviewer_b_submission).__name__}"
            )

        self.reviewer_a_submission.validate_current_state()
        self.reviewer_b_submission.validate_current_state()

        if self.reviewer_a_submission.reviewer_role != "reviewer_a":
            raise CalibrationComparisonGateError(
                f"Expected reviewer_a role, got '{self.reviewer_a_submission.reviewer_role}'"
            )
        if self.reviewer_b_submission.reviewer_role != "reviewer_b":
            raise CalibrationComparisonGateError(
                f"Expected reviewer_b role, got '{self.reviewer_b_submission.reviewer_role}'"
            )

        if self.reviewer_a_submission.fixture_pack_hash != self.reviewer_b_submission.fixture_pack_hash:
            raise CalibrationComparisonGateError(
                f"Fixture pack hash mismatch between Reviewer A ('{self.reviewer_a_submission.fixture_pack_hash}') "
                f"and Reviewer B ('{self.reviewer_b_submission.fixture_pack_hash}')"
            )

        if self.reviewer_a_submission.calibration_design_id != self.reviewer_b_submission.calibration_design_id:
            raise CalibrationComparisonGateError("Calibration design ID mismatch between Reviewer A and Reviewer B")

        if (
            self.reviewer_a_submission.case_ids != CALIBRATION_CASE_IDS
            or self.reviewer_b_submission.case_ids != CALIBRATION_CASE_IDS
        ):
            raise CalibrationComparisonGateError("Both submissions must cover all 8 CAL-2CC cases")

    @classmethod
    def from_locked_submissions(
        cls,
        reviewer_a_submission: CalibrationLockedSubmission,
        reviewer_b_submission: CalibrationLockedSubmission,
    ) -> CalibrationComparisonView:
        return cls(reviewer_a_submission, reviewer_b_submission)

    @property
    def fixture_pack_hash(self) -> str:
        return self.reviewer_a_submission.fixture_pack_hash

    @property
    def case_ids(self) -> tuple[str, ...]:
        return CALIBRATION_CASE_IDS

    def get_case_summary(self, case_id: str) -> dict[str, Any]:
        self.validate_current_state()
        if case_id not in CALIBRATION_CASE_IDS:
            raise KeyError(f"Case '{case_id}' not found in calibration design")

        recs_a = self.reviewer_a_submission.records_by_case.get(case_id, [])
        recs_b = self.reviewer_b_submission.records_by_case.get(case_id, [])
        reason_a = self.reviewer_a_submission.no_supportable_unit_reasons.get(case_id, "")
        reason_b = self.reviewer_b_submission.no_supportable_unit_reasons.get(case_id, "")

        exact_duplicate_indices: list[tuple[int, int]] = []
        for idx_a, ra in enumerate(recs_a):
            for idx_b, rb in enumerate(recs_b):
                if self._is_exact_record_duplicate(ra, rb):
                    exact_duplicate_indices.append((idx_a, idx_b))

        return {
            "case_id": case_id,
            "reviewer_a_records_count": len(recs_a),
            "reviewer_b_records_count": len(recs_b),
            "reviewer_a_has_no_unit_reason": bool(reason_a.strip()),
            "reviewer_b_has_no_unit_reason": bool(reason_b.strip()),
            "reviewer_a_no_unit_reason": reason_a,
            "reviewer_b_no_unit_reason": reason_b,
            "exact_duplicate_pairs_count": len(exact_duplicate_indices),
            "exact_duplicate_pairs": exact_duplicate_indices,
        }

    @staticmethod
    def _is_exact_record_duplicate(rec_a: dict[str, Any], rec_b: dict[str, Any]) -> bool:
        """True exact duplicate check over complete stored record representations (Part J)."""
        return canonical_json_dumps(rec_a) == canonical_json_dumps(rec_b)


# ==============================================================================
# CALIBRATION DISAGREEMENT LOG (Task 11 & 12, Part K, L)
# ==============================================================================

@dataclass
class CalibrationDisagreementEntry:
    """Structured disagreement entry recorded during calibration review."""

    calibration_case_id: str
    disagreement_id: str
    decision_category: str
    reviewer_a_position: str
    reviewer_b_position: str
    ambiguity_classification: Literal["A_CASE_LEVEL", "B_METHODOLOGICAL_AMBIGUITY"]
    evidence_ids_considered: list[str] = field(default_factory=list)
    protocol_sections_considered: list[str] = field(default_factory=list)
    human_resolution: str = ""
    resolution_rationale: str = ""
    participants: list[str] = field(default_factory=list)
    resolution_date: str = ""
    clarification_refreeze_id: str = ""
    clarification_refreeze_attested: bool = False
    status: Literal["open", "resolved"] = "open"

    def validate_current_state(self) -> None:
        if self.calibration_case_id not in CALIBRATION_CASE_IDS:
            raise ValueError(
                f"Invalid calibration_case_id '{self.calibration_case_id}': must be one of {CALIBRATION_CASE_IDS}"
            )
        _require_non_empty_str(self.disagreement_id, "disagreement_id")
        _require_non_empty_str(self.decision_category, "decision_category")
        _require_non_empty_str(self.reviewer_a_position, "reviewer_a_position")
        _require_non_empty_str(self.reviewer_b_position, "reviewer_b_position")

        if self.ambiguity_classification not in ALLOWED_AMBIGUITY_CLASSIFICATIONS:
            raise ValueError(
                f"Invalid ambiguity_classification '{self.ambiguity_classification}': "
                f"must be one of {ALLOWED_AMBIGUITY_CLASSIFICATIONS}"
            )
        if self.status not in ALLOWED_DISAGREEMENT_STATUSES:
            raise ValueError(f"Invalid status '{self.status}': must be one of {ALLOWED_DISAGREEMENT_STATUSES}")

        _require_bool(self.clarification_refreeze_attested, "clarification_refreeze_attested")

        if not isinstance(self.evidence_ids_considered, list):
            raise TypeError("evidence_ids_considered must be a list")
        expected_ev_prefix = f"cal2cc:ev:{self.calibration_case_id}:"
        for eid in self.evidence_ids_considered:
            _require_non_empty_str(eid, "evidence_id in evidence_ids_considered")
            if not eid.startswith(expected_ev_prefix):
                raise CalibrationGateError(
                    f"evidence_id '{eid}' does not belong to case '{self.calibration_case_id}' (expected prefix '{expected_ev_prefix}')"
                )
            if not CALIBRATION_EVIDENCE_ID_PATTERN.match(eid):
                raise CalibrationGateError(f"evidence_id '{eid}' does not match required synthetic pattern")

        if not isinstance(self.protocol_sections_considered, list):
            raise TypeError("protocol_sections_considered must be a list")
        for sec in self.protocol_sections_considered:
            _require_non_empty_str(sec, "protocol_section in protocol_sections_considered")

        if not isinstance(self.participants, list):
            raise TypeError("participants must be a list")
        for p in self.participants:
            _require_non_empty_str(p, "participant in participants")

        if not isinstance(self.human_resolution, str):
            raise TypeError("human_resolution must be a str")
        if not isinstance(self.resolution_rationale, str):
            raise TypeError("resolution_rationale must be a str")
        if not isinstance(self.resolution_date, str):
            raise TypeError("resolution_date must be a str")
        if not isinstance(self.clarification_refreeze_id, str):
            raise TypeError("clarification_refreeze_id must be a str")

        # Resolution gates (Task 11 & 12)
        if self.status == "resolved":
            _require_non_empty_str(self.human_resolution, "human_resolution")
            _require_non_empty_str(self.resolution_rationale, "resolution_rationale")
            _require_non_empty_str(self.resolution_date, "resolution_date")
            if not self.participants:
                raise CalibrationStateError("Resolved disagreement must record participating reviewers")
            if self.ambiguity_classification == "B_METHODOLOGICAL_AMBIGUITY":
                _require_non_empty_str(self.clarification_refreeze_id, "clarification_refreeze_id")
                if not self.clarification_refreeze_attested:
                    raise CalibrationStateError(
                        f"Disagreement '{self.disagreement_id}' is classified as B_METHODOLOGICAL_AMBIGUITY "
                        "and cannot be marked resolved without clarification_refreeze_attested == True"
                    )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def resolve(
        self,
        human_resolution: str,
        resolution_rationale: str,
        participants: list[str],
        resolution_date: str,
        clarification_refreeze_id: str = "",
        clarification_refreeze_attested: bool = False,
    ) -> None:
        """Atomic resolution transition (Part L). Pre-validates candidate before updating self."""
        candidate = copy.deepcopy(self)
        candidate.human_resolution = human_resolution
        candidate.resolution_rationale = resolution_rationale
        candidate.participants = copy.deepcopy(participants)
        candidate.resolution_date = resolution_date
        candidate.clarification_refreeze_id = clarification_refreeze_id
        candidate.clarification_refreeze_attested = clarification_refreeze_attested
        candidate.status = "resolved"
        candidate.validate_current_state()

        self.human_resolution = candidate.human_resolution
        self.resolution_rationale = candidate.resolution_rationale
        self.participants = candidate.participants
        self.resolution_date = candidate.resolution_date
        self.clarification_refreeze_id = candidate.clarification_refreeze_id
        self.clarification_refreeze_attested = candidate.clarification_refreeze_attested
        self.status = "resolved"

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "calibration_case_id": self.calibration_case_id,
            "disagreement_id": self.disagreement_id,
            "decision_category": self.decision_category,
            "reviewer_a_position": self.reviewer_a_position,
            "reviewer_b_position": self.reviewer_b_position,
            "evidence_ids_considered": list(self.evidence_ids_considered),
            "protocol_sections_considered": list(self.protocol_sections_considered),
            "ambiguity_classification": self.ambiguity_classification,
            "human_resolution": self.human_resolution,
            "resolution_rationale": self.resolution_rationale,
            "participants": list(self.participants),
            "resolution_date": self.resolution_date,
            "clarification_refreeze_id": self.clarification_refreeze_id,
            "clarification_refreeze_attested": self.clarification_refreeze_attested,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationDisagreementEntry:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationDisagreementEntry")
        return cls(
            calibration_case_id=data.get("calibration_case_id", ""),
            disagreement_id=data.get("disagreement_id", ""),
            decision_category=data.get("decision_category", ""),
            reviewer_a_position=data.get("reviewer_a_position", ""),
            reviewer_b_position=data.get("reviewer_b_position", ""),
            evidence_ids_considered=data.get("evidence_ids_considered", []),
            protocol_sections_considered=data.get("protocol_sections_considered", []),
            ambiguity_classification=data.get("ambiguity_classification", "A_CASE_LEVEL"),
            human_resolution=data.get("human_resolution", ""),
            resolution_rationale=data.get("resolution_rationale", ""),
            participants=data.get("participants", []),
            resolution_date=data.get("resolution_date", ""),
            clarification_refreeze_id=data.get("clarification_refreeze_id", ""),
            clarification_refreeze_attested=data.get("clarification_refreeze_attested", False),
            status=data.get("status", "open"),
        )


@dataclass
class CalibrationDisagreementLog:
    """Container for human-entered calibration disagreements bound to exact reviewer submissions (Part K)."""

    fixture_pack_hash: str
    reviewer_a_submission_hash: str = ""
    reviewer_b_submission_hash: str = ""
    entries: list[CalibrationDisagreementEntry] = field(default_factory=list)
    calibration_design_id: str = CALIBRATION_DESIGN_ID

    def validate_current_state(self) -> None:
        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )
        _require_non_empty_str(self.fixture_pack_hash, "fixture_pack_hash")
        if not isinstance(self.reviewer_a_submission_hash, str):
            raise TypeError("reviewer_a_submission_hash must be a str")
        if not isinstance(self.reviewer_b_submission_hash, str):
            raise TypeError("reviewer_b_submission_hash must be a str")
        if not isinstance(self.entries, list):
            raise TypeError("entries must be a list")
        seen_ids: set[str] = set()
        for entry in self.entries:
            if not isinstance(entry, CalibrationDisagreementEntry):
                raise TypeError(f"Expected CalibrationDisagreementEntry, got {type(entry).__name__}")
            entry.validate_current_state()
            if entry.disagreement_id in seen_ids:
                raise ValueError(f"Duplicate disagreement_id '{entry.disagreement_id}' in log")
            seen_ids.add(entry.disagreement_id)

    def __post_init__(self) -> None:
        self.validate_current_state()

    @classmethod
    def create_for_comparison(cls, comparison_view: CalibrationComparisonView) -> CalibrationDisagreementLog:
        """Create a new disagreement log bound to exact Reviewer A & B locked submission hashes."""
        comparison_view.validate_current_state()
        return cls(
            fixture_pack_hash=comparison_view.fixture_pack_hash,
            reviewer_a_submission_hash=comparison_view.reviewer_a_submission.submission_hash,
            reviewer_b_submission_hash=comparison_view.reviewer_b_submission.submission_hash,
            entries=[],
            calibration_design_id=comparison_view.reviewer_a_submission.calibration_design_id,
        )

    def add_entry(self, entry: CalibrationDisagreementEntry) -> None:
        entry.validate_current_state()
        self.entries.append(entry)
        self.validate_current_state()

    def has_open_disagreements(self) -> bool:
        self.validate_current_state()
        return any(e.status == "open" for e in self.entries)

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        return {
            "calibration_design_id": self.calibration_design_id,
            "fixture_pack_hash": self.fixture_pack_hash,
            "reviewer_a_submission_hash": self.reviewer_a_submission_hash,
            "reviewer_b_submission_hash": self.reviewer_b_submission_hash,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationDisagreementLog:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationDisagreementLog")
        entries_raw = data.get("entries", [])
        if not isinstance(entries_raw, list):
            raise TypeError("entries must be a list")
        return cls(
            calibration_design_id=data.get("calibration_design_id", CALIBRATION_DESIGN_ID),
            fixture_pack_hash=data.get("fixture_pack_hash", ""),
            reviewer_a_submission_hash=data.get("reviewer_a_submission_hash", ""),
            reviewer_b_submission_hash=data.get("reviewer_b_submission_hash", ""),
            entries=[CalibrationDisagreementEntry.from_dict(e) for e in entries_raw],
        )


# ==============================================================================
# CALIBRATION COMPLETION CHECKLIST & STOP CONDITIONS (Tasks 13 & 14, Part M, N)
# ==============================================================================

class CalibrationCompletionChecklist:
    """Human-attested completion structure governing formal annotation readiness."""

    def __init__(
        self,
        fixture_pack: CalibrationFixturePack,
        reviewer_a_submission: CalibrationLockedSubmission,
        reviewer_b_submission: CalibrationLockedSubmission,
        disagreement_log: CalibrationDisagreementLog,
        all_eight_boundaries_reviewed: bool = False,
        boundary_05_07_08_distinction_reviewed: bool = False,
        reviewers_agree_rules_applicable: bool = False,
        no_calibration_artifact_model_exposed: bool = False,
        no_numerical_agreement_threshold_used: bool = False,
        attestor_a: str = "",
        attestor_b: str = "",
        attestation_notes: str = "",
        calibration_design_id: str = CALIBRATION_DESIGN_ID,
        calibration_ready_for_formal_annotation: bool = False,
    ) -> None:
        self.fixture_pack = fixture_pack
        self.reviewer_a_submission = reviewer_a_submission
        self.reviewer_b_submission = reviewer_b_submission
        self.disagreement_log = disagreement_log
        self.all_eight_boundaries_reviewed = all_eight_boundaries_reviewed
        self.boundary_05_07_08_distinction_reviewed = boundary_05_07_08_distinction_reviewed
        self.reviewers_agree_rules_applicable = reviewers_agree_rules_applicable
        self.no_calibration_artifact_model_exposed = no_calibration_artifact_model_exposed
        self.no_numerical_agreement_threshold_used = no_numerical_agreement_threshold_used
        self.attestor_a = attestor_a
        self.attestor_b = attestor_b
        self.attestation_notes = attestation_notes
        self.calibration_design_id = calibration_design_id
        self._calibration_ready_for_formal_annotation: bool = False

        self.validate_current_state()

        if calibration_ready_for_formal_annotation:
            self.validate_ready_for_completion()
            self._calibration_ready_for_formal_annotation = True

    @property
    def calibration_ready_for_formal_annotation(self) -> bool:
        """Non-forgeable readiness property (Part N). Revalidates completion gates if True."""
        if not self._calibration_ready_for_formal_annotation:
            return False
        self.validate_ready_for_completion()
        return True

    @calibration_ready_for_formal_annotation.setter
    def calibration_ready_for_formal_annotation(self, val: Any) -> None:
        _require_bool(val, "calibration_ready_for_formal_annotation")
        if val:
            self.validate_ready_for_completion()
        self._calibration_ready_for_formal_annotation = val

    def validate_current_state(self) -> None:
        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )

        _require_bool(self.all_eight_boundaries_reviewed, "all_eight_boundaries_reviewed")
        _require_bool(self.boundary_05_07_08_distinction_reviewed, "boundary_05_07_08_distinction_reviewed")
        _require_bool(self.reviewers_agree_rules_applicable, "reviewers_agree_rules_applicable")
        _require_bool(self.no_calibration_artifact_model_exposed, "no_calibration_artifact_model_exposed")
        _require_bool(self.no_numerical_agreement_threshold_used, "no_numerical_agreement_threshold_used")

        if not isinstance(self.attestor_a, str):
            raise TypeError(f"attestor_a must be str, got {type(self.attestor_a).__name__}")
        if not isinstance(self.attestor_b, str):
            raise TypeError(f"attestor_b must be str, got {type(self.attestor_b).__name__}")
        if not isinstance(self.attestation_notes, str):
            raise TypeError(f"attestation_notes must be str, got {type(self.attestation_notes).__name__}")

        if not isinstance(self.fixture_pack, CalibrationFixturePack):
            raise TypeError("fixture_pack must be CalibrationFixturePack")
        self.fixture_pack.validate_current_state()
        if self.fixture_pack.fixture_pack_canonical_sha256 is None:
            raise CalibrationGateError("fixture_pack must be frozen with a canonical SHA256")

        if type(self.reviewer_a_submission) is not CalibrationLockedSubmission:
            raise TypeError("reviewer_a_submission must be exact CalibrationLockedSubmission")
        self.reviewer_a_submission.validate_current_state()

        if type(self.reviewer_b_submission) is not CalibrationLockedSubmission:
            raise TypeError("reviewer_b_submission must be exact CalibrationLockedSubmission")
        self.reviewer_b_submission.validate_current_state()

        if not isinstance(self.disagreement_log, CalibrationDisagreementLog):
            raise TypeError("disagreement_log must be CalibrationDisagreementLog")
        self.disagreement_log.validate_current_state()

        f_hash = self.fixture_pack.fixture_pack_canonical_sha256
        if self.reviewer_a_submission.reviewer_role != "reviewer_a":
            raise CalibrationGateError("reviewer_a_submission must have reviewer_role='reviewer_a'")
        if self.reviewer_b_submission.reviewer_role != "reviewer_b":
            raise CalibrationGateError("reviewer_b_submission must have reviewer_role='reviewer_b'")

        if self.reviewer_a_submission.fixture_pack_hash != f_hash:
            raise CalibrationGateError("reviewer_a_submission fixture_pack_hash does not match fixture pack")
        if self.reviewer_b_submission.fixture_pack_hash != f_hash:
            raise CalibrationGateError("reviewer_b_submission fixture_pack_hash does not match fixture pack")
        if self.disagreement_log.fixture_pack_hash != f_hash:
            raise CalibrationGateError("disagreement_log fixture_pack_hash does not match fixture pack")

        # Disagreement log submission hash binding (Part K)
        if self.disagreement_log.reviewer_a_submission_hash != self.reviewer_a_submission.submission_hash:
            raise CalibrationGateError(
                "disagreement_log reviewer_a_submission_hash does not match Reviewer A submission hash"
            )
        if self.disagreement_log.reviewer_b_submission_hash != self.reviewer_b_submission.submission_hash:
            raise CalibrationGateError(
                "disagreement_log reviewer_b_submission_hash does not match Reviewer B submission hash"
            )

        if self._calibration_ready_for_formal_annotation:
            self.validate_ready_for_completion()

    def validate_ready_for_completion(self) -> None:
        """Master fail-closed validator for marking calibration complete (Part M)."""
        # Revalidate nested authority structures
        self.fixture_pack.validate_current_state()
        self.reviewer_a_submission.validate_current_state()
        self.reviewer_b_submission.validate_current_state()
        self.disagreement_log.validate_current_state()

        # Position-specific roles remain mandatory even if log hashes are rebound.
        if self.reviewer_a_submission.reviewer_role != "reviewer_a":
            raise CalibrationCompletionError(
                "reviewer_a_submission must have reviewer_role='reviewer_a'"
            )
        if self.reviewer_b_submission.reviewer_role != "reviewer_b":
            raise CalibrationCompletionError(
                "reviewer_b_submission must have reviewer_role='reviewer_b'"
            )

        f_hash = self.fixture_pack.fixture_pack_canonical_sha256
        if f_hash is None:
            raise CalibrationCompletionError("fixture_pack must be frozen")
        if self.reviewer_a_submission.fixture_pack_hash != f_hash:
            raise CalibrationCompletionError("Reviewer A fixture hash mismatch")
        if self.reviewer_b_submission.fixture_pack_hash != f_hash:
            raise CalibrationCompletionError("Reviewer B fixture hash mismatch")
        if self.disagreement_log.fixture_pack_hash != f_hash:
            raise CalibrationCompletionError("Disagreement log fixture hash mismatch")
        if self.disagreement_log.reviewer_a_submission_hash != self.reviewer_a_submission.submission_hash:
            raise CalibrationCompletionError("Disagreement log Reviewer A submission hash mismatch")
        if self.disagreement_log.reviewer_b_submission_hash != self.reviewer_b_submission.submission_hash:
            raise CalibrationCompletionError("Disagreement log Reviewer B submission hash mismatch")

        # 1. Human process attestations
        if not self.all_eight_boundaries_reviewed:
            raise CalibrationCompletionError("all_eight_boundaries_reviewed must be True")
        if not self.boundary_05_07_08_distinction_reviewed:
            raise CalibrationCompletionError("boundary_05_07_08_distinction_reviewed must be True")
        if not self.reviewers_agree_rules_applicable:
            raise CalibrationCompletionError("reviewers_agree_rules_applicable must be True")
        if not self.no_calibration_artifact_model_exposed:
            raise CalibrationCompletionError("no_calibration_artifact_model_exposed must be True")
        if not self.no_numerical_agreement_threshold_used:
            raise CalibrationCompletionError("no_numerical_agreement_threshold_used must be True")

        _require_non_empty_str(self.attestor_a, "attestor_a")
        _require_non_empty_str(self.attestor_b, "attestor_b")

        # 2. Fixture pack origin and authorship routing
        if not self.fixture_pack.formal_material_not_used_attested:
            raise CalibrationCompletionError("fixture_pack.formal_material_not_used_attested must be True")

        if self.fixture_pack.text_origin == "human_authored":
            if not self.fixture_pack.human_authorship_attested:
                raise CalibrationCompletionError(
                    "fixture_pack.human_authorship_attested must be True for human_authored pack"
                )
            if self.fixture_pack.model_generated_final_fixture_text is not False:
                raise CalibrationCompletionError(
                    "fixture_pack.model_generated_final_fixture_text must be False for human_authored pack"
                )
        elif self.fixture_pack.text_origin == "ai_drafted_human_approved":
            if self.fixture_pack.human_authorship_attested is not False:
                raise CalibrationCompletionError(
                    "fixture_pack.human_authorship_attested must be False for ai_drafted_human_approved pack"
                )
            if self.fixture_pack.model_generated_final_fixture_text is not True:
                raise CalibrationCompletionError(
                    "fixture_pack.model_generated_final_fixture_text must be True for ai_drafted_human_approved pack"
                )
            if self.fixture_pack.ai_draft_provenance is None:
                raise CalibrationCompletionError(
                    "fixture_pack.ai_draft_provenance is required for ai_drafted_human_approved pack"
                )
            if self.fixture_pack.case_approvals is None or len(self.fixture_pack.case_approvals) != 8:
                raise CalibrationCompletionError(
                    "fixture_pack.case_approvals must contain all 8 case approvals"
                )
            if self.fixture_pack.pack_approval is None:
                raise CalibrationCompletionError(
                    "fixture_pack.pack_approval is required for ai_drafted_human_approved pack"
                )
        else:
            raise CalibrationCompletionError(
                f"Unknown or invalid fixture_pack.text_origin: '{self.fixture_pack.text_origin}'"
            )

        # 3. Disagreement resolution
        if self.disagreement_log.has_open_disagreements():
            raise CalibrationCompletionError("Cannot complete calibration: open disagreements exist in log")

        for entry in self.disagreement_log.entries:
            if entry.ambiguity_classification == "B_METHODOLOGICAL_AMBIGUITY":
                if not entry.clarification_refreeze_id or not entry.clarification_refreeze_attested:
                    raise CalibrationCompletionError(
                        f"Cannot complete calibration: Type-B disagreement '{entry.disagreement_id}' lacks clarification refreeze"
                    )

    def mark_calibration_complete(self) -> None:
        """Mark calibration complete and ready for formal annotation transition."""
        self.validate_ready_for_completion()
        self._calibration_ready_for_formal_annotation = True

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        if self._calibration_ready_for_formal_annotation:
            self.validate_ready_for_completion()
        return {
            "calibration_design_id": self.calibration_design_id,
            "calibration_ready_for_formal_annotation": self._calibration_ready_for_formal_annotation,
            "all_eight_boundaries_reviewed": self.all_eight_boundaries_reviewed,
            "boundary_05_07_08_distinction_reviewed": self.boundary_05_07_08_distinction_reviewed,
            "reviewers_agree_rules_applicable": self.reviewers_agree_rules_applicable,
            "no_calibration_artifact_model_exposed": self.no_calibration_artifact_model_exposed,
            "no_numerical_agreement_threshold_used": self.no_numerical_agreement_threshold_used,
            "attestor_a": self.attestor_a,
            "attestor_b": self.attestor_b,
            "attestation_notes": self.attestation_notes,
            "fixture_pack": self.fixture_pack.to_dict(),
            "reviewer_a_submission": self.reviewer_a_submission.to_dict(),
            "reviewer_b_submission": self.reviewer_b_submission.to_dict(),
            "disagreement_log": self.disagreement_log.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CalibrationCompletionChecklist:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationCompletionChecklist")
        fp = CalibrationFixturePack.from_dict(data.get("fixture_pack", {}))
        sub_a = load_verified_locked_submission(data.get("reviewer_a_submission", {}), fp)
        sub_b = load_verified_locked_submission(data.get("reviewer_b_submission", {}), fp)
        d_log = CalibrationDisagreementLog.from_dict(data.get("disagreement_log", {}))
        return cls(
            calibration_design_id=data.get("calibration_design_id", CALIBRATION_DESIGN_ID),
            calibration_ready_for_formal_annotation=data.get("calibration_ready_for_formal_annotation", False),
            all_eight_boundaries_reviewed=data.get("all_eight_boundaries_reviewed", False),
            boundary_05_07_08_distinction_reviewed=data.get("boundary_05_07_08_distinction_reviewed", False),
            reviewers_agree_rules_applicable=data.get("reviewers_agree_rules_applicable", False),
            no_calibration_artifact_model_exposed=data.get("no_calibration_artifact_model_exposed", False),
            no_numerical_agreement_threshold_used=data.get("no_numerical_agreement_threshold_used", False),
            attestor_a=data.get("attestor_a", ""),
            attestor_b=data.get("attestor_b", ""),
            attestation_notes=data.get("attestation_notes", ""),
            fixture_pack=fp,
            reviewer_a_submission=sub_a,
            reviewer_b_submission=sub_b,
            disagreement_log=d_log,
        )
