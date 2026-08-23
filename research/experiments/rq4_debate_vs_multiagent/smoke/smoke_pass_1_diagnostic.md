# RQ4 real smoke pass 1 diagnostic

- Status: `FAIL` (operational architecture gate)
- Primary executions: 20/20 completed; C2 usable 10/10; C4 usable 10/10
- Provider attempt failures/retries: 0/0
- Failed requirement: the reused backend returned legacy deterministic debate summaries and did not expose or execute genuine critique/revision/consensus provider stages.
- Root cause: port 8002 was already served by a backend process loaded before the genuine C4 implementation. The lifecycle check validated provider/corpus configuration but had no implementation fingerprint, so it incorrectly reused the stale process.
- Correction: `/health` now exposes workbench and genuine-C4 implementation SHA-256 values. The RQ4 launcher reuses a backend only when both match the current files; otherwise it leaves the unrelated process untouched and starts an isolated current backend on an available local port.
- Benchmark/protocol changes: none.
- Formal executions: 0.
- Pass 2 authorization: permitted because pass 1 demonstrated and pass 2 follows a genuine backend lifecycle/implementation-selection fix.
