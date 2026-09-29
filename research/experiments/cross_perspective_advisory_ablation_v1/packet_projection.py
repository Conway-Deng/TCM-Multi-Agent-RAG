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
    """Loads and retains frozen parent file bytes as immutable anchors,
    parsing parent records using strict duplicate-key-rejecting JSON parsing."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

        # 1. Read and verify question manifest bytes
        q_manifest_path = repo_root / QUESTION_MANIFEST_RELPATH
        self.question_manifest_bytes = q_manifest_path.read_bytes()
        actual_q_sha = sha256_bytes(self.question_manifest_bytes)
        if actual_q_sha != EXPECTED_QUESTION_MANIFEST_SHA256:
            raise ValueError(
                f"Question manifest SHA256 mismatch: {actual_q_sha} != {EXPECTED_QUESTION_MANIFEST_SHA256}"
            )

        # 2. Read and verify TCM raw retrieval bytes
        tcm_path = repo_root / TCM_RAW_RETRIEVAL_RELPATH
        self.tcm_raw_bytes = tcm_path.read_bytes()
        actual_tcm_sha = sha256_bytes(self.tcm_raw_bytes)
        if actual_tcm_sha != EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256:
            raise ValueError(
                f"TCM raw retrieval byte SHA256 mismatch: {actual_tcm_sha} != {EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256}"
            )

        # 3. Read and verify Western raw retrieval bytes
        western_path = repo_root / WESTERN_RAW_RETRIEVAL_RELPATH
        self.western_raw_bytes = western_path.read_bytes()
        actual_western_sha = sha256_bytes(self.western_raw_bytes)
        if actual_western_sha != EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256:
            raise ValueError(
                f"Western raw retrieval byte SHA256 mismatch: {actual_western_sha} != {EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256}"
            )

        # 4. Parse question manifest records in physical manifest order
        self.question_manifest_records: list[dict[str, Any]] = []
        self.questions_by_id: dict[str, dict[str, Any]] = {}
        for line in self.question_manifest_bytes.decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            q_rec = strict_json_loads(line)
            qid = q_rec["question_id"]
            if qid in self.questions_by_id:
                raise ValueError(f"Duplicate question_id in question manifest: {qid}")
            self.question_manifest_records.append(q_rec)
            self.questions_by_id[qid] = q_rec

        if len(self.question_manifest_records) != EXPECTED_QUESTION_COUNT:
            raise ValueError(
                f"Expected {EXPECTED_QUESTION_COUNT} questions, got {len(self.question_manifest_records)}"
            )

        # 5. Parse TCM raw retrieval records
        self.tcm_raw_records: dict[str, RawRetrievalRecord] = {}
        for line in self.tcm_raw_bytes.decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec_dict = strict_json_loads(line)
            rec = RawRetrievalRecord.model_validate(rec_dict)
            if rec.question_id in self.tcm_raw_records:
                raise ValueError(f"Duplicate question_id in TCM raw retrieval: {rec.question_id}")
            self.tcm_raw_records[rec.question_id] = rec

        if len(self.tcm_raw_records) != EXPECTED_TCM_RECORDS:
            raise ValueError(
                f"Expected {EXPECTED_TCM_RECORDS} TCM records, got {len(self.tcm_raw_records)}"
            )

        # 6. Parse Western raw retrieval records
        self.western_raw_records: dict[str, RawRetrievalRecord] = {}
        for line in self.western_raw_bytes.decode("utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rec_dict = strict_json_loads(line)
            rec = RawRetrievalRecord.model_validate(rec_dict)
            if rec.question_id in self.western_raw_records:
                raise ValueError(f"Duplicate question_id in Western raw retrieval: {rec.question_id}")
            self.western_raw_records[rec.question_id] = rec

        if len(self.western_raw_records) != EXPECTED_WESTERN_RECORDS:
            raise ValueError(
                f"Expected {EXPECTED_WESTERN_RECORDS} Western records, got {len(self.western_raw_records)}"
            )

        # 7. Verify 1-to-1 correspondence with question manifest
        for q_rec in self.question_manifest_records:
            qid = q_rec["question_id"]
            if qid not in self.tcm_raw_records:
                raise ValueError(f"Missing TCM record for manifest question {qid}")
            if qid not in self.western_raw_records:
                raise ValueError(f"Missing Western record for manifest question {qid}")


def project_raw_record_to_frozen_packet(
    record: RawRetrievalRecord,
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
    if len(record.results) != HITS_PER_RECORD:
        raise ValueError(
            f"Expected exactly {HITS_PER_RECORD} hits in RawRetrievalRecord, got {len(record.results)}"
        )

    evidence_items: list[FrozenEvidenceItem] = []
    for hit in record.results:
        ev_id = format_evidence_id(
            question_id=record.question_id,
            perspective=record.perspective,
            rank=hit.rank,
            chunk_id=hit.chunk_id,
        )
        item = FrozenEvidenceItem(
            evidence_id=ev_id,
            rank=hit.rank,
            retrieval_score=hit.retrieval_score,
            score_is_zero=hit.score_is_zero,
            chunk_id=hit.chunk_id,
            corpus_record_ordinal=hit.corpus_record_ordinal,
            exact_chunk_text=hit.exact_original_chunk_text,
            chunk_text_sha256=hit.chunk_text_utf8_sha256,
            chunk_record_canonical_sha256=hit.chunk_record_canonical_sha256,
            source_id=hit.source_id,
            source_record_id=hit.source_record_id,
            source_title=hit.source_title,
            source_url=hit.source_url,
            doi=hit.doi,
            pmcid=hit.pmcid,
            section_or_category=hit.section_or_category,
            source_citation_or_version=hit.source_citation_or_version,
            license_or_access_status=hit.license_or_access_status,
            review_status=hit.review_status,
            provenance=copy.deepcopy(hit.provenance),
            support_basis="verbatim_source_copy",
            semantic_support_status="not_assessed",
        )
        evidence_items.append(item)

    pkt_id = format_packet_id(record.question_id, record.perspective)

    packet_dict: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "transformation_contract_id": PACKET_CONTRACT_ID,
        "packet_id": pkt_id,
        "question_id": record.question_id,
        "candidate_id": record.candidate_id,
        "question_text": record.question_text,
        "topic": record.topic,
        "task_type": record.task_type,
        "perspective": record.perspective,
        "question_manifest_sha256": record.question_manifest_sha256,
        "retrieval_algorithm_id": record.retrieval_algorithm_id,
        "retrieval_artifact_sha256": raw_artifact_sha256,
        "retrieval_record_id": record.retrieval_record_id,
        "retrieval_record_canonical_sha256": record.record_canonical_sha256,
        "corpus_id": record.corpus_id,
        "corpus_version": record.corpus_version,
        "corpus_sha256": record.corpus_sha256,
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
    item: FrozenEvidenceItem,
    expected_question_id: str,
    expected_perspective: str,
    raw_item: RawRetrievalItem | dict[str, Any] | None = None,
) -> None:
    """Independently recompute and verify the integrity of a FrozenEvidenceItem."""
    expected_id = format_evidence_id(
        question_id=expected_question_id,
        perspective=expected_perspective,
        rank=item.rank,
        chunk_id=item.chunk_id,
    )
    if item.evidence_id != expected_id:
        raise ValueError(
            f"Evidence ID mismatch: actual {item.evidence_id} != expected {expected_id}"
        )
    if item.rank < 1 or item.rank > HITS_PER_RECORD:
        raise ValueError(f"Rank out of bounds: {item.rank}")

    recomputed_sha = sha256_text(item.exact_chunk_text)
    if item.chunk_text_sha256 != recomputed_sha:
        raise ValueError(
            f"Chunk text SHA256 mismatch on {item.evidence_id}: recorded {item.chunk_text_sha256} != recomputed {recomputed_sha}"
        )

    if item.support_basis != SUPPORT_BASIS:
        raise ValueError(f"Invalid support_basis: {item.support_basis}")
    if item.semantic_support_status != SEMANTIC_SUPPORT_STATUS:
        raise ValueError(f"Invalid semantic_support_status: {item.semantic_support_status}")

    if raw_item is not None:
        if isinstance(raw_item, BaseModel):
            raw_dict = raw_item.model_dump(mode="json")
        else:
            raw_dict = raw_item

        item_dict = item.model_dump(mode="json")

        # Compare ALL projected fields derived from raw hit
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
            val_item = item_dict.get(item_key)
            val_raw = raw_dict.get(raw_key)
            strict_deep_compare(val_item, val_raw, path=f"{item.evidence_id}.{item_key}")

        # Complete provenance structure comparison
        strict_deep_compare(
            item_dict.get("provenance", {}),
            raw_dict.get("provenance", {}),
            path=f"{item.evidence_id}.provenance",
        )


def validate_frozen_packet_integrity(
    packet: FrozenEvidencePacket,
    raw_record: RawRetrievalRecord | dict[str, Any] | None = None,
    raw_artifact_sha256: str | None = None,
    manifest_question: dict[str, Any] | None = None,
) -> None:
    """Independently recompute and verify the integrity of a FrozenEvidencePacket."""
    expected_pkt_id = format_packet_id(packet.question_id, packet.perspective)
    if packet.packet_id != expected_pkt_id:
        raise ValueError(
            f"Packet ID mismatch: actual {packet.packet_id} != expected {expected_pkt_id}"
        )

    if packet.schema_version != SCHEMA_VERSION:
        raise ValueError(f"Schema version mismatch: {packet.schema_version} != {SCHEMA_VERSION}")
    if packet.transformation_contract_id != PACKET_CONTRACT_ID:
        raise ValueError(f"Contract ID mismatch: {packet.transformation_contract_id} != {PACKET_CONTRACT_ID}")

    if len(packet.evidence_items) != HITS_PER_RECORD:
        raise ValueError(f"Expected {HITS_PER_RECORD} items, found {len(packet.evidence_items)}")
    ranks = [item.rank for item in packet.evidence_items]
    if ranks != list(range(1, HITS_PER_RECORD + 1)):
        raise ValueError(f"Items ranks must be 1..{HITS_PER_RECORD}, got {ranks}")
    chunk_ids = [item.chunk_id for item in packet.evidence_items]
    if len(set(chunk_ids)) != HITS_PER_RECORD:
        raise ValueError(f"Duplicate chunk IDs found in packet: {chunk_ids}")
    ev_ids = [item.evidence_id for item in packet.evidence_items]
    if len(set(ev_ids)) != HITS_PER_RECORD:
        raise ValueError(f"Duplicate evidence IDs found in packet: {ev_ids}")

    # Validate each evidence item
    if raw_record is not None:
        if isinstance(raw_record, BaseModel):
            raw_hits = raw_record.results
            raw_dict = raw_record.model_dump(mode="json")
        else:
            raw_hits = raw_record.get("results", [])
            raw_dict = raw_record
    else:
        raw_hits = None
        raw_dict = None

    for idx, item in enumerate(packet.evidence_items):
        raw_hit = None
        if raw_hits is not None and len(raw_hits) > idx:
            raw_hit = raw_hits[idx]
        validate_frozen_evidence_item_integrity(
            item,
            expected_question_id=packet.question_id,
            expected_perspective=packet.perspective,
            raw_item=raw_hit,
        )
        expected_claim_id = format_compatibility_claim_id(item.evidence_id)
        if not expected_claim_id.startswith("cpaa1:sx:"):
            raise ValueError(f"Invalid wrapper claim ID format: {expected_claim_id}")

    # Validate against parent raw record
    if raw_dict is not None:
        packet_dict = packet.model_dump(mode="json")
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
        packet_dict = packet.model_dump(mode="json")
        strict_deep_compare(
            packet_dict["candidate_id"],
            manifest_candidate_id,
            path="packet.candidate_id_vs_manifest",
        )
        strict_deep_compare(
            packet_dict["question_id"],
            manifest_question["question_id"],
            path="packet.question_id_vs_manifest",
        )
        strict_deep_compare(
            packet_dict["question_text"],
            manifest_question["question_text"],
            path="packet.question_text_vs_manifest",
        )
        strict_deep_compare(
            packet_dict["topic"],
            manifest_question["topic"],
            path="packet.topic_vs_manifest",
        )
        strict_deep_compare(
            packet_dict["task_type"],
            manifest_question["task_type"],
            path="packet.task_type_vs_manifest",
        )

    if raw_artifact_sha256 is not None:
        if packet.retrieval_artifact_sha256 != raw_artifact_sha256:
            raise ValueError(
                f"raw_artifact_sha256 mismatch: {packet.retrieval_artifact_sha256} != {raw_artifact_sha256}"
            )

    # Independent canonical hash recomputation
    recomputed_hash = packet_canonical_sha256(packet)
    if packet.packet_canonical_sha256 != recomputed_hash:
        raise ValueError(
            f"Packet canonical SHA256 mismatch! Stored {packet.packet_canonical_sha256} != recomputed {recomputed_hash}"
        )


def validate_packet_against_trusted_parent(
    packet: FrozenEvidencePacket,
    trusted_store: TrustedParentStore,
) -> None:
    """Validate packet against trusted byte anchors retained in TrustedParentStore."""
    if packet.perspective == "tcm":
        if packet.question_id not in trusted_store.tcm_raw_records:
            raise ValueError(f"Question ID {packet.question_id} not in trusted TCM raw records")
        raw_rec = trusted_store.tcm_raw_records[packet.question_id]
        expected_artifact_sha = EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256
    elif packet.perspective == "western":
        if packet.question_id not in trusted_store.western_raw_records:
            raise ValueError(f"Question ID {packet.question_id} not in trusted Western raw records")
        raw_rec = trusted_store.western_raw_records[packet.question_id]
        expected_artifact_sha = EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256
    else:
        raise ValueError(f"Unknown perspective: {packet.perspective}")

    if packet.question_id not in trusted_store.questions_by_id:
        raise ValueError(f"Question ID {packet.question_id} not in trusted question manifest")
    manifest_q = trusted_store.questions_by_id[packet.question_id]

    validate_frozen_packet_integrity(
        packet=packet,
        raw_record=raw_rec,
        raw_artifact_sha256=expected_artifact_sha,
        manifest_question=manifest_q,
    )
