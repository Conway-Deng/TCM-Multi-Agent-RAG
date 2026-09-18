# Frozen Failure and Retry Policy

Each formal cell receives one initial attempt and at most one retry event. Cell-level `attempt_count=1` means no retry event; `attempt_count=2` means the single retry event was used.

Retry once only for:

- network/connectivity transport failure;
- HTTP 5xx;
- provider timeout;
- malformed transport-level response.

R0 is local and is never converted into a technical-missing quality result: an unexpected exception is a fatal runner defect. R1 and R2 retry only the dense operation. R3 treats dense and reranker as distinct operations; it retries only the failed operation and never repeats a successful dense provider operation because reranking failed. Once the cell retry budget is consumed, any later retryable provider failure terminates the cell as `technical_failure`.

Every cell ends as `success` or `technical_failure`. A technical failure preserves metadata, retry state, provider-operation trace, errors, and timestamps but fabricates no ranking or score. Fatal schema, checkpoint, input-integrity, local-R0, condition-mapping, or protocol-path defects stop the run unsealed.

Stage A seals only after 192 unique terminal `(case_id, retrieval_condition)` records exist. Missing, duplicate, in-progress, or corrupt cells prevent sealing. Before sealing, ordinary interruption resumes only absent cells; sealed cells cannot be rerun or overwritten.

Never retry because of weak answer quality, unsupported content, insufficient evidence, poor citation behavior, model disagreement, output-quality rejection, or judge content/schema failure. A valid generated answer is never rerun.

Every generation cell records `first_attempt_success`, `attempt_count`, `technical_retry_used`, `first_error_type`, and `final_generation_success`. Provider reliability reports both first-attempt success and final completion.

If both permitted attempts fail, retain the immutable retrieval result, set generation outcome to technical failure, leave the answer empty, exclude the cell from semantic answer-quality denominators, and report missingness. Do not fabricate an answer.

Judge schema/content failures are not used to tune prompts against benchmark cases and are not silently retried as quality failures.

Interrupted runs resume by detecting the unique `experiment_id` derived from `(case_id, retrieval_condition)`. Resume never duplicates completed cells and never bypasses this retry policy.

## Downstream propagation

A Stage A technical failure is propagated as upstream technical missingness. Stage B and C retain the cell identity but make zero generator/judge calls, record zero provider attempts and latency, and emit no answer, provenance, or semantic labels. This is not abstention, evidence insufficiency, a content failure, or a generator/judge failure.
