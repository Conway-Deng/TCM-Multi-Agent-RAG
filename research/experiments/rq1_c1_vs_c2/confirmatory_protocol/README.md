# RQ1 confirmatory study automation

Current checkpoint: `BENCHMARK_SOURCE_REVIEW_REQUIRED`. No formal run is authorized until the external source review is imported, adjudicated, and the benchmark/config hashes are frozen.

Preflight:

    .\scripts\run-rq1-confirmatory.ps1 -PreflightOnly

Dry-run and resume simulation:

    .\scripts\run-rq1-confirmatory.ps1 -DryRun
    .\scripts\run-rq1-confirmatory.ps1 -SimulateResume

Future approved run:

    .\scripts\run-rq1-confirmatory.ps1 -Stage run

The runner persists execution order and manifest, appends and fsyncs every completed record, and skips every completed question/condition pair on resume.
