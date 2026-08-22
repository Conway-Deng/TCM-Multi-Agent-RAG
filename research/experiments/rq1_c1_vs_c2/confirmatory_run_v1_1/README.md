# RQ1 confirmatory formal run v1.1

Status: `PREPARED_FROZEN` — zero provider runs completed.

`formal_execution_manifest.json` and `execution_order.json` were locked before provider execution. Run IDs, order, benchmark/corpus hashes, model, retrieval, generation settings, retry/timeout/fallback policies, and grounding policy are immutable. Completed records are appended immediately to `results.jsonl`; resume skips validated completed question/condition pairs.

Launch from the repository root with `./scripts/run-rq1-confirmatory.ps1`. After 200 planned executions, the pipeline validates the run, computes objective metrics, exports `semantic_review_for_gpt.csv`, and stops at `SEMANTIC_REVIEW_REQUIRED` without assigning semantic labels.
