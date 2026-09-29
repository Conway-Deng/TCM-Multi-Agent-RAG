from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
_CURRENT_DIR = Path(__file__).resolve().parent

# Ensure backend takes precedence to prevent local schemas.py shadowing backend/schemas
for p in (str(_CURRENT_DIR), str(_BACKEND_DIR), str(_REPO_ROOT)):
    if p in sys.path:
        sys.path.remove(p)

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_BACKEND_DIR))

try:
    from backend.cross_perspective.schemas import (
        EvidenceReference,
        PerspectiveClaim,
        PerspectiveEvidencePacket,
        ProvenanceRecord,
    )
except ModuleNotFoundError:
    from cross_perspective.schemas import (
        EvidenceReference,
        PerspectiveClaim,
        PerspectiveEvidencePacket,
        ProvenanceRecord,
    )

try:
    from .manifest import sha256_text
    from .packet_contract import (
        COMPATIBILITY_CLAIM_KIND,
        COMPATIBILITY_SUPPORT_STATUS,
        EXPECTED_QUESTION_COUNT,
        EXPECTED_QUESTION_MANIFEST_SHA256,
        EXPECTED_TCM_ITEMS,
        EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_TCM_RECORDS,
        EXPECTED_WESTERN_ITEMS,
        EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_WESTERN_RECORDS,
        HITS_PER_RECORD,
        PACKET_CONTRACT_ID,
        QUESTION_MANIFEST_RELPATH,
        SCHEMA_VERSION,
        SEMANTIC_SUPPORT_STATUS,
        SUPPORT_BASIS,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
        format_compatibility_claim_id,
        format_evidence_id,
        format_packet_id,
    )
    from .packet_serialization import (
        packet_canonical_sha256,
        sha256_bytes,
        strict_deep_compare,
        strict_json_loads,
    )
    from .schemas import (
        FrozenEvidenceItem,
        FrozenEvidencePacket,
        RawRetrievalItem,
        RawRetrievalRecord,
    )
except ImportError:
    from research.experiments.cross_perspective_advisory_ablation_v1.manifest import sha256_text
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_contract import (
        COMPATIBILITY_CLAIM_KIND,
        COMPATIBILITY_SUPPORT_STATUS,
        EXPECTED_QUESTION_COUNT,
        EXPECTED_QUESTION_MANIFEST_SHA256,
        EXPECTED_TCM_ITEMS,
        EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_TCM_RECORDS,
        EXPECTED_WESTERN_ITEMS,
        EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_WESTERN_RECORDS,
        HITS_PER_RECORD,
        PACKET_CONTRACT_ID,
        QUESTION_MANIFEST_RELPATH,
        SCHEMA_VERSION,
        SEMANTIC_SUPPORT_STATUS,
        SUPPORT_BASIS,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
        format_compatibility_claim_id,
        format_evidence_id,
        format_packet_id,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
        packet_canonical_sha256,
        sha256_bytes,
        strict_deep_compare,
        strict_json_loads,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
        FrozenEvidenceItem,
        FrozenEvidencePacket,
        RawRetrievalItem,
        RawRetrievalRecord,
    )


class TrustedParentStore:
    """Retains frozen parent file bytes as immutable anchors.
    Authoritative validation ALWAYS parses fresh parent dictionaries from verified bytes."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

        # 1. Read and verify question manifest bytes
        q_manifest_path = repo_root / QUESTION_MANIFEST_RELPATH
        if not q_manifest_path.exists():
            raise FileNotFoundError(f"Question manifest not found at {q_manifest_path}")
        self._question_manifest_bytes: bytes = q_manifest_path.read_bytes()
        actual_q_sha = sha256_bytes(self._question_manifest_bytes)
        if actual_q_sha != EXPECTED_QUESTION_MANIFEST_SHA256:
            raise ValueError(
                f"Question manifest SHA mismatch: actual {actual_q_sha} != expected {EXPECTED_QUESTION_MANIFEST_SHA256}"
            )

        # 2. Read and verify TCM raw retrieval bytes
        tcm_path = repo_root / TCM_RAW_RETRIEVAL_RELPATH
        if not tcm_path.exists():
            raise FileNotFoundError(f"TCM raw retrieval artifact not found at {tcm_path}")
        self._tcm_raw_bytes: bytes = tcm_path.read_bytes()
        actual_tcm_sha = sha256_bytes(self._tcm_raw_bytes)
        if actual_tcm_sha != EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256:
            raise ValueError(
                f"TCM raw retrieval byte SHA mismatch: actual {actual_tcm_sha} != expected {EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256}"
            )

        # 3. Read and verify Western raw retrieval bytes
        western_path = repo_root / WESTERN_RAW_RETRIEVAL_RELPATH
        if not western_path.exists():
            raise FileNotFoundError(f"Western raw retrieval artifact not found at {western_path}")
        self._western_raw_bytes: bytes = western_path.read_bytes()
        actual_western_sha = sha256_bytes(self._western_raw_bytes)
        if actual_western_sha != EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256:
            raise ValueError(
                f"Western raw retrieval byte SHA mismatch: actual {actual_western_sha} != expected {EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256}"
            )

        # 4. Map question IDs to immutable raw byte line slices
        self._manifest_line_bytes_by_qid: dict[str, bytes] = {}
        self._manifest_qids: list[str] = []
        for line_bytes in self._question_manifest_bytes.splitlines():
            line_bytes = line_bytes.strip()
            if not line_bytes:
                continue
            q_rec = strict_json_loads(line_bytes)
            qid = q_rec["question_id"]
            if qid in self._manifest_line_bytes_by_qid:
                raise ValueError(f"Duplicate question_id in question manifest: {qid}")
            self._manifest_line_bytes_by_qid[qid] = line_bytes
            self._manifest_qids.append(qid)

        if len(self._manifest_qids) != EXPECTED_QUESTION_COUNT:
            raise ValueError(
                f"Expected {EXPECTED_QUESTION_COUNT} questions, got {len(self._manifest_qids)}"
            )

        # 5. Map TCM line bytes
        self._tcm_line_bytes_by_qid: dict[str, bytes] = {}
        for line_bytes in self._tcm_raw_bytes.splitlines():
            line_bytes = line_bytes.strip()
            if not line_bytes:
                continue
            rec_dict = strict_json_loads(line_bytes)
            qid = rec_dict["question_id"]
            if qid in self._tcm_line_bytes_by_qid:
                raise ValueError(f"Duplicate question_id in TCM raw retrieval: {qid}")
            self._tcm_line_bytes_by_qid[qid] = line_bytes

        if len(self._tcm_line_bytes_by_qid) != EXPECTED_TCM_RECORDS:
            raise ValueError(
                f"Expected {EXPECTED_TCM_RECORDS} TCM records, got {len(self._tcm_line_bytes_by_qid)}"
            )

        # 6. Map Western line bytes
        self._western_line_bytes_by_qid: dict[str, bytes] = {}
        for line_bytes in self._western_raw_bytes.splitlines():
            line_bytes = line_bytes.strip()
            if not line_bytes:
                continue
            rec_dict = strict_json_loads(line_bytes)
            qid = rec_dict["question_id"]
            if qid in self._western_line_bytes_by_qid:
                raise ValueError(f"Duplicate question_id in Western raw retrieval: {qid}")
            self._western_line_bytes_by_qid[qid] = line_bytes

        if len(self._western_line_bytes_by_qid) != EXPECTED_WESTERN_RECORDS:
            raise ValueError(
                f"Expected {EXPECTED_WESTERN_RECORDS} Western records, got {len(self._western_line_bytes_by_qid)}"
            )

        # 7. Check 1-to-1 correspondence with manifest
        for qid in self._manifest_qids:
            if qid not in self._tcm_line_bytes_by_qid:
                raise ValueError(f"Missing TCM record for manifest question {qid}")
            if qid not in self._western_line_bytes_by_qid:
                raise ValueError(f"Missing Western record for manifest question {qid}")

    @property
    def question_manifest_bytes(self) -> bytes:
        """Immutable raw question manifest bytes."""
        return self._question_manifest_bytes

    @property
    def tcm_raw_bytes(self) -> bytes:
        """Immutable raw TCM retrieval bytes."""
        return self._tcm_raw_bytes

    @property
    def western_raw_bytes(self) -> bytes:
        """Immutable raw Western retrieval bytes."""
        return self._western_raw_bytes

    def get_manifest_question_ids(self) -> list[str]:
        """Return question IDs in physical manifest order."""
        return list(self._manifest_qids)

    def get_fresh_manifest_question_dict(self, question_id: str) -> dict[str, Any]:
        """Parse a FRESH raw JSON dictionary for a manifest question from verified bytes."""
        if question_id not in self._manifest_line_bytes_by_qid:
            raise KeyError(f"Question ID {question_id} not found in verified question manifest bytes")
        return strict_json_loads(self._manifest_line_bytes_by_qid[question_id])

    def get_fresh_raw_record_dict(self, perspective: str, question_id: str) -> dict[str, Any]:
        """Parse a FRESH raw JSON dictionary for a retrieval record from verified bytes."""
        if perspective == "tcm":
            mapping = self._tcm_line_bytes_by_qid
        elif perspective == "western":
            mapping = self._western_line_bytes_by_qid
        else:
            raise ValueError(f"Unknown perspective: {perspective}")

        if question_id not in mapping:
            raise KeyError(f"Question ID {question_id} not found in verified {perspective} raw retrieval bytes")
        return strict_json_loads(mapping[question_id])

    @property
    def question_manifest_records(self) -> list[dict[str, Any]]:
        """Return freshly parsed question manifest records in physical manifest order."""
        return [self.get_fresh_manifest_question_dict(qid) for qid in self._manifest_qids]

    @property
    def questions_by_id(self) -> dict[str, dict[str, Any]]:
        """Return freshly parsed question manifest records by question ID."""
        return {qid: self.get_fresh_manifest_question_dict(qid) for qid in self._manifest_qids}

    @property
    def tcm_raw_records(self) -> dict[str, RawRetrievalRecord]:
        """Return freshly parsed Pydantic RawRetrievalRecords by question ID."""
        return {
            qid: RawRetrievalRecord.model_validate(self.get_fresh_raw_record_dict("tcm", qid))
            for qid in self._manifest_qids
        }

    @property
    def western_raw_records(self) -> dict[str, RawRetrievalRecord]:
        """Return freshly parsed Pydantic RawRetrievalRecords by question ID."""
        return {
            qid: RawRetrievalRecord.model_validate(self.get_fresh_raw_record_dict("western", qid))
            for qid in self._manifest_qids
        }


def project_raw_record_to_frozen_packet(
    record: RawRetrievalRecord | dict[str, Any],
    raw_artifact_sha256: str,
) -> FrozenEvidencePacket:
    """Deterministically transform a RawRetrievalRecord into an immutable FrozenEvidencePacket.
    
    Preserves:
    - all 4 hits in exact rank order
    - verbatim chunk text byte/logical content (no truncation, no stripping)
    - retrieval score and score_is_zero status
    - corpus_record_ordinal
    - source metadata and provenance (including None values)
    - chunk hashes
    - defensive deep-copy of provenance
    """
    if isinstance(record, BaseModel):
        rec_dict = record.model_dump(mode="json")
    else:
        rec_dict = record

    results = rec_dict.get("results", [])
    if len(results) != HITS_PER_RECORD:
        raise ValueError(
            f"Expected exactly {HITS_PER_RECORD} hits in raw retrieval record, got {len(results)}"
        )

    evidence_items: list[FrozenEvidenceItem] = []
    for hit in results:
        ev_id = format_evidence_id(
            question_id=rec_dict["question_id"],
            perspective=rec_dict["perspective"],
            rank=hit["rank"],
            chunk_id=hit["chunk_id"],
        )
        item = FrozenEvidenceItem(
            evidence_id=ev_id,
            rank=hit["rank"],
            retrieval_score=hit["retrieval_score"],
            score_is_zero=hit["score_is_zero"],
            chunk_id=hit["chunk_id"],
            corpus_record_ordinal=hit["corpus_record_ordinal"],
            exact_chunk_text=hit["exact_original_chunk_text"],
            chunk_text_sha256=hit["chunk_text_utf8_sha256"],
            chunk_record_canonical_sha256=hit["chunk_record_canonical_sha256"],
            source_id=hit["source_id"],
            source_record_id=hit.get("source_record_id"),
            source_title=hit.get("source_title"),
            source_url=hit.get("source_url"),
            doi=hit.get("doi"),
            pmcid=hit.get("pmcid"),
            section_or_category=hit.get("section_or_category"),
            source_citation_or_version=hit.get("source_citation_or_version"),
            license_or_access_status=hit.get("license_or_access_status"),
            review_status=hit.get("review_status"),
            provenance=copy.deepcopy(hit.get("provenance", {})),
            support_basis="verbatim_source_copy",
            semantic_support_status="not_assessed",
        )
        evidence_items.append(item)

    pkt_id = format_packet_id(rec_dict["question_id"], rec_dict["perspective"])

    packet_dict: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "transformation_contract_id": PACKET_CONTRACT_ID,
        "packet_id": pkt_id,
        "question_id": rec_dict["question_id"],
        "candidate_id": rec_dict["candidate_id"],
        "question_text": rec_dict["question_text"],
        "topic": rec_dict["topic"],
        "task_type": rec_dict["task_type"],
        "perspective": rec_dict["perspective"],
        "question_manifest_sha256": rec_dict["question_manifest_sha256"],
        "retrieval_algorithm_id": rec_dict["retrieval_algorithm_id"],
        "retrieval_artifact_sha256": raw_artifact_sha256,
        "retrieval_record_id": rec_dict["retrieval_record_id"],
        "retrieval_record_canonical_sha256": rec_dict.get("record_canonical_sha256") or rec_dict.get("retrieval_record_canonical_sha256"),
        "corpus_id": rec_dict["corpus_id"],
        "corpus_version": rec_dict["corpus_version"],
        "corpus_sha256": rec_dict["corpus_sha256"],
        "evidence_items": tuple(item.model_dump(mode="json") for item in evidence_items),
    }
    canonical_sha = packet_canonical_sha256(packet_dict)
    packet_dict["packet_canonical_sha256"] = canonical_sha

    return FrozenEvidencePacket.model_validate(packet_dict)


def project_frozen_packet_to_compatibility_wrapper(
    packet: FrozenEvidencePacket,
) -> PerspectiveEvidencePacket:
    """Deterministically convert a native FrozenEvidencePacket into a PerspectiveEvidencePacket wrapper.
    
    Contains exactly 4 source_excerpt claims:
    - claim_text == exact native evidence text (no truncation)
    - claim_kind == "source_excerpt"
    - support_status == "supported" (structural-only indicator)
    - evidence_refs and provenance link exact source and chunk IDs
    """
    claims: list[PerspectiveClaim] = []
    provenance_list: list[ProvenanceRecord] = []

    for item in packet.evidence_items:
        claim_id = format_compatibility_claim_id(item.evidence_id)
        ref = EvidenceReference(
            source_id=item.source_id,
            chunk_id=item.chunk_id,
            title=item.source_title,
        )
        claim = PerspectiveClaim(
            claim_id=claim_id,
            claim_text=item.exact_chunk_text,
            evidence_refs=[ref],
            support_status="supported",
            claim_kind="source_excerpt",
        )
        claims.append(claim)

        prov = ProvenanceRecord(
            source_id=item.source_id,
            chunk_id=item.chunk_id,
            title=item.source_title,
            source_url=item.source_url or "",
            source_type="research_corpus",
            section=item.section_or_category or "",
            excerpt=item.exact_chunk_text,
            identifier=item.doi or item.pmcid or item.source_record_id or "",
            license=item.license_or_access_status or "",
        )
        provenance_list.append(prov)

    wrapper = PerspectiveEvidencePacket(
        perspective=packet.perspective,
        available=True,
        execution_status="available",
        interpretation="CPAA1 frozen lossless evidence packet (source-passage projection)",
        claims=claims,
        uncertainty=[],
        missing_information=[],
        limitations=[],
        provenance=provenance_list,
        failure=None,
    )
    return wrapper


def validate_frozen_evidence_item_integrity(
    item: FrozenEvidenceItem | dict[str, Any],
    expected_question_id: str,
    expected_perspective: str,
    raw_item: RawRetrievalItem | dict[str, Any] | None = None,
) -> None:
    """Independently recompute and verify the integrity of a FrozenEvidenceItem.
    Compares presence and types directly against raw JSON dictionaries."""
    if isinstance(item, BaseModel):
        item_dict = item.model_dump(mode="json")
    else:
        item_dict = item

    rank = item_dict.get("rank", 0)
    chunk_id = item_dict.get("chunk_id", "")
    ev_id = item_dict.get("evidence_id", "")

    expected_id = format_evidence_id(
        question_id=expected_question_id,
        perspective=expected_perspective,
        rank=rank,
        chunk_id=chunk_id,
    )
    if ev_id != expected_id:
        raise ValueError(
            f"Evidence ID mismatch: actual {ev_id} != expected {expected_id}"
        )
    if rank < 1 or rank > HITS_PER_RECORD:
        raise ValueError(f"Rank out of bounds: {rank}")

    chunk_text = item_dict.get("exact_chunk_text", "")
    recomputed_sha = sha256_text(chunk_text)
    if item_dict.get("chunk_text_sha256") != recomputed_sha:
        raise ValueError(
            f"Chunk text SHA256 mismatch on {ev_id}: recorded {item_dict.get('chunk_text_sha256')} != recomputed {recomputed_sha}"
        )

    if item_dict.get("support_basis") != SUPPORT_BASIS:
        raise ValueError(f"Invalid support_basis: {item_dict.get('support_basis')}")
    if item_dict.get("semantic_support_status") != SEMANTIC_SUPPORT_STATUS:
        raise ValueError(f"Invalid semantic_support_status: {item_dict.get('semantic_support_status')}")

    if raw_item is not None:
        if isinstance(raw_item, BaseModel):
            raw_dict = raw_item.model_dump(mode="json")
        else:
            raw_dict = raw_item

        fields_to_compare = [
            ("rank", "rank"),
            ("retrieval_score", "retrieval_score"),
            ("score_is_zero", "score_is_zero"),
            ("chunk_id", "chunk_id"),
            ("corpus_record_ordinal", "corpus_record_ordinal"),
            ("exact_chunk_text", "exact_original_chunk_text"),
            ("chunk_text_sha256", "chunk_text_utf8_sha256"),
            ("chunk_record_canonical_sha256", "chunk_record_canonical_sha256"),
            ("source_id", "source_id"),
            ("source_record_id", "source_record_id"),
            ("source_title", "source_title"),
            ("source_url", "source_url"),
            ("doi", "doi"),
            ("pmcid", "pmcid"),
            ("section_or_category", "section_or_category"),
            ("source_citation_or_version", "source_citation_or_version"),
            ("license_or_access_status", "license_or_access_status"),
            ("review_status", "review_status"),
        ]

        for item_key, raw_key in fields_to_compare:
            if raw_key not in raw_dict:
                raise KeyError(f"Authoritative raw parent hit is missing expected key {raw_key!r} for {ev_id}")
            if item_key not in item_dict:
                raise KeyError(f"Evidence item is missing required key {item_key!r} for {ev_id}")
            val_item = item_dict[item_key]
            val_raw = raw_dict[raw_key]
            strict_deep_compare(val_item, val_raw, path=f"{ev_id}.{item_key}")

        # Complete provenance structure comparison
        if "provenance" not in raw_dict:
            raise KeyError(f"Authoritative raw parent hit is missing 'provenance' key for {ev_id}")
        if "provenance" not in item_dict:
            raise KeyError(f"Evidence item is missing 'provenance' key for {ev_id}")
        strict_deep_compare(
            item_dict["provenance"],
            raw_dict["provenance"],
            path=f"{ev_id}.provenance",
        )


def validate_frozen_packet_integrity(
    packet: FrozenEvidencePacket | dict[str, Any],
    raw_record: RawRetrievalRecord | dict[str, Any] | None = None,
    raw_artifact_sha256: str | None = None,
    manifest_question: dict[str, Any] | None = None,
) -> None:
    """Independently recompute and verify the integrity of a FrozenEvidencePacket."""
    if isinstance(packet, BaseModel):
        packet_dict = packet.model_dump(mode="json")
    else:
        packet_dict = packet

    expected_pkt_id = format_packet_id(packet_dict["question_id"], packet_dict["perspective"])
    if packet_dict["packet_id"] != expected_pkt_id:
        raise ValueError(
            f"Packet ID mismatch: actual {packet_dict['packet_id']} != expected {expected_pkt_id}"
        )

    if packet_dict["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"Schema version mismatch: {packet_dict['schema_version']} != {SCHEMA_VERSION}")
    if packet_dict["transformation_contract_id"] != PACKET_CONTRACT_ID:
        raise ValueError(f"Contract ID mismatch: {packet_dict['transformation_contract_id']} != {PACKET_CONTRACT_ID}")

    evidence_items = packet_dict.get("evidence_items", [])
    if len(evidence_items) != HITS_PER_RECORD:
        raise ValueError(f"Expected {HITS_PER_RECORD} items, found {len(evidence_items)}")
    ranks = [item.get("rank") if isinstance(item, dict) else item.rank for item in evidence_items]
    if ranks != list(range(1, HITS_PER_RECORD + 1)):
        raise ValueError(f"Items ranks must be 1..{HITS_PER_RECORD}, got {ranks}")
    chunk_ids = [item.get("chunk_id") if isinstance(item, dict) else item.chunk_id for item in evidence_items]
    if len(set(chunk_ids)) != HITS_PER_RECORD:
        raise ValueError(f"Duplicate chunk IDs found in packet: {chunk_ids}")
    ev_ids = [item.get("evidence_id") if isinstance(item, dict) else item.evidence_id for item in evidence_items]
    if len(set(ev_ids)) != HITS_PER_RECORD:
        raise ValueError(f"Duplicate evidence IDs found in packet: {ev_ids}")

    # Validate each evidence item
    if raw_record is not None:
        if isinstance(raw_record, BaseModel):
            raw_dict = raw_record.model_dump(mode="json")
        else:
            raw_dict = raw_record
        raw_hits = raw_dict.get("results", [])
    else:
        raw_dict = None
        raw_hits = None

    for idx, item in enumerate(evidence_items):
        raw_hit = None
        if raw_hits is not None and len(raw_hits) > idx:
            raw_hit = raw_hits[idx]
        validate_frozen_evidence_item_integrity(
            item,
            expected_question_id=packet_dict["question_id"],
            expected_perspective=packet_dict["perspective"],
            raw_item=raw_hit,
        )
        item_id = item.get("evidence_id") if isinstance(item, dict) else item.evidence_id
        expected_claim_id = format_compatibility_claim_id(item_id)
        if not expected_claim_id.startswith("cpaa1:sx:"):
            raise ValueError(f"Invalid wrapper claim ID format: {expected_claim_id}")

    # Validate against parent raw record
    if raw_dict is not None:
        correspondence_fields = [
            ("question_id", "question_id"),
            ("candidate_id", "candidate_id"),
            ("question_text", "question_text"),
            ("topic", "topic"),
            ("task_type", "task_type"),
            ("perspective", "perspective"),
            ("question_manifest_sha256", "question_manifest_sha256"),
            ("retrieval_algorithm_id", "retrieval_algorithm_id"),
            ("retrieval_record_id", "retrieval_record_id"),
            ("retrieval_record_canonical_sha256", "record_canonical_sha256"),
            ("corpus_id", "corpus_id"),
            ("corpus_version", "corpus_version"),
            ("corpus_sha256", "corpus_sha256"),
        ]
        for p_key, r_key in correspondence_fields:
            if r_key not in raw_dict:
                raise KeyError(f"Raw record missing key {r_key!r}")
            if p_key not in packet_dict:
                raise KeyError(f"Packet missing key {p_key!r}")
            strict_deep_compare(
                packet_dict[p_key],
                raw_dict[r_key],
                path=f"packet.{p_key}",
            )

    # Validate against parent question manifest record
    if manifest_question is not None:
        manifest_candidate_id = (
            manifest_question.get("candidate_id")
            or manifest_question.get("selection_metadata", {}).get("candidate_id")
        )
        if manifest_candidate_id is None:
            raise KeyError("Manifest question missing candidate_id")
        if "candidate_id" not in packet_dict:
            raise KeyError("Packet missing candidate_id")
        strict_deep_compare(
            packet_dict["candidate_id"],
            manifest_candidate_id,
            path="packet.candidate_id_vs_manifest",
        )
        for field in ("question_id", "question_text", "topic", "task_type"):
            if field not in manifest_question:
                raise KeyError(f"Manifest question missing {field!r}")
            if field not in packet_dict:
                raise KeyError(f"Packet missing {field!r}")
            strict_deep_compare(
                packet_dict[field],
                manifest_question[field],
                path=f"packet.{field}_vs_manifest",
            )

    if raw_artifact_sha256 is not None:
        if packet_dict["retrieval_artifact_sha256"] != raw_artifact_sha256:
            raise ValueError(
                f"raw_artifact_sha256 mismatch: {packet_dict['retrieval_artifact_sha256']} != {raw_artifact_sha256}"
            )

    # Independent canonical hash recomputation
    recomputed_hash = packet_canonical_sha256(packet_dict)
    if packet_dict["packet_canonical_sha256"] != recomputed_hash:
        raise ValueError(
            f"Packet canonical SHA256 mismatch! Stored {packet_dict['packet_canonical_sha256']} != recomputed {recomputed_hash}"
        )


def validate_packet_against_trusted_parent(
    packet: FrozenEvidencePacket | dict[str, Any],
    trusted_store: TrustedParentStore,
) -> None:
    """Validate packet against trusted byte anchors retained in TrustedParentStore.
    Authoritative raw record and manifest question are ALWAYS parsed fresh from verified bytes."""
    if isinstance(packet, BaseModel):
        pkt_dict = packet.model_dump(mode="json")
    else:
        pkt_dict = packet

    perspective = pkt_dict["perspective"]
    question_id = pkt_dict["question_id"]

    if perspective == "tcm":
        expected_artifact_sha = EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256
    elif perspective == "western":
        expected_artifact_sha = EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256
    else:
        raise ValueError(f"Unknown perspective: {perspective}")

    # Fetch fresh raw dict directly from SHA-bound file bytes
    fresh_raw_dict = trusted_store.get_fresh_raw_record_dict(perspective, question_id)
    # Fetch fresh manifest dict directly from SHA-bound manifest bytes
    fresh_manifest_dict = trusted_store.get_fresh_manifest_question_dict(question_id)

    validate_frozen_packet_integrity(
        packet=packet,
        raw_record=fresh_raw_dict,
        raw_artifact_sha256=expected_artifact_sha,
        manifest_question=fresh_manifest_dict,
    )
