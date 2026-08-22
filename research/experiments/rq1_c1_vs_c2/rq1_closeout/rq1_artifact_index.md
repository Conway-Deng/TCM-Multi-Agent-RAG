# RQ1 artifact index

| Area | Purpose | Repository-relative path | Important files |
|---|---|---|---|
| Frozen benchmark | Gold questions and evidence mappings | `research/benchmarks/tcm_gold_v1_2/` | `benchmark_v1_2.jsonl`, `freeze_manifest_v1_2.json` |
| Corpus | Frozen Corpus v1 data | `research/corpus/tcm_v1/` | `chunks.jsonl` |
| Repeat 1 raw | First immutable 100-run pass | `research/experiments/rq1_c1_vs_c2/formal_pass_1_retry_20260821/` | `results.jsonl`, `manifest.json`, `summary.json` |
| Repeat 2 raw | Second immutable 100-run pass | `research/experiments/rq1_c1_vs_c2/formal_repeat_2_20260822/` | `results.jsonl`, `manifest.json`, `summary.json` |
| Repeat 3 raw | Third immutable 100-run pass | `research/experiments/rq1_c1_vs_c2/formal_repeat_3_20260823/` | `results.jsonl`, `manifest.json`, `summary.json` |
| Repeat 1 semantic | AI-assisted semantic evaluation | `research/experiments/rq1_c1_vs_c2/formal_pass_1_retry_20260821/semantic_validation/` | `ai_semantic_review_all_204.json` |
| Repeat 2/3 semantic | Imported external GPT reviews | `research/experiments/rq1_c1_vs_c2/semantic_evaluation/` | `repeat_2_semantic_scores.json`, `repeat_3_semantic_scores.json` |
| Final statistics | Three-repeat repeated-measures analysis | `research/experiments/rq1_c1_vs_c2/evaluation/final_three_repeat_analysis/` | `three_repeat_statistics.json`, `rq1_final_summary.md` |
| Reliability | Three-repeat execution reliability | same final statistics directory | `reliability_three_repeat.json` |
| Latency | Three-repeat latency summaries | same final statistics directory | `latency_three_repeat.json` |
| Progress note | Research log | external `D:\project\AI-Second-Brain\30-Research-MediRAG\2026-08-21 TCM Research Progress.md` | dated RQ1 entries |

## Confirmatory extension (Study 1B)

| Area | Purpose | Repository-relative path | Important files |
|---|---|---|---|
| Frozen confirmatory benchmark | 100 new held-out questions | `research/benchmarks/tcm_gold_rq1_confirmatory_v1/` | `benchmark_confirmatory_v1_1_frozen.jsonl`, `freeze_manifest_confirmatory_v1_1.json` |
| Confirmatory raw run | 200 locked C1/C2 executions | `research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1/` | `results.jsonl`, `formal_execution_manifest.json`, `summary.json` |
| Confirmatory semantic analysis | Imported 422-row external review and paired analysis | `research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1/final_analysis/` | `confirmatory_final_results.md`, `confirmatory_paired_statistics.json`, `confirmatory_analysis_manifest.json` |
| Final combined closeout | Study 1A/1B synthesis without naive pooling | `research/experiments/rq1_c1_vs_c2/rq1_closeout/` | `rq1_final_results_with_confirmatory.md`, `rq1_final_manifest_with_confirmatory.json`, `rq1_final_conclusion.md` |

Relevant revisions: frozen runner `635c5db`; objective evaluation `9c73bb6`; semantic protocol `631ffbe`; formal pass 1 analysis `e56f209`; repeat packet preparation `f2ee29e`; final three-repeat analysis `2da82df`.
