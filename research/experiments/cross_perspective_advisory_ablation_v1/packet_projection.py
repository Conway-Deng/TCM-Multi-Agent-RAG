from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

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
    from .packet_contract import (
        COMPATIBILITY_CLAIM_KIND,
        COMPATIBILITY_SUPPORT_STATUS,
        HITS_PER_RECORD,
        PACKET_CONTRACT_ID,
        SCHEMA_VERSION,
        SUPPORT_BASIS,
        SEMANTIC_SUPPORT_STATUS,
        compute_packet_canonical_sha256,
        format_compatibility_claim_id,
        format_evidence_id,
        format_packet_id,
    )
    from .schemas import (
        FrozenEvidenceItem,
        FrozenEvidencePacket,
        RawRetrievalItem,
        RawRetrievalRecord,
    )
except ImportError:
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_contract import (
        COMPATIBILITY_CLAIM_KIND,
        COMPATIBILITY_SUPPORT_STATUS,
        HITS_PER_RECORD,
        PACKET_CONTRACT_ID,
        SCHEMA_VERSION,
        SUPPORT_BASIS,
        SEMANTIC_SUPPORT_STATUS,
        compute_packet_canonical_sha256,
        format_compatibility_claim_id,
        format_evidence_id,
        format_packet_id,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
        FrozenEvidenceItem,
        FrozenEvidencePacket,
        RawRetrievalItem,
        RawRetrievalRecord,
    )


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
            provenance=dict(hit.provenance),
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
        "evidence_items": [item.model_dump(mode="json") for item in evidence_items],
    }
    canonical_sha = compute_packet_canonical_sha256(packet_dict)
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
