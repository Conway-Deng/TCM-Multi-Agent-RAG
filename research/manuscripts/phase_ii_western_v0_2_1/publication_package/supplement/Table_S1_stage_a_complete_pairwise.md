# Table S1: Complete Stage-A Paired Retrieval Statistics

| Comparison | Paired n | Mean Recall Diff | 95% Bootstrap CI | R0 Hit / Comp Miss | R0 Miss / Comp Hit | Discordant Pairs | Exact McNemar p |
|---|---|---|---|---|---|---|---|
| R1 - R0 | 42 | 0.206349 | [0.083333, 0.333333] | 2 | 10 | 12 | 0.038574 |
| R2 - R0 | 42 | 0.095238 | [0.011905, 0.190476] | 0 | 6 | 6 | 0.031250 |
| R3 - R0 | 42 | 0.107143 | [0.011905, 0.218254] | 2 | 6 | 8 | 0.289062 |

**Note:** Western Formal Study v0.1.5. Headline retrieval paired comparisons across 42 answerable cases. Chunk recall differences evaluate micro-aggregated primary gold items. Confidence intervals are 95% percentile intervals from 10,000 paired case bootstrap resamples (seed 20260815). McNemar p-values evaluate paired Hit@4 discordance using an exact two-sided binomial test. No multiplicity adjustment was prespecified in Stage A.
