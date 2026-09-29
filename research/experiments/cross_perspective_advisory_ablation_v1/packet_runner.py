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
        EXPECTED_TCM_ITEMS,
        EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_TCM_RECORDS,
        EXPECTED_TOTAL_ITEMS,
        EXPECTED_TOTAL_RECORDS,
        EXPECTED_WESTERN_ITEMS,
        EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_WESTERN_RECORDS,
        HITS_PER_RECORD,
        PACKET_CONTRACT_ID,
        QUESTION_MANIFEST_RELPATH,
        STUDY_ID,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
    )
    from .packet_projection import (
        project_frozen_packet_to_compatibility_wrapper,
        project_raw_record_to_frozen_packet,
        validate_frozen_packet_integrity,
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
        RawRetrievalItem,
        RawRetrievalRecord,
    )
    from .token_budget_scaffold import TokenBudgetScaffold
except ImportError:
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_contract import (
        AMENDMENT_ID,
        EXPECTED_QUESTION_COUNT,
        EXPECTED_QUESTION_MANIFEST_SHA256,
        EXPECTED_TCM_ITEMS,
        EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_TCM_RECORDS,
        EXPECTED_TOTAL_ITEMS,
        EXPECTED_TOTAL_RECORDS,
        EXPECTED_WESTERN_ITEMS,
        EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256,
        EXPECTED_WESTERN_RECORDS,
        HITS_PER_RECORD,
        PACKET_CONTRACT_ID,
        QUESTION_MANIFEST_RELPATH,
        STUDY_ID,
        TCM_RAW_RETRIEVAL_RELPATH,
        WESTERN_RAW_RETRIEVAL_RELPATH,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.packet_projection import (
        project_frozen_packet_to_compatibility_wrapper,
        project_raw_record_to_frozen_packet,
        validate_frozen_packet_integrity,
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
        RawRetrievalItem,
        RawRetrievalRecord,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.token_budget_scaffold import (
        TokenBudgetScaffold,
    )


def check_formal_packet_generation_authorization(authorized: bool = False) -> None:
    """Fail-closed execution guard: formal packet generation is unauthorized in Phase 1E."""
    if authorized:
        raise PermissionError("FATAL: Formal packet generation is not authorized in Phase 1E.")


def validate_packet_preflight(repo_root: Path) -> dict[str, Any]:
    """Run non-formal dry preflight validation for Phase 1E.
    
    Verifies:
    1. Parent hashes (question manifest, TCM raw retrieval, Western raw retrieval).
    2. Parsed frozen retrieval records (48 TCM, 48 Western, exactly 4 hits each).
    3. Production baseline prompt hashes and amended research prompt variants.
    4. Real-data read-only / in-memory full projection and integrity validation (96 packets, 384 items).
    5. Token budget offline status (reports NOT_YET_CLEARABLE).
    6. Confirmation that no formal packet output files exist and no packets/ directory is created.
    """
    # 1. Verify parent artifact byte hashes
    q_path = repo_root / QUESTION_MANIFEST_RELPATH
    if not q_path.exists():
        raise FileNotFoundError(f"Question manifest not found at {q_path}")
    q_bytes = q_path.read_bytes()
    q_sha = hashlib.sha256(q_bytes).hexdigest()
    if q_sha != EXPECTED_QUESTION_MANIFEST_SHA256:
        raise ValueError(
            f"Question manifest SHA mismatch: actual {q_sha} != expected {EXPECTED_QUESTION_MANIFEST_SHA256}"
        )

    tcm_path = repo_root / TCM_RAW_RETRIEVAL_RELPATH
    if not tcm_path.exists():
        raise FileNotFoundError(f"TCM raw retrieval artifact not found at {tcm_path}")
    tcm_bytes = tcm_path.read_bytes()
    tcm_sha = hashlib.sha256(tcm_bytes).hexdigest()
    if tcm_sha != EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256:
        raise ValueError(
            f"TCM raw retrieval byte SHA mismatch: actual {tcm_sha} != expected {EXPECTED_TCM_RAW_RETRIEVAL_BYTE_SHA256}"
        )

    west_path = repo_root / WESTERN_RAW_RETRIEVAL_RELPATH
    if not west_path.exists():
        raise FileNotFoundError(f"Western raw retrieval artifact not found at {west_path}")
    west_bytes = west_path.read_bytes()
    west_sha = hashlib.sha256(west_bytes).hexdigest()
    if west_sha != EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256:
        raise ValueError(
            f"Western raw retrieval byte SHA mismatch: actual {west_sha} != expected {EXPECTED_WESTERN_RAW_RETRIEVAL_BYTE_SHA256}"
        )

    # 2. Parse and validate retrieval records
    tcm_records: list[RawRetrievalRecord] = []
    with tcm_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tcm_records.append(RawRetrievalRecord.model_validate_json(line.strip()))
    if len(tcm_records) != EXPECTED_TCM_RECORDS:
        raise ValueError(f"Expected {EXPECTED_TCM_RECORDS} TCM records, got {len(tcm_records)}")

    west_records: list[RawRetrievalRecord] = []
    with west_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                west_records.append(RawRetrievalRecord.model_validate_json(line.strip()))
    if len(west_records) != EXPECTED_WESTERN_RECORDS:
        raise ValueError(f"Expected {EXPECTED_WESTERN_RECORDS} Western records, got {len(west_records)}")

    for rec in tcm_records + west_records:
        if len(rec.results) != HITS_PER_RECORD:
            raise ValueError(f"Record {rec.retrieval_record_id} has {len(rec.results)} hits, expected {HITS_PER_RECORD}")

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

    # 4. Real-data read-only / in-memory full projection and integrity validation
    tcm_packets: list[FrozenEvidencePacket] = []
    for rec in tcm_records:
        pkt = project_raw_record_to_frozen_packet(rec, raw_artifact_sha256=tcm_sha)
        validate_frozen_packet_integrity(pkt, raw_record=rec, raw_artifact_sha256=tcm_sha)
        tcm_packets.append(pkt)

    west_packets: list[FrozenEvidencePacket] = []
    for rec in west_records:
        pkt = project_raw_record_to_frozen_packet(rec, raw_artifact_sha256=west_sha)
        validate_frozen_packet_integrity(pkt, raw_record=rec, raw_artifact_sha256=west_sha)
        west_packets.append(pkt)

    all_packets = tcm_packets + west_packets
    if len(tcm_packets) != EXPECTED_TCM_RECORDS:
        raise ValueError(f"Expected {EXPECTED_TCM_RECORDS} TCM packets, got {len(tcm_packets)}")
    if len(west_packets) != EXPECTED_WESTERN_RECORDS:
        raise ValueError(f"Expected {EXPECTED_WESTERN_RECORDS} Western packets, got {len(west_packets)}")
    if len(all_packets) != EXPECTED_TOTAL_RECORDS:
        raise ValueError(f"Expected {EXPECTED_TOTAL_RECORDS} total packets, got {len(all_packets)}")

    total_items = sum(len(pkt.evidence_items) for pkt in all_packets)
    if total_items != EXPECTED_TOTAL_ITEMS:
        raise ValueError(f"Expected {EXPECTED_TOTAL_ITEMS} total evidence items, got {total_items}")

    tcm_qids = {pkt.question_id for pkt in tcm_packets}
    west_qids = {pkt.question_id for pkt in west_packets}
    if len(tcm_qids) != EXPECTED_QUESTION_COUNT:
        raise ValueError(f"Expected {EXPECTED_QUESTION_COUNT} unique TCM question IDs, got {len(tcm_qids)}")
    if len(west_qids) != EXPECTED_QUESTION_COUNT:
        raise ValueError(f"Expected {EXPECTED_QUESTION_COUNT} unique Western question IDs, got {len(west_qids)}")
    if tcm_qids != west_qids:
        raise ValueError("Mismatch between TCM question IDs and Western question IDs")

    # Fast synthetic sanity check
    synthetic_record = RawRetrievalRecord(
        schema_version="cpaa1_raw_retrieval_v1",
        retrieval_record_id="cpaa1:ret:TEST-001:tcm:R0",
        question_id="TEST-001",
        candidate_id="CAND-001",
        question_text="Synthetic test question text?",
        topic="cough",
        task_type="evidence_description",
        perspective="tcm",
        question_manifest_sha256=EXPECTED_QUESTION_MANIFEST_SHA256,
        corpus_id="tcm_v1",
        corpus_version="tcm-research-corpus-v1",
        corpus_sha256="316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9",
        retrieval_algorithm_id="CPAA1-R0-LEXICAL-V1",
        query_text="Synthetic test question text?",
        query_text_sha256=hashlib.sha256("Synthetic test question text?".encode("utf-8")).hexdigest(),
        requested_top_k=4,
        returned_count=4,
        positive_score_count=4,
        zero_score_count=0,
        retrieval_status="SUCCESS",
        retrieved_at_utc="2026-09-29T00:00:00Z",
        implementation_commit="b234f40f2beb017431de2ce27256b983d3eeb177",
        record_canonical_sha256="0" * 64,
        results=[
            RawRetrievalItem(
                rank=i,
                retrieval_score=1.0 - (i * 0.1),
                score_is_zero=False,
                chunk_id=f"tcm_chunk_{i}",
                corpus_record_ordinal=i * 10,
                source_id=f"tcm_src_{i}",
                source_title=f"Source Title {i}",
                exact_original_chunk_text=f"Synthetic chunk text {i} for testing.",
                chunk_text_utf8_sha256=hashlib.sha256(f"Synthetic chunk text {i} for testing.".encode("utf-8")).hexdigest(),
                chunk_record_canonical_sha256="1" * 64,
            )
            for i in range(1, 5)
        ],
    )
    synth_packet = project_raw_record_to_frozen_packet(synthetic_record, raw_artifact_sha256="a" * 64)
    synth_wrapper = project_frozen_packet_to_compatibility_wrapper(synth_packet)
    assert len(synth_packet.evidence_items) == 4
    assert len(synth_wrapper.claims) == 4
    assert synth_wrapper.claims[0].claim_kind == "source_excerpt"

    # 5. Token budget offline scaffolding check
    tb_rec = TokenBudgetScaffold.evaluate_role_budget(
        role="governance",
        question_id="TEST-001",
        system_prompt=RESEARCH_SYSTEM_PROMPTS["governance"],
        user_payload="Synthetic payload",
    )
    if tb_rec.status != "NOT_YET_CLEARABLE":
        raise ValueError(f"Expected token budget status NOT_YET_CLEARABLE, got {tb_rec.status}")

    # 6. Verify absence of formal packet output files
    packets_dir = repo_root / "research/experiments/cross_perspective_advisory_ablation_v1/packets"
    forbidden_files = [
        packets_dir / "tcm_packets.jsonl",
        packets_dir / "western_packets.jsonl",
        packets_dir / "packet_manifest.json",
        packets_dir / "packet_freeze_receipt.json",
    ]
    for p in forbidden_files:
        if p.exists():
            raise FileNotFoundError(f"Formal packet output file must NOT exist in Phase 1E: {p}")

    return {
        "status": "PASS",
        "study_id": STUDY_ID,
        "amendment_id": AMENDMENT_ID,
        "packet_contract_id": PACKET_CONTRACT_ID,
        "question_manifest_sha256": q_sha,
        "tcm_raw_retrieval_byte_sha256": tcm_sha,
        "western_raw_retrieval_byte_sha256": west_sha,
        "parsed_tcm_records": len(tcm_records),
        "parsed_western_records": len(west_records),
        "total_parsed_records": len(tcm_records) + len(west_records),
        "total_parsed_hits": (len(tcm_records) + len(west_records)) * HITS_PER_RECORD,
        "in_memory_tcm_packets": len(tcm_packets),
        "in_memory_western_packets": len(west_packets),
        "in_memory_total_packets": len(all_packets),
        "in_memory_total_items": total_items,
        "all_packets_validated": True,
        "expected_tcm_packets": EXPECTED_TCM_RECORDS,
        "expected_western_packets": EXPECTED_WESTERN_RECORDS,
        "expected_total_packets": EXPECTED_TOTAL_RECORDS,
        "expected_tcm_items": EXPECTED_TCM_ITEMS,
        "expected_western_items": EXPECTED_WESTERN_ITEMS,
        "expected_total_items": EXPECTED_TOTAL_ITEMS,
        "token_budget_scaffold_status": tb_rec.status,
        "formal_packets_materialized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1E Packet Preflight Runner for Advisory Ablation Study"
    )
    parser.add_argument(
        "--execute-formal-packet-generation",
        action="store_true",
        default=False,
        help="EXECUTION GUARD: authorize formal packet generation (FORBIDDEN in Phase 1E)",
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
        print("PHASE 1E PACKET PREFLIGHT (NON-FORMAL DRY MODE)")
        print("=" * 60)
        report = validate_packet_preflight(repo_root)
        print("PREFLIGHT VALIDATION: PASS")
        for k, v in report.items():
            print(f"  {k}: {v}")
        print("=" * 60)
        print("FORMAL PACKET GENERATION WAS NOT EXECUTED.")
        print("NO FORMAL PACKET OUTPUT FILES WERE GENERATED.")
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
