# External Reference Register v0.2.1

## Purpose and Scope

This register documents the approved external scientific literature integrated into Phase II Western Manuscript working version v0.2.1. These references support background, methodological, and interpretive claims (E01–E06) identified during manuscript drafting and scientific review.

**Selection Provenance:**
All references in this register were selected by prior GPT-5.6 Sol literature review and verified against publication records. No new literature selection, web searches, or exploratory bibliographic expansions were performed during v0.2.1 assembly.

---

## Reference Summary Table

| Ref ID | Authors | Year | Short Title | Venue / Journal | DOI | Mapped Claims |
|---|---|---|---|---|---|---|
| **R1** | Zhao et al. | 2026 | Evaluation Methods for Inference-Time RAG and Graph-RAG in Health Care | *J Med Internet Res* | `10.2196/90046` | E01 |
| **R2** | Samuel et al. | 2026 | Beyond Relevance: On Retrieval and RAG Information Coverage | *Proc ACM SIGIR ICTIR* | `10.1145/3805713.3820424` | E01, E04 |
| **R3** | Wu et al. | 2025 | Assessing How Well LLMs Cite Relevant Medical References | *Nat Commun* | `10.1038/s41467-025-58551-6` | E02 |
| **R4** | Carl et al. | 2026 | Transparent Source Attribution in Uro-Oncology LLMs | *Eur J Cancer* | `10.1016/j.ejca.2025.116168` | E02 |
| **R5** | Liu et al. (CONSORT-AI) | 2020 | Reporting Guidelines for Clinical Trials Involving AI (CONSORT-AI) | *BMJ* | `10.1136/bmj.m3164` | E03 |
| **R6** | Vasey et al. (DECIDE-AI) | 2022 | Early-Stage Clinical Evaluation of AI Decision Support (DECIDE-AI) | *Nat Med* | `10.1038/s41591-022-01772-9` | E03 |
| **R7** | Ru et al. (RAGChecker) | 2024 | RAGChecker: Diagnosing Retrieval-Augmented Generation | *NeurIPS 2024* | `10.52202/079017-0692` | E04 |
| **R8** | Pattnayak & Bhatia | 2026 | ReproEvalCard: Reporting Standard for Reproducible LLM Evaluation | *ACL 2026 Short Papers* | `10.18653/v1/2026.acl-short.22` | E05 |
| **R9** | Bavaresco et al. | 2025 | LLMs instead of Human Judges? Empirical Study Across 20 NLP Tasks | *ACL 2025 Short Papers* | `10.18653/v1/2025.acl-short.20` | E05, E06 |
| **R10** | Xu et al. | 2025 | The Progress Illusion: Revisiting Meta-Evaluation of LLM Evaluators | *EMNLP 2025 Findings* | `10.18653/v1/2025.findings-emnlp.1036` | E06 |

---

## Detailed Reference Dossiers

### R1 — Zhao et al. 2026
- **Reference ID:** R1
- **Full Title:** "Evaluation Methods for Inference-Time Retrieval-Augmented and Graph Retrieval-Augmented Large Language Models in Health Care: Scoping Review"
- **Authors:** Yuhan Zhao, Yiqun Miao, Rongrong Guo, Yuan Luo, Huiying Wang, Ying Wu
- **Year:** 2026
- **Venue / Journal:** *Journal of Medical Internet Research*
- **Volume / Pages / Article:** 2026;28:e90046
- **DOI:** `10.2196/90046`
- **Mapped Claim(s):** E01
- **Exact Bounded Role in Manuscript:** Provides scoping-review context that healthcare RAG behavior depends on retrieval as well as generation, supporting retrieval-layer evaluation.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Supports that healthcare RAG requires systematic evaluation of retrieval alongside generation; does not warrant claiming that better retrieval always produces clinically better answers.

### R2 — Samuel et al. 2026
- **Reference ID:** R2
- **Full Title:** "Beyond Relevance: On the Relationship Between Retrieval and RAG Information Coverage"
- **Authors:** Saron Samuel, Alexander Martin, Eugene Yang, Andrew Yates, Dawn Lawrie, Ian Soboroff, Laura Dietz, Benjamin Van Durme
- **Year:** 2026
- **Venue / Journal:** *Proceedings of the 2026 International ACM SIGIR Conference on Innovative Concepts and Theories in Information Retrieval (ICTIR)*
- **Volume / Pages / Article:** 2026:337–348
- **DOI:** `10.1145/3805713.3820424`
- **Mapped Claim(s):** E01, E04
- **Exact Bounded Role in Manuscript:** Examines the relationship between retrieval and information coverage available to generation (E01) and supports that retrieval metrics and downstream RAG generation coverage are related but not interchangeable (E04).
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Retains the manuscript's non-causal boundary. Shows empirical correlation between retrieval and coverage without implying a deterministic or causal guarantee between retrieval rankings and downstream generation quality.

### R3 — Wu et al. 2025
- **Reference ID:** R3
- **Full Title:** "An automated framework for assessing how well LLMs cite relevant medical references"
- **Authors:** Kevin Wu, Eric Wu, Kevin Wei, Angela Zhang, Allison Casasola, Teresa Nguyen, Sith Riantawan, Patricia Shi, Daniel Ho, James Zou
- **Year:** 2025
- **Venue / Journal:** *Nature Communications*
- **Volume / Pages / Article:** 2025;16:3615
- **DOI:** `10.1038/s41467-025-58551-6`
- **Mapped Claim(s):** E02
- **Exact Bounded Role in Manuscript:** Supports the necessity of transparent, verifiable reference attribution and citation provenance in medical LLM outputs, framing MediRAG’s structured chunk- and source-level provenance fields.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Supports source support, attribution, and verifiability; does not imply that generating citations automatically guarantees clinical accuracy or safety.

### R4 — Carl et al. 2026
- **Reference ID:** R4
- **Full Title:** "Enhancing clinicians' trust in large language models via transparent source attribution: A randomized controlled evaluation in uro-oncology"
- **Authors:** Nicolas Carl et al.
- **Year:** 2026
- **Venue / Journal:** *European Journal of Cancer*
- **Volume / Pages / Article:** 2026;233:116168
- **DOI:** `10.1016/j.ejca.2025.116168`
- **Mapped Claim(s):** E02
- **Exact Bounded Role in Manuscript:** Reports a clinical evaluation of transparent source attribution and supports the relevance of source verifiability and auditability in medical AI information systems.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Supports the auditability rationale for provenance fields; does not imply that MediRAG’s metadata fields alone prove clinical efficacy.

### R5 — Liu et al. 2020
- **Reference ID:** R5
- **Full Title:** "Reporting guidelines for clinical trial reports for interventions involving artificial intelligence: the CONSORT-AI Extension"
- **Authors:** Xiaoxuan Liu, Samantha Cruz Rivera, David Moher, Melanie J Calvert, Alastair K Denniston, on behalf of the SPIRIT-AI and CONSORT-AI Working Group
- **Year:** 2020
- **Venue / Journal:** *BMJ*
- **Volume / Pages / Article:** 2020;370:m3164
- **DOI:** `10.1136/bmj.m3164`
- **Mapped Claim(s):** E03
- **Exact Bounded Role in Manuscript:** Methodological context from established AI evaluation reporting standards emphasizing transparent reporting of missing data, unevaluated outcomes, and performance errors.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Methodological context only. CONSORT-AI does not directly govern this computational benchmark pilot; it illustrates the general scientific norm of explicitly reporting unachieved evaluation stages rather than concealing or rewriting them.

### R6 — Vasey et al. 2022
- **Reference ID:** R6
- **Full Title:** "Reporting guideline for the early-stage clinical evaluation of decision support systems driven by artificial intelligence: DECIDE-AI"
- **Authors:** Baptiste Vasey et al.
- **Year:** 2022
- **Venue / Journal:** *Nature Medicine*
- **Volume / Pages / Article:** 2022;28:924–933
- **DOI:** `10.1038/s41591-022-01772-9`
- **Mapped Claim(s):** E03
- **Exact Bounded Role in Manuscript:** Methodological context from early-stage AI decision support evaluation guidelines emphasizing transparent documentation of study modifications, failure modes, and unevaluated components.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Methodological context only. DECIDE-AI does not directly govern this computational study; it provides broader guidance on transparently reporting evaluation limits and error handling.

### R7 — Ru et al. 2024
- **Reference ID:** R7
- **Full Title:** "RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation"
- **Authors:** Dongyu Ru et al.
- **Year:** 2024
- **Venue / Journal:** *Advances in Neural Information Processing Systems 37 (NeurIPS 2024)*
- **Volume / Pages / Article:** NeurIPS 2024
- **DOI:** `10.52202/079017-0692`
- **Mapped Claim(s):** E04
- **Exact Bounded Role in Manuscript:** Supports fine-grained diagnostic separation between retrieval-layer metrics and generation-layer metrics, reinforcing that retrieval success and downstream generation quality measure distinct phenomena.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Confirms that retrieval metrics and answer quality are not interchangeable; does not imply causal determinism between retrieval rankings and generation correctness.

### R8 — Pattnayak & Bhatia 2026
- **Reference ID:** R8
- **Full Title:** "ReproEvalCard: A Reporting Standard for Reproducible Evaluation of LLM Pipelines"
- **Authors:** Priyaranjan Pattnayak, Apoorv Bhatia
- **Year:** 2026
- **Venue / Journal:** *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 2: Short Papers)*
- **Volume / Pages / Article:** 2026:238–249
- **DOI:** `10.18653/v1/2026.acl-short.22`
- **Mapped Claim(s):** E05
- **Exact Bounded Role in Manuscript:** Provides methodological context for reproducible evaluation pipelines, transparent protocol documentation, judge configuration provenance, randomness controls, and intermediate execution traces.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Supports rigorous reporting of evaluation protocol execution and incident handling; does not imply that candidate judges in Western Formal Study v0.1.5 were benchmarked against ReproEvalCard directly.

### R9 — Bavaresco et al. 2025
- **Reference ID:** R9
- **Full Title:** "LLMs instead of Human Judges? A Large Scale Empirical Study across 20 NLP Evaluation Tasks"
- **Authors:** Anna Bavaresco et al.
- **Year:** 2025
- **Venue / Journal:** *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 2: Short Papers)*
- **Volume / Pages / Article:** 2025:238–255
- **DOI:** `10.18653/v1/2025.acl-short.20`
- **Mapped Claim(s):** E05, E06
- **Exact Bounded Role in Manuscript:** Provides empirical context on LLM-as-a-judge behavior, showing that model agreement varies substantially across tasks and rubrics, underscoring that automated judges cannot be assumed interchangeable with human judges and require explicit qualification and limitation boundaries.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Methodological context only. Does not imply that GPT-5.6 Sol failed validation, equals human experts, or was evaluated in Bavaresco et al.

### R10 — Xu et al. 2025
- **Reference ID:** R10
- **Full Title:** "The Progress Illusion: Revisiting meta-evaluation standards of LLM evaluators"
- **Authors:** Tianruo Rose Xu, Vedant Gaur, Liu Leqi, Tanya Goyal
- **Year:** 2025
- **Venue / Journal:** *Findings of the Association for Computational Linguistics: EMNLP 2025*
- **Volume / Pages / Article:** 2025:19033–19043
- **DOI:** `10.18653/v1/2025.findings-emnlp.1036`
- **Mapped Claim(s):** E06
- **Exact Bounded Role in Manuscript:** Demonstrates sensitivity, prompt/rubric dependence, and meta-evaluation pitfalls in automated LLM evaluators, supporting the explicit manuscript limitation that single-judge findings are evaluator- and rubric-dependent.
- **Selection Statement:** This reference was selected by prior GPT-5.6 Sol literature review.
- **Interpretive Boundary:** Methodological context only. Reinforces that single-model LLM evaluations must report evaluator dependence; does not invalidate the bounded descriptive findings of Follow-up v0.2.

---

## Mapped Claims and Prohibited Interpretations

| Claim ID | Mapped References | Primary Role | Prohibited Stronger Interpretation |
|---|---|---|---|
| **E01** | R1, R2 | Retrieval importance in RAG | Better retrieval always produces better answers. |
| **E02** | R3, R4 | Provenance and source attribution | Citations automatically establish clinical trustworthiness. |
| **E03** | R5, R6 | Reporting missing / unevaluated study elements | CONSORT-AI or DECIDE-AI directly governs this computational benchmark. |
| **E04** | R2, R7 | Non-equivalence of retrieval and generation metrics | Higher retrieval metrics causally guarantee higher answer quality. |
| **E05** | R8, R9 | Automated evaluator qualification and governance | Preserved qualification incidents constitute a universal benchmark of judge-model capability. |
| **E06** | R9, R10 | Evaluator reliability and model dependence | A single AI evaluator is interchangeable with human clinical experts or other model families. |
