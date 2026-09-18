from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.formal_eval import (  # noqa: E402
    BENCHMARK_COMMIT,
    BENCHMARK_MANIFEST_SHA256,
    BENCHMARK_SHA256,
    BENCHMARK_VERSION,
    CANDIDATE_DEPTH,
    CONDITIONS,
    CORPUS_CHUNKS_SHA256,
    FINAL_TOP_K,
    GENERATOR_MAX_TOKENS,
    GENERATOR_MODEL,
    GENERATOR_PROVIDER,
    GENERATOR_TEMPERATURE,
    GENERATOR_TIMEOUT_SECONDS,
    INTENDED_CASES,
    INTENDED_CELLS,
    JUDGE_MAX_TOKENS,
    JUDGE_MODEL,
    JUDGE_PROVIDER,
    JUDGE_TEMPERATURE,
    JUDGE_TIMEOUT_SECONDS,
    PROTOCOL_VERSION,
    RETRIEVAL_CONDITIONS,
    RETRYABLE_ERROR_TYPES,
    RUNTIME_COMMIT,
    SOURCE_REGISTRY_SHA256,
    balanced_execution_order,
    headline_retrieval_case_ids,
    insufficient_case_ids,
    load_frozen_cases,
    verify_frozen_inputs,
)
from western.formal_judge import FormalJudgeOutput  # noqa: E402


OUT = ROOT / "research/experiments/western_formal_v0_1/protocol"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    verified = verify_frozen_inputs(ROOT)
    cases = load_frozen_cases(ROOT)
    order = balanced_execution_order(cases)
    topic_counts = dict(sorted(Counter(case["topic"] for case in cases).items()))
    type_counts = dict(sorted(Counter(case["question_type"] for case in cases).items()))
    answerability_counts = dict(sorted(Counter(case["answerability"] for case in cases).items()))
    eligible = headline_retrieval_case_ids(cases)
    insufficient = insufficient_case_ids(cases)
    assert len(cases) == INTENDED_CASES
    assert len(order) == INTENDED_CELLS
    assert len(eligible) == 42
    assert len(insufficient) == 6
    protocol = {
        "protocol_name": "MediRAG-West Formal Evaluation Protocol v0.1",
        "protocol_version": PROTOCOL_VERSION,
        "status": "frozen_before_formal_execution",
        "scientific_scope": "Performance only within the frozen 16-source, 271-chunk Western pilot corpus; not general medical or clinical competence.",
        "runtime_commit": RUNTIME_COMMIT,
        "benchmark_commit": BENCHMARK_COMMIT,
        "benchmark_version": BENCHMARK_VERSION,
        **verified,
        "formal_case_count": len(cases),
        "intended_generation_cells": INTENDED_CELLS,
        "topic_counts": topic_counts,
        "question_type_counts": type_counts,
        "answerability_counts": answerability_counts,
        "research_questions": {
            "W-RQ1": "How do retrieval strategies affect gold-evidence retrieval within the frozen MediRAG-West pilot corpus?",
            "W-RQ2": "With the generator held fixed, how do retrieval strategies affect evidence coverage and unsupported-claim behavior in generated Western pilot answers?",
            "W-RQ3": "How does the system behave when the frozen pilot corpus provides incomplete or insufficient evidence?",
        },
        "retrieval_conditions": RETRIEVAL_CONDITIONS,
        "headline_retrieval_denominator": {
            "policy": "supported or partially_supported cases with non-empty primary gold; all insufficient cases reported separately",
            "case_count": len(eligible),
        },
        "retrieval_metrics": [
            "macro_primary_gold_chunk_recall_at_4",
            "aggregate_primary_gold_chunk_recall_at_4",
            "macro_primary_source_recall_at_4",
            "aggregate_primary_source_recall_at_4",
            "mrr_first_primary_gold_chunk",
            "hit_at_4",
        ],
        "secondary_retrieval_diagnostics": ["primary_or_secondary_gold_hit_at_4", "primary_or_secondary_gold_recall_at_4"],
        "generator": {
            "provider": GENERATOR_PROVIDER,
            "model": GENERATOR_MODEL,
            "temperature": GENERATOR_TEMPERATURE,
            "max_tokens": GENERATOR_MAX_TOKENS,
            "retrieval_top_k": FINAL_TOP_K,
            "evidence_excerpt_max_characters": 1000,
            "timeout_seconds": GENERATOR_TIMEOUT_SECONDS,
            "prompt_contract": "current frozen WesternEvidenceAgent SYSTEM_PROMPT and generation prompt unchanged",
            "generations_per_cell": 1,
        },
        "judge": {
            "judge_type": "automated_secondary_model",
            "provider": JUDGE_PROVIDER,
            "model": JUDGE_MODEL,
            "temperature": JUDGE_TEMPERATURE,
            "max_tokens": JUDGE_MAX_TOKENS,
            "timeout_seconds": JUDGE_TIMEOUT_SECONDS,
            "human_verified": False,
            "domain_expert_verified": False,
        },
        "technical_retry_policy": {
            "maximum_retries": 1,
            "retryable_error_types": sorted(RETRYABLE_ERROR_TYPES),
            "nonretryable_reasons": [
                "weak_answer_quality", "unsupported_answer", "insufficient_evidence", "poor_citation_behavior",
                "model_disagreement", "content_level_failure", "judge_schema_or_content_failure",
            ],
        },
        "execution_order": {
            "policy": "deterministic balanced four-condition rotation by frozen case index",
            "condition_order": list(CONDITIONS),
            "cell_count": len(order),
        },
        "stages": {
            "A": "retrieval only; sealed output is immutable Stage B input",
            "B": "generation only from sealed Stage A; sealed output is immutable Stage C input",
            "C": "judge only from sealed Stage A and B outputs",
        },
        "generation_metrics": [
            "claim_support_rate", "partially_supported_claim_rate", "unsupported_claim_rate",
            "answers_with_any_unsupported_claim", "mean_unsupported_claims_per_completed_answer",
            "evidence_point_coverage_rate", "evidence_point_partial_coverage_rate",
        ],
        "insufficient_evidence_metrics": [
            "system_abstained", "explicitly_stated_evidence_insufficiency",
            "substantive_answer_despite_insufficiency", "overclaimed_beyond_pilot_evidence",
            "appropriate_insufficiency_handling",
        ],
        "provenance_metrics": {
            "name": "provenance_integrity_rate",
            "scope": "application-level provenance membership and resolution; not sentence-level citation correctness",
        },
        "observable_scope_flags": [
            "diagnosis_like_personalized_statement", "individualized_dosing",
            "prescription_like_recommendation", "research_or_educational_limitation_preserved",
        ],
        "latency_and_reliability": [
            "retrieval_latency_ms", "generation_latency_ms", "judge_latency_ms",
            "first_attempt_provider_success", "final_provider_completion", "technical_failure_count",
            "retry_count", "total_experiment_elapsed_time",
        ],
        "primary_comparisons": ["R0_vs_R1", "R0_vs_R2", "R0_vs_R3"],
        "statistical_plan": {
            "paired_binary": "McNemar where applicable",
            "paired_bounded": "paired differences with 95% bootstrap confidence intervals where implemented",
            "report": "exact sample sizes; do not overemphasize p-values",
        },
        "raw_output_policy": "new run_id for every repeat; never overwrite a run or sealed stage",
        "formal_results_generated": False,
    }
    write_json(OUT / "protocol.json", protocol)
    write_json(OUT / "execution_order.json", {
        "protocol_version": PROTOCOL_VERSION,
        "policy": "case n starts with condition offset (n-1) mod 4, then cycles R0,R1,R2,R3",
        "cell_count": len(order),
        "cells": order,
    })
    write_json(OUT / "judge_schema.json", FormalJudgeOutput.model_json_schema())
    protocol_hash = hashlib.sha256((OUT / "protocol.json").read_bytes()).hexdigest()
    print(json.dumps({
        "protocol_sha256": protocol_hash,
        "case_count": len(cases),
        "cell_count": len(order),
        "retrieval_denominator": len(eligible),
        "insufficient_case_count": len(insufficient),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
