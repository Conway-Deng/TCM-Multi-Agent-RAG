# RQ1 confirmatory formal run v1.1

Status: `RQ1_CONFIRMATORY_COMPLETE` — all 200 locked provider runs completed and the final external semantic review was imported.

`formal_execution_manifest.json` and `execution_order.json` were locked before provider execution. Run IDs, order, benchmark/corpus hashes, model, retrieval, generation settings, retry/timeout/fallback policies, and grounding policy are immutable. Completed records are appended immediately to `results.jsonl`; resume skips validated completed question/condition pairs.

The completed run contains 100 C1 and 100 C2 records. The externally returned 422-row semantic review was imported without altering answers, Gold, evidence, or labels; final paired analysis is under `final_analysis/`. The terminal pipeline state is `RQ1_CONFIRMATORY_COMPLETE`. Re-running the launcher returns that state and does not start new provider work.
