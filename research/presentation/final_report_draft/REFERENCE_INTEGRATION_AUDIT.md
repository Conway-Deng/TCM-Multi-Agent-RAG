# Reference Integration Audit

| Reference | Where cited | Exact role | Background / interpretation / corpus source | Any risk of overclaim | PASS/FAIL |
|---|---|---|---|---|---|
| [1] Lewis et al. | Sections 1.1 and 2, foundational RAG paragraph | Define retrieval-augmented generation and motivate external evidence | Background | Low; not used as evidence for project results | PASS |
| [2] Amugongo et al. | Sections 1.1 and 2, healthcare/TCM RAG paragraph | Contextualise healthcare RAG and heterogeneous evaluation | Background | Low; healthcare review is not presented as validation of this corpus | PASS |
| [3] Zhang et al. | Section 2, healthcare/TCM RAG paragraph | Establish prior TCM-specific RAG question-answering work | Background | Explicitly distinguished from this project's corpus | PASS |
| [4] Es et al. | Section 2, RAG evaluation paragraph; Section 5.2 retrieval analysis | Contextualise distinct retrieval, context, and faithfulness dimensions | Background / interpretation | Explicitly not claimed as the project's framework or result source | PASS |
| [5] Saad-Falcon et al. | Section 2, RAG evaluation and judge paragraphs; Section 5.2 judge analysis | Contextualise automated RAG evaluation and model-based evaluators | Background / interpretation | Explicitly not claimed as an implementation dependency | PASS |
| [6] Du et al. | Sections 1.1 and 2, multi-agent debate; Section 5.2 debate analysis | Give the positive side of prior debate findings under some tasks | Background / interpretation | Balanced with [7]; no universal improvement claim | PASS |
| [7] Smit et al. | Sections 1.1 and 2, multi-agent debate; Section 5.2 debate analysis | Give broader evidence on configuration-dependent debate trade-offs | Background / interpretation | No claim that debate is universally harmful | PASS |
| [8] Zheng et al. | Sections 1.1 and 2, LLM-as-a-Judge; Section 5.2 judge analysis | Contextualise judge usefulness, sensitivity, and bias | Background / interpretation | No clinical adjudication claim; project judge results remain frozen artifacts | PASS |
| [9] Wu et al. | Section 3.3 corpus provenance paragraph; References | Identify SymMap as one external structured source used for corpus construction | Corpus source | Corpus counts are explicitly attributed to the project manifest, not [9] | PASS |
| [10] Lv et al. | Section 3.3 corpus provenance paragraph; References | Identify TCMBank as one external structured source used for corpus construction | Corpus source | Corpus counts are explicitly attributed to the project manifest, not [10] | PASS |

## Boundary checks

- Exactly ten bibliography entries are present.
- No `[REFERENCE NEEDED]` placeholder remains.
- Section 2 is a six-paragraph Related Work section rather than a summary of the project's experiments.
- Section 3.3 cites TCMBank [10] and SymMap v2 [9] and reports 4,461, 3,531, and 930 only as frozen project-manifest counts.
- No Huangdi Neijing / 黄帝内经 corpus input is introduced.
- Zhang et al.'s corpus is explicitly distinguished from the project corpus.
- External publications are not used as evidence for benchmark N values, Full Recall, Accuracy, Macro-F1, usability, latency, confidence intervals, or p-values.
- SafeJudge remains a deterministic prototype governance extension; evidence confidence remains a source-grounded response reliability indicator.
