# RQ4 development smoke

The bounded real smoke uses the 10 distinct development-only questions in `development_questions.json`. Every question runs once under C2 and once under C4, for 20 primary condition executions. The set is rejected before execution if its normalized question text or evidence IDs overlap any repository benchmark JSONL.

Smoke artifacts are separate from formal outputs. A successful smoke stops at `SMOKE_TEST_PASSED`; the committed formal-code checkpoint is then validated with `scripts\rq4.cmd prepare` before the state can become `READY_FOR_FORMAL_RQ4_RUN`.

The permitted second and final pass completed on 2026-08-23 with `SMOKE_TEST_FAILED`. C2 was usable for 10/10 questions. C4 completed 2/10 full genuine sequences; 8/10 failed at required critique stages. Across the pass, 17 provider attempts failed (13 malformed structured responses and 4 timeouts), and 9 retries were performed within the fixed one-retry bound. See `smoke_validation.json`, `smoke_provider_attempts.jsonl`, and `smoke_pass_2_diagnostic.md`.
