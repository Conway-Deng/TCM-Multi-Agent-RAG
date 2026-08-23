# How to run RQ4 locally

## Current state

`BENCHMARK_SOURCE_REVIEW_REQUIRED`

## What it means

The platform is ready, but the RQ4 v1.2 source-grounded benchmark is a draft. Formal execution is blocked until every Question ↔ Gold ↔ source row in `external_source_review_v1_2_for_gpt.csv` is externally reviewed and approved.

## What command to run

For safe status only:

```bat
scripts\rq4.cmd
```

After an approved review is returned, import it with `scripts\rq4.cmd import-benchmark <completed_csv>`. Then run the real development check with `scripts\rq4.cmd smoke`. Only after it passes, start the several-hour formal run with:

```bat
scripts\rq4.cmd formal
```

Do not close that terminal during the formal run. Closing a separate dashboard browser is safe.

## Check progress

In another terminal run `scripts\rq4.cmd dashboard`, then open the printed local URL (normally `http://127.0.0.1:5600`). The dashboard is read-only. `scripts\rq4.cmd status` is also safe.

## If stalled

Check status. The runner uses hard timeouts and persists each completed execution. If it reports `FORMAL_STALLED`, use `scripts\rq4.cmd resume`; completed execution IDs are validated and skipped.

## Review CSV

After all 200 executions, the runner stops at `SEMANTIC_REVIEW_REQUIRED` and prints the path to `formal_run_v1\rq4_semantic_review_for_gpt.csv`. Import the completed packet with `scripts\rq4.cmd finalize <completed_csv>`.
