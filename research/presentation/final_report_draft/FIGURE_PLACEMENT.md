# Figure placement

| Figure | Report section | Proposed caption | Purpose and caveat |
|---|---|---|---|
| `figure1_system_architecture.png` | 3.1 | **Figure 1.** TCM-focused MediRAG-Judge pipeline from question input through planning, retrieval, specialist reasoning, debate/consensus, governance judges, and integrated response. | Establishes the implemented interface; not clinical certification. |
| `figure2a_retrieval_selection.png` | 5.1.3 | **Figure 2a.** Selection-stage Recall@4 across R0–R3 on the frozen 40-question selection set. | Selection metric only; not downstream answer quality. |
| `figure2b_retrieval_downstream.png` | 5.1.3 | **Figure 2b.** Confirmation-stage downstream Full Recall for R0 and selected R3 on a separate 60-question confirmation set. | Shows that better retrieval selection did not automatically improve generation. |
| `figure3a_rq4_quality_reliability.png` | 5.1.2 | **Figure 3a.** RQ4 C2 ordinary Multi-Agent versus C4 one-round same-model Debate. Full Recall uses 80 complete usable pairs; usability uses 100 executions per condition. | Populations are intentionally separated. |
| `figure3b_rq4_latency.png` | 5.1.2 | **Figure 3b.** Mean latency for C2 and C4 in seconds under the RQ4 protocol. | Latency is shown separately from quality. |
| `figure4_evidence_judge.png` | 5.1.4 | **Figure 4.** Research B Accuracy and Macro-F1 for J1 claim-only and J2 claim-plus-evidence judging. | Source-grounded classification, not clinical correctness. |
| `figure5_a3_quality_usability.png` | 5.1.6 | **Figure 5a.** A3 v1.3 M1 homogeneous versus M2 tested heterogeneous debate. Strict Full Recall uses 76 complete usable pairs; usability uses 100 executions per condition. | M2 is not three independent model families. |
| `figure5_a3_latency.png` | 5.1.6 | **Figure 5b.** A3 v1.3 mean latency in seconds for M1 and M2. | Operational cost is separate from complete-pair semantic quality. |
