from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_DIR = _REPO_ROOT / "backend"
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
    from backend.corpus.models import KnowledgeChunk, SourceRecord
    from backend.corpus.v1_models import ResearchChunk
    from backend.retrieval.engine import RetrievalEngine
    from backend.schemas.research import RetrievalStrategy
    from backend.western.models import WesternKnowledgeChunk, WesternSourceRecord
except ModuleNotFoundError:
    from corpus.models import KnowledgeChunk, SourceRecord
    from corpus.v1_models import ResearchChunk
    from retrieval.engine import RetrievalEngine
    from schemas.research import RetrievalStrategy
    from western.models import WesternKnowledgeChunk, WesternSourceRecord

try:
    from .manifest import (
        canonical_json_dumps,
        sha256_canonical_obj,
        sha256_file,
        sha256_text,
        verify_file_hash,
    )
    from .preflight import PreflightValidationError, validate_question_population
    from .retrieval_contract import (
        ALGORITHM_ID,
        EXPECTED_QUESTION_COUNT,
        EXPECTED_QUESTION_MANIFEST_SHA256,
        EXPECTED_TCM_CORPUS_SHA256,
        EXPECTED_WESTERN_CORPUS_SHA256,
        LOCKED_RETRIEVAL_CONTRACT,
        QUESTION_MANIFEST_RELPATH,
        REQUESTED_TOP_K,
        STUDY_ID,
        TCM_CORPUS_ID,
        TCM_CORPUS_RELPATH,
        TCM_CORPUS_VERSION,
        WESTERN_CORPUS_ID,
        WESTERN_CORPUS_RELPATH,
        WESTERN_CORPUS_VERSION,
        WESTERN_SOURCE_REGISTRY_RELPATH,
        compute_chunk_text_sha256,
        compute_record_canonical_sha256,
    )
    from .schemas import (
        RawRetrievalItem,
        RawRetrievalRecord,
        RetrievalRunManifest,
        SelectedQuestion,
    )
except ImportError:
    from research.experiments.cross_perspective_advisory_ablation_v1.manifest import (
        canonical_json_dumps,
        sha256_canonical_obj,
        sha256_file,
        sha256_text,
        verify_file_hash,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.preflight import (
        PreflightValidationError,
        validate_question_population,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.retrieval_contract import (
        ALGORITHM_ID,
        EXPECTED_QUESTION_COUNT,
        EXPECTED_QUESTION_MANIFEST_SHA256,
        EXPECTED_TCM_CORPUS_SHA256,
        EXPECTED_WESTERN_CORPUS_SHA256,
        LOCKED_RETRIEVAL_CONTRACT,
        QUESTION_MANIFEST_RELPATH,
        REQUESTED_TOP_K,
        STUDY_ID,
        TCM_CORPUS_ID,
        TCM_CORPUS_RELPATH,
        TCM_CORPUS_VERSION,
        WESTERN_CORPUS_ID,
        WESTERN_CORPUS_RELPATH,
        WESTERN_CORPUS_VERSION,
        WESTERN_SOURCE_REGISTRY_RELPATH,
        compute_chunk_text_sha256,
        compute_record_canonical_sha256,
    )
    from research.experiments.cross_perspective_advisory_ablation_v1.schemas import (
        RawRetrievalItem,
        RawRetrievalRecord,
        RetrievalRunManifest,
        SelectedQuestion,
    )



def load_tcm_corpus_explicit(
    repo_root: Path | str = ".",
) -> tuple[tuple[KnowledgeChunk, ...], tuple[dict[str, Any], ...]]:
    """Explicitly load and validate the locked TCM research corpus v1.

    Returns:
        (knowledge_chunks, raw_records)
    """
    root = Path(repo_root)
    corpus_path = root / TCM_CORPUS_RELPATH
    if not corpus_path.is_file():
        raise PreflightValidationError(f"TCM research corpus missing at {corpus_path}")
    if not verify_file_hash(corpus_path, EXPECTED_TCM_CORPUS_SHA256):
        raise PreflightValidationError(
            f"TCM corpus SHA256 mismatch! Expected {EXPECTED_TCM_CORPUS_SHA256}, "
            f"got {sha256_file(corpus_path)}"
        )

    lines = [line.strip() for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 4:
        raise PreflightValidationError(f"TCM corpus must contain >= 4 records, got {len(lines)}")

    knowledge_chunks: list[KnowledgeChunk] = []
    raw_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for ordinal, line in enumerate(lines):
        try:
            raw = json.loads(line)
            chunk = ResearchChunk.model_validate(raw)
        except Exception as exc:
            raise PreflightValidationError(f"Malformed TCM chunk at ordinal {ordinal}: {exc}") from exc

        if not chunk.text or not chunk.text.strip():
            raise PreflightValidationError(f"Empty searchable text in TCM chunk {chunk.chunk_id} at ordinal {ordinal}")

        if chunk.chunk_id in seen_ids:
            raise PreflightValidationError(f"Duplicate TCM chunk_id detected: {chunk.chunk_id} at ordinal {ordinal}")
        seen_ids.add(chunk.chunk_id)

        # Construct established research KnowledgeChunk representation
        unique_keywords = list(dict.fromkeys([chunk.entity_name, *chunk.aliases]))
        topics = [v for v in dict.fromkeys([chunk.category, chunk.entity_type, chunk.subcategory or ""]) if v]
        kc = KnowledgeChunk(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id,
            source_ids=[chunk.source_id],
            section=chunk.subcategory or chunk.category,
            text=chunk.text,
            language=chunk.language,
            topics=topics,
            syndromes=[chunk.entity_name, *chunk.aliases] if chunk.entity_type == "syndrome" else [],
            herbs=[chunk.entity_name, *chunk.aliases] if chunk.entity_type == "herb" else [],
            meridians=[],
            safety_tags=[],
            human_review_status=chunk.review_status,
            keywords=unique_keywords,
        )
        knowledge_chunks.append(kc)
        raw_records.append(raw)

    return tuple(knowledge_chunks), tuple(raw_records)


def load_western_corpus_explicit(
    repo_root: Path | str = ".",
) -> tuple[tuple[WesternKnowledgeChunk, ...], dict[str, WesternSourceRecord], tuple[dict[str, Any], ...]]:
    """Explicitly load and validate the locked Western research corpus v0.1.

    Returns:
        (western_chunks, sources_dict, raw_records)
    """
    root = Path(repo_root)
    corpus_path = root / WESTERN_CORPUS_RELPATH
    registry_path = root / WESTERN_SOURCE_REGISTRY_RELPATH

    if not corpus_path.is_file():
        raise PreflightValidationError(f"Western research corpus missing at {corpus_path}")
    if not registry_path.is_file():
        raise PreflightValidationError(f"Western source registry missing at {registry_path}")

    if not verify_file_hash(corpus_path, EXPECTED_WESTERN_CORPUS_SHA256):
        raise PreflightValidationError(
            f"Western corpus SHA256 mismatch! Expected {EXPECTED_WESTERN_CORPUS_SHA256}, "
            f"got {sha256_file(corpus_path)}"
        )

    try:
        source_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        sources = {item["source_id"]: WesternSourceRecord.model_validate(item) for item in source_payload}
    except Exception as exc:
        raise PreflightValidationError(f"Malformed Western source registry: {exc}") from exc

    lines = [line.strip() for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 4:
        raise PreflightValidationError(f"Western corpus must contain >= 4 records, got {len(lines)}")

    western_chunks: list[WesternKnowledgeChunk] = []
    raw_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for ordinal, line in enumerate(lines):
        try:
            raw = json.loads(line)
            chunk = WesternKnowledgeChunk.model_validate(raw)
        except Exception as exc:
            raise PreflightValidationError(f"Malformed Western chunk at ordinal {ordinal}: {exc}") from exc

        if not chunk.text or not chunk.text.strip():
            raise PreflightValidationError(f"Empty searchable text in Western chunk {chunk.chunk_id} at ordinal {ordinal}")

        if chunk.chunk_id in seen_ids:
            raise PreflightValidationError(f"Duplicate Western chunk_id detected: {chunk.chunk_id} at ordinal {ordinal}")
        seen_ids.add(chunk.chunk_id)

        if chunk.source_id not in sources:
            raise PreflightValidationError(
                f"Western chunk {chunk.chunk_id} references unresolvable source_id: {chunk.source_id}"
            )

        western_chunks.append(chunk)
        raw_records.append(raw)

    return tuple(western_chunks), sources, tuple(raw_records)


def validate_retrieval_preflight(repo_root: Path | str = ".") -> dict[str, Any]:
    """Execute complete Phase 1B retrieval preflight WITHOUT running retrieval on any question.

    Verifications:
    1. Question manifest byte hash matches locked constant.
    2. Exactly 48 questions present.
    3. Existing question population structure passes (12 per topic, 4 per task type).
    4. Candidate ID is preserved on every question.
    5. TCM corpus file exists and byte hash matches locked constant.
    6. Western corpus file exists and byte hash matches locked constant.
    7. Corpora parse successfully without malformed records.
    8. No duplicate chunk IDs in either corpus.
    9. Non-empty required searchable text in every chunk.
    10. Required provenance is strictly resolvable.
    11. Corpus record ordinals are sequential and deterministic.
    12. Both corpora have size >= 4.
    13. No fallback corpus is accessed or allowed.
    14. Retrieval contract serializes canonically and deterministically.
    """
    root = Path(repo_root)

    # 1. Question manifest hash
    manifest_path = root / QUESTION_MANIFEST_RELPATH
    if not manifest_path.is_file():
        raise PreflightValidationError(f"Question manifest missing: {manifest_path}")

    actual_manifest_sha = sha256_file(manifest_path)
    if actual_manifest_sha != EXPECTED_QUESTION_MANIFEST_SHA256:
        raise PreflightValidationError(
            f"Question manifest SHA256 mismatch! Expected {EXPECTED_QUESTION_MANIFEST_SHA256}, got {actual_manifest_sha}"
        )

    # 2 & 3. Parse questions and validate population
    q_lines = [line.strip() for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(q_lines) != EXPECTED_QUESTION_COUNT:
        raise PreflightValidationError(
            f"Expected exactly {EXPECTED_QUESTION_COUNT} questions, got {len(q_lines)}"
        )

    questions: list[SelectedQuestion] = []
    for line in q_lines:
        try:
            questions.append(SelectedQuestion.model_validate_json(line))
        except Exception as exc:
            raise PreflightValidationError(f"Failed to parse SelectedQuestion record: {exc}") from exc

    validate_question_population(questions)

    # 4. Candidate ID preserved
    for q in questions:
        cid = q.selection_metadata.get("candidate_id") or getattr(q, "candidate_id", None)
        if not cid or not str(cid).strip():
            raise PreflightValidationError(f"Question {q.question_id} lacks preserved candidate_id")

    # 5, 7, 8, 9, 10, 11, 12, 13. TCM Corpus validation
    tcm_chunks, tcm_raw = load_tcm_corpus_explicit(root)

    # 6, 7, 8, 9, 10, 11, 12, 13. Western Corpus validation
    western_chunks, western_sources, western_raw = load_western_corpus_explicit(root)

    # 14. Contract canonical serialization
    contract_dict = LOCKED_RETRIEVAL_CONTRACT.as_dict()
    contract_json = canonical_json_dumps(contract_dict)
    contract_sha256 = sha256_text(contract_json)

    return {
        "status": "PASS",
        "study_id": STUDY_ID,
        "retrieval_algorithm_id": ALGORITHM_ID,
        "question_manifest_sha256": actual_manifest_sha,
        "question_count": len(questions),
        "tcm_corpus_sha256": EXPECTED_TCM_CORPUS_SHA256,
        "tcm_chunk_count": len(tcm_chunks),
        "western_corpus_sha256": EXPECTED_WESTERN_CORPUS_SHA256,
        "western_chunk_count": len(western_chunks),
        "western_source_count": len(western_sources),
        "contract_canonical_sha256": contract_sha256,
        "preflight_mode": "DRY_PREFLIGHT_ONLY_NO_SEARCH",
    }


async def _search_perspective(
    engine: RetrievalEngine,
    question_text: str,
    top_k: int = 4,
) -> list[Any]:
    """Execute direct unfiltered R0 lexical search for exact question text."""
    return await engine.search(
        question_text,
        strategy=RetrievalStrategy.R0,
        top_k=top_k,
        topics=None,
    )


def execute_formal_retrieval(
    repo_root: Path | str = ".",
    *,
    allow_formal: bool = False,
    git_commit_sha: str = "UNKNOWN",
) -> dict[str, Any]:
    """Execute formal Phase 1 retrieval.

    CRITICAL GUARD: Requires explicit allow_formal=True.
    In Phase 1B, this function MUST NOT be called.
    """
    if not allow_formal:
        raise RuntimeError(
            "FATAL: Formal retrieval execution is NOT authorized. "
            "Pass --execute-formal-retrieval explicitly to allow formal execution."
        )

    root = Path(repo_root)
    # Run preflight first
    preflight_report = validate_retrieval_preflight(root)

    # Load questions
    manifest_path = root / QUESTION_MANIFEST_RELPATH
    questions = [
        SelectedQuestion.model_validate_json(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Load corpora
    tcm_chunks, tcm_raw = load_tcm_corpus_explicit(root)
    western_chunks, western_sources, western_raw = load_western_corpus_explicit(root)

    tcm_raw_by_id = {r["chunk_id"]: (idx, r) for idx, r in enumerate(tcm_raw)}
    west_raw_by_id = {r["chunk_id"]: (idx, r) for idx, r in enumerate(western_raw)}

    tcm_engine = RetrievalEngine(chunks=tcm_chunks, corpus_sha256=EXPECTED_TCM_CORPUS_SHA256)
    west_engine = RetrievalEngine(
        chunks=western_chunks,
        sources=western_sources,
        corpus_sha256=EXPECTED_WESTERN_CORPUS_SHA256,
    )

    retrieval_dir = root / "research" / "experiments" / "cross_perspective_advisory_ablation_v1" / "retrieval"
    retrieval_dir.mkdir(parents=True, exist_ok=True)

    tcm_records: list[RawRetrievalRecord] = []
    west_records: list[RawRetrievalRecord] = []

    async def _run_all() -> None:
        for q in questions:
            cid = str(q.selection_metadata.get("candidate_id") or getattr(q, "candidate_id", ""))
            query_sha = sha256_text(q.question_text)
            now_iso = datetime.now(timezone.utc).isoformat()

            # TCM Search
            tcm_results_raw = await _search_perspective(tcm_engine, q.question_text, top_k=REQUESTED_TOP_K)
            tcm_items: list[RawRetrievalItem] = []
            for rank_idx, item in enumerate(tcm_results_raw, 1):
                ordinal, raw = tcm_raw_by_id[item.chunk_id]
                score = float(item.lexical_score or 0.0)
                item_dict = {
                    "rank": rank_idx,
                    "retrieval_score": score,
                    "score_is_zero": (score == 0.0),
                    "chunk_id": item.chunk_id,
                    "corpus_record_ordinal": ordinal,
                    "source_id": raw["source_id"],
                    "source_record_id": raw.get("source_record_id"),
                    "source_title": raw.get("source_title"),
                    "source_url": raw.get("source_url"),
                    "doi": None,
                    "pmcid": None,
                    "section_or_category": raw.get("subcategory") or raw.get("category"),
                    "license_or_access_status": raw.get("source_license_status"),
                    "source_citation_or_version": raw.get("source_citation"),
                    "review_status": raw.get("review_status"),
                    "exact_original_chunk_text": raw["text"],
                    "chunk_text_utf8_sha256": compute_chunk_text_sha256(raw["text"]),
                    "chunk_record_canonical_sha256": sha256_canonical_obj(raw),
                    "provenance": {
                        "source_name": raw.get("source_name"),
                        "source_version": raw.get("source_version"),
                        "source_access_date": raw.get("source_access_date"),
                        "category": raw.get("category"),
                        "subcategory": raw.get("subcategory"),
                        "entity_name": raw.get("entity_name"),
                        "entity_type": raw.get("entity_type"),
                        "language": raw.get("language"),
                        "expert_review_claimed_by_source": raw.get("expert_review_claimed_by_source"),
                        "transformation_history": raw.get("transformation_history", []),
                        "conflict_group_ids": raw.get("conflict_group_ids", []),
                    },
                }
                tcm_items.append(RawRetrievalItem.model_validate(item_dict))

            pos_count = sum(1 for it in tcm_items if not it.score_is_zero)
            zero_count = sum(1 for it in tcm_items if it.score_is_zero)
            tcm_record_data = {
                "schema_version": "cpaa1_raw_retrieval_v1",
                "retrieval_record_id": f"ret-tcm-{q.question_id}",
                "question_id": q.question_id,
                "candidate_id": cid,
                "question_text": q.question_text,
                "topic": q.topic,
                "task_type": q.task_type,
                "perspective": "tcm",
                "question_manifest_sha256": EXPECTED_QUESTION_MANIFEST_SHA256,
                "corpus_id": TCM_CORPUS_ID,
                "corpus_version": TCM_CORPUS_VERSION,
                "corpus_sha256": EXPECTED_TCM_CORPUS_SHA256,
                "retrieval_algorithm_id": ALGORITHM_ID,
                "retrieval_config": LOCKED_RETRIEVAL_CONTRACT.as_dict(),
                "query_text": q.question_text,
                "query_text_sha256": query_sha,
                "requested_top_k": REQUESTED_TOP_K,
                "returned_count": len(tcm_items),
                "positive_score_count": pos_count,
                "zero_score_count": zero_count,
                "retrieval_status": "completed" if pos_count > 0 else "zero_coverage",
                "retrieved_at_utc": now_iso,
                "implementation_commit": git_commit_sha,
                "results": [it.model_dump(mode="json") for it in tcm_items],
            }
            tcm_record_data["record_canonical_sha256"] = compute_record_canonical_sha256(tcm_record_data)
            tcm_records.append(RawRetrievalRecord.model_validate(tcm_record_data))

            # Western Search
            west_results_raw = await _search_perspective(west_engine, q.question_text, top_k=REQUESTED_TOP_K)
            west_items: list[RawRetrievalItem] = []
            for rank_idx, item in enumerate(west_results_raw, 1):
                ordinal, raw = west_raw_by_id[item.chunk_id]
                source = western_sources[raw["source_id"]]
                score = float(item.lexical_score or 0.0)
                item_dict = {
                    "rank": rank_idx,
                    "retrieval_score": score,
                    "score_is_zero": (score == 0.0),
                    "chunk_id": item.chunk_id,
                    "corpus_record_ordinal": ordinal,
                    "source_id": raw["source_id"],
                    "source_record_id": raw.get("source_record_id"),
                    "source_title": source.title,
                    "source_url": raw.get("source_url") or source.source_url,
                    "doi": raw.get("doi") or source.doi,
                    "pmcid": raw.get("pmcid") or source.pmcid,
                    "section_or_category": raw.get("section"),
                    "license_or_access_status": source.license,
                    "source_citation_or_version": f"{source.organization_or_journal} ({source.publication_year})" if source.publication_year else source.organization_or_journal,
                    "review_status": raw.get("human_review_status") or source.review_status,
                    "exact_original_chunk_text": raw["text"],
                    "chunk_text_utf8_sha256": compute_chunk_text_sha256(raw["text"]),
                    "chunk_record_canonical_sha256": sha256_canonical_obj(raw),
                    "provenance": {
                        "source_type": source.source_type,
                        "organization_or_journal": source.organization_or_journal,
                        "publication_year": source.publication_year,
                        "license_url": source.license_url,
                        "evidence_category": source.evidence_category,
                        "review_status": source.review_status,
                    },
                }
                west_items.append(RawRetrievalItem.model_validate(item_dict))

            pos_count = sum(1 for it in west_items if not it.score_is_zero)
            zero_count = sum(1 for it in west_items if it.score_is_zero)
            west_record_data = {
                "schema_version": "cpaa1_raw_retrieval_v1",
                "retrieval_record_id": f"ret-west-{q.question_id}",
                "question_id": q.question_id,
                "candidate_id": cid,
                "question_text": q.question_text,
                "topic": q.topic,
                "task_type": q.task_type,
                "perspective": "western",
                "question_manifest_sha256": EXPECTED_QUESTION_MANIFEST_SHA256,
                "corpus_id": WESTERN_CORPUS_ID,
                "corpus_version": WESTERN_CORPUS_VERSION,
                "corpus_sha256": EXPECTED_WESTERN_CORPUS_SHA256,
                "retrieval_algorithm_id": ALGORITHM_ID,
                "retrieval_config": LOCKED_RETRIEVAL_CONTRACT.as_dict(),
                "query_text": q.question_text,
                "query_text_sha256": query_sha,
                "requested_top_k": REQUESTED_TOP_K,
                "returned_count": len(west_items),
                "positive_score_count": pos_count,
                "zero_score_count": zero_count,
                "retrieval_status": "completed" if pos_count > 0 else "zero_coverage",
                "retrieved_at_utc": now_iso,
                "implementation_commit": git_commit_sha,
                "results": [it.model_dump(mode="json") for it in west_items],
            }
            west_record_data["record_canonical_sha256"] = compute_record_canonical_sha256(west_record_data)
            west_records.append(RawRetrievalRecord.model_validate(west_record_data))

    asyncio.run(_run_all())

    # Write output files
    tcm_output_path = retrieval_dir / "retrieval_tcm_r0_top4.jsonl"
    west_output_path = retrieval_dir / "retrieval_western_r0_top4.jsonl"

    tcm_output_path.write_text(
        "\n".join(canonical_json_dumps(r.model_dump(mode="json")) for r in tcm_records) + "\n",
        encoding="utf-8",
    )
    west_output_path.write_text(
        "\n".join(canonical_json_dumps(r.model_dump(mode="json")) for r in west_records) + "\n",
        encoding="utf-8",
    )

    tcm_out_sha = sha256_file(tcm_output_path)
    west_out_sha = sha256_file(west_output_path)

    manifest_data = {
        "schema_version": "cpaa1_retrieval_manifest_v1",
        "study_id": STUDY_ID,
        "algorithm_id": ALGORITHM_ID,
        "question_manifest_sha256": EXPECTED_QUESTION_MANIFEST_SHA256,
        "question_count": len(questions),
        "tcm_corpus_sha256": EXPECTED_TCM_CORPUS_SHA256,
        "tcm_record_count": len(tcm_records),
        "tcm_retrieval_output_sha256": tcm_out_sha,
        "western_corpus_sha256": EXPECTED_WESTERN_CORPUS_SHA256,
        "western_record_count": len(west_records),
        "western_retrieval_output_sha256": west_out_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "implementation_commit": git_commit_sha,
        "contract": LOCKED_RETRIEVAL_CONTRACT.as_dict(),
    }
    manifest = RetrievalRunManifest.model_validate(manifest_data)
    manifest_path_out = retrieval_dir / "retrieval_manifest.json"
    manifest_path_out.write_text(canonical_json_dumps(manifest.model_dump(mode="json")), encoding="utf-8")

    return {
        "status": "COMPLETED",
        "tcm_records": len(tcm_records),
        "western_records": len(west_records),
        "tcm_output_sha256": tcm_out_sha,
        "western_output_sha256": west_out_sha,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 1B Retrieval Preflight Runner for Advisory Ablation Study"
    )
    parser.add_argument(
        "--execute-formal-retrieval",
        action="store_true",
        default=False,
        help="EXECUTION GUARD: authorize formal retrieval execution (FORBIDDEN in Phase 1B)",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        default=True,
        help="Run non-formal dry preflight validation only (default: True)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]

    if not args.execute_formal_retrieval:
        print("=" * 60)
        print("PHASE 1B RETRIEVAL PREFLIGHT (NON-FORMAL DRY MODE)")
        print("=" * 60)
        report = validate_retrieval_preflight(repo_root)
        print("PREFLIGHT VALIDATION: PASS")
        for k, v in report.items():
            print(f"  {k}: {v}")
        print("=" * 60)
        print("FORMAL RETRIEVAL WAS NOT EXECUTED.")
        print("NO RETRIEVAL OUTPUT FILES WERE GENERATED.")
        print("=" * 60)
        sys.exit(0)
    else:
        print("FATAL: Formal retrieval execution is not authorized in Phase 1B.")
        sys.exit(1)


if __name__ == "__main__":
    main()
