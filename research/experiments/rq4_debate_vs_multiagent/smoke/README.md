# RQ4 development smoke

The bounded real smoke uses the 10 distinct development-only questions in `development_questions.json`. Every question runs once under C2 and once under C4, for 20 primary condition executions. The set is rejected before execution if its normalized question text or evidence IDs overlap any repository benchmark JSONL.

Smoke artifacts are separate from formal outputs. A successful smoke stops at `SMOKE_TEST_PASSED`; the committed formal-code checkpoint is then validated with `scripts\rq4.cmd prepare` before the state can become `READY_FOR_FORMAL_RQ4_RUN`.
