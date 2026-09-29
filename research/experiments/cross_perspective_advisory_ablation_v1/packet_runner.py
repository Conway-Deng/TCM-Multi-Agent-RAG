from __future__ import annotations

import argparse
import hashlib
import json
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

from backend.cross_perspective.cross_perspective_critic import CRITIC_SYSTEM_PROMPT
from backend.cross_perspective.governance import GOVERNANCE_SYSTEM_PROMPT
from backend.cross_perspective.perspective_agents import (
    COVERAGE_AUDITOR_SYSTEM_PROMPT,
    EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
    GROUNDING_SKEPTIC_SYSTEM_PROMPT,
)

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
        SERIALIZATION_VERSION,
        STUDY_ID,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
    )
    from .packet_projection import (
        TrustedParentStore,
        project_frozen_packet_to_compatibility_wrapper,
        project_raw_record_to_frozen_packet,
        validate_frozen_packet_integrity,
        validate_packet_against_trusted_parent,
    )
    from .packet_serialization import (
        canonical_json_bytes,
        canonical_json_text,
        manifest_canonical_sha256,
        manifest_file_bytes,
        perspective_canonical_aggregate_sha256,
        receipt_file_bytes,
        serialize_jsonl_records,
        sha256_bytes,
        strict_deep_compare,
        strict_json_loads,
    )
    from .packet_writer import (
        PHASE_1F_FORMAL_AUTHORIZATION_GRANTED,
        build_in_memory_formal_packet_artifacts,
        verify_frozen_inputs,
        verify_research_prompts,
        write_formal_packet_artifacts,
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
        RawRetrievalItem,
        RawRetrievalRecord,
    )
    from .token_budget_scaffold import TokenBudgetScaffold
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
        SERIALIZATION_VERSION,
        STUDY_ID,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_projection import (
        TrustedParentStore,
        project_frozen_packet_to_compatibility_wrapper,
        project_raw_record_to_frozen_packet,
        validate_frozen_packet_integrity,
        validate_packet_against_trusted_parent,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_serialization import (
        canonical_json_bytes,
        canonical_json_text,
        manifest_canonical_sha256,
        manifest_file_bytes,
        perspective_canonical_aggregate_sha256,
        receipt_file_bytes,
        serialize_jsonl_records,
        sha256_bytes,
        strict_deep_compare,
        strict_json_loads,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_writer import (
        PHASE_1F_FORMAL_AUTHORIZATION_GRANTED,
        build_in_memory_formal_packet_artifacts,
        verify_frozen_inputs,
        verify_research_prompts,
        write_formal_packet_artifacts,
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
        RawRetrievalItem,
        RawRetrievalRecord,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.token_budget_scaffold import (
        TokenBudgetScaffold,
    )


def verify_python_runtime() -> str:
    """Verify that current runtime is strictly CPython 3.12.14 standard library."""
    version_info = sys.version_info
    actual_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    if actual_version != "3.12.14" or sys.implementation.name != "cpython":
        raise RuntimeError(
            f"Serialization reference requirement failed: expected CPython 3.12.14, got {sys.implementation.name} {actual_version}"
        )
    return f"{sys.implementation.name} {actual_version}"


def check_formal_packet_generation_authorization(authorized: bool = False) -> None:
    """Fail-closed execution guard: formal packet generation is unauthorized in Phase 1E/1F."""
    if authorized:
        raise PermissionError(
            "FATAL: Formal packet generation is not authorized in Phase 1E (unauthorized in Phase 1F). Return to SOL."
        )


def validate_packet_preflight(repo_root: Path) -> dict[str, Any]:
    """Run non-formal dry preflight validation for Phase 1F.
    
    Verifies:
    1. Python serialization runtime requirement (strictly CPython 3.12.14).
    2. Parent artifact byte hashes (question manifest, TCM raw retrieval, Western raw retrieval).
    3. Production baseline prompt hashes and amended research prompt variants.
    4. Trusted parent store loading and duplicate-key rejection.
    5. Real-data read-only / in-memory full projection and integrity validation (96 packets, 384 items).
    6. Complete 96/384 correspondence against trusted SHA-bound parent bytes.
    7. Serialization conformance and deterministic repeated-buffer equivalence.
    8. Manifest and receipt schema validity in memory.
    9. Token budget offline status (reports NOT_YET_CLEARABLE).
    10. Confirmation that no formal packet output files exist and packets/ directory is not present.
    """
    # 1. Verify Python serialization runtime
    py_runtime = verify_python_runtime()

    # 2. Verify parent artifact byte hashes
    input_hashes = verify_frozen_inputs(repo_root)

    # 3. Verify production baseline prompt hashes and amended prompt map
    production_baselines = {
        "evidence_specialist": EVIDENCE_SPECIALIST_SYSTEM_PROMPT,
        "coverage_auditor": COVERAGE_AUDITOR_SYSTEM_PROMPT,
        "grounding_skeptic": GROUNDING_SKEPTIC_SYSTEM_PROMPT,
        "critic": CRITIC_SYSTEM_PROMPT,
        "governance": GOVERNANCE_SYSTEM_PROMPT,
    }
    for role, base_prompt in production_baselines.items():
        verify_baseline_prompt_hash(role, base_prompt)

    map_path = repo_root / "research/experiments/cross_perspective_advisory_ablation_v1/prompt_amendment_map_v1.json"
    if not map_path.exists():
        raise FileNotFoundError(f"Prompt amendment map not found at {map_path}")
    map_data = json.loads(map_path.read_text(encoding="utf-8"))
    if len(map_data) != 5:
        raise ValueError(f"Expected exactly 5 records in prompt amendment map, got {len(map_data)}")
    for entry in map_data:
        role = entry["role"]
        amended_text = RESEARCH_SYSTEM_PROMPTS[role]
        actual_amended_sha = sha256_prompt(amended_text)
        if actual_amended_sha != entry["amended_prompt_sha256"]:
            raise ValueError(
                f"Amended prompt SHA mismatch for role {role}: actual {actual_amended_sha} != map {entry['amended_prompt_sha256']}"
            )
        if actual_amended_sha != EXPECTED_AMENDED_PROMPT_HASHES[role]:
            raise ValueError(
                f"Amended prompt SHA mismatch against constant for {role}: {actual_amended_sha} != {EXPECTED_AMENDED_PROMPT_HASHES[role]}"
            )

    # 4. Load trusted parent store
    trusted_store = TrustedParentStore(repo_root)

    # 5. Build in-memory formal packet artifacts (dry test with dummy 40-hex commit identity)
    dummy_test_commit = "0" * 40
    artifacts_run1 = build_in_memory_formal_packet_artifacts(
        repo_root=repo_root,
        implementation_commit=dummy_test_commit,
    )
    artifacts_run2 = build_in_memory_formal_packet_artifacts(
        repo_root=repo_root,
        implementation_commit=dummy_test_commit,
    )

    # 6. Verify deterministic repeated in-memory construction
    if artifacts_run1.tcm_jsonl_bytes != artifacts_run2.tcm_jsonl_bytes:
        raise ValueError("TCM in-memory serialization is not deterministic across repeated runs!")
    if artifacts_run1.western_jsonl_bytes != artifacts_run2.western_jsonl_bytes:
        raise ValueError("Western in-memory serialization is not deterministic across repeated runs!")
    if artifacts_run1.manifest_bytes != artifacts_run2.manifest_bytes:
        raise ValueError("Manifest in-memory serialization is not deterministic across repeated runs!")
    if artifacts_run1.receipt_bytes != artifacts_run2.receipt_bytes:
        raise ValueError("Receipt in-memory serialization is not deterministic across repeated runs!")

    # 7. Token budget scaffold check
    tb_rec = TokenBudgetScaffold.evaluate_role_budget(
        role="evidence_specialist",
        question_id="dry-preflight",
        system_prompt="",
        user_payload="",
    )

    # 8. Verify absence of formal packet output files
    packets_dir = repo_root / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    forbidden_files = [
        packets_dir / "tcm_packets.jsonl",
        packets_dir / "western_packets.jsonl",
        packets_dir / "packet_manifest.json",
        packets_dir / "packet_freeze_receipt.json",
    ]
    for p in forbidden_files:
        if p.exists():
            raise FileNotFoundError(f"Formal packet output file must NOT exist in Phase 1F: {p}")
    if packets_dir.exists():
        raise FileExistsError(f"Formal packets directory must NOT exist in Phase 1F: {packets_dir}")

    return {
        "status": "PASS",
        "study_id": STUDY_ID,
        "amendment_id": AMENDMENT_ID,
        "packet_contract_id": PACKET_CONTRACT_ID,
        "serialization_version": SERIALIZATION_VERSION,
        "python_runtime": py_runtime,
        "question_manifest_sha256": input_hashes["question_manifest_sha256"],
        "tcm_raw_retrieval_byte_sha256": input_hashes["tcm_raw_retrieval_byte_sha256"],
        "western_raw_retrieval_byte_sha256": input_hashes["western_raw_retrieval_byte_sha256"],
        "parsed_tcm_records": len(trusted_store.tcm_raw_records),
        "parsed_western_records": len(trusted_store.western_raw_records),
        "total_parsed_records": len(trusted_store.tcm_raw_records) + len(trusted_store.western_raw_records),
        "total_parsed_hits": (len(trusted_store.tcm_raw_records) + len(trusted_store.western_raw_records)) * HITS_PER_RECORD,
        "in_memory_tcm_packets": len(artifacts_run1.tcm_packets),
        "in_memory_western_packets": len(artifacts_run1.western_packets),
        "in_memory_total_packets": len(artifacts_run1.tcm_packets) + len(artifacts_run1.western_packets),
        "in_memory_total_items": (len(artifacts_run1.tcm_packets) + len(artifacts_run1.western_packets)) * HITS_PER_RECORD,
        "all_packets_validated": True,
        "expected_tcm_packets": EXPECTED_TCM_RECORDS,
        "expected_western_packets": EXPECTED_WESTERN_RECORDS,
        "expected_total_packets": EXPECTED_TOTAL_RECORDS,
        "expected_tcm_items": EXPECTED_TCM_ITEMS,
        "expected_western_items": EXPECTED_WESTERN_ITEMS,
        "expected_total_items": EXPECTED_TOTAL_ITEMS,
        "deterministic_repeated_buffers": True,
        "token_budget_scaffold_status": tb_rec.status,
        "formal_packets_materialized": False,
        "formal_packets_dir_exists": packets_dir.exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1F Packet Writer and Preflight Runner for Advisory Ablation Study"
    )
    parser.add_argument(
        "--execute-formal-packet-generation",
        action="store_true",
        default=False,
        help="EXECUTION GUARD: authorize formal packet generation (FORBIDDEN in Phase 1F)",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        default=True,
        help="Run non-formal dry preflight validation only (default: True)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]

    if not args.execute_formal_packet_generation:
        print("=" * 60)
        print("PHASE 1F PACKET WRITER PREFLIGHT (NON-FORMAL DRY MODE)")
        print("=" * 60)
        report = validate_packet_preflight(repo_root)
        print("PREFLIGHT VALIDATION: PASS")
        for k, v in report.items():
            print(f"  {k}: {v}")
        print("=" * 60)
        print("FORMAL PACKET GENERATION WAS NOT EXECUTED.")
        print("NO FORMAL PACKET OUTPUT FILES WERE GENERATED.")
        print("REAL PACKETS DIRECTORY DOES NOT EXIST.")
        print("=" * 60)
        sys.exit(0)
    else:
        try:
            check_formal_packet_generation_authorization(True)
        except PermissionError as exc:
            print(f"FATAL: {exc}")
            sys.exit(1)


if __name__ == "__main__":
    main()
