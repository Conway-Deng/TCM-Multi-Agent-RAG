# RQ1 paired statistical analysis

Primary unit: question pair (45 complete usable pairs), not individual Gold facts. Bootstrap: 10,000 question-level resamples, seed 20260821.

## Semantic quality

| Metric | C1 mean | C2 mean | Mean C2-C1 | 95% bootstrap CI | Wilcoxon p |
|---|---:|---:|---:|---:|---:|
| full_recall | 88.15% | 90.74% | 2.59% | [-1.85%, 7.78%] | 0.3404 |
| partial_or_better | 94.81% | 97.04% | 2.22% | [0.00%, 5.19%] | 0.0588 |
| missing_rate | 4.44% | 2.22% | -2.22% | [-5.19%, 0.00%] | 0.0588 |
| contradiction_rate | 0.74% | 0.74% | 0.00% | [0.00%, 0.00%] | 0.0000 |

## Reliability

C1 usable: 47/50 (94%). C2 usable: 45/50 (90%). Paired table: both 45, C1-only 2, C2-only 0, neither 3. McNemar exact two-sided p is 0.5000 (two discordant pairs in one direction).

## Interpretation

C2 had higher observed semantic Gold-fact coverage on this first pass for full recall and partial-or-better recall, with lower missing rate. Contradiction rates were nearly identical. The paired confidence intervals and tests should be interpreted cautiously; this is not a claim of clinical or medical superiority. C2 had lower reliability and higher mean latency on all-run summaries, while paired usable latency is analyzed separately in the machine-readable artifacts.

Retrieval and citation paired statistics are in paired_objective_statistics.json. Limitations include one formal pass, 50 benchmark questions, 45 complete semantic pairs, R0 only, Qwen/Qwen3-8B only, and AI-assisted semantic evaluation without independent human or expert validation. Recommendation: resolve methodology and reliability considerations, then consider repeat formal passes; do not start automatically.
