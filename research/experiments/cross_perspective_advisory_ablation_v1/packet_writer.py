from __future__ import annotations

import copy
import re
import shutil
import subprocess
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
        EXPECTED_ORIGINAL_PROMPT_HASHES,
        RESEARCH_SYSTEM_PROMPTS,
        sha256_prompt,
        verify_baseline_prompt_hash,
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
        EXPECTED_ORIGINAL_PROMPT_HASHES,
        RESEARCH_SYSTEM_PROMPTS,
        sha256_prompt,
        verify_baseline_prompt_hash,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
        FrozenEvidencePacket,
        PacketFreezeReceipt,
        PacketRunManifest,
    )

# Tracked Formal Execution Authorization Gate: STRICTLY CLOSED in Phase 1F-FIX
PHASE_1G_FORMAL_AUTHORIZATION_GRANTED: bool = False
PHASE_1F_FORMAL_AUTHORIZATION_GRANTED: bool = False  # Backward-compatible alias


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


def get_git_executable() -> str:
    """Locate the git binary on the host system."""
    git_bin = shutil.which("git")
    if git_bin:
        return git_bin
    common_locations = [
        Path(r"D:\Git\cmd\git.exe"),
        Path(r"C:\Program Files\Git\cmd\git.exe"),
        Path(r"C:\Program Files\Git\bin\git.exe"),
    ]
    for loc in common_locations:
        if loc.exists():
            return str(loc)
    raise FileNotFoundError("git executable not found in PATH or standard installation locations")


def verify_and_get_executing_git_head(
    repo_root: Path,
    expected_branch: str = "research/cross-perspective-advisory-ablation-v1",
) -> str:
    """Retrieve and verify real executing git HEAD SHA and clean tracked working tree."""
    git_bin = get_git_executable()

    # 1. Verify branch
    res_b = subprocess.run(
        [git_bin, "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if res_b.returncode != 0:
        raise RuntimeError(f"Failed to query git branch: {res_b.stderr}")
    current_branch = res_b.stdout.strip()
    if current_branch != expected_branch:
        raise RuntimeError(
            f"Executing branch mismatch: expected '{expected_branch}', got '{current_branch}'"
        )

    # 2. Verify clean tracked tree (both working-tree modifications and staged changes)
    res_diff = subprocess.run(
        [git_bin, "diff-index", "--quiet", "HEAD", "--"],
        cwd=repo_root,
        capture_output=True,
    )
    if res_diff.returncode != 0:
        raise RuntimeError(
            "Tracked working tree has uncommitted modifications; formal execution requires a clean tracked tree."
        )

    # 3. Retrieve HEAD commit SHA
    res_h = subprocess.run(
        [git_bin, "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if res_h.returncode != 0:
        raise RuntimeError(f"Failed to query git HEAD: {res_h.stderr}")
    head_sha = res_h.stdout.strip()
    if not re.match(r"^[0-9a-f]{40}$", head_sha):
        raise ValueError(f"Invalid executing git HEAD SHA format: {head_sha!r}")

    return head_sha


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
    """Build candidate formal packet artifacts completely in memory.
    
    This function performs non-writing preflight construction. It does NOT write files
    or seal a formal run; formal freeze requires execute_formal_packet_generation.
    """
    validate_implementation_commit_format(implementation_commit)
    verify_frozen_inputs(repo_root)
    research_prompt_hashes = verify_research_prompts()

    # Load trusted parent store from verified file bytes
    trusted_store = TrustedParentStore(repo_root)
    manifest_qids = trusted_store.get_manifest_question_ids()

    # Project TCM packets in physical question manifest order
    tcm_packets: list[FrozenEvidencePacket] = []
    for qid in manifest_qids:
        raw_dict = trusted_store.get_fresh_raw_record_dict("tcm", qid)
        pkt = project_raw_record_to_frozen_packet(
            record=raw_dict,
            raw_artifact_sha256=EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        )
        validate_packet_against_trusted_parent(pkt, trusted_store)
        tcm_packets.append(pkt)

    # Project Western packets in physical question manifest order
    western_packets: list[FrozenEvidencePacket] = []
    for qid in manifest_qids:
        raw_dict = trusted_store.get_fresh_raw_record_dict("western", qid)
        pkt = project_raw_record_to_frozen_packet(
            record=raw_dict,
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


def execute_formal_packet_generation(
    repo_root: Path,
    output_dir: Path | None = None,
    request_formal_execution: bool = False,
    _inject_failure_after: str | None = None,
) -> dict[str, Any]:
    """Execute formal deterministic packet generation from frozen inputs to sealed disk receipt.

    THE SINGLE HIGH-LEVEL FORMAL EXECUTION PATH.
    Does NOT trust caller-supplied artifact bundles.
    Does NOT unlink partial files on failure (preserves forensic evidence).
    Does NOT retry automatically.

    Sealing rule: A run is SEALED only if packet_freeze_receipt.json exists and passes post-write audit.
    """
    # 1. Tracked authorization gate
    if not request_formal_execution:
        raise PermissionError(
            "Formal packet execution was not explicitly requested (request_formal_execution=False)."
        )

    if not PHASE_1G_FORMAL_AUTHORIZATION_GRANTED:
        raise PermissionError(
            "FORMAL EXECUTION DENIED: Phase 1G formal authorization remains CLOSED "
            "(PHASE_1G_FORMAL_AUTHORIZATION_GRANTED=False). "
            "Formal packet generation is not authorized. Return to SOL."
        )

    # 2. Target path & collision verification
    if output_dir is None:
        output_dir = repo_root / "research/experiments/cross_perspective_advisory_ablation_v1/packets"

    tcm_file = output_dir / "tcm_packets.jsonl"
    western_file = output_dir / "western_packets.jsonl"
    manifest_file = output_dir / "packet_manifest.json"
    receipt_file = output_dir / "packet_freeze_receipt.json"

    # Pre-check: fail closed before creating anything if ANY formal output exists
    for target in (tcm_file, western_file, manifest_file, receipt_file):
        if target.exists():
            raise FileExistsError(
                f"Formal output target already exists at {target}. "
                "Resuming partial runs or overwriting formal freeze artifacts is strictly FORBIDDEN. "
                "Forensic inspection required."
            )

    # 3. Verify CPython 3.12.14 runtime requirement
    if sys.implementation.name != "cpython" or sys.version_info[:3] != (3, 12, 14):
        raise RuntimeError(
            f"Serialization reference requirement failed: expected CPython 3.12.14, "
            f"got {sys.implementation.name} {sys.version_info}"
        )

    # 4. Verify executing Git HEAD and clean tracked tree
    executing_head = verify_and_get_executing_git_head(repo_root)

    # 5. Build candidate artifacts internally from verified bytes
    artifacts = build_in_memory_formal_packet_artifacts(
        repo_root=repo_root,
        implementation_commit=executing_head,
    )

    trusted_store = TrustedParentStore(repo_root)

    # 6. Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # 7. Write order Step 1: TCM packets (exclusive create, NO cleanup on failure)
    with open(tcm_file, "xb") as f:
        f.write(artifacts.tcm_jsonl_bytes)
    if _inject_failure_after == "tcm_write":
        raise RuntimeError("Injected failure after TCM write")

    # 8. Write order Step 2: Western packets (exclusive create, NO cleanup on failure)
    with open(western_file, "xb") as f:
        f.write(artifacts.western_jsonl_bytes)
    if _inject_failure_after == "western_write":
        raise RuntimeError("Injected failure after Western write")

    # 9. Write order Step 3: Reread and audit BOTH packet files from disk
    tcm_disk_bytes = tcm_file.read_bytes()
    if sha256_bytes(tcm_disk_bytes) != artifacts.tcm_packet_byte_sha256:
        raise ValueError("TCM packet disk bytes SHA mismatch against in-memory verification")
    tcm_lines = [l for l in tcm_disk_bytes.decode("utf-8").splitlines() if l.strip()]
    if len(tcm_lines) != EXPECTED_TCM_RECORDS:
        raise ValueError(f"Expected {EXPECTED_TCM_RECORDS} TCM disk records, got {len(tcm_lines)}")
    for line in tcm_lines:
        pkt_dict = strict_json_loads(line)
        validate_packet_against_trusted_parent(pkt_dict, trusted_store)

    western_disk_bytes = western_file.read_bytes()
    if sha256_bytes(western_disk_bytes) != artifacts.western_packet_byte_sha256:
        raise ValueError("Western packet disk bytes SHA mismatch against in-memory verification")
    western_lines = [l for l in western_disk_bytes.decode("utf-8").splitlines() if l.strip()]
    if len(western_lines) != EXPECTED_WESTERN_RECORDS:
        raise ValueError(f"Expected {EXPECTED_WESTERN_RECORDS} Western disk records, got {len(western_lines)}")
    for line in western_lines:
        pkt_dict = strict_json_loads(line)
        validate_packet_against_trusted_parent(pkt_dict, trusted_store)

    if _inject_failure_after == "packet_audit":
        raise RuntimeError("Injected failure after packet audit")

    # 10. Post-write parent hash, prompt hash, and Git HEAD recheck from disk
    verify_frozen_inputs(repo_root)
    verify_research_prompts()
    current_head = verify_and_get_executing_git_head(repo_root)
    if current_head != executing_head:
        raise RuntimeError(
            f"Git HEAD changed during packet write: initial {executing_head} != current {current_head}"
        )
    if _inject_failure_after == "post_write_parent_recheck":
        raise RuntimeError("Injected failure after post-write parent recheck")

    # 11. Write order Step 4: Write packet_manifest.json
    with open(manifest_file, "xb") as f:
        f.write(artifacts.manifest_bytes)
    if _inject_failure_after == "manifest_write":
        raise RuntimeError("Injected failure after manifest write")

    # Reread and audit manifest
    manifest_disk_bytes = manifest_file.read_bytes()
    if sha256_bytes(manifest_disk_bytes) != artifacts.manifest_byte_sha256:
        raise ValueError("Manifest disk bytes SHA mismatch")
    strict_json_loads(manifest_disk_bytes)
    PacketRunManifest.model_validate_json(manifest_disk_bytes)
    if _inject_failure_after == "manifest_audit":
        raise RuntimeError("Injected failure after manifest audit")

    # 12. Write order Step 5: Write packet_freeze_receipt.json LAST (sealing artifact)
    with open(receipt_file, "xb") as f:
        f.write(artifacts.receipt_bytes)
    if _inject_failure_after == "receipt_write":
        raise RuntimeError("Injected failure after receipt write")

    # Reread and audit receipt
    receipt_disk_bytes = receipt_file.read_bytes()
    if sha256_bytes(receipt_disk_bytes) != artifacts.receipt_byte_sha256:
        raise ValueError("Receipt disk bytes SHA mismatch")
    strict_json_loads(receipt_disk_bytes)
    verified_receipt = PacketFreezeReceipt.model_validate_json(receipt_disk_bytes)
    if verified_receipt.manifest_byte_sha256 != artifacts.manifest_byte_sha256:
        raise ValueError("Receipt manifest byte SHA linkage mismatch")
    if _inject_failure_after == "receipt_audit":
        raise RuntimeError("Injected failure after receipt audit")

    return {
        "status": "SEALED",
        "output_dir": str(output_dir),
        "implementation_commit": executing_head,
        "tcm_packet_byte_sha256": artifacts.tcm_packet_byte_sha256,
        "western_packet_byte_sha256": artifacts.western_packet_byte_sha256,
        "manifest_byte_sha256": artifacts.manifest_byte_sha256,
        "receipt_byte_sha256": artifacts.receipt_byte_sha256,
        "manifest_canonical_sha256": artifacts.manifest_canonical_sha256,
        "receipt_canonical_sha256": artifacts.receipt_canonical_sha256,
    }


def write_formal_packet_artifacts(
    artifacts: InMemoryFormalPacketArtifacts,
    output_dir: Path,
    request_formal_execution: bool = False,
    authorize_formal: bool = False,
) -> dict[str, str]:
    """Low-level test sink writer for synthetic unit tests.
    
    SAFETY CONTROLS:
    - Never deletes partial files on failure (preserves forensic evidence).
    - Blocks writing to the real study packets/ directory.
    - Requires explicit authorization.
    """
    if not request_formal_execution:
        raise PermissionError(
            "Formal packet execution was not explicitly requested (request_formal_execution=False)."
        )

    if not authorize_formal:
        raise PermissionError(
            "FORMAL EXECUTION DENIED: Phase 1F/1G authorization remains CLOSED. "
            "Formal packet generation is not authorized. Return to SOL."
        )

    real_packets_dir = (
        _REPO_ROOT / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    ).resolve()
    if output_dir.resolve() == real_packets_dir:
        raise PermissionError(
            "Writing to the real study packets directory is strictly FORBIDDEN in Phase 1F-FIX."
        )

    target_files = {
        "tcm_packets.jsonl": artifacts.tcm_jsonl_bytes,
        "western_packets.jsonl": artifacts.western_jsonl_bytes,
        "packet_manifest.json": artifacts.manifest_bytes,
        "packet_freeze_receipt.json": artifacts.receipt_bytes,
    }

    for filename in target_files:
        target_path = output_dir / filename
        if target_path.exists():
            raise FileExistsError(
                f"Formal output target already exists: {target_path}. Overwrite is forbidden."
            )

    output_dir.mkdir(parents=True, exist_ok=True)

    # Write without deleting on failure (Task 10)
    for filename, data in target_files.items():
        target_path = output_dir / filename
        with open(target_path, "xb") as f:
            f.write(data)

    return {
        "status": "WRITTEN",
        "output_dir": str(output_dir),
        "tcm_packet_byte_sha256": artifacts.tcm_packet_byte_sha256,
        "western_packet_byte_sha256": artifacts.western_packet_byte_sha256,
        "manifest_byte_sha256": artifacts.manifest_byte_sha256,
        "receipt_byte_sha256": artifacts.receipt_byte_sha256,
    }
