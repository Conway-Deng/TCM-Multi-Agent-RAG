# Report source map

All numerical statements below were checked against frozen artifacts in the sibling `code_git` checkout. Hashes are SHA-256.

| Report section | Statement / value | Source artifact | SHA-256 |
|---|---|---|---|
| 3, 8 | Integrated TCM pipeline and SafeJudge/Confidence Judge terminology | `integrated_medirag_judge` commits `878bb85` through `911b190`; `research/safejudge_extension/SAFEJUDGE_V0_1_FROZEN_SPEC.md` | implementation traceability; frozen spec semantics unchanged |
| 4.3, Table 1 | TCM Corpus v1: 4,461 chunks | `research/corpus/manifests/tcm_v1_manifest.json` | `94B216F0ED79460825217311ECBB18C628AEC0BFC6519943DF384027A829F3CE` |
| 5.1, Figure 2a | Selection Recall@4: R0 0.95, R1 0.95, R2 0.975, R3 1.00 | `research/retrieval_ablation/formal_stage1/stage1_summary.json` | `083502DA7C1519A1E5D6CDF083CEB8B1E09385BFC53DFF61F8C0FB5663DF46B1` |
| 5.1, Figure 2b | Confirmation Full Recall: R0 0.8000, R3 0.7667; difference −0.0333; CI −0.1500 to +0.0833; p=0.7744 | `research/retrieval_ablation/RETRIEVAL_ABLATION_FINAL_SUMMARY.md` | `54E6A816C496747B9B20F8535BD1BBD5C3AD87E1AC43E9BF923DAD6F292127A7` |
| 5.1, Figure 3 | RQ4 C2/C4 Full Recall 83.75%/81.25%; usability 88/80; latency 7.2785/39.6598 s | `research/experiments/rq4_debate_vs_multiagent/formal_run_v1/final_analysis/rq4_final_results.md` | `A19AA22F1D41F4DCE7DA5272B3433D85CA604D02B9DCA90EA1CD8B1D4C6512E4` |
| 5.1, Figure 4 | Research B Accuracy 35.56%/82.92%; Macro-F1 0.2903/0.7975; CI and McNemar p | `research/research_b/formal_run_v1/final_analysis/research_b_final_results.md` | `1CDC21465EDE4019E4DC9B857777C7191C3693BFDA6C0AEE64DE2EE2EE8D65B0` |
| 5.1 | Research C K1/K2 Macro-F1 0.7797/0.7589; coverage and transparency signals | `research/research_c/formal_run_v1/research_c_final_results.json` | `DAE21B60EC53DBFC714B79FFAD8EB4E9264B2B312472358BE0E380063ED6DFFD` |
| 5.1, Figure 5 | A3 M1/M2 strict Full Recall 73.7%/81.6%, N=76; CI +1.3 to +15.8; p=0.0703125 | `research/multi_model_debate/formal_v1_3/FINAL_RESULTS.md` | `C3ED3D075744E359ADD124E6A5EC153884138361253D33CB110D71C5845A8EB8` |
| 5.1, Figure 5 | A3 usability 96/78 per 100; p=0.000121117; latency 115.12/391.46 s | same A3 `FINAL_RESULTS.md` | same hash |
| 5.1 | RQ1 confirmatory C1/C2 Full Recall 90.76%/90.58%; difference −0.18 pp; CI −1.81 to +1.63 | `research/experiments/rq1_c1_vs_c2/rq1_closeout/rq1_final_results_with_confirmatory.md` | `A2664A51A1BABC70D176F7BBA7BE33D7AAA5207534BAD3562476ED48362825AC` |

The template was found at `D:\project\multi_agent_rag_research\Summer Internship Final Report 2026 template.docx`; the repository-relative path named in the prompt was absent. The template itself was not modified.
