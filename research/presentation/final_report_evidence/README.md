# Final report evidence and figure package

This package is presentation-only. It does not rerun experiments, call providers, or alter frozen research artifacts. PNG figures are exported at 300 DPI; SVG companions are provided for editing.

## Figures and provenance

| Figure | Outputs | Frozen source artifact(s) | Interpretation / caveat |
|---|---|---|---|
| 1. TCM-focused system architecture | `figures/figure1_system_architecture.{png,svg}` | Integrated interface at commit `3d67cce`; frozen SafeJudge terminology | Interface pipeline, not clinical certification or medical truth. |
| 2. Retrieval ablation | `figures/figure2a_retrieval_selection.*`, `figure2b_retrieval_downstream.*` | `research/retrieval_ablation/formal_stage1/stage1_summary.json`; `RETRIEVAL_ABLATION_FINAL_SUMMARY.md` | R3 reached 100% selection Recall@4, but confirmation Full Recall was 76.67% vs R0 80.00%; selection and confirmation populations are separate. |
| 3. Same-model debate trade-off | `figures/figure3a_rq4_quality_reliability.*`, `figure3b_rq4_latency.*` | `research/experiments/rq4_debate_vs_multiagent/formal_run_v1/final_analysis/rq4_final_results.md` | C4 did not improve Full Recall and was slower/less usable; quality uses 80 complete usable pairs, usability uses all 100 executions. |
| 4. Evidence-aware judge | `figures/figure4_evidence_judge.*` | `research/research_b/formal_run_v1/final_analysis/research_b_final_results.md`; classification report JSON | Evidence access materially improved Accuracy and Macro-F1 in this source-grounded classification task. |
| 5. A3 homogeneous vs heterogeneous debate | `figures/figure5_a3_quality_usability.*`, `figure5_a3_latency.*` | `research/multi_model_debate/formal_v1_3/FINAL_RESULTS.md` | M2 point estimate was higher on strict Full Recall but had lower usability and much higher latency; quality N=76 complete pairs, usability N=100 executions. |

Machine-readable plotted values are in `figure_data/`. The analysis/generation script is `generate.ps1` in this package; it uses only the values recorded in the tables and frozen summaries above.

## Statistical companion values

- Retrieval confirmation: R3−R0 Full Recall −3.33 pp; paired bootstrap 95% CI −15.00 to +8.33 pp; exact McNemar p=0.7744.
- RQ4: C4−C2 Full Recall −2.50 pp; 95% CI −8.12 to +2.50 pp; Wilcoxon p=0.313938. Usability 80/100 vs 88/100; exact McNemar p=0.0078125.
- Research B: J2−J1 Accuracy +47.36 pp; 95% CI +41.00 to +53.97 pp; exact McNemar p=5.5852e−33. Macro-F1 difference +0.5072.
- A3 v1.3: M2−M1 strict Full Recall +7.9 pp; paired bootstrap 95% CI +1.3 to +15.8 pp; exact McNemar p=0.0703125. Usability difference −18.0 pp; exact paired p=0.000121117.

## Source hashes (SHA-256)

- `retrieval_ablation/formal_stage1/stage1_summary.json`: `083502DA7C1519A1E5D6CDF083CEB8B1E09385BFC53DFF61F8C0FB5663DF46B1`
- `retrieval_ablation/RETRIEVAL_ABLATION_FINAL_SUMMARY.md`: `54E6A816C496747B9B20F8535BD1BBD5C3AD87E1AC43E9BF923DAD6F292127A7`
- `research_b/formal_run_v1/final_analysis/research_b_final_results.md`: `1CDC21465EDE4019E4DC9B857777C7191C3693BFDA6C0AEE64DE2EE2EE8D65B0`
- `research_b/formal_run_v1/final_analysis/research_b_classification_report.json`: `E13EFBB115501C5A7BAB73E78093BFF6AA03E46F7EF1117CC31E14B2A6A2E3DF`
- `research_c/formal_run_v1/research_c_final_results.md`: `FAFF71AFD22EAF8590D4BCBD526459EC1062D6377C82677004680516ABC2D7C`
- `research_c/formal_run_v1/research_c_final_results.json`: `DAE21B60EC53DBFC714B79FFAD8EB4E9264B2B312472358BE0E380063ED6DFFD`
- `experiments/rq4_debate_vs_multiagent/formal_run_v1/final_analysis/rq4_final_results.md`: `A19AA22F1D41F4DCE7DA5272B3433D85CA604D02B9DCA90EA1CD8B1D4C6512E4`
- `experiments/rq1_c1_vs_c2/rq1_closeout/rq1_final_results_with_confirmatory.md`: `A2664A51A1BABC70D176F7BBA7BE33D7AAA5207534BAD3562476ED48362825AC`
- `multi_model_debate/formal_v1_3/FINAL_RESULTS.md`: `C3ED3D075744E359ADD124E6A5EC153884138361253D33CB110D71C5845A8EB8`

## Caveats

All values are source-grounded TCM research metrics, not clinical safety, clinical probability, medical certainty, or treatment efficacy. A3 M2 is a tested three-checkpoint configuration, not three fully independent model families. Retrieval selection and confirmation stages use different question sets. Unusable executions are separated from semantic quality where specified. Research C has only 12 authentic direct-conflict cases.
