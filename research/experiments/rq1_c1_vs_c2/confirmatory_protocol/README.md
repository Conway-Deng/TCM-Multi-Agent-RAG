# RQ1 confirmatory study automation

Current status: benchmark and protocol frozen before provider execution. The immutable execution manifest is prepared for 200 interleaved C1/C2 runs. The automated pipeline must stop at `SEMANTIC_REVIEW_REQUIRED` after objective evaluation and packet export; it must not fabricate semantic labels or a final semantic conclusion.

Preflight:

    .\scripts\run-rq1-confirmatory.ps1 -PreflightOnly

Dry-run and resume simulation:

    .\scripts\run-rq1-confirmatory.ps1 -DryRun
    .\scripts\run-rq1-confirmatory.ps1 -SimulateResume

Future approved run:

    .\scripts\run-rq1-confirmatory.ps1 -Stage run

The runner persists execution order and manifest, appends and fsyncs every completed record, and skips every completed question/condition pair on resume.
