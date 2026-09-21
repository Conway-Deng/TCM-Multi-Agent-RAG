# Western Semantic Follow-up v0.2 — FROZEN

## 1. Study identity and freeze timestamp

- Follow-up identity: **Western Semantic Follow-up v0.2**
- Freeze timestamp: `2026-09-21T03:05:00Z` (`2026-09-21T11:05:00+08:00`)
- Status: **FROZEN** (post-scientific-review archival freeze)

## 2. Parent dataset identity

- Parent Stage-B primary generation run ID: `western-formal-v0.1.2-stage-b-r1-20260919-01`
- Parent Stage-B generation dataset SHA256: `afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c`
- Parent Stage-A retrieval run ID: `western-formal-v0.1.2-stage-a-20260918-01`
- Parent Stage-A retrieval dataset SHA256: `91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e`
- Frozen benchmark: `western-pilot-v0.1` (`research/benchmarks/western_pilot_v0_1/benchmark.jsonl`, 48 cases, SHA256 `29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6`)
- Frozen Western corpus: `medirag-west-v0.1-pilot` (`research/corpus/west_v0_1/chunks.jsonl`, 271 chunks, SHA256 `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b`)

## 3. Evaluator, blinding, and methodology

- Evaluator: **GPT-5.6 Sol**
- Blinding: Retrieval-condition identity (R0, R1, R2, R3) and original experiment IDs were completely concealed from the evaluator during annotation.
- Evaluation basis: Evidence-grounded semantic evaluation judged solely against frozen expected evidence points, supplied top-4 retrieved evidence passages, and generated answers.
- Single-evaluator limitation: All semantic annotations were produced by a single AI evaluator applying the frozen rubric.
- No human/clinician adjudication: No human, physician, clinician, or independent expert participated in grading or adjudicating these answers.
- No inter-rater reliability: No second evaluator was deployed; inter-rater agreement is not estimated.
- No judge-family robustness analysis: Findings reflect this specific evaluator model and rubric, not generalized judge-family robustness.
- Evidence-grounded, not clinical validation: This evaluation measures evidence coverage and fidelity to supplied corpus excerpts; it does not establish clinical correctness, safety, or medical validity.

## 4. Populations and statistical specifications

- **W-RQ2 Population:** 42 answerable cases (38 supported, 4 partially supported), 168 cells. Zero missing semantic judgments.
- **W-RQ3 Population:** 6 insufficient-evidence cases, 24 cells. Evaluated separately; not pooled into W-RQ2; not treated as zero scores.
- **Primary endpoint:** Case-level macro mean of `full_coverage_score` (`n_fully_covered / n_expected_points`).
- **Bootstrap specification:** 10,000 case-level resamples with replacement, seed `20260815`, 95% percentile confidence intervals.
- **McNemar test:** Exact two-sided binomial test on paired discordant presence indicators for unsupported claims, with Holm family-wise error rate control across the 3 pre-specified R0 comparisons (family size = 3).
- **W-RQ3 handling:** Purely descriptive categorical distribution across 4 pre-registered categories; no hypothesis tests performed.
- **Composite score:** None created.
- **Missingness & imputation:** No missing semantic judgments exist; no zero imputation was applied; paired analyses use complete case intersections.

## 5. Relationship to historical Western Formal Study v0.1.5

- Western Formal Study v0.1.5 remains historically closed and unchanged.
- Its original automated Stage C remains prospectively terminated under its defined stopping rule.
- Western Semantic Follow-up v0.2 is a separate post-study evaluation.
- This follow-up does not reopen, modify, resume, or retroactively alter Western Formal Study v0.1.5.

## 6. Immutable artifact provenance hashes

### Tracked archival files

| Artifact | Relative path | SHA256 |
|---|---|---|
| Analysis script | `scripts/analyze-western-semantic-followup-v0_2.py` | `618f77474d064465612b4608152a4b332f520dea93e2f88624dc0013912945e9` |
| Pre-deblind plan | `research/experiments/western_semantic_followup_v0_2/analysis_plan_predeblind.json` | `c8f17b3e1e7ccad8152027fb8da46c1e9fc47da599ac3fed36966ee18a90bd08` |
| Export manifest | `research/experiments/western_semantic_followup_v0_2/stage_c2_export_manifest.json` | `3eaa05cf1bd7d0eda39a0599abaa26569662020b715753295df982d01eaef343` |
| Deblinded dataset | `research/experiments/western_semantic_followup_v0_2/stage_c2_deblinded_judgments.csv` | `6387aa644f36cb4df746d18f595de212a5ea7f6881e67b601031cb2f1a43757c` |
| Analysis manifest | `research/experiments/western_semantic_followup_v0_2/stage_c2_analysis_manifest.json` | `3b7d19979912253468d350368bd22ff1d50b76991587713e9121c357f16f5d8e` |
| Results document | `research/experiments/western_semantic_followup_v0_2/STAGE_C2_RESULTS_v0.2.md` | `1158675a0c75c047847282b2fae9388f96a51f0c3bce685691502ff3fdade633` |

### Tracked tables (12 files)

| Table file | Relative path | SHA256 |
|---|---|---|
| Primary coverage by condition | `tables/w_rq2_primary_coverage_by_condition.csv` | `d28f73e271a23bbe8b76bc123dd533477048b22874fcd24ca052c8d19e517dde` |
| Primary pairwise vs R0 | `tables/w_rq2_primary_pairwise_vs_r0.csv` | `dda72a59583e1f2183d48fee6487ea79a1933737cec764ae6ff4507554983b65` |
| Partial credit by condition | `tables/w_rq2_partial_credit_by_condition.csv` | `b048efdcac0f23857443cfcba3824b8c82be7fda4a31c95cad20d0c62a154b05` |
| Partial credit pairwise vs R0 | `tables/w_rq2_partial_credit_pairwise_vs_r0.csv` | `0247cf9053a905c92ef48fab94c073c94409d295a2a1d369b3694b4214325032` |
| Unsupported presence by condition | `tables/w_rq2_unsupported_presence_by_condition.csv` | `ae48ea2817d9fb3930ec1ce196ee61d2ad7bdf6c40e841d46f23abbd64035c03` |
| Unsupported McNemar vs R0 | `tables/w_rq2_unsupported_mcnemar_vs_r0.csv` | `c3c9648aae172b610361b2f51c915dab6bcb4261dfa76a4e45307d720d539ecc` |
| Unsupported count by condition | `tables/w_rq2_unsupported_count_by_condition.csv` | `2aedadc24e88d77ea205be47d33c6ef912cd7098cccd9fb4f2eaaf4f54658264` |
| Unsupported count pairwise vs R0 | `tables/w_rq2_unsupported_count_pairwise_vs_r0.csv` | `a50b531de2562aebb37b49fbc1f27843826583ea810497665b76b9ae98698abd` |
| Contradictions by condition | `tables/w_rq2_contradictions_by_condition.csv` | `9453368e7e5d85b3cc33fd1c022be2dbb0a9191a273694770794c8bc2afbe65a` |
| Expected point labels by condition | `tables/w_rq2_expected_point_labels_by_condition.csv` | `8dbef888655efe24607efcfb3cd3a7b92d3965a0c5e7dcf1a9f88b729a758113` |
| Insufficient label distribution | `tables/w_rq3_insufficient_label_distribution.csv` | `5df1d0de46903c65f6b0093d79e3723d93c6d803fa10239d69cc259761fa81d3` |
| W-RQ3 case by condition | `tables/w_rq3_case_by_condition.csv` | `7aec21773a3e6f9503f974dfe6d9e865712373f16c5e6beeccfa49e566084b10` |

### Local-only provenance (Not tracked in Git)

The following files contain raw source-derived passages or secret key mappings and remain strictly local-only:

- Populated judgment workbook (`stage_c2_gpt56sol_judgments.xlsx`): SHA256 `81b260b4ad424d6f52a36414e30fd8e7bd22068d8f3e02496a39d7320593fc80`
- Secret blind key (`stage_c2_blind_key.csv`): SHA256 `6a7a287754ba14651a1b6fe61a4e0a49d2815fe96e013e564cf6b75a44f1f4e5`
- Blank blinded template workbook (`stage_c2_blinded_eval_input.xlsx`): SHA256 `106831e93633c572a864c849e562bff4a2d3e7b19f0c407230114c6f32642923`
