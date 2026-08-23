# RQ4 Final Analysis

Status: **RQ4 COMPLETE**

## Semantic review import

The frozen blinded packet was validated against the completed review: 412 rows, 90 represented questions, no duplicate or missing item IDs, and all protected fields (question, anonymous label, Gold fact, evidence, and answer) unchanged. Labels: {'SUPPORTED': 335, 'PARTIALLY_SUPPORTED': 26, 'NOT_SUPPORTED': 39, 'CONTRADICTED': 12}. Confidence: {'HIGH': 411, 'MEDIUM': 1}.

The 19 review rows tied to explicit execution-failure answers were imported unchanged. Primary paired semantic metrics use only the 80 questions with a usable C2 and usable C4 execution; no failure was imputed as a semantic label.

## Unblinding

Unblinding used only `formal_execution_manifest.json` and its per-question `semantic_blinding_mapping`. The mapping is counterbalanced by question (43 questions C2=SYSTEM_A; 57 questions C2=SYSTEM_B), so there is no single global SYSTEM_A/SYSTEM_B identity.

## Primary and secondary results

| metric | C2 | C4 | C4-C2 | 95% CI (pp) | Wilcoxon p |
|---|---:|---:|---:|---:|---:|
| Full Recall | 83.75% | 81.25% | -2.50 pp | -8.12 to 2.50 | 0.313938 |
| Partial-or-Better | 91.25% | 93.75% | 2.50 pp | 0.42 to 5.42 | 0.100348 |
| Missing | 5.83% | 4.17% | -1.67 pp | -3.33 to -0.42 | 0.100348 |
| Contradiction | 2.92% | 2.08% | -0.83 pp | -3.75 to 1.25 | 1 |

Full Recall is evaluated against 0 pp and the preregistered +5 pp threshold; observed difference is -2.50 pp.

## Reliability and latency

C2 usable: 88/100; C4 usable: 80/100; both: 80; C2-only: 8; C4-only: 0; neither: 12. Exact McNemar p=0.0078125. Mean latency C2=7278.5 ms, C4=39659.8 ms; medians 3913.0/20397.0 ms; paired Wilcoxon p=7.99953e-15. Provider attempts: C2=125, C4=431.

## Objective metrics and debate diagnostics

Mean retrieval recall: C2=0.9000, C4=0.9000; citation recall: C2=0.8900, C4=0.7400; citation precision: C2=0.6117, C4=0.5892. Debate diagnostics are recorded in `rq4_debate_diagnostics.json`: 100 C4 traces, grounding critic invoked 75 times, multi-specialist debate 15 times, mean internal provider calls 3.07, maximum rounds 1.

## RQ1 + RQ4 synthesis

RQ1 established the frozen C1-vs-C2 comparison for single-agent versus independent-specialist generation, while RQ4 compares C2 with a structured C4 debate under the same corpus, retrieval, model, and question-level unit. The RQ4 estimate therefore addresses whether adding critique/revision/consensus improves grounded semantic recall beyond the already multi-specialist C2 baseline, with execution reliability and semantic quality reported separately.

## Final RQ4 answer

Under the frozen RQ4 protocol, C4 Full Recall was 81.25% versus 83.75% for C2, a difference of -2.50 percentage points (95% bootstrap CI -8.12 to 2.50; Wilcoxon p=0.313938) across 80 complete usable question pairs. The preregistered +5 pp threshold was not met, and C4 usable execution rate was 80/100 versus 88/100 for C2.

## Limitations

Ten planned questions had no represented semantic review because no usable C4 answer was available (eight were C2-only usable and two had neither condition usable); their exact execution statuses are preserved in `rq4_reliability_analysis.json`. The semantic review was AI-assisted external review, not independent human or clinical/TCM expert validation. Counterbalanced anonymous labels were unblinded only through the frozen manifest. Bootstrap intervals and Wilcoxon tests are question-level and exploratory beyond the preregistered primary comparison; provider failures and retries are reported rather than silently treated as quality outcomes.
