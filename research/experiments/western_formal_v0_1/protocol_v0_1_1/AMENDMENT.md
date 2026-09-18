# Protocol Safety Amendment v0.1.1

`western_formal_v0.1.1` supersedes `western-formal-v0.1` before formal execution.

- `superseded_before_formal_execution = true`
- `formal_cells_executed_under_v0_1 = 0`
- Reason: pre-execution runner safety / stage-finalization defects

These defects were found before formal Stage A execution. No formal result existed or was inspected, and no algorithm was changed in response to performance. The benchmark, gold evidence, corpus, retrieval definitions and parameters, prompts, generator, judge, metrics, balanced order, and statistical comparison families are unchanged.

## Defect 1 — formal retrieval retry records

The frozen Stage A path called `RetrievalEngine.search()` directly and therefore did not apply the frozen technical-retry policy or record `attempt_count`, `technical_retry_used`, `first_error_type`, and final retrieval success.

v0.1.1 adds a formal-only wrapper around the unchanged retrieval operations. It enforces one cell-level retry event, separates dense and reranker traces, and writes the full terminal retry state for every cell.

## Defect 2 — terminal-cell sealing

Stage A sealing required 192 successful retrieval records rather than 192 terminal formal cell records, conflicting with the frozen technical-missingness policy.

v0.1.1 requires exactly 192 unique terminal cells, each in `success` or `technical_failure`. A fatal runner defect, missing cell, duplicate, in-progress record, input mismatch, or corrupt checkpoint prevents sealing.

## Defect 3 — Stage-A-only finalization

Stage A could not independently produce and freeze Stage-A-only metrics, provider metrics, manifests, and result artifacts because `finalize_run` required Stages A, B, and C to be sealed.

v0.1.1 adds `finalize_stage_a_run`, which requires only a valid sealed Stage A and emits immutable Stage-A-only raw results, retrieval metrics, provider metrics, pairwise statistics, run manifest, and freeze record. It emits no fabricated Stage B or C artifact.

## Defect 4 — complete run identity

The run manifest did not record the complete required checkpoint commits and frozen hash set.

v0.1.1 records the execution/protocol checkpoint HEAD, runtime and benchmark checkpoints, original v0.1 commit, protocol/benchmark/manifest/corpus/registry hashes, and the supersession fact. Stage A refuses to start if verification fails.
