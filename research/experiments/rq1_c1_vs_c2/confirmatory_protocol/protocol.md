# RQ1 confirmatory protocol

Status: PRE-REGISTERED — BENCHMARK SOURCE REVIEW REQUIRED.

Primary comparison: C1 Single-RAG versus C2 Multi-Agent under fixed Qwen/Qwen3-8B, Corpus v1, and R0 retrieval.

Primary metric: question-level Gold Fact Full Recall. Secondary metrics: Partial-or-Better Recall, Missing Gold Rate, Contradiction Rate, usable-answer reliability, and latency.

The primary estimand is the mean paired difference C2 − C1. The primary statistical unit is the question. The planned sample is 100 new questions, one confirmatory pass, and 200 generation runs (100 per condition) in deterministic interleaved order.

Analysis uses 10,000 paired question-level bootstrap resamples, seed `20260821`, a 95% confidence interval, and Wilcoxon signed-rank where informative. A five-percentage-point Full Recall difference is pre-registered as a clearly meaningful architecture-level improvement. This threshold must not change after results are observed. Statistical significance is not promised or required.

The system, model, corpus, retrieval, generation parameters, retry/timeout/fallback policies, grounding rules, and benchmark may not be tuned from formal outputs.

Checkpoints: `BENCHMARK_SOURCE_REVIEW_REQUIRED` before any provider run, then `SEMANTIC_REVIEW_REQUIRED` after formal execution and objective evaluation/export.
