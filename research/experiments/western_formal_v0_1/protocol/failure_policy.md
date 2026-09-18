# Frozen Failure and Retry Policy

Each provider operation receives one initial attempt and at most one retry.

Retry once only for:

- network/connectivity transport failure;
- HTTP 5xx;
- provider timeout;
- malformed transport-level response.

Never retry because of weak answer quality, unsupported content, insufficient evidence, poor citation behavior, model disagreement, output-quality rejection, or judge content/schema failure. A valid generated answer is never rerun.

Every generation cell records `first_attempt_success`, `attempt_count`, `technical_retry_used`, `first_error_type`, and `final_generation_success`. Provider reliability reports both first-attempt success and final completion.

If both permitted attempts fail, retain the immutable retrieval result, set generation outcome to technical failure, leave the answer empty, exclude the cell from semantic answer-quality denominators, and report missingness. Do not fabricate an answer.

Judge schema/content failures are not used to tune prompts against benchmark cases and are not silently retried as quality failures.

Interrupted runs resume by detecting the unique `experiment_id` derived from `(case_id, retrieval_condition)`. Resume never duplicates completed cells and never bypasses this retry policy.
