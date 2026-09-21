# Western Semantic Follow-up v0.2 — Blinded GPT-5.6 Sol Evaluation

## Study identity

This is a new Western Semantic Follow-up v0.2. It is not a reopening of the closed Western Formal Study v0.1.5 and does not constitute Wave 3. It reuses the frozen benchmark, Stage-A retrieval outputs, and primary Stage-B generated answers. A single GPT-5.6 Sol evaluator supplied evidence-grounded semantic annotations using only the frozen expected evidence points, supplied passages, and generated answer. Retrieval-condition identity was concealed from the evaluator.

## Analysis populations

W-RQ2 contains 42 answerable cases (supported or partially_supported), 168 cells, and no missing semantic judgments. W-RQ3 contains 6 insufficient-evidence cases and 24 cells. Insufficient cases are excluded from W-RQ2 and are not treated as zeros.

## W-RQ2 primary endpoint

The primary endpoint is the case-level macro mean of full_coverage_score. No micro-total across evidence points was used.

| Condition | n | Mean | SD | Median | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| R0 | 42 | 0.543651 | 0.453919 | 0.500000 | 0 | 1 |
| R1 | 42 | 0.805556 | 0.335191 | 1.000000 | 0 | 1 |
| R2 | 42 | 0.626984 | 0.430556 | 1.000000 | 0 | 1 |
| R3 | 42 | 0.710317 | 0.387927 | 1.000000 | 0 | 1 |

Paired comparisons use case_id, with 42 paired cases for each comparison and 10,000 case-resamples (seed 20260815). The observed paired mean difference and percentile interval are descriptive:

| Comparison | n | Mean difference | Median difference | 95% bootstrap CI |
|---|---:|---:|---:|---:|
| R1 - R0 | 42 | 0.261905 | 0.000000 | [0.142857, 0.392857] |
| R2 - R0 | 42 | 0.083333 | 0.000000 | [0.000000, 0.178571] |
| R3 - R0 | 42 | 0.166667 | 0.000000 | [0.059524, 0.285714] |

## W-RQ2 secondary findings

Partial-credit coverage, unsupported-claim measures, contradictions, and expected-point labels are descriptive secondary analyses; no composite score was created.

Partial-credit coverage:

| Condition | n | Mean | SD | Median | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| R0 | 42 | 0.686508 | 0.338281 | 0.750000 | 0 | 1 |
| R1 | 42 | 0.863095 | 0.229012 | 1.000000 | 0.250000 | 1 |
| R2 | 42 | 0.738095 | 0.321735 | 1.000000 | 0 | 1 |
| R3 | 42 | 0.785714 | 0.300261 | 1.000000 | 0 | 1 |

Paired partial-credit differences versus R0:

| Comparison | n | Mean difference | Median difference | 95% bootstrap CI |
|---|---:|---:|---:|---:|
| R1 - R0 | 42 | 0.176587 | 0.000000 | [0.087302, 0.277778] |
| R2 - R0 | 42 | 0.051587 | 0.000000 | [-0.015873, 0.123016] |
| R3 - R0 | 42 | 0.099206 | 0.000000 | [0.021825, 0.188492] |

Unsupported-claim presence rates:

| Condition | TRUE | FALSE | Rate | n |
|---|---:|---:|---:|---:|
| R0 | 9 | 33 | 0.214286 | 42 |
| R1 | 5 | 37 | 0.119048 | 42 |
| R2 | 3 | 39 | 0.071429 | 42 |
| R3 | 3 | 39 | 0.071429 | 42 |

Exact two-sided McNemar p-values and Holm adjustment across the three pre-specified comparisons:

| Comparison | R0 FALSE/comparison TRUE | R0 TRUE/comparison FALSE | Discordant | Raw p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| R1 vs R0 | 3 | 7 | 10 | 0.343750 | 0.343750 |
| R2 vs R0 | 0 | 6 | 6 | 0.031250 | 0.093750 |
| R3 vs R0 | 1 | 7 | 8 | 0.070312 | 0.140625 |

Unsupported-claim count summaries:

| Condition | Mean | SD | Median | Min | Max |
|---|---:|---:|---:|---:|---:|
| R0 | 0.261905 | 0.543679 | 0.000000 | 0 | 2 |
| R1 | 0.119048 | 0.327770 | 0.000000 | 0 | 1 |
| R2 | 0.095238 | 0.370203 | 0.000000 | 0 | 2 |
| R3 | 0.095238 | 0.370203 | 0.000000 | 0 | 2 |

Paired unsupported-claim count differences versus R0:

| Comparison | Mean difference | 95% bootstrap CI |
|---|---:|---:|
| R1 - R0 | -0.142857 | [-0.309524, 0.023810] |
| R2 - R0 | -0.166667 | [-0.285714, -0.071429] |
| R3 - R0 | -0.166667 | [-0.333333, 0.000000] |

Contradiction summaries:

| Condition | TRUE | FALSE | Rate | Total n_contradicted |
|---|---:|---:|---:|---:|
| R0 | 5 | 37 | 0.119048 | 3 |
| R1 | 1 | 41 | 0.023810 | 1 |
| R2 | 2 | 40 | 0.047619 | 1 |
| R3 | 1 | 41 | 0.023810 | 0 |

Expected-point label totals:

| Condition | Covered | Partially covered | Not covered | Contradicted | Total points |
|---|---:|---:|---:|---:|---:|
| R0 | 31 | 16 | 8 | 3 | 58 |
| R1 | 44 | 7 | 6 | 1 | 58 |
| R2 | 35 | 13 | 9 | 1 | 58 |
| R3 | 38 | 10 | 10 | 0 | 58 |

These secondary quantities were not used to create a new inferential endpoint; expected points remain nested within cases.

## W-RQ3 insufficient-evidence handling

The four frozen labels are reported by condition with n=6 per condition; no hypothesis test or composite endpoint was used.

| Condition | n | Appropriate abstention | Bounded insufficiency | Substantive answer without acknowledgement | Overclaim beyond pilot evidence |
|---|---:|---:|---:|---:|---:|
| R0 | 6 | 1 | 5 | 0 | 0 |
| R1 | 6 | 0 | 5 | 0 | 1 |
| R2 | 6 | 0 | 5 | 0 | 1 |
| R3 | 6 | 0 | 5 | 0 | 1 |

The case-by-condition labels are in `tables/w_rq3_case_by_condition.csv`.

## Interpretation boundaries

This follow-up estimates evidence-grounded semantic behavior under a single GPT-5.6 Sol evaluator. It does not establish clinical correctness, clinical safety, diagnostic validity, physician agreement, human-expert agreement, or a general advantage of any medical system over another. The evaluator is not a human or clinician. These annotations do not constitute clinical validation.

## Evaluator and blinding limitations

One evaluator, GPT-5.6 Sol, applied the frozen rubric. There was no human or clinician adjudicator, no inter-rater reliability estimate, and no judge-family robustness estimate. The semantic labels therefore depend on this evaluator's application of the frozen rubric.

Retrieval-condition identity was concealed from the evaluator, but the answer and supplied evidence could indirectly reveal differences in retrieval quality or content. Condition-label concealment does not establish that the evaluator could not infer such differences.

## Relationship to Stage A

Stage A measured retrieval performance. This follow-up measures evidence-grounded semantic behavior under one evaluator. Any descriptive alignment between those results does not establish that retrieval performance caused differences in generated-answer quality.

## Relationship to Western Formal Study v0.1.5

Western Formal Study v0.1.5 remains historically unchanged. Its original automated Stage C remains prospectively terminated, and W-RQ2/W-RQ3 semantic estimates remain unavailable within that study version. Western Semantic Follow-up v0.2 separately provides new post-study semantic estimates for the same frozen Stage-B answer set and does not rewrite the historical study status.

## Scientific conclusion

Within this frozen 16-review, 48-case pilot and under a single blinded GPT-5.6 Sol evidence-grounded evaluator, semantic evidence coverage and unsupported-claim behavior differed descriptively across retrieval conditions.

## Reproducibility

The exact input hashes, frozen pre-deblind plan hash, deblinded dataset hash, table hashes, and script hash are recorded in `stage_c2_analysis_manifest.json`. The analysis is offline and uses no provider, model, or network call. The populated judgment workbook was supplied outside the repository and verified by its required SHA256; the repository retains the separate blank blinded template.
