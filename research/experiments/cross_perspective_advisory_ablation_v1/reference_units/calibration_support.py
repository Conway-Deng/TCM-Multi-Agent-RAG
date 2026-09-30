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
"""

from __future__ import annotations

import copy
import hashlib
import json
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
# CALIBRATION CONSTANTS / IDENTIFIERS (Task 2)
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


# ==============================================================================
# FORMAL-MATERIAL SEPARATION CHECK (Task 5)
# ==============================================================================

def check_formal_material_separation(
    case_ids: Sequence[str],
    packet_ids: Sequence[str],
    evidence_ids: Sequence[str],
    question_texts: Sequence[str] = (),
) -> None:
    """Mechanically verify that calibration items do not reuse formal study identifiers or text."""
    for pid in packet_ids:
        if pid.startswith("cpaa1:packet:") or pid.startswith("packet:tcm:") or pid.startswith("packet:western:"):
            raise CalibrationGateError(f"Calibration packet_id '{pid}' reuses formal packet prefix")
        if not pid.startswith(CALIBRATION_PACKET_ID_PREFIX):
            raise CalibrationGateError(
                f"Calibration packet_id '{pid}' must start with '{CALIBRATION_PACKET_ID_PREFIX}'"
            )

    for eid in evidence_ids:
        if eid.startswith("cpaa1:ev:") or eid.startswith("ev:tcm:") or eid.startswith("ev:western:"):
            raise CalibrationGateError(f"Calibration evidence_id '{eid}' reuses formal evidence prefix")
        if not eid.startswith(CALIBRATION_EVIDENCE_ID_PREFIX):
            raise CalibrationGateError(
                f"Calibration evidence_id '{eid}' must start with '{CALIBRATION_EVIDENCE_ID_PREFIX}'"
            )

    for cid in case_ids:
        if cid not in CALIBRATION_CASE_IDS:
            raise CalibrationGateError(f"Case ID '{cid}' is not an approved CAL-2CC case ID")
        if cid.startswith("syn_") or cid.startswith("cpaa1:"):
            raise CalibrationGateError(f"Case ID '{cid}' reuses formal/synthetic study prefix")

    manifest_path = Path(__file__).resolve().parent.parent / "packets" / "packet_manifest.json"
    if manifest_path.exists():
        try:
            m_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(m_data, list):
                formal_q_texts = {
                    item.get("question_text")
                    for item in m_data
                    if isinstance(item, dict) and "question_text" in item
                }
                for qt in question_texts:
                    if qt in formal_q_texts:
                        raise CalibrationGateError(
                            "Calibration question text matches formal study question text exactly"
                        )
        except CalibrationGateError:
            raise
        except Exception:
            pass


# ==============================================================================
# HUMAN-AUTHORED FIXTURE PACK SCHEMA (Task 3, 4, 6)
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
        _require_non_empty_str(self.evidence_id, "evidence_id")
        if (
            self.evidence_id.startswith("cpaa1:ev:")
            or self.evidence_id.startswith("ev:tcm:")
            or self.evidence_id.startswith("ev:western:")
        ):
            raise CalibrationGateError(f"Calibration evidence_id '{self.evidence_id}' reuses formal evidence prefix")
        if not self.evidence_id.startswith(CALIBRATION_EVIDENCE_ID_PREFIX):
            raise CalibrationGateError(
                f"evidence_id '{self.evidence_id}' must start with '{CALIBRATION_EVIDENCE_ID_PREFIX}'"
            )
        if type(self.rank) is not int or self.rank < 1 or self.rank > 4:
            raise ValueError(f"rank must be an integer between 1 and 4, got {self.rank!r}")
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
        if not self.packet_id.startswith(CALIBRATION_PACKET_ID_PREFIX):
            raise CalibrationGateError(
                f"packet_id '{self.packet_id}' must start with '{CALIBRATION_PACKET_ID_PREFIX}'"
            )
        if self.perspective not in ALLOWED_PERSPECTIVES:
            raise ValueError(f"Invalid perspective '{self.perspective}': must be 'tcm' or 'western'")
        if self.case_id not in CALIBRATION_CASE_IDS:
            raise ValueError(f"Invalid case_id '{self.case_id}': must be one of {CALIBRATION_CASE_IDS}")
        if not isinstance(self.evidence_items, list):
            raise TypeError("evidence_items must be a list")
        if len(self.evidence_items) != 4:
            raise ValueError(f"Packet must contain exactly 4 evidence items, got {len(self.evidence_items)}")

        ranks: list[int] = []
        for item in self.evidence_items:
            if not isinstance(item, CalibrationEvidenceItem):
                raise TypeError(f"Expected CalibrationEvidenceItem, got {type(item).__name__}")
            item.validate_current_state()
            ranks.append(item.rank)

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
class CalibrationFixturePack:
    """Human-authored fixture pack containing exactly 8 calibration challenge cases."""

    fixture_author: str
    human_authorship_attested: bool
    formal_material_not_used_attested: bool
    model_generated_final_fixture_text: bool
    cases: dict[str, CalibrationCase]
    calibration_design_id: str = CALIBRATION_DESIGN_ID
    study_id: str = STUDY_ID
    protocol_id: str = PROTOCOL_ID
    protocol_hash: str = FROZEN_PROTOCOL_BYTE_SHA256
    fixture_pack_canonical_sha256: str | None = None

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

        if self.fixture_pack_canonical_sha256 is not None:
            if not self.human_authorship_attested:
                raise CalibrationGateError("human_authorship_attested must be True for calibration fixture freeze")
            if not self.formal_material_not_used_attested:
                raise CalibrationGateError("formal_material_not_used_attested must be True for calibration fixture freeze")
            if self.model_generated_final_fixture_text is not False:
                raise CalibrationGateError(
                    "model_generated_final_fixture_text must be False; model text cannot be frozen as calibration material"
                )

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

        # Formal material separation check (Task 5)
        check_formal_material_separation(
            case_ids=list(self.cases.keys()),
            packet_ids=packet_ids,
            evidence_ids=evidence_ids,
            question_texts=question_texts,
        )

        # Self-hash verification if frozen (Task 6)
        if self.fixture_pack_canonical_sha256 is not None:
            expected_hash = self.compute_canonical_sha256()
            if self.fixture_pack_canonical_sha256 != expected_hash:
                raise ValueError(
                    f"fixture_pack_canonical_sha256 mismatch: recorded '{self.fixture_pack_canonical_sha256}' "
                    f"!= computed '{expected_hash}'"
                )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def _to_dict_unhashed(self) -> dict[str, Any]:
        return {
            "calibration_design_id": self.calibration_design_id,
            "study_id": self.study_id,
            "protocol_id": self.protocol_id,
            "protocol_hash": self.protocol_hash,
            "fixture_author": self.fixture_author,
            "human_authorship_attested": self.human_authorship_attested,
            "formal_material_not_used_attested": self.formal_material_not_used_attested,
            "model_generated_final_fixture_text": self.model_generated_final_fixture_text,
            "cases": {cid: case.to_dict() for cid, case in sorted(self.cases.items())},
        }

    def compute_canonical_sha256(self) -> str:
        data = self._to_dict_unhashed()
        return compute_canonical_sha256(data)

    def freeze(self) -> None:
        """Freeze and compute deterministic fixture-pack hash."""
        _require_non_empty_str(self.fixture_author, "fixture_author")
        if not self.human_authorship_attested:
            raise CalibrationGateError("human_authorship_attested must be True for calibration fixture freeze")
        if not self.formal_material_not_used_attested:
            raise CalibrationGateError("formal_material_not_used_attested must be True for calibration fixture freeze")
        if self.model_generated_final_fixture_text is not False:
            raise CalibrationGateError(
                "model_generated_final_fixture_text must be False; model text cannot be frozen as calibration material"
            )
        self.fixture_pack_canonical_sha256 = None
        self.validate_current_state()
        self.fixture_pack_canonical_sha256 = self.compute_canonical_sha256()

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
        return cls(
            calibration_design_id=data.get("calibration_design_id", CALIBRATION_DESIGN_ID),
            study_id=data.get("study_id", STUDY_ID),
            protocol_id=data.get("protocol_id", PROTOCOL_ID),
            protocol_hash=data.get("protocol_hash", FROZEN_PROTOCOL_BYTE_SHA256),
            fixture_author=data.get("fixture_author", ""),
            human_authorship_attested=data.get("human_authorship_attested", False),
            formal_material_not_used_attested=data.get("formal_material_not_used_attested", False),
            model_generated_final_fixture_text=data.get("model_generated_final_fixture_text", True),
            cases=cases,
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
# CALIBRATION REVIEWER WORKSPACE & LOCKED SUBMISSION (Tasks 7, 8, 9)
# ==============================================================================

@dataclass
class CalibrationCaseReviewState:
    """Per-case calibration review state inside a reviewer workspace."""

    case_id: str
    annotation_complete: bool = False
    records: list[dict[str, Any]] = field(default_factory=list)
    no_supportable_unit_reason: str = ""

    def validate_current_state(self) -> None:
        if self.case_id not in CALIBRATION_CASE_IDS:
            raise ValueError(f"Invalid case_id '{self.case_id}': must be one of {CALIBRATION_CASE_IDS}")
        _require_bool(self.annotation_complete, "annotation_complete")
        if not isinstance(self.no_supportable_unit_reason, str):
            raise TypeError(
                f"no_supportable_unit_reason must be a str, got {type(self.no_supportable_unit_reason).__name__}"
            )
        if not isinstance(self.records, list):
            raise TypeError(f"records must be a list, got {type(self.records).__name__}")

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
        return cls(
            case_id=data.get("case_id", ""),
            annotation_complete=data.get("annotation_complete", False),
            records=data.get("records", []),
            no_supportable_unit_reason=data.get("no_supportable_unit_reason", ""),
        )


@dataclass(frozen=True)
class CalibrationLockedSubmission:
    """Immutable cryptographic snapshot of a locked calibration reviewer submission."""

    calibration_design_id: str
    fixture_pack_hash: str
    reviewer_role: Literal["reviewer_a", "reviewer_b"]
    case_ids: tuple[str, ...]
    records_by_case: dict[str, list[dict[str, Any]]]
    case_completion_states: dict[str, bool]
    no_supportable_unit_reasons: dict[str, str]
    submission_version: int
    lock_timestamp: str
    submission_hash: str

    def validate_current_state(self) -> None:
        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )
        _require_non_empty_str(self.fixture_pack_hash, "fixture_pack_hash")
        if self.reviewer_role not in ALLOWED_REVIEWER_ROLES:
            raise ValueError(f"reviewer_role must be 'reviewer_a' or 'reviewer_b', got '{self.reviewer_role}'")
        if self.case_ids != CALIBRATION_CASE_IDS:
            raise ValueError(f"case_ids must exactly match {CALIBRATION_CASE_IDS}, got {self.case_ids}")
        if type(self.submission_version) is not int or self.submission_version < 1:
            raise ValueError(f"submission_version must be an integer >= 1, got {self.submission_version!r}")
        _require_non_empty_str(self.lock_timestamp, "lock_timestamp")

        # Mechanical gate requirements (Task 9)
        for cid in CALIBRATION_CASE_IDS:
            comp = self.case_completion_states.get(cid)
            _require_bool(comp, f"case_completion_states[{cid}]")
            if not comp:
                raise CalibrationLockError(f"Case '{cid}' is not marked annotation_complete in locked submission")
            recs = self.records_by_case.get(cid, [])
            if not isinstance(recs, list):
                raise TypeError(f"records_by_case[{cid}] must be a list")
            reason = self.no_supportable_unit_reasons.get(cid, "")
            if not isinstance(reason, str):
                raise TypeError(f"no_supportable_unit_reasons[{cid}] must be a str")
            if not (len(recs) > 0 or bool(reason.strip())):
                raise CalibrationLockError(
                    f"Case '{cid}' has neither reference units nor no_supportable_unit_reason in locked submission"
                )

        # Verify hash
        expected_hash = compute_canonical_sha256(self._to_dict_unhashed())
        if self.submission_hash != expected_hash:
            raise CalibrationLockError(
                f"submission_hash mismatch: recorded '{self.submission_hash}' != computed '{expected_hash}'"
            )

    def __post_init__(self) -> None:
        self.validate_current_state()

    def _to_dict_unhashed(self) -> dict[str, Any]:
        return {
            "calibration_design_id": self.calibration_design_id,
            "fixture_pack_hash": self.fixture_pack_hash,
            "reviewer_role": self.reviewer_role,
            "case_ids": list(self.case_ids),
            "records_by_case": {k: copy.deepcopy(v) for k, v in sorted(self.records_by_case.items())},
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
    def from_dict(cls, data: dict[str, Any]) -> CalibrationLockedSubmission:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationLockedSubmission")
        case_ids_raw = data.get("case_ids", [])
        return cls(
            calibration_design_id=data.get("calibration_design_id", CALIBRATION_DESIGN_ID),
            fixture_pack_hash=data.get("fixture_pack_hash", ""),
            reviewer_role=data.get("reviewer_role", "reviewer_a"),
            case_ids=tuple(case_ids_raw),
            records_by_case=data.get("records_by_case", {}),
            case_completion_states=data.get("case_completion_states", {}),
            no_supportable_unit_reasons=data.get("no_supportable_unit_reasons", {}),
            submission_version=data.get("submission_version", 1),
            lock_timestamp=data.get("lock_timestamp", ""),
            submission_hash=data.get("submission_hash", ""),
        )


@dataclass
class CalibrationReviewerWorkspace:
    """Isolated working environment for a single calibration reviewer."""

    reviewer_role: Literal["reviewer_a", "reviewer_b"]
    fixture_pack_hash: str
    cases: dict[str, CalibrationCaseReviewState] = field(default_factory=dict)
    calibration_design_id: str = CALIBRATION_DESIGN_ID
    workspace_kind: str = "calibration"
    submission_version: int = 1
    is_locked: bool = False
    locked_snapshot: CalibrationLockedSubmission | None = None
    _anchor_index: FrozenPacketAnchorIndex | None = field(default=None, repr=False)

    def validate_current_state(self) -> None:
        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )
        if self.workspace_kind != "calibration":
            raise ValueError(f"workspace_kind must be 'calibration', got '{self.workspace_kind}'")
        if self.reviewer_role not in ALLOWED_REVIEWER_ROLES:
            raise ValueError(f"reviewer_role must be 'reviewer_a' or 'reviewer_b', got '{self.reviewer_role}'")
        _require_non_empty_str(self.fixture_pack_hash, "fixture_pack_hash")
        _require_bool(self.is_locked, "is_locked")
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

        if self.is_locked:
            if self.locked_snapshot is None:
                raise CalibrationLockError("Workspace is marked is_locked=True but locked_snapshot is None")
            if not isinstance(self.locked_snapshot, CalibrationLockedSubmission):
                raise TypeError("locked_snapshot must be CalibrationLockedSubmission")
            self.locked_snapshot.validate_current_state()
            if self.locked_snapshot.fixture_pack_hash != self.fixture_pack_hash:
                raise CalibrationLockError("locked_snapshot fixture_pack_hash does not match workspace")
            if self.locked_snapshot.reviewer_role != self.reviewer_role:
                raise CalibrationLockError("locked_snapshot reviewer_role does not match workspace")
            if self.locked_snapshot.submission_version != self.submission_version:
                raise CalibrationLockError("locked_snapshot submission_version does not match workspace")

    def __post_init__(self) -> None:
        if not self.cases:
            self.cases = {
                cid: CalibrationCaseReviewState(case_id=cid)
                for cid in CALIBRATION_CASE_IDS
            }
        self.validate_current_state()

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
            is_locked=False,
            locked_snapshot=None,
            _anchor_index=index,
        )

    def bind_anchor_index(self, index: FrozenPacketAnchorIndex) -> None:
        self._anchor_index = index

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

        if self._anchor_index is not None:
            errors = validate_reference_unit_record(rec_dict, mode="draft", packet_index=self._anchor_index)
            if errors:
                raise ValueError(f"Record validation failed: {'; '.join(errors)}")

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

        # Gate requirements (Task 9)
        for cid in CALIBRATION_CASE_IDS:
            c_state = self.cases[cid]
            if not c_state.annotation_complete:
                raise CalibrationLockError(f"Cannot lock: case '{cid}' is not marked annotation_complete")
            has_records = len(c_state.records) > 0
            has_reason = bool(c_state.no_supportable_unit_reason.strip())
            if not (has_records or has_reason):
                raise CalibrationLockError(
                    f"Cannot lock: case '{cid}' has neither reference units nor no_supportable_unit_reason"
                )
            if self._anchor_index is not None:
                for rec in c_state.records:
                    errors = validate_reference_unit_record(rec, mode="draft", packet_index=self._anchor_index)
                    if errors:
                        raise CalibrationLockError(
                            f"Cannot lock: record validation failed for case '{cid}': {'; '.join(errors)}"
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
        )

        self.locked_snapshot = snapshot
        self.is_locked = True
        return snapshot

    def create_amended_version(self) -> CalibrationReviewerWorkspace:
        if not self.is_locked:
            raise CalibrationLockError("Cannot create amended version from an unlocked workspace")
        new_cases = {
            cid: CalibrationCaseReviewState(
                case_id=cid,
                annotation_complete=False,
                records=copy.deepcopy(self.cases[cid].records),
                no_supportable_unit_reason=self.cases[cid].no_supportable_unit_reason,
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
            is_locked=False,
            locked_snapshot=None,
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
    def from_dict(cls, data: dict[str, Any]) -> CalibrationReviewerWorkspace:
        if not isinstance(data, dict):
            raise TypeError("Expected dict for CalibrationReviewerWorkspace")
        cases_raw = data.get("cases", {})
        if not isinstance(cases_raw, dict):
            raise TypeError("cases must be a dictionary")
        cases = {cid: CalibrationCaseReviewState.from_dict(c_data) for cid, c_data in cases_raw.items()}
        snap_raw = data.get("locked_snapshot")
        snap = CalibrationLockedSubmission.from_dict(snap_raw) if snap_raw is not None else None
        return cls(
            calibration_design_id=data.get("calibration_design_id", CALIBRATION_DESIGN_ID),
            workspace_kind=data.get("workspace_kind", "calibration"),
            reviewer_role=data.get("reviewer_role", "reviewer_a"),
            fixture_pack_hash=data.get("fixture_pack_hash", ""),
            submission_version=data.get("submission_version", 1),
            is_locked=data.get("is_locked", False),
            locked_snapshot=snap,
            cases=cases,
        )


# ==============================================================================
# A/B COMPARISON GATE (Task 10)
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
        if not isinstance(self.reviewer_a_submission, CalibrationLockedSubmission):
            raise CalibrationComparisonGateError(
                f"reviewer_a_submission must be CalibrationLockedSubmission, got {type(self.reviewer_a_submission).__name__}"
            )
        if not isinstance(self.reviewer_b_submission, CalibrationLockedSubmission):
            raise CalibrationComparisonGateError(
                f"reviewer_b_submission must be CalibrationLockedSubmission, got {type(self.reviewer_b_submission).__name__}"
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
        keys_to_compare = ("unit_type", "perspective_scope", "unit_text", "support_scope")
        for k in keys_to_compare:
            if rec_a.get(k) != rec_b.get(k):
                return False
        anchors_a = rec_a.get("evidence_anchors", [])
        anchors_b = rec_b.get("evidence_anchors", [])
        if len(anchors_a) != len(anchors_b):
            return False
        return canonical_json_dumps(anchors_a) == canonical_json_dumps(anchors_b)


# ==============================================================================
# CALIBRATION DISAGREEMENT LOG (Task 11 & 12)
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
        if not isinstance(self.protocol_sections_considered, list):
            raise TypeError("protocol_sections_considered must be a list")
        if not isinstance(self.participants, list):
            raise TypeError("participants must be a list")

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
        self.human_resolution = human_resolution
        self.resolution_rationale = resolution_rationale
        self.participants = participants
        self.resolution_date = resolution_date
        self.clarification_refreeze_id = clarification_refreeze_id
        self.clarification_refreeze_attested = clarification_refreeze_attested
        self.status = "resolved"
        self.validate_current_state()

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
    """Container for human-entered calibration disagreements."""

    fixture_pack_hash: str
    entries: list[CalibrationDisagreementEntry] = field(default_factory=list)
    calibration_design_id: str = CALIBRATION_DESIGN_ID

    def validate_current_state(self) -> None:
        if self.calibration_design_id != CALIBRATION_DESIGN_ID:
            raise ValueError(
                f"calibration_design_id mismatch: '{self.calibration_design_id}' != '{CALIBRATION_DESIGN_ID}'"
            )
        _require_non_empty_str(self.fixture_pack_hash, "fixture_pack_hash")
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
            entries=[CalibrationDisagreementEntry.from_dict(e) for e in entries_raw],
        )


# ==============================================================================
# CALIBRATION COMPLETION CHECKLIST & STOP CONDITIONS (Tasks 13 & 14)
# ==============================================================================

@dataclass
class CalibrationCompletionChecklist:
    """Human-attested completion structure governing formal annotation readiness."""

    fixture_pack: CalibrationFixturePack
    reviewer_a_submission: CalibrationLockedSubmission
    reviewer_b_submission: CalibrationLockedSubmission
    disagreement_log: CalibrationDisagreementLog
    all_eight_boundaries_reviewed: bool = False
    boundary_05_07_08_distinction_reviewed: bool = False
    reviewers_agree_rules_applicable: bool = False
    no_calibration_artifact_model_exposed: bool = False
    no_numerical_agreement_threshold_used: bool = False
    attestor_a: str = ""
    attestor_b: str = ""
    attestation_notes: str = ""
    calibration_design_id: str = CALIBRATION_DESIGN_ID
    calibration_ready_for_formal_annotation: bool = False

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
        _require_bool(self.calibration_ready_for_formal_annotation, "calibration_ready_for_formal_annotation")

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

        if not isinstance(self.reviewer_a_submission, CalibrationLockedSubmission):
            raise TypeError("reviewer_a_submission must be CalibrationLockedSubmission")
        self.reviewer_a_submission.validate_current_state()

        if not isinstance(self.reviewer_b_submission, CalibrationLockedSubmission):
            raise TypeError("reviewer_b_submission must be CalibrationLockedSubmission")
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

        # Direct construction bypass prevention (Task 14 & 15)
        if self.calibration_ready_for_formal_annotation:
            self.validate_ready_for_completion()

    def __post_init__(self) -> None:
        self.validate_current_state()

    def validate_ready_for_completion(self) -> None:
        """Master fail-closed validator for marking calibration complete."""
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

        # 2. Fixture pack authorship
        if not self.fixture_pack.human_authorship_attested:
            raise CalibrationCompletionError("fixture_pack.human_authorship_attested must be True")
        if not self.fixture_pack.formal_material_not_used_attested:
            raise CalibrationCompletionError("fixture_pack.formal_material_not_used_attested must be True")
        if self.fixture_pack.model_generated_final_fixture_text is not False:
            raise CalibrationCompletionError("fixture_pack.model_generated_final_fixture_text must be False")

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
        self.calibration_ready_for_formal_annotation = True

    def to_dict(self) -> dict[str, Any]:
        self.validate_current_state()
        if self.calibration_ready_for_formal_annotation:
            self.validate_ready_for_completion()
        return {
            "calibration_design_id": self.calibration_design_id,
            "calibration_ready_for_formal_annotation": self.calibration_ready_for_formal_annotation,
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
        sub_a = CalibrationLockedSubmission.from_dict(data.get("reviewer_a_submission", {}))
        sub_b = CalibrationLockedSubmission.from_dict(data.get("reviewer_b_submission", {}))
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
