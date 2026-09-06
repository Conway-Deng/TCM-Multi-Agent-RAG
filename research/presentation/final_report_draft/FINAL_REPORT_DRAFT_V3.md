# TCM-Focused MediRAG-Judge
## Evaluating Retrieval, Multi-Agent Debate, and Evidence-Aware Judging for Trustworthy Traditional Chinese Medicine Question Answering

**Working draft for supervisor review**  
**Project scope:** TCM-focused empirical implementation of the broader MediRAG-Judge vision

## 1. Project Overview

### 1.1 Problem Statement

Large language models (LLMs) can produce fluent answers that are insufficiently supported by their available evidence. This is especially important for health-related question answering, where a plausible-sounding statement may be mistaken for an established source claim. Retrieval-augmented generation (RAG) addresses part of this problem by supplying documents or evidence passages to the generation process [1], [2]. Retrieval, however, is not equivalent to correct use of evidence: a system can retrieve a relevant passage and still omit a qualifying statement, overstate a source, combine unrelated facts, or present an unsupported treatment or dosage assertion.

Multi-agent systems offer another possible response. Independent specialist agents can examine different aspects of a question, while debate or critique may expose disagreement before a final answer is synthesised [6], [7]. These mechanisms also introduce costs. More calls increase latency and failure opportunities; agents can share the same blind spots; and a consensus stage can conceal rather than resolve disagreement. A careful evaluation must therefore distinguish evidence retrieval, answer quality, reliability, and latency instead of assuming that architectural complexity is beneficial.

Automated evaluation has a related limitation. An LLM judge that sees only a claim may have little basis for deciding whether the claim is supported [8]. Supplying the reviewed evidence may improve source-grounded classification, but the resulting score is still an evaluation signal rather than ground truth. Conflict-aware and safety-oriented governance can make uncertainty and unsupported content visible, but these mechanisms should not be described as clinical certification.

This project investigates these issues in a controlled TCM setting. The implementation is intentionally narrower than the original cross-paradigm MediRAG-Judge vision: it is a TCM-focused research system using a provenance-aware TCM Corpus v1 and frozen source-grounded benchmarks. The study asks when retrieval, specialist reasoning, debate, evidence-aware judging, and transparent governance help or fail under reproducible conditions.

### 1.2 Research Objectives

1. **O1 — Retrieval:** Evaluate how retrieval strategies affect evidence retrieval and downstream source-grounded TCM answer quality.
2. **O2 — Agent architecture:** Evaluate whether multi-agent reasoning, structured debate, and model/checkpoint heterogeneity improve answer completeness and reliability.
3. **O3 — Governance:** Evaluate evidence-aware judging and conflict-aware governance for detecting and transparently handling unsupported or conflicting TCM outputs.
4. **O4 — Prototype:** Develop and demonstrate an integrated TCM-focused MediRAG-Judge prototype combining evidence, conflict, source-grounded safety, and evidence-confidence signals.

### 1.3 Research Questions / Hypotheses

**RQ1 — Retrieval.** How do different retrieval strategies affect evidence retrieval and downstream source-grounded TCM answer quality?

**RQ2 — Agent architecture and debate.** Does increasing agent, debate, or model/checkpoint diversity improve source-grounded TCM answer completeness and reliability?

**RQ3 — Evidence and conflict governance.** Can evidence-aware judging and conflict-aware mechanisms improve the detection and transparent handling of unsupported or conflicting TCM outputs?

**RQ4 — Integrated governance.** How can evidence, conflict, source-grounded safety, and evidence-confidence signals be integrated into an explainable TCM-focused MediRAG-Judge response?

## 2. Related Work & Research Gap

Retrieval-augmented generation (RAG) combines a generative language model with an external retrieval stage, allowing an answer to condition on documents or passages that are not contained solely in the model's parametric memory [1]. This architecture can improve access to knowledge-intensive information, but it also introduces a pipeline whose components must be evaluated separately. Retrieval determines which material is available; generation determines how that material is selected, interpreted, qualified, and expressed. The distinction is central for any evidence-grounded question-answering system.

Healthcare RAG is an active area because medical and health-related questions require heterogeneous sources, specialised terminology, and careful treatment of uncertainty [2]. Recent reviews also note that healthcare RAG evaluations remain heterogeneous in task definitions, datasets, metrics, and validation procedures [2]. TCM-specific work has demonstrated RAG-based question answering for traditional Chinese medicine [3], showing the feasibility of adapting retrieval and generation to domain terminology and knowledge structures. The corpus used by Zhang et al. [3] is a separate resource from the TCM Research Corpus v1 used in this project; the citation establishes domain context, not corpus identity or provenance.

RAG evaluation literature distinguishes retrieval relevance from the quality and faithfulness of the generated answer. RAGAs provides automated measures for dimensions such as context relevance, context recall, and answer faithfulness [4]. ARES similarly frames evaluation as a combination of retrieval, generation, and factuality-oriented assessments supported by automated evaluators [5]. These frameworks motivate treating passage retrieval, evidence use, and answer quality as related but non-equivalent measurements. They do not define the present project's frozen metrics, and this project does not claim to implement either framework.

Multi-agent reasoning and debate provide another line of related work. Du et al. report improvements in factuality and reasoning for some tasks when multiple agents critique and revise one another [6]. However, broader benchmarking of debate strategies finds that gains are not reliable across all tasks and configurations, with trade-offs involving cost, time, coordination, and accuracy [7]. The literature therefore supports a balanced question: debate may help under particular conditions, but additional agents and deliberation are not automatically beneficial. Model capability, role design, number of rounds, and consensus procedure all affect the outcome.

Model-based judging is increasingly used as a scalable way to evaluate generated answers and retrieval-augmented systems. ARES places automated evaluators within a structured RAG assessment framework [5], while MT-Bench and Chatbot Arena show both the usefulness and the sensitivity of LLM-as-a-Judge comparisons [8]. Judge behaviour can depend on prompt framing, available evidence, response order, style, and other biases; consequently, a judge score is an evaluation signal whose setup requires validation. This motivates empirical comparison of judge inputs, including whether the judge receives the evidence needed to assess a claim. The present paragraph does not treat these methods as clinical adjudication.

The research gap addressed by this project is the controlled integration of these strands in a TCM-focused framework. Prior work has studied retrieval-augmented generation, healthcare and TCM question answering, RAG evaluation, multi-agent debate, and model-based judging individually. The present study brings together retrieval quality, downstream source-grounded answer quality, agent/debate architecture, operational usability, latency, evidence-aware judging, and conflict transparency while keeping their units and benchmark populations separate. This design makes it possible to examine trade-offs across the pipeline without treating an external paper, a retrieval metric, or a judge score as evidence for the project's own frozen numerical results.
## 3. Proposed Method

### 3.1 Overall Approach

The integrated response path is:

**Question -> Planner -> Retrieval -> Specialist Agents -> Debate / Consensus -> Evidence Judge -> Safety Judge -> Conflict Judge -> Confidence Judge -> Integrated Response**

The final prototype is TCM-focused. It exposes retrieved passages and citations, specialist contributions, debate agreements and disagreements, judge outputs, and an integrated answer. The system records source-grounded safety flags, an evidence-supported caution assessment, evidence confidence, and response reliability indicators.

**Figure 1 placeholder.** *TCM-focused MediRAG-Judge pipeline from question input through planning, retrieval, specialist reasoning, debate/consensus, governance judges, and the integrated response. Governance indicators are source-grounded research signals and do not establish clinical certification or medical truth.*

### 3.2 Method / Architecture

The Planner establishes scope and retrieval intent before evidence is selected. Retrieval conditions R0, R1, R2, and R3 represent lexical, dense, hybrid, and hybrid-plus-reranking configurations as defined by the frozen retrieval protocol. Specialist agents operate over the retrieved evidence and may abstain when the evidence is outside their assigned subdomain. The ordinary Multi-Agent condition aggregates independent specialist outputs. The C4 Debate condition adds a one-round critique, revision, and consensus sequence under the tested same-model configuration.

The Evidence Judge compares structured claims with available evidence and citations. The Conflict Judge reports agreement, disagreement, and unresolved conflict rather than forcing a single interpretation. Safety Judge v0.1 applies six deterministic source-grounded rules, including unsupported treatment certainty, absolute medical claims, unsupported dosage or use, source caution not preserved, conflict over-resolution, and unsupported diagnostic certainty. Its output is a source-grounded safety score and finding list with rule identifiers, severity, and explanations.

Confidence Judge v0.1 computes evidence confidence from observable signals: evidence coverage, citation coverage, retrieval sufficiency, verified evidence ratio, unsupported-claim burden, unresolved conflict, model failure, and safety findings. Frozen weights, penalties, caps, and bands produce a 0–1 evidence-confidence score classified as insufficient, limited, moderate, or strong. Agent self-confidence is excluded from this score. The integrated prototype mirrors the typed judge objects into the final response while retaining legacy fields for compatibility. Individual historical experiment conditions did not necessarily invoke every judge; the final integrated pipeline should not be confused with any single frozen comparison.

### 3.3 Implementation

The backend is implemented in Python with FastAPI and a local orchestration layer. A vanilla HTML, CSS, and JavaScript dashboard provides the research workbench and formal-results presentation. The local deterministic mode can run without an external provider and is used for the integrated demonstration. Formal LLM inference in the completed research lines was accessed through the configured SiliconFlow provider API; the reports do not claim that all LLMs were hosted locally.

The principal model in the TCM experiments was Qwen/Qwen3-8B. A3 v1.3 additionally tested THUDM/GLM-Z1-9B-0414 and deepseek-ai/DeepSeek-R1-0528-Qwen3-8B in the heterogeneous configuration, while the consensus model remained Qwen/Qwen3-8B. The system used the TCM Corpus v1 and frozen benchmark packets, with fixed prompts, roles, decoding controls, evidence identifiers, and reproducibility manifests. The prototype is locally deployable research software on the Windows workstation; it is not a deployed medical system.

TCM Research Corpus v1 was constructed from two structured TCM data sources: TCMBank [10] and SymMap v2 [9]. Following the project's documented normalization and deduplication pipeline, the frozen corpus contained 4,461 retrieval chunks, comprising 3,531 TCMBank-derived chunks and 930 SymMap-derived chunks. The corpus preserves source provenance; however, provenance and source-level curation should not be interpreted as independent clinical validation of the resulting research corpus.

## 4. Experimental Design & Evaluation

### 4.1 Baselines

The architecture comparisons use C1 Single-RAG, C2 ordinary Multi-Agent, and C4 same-model structured Debate. Retrieval Ablation compares R0–R3 in a selection stage and then compares R0 with the selected R3 in an untouched confirmation stage. Research B compares J1 claim-only judging with J2 claim-plus-evidence judging. Research C compares K1 and K2 conflict conditions. A3 v1.3 compares M1 homogeneous Qwen/Qwen3-8B debate with M2, a tested heterogeneous three-checkpoint configuration. M2 is not three fully independent model families.

These comparisons use different benchmark populations and are reported separately. In particular, the RQ1 confirmatory C1/C2 study is not merged with the RQ4 C2/C4 benchmark, and A3 quality uses complete usable pairs while A3 usability uses every scheduled execution.

### 4.2 Evaluation Metrics

**Recall@k** is the proportion of relevant or gold evidence retrieved within the top *k* results. This report uses Recall@4 for the most interpretable retrieval comparison. **Strict Gold Fact Full Recall** requires all constituent gold atomic facts to be labelled SUPPORTED. **Gold Fact Recall** measures supported facts at the atomic-fact level, while **Partial-or-Better** includes supported and partially supported facts according to the frozen review scheme.

For Research B and C, **Accuracy** is the proportion of correctly classified cases and **Macro-F1** is the unweighted mean of class-level F1 scores. **Usability** is the proportion of scheduled executions producing a usable response; unusable executions are not silently converted into semantic zeroes in complete-pair quality analysis. **Citation recall** measures cited gold evidence coverage and **citation precision** measures how much cited material is relevant under the corresponding frozen metric. **Latency** is elapsed execution time, reported in milliseconds or seconds as appropriate.

The statistical procedures were those fixed by each protocol: paired bootstrap confidence intervals, exact McNemar tests for paired binary outcomes where specified, and Wilcoxon tests for the RQ4 latency analysis. Independent blinded semantic review evaluated source-grounded agreement with supplied evidence. It was not independent clinical or TCM expert validation.

### 4.3 Experimental Setup

The TCM Corpus v1 contains 4,461 indexed chunks in the configured runtime. RQ1 confirmatory used 100 held-out questions. RQ4 represented 90 questions and had 80 complete usable C2/C4 pairs. Research B used 240 balanced cases, 60 in each of SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, and CONTRADICTED classes, with 480 judge executions. Research C used 132 conflict cases, including 12 authentic direct-conflict cases. A3 v1.3 scheduled 100 executions per condition and included 76 complete usable pairs for strict quality analysis.

Formal runs used fixed model and prompt configurations, recorded evidence identifiers, bounded retries, and frozen manifests. The final A3 analysis excluded aborted v1, v1.1, and v1.2 outputs. Its M2 configuration combined Qwen/Qwen3-8B, GLM-Z1-9B-0414, and DeepSeek-R1-0528-Qwen3-8B, with Qwen/Qwen3-8B as consensus model. Frozen artifact hashes and source mappings are recorded in `REPORT_SOURCE_MAP.md`.

The paired design is important in the comparisons that use it. The same question-level unit is presented to both conditions, and bootstrap or exact paired tests operate on matched outcomes. Where a condition fails to produce a usable response, the failure is retained in the reliability analysis. For semantic quality, the protocols specify when only complete usable pairs are eligible; this prevents operational failures from being silently treated as incorrect source-grounded labels while still reporting their practical cost. The report consequently presents quality and usability side by side rather than treating one as a replacement for the other.

## 5. Results, Findings & Analysis

### 5.1 Key Results and Findings

**Finding 1 — Architectural complexity alone did not consistently improve source-grounded completeness.** In the RQ1 confirmatory study, C1 Full Recall was 90.76% and C2 was 90.58%, a difference of −0.18 percentage points (95% CI −1.81 to +1.63; exact paired p=1.0000). The result does not support a meaningful confirmatory improvement from adding independent specialists under that benchmark. RQ1 used a different population from RQ4 and is not a three-condition C1–C2–C4 experiment.

**Finding 2 — The tested same-model debate traded reliability and latency for no Full Recall gain.** In RQ4/A2, C2 Full Recall was 83.75% and C4 was 81.25% across 80 complete usable pairs (difference −2.50 pp; 95% CI −8.12 to +2.50; Wilcoxon p=0.313938). Usability was 88/100 for C2 and 80/100 for C4, while mean latency increased from 7.28 s to 39.66 s. The tested one-round design therefore did not improve semantic recall and was associated with lower usability and substantially higher latency. This does not establish that every possible debate design is harmful. Prior work has reported gains from multi-agent debate under some tasks [6], while broader benchmarking has shown that these gains are not consistent across configurations and can involve cost and latency trade-offs [7].

**Finding 3 — Better retrieval metrics did not automatically improve downstream generation.** In the 40-question selection stage, Recall@4 was 95.00% for R0, 95.00% for R1, 97.50% for R2, and 100.00% for R3. The selected R3 was then evaluated against R0 on a separate 60-question confirmation set: downstream Full Recall was 80.00% for R0 and 76.67% for R3 (R3−R0 −3.33 pp; 95% paired bootstrap CI −15.00 to +8.33; McNemar p=0.7744). Selection and confirmation are distinct populations, so the figure should be read as evidence that retrieval improvement requires downstream verification, not as a single pooled experiment.

**Finding 4 — Evidence-aware judging produced the clearest positive result.** Research B Accuracy increased from 35.56% for J1 claim-only judging to 82.92% for J2 claim-plus-evidence judging, a +47.36 percentage-point difference (95% CI +41.00 to +53.97; exact McNemar p=5.5852e−33). Macro-F1 increased from 0.2903 (29.03%) to 0.7975 (79.75%), a difference of 0.5072. Usability was 239/240 for J1 and 240/240 for J2. This finding supports the importance of evidence access for source-grounded classification; it does not prove clinical correctness.

**Finding 5 — Heterogeneous debate showed a quality point estimate with substantial operational cost.** In A3 v1.3, strict Full Recall over 76 complete usable pairs was 73.7% for M1 and 81.6% for M2, a +7.9 pp point difference (paired bootstrap 95% CI +1.3 to +15.8; exact McNemar p=0.0703125). The preregistered exact test did not reach the conventional 0.05 threshold, so confirmatory evidence for a quality advantage was not statistically clear. Usability over all 100 executions per condition was 96.0% for M1 and 78.0% for M2 (difference −18.0 pp; exact paired p=0.000121117). Mean latency was 115.12 s versus 391.46 s. M2 also showed more initial disagreement, revision activity, and consensus change. The tested heterogeneity increased deliberative activity but carried a major reliability and latency cost.

### 5.2 Analysis

The results point to a separation between information access, reasoning structure, and governance. R3’s selection-stage retrieval result was the strongest, yet its confirmation Full Recall was lower than R0’s. This may reflect interactions between ranking, prompt context, answer synthesis, and the exact evidence needed by a question. It demonstrates why retrieval metrics should not be treated as proxies for final answer quality. This separation is consistent with RAG evaluation frameworks that treat retrieval relevance and generation faithfulness as distinct dimensions [4], [5].

The C2/C4 result similarly warns against treating additional reasoning stages as a guaranteed improvement. Debate created more opportunities for critique and consensus, but the measured quality difference was negative and uncertain while latency was more than five times higher. A3 adds a different trade-off: M2’s point estimate among complete usable pairs was higher, but the reliability penalty meant that fewer runs produced usable outputs. Reporting complete-pair quality separately from all-execution usability prevents the lower M2 usability from being hidden or incorrectly scored as semantic failure.

Research B isolates a more direct mechanism. A judge with evidence access can compare claims with source passages, whereas a claim-only judge must infer source support without the relevant record. The large Accuracy and Macro-F1 difference therefore motivates evidence-first evaluation interfaces. It should not be generalized beyond the frozen TCM classification task without new validation. Model-based evaluation is an established approach in RAG and LLM assessment [5], [8], but known judge biases and task dependence reinforce the need to validate the judging setup rather than assume general reliability.

Research C is a governance result rather than an accuracy result. K2 Macro-F1 was 75.89%, below K1’s 77.97% (difference −2.09 pp; bootstrap CI −9.12 to +4.90; McNemar p=0.6476), but K2 improved citation coverage to 73.48%, viewpoint preservation to 67.42%, and uncertainty signalling to 84.09%. The main benefit was conflict transparency and reduced unsupported conflict resolution, not aggregate classification improvement.

### 5.3 Research / Project Implications

The broad implication is that architectural complexity is not a substitute for evidence discipline. Retrieval and debate should be evaluated downstream, with usability and latency reported alongside quality. Evidence-aware judging is a promising governance direction because its benefit was clearer and directly tied to access to reviewed evidence. Conflict, safety, and confidence mechanisms are most defensible as transparent response-governance signals: they show what evidence supports, where a response is cautious or unsupported, where conflict remains, and how reliable the observable evidence signals appear.

## 7. Limitations

This implementation is a TCM-focused subset of the broader MediRAG-Judge vision. Western Medicine, Nutrition, Lifestyle, and Pharmacology specialist knowledge bases were not formally implemented in this study. The original cross-paradigm conflict question was scoped to intra-TCM source conflict, so Research C should not be interpreted as a general estimate of conflict across healthcare paradigms.

The work did not include a human participant trust or usability study, clinical expert validation, or independent TCM expert adjudication. Corpus provenance identifies source records but does not constitute clinical validation. Independent AI semantic review measures agreement with supplied source-grounded reference material; it is not expert medical evaluation and does not establish medical truth.

The model and checkpoint set was limited. A3 M2 confounds model/checkpoint heterogeneity with differences in checkpoint capability, and it is not three fully independent model families. The A3 quality estimate is conditional on 76 complete usable pairs because M2 had lower usability; unusable conditions were deliberately not scored as semantic zeroes. The formal studies also used a limited number of corpora, benchmarks, provider settings, and prompt designs.

SafeJudge v0.1 and Confidence Judge v0.1 are deterministic prototype governance components. Their weights, penalties, caps, and confidence bands were frozen and offline tested, but not independently calibrated against a clinical benchmark. Deterministic text rules may miss paraphrases, quotation context, negation, or domain-specific nuance. Conversely, a source-grounded flag does not prove that a statement is medically unsafe; it indicates a detectable evidence or caution issue under the rule set.

Finally, the prototype is local research software with a static dashboard and deterministic fallback mode. It has not been deployed as a medical system, and no claim is made about real-world treatment efficacy, diagnosis, or patient outcomes.

## 8. Prototype / System Demonstration

### 8.1 Prototype Overview

The validated prototype is a locally deployable TCM-focused MediRAG-Judge research workbench. A user enters a TCM research question; the backend plans scope, retrieves source passages, invokes evidence-scoped specialist roles, and optionally performs debate or consensus. The final integrated response retains citations and exposes governance metadata.

### 8.2 Key Features

The workbench displays the question, retrieval strategy, evidence excerpts and identifiers, specialist contributions, participating and abstaining agents, debate agreements and disagreements, and the cited integrated answer. The integrated interface includes a compact panel for evidence coverage, citation coverage, retrieval sufficiency, verified evidence ratio, conflict status and score, source-grounded safety findings, safety score, evidence-confidence score and band, positive signal contributions, penalties, and applied caps. When typed judge fields are absent, the interface preserves legacy output and reports that the integrated field is unavailable for that condition.

### 8.3 Demonstration Results

The offline backend suite passed 76 tests with 4 skips, and six deterministic integrated demo scenarios passed. The demonstrations cover strong evidence, weak retrieval, unsupported treatment certainty, unsupported dosage/use, unresolved conflict, and source caution preservation. They are non-formal demonstrations, not additional experiments.

**[SCREENSHOT A — Overall prototype/dashboard]**  
Show the TCM-focused pipeline, question input, and local workbench status.

**[SCREENSHOT B — Strong-evidence response]**  
Show retrieved evidence, specialist output, citations, integrated response, and strong evidence-confidence band.

**[SCREENSHOT C — Source-grounded safety flagged response]**  
Show rule IDs, severities, explanations, and source-grounded safety score.

**[SCREENSHOT D — Conflict / reduced evidence-confidence response]**  
Show unresolved conflict, penalties/caps, evidence-confidence band, and final cautious response.

## 9. Conclusion & Future Work

### 9.1 Conclusion

This project evaluated a TCM-focused empirical implementation of MediRAG-Judge across retrieval, agent architecture, debate, evidence-aware judging, and conflict governance. The completed evidence does not support a simple “more agents is better” conclusion. The RQ1 confirmatory comparison was essentially tied, and the tested same-model debate configuration reduced Full Recall while increasing latency and lowering usability. Retrieval Ablation showed that a stronger selection-stage retrieval score did not translate into better downstream Full Recall in the confirmation set.

The clearest positive finding came from evidence-aware judging. Supplying reviewed evidence to the judge substantially increased source-grounded classification Accuracy and Macro-F1 compared with claim-only judging. Research C further suggests that governance mechanisms can improve citation, viewpoint, uncertainty, and conflict transparency even when aggregate classification does not improve. A3 v1.3 showed a higher M2 Full Recall point estimate among complete usable pairs, but the exact confirmatory test was not conventionally significant and M2 had substantially worse usability and latency.

The integrated prototype turns these lessons into an explainable response interface. It preserves evidence and citations, exposes conflict, applies deterministic source-grounded safety flags, and reports evidence confidence as a response reliability indicator. These components make limitations visible; they do not convert a source-grounded research signal into clinical certification or medical certainty.

### 9.2 Future Work

1. Extend the architecture with genuinely evidence-backed cross-paradigm agents for TCM, Western Medicine, Nutrition, and Lifestyle, with each domain evaluated separately before integration.
2. Conduct independent clinical and subject-matter expert evaluation of source selection, claim labels, conflict handling, and response interpretation.
3. Run a human trust and usability study that measures whether evidence and uncertainty displays improve calibrated understanding rather than simple confidence.
4. Evaluate larger and more independent model diversity while separating model capability from diversity effects and preserving complete-pair and usability analyses.
5. Calibrate and validate the Safety Judge and evidence-confidence indicators against independently reviewed data, including paraphrase, quotation, negation, and adverse-signal cases.

## 10. References

[1] P. Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” *Advances in Neural Information Processing Systems*, vol. 33, pp. 9459–9474, 2020.

[2] L. M. Amugongo, P. Mascheroni, S. Brooks, S. Doering, and J. Seidel, “Retrieval augmented generation for large language models in healthcare: A systematic review,” *PLOS Digital Health*, vol. 4, no. 6, e0000877, 2025, doi: 10.1371/journal.pdig.0000877.

[3] Y. Zhang, H. Li, X. Lang, Z. Zhou, Y. Ling, and Z. Wang, “Construction of Traditional Chinese Medicine Question-Answering Large Language Model Based on Retrieval-Augmented Generation Technology,” *Journal of Nanjing University of Traditional Chinese Medicine*, vol. 40, no. 12, pp. 1375–1382, 2024, doi: 10.14148/j.issn.1672-0482.2024.1375.

[4] S. Es, J. James, L. Espinosa Anke, and S. Schockaert, “RAGAs: Automated Evaluation of Retrieval Augmented Generation,” in *Proceedings of the 18th Conference of the European Chapter of the Association for Computational Linguistics: System Demonstrations*, pp. 150–158, 2024, doi: 10.18653/v1/2024.eacl-demo.16.

[5] J. Saad-Falcon, O. Khattab, C. Potts, and M. Zaharia, “ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems,” in *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)*, pp. 338–354, 2024, doi: 10.18653/v1/2024.naacl-long.20.

[6] Y. Du, S. Li, A. Torralba, J. B. Tenenbaum, and I. Mordatch, “Improving Factuality and Reasoning in Language Models through Multiagent Debate,” in *Proceedings of the 41st International Conference on Machine Learning*, PMLR 235, pp. 11733–11763, 2024.

[7] A. P. Smit, N. Grinsztajn, P. Duckworth, T. D. Barrett, and A. Pretorius, “Should we be going MAD? A Look at Multi-Agent Debate Strategies for LLMs,” in *Proceedings of the 41st International Conference on Machine Learning*, PMLR 235, pp. 45883–45905, 2024.

[8] L. Zheng et al., “Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena,” *Advances in Neural Information Processing Systems*, vol. 36, 2023.

[9] Y. Wu et al., “SymMap: an integrative database of traditional Chinese medicine enhanced by symptom mapping,” *Nucleic Acids Research*, vol. 47, no. D1, pp. D1110–D1117, 2019, doi: 10.1093/nar/gky1021.

[10] Q. Lv, G. Chen, H. He, Z. Yang, L. Zhao, H.-Y. Chen, and C. Yu-Chian Chen, “TCMBank: bridges between the largest herbal medicines, chemical ingredients, target proteins, and associated diseases with intelligence text mining,” *Chemical Science*, vol. 14, pp. 10684–10701, 2023, doi: 10.1039/D3SC02139D.

