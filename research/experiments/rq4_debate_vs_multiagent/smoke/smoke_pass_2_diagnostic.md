# RQ4 real smoke pass 2 diagnostic

- Final state: `SMOKE_TEST_FAILED`
- Development questions: 10 distinct questions, each executed once under C2 and once under C4
- C2 usable: 10/10
- C4 full genuine sequences: 2/10 (one `PASS`, one `PASS_WITH_RETRY`)
- C4 required-stage failures: 8/10
- Provider attempts: 45 total, 28 succeeded, 17 failed
- Failed attempts: 13 `malformed_response`, 4 `timeout`
- Retries performed: 9; no stage exceeded two total attempts
- Seven C4 executions stopped at `critique:grounding_critic`; the multi-specialist execution stopped at `critique:herbal`
- The malformed responses were either invalid/truncated JSON or structured critique fields returned as objects where the frozen schema requires strings
- Provider timeouts were recorded at the configured backend timeout; no HTTP status was available for local parse/timeout failures
- No successful C4 execution silently fell back to C2
- Formal RQ4 results: 0

Pass 1 exposed stale-backend reuse and was preserved separately. The implementation-fingerprint fix caused pass 2 to exercise the current genuine C4 path. Because pass 2 still failed the operational threshold and two complete passes are the maximum, no further smoke or formal execution was started.
