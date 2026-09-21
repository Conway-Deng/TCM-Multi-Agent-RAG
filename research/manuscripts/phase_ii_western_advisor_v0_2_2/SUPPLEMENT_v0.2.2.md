# Supplementary Material — Phase II Western Advisor-Facing Manuscript v0.2.2

This supplement reproduces the frozen supplementary tables from the Phase II Western Manuscript v0.2.1 publication package. It contains no new analysis.

## Table S1: Complete Stage-A Paired Retrieval Statistics

| Comparison | Paired n | Mean Recall Diff | 95% Bootstrap CI | R0 Hit / Comp Miss | R0 Miss / Comp Hit | Discordant Pairs | Exact McNemar p |
|---|---|---|---|---|---|---|---|
| R1 - R0 | 42 | 0.206349 | [0.083333, 0.333333] | 2 | 10 | 12 | 0.038574 |
| R2 - R0 | 42 | 0.095238 | [0.011905, 0.190476] | 0 | 6 | 6 | 0.031250 |
| R3 - R0 | 42 | 0.107143 | [0.011905, 0.218254] | 2 | 6 | 8 | 0.289062 |

**Note:** Western Formal Study v0.1.5. Headline retrieval paired comparisons across 42 answerable cases. Chunk recall differences evaluate micro-aggregated primary gold items. Confidence intervals are 95% percentile intervals from 10,000 paired case bootstrap resamples (seed 20260815). McNemar p-values evaluate paired Hit@4 discordance using an exact two-sided binomial test. No multiplicity adjustment was prespecified in Stage A.

## Table S2: Detailed W-RQ2 Secondary Semantic Outcomes

### Panel A: Partial-Credit Coverage

| Condition | n | Mean | SD | Median | Min | Max |
|---|---|---|---|---|---|---|
| R0 | 42 | 0.686508 | 0.338281 | 0.75 | 0 | 1 |
| R1 | 42 | 0.863095 | 0.229012 | 1.0 | 0.25 | 1 |
| R2 | 42 | 0.738095 | 0.321735 | 1.0 | 0 | 1 |
| R3 | 42 | 0.785714 | 0.300261 | 1.0 | 0 | 1 |

| Paired Comparison | n | Mean Diff | 95% Bootstrap CI |
|---|---|---|---|
| R1 - R0 | 42 | 0.176587 | [0.087302, 0.277778] |
| R2 - R0 | 42 | 0.051587 | [-0.015873, 0.123016] |
| R3 - R0 | 42 | 0.099206 | [0.021825, 0.188492] |

### Panel B: Unsupported-Claim Counts

| Condition | n | Mean Count | SD | Median | Min | Max |
|---|---|---|---|---|---|---|
| R0 | 42 | 0.261905 | 0.543679 | 0.0 | 0 | 2 |
| R1 | 42 | 0.119048 | 0.327770 | 0.0 | 0 | 1 |
| R2 | 42 | 0.095238 | 0.370203 | 0.0 | 0 | 2 |
| R3 | 42 | 0.095238 | 0.370203 | 0.0 | 0 | 2 |

| Paired Comparison | n | Mean Diff | 95% Bootstrap CI |
|---|---|---|---|
| R1 - R0 | 42 | -0.142857 | [-0.309524, 0.023810] |
| R2 - R0 | 42 | -0.166667 | [-0.285714, -0.071429] |
| R3 - R0 | 42 | -0.166667 | [-0.333333, 0.000000] |

### Panel C: Expected Evidence-Point Label Totals

| Condition | Covered | Partially Covered | Not Covered | Contradicted | Total Points | n Cases |
|---|---|---|---|---|---|---|
| R0 | 31 | 16 | 8 | 3 | 58 | 42 |
| R1 | 44 | 7 | 6 | 1 | 58 | 42 |
| R2 | 35 | 13 | 9 | 1 | 58 | 42 |
| R3 | 38 | 10 | 10 | 0 | 58 | 42 |

**Note:** Western Semantic Follow-up v0.2 secondary outcomes. 42 answerable cases per condition. Bootstrap resamples = 10,000, seed = 20260815. In Panel C, individual expected points are nested within benchmark cases and do not represent independent inferential units.

## Table S3: W-RQ3 Insufficient-Evidence Handling

### Panel A: Condition-Level Categorical Handling Distribution (n = 6 cases per condition)

| Condition | n | Appropriate Abstention | Bounded Insufficiency | Substantive w/o Ack | Overclaim Beyond Pilot |
|---|---|---|---|---|---|
| R0 | 6 | 1 (16.7%) | 5 (83.3%) | 0 (0.0%) | 0 (0.0%) |
| R1 | 6 | 0 (0.0%) | 5 (83.3%) | 0 (0.0%) | 1 (16.7%) |
| R2 | 6 | 0 (0.0%) | 5 (83.3%) | 0 (0.0%) | 1 (16.7%) |
| R3 | 6 | 0 (0.0%) | 5 (83.3%) | 0 (0.0%) | 1 (16.7%) |

### Panel B: Complete Case-Level Audit Labels (all 24 condition-case cells)

| Case ID | Condition | Insufficient Handling Label |
|---|---|---|
| `westbench-v0.1-constipation-12` | R0 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-cough-11` | R0 | `appropriate_abstention` |
| `westbench-v0.1-cough-12` | R0 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-dyspepsia-11` | R0 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-dyspepsia-12` | R0 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-headache-12` | R0 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-constipation-12` | R1 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-cough-11` | R1 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-cough-12` | R1 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-dyspepsia-11` | R1 | `overclaim_beyond_pilot_evidence` |
| `westbench-v0.1-dyspepsia-12` | R1 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-headache-12` | R1 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-constipation-12` | R2 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-cough-11` | R2 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-cough-12` | R2 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-dyspepsia-11` | R2 | `overclaim_beyond_pilot_evidence` |
| `westbench-v0.1-dyspepsia-12` | R2 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-headache-12` | R2 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-constipation-12` | R3 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-cough-11` | R3 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-cough-12` | R3 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-dyspepsia-11` | R3 | `overclaim_beyond_pilot_evidence` |
| `westbench-v0.1-dyspepsia-12` | R3 | `appropriate_bounded_insufficiency` |
| `westbench-v0.1-headache-12` | R3 | `appropriate_bounded_insufficiency` |

**Note:** W-RQ3 descriptive evaluation in Western Semantic Follow-up v0.2. Total denominator is 6 insufficient-evidence cases across 4 conditions (24 cells total). Due to small sample size, results are reported purely descriptively with no inferential tests performed. Evaluated by single GPT-5.6 Sol evaluator against frozen pilot evidence.
