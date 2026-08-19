# TCM Gold Benchmark v1

Status: `DRAFT_SOURCE_GROUNDED`; not clinically validated and not experiment-ready until human review.

The benchmark contains 50 deterministic, source-derived questions from the frozen TCM Research Corpus v1. Each atomic gold fact links to preferred evidence IDs and a short excerpt; alternate IDs are provided where equivalent records are appropriate. Multi-target items keep target-specific facts separate and use `relationship_gold_status=not_established` unless explicit co-occurring evidence exists (none in this draft).

## Review workflow

1. Open `review_sheet.csv`.
2. Check each question, atomic fact, source, chunk ID, and excerpt against the local corpus.
3. Set `review_status` to `APPROVED`, `REVISE`, or `REMOVE` and record notes.
4. Resolve all non-APPROVED rows before running C1/C2 experiments.

Do not treat corpus-reported traditional claims as clinical correctness. Do not use model outputs as gold truth.
