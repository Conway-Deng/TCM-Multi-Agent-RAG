from __future__ import annotations

import copy
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
_CURRENT_DIR = Path(__file__).resolve().parent

for p in (str(_CURRENT_DIR), str(_BACKEND_DIR), str(_REPO_ROOT)):
    if p in sys.path:
        sys.path.remove(p)

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_BACKEND_DIR))

try:
    from .packet_contract import (
        AMENDMENT_ID,
        EXPECTED_QUESTION_COUNT,
        EXPECTED_QUESTION_MANIFEST_SHA256,
        EXPECTED_TCM_CORPUS_SHA256,
        EXPECTED_TCM_ITEMS,
        EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_TCM_RECORDS,
        EXPECTED_TOTAL_ITEMS,
        EXPECTED_TOTAL_RECORDS,
        EXPECTED_WESTERN_CORPUS_SHA256,
        EXPECTED_WESTERN_ITEMS,
        EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_WESTERN_RECORDS,
        HITS_PER_RECORD,
        MANIFEST_SCHEMA_VERSION,
        PACKET_CONTRACT_ID,
        QUESTION_MANIFEST_RELPATH,
        RECEIPT_SCHEMA_VERSION,
        SCHEMA_VERSION,
        SERIALIZATION_VERSION,
        STUDY_ID,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
    )
    from .packet_projection import (
        TrustedParentStore,
        project_raw_record_to_frozen_packet,
        validate_frozen_packet_integrity,
        validate_packet_against_trusted_parent,
    )
    from .packet_serialization import (
        canonical_json_bytes,
        manifest_canonical_sha256,
        manifest_file_bytes,
        perspective_canonical_aggregate_sha256,
        receipt_file_bytes,
        serialize_jsonl_records,
        sha256_bytes,
        strict_json_loads,
    )
    from .prompt_variants import (
        EXPECTED_AMENDED_PROMPT_HASHES,
        RESEARCH_SYSTEM_PROMPTS,
        sha256_prompt,
    )
    from .schemas import (
        FrozenEvidencePacket,
        PacketFreezeReceipt,
        PacketRunManifest,
    )
except ImportError:
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_contract import (
        AMENDMENT_ID,
        EXPECTED_QUESTION_COUNT,
        EXPECTED_QUESTION_MANIFEST_SHA256,
        EXPECTED_TCM_CORPUS_SHA256,
        EXPECTED_TCM_ITEMS,
        EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_TCM_RECORDS,
        EXPECTED_TOTAL_ITEMS,
        EXPECTED_TOTAL_RECORDS,
        EXPECTED_WESTERN_CORPUS_SHA256,
        EXPECTED_WESTERN_ITEMS,
        EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_WESTERN_RECORDS,
        HITS_PER_RECORD,
        MANIFEST_SCHEMA_VERSION,
        PACKET_CONTRACT_ID,
        QUESTION_MANIFEST_RELPATH,
        RECEIPT_SCHEMA_VERSION,
        SCHEMA_VERSION,
        SERIALIZATION_VERSION,
        STUDY_ID,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_projection import (
        TrustedParentStore,
        project_raw_record_to_frozen_packet,
        validate_frozen_packet_integrity,
        validate_packet_against_trusted_parent,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
        canonical_json_bytes,
        manifest_canonical_sha256,
        manifest_file_bytes,
        perspective_canonical_aggregate_sha256,
        receipt_file_bytes,
        serialize_jsonl_records,
        sha256_bytes,
        strict_json_loads,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.prompt_variants import (
        EXPECTED_AMENDED_PROMPT_HASHES,
        RESEARCH_SYSTEM_PROMPTS,
        sha256_prompt,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
        FrozenEvidencePacket,
        PacketFreezeReceipt,
        PacketRunManifest,
    )


# Phase 1F Formal Execution Authorization Gate: CLOSED
PHASE_1F_FORMAL_AUTHORIZATION_GRANTED: bool = False


@dataclass(frozen=True)
class InMemoryFormalPacketArtifacts:
    tcm_packets: list[FrozenEvidencePacket]
    western_packets: list[FrozenEvidencePacket]
    tcm_jsonl_bytes: bytes
    western_jsonl_bytes: bytes
    tcm_packet_byte_sha256: str
    western_packet_byte_sha256: str
    tcm_packet_canonical_aggregate_sha256: str
    western_packet_canonical_aggregate_sha256: str
    manifest: PacketRunManifest
    manifest_bytes: bytes
    manifest_canonical_sha256: str
    manifest_byte_sha256: str
    receipt: PacketFreezeReceipt
    receipt_bytes: bytes
    receipt_canonical_sha256: str
    receipt_byte_sha256: str


def validate_implementation_commit_format(commit: str) -> None:
    """Validate that implementation commit is an explicit 40-character lowercase hex string."""
    if not isinstance(commit, str):
        raise TypeError(f"implementation_commit must be a string, got {type(commit).__name__}")
    if not re.match(r"^[0-9a-f]{40}$", commit):
        raise ValueError(
            f"implementation_commit must be a 40-character lowercase hexadecimal string, got {commit!r}"
        )


def verify_frozen_inputs(repo_root: Path) -> dict[str, str]:
    """Verify byte SHA256 of all frozen inputs prior to packet generation."""
    q_manifest_path = repo_root / QUESTION_MANIFEST_RELPATH
    if not q_manifest_path.exists():
        raise FileNotFoundError(f"Question manifest not found at {q_manifest_path}")
    q_sha = sha256_bytes(q_manifest_path.read_bytes())
    if q_sha != EXPECTED_QUESTION_MANIFEST_SHA256:
        raise ValueError(
            f"Question manifest SHA mismatch: actual {q_sha} != expected {EXPECTED_QUESTION_MANIFEST_SHA256}"
        )

    tcm_raw_path = repo_root / TCM_RAW_RETRIEVAL_RELPATH
    if not tcm_raw_path.exists():
        raise FileNotFoundError(f"TCM raw retrieval artifact not found at {tcm_raw_path}")
    tcm_sha = sha256_bytes(tcm_raw_path.read_bytes())
    if tcm_sha != EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256:
        raise ValueError(
            f"TCM raw retrieval byte SHA mismatch: actual {tcm_sha} != expected {EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256}"
        )

    western_raw_path = repo_root / WESTERN_RAW_RETRIEVAL_RELPATH
    if not western_raw_path.exists():
        raise FileNotFoundError(f"Western raw retrieval artifact not found at {western_raw_path}")
    western_sha = sha256_bytes(western_raw_path.read_bytes())
    if western_sha != EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256:
        raise ValueError(
            f"Western raw retrieval byte SHA mismatch: actual {western_sha} != expected {EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256}"
        )

    return {
        "question_manifest_sha256": q_sha,
        "tcm_raw_retrieval_byte_sha256": tcm_sha,
        "western_raw_retrieval_byte_sha256": western_sha,
    }


def verify_research_prompts() -> dict[str, str]:
    """Verify research system prompt hashes against frozen amendment expectations."""
    required_roles = [
        "evidence_specialist",
        "coverage_auditor",
        "grounding_skeptic",
        "critic",
        "governance",
    ]
    computed: dict[str, str] = {}
    for role in required_roles:
        expected = EXPECTED_AMENDED_PROMPT_HASHES[role]
        runtime_text = RESEARCH_SYSTEM_PROMPTS[role]
        actual = sha256_prompt(runtime_text)
        if actual != expected:
            raise ValueError(
                f"Amended prompt hash mismatch for role '{role}': actual {actual} != expected {expected}"
            )
        computed[role] = actual
    return computed


def build_in_memory_formal_packet_artifacts(
    repo_root: Path,
    implementation_commit: str,
) -> InMemoryFormalPacketArtifacts:
    """Build all formal packet artifacts completely in memory.
    
    Executes steps 1–12 of the formal writer design:
    1. Verify frozen parent file hashes
    2. Verify research prompt hashes
    3. Load trusted parent records from verified file bytes
    4. Project exactly 96 packets (48 TCM + 48 Western) in physical question manifest order
    5. Validate all packets against trusted parents
    6. Compute deterministic output buffers in memory
    7. Parse output buffers and revalidate reconstructed packets
    8. Compute byte and canonical aggregate hashes
    9. Build manifest in memory
    10. Build freeze receipt in memory
    11. Validate all metadata schemas
    """
    validate_implementation_commit_format(implementation_commit)
    verify_frozen_inputs(repo_root)
    research_prompt_hashes = verify_research_prompts()

    # Load trusted parent store from verified file bytes
    trusted_store = TrustedParentStore(repo_root)

    # Project TCM packets in physical question manifest order
    tcm_packets: list[FrozenEvidencePacket] = []
    for q_rec in trusted_store.question_manifest_records:
        qid = q_rec["question_id"]
        raw_rec = trusted_store.tcm_raw_records[qid]
        pkt = project_raw_record_to_frozen_packet(
            record=raw_rec,
            raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        )
        validate_packet_against_trusted_parent(pkt, trusted_store)
        tcm_packets.append(pkt)

    # Project Western packets in physical question manifest order
    western_packets: list[FrozenEvidencePacket] = []
    for q_rec in trusted_store.question_manifest_records:
        qid = q_rec["question_id"]
        raw_rec = trusted_store.western_raw_records[qid]
        pkt = project_raw_record_to_frozen_packet(
            record=raw_rec,
            raw_artifact_sha256=EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        )
        validate_packet_against_trusted_parent(pkt, trusted_store)
        western_packets.append(pkt)

    if len(tcm_packets) != EXPECTED_TCM_RECORDS:
        raise ValueError(f"Expected {EXPECTED_TCM_RECORDS} TCM packets, got {len(tcm_packets)}")
    if len(western_packets) != EXPECTED_WESTERN_RECORDS:
        raise ValueError(
            f"Expected {EXPECTED_WESTERN_RECORDS} Western packets, got {len(western_packets)}"
        )

    # Compute deterministic in-memory buffers
    tcm_jsonl_bytes = serialize_jsonl_records(tcm_packets)
    western_jsonl_bytes = serialize_jsonl_records(western_packets)

    # Parse and revalidate reconstructed packets from serialized bytes
    for line in tcm_jsonl_bytes.decode("utf-8").splitlines():
        if not line:
            continue
        pkt_dict = strict_json_loads(line)
        reconstructed = FrozenEvidencePacket.model_validate(pkt_dict)
        validate_packet_against_trusted_parent(reconstructed, trusted_store)

    for line in western_jsonl_bytes.decode("utf-8").splitlines():
        if not line:
            continue
        pkt_dict = strict_json_loads(line)
        reconstructed = FrozenEvidencePacket.model_validate(pkt_dict)
        validate_packet_against_trusted_parent(reconstructed, trusted_store)

    # Compute byte hashes and canonical aggregate hashes
    tcm_packet_byte_sha256 = sha256_bytes(tcm_jsonl_bytes)
    western_packet_byte_sha256 = sha256_bytes(western_jsonl_bytes)
    tcm_agg_sha = perspective_canonical_aggregate_sha256(tcm_packets)
    western_agg_sha = perspective_canonical_aggregate_sha256(western_packets)

    # Build manifest in memory
    manifest = PacketRunManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        study_id=STUDY_ID,
        amendment_id=AMENDMENT_ID,
        packet_contract_id=PACKET_CONTRACT_ID,
        serialization_version=SERIALIZATION_VERSION,
        implementation_commit=implementation_commit,
        question_manifest_sha256=EXPECTED_QUESTION_MANIFEST_SHA256,
        tcm_raw_retrieval_byte_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        western_raw_retrieval_byte_sha256=EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        tcm_corpus_sha256=EXPECTED_TCM_CORPUS_SHA256,
        western_corpus_sha256=EXPECTED_WESTERN_CORPUS_SHA256,
        research_prompt_sha256=research_prompt_hashes,
        tcm_packet_byte_sha256=tcm_packet_byte_sha256,
        western_packet_byte_sha256=western_packet_byte_sha256,
        tcm_packet_canonical_aggregate_sha256=tcm_agg_sha,
        western_packet_canonical_aggregate_sha256=western_agg_sha,
        tcm_packet_count=EXPECTED_TCM_RECORDS,
        western_packet_count=EXPECTED_WESTERN_RECORDS,
        total_packet_count=EXPECTED_TOTAL_RECORDS,
        tcm_evidence_item_count=EXPECTED_TCM_ITEMS,
        western_evidence_item_count=EXPECTED_WESTERN_ITEMS,
        total_evidence_item_count=EXPECTED_TOTAL_ITEMS,
        integrity_audit_status="PASS",
        no_retrieval_attestation=True,
        no_model_provider_attestation=True,
        local_only_packet_jsonls=True,
    )
    manifest_bytes = manifest_file_bytes(manifest)
    manifest_canonical_sha = manifest_canonical_sha256(manifest)
    manifest_byte_sha = sha256_bytes(manifest_bytes)

    # Build receipt in memory
    receipt_data = manifest.model_dump(mode="json")
    receipt_data["schema_version"] = RECEIPT_SCHEMA_VERSION
    receipt_data["manifest_byte_sha256"] = manifest_byte_sha
    receipt_data["manifest_canonical_sha256"] = manifest_canonical_sha

    receipt = PacketFreezeReceipt.model_validate(receipt_data)
    receipt_bytes = receipt_file_bytes(receipt)
    receipt_canonical_sha = sha256_bytes(canonical_json_bytes(receipt.model_dump(mode="json")))
    receipt_byte_sha = sha256_bytes(receipt_bytes)

    # Verify metadata round-trip parsing
    strict_json_loads(manifest_bytes)
    strict_json_loads(receipt_bytes)

    return InMemoryFormalPacketArtifacts(
        tcm_packets=tcm_packets,
        western_packets=western_packets,
        tcm_jsonl_bytes=tcm_jsonl_bytes,
        western_jsonl_bytes=western_jsonl_bytes,
        tcm_packet_byte_sha256=tcm_packet_byte_sha256,
        western_packet_byte_sha256=western_packet_byte_sha256,
        tcm_packet_canonical_aggregate_sha256=tcm_agg_sha,
        western_packet_canonical_aggregate_sha256=western_agg_sha,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        manifest_canonical_sha256=manifest_canonical_sha,
        manifest_byte_sha256=manifest_byte_sha,
        receipt=receipt,
        receipt_bytes=receipt_bytes,
        receipt_canonical_sha256=receipt_canonical_sha,
        receipt_byte_sha256=receipt_byte_sha,
    )


def write_formal_packet_artifacts(
    artifacts: InMemoryFormalPacketArtifacts,
    output_dir: Path,
    request_formal_execution: bool = False,
    authorize_formal: bool = False,
) -> dict[str, str]:
    """Write formal packet artifacts to disk with exclusive creation.
    
    SAFETY CONTROLS:
    - Phase 1F formal authorization remains strictly CLOSED.
    - Requires BOTH request_formal_execution=True AND authorize_formal=True.
    - Uses exclusive creation (mode="xb") — never overwrites existing files.
    - Pre-checks that NONE of the target files exist before writing any file.
    - Writes to temporary paths or synthetic test output dirs during testing.
    """
    if not request_formal_execution:
        raise PermissionError(
            "Formal packet execution was not explicitly requested (request_formal_execution=False)."
        )

    if not authorize_formal:
        raise PermissionError(
            "FORMAL EXECUTION DENIED: Phase 1F authorization remains CLOSED. "
            "Formal packet generation is not authorized. Return to SOL."
        )

    # Guard against unauthorized writing to the real study packets/ directory
    real_packets_dir = (
        _REPO_ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    ).resolve()
    if output_dir.resolve() == real_packets_dir:
        raise PermissionError(
            "Writing to the real study packets directory is strictly FORBIDDEN in Phase 1F."
        )

    target_files = {
        "tcm_packets.jsonl": artifacts.tcm_jsonl_bytes,
        "western_packets.jsonl": artifacts.western_jsonl_bytes,
        "packet_manifest.json": artifacts.manifest_bytes,
        "packet_freeze_receipt.json": artifacts.receipt_bytes,
    }

    # Pre-check: fail before any write if ANY target file exists
    for filename in target_files:
        target_path = output_dir / filename
        if target_path.exists():
            raise FileExistsError(
                f"Formal output target already exists: {target_path}. Overwrite is forbidden."
            )

    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    try:
        for filename, data in target_files.items():
            target_path = output_dir / filename
            with open(target_path, "xb") as f:
                f.write(data)
            written.append(target_path)
    except Exception:
        for p in written:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        raise

    return {
        "status": "WRITTEN",
        "output_dir": str(output_dir),
        "tcm_packet_byte_sha256": artifacts.tcm_packet_byte_sha256,
        "western_packet_byte_sha256": artifacts.western_packet_byte_sha256,
        "manifest_byte_sha256": artifacts.manifest_byte_sha256,
        "receipt_byte_sha256": artifacts.receipt_byte_sha256,
    }
