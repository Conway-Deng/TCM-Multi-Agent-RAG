# Phase II Western Manuscript v0.2.1 — Figure and Table Plan

## 1. Purpose and design decision

This document specifies a compact publication package for the frozen **Phase II Western Manuscript v0.2.1**. It is a presentation plan only: it creates no new analysis, changes no frozen result, and does not reopen Western Formal Study v0.1.5 or Western Semantic Follow-up v0.2.

The recommended main-text package contains **three figures and three tables**:

- Figure 1: study architecture and experimental sequence;
- Figure 2: Stage-A paired primary-gold chunk-recall differences versus R0;
- Figure 3: follow-up paired full-coverage differences versus R0;
- Table 1: Stage-A headline retrieval metrics;
- Table 2: follow-up semantic coverage by condition;
- Table 3: unsupported-claim and contradiction behavior.

The supplement contains **three multi-panel tables and no additional figures**. This is sufficient to show detailed paired statistics, secondary W-RQ2 outcomes, and the small descriptive W-RQ3 distribution without crowding the main manuscript or turning small denominators into visually prominent comparisons.

The package deliberately uses tables for exact condition-level values and forest-style plots for prespecified paired differences. It does not repeat condition means in a second bar chart, create a composite score, or use visual emphasis to identify a winner.

## 2. Recommended main figures

### Figure 1 — Study architecture and frozen-data reuse

| Element | Specification |
|---|---|
| Placement | Main manuscript |
| Scientific purpose | Explain the two-component study architecture, the formal execution sequence, and the separate post-study reuse of frozen Stage-B outputs. This figure resolves a distinction that is cumbersome to communicate repeatedly in prose. |
| Authoritative sources | `research/manuscripts/phase_ii_western_v0_2_1/MANUSCRIPT_FROZEN.md`; `research/manuscripts/phase_ii_western_v0_2_1/PHASE_II_MANUSCRIPT_v0.2.1.md`; `research/experiments/western_semantic_followup_v0_2/FROZEN.md`; `research/experiments/western_semantic_followup_v0_2/stage_c2_analysis_manifest.json` |
| Data fields/content | Corpus: 16 reviews, 271 chunks, four topic domains. Benchmark: 48 cases. Stage A: four conditions × 48 cases = 192 retrieval cells, completed. Stage B: fixed `Qwen/Qwen3-8B`, 192 primary generation cells, completed. Historical automated Stage C: prospectively terminated without a Primary Judge. Follow-up: 192 unchanged Stage-B answers reused; W-RQ2 = 42 cases × 4 = 168 cells; W-RQ3 = 6 cases × 4 = 24 cells. |
| Preferred structure | Two clearly titled containers. The left/top container is **Western Formal Study v0.1.5** and contains Corpus → Benchmark → Stage A → Stage B, with a separate terminal node for “Automated Stage C terminated.” The right/bottom container is **Separate post-study Western Semantic Follow-up v0.2**. A branch must leave the frozen Stage-B output and enter the follow-up, labeled “unchanged frozen Stage-B answers reused.” No arrow may run from the terminated Stage-C node into the follow-up. |
| Caption content | State both study identities; identify completion of Stage A and Stage B; state that automated Stage C terminated; state that the follow-up was a separate post-study evaluation reusing unchanged frozen answers; give W-RQ2 and W-RQ3 cell counts. |
| Must not be inferred | The follow-up resumed or completed historical Stage C; Stage-B completion demonstrates answer quality; the follow-up is Wave 3; the two components were one uninterrupted experiment. |
| Manuscript insertion point | End of Section 3 (“System and study design”), before the detailed corpus and benchmark sections. First textual reference should be in the final paragraph of Section 3. |

**Visual encoding:** Use solid borders for the formal-study container and a distinct double-line or dashed border for the follow-up container. The terminal Stage-C node should use a neutral stop-cap shape or horizontal terminal line, not red. The reuse branch should be visibly independent of the Stage-C terminal path. Labels, border styles, and topology—not color—must carry the distinction.

### Figure 2 — Stage-A paired primary-gold chunk-recall differences

| Element | Specification |
|---|---|
| Placement | Main manuscript |
| Scientific purpose | Show the prespecified within-case recall comparisons against R0, including uncertainty, more directly than a grouped bar chart can. |
| Authoritative source | `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/tables/stage_a_pairwise_vs_r0.csv` |
| Data fields | `comparison`, `n_paired_cases`, `mean_chunk_recall_difference`, `bootstrap_ci_lower_95`, `bootstrap_ci_upper_95`. Values: R1−R0 0.206349 [0.083333, 0.333333]; R2−R0 0.0952381 [0.0119048, 0.190476]; R3−R0 0.107143 [0.0119048, 0.218254]. |
| Preferred structure | Horizontal forest-style plot with one row per comparison, a point estimate, capped 95% bootstrap interval, and a vertical zero reference line. Order rows R1−R0, R2−R0, R3−R0. Print the estimate and interval as right-side text. Do not encode exact McNemar p-values in the plot. |
| Caption content | Define the effect as comparison minus R0; identify primary-gold chunk recall; state `n = 42` paired cases for each comparison; state 10,000 paired case bootstrap resamples, seed `20260815`, percentile 95% intervals; state that intervals are descriptive. |
| Must not be inferred | Binary statistical significance, general superiority, causal improvement in generated answers, or a ranking outside the frozen pilot. |
| Manuscript insertion point | Section 11.2, immediately after Table 1 and the paired-comparison paragraph. |

The existing `stage_a_paired_recall_difference` figure has the correct scientific geometry and is a suitable structural reference, but it should be mechanically regenerated in the final package style rather than copied. Regeneration should harmonize type size, neutral palette, line weights, decimal formatting, and dimensions with Figure 3.

### Figure 3 — Follow-up paired full-coverage differences

| Element | Specification |
|---|---|
| Placement | Main manuscript |
| Scientific purpose | Present the primary semantic endpoint through its prespecified paired comparisons while keeping the separate follow-up identity visible. |
| Authoritative source | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_primary_pairwise_vs_r0.csv` |
| Data fields | `comparison`, `n`, `mean_difference`, `bootstrap_ci_95_low`, `bootstrap_ci_95_high`, `bootstrap_seed`, `bootstrap_resamples`. Values: R1−R0 0.261905 [0.142857, 0.392857]; R2−R0 0.083333 [0.000000, 0.178571]; R3−R0 0.166667 [0.059524, 0.285714]. |
| Preferred structure | Horizontal forest-style plot parallel to Figure 2, with point estimates, capped 95% bootstrap intervals, and a vertical zero reference line. The title or subtitle must say “Separate Western Semantic Follow-up v0.2” and “full-coverage score.” |
| Caption content | Identify `full_coverage_score` as the primary endpoint; define comparison minus R0; state `n = 42` paired answerable cases, 10,000 case bootstrap resamples, seed `20260815`, and percentile intervals; identify the single blinded GPT-5.6 Sol evidence-grounded evaluator; state that the result is descriptive and pilot-specific. |
| Must not be inferred | Clinical correctness, clinical safety, causal transfer from retrieval to generation, general condition superiority, human agreement, or judge-family robustness. |
| Manuscript insertion point | Section 11.6, after Table 2 and the primary paired-comparison paragraph. |

Condition means should not be plotted again. Table 2 supplies their exact values, while Figure 3 supplies the paired comparison and interval geometry. This division avoids two graphics telling the same story.

## 3. Recommended main tables

### Table 1 — Frozen Stage-A headline retrieval metrics

| Element | Specification |
|---|---|
| Placement | Main manuscript; retain the existing Table 1 role |
| Scientific purpose | Provide exact values for the four complementary retrieval metrics without implying that they form a composite score. |
| Authoritative source | `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/tables/stage_a_headline_metrics.csv` |
| Data fields | `condition`, `n_cases`, `primary_gold_chunk_recall_at_4`, `primary_source_recall_at_4`, `hit_at_4`, `mrr` |
| Preferred structure | Four condition rows and columns for `n`, aggregate primary-gold chunk recall@4, aggregate primary-source recall@4, Hit@4, and MRR. Use six decimals consistently. Do not bold, shade, rank, or annotate a maximum. Definitions remain in Methods and the table note. |
| Caption content | State frozen Stage A; 42 supported or partially supported cases with non-empty primary gold; all metrics evaluated at top 4; aggregate recalls are micro-aggregates. |
| Must not be inferred | Overall condition ranking, clinical preference, semantic answer quality, or clean latency comparison. |
| Manuscript insertion point | Existing location in Section 11.2. |

The existing grouped Stage-A bar chart should not accompany this table in the main text. The exact table is more legible, does not require four color encodings, and avoids visually treating distinct metrics as one ranked score.

### Table 2 — Follow-up semantic coverage by retrieval condition

| Element | Specification |
|---|---|
| Placement | Main manuscript; refine the existing Table 2 role |
| Scientific purpose | Report exact condition-level coverage summaries while Figure 3 carries the paired primary comparison. |
| Authoritative sources | `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_primary_coverage_by_condition.csv`; `research/experiments/western_semantic_followup_v0_2/tables/w_rq2_partial_credit_by_condition.csv` |
| Data fields | For each condition: `n`, primary `mean` and `sd` from the full-coverage file; secondary `mean` and `sd` from the partial-credit file. Median/min/max may be moved to Supplementary Table S2 if space is constrained. |
| Preferred structure | Four condition rows. Columns: `n`, mean full-coverage score (primary), SD, mean partial-credit coverage (secondary), SD. Use six decimals in the data-production file and a consistent journal display precision of three decimals in the typeset table, with full precision retained in source data. Separate the primary and secondary headers visually. |
| Caption content | State separate Western Semantic Follow-up v0.2; 42 answerable cases per condition; single GPT-5.6 Sol evidence-grounded evaluator; full coverage is the primary endpoint and partial credit is secondary; case-level macro means. |
| Must not be inferred | Partial credit is a co-primary endpoint, condition means are unpaired estimates, or the table establishes clinical accuracy, safety, or general superiority. |
| Manuscript insertion point | Section 11.6, before Figure 3. |

### Table 3 — Unsupported-claim presence and contradiction behavior

| Element | Specification |
|---|---|
| Placement | Main manuscript |
| Scientific purpose | Communicate the main secondary evidence-grounded behavior outcomes exactly without converting them into a composite or visually amplified score. |
| Authoritative sources | `tables/w_rq2_unsupported_presence_by_condition.csv`; `tables/w_rq2_unsupported_mcnemar_vs_r0.csv`; `tables/w_rq2_contradictions_by_condition.csv` under `research/experiments/western_semantic_followup_v0_2/` |
| Data fields | Panel A: `retrieval_condition`, unsupported `true_count`, unsupported `rate`, contradiction `true_count`, contradiction `rate`, `n`, and `total_n_contradicted`. Panel B: `comparison`, paired discordances, `exact_two_sided_mcnemar_p_raw`, `holm_adjusted_p`, and `holm_family_size`. |
| Preferred structure | Two compact panels. Panel A has one row per condition and displays `n/N (rate)` for unsupported-claim presence and contradiction presence plus contradicted expected-point total. Panel B has one row per R1/R2/R3 comparison versus R0 and reports raw and Holm-adjusted exact McNemar p-values. Use neutral alignment and no conditional formatting. |
| Caption content | State 42 answerable cases per condition; outcomes are frozen rubric-defined secondary measures; McNemar tests are exact and two-sided; Holm family size is three; p-values are presented without a binary verdict. |
| Must not be inferred | Validated hallucination reduction, improved factuality generally, clinical safety, multiplicity-adjusted condition ranking, or a combined quality score. |
| Manuscript insertion point | Section 11.7, replacing repetition of all table values in prose while retaining the bounded interpretation paragraph. |

## 4. Recommended supplementary material

No supplementary figure is necessary. The detailed information is tabular and would not benefit from additional charts.

### Supplementary Table S1 — Complete Stage-A paired statistics

- **Purpose:** Preserve exact paired effect estimates, intervals, paired sample sizes, technical-missing counts, Hit@4 discordances, and exact McNemar p-values.
- **Source:** `stage_a_pairwise_vs_r0.csv`.
- **Fields:** All columns in the frozen CSV.
- **Structure:** One row per comparison; no significance labels or stars.
- **Boundary:** McNemar p-values concern paired Hit@4 discordance and are distinct from the chunk-recall effect and bootstrap interval.
- **Main-text cross-reference:** Section 11.2 and Figure 2 caption or table note.

### Supplementary Table S2 — Detailed W-RQ2 secondary outcomes

- **Purpose:** Preserve secondary detail without widening the main tables.
- **Sources:** `w_rq2_partial_credit_by_condition.csv`, `w_rq2_partial_credit_pairwise_vs_r0.csv`, `w_rq2_unsupported_count_by_condition.csv`, `w_rq2_unsupported_count_pairwise_vs_r0.csv`, and `w_rq2_expected_point_labels_by_condition.csv`.
- **Structure:** Three labeled panels: (A) partial-credit descriptive and paired statistics; (B) unsupported-claim count descriptive and paired statistics; (C) covered/partially covered/not covered/contradicted expected-point totals. Retain bootstrap seed and resample count in the note rather than repeating them in every row.
- **Boundary:** Secondary outcomes are not combined with the primary endpoint; expected points are nested within cases and are not independent inferential observations.
- **Main-text cross-reference:** Sections 11.6 and 11.7.

### Supplementary Table S3 — W-RQ3 insufficient-evidence handling

- **Purpose:** Preserve the complete descriptive W-RQ3 result while avoiding a visually exaggerated main-text comparison based on six cases per condition.
- **Sources:** `w_rq3_insufficient_label_distribution.csv` and `w_rq3_case_by_condition.csv`.
- **Structure:** Panel A reports the four-category count distribution by condition. Panel B lists case ID, condition, and frozen `insufficient_handling` label for traceability. Counts, not percentages alone, must be shown.
- **Boundary:** `n = 6` per condition; no inferential test, ranking, safety score, or generalized conclusion.
- **Main-text cross-reference:** Section 11.8. The main text should retain the concise prose summary and point readers to Table S3.

## 5. Rejected candidate visualizations

| Candidate | Decision and reason |
|---|---|
| Grouped bar chart of all four Stage-A metrics | Reject from main and supplement. Table 1 communicates exact values more compactly; grouped bars encourage visual ranking across distinct metrics and rely on several color categories. The existing chart is useful for internal checking but not needed in the final package. |
| Grouped point plot of Stage-A condition metrics | Reject. It retains the same metric-mixing and redundancy problems as the grouped bar chart. |
| Bar chart of full-coverage condition means | Reject. Figure 3 presents the more relevant paired comparison and Table 2 gives exact means. A second means chart would be redundant. |
| Unsupported-claim or contradiction bar chart | Reject. Small event counts and different rubric outcomes are better represented by exact `n/N` values; bars could visually suggest a safety ranking. |
| Stacked expected-point chart | Reject from the main text. Points are nested within cases, and a prominent stacked chart could make them appear like independent observations. Retain counts in Supplementary Table S2. |
| W-RQ3 chart | Reject. With six cases per condition and descriptive-only analysis, a plot would overstate visual differences. Use prose plus Supplementary Table S3. |
| Pie, donut, radar, traffic-light, or composite-score graphic | Reject. These formats either obscure denominators, imply a unified performance construct, or create winner/safety semantics unsupported by the design. |
| Latency comparison | Reject. Frozen latency is confounded by cache state and execution order. |

## 6. Exact data-source crosswalk

| Output ID | Frozen source file(s) | Exact data used |
|---|---|---|
| Figure 1 | `MANUSCRIPT_FROZEN.md`; follow-up `FROZEN.md`; `stage_c2_analysis_manifest.json` | Study identities; 16/271 corpus; 48 cases; Stage-A and Stage-B 192-cell completions; terminated automated Stage C; W-RQ2 42/168; W-RQ3 6/24; frozen-answer reuse |
| Figure 2 | `stage_a_publication_v0_1_5/tables/stage_a_pairwise_vs_r0.csv` | `comparison`, `n_paired_cases`, recall mean difference, bootstrap lower/upper bounds |
| Figure 3 | `western_semantic_followup_v0_2/tables/w_rq2_primary_pairwise_vs_r0.csv` | `comparison`, `n`, full-coverage mean difference, bootstrap lower/upper bounds, seed, resamples |
| Table 1 | `stage_a_publication_v0_1_5/tables/stage_a_headline_metrics.csv` | Condition, n, chunk recall, source recall, Hit@4, MRR |
| Table 2 | `w_rq2_primary_coverage_by_condition.csv`; `w_rq2_partial_credit_by_condition.csv` | Condition, n, primary mean/SD, secondary mean/SD |
| Table 3 | `w_rq2_unsupported_presence_by_condition.csv`; `w_rq2_unsupported_mcnemar_vs_r0.csv`; `w_rq2_contradictions_by_condition.csv` | Presence counts/rates, contradiction counts/rates, contradicted-point totals, discordances, raw/Holm p-values |
| Table S1 | `stage_a_pairwise_vs_r0.csv` | All frozen columns |
| Table S2 | Five W-RQ2 partial-credit, unsupported-count, and expected-point CSVs named above | All frozen condition summaries and paired estimates relevant to those secondary outcomes |
| Table S3 | `w_rq3_insufficient_label_distribution.csv`; `w_rq3_case_by_condition.csv` | Four-category distributions and case-condition labels |

All relative follow-up table paths in this plan resolve under `research/experiments/western_semantic_followup_v0_2/tables/`. All Stage-A publication table paths resolve under `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/tables/`.

## 7. Rendering requirements

1. Generate every figure deterministically from the frozen files; do not transcribe values into plotting code as independent constants.
2. Produce an editable SVG as the primary figure and a PNG export at **300 dpi or higher at final print dimensions**. Keep a white background and no transparency-dependent elements.
3. Design Figure 1 for double-column width. Design Figures 2 and 3 so they remain legible at single-column width; a matched double-column layout is acceptable if journal format requires it.
4. Use a consistent sans-serif font, with a minimum final-size text height equivalent to 8 pt and axis/caption-supporting labels preferably 9–10 pt.
5. Use a neutral grayscale-safe palette. If an accent is used, use one color-blind-safe dark accent consistently for point estimates and pair it with shape, line, labels, or border style so color is never the sole encoding.
6. Use no gradients, shadows, 3D effects, icons suggesting quality, or semantic red/green. Use equal visual weight for R1−R0, R2−R0, and R3−R0.
7. Keep zero reference lines neutral and visually distinct from confidence intervals. Do not add stars, `NS`, binary significance labels, or p-value color.
8. Use neutral condition labels `R0`, `R1`, `R2`, and `R3`; define their retrieval methods in the manuscript or a table note rather than in a crowded legend.
9. Use consistent numeric formatting: condition tables may display three decimals for journal readability, while forest-plot side labels should display estimate and limits to three decimals. Authoritative CSV precision remains unchanged and should be available in supplementary/source tables.
10. Tables must use horizontal rules sparingly, no vertical-rule grid, no cell heat maps, and no maximum-value highlighting. Align decimals and show numerator/denominator for event counts.
11. Supply concise alternative text for each figure. Alternative text must describe structure and values without calling any condition best, safer, or superior.

## 8. Caption requirements

Every caption must be interpretable without returning to the body text and must include:

- the study component: Western Formal Study v0.1.5 or separate Western Semantic Follow-up v0.2;
- the analysis population and denominator;
- the endpoint and direction of any contrast;
- the interval method where applicable;
- whether the outcome is primary, secondary, or descriptive;
- a bounded interpretation sentence where misreading is plausible.

Captions must not use “best,” “winner,” “superior,” “optimal,” “outperformed,” “significant,” “non-significant,” “safer,” “hallucination reduction,” or equivalent ranking/clinical language. For Tables 2 and 3 and Figure 3, captions should state that evaluation was performed by one GPT-5.6 Sol evidence-grounded evaluator and is not clinical validation.

## 9. Manuscript insertion sequence and interpretation safeguards

Recommended sequence:

1. Cite Figure 1 in Section 3 to establish study architecture before detailed Methods.
2. Retain Table 1 in Section 11.2, followed by Figure 2 for the paired Stage-A effects.
3. Place Table 2 and then Figure 3 in Section 11.6, separating condition-level descriptions from paired primary-endpoint comparisons.
4. Place Table 3 in Section 11.7.
5. Keep W-RQ3 as bounded prose in Section 11.8 with a reference to Supplementary Table S3.
6. Cite Tables S1 and S2 only where the detailed secondary or exact paired statistics are first mentioned.

Package-wide safeguards:

- Never visually join the terminated Stage-C node to the follow-up as a continuation.
- Never use color, order, boldface, or annotations to designate a preferred condition.
- Treat confidence intervals and p-values descriptively; do not translate them into binary labels.
- Keep full coverage visibly designated as the follow-up primary endpoint; label partial credit and unsupported/contradiction outcomes as secondary.
- Do not interpret lower rubric-defined unsupported-claim or contradiction counts as clinical safety, general factuality, or validated hallucination reduction.
- Do not infer that Stage-A retrieval differences caused follow-up semantic differences.
- Do not treat individual expected points as independent inferential units.
- State the single-evaluator limitation wherever semantic results are summarized visually.
- Preserve pilot scope: 16 reviews, four topic domains, 48 cases, one fixed generator, and one semantic evaluator.

## 10. Proposed next mechanical rendering step

The next task should be a strictly mechanical rendering pass, not an analysis pass:

1. Create one deterministic rendering script that reads the frozen CSV/JSON/Markdown sources listed above.
2. Fail closed if expected files, conditions, row counts, denominators, seeds, resample counts, or frozen values differ from the plan.
3. Render Figures 1–3 as SVG and PNG using one shared style configuration.
4. Generate Tables 1–3 and S1–S3 directly from the source files into manuscript-ready Markdown or another requested journal format.
5. Produce a source-to-output manifest containing input paths and hashes, rendering-script hash, output hashes, dimensions, and raster DPI.
6. Perform visual QA at final single- and double-column sizes, including grayscale inspection and label-overlap checks.
7. Verify every rendered value against the frozen CSVs and run `git diff --check` before any freeze or commit.

No provider, model, or network call is required for that rendering pass, and no experiment should be rerun.

## 11. Advisor-facing sufficiency decision

**Yes.** The planned package is sufficient for an advisor-facing draft without additional experiments from a presentation-completeness perspective. It communicates the study architecture, Stage-A retrieval results, primary follow-up coverage result, unsupported-claim and contradiction behavior, and W-RQ3 handling with exact denominators and appropriate uncertainty. This judgment does not expand the study’s evidentiary scope: the package remains pilot-scale, single-generator, single-evaluator, non-clinical, and non-causal.
