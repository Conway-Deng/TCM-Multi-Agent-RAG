# Provisional title

**Corpus-Bounded Western Evidence Retrieval in MediRAG: A Reproducible Pilot and Blinded Semantic Follow-up**

> **Draft status:** Phase-II manuscript skeleton for scientific review, integrating the historically closed Western Formal Study v0.1.5 and the separately frozen Western Semantic Follow-up v0.2. Repository artifacts, rather than this draft, remain authoritative.

## Abstract

**Background:** Retrieval-augmented generation (RAG) depends on the evidence made available to generation as well as on the generator itself. Medical information systems therefore require explicit control of corpus scope, evidence provenance, and evaluation boundaries. [CITATION NEEDED: retrieval quality in medical RAG] [CITATION NEEDED: provenance and traceability for evidence-grounded medical information systems]

**Objective:** This Phase-II study examined a separate Western-evidence extension of MediRAG. It asked how four frozen retrieval conditions affected gold-evidence retrieval in a bounded pilot corpus and, in a later post-study follow-up, how those conditions differed in evidence-grounded semantic behavior for fixed-generator answers.

**Methods:** The Western pilot corpus comprised 16 PubMed Central Open Access systematic reviews, four in each of four topic domains—cough, dyspepsia/digestive symptoms, headache, and constipation—segmented into 271 deterministic chunks. The frozen benchmark contained 48 cases. Four retrieval conditions were evaluated: lexical retrieval (R0), dense retrieval (R1), lexical–dense reciprocal-rank fusion (R2), and fusion followed by reranking (R3), each returning four chunks. Headline Stage-A retrieval metrics used the 42 supported or partially supported cases with non-empty primary gold evidence. Generation used the fixed `Qwen/Qwen3-8B` model. The original automated Stage C terminated prospectively without a qualified Primary Judge. Western Semantic Follow-up v0.2 subsequently reused the unchanged Stage-B answers and applied one GPT-5.6 Sol evaluator with retrieval-condition identity concealed. Its primary endpoint was the case-level macro mean of full evidence-point coverage; paired intervals used 10,000 case bootstrap resamples with seed `20260815`.

**Results:** Stage A completed all 192 retrieval cells without technical failure. Aggregate primary-gold chunk recall@4 was 0.428571, 0.634921, 0.539683, and 0.523810 for R0–R3, respectively; Hit@4 was 0.595238, 0.785714, 0.738095, and 0.690476. R1 measured higher on the frozen headline retrieval metrics in this pilot. A complete primary Stage-B generation dataset was obtained for 192/192 cells after a separately preserved provider-outage attempt. Within Western Formal Study v0.1.5, W-RQ2 and W-RQ3 remained unavailable because automated Stage C terminated. In the separate follow-up, mean full-coverage scores were 0.543651, 0.805556, 0.626984, and 0.710317 for R0–R3. Paired mean differences versus R0 were 0.261905 for R1 (95% bootstrap CI [0.142857, 0.392857]), 0.083333 for R2 ([0.000000, 0.178571]), and 0.166667 for R3 ([0.059524, 0.285714]). Unsupported-claim presence was 9/42, 5/42, 3/42, and 3/42, respectively.

**Limitations and conclusion:** The corpus, topics, benchmark, generator, and provider environment were narrowly bounded; benchmark drafting and secondary review were AI-assisted. The follow-up used one AI evaluator without human or clinician adjudication, inter-rater reliability, or judge-family robustness assessment. Condition identity was concealed, but answer and evidence content could indirectly signal retrieval characteristics. Within this frozen 16-review, 48-case pilot and under a single blinded GPT-5.6 Sol evidence-grounded evaluator, semantic evidence coverage and unsupported-claim behavior differed descriptively across retrieval conditions. These findings do not establish clinical correctness, clinical safety, or a causal relationship between retrieval and generated-answer quality.

## 1. Introduction

RAG systems combine retrieval from an external corpus with language-model generation. Their behavior is shaped by which documents are eligible for retrieval, how evidence is ranked, and how retrieved material is passed to generation—not only by the generator. In medical information settings, weak or opaque retrieval can limit the evidence available to an otherwise fixed generator, while incomplete provenance can make outputs difficult to audit. [CITATION NEEDED: retrieval quality in medical RAG] [CITATION NEEDED: provenance and traceability for evidence-grounded medical information systems]

MediRAG Phase II extends the project with a Western-evidence pathway that is separate from the existing traditional Chinese medicine (TCM) pathway. The separation is architectural and evidentiary: the Western runtime loads a dedicated Western pilot corpus, routes questions to one of four Western topic domains, retrieves only from that injected corpus, and exposes source and chunk provenance. The TCM runtime and its specialist-oriented research workflow are not treated as interchangeable with the Western pathway. This separation supports corpus-bounded evaluation without implying that either evidence tradition is comprehensive or that the two pathways were compared clinically.

The formal Western pilot focused on retrieval and controlled evidence-grounded generation. Stage A compared four frozen retrieval conditions. Stage B generated one answer for each benchmark-condition cell with a fixed generator. Stage C was intended to evaluate evidence coverage, unsupported-claim behavior, and incomplete-evidence responses with a separately qualified automated judge. The qualification process ultimately reached its prospectively specified stopping rule without selecting a Primary Judge. Western Formal Study v0.1.5 therefore has a complete retrieval result for W-RQ1 and a complete generation dataset, but no formal semantic estimates for W-RQ2 or W-RQ3.

Western Semantic Follow-up v0.2 was created afterward as a separate post-study evaluation of the already frozen Stage-B answers. It supplies evidence-grounded semantic estimates under one GPT-5.6 Sol evaluator without changing the historical Stage-C status. This manuscript reports both components while keeping their designs and claims distinct. It does not treat provider availability or judge qualification as evidence about the medical quality of generated answers or the general capability of any candidate model. [CITATION NEEDED: transparent reporting of missing or unevaluable outcomes in computational studies]

## 2. Research questions

The protocol defined three Western research questions. Their planned analyses and final estimability must be kept distinct.

| RQ | Question | Planned analysis | Final status |
|---|---|---|---|
| W-RQ1 | How do retrieval strategies affect gold-evidence retrieval within the frozen MediRAG-West pilot corpus? | Stage-A retrieval metrics and paired comparisons across R0–R3 | **Estimable** from the frozen Stage-A results |
| W-RQ2 | With the generator held fixed, how do retrieval strategies affect evidence coverage and unsupported-claim behavior in generated Western pilot answers? | Stage-B generation followed by semantic assessment | **Unavailable within v0.1.5; estimated separately in Follow-up v0.2** |
| W-RQ3 | How does the system behave when the frozen pilot corpus provides incomplete or insufficient evidence? | Semantic evaluation of insufficient-evidence cases | **Unavailable within v0.1.5; described separately in Follow-up v0.2** |

Unavailable semantic estimates within v0.1.5 are not null effects and do not indicate that retrieval had no effect. Stage B supplies generated answers but does not by itself answer W-RQ2 or W-RQ3. Follow-up v0.2 provides separate post-study semantic estimates under its own frozen single-evaluator design; it does not retroactively complete Stage C in v0.1.5.

## 3. System and study design

The software exposes separate TCM and Western evidence paths. The Western path is implemented through `WesternEvidenceAgent`, `WesternRetriever`, and the existing `RetrievalEngine` operating on an injected Western runtime corpus. Topic routing limits retrieval to cough, dyspepsia/digestive symptoms, headache, or constipation. Runtime checks reject evidence outside the Western corpus or routed topic.

Retrieved evidence carries chunk ID, source ID, rank, article title, section, PMCID, DOI where available, source URL, article-specific license, topic, and additional source metadata. Application-generated citation objects preserve these fields separately from generated prose. The generator receives bounded evidence excerpts and source-facing labels, while application-side provenance remains authoritative. This design supports traceability at the retrieved-item level; it is not equivalent to sentence-level verification of every generated claim.

The Western v1 runtime is a single Western evidence agent. It does not use the TCM specialist decomposition, and this manuscript makes no claim that it does. The formal experiment evaluates the Western pilot pathway only. Retrieval conditions were frozen before execution, and the generator was held fixed to SiliconFlow `Qwen/Qwen3-8B`, temperature 0, maximum output 256 tokens, 120-second timeout, one generation per cell, and retrieval top-k 4.

Repository evidence: `backend/western/agent.py`, `backend/western/retrieval.py`, `backend/western/schemas.py`, and `research/experiments/western_formal_v0_1/protocol_v0_1_2/`.

## 4. Western pilot corpus

The MediRAG-West PMC Open Access Pilot Corpus (`medirag-west-v0.1-pilot`) contains 16 systematic reviews available through PubMed Central Open Access. Four reviews were selected for each of the four pilot topics: cough, dyspepsia/digestive symptoms, headache, and constipation. Deterministic segmentation produced 271 chunks.

The source registry preserves article-level PMCID, DOI, source URL, journal or organization, publication year, source type, evidence category, license name, license text, license URL, retrieval timestamp, and review-status metadata. Chunk records preserve stable chunk and source identifiers, sections, topics, and Western-domain designation. The included articles carry multiple article-specific Creative Commons license variants; the registry, rather than a single package-wide license assumption, is the source for reuse conditions.

This is a deliberately small pilot corpus of systematic reviews. It is not a comprehensive representation of Western medical knowledge, clinical guidelines, primary research, or all evidence relevant to the four topics. Its bounded scope enables deterministic retrieval evaluation but constrains generalization.

Repository evidence: `research/corpus/west_v0_1/chunks.jsonl` and `research/corpus/west_v0_1/source_registry.json`.

## 5. Benchmark

The frozen MediRAG-West Pilot Benchmark v0.1 contains 48 cases, with 12 cases per topic. Its question-type distribution is 16 direct-evidence cases, 12 paraphrased-retrieval cases, 12 multi-source-synthesis cases, and eight difficult-or-insufficient cases. Answerability labels comprise 38 supported, four partially supported, and six insufficient cases.

The primary Stage-A headline population includes the 42 supported or partially supported cases with non-empty primary gold evidence. The six insufficient cases are outside the primary-gold headline recall and MRR denominators and are not silently scored as retrieval failures. This distinction separates absence of annotated primary gold from failure to retrieve existing primary gold.

Benchmark construction was AI-assisted. The manifest records AI-assisted draft annotation with secondary review by `GPT-5.6 Sol`, identifies the benchmark status as `draft_for_manual_review`, and sets both `human_verified` and `domain_expert_verified` to false. No clinician, physician, human expert, or independent domain expert adjudicated the benchmark. The benchmark can support this bounded pilot analysis but must not be described as expert-validated.

Repository evidence: `research/benchmarks/western_pilot_v0_1/benchmark.jsonl` and `benchmark_manifest.json`.

## 6. Retrieval conditions

All conditions returned a final top four and were executed in a balanced rotating order.

| Condition | Frozen definition |
|---|---|
| R0 | Local deterministic BM25-like lexical retrieval over all topic-filtered chunks; top 4 |
| R1 | Dense cosine-similarity retrieval using SiliconFlow `BAAI/bge-m3` over all topic-filtered chunks; top 4 |
| R2 | Lexical plus dense reciprocal-rank fusion using `1/(60 + lexical_rank) + 1/(60 + dense_rank)`; top 4 |
| R3 | R2 candidate generation at depth 12 followed by `BAAI/bge-reranker-v2-m3` reranking; return top 4 |

These definitions describe experimental conditions, not a ranking or recommendation. Formal-strict execution required the stated provider/model identities and prohibited local fallback for provider-dependent conditions.

## 7. Outcome measures and statistics

Stage-A headline outcomes were aggregate primary-gold chunk recall@4, aggregate primary-source recall@4, Hit@4, and MRR. “Aggregate” denotes a micro-aggregate: total retrieved primary-gold chunks divided by total primary-gold chunks, or total retrieved primary-gold sources divided by total primary-gold sources, across eligible cases. Hit@4 is binary per case and equals one when at least one primary-gold chunk appears in the top four. MRR is the mean reciprocal rank of the first retrieved primary-gold chunk; it is zero for an eligible case when none is retrieved.

Pairwise comparisons were prespecified for R1, R2, and R3 against R0. Each comparison used the successful-pair intersection and excluded technical failures without imputing zero. The effect measure was the mean within-case difference in primary-gold chunk recall. Percentile 95% confidence intervals used case-level paired bootstrap resampling with 10,000 replicates and seed `20260815`. Exact two-sided McNemar p-values used paired Hit@4 discordance. Stage A applied no multiplicity correction. P-values and intervals are reported descriptively rather than converted into categorical verdicts.

Retrieval latency was recorded but is not used for a clean speed comparison because cache state and execution order were confounded in the frozen run.

Repository evidence: `research/experiments/western_formal_v0_1/protocol_v0_1_2/metric_definitions.md`, `backend/western/formal_eval.py`, and the Stage-A publication tables.

## 8. Stage B generation

The original Stage-B attempt associated with run `western-formal-v0.1.2-stage-a-20260918-01` produced 192 terminal records: 106 completed answers and 86 technical failures. The failures formed an uninterrupted suffix beginning at human cell 107, with no subsequent success. On operational metadata, this epoch was classified as a provider/infrastructure outage. It remains preserved for audit, was not standard-finalized as the primary dataset, and was not pooled with the repeat. The adjudication did not inspect the semantic content of the 106 successful answers.

A prospectively governed full-matrix repeat used run ID `western-formal-v0.1.2-stage-b-r1-20260919-01`. It regenerated all 192 cells in frozen order and reused none of the original answers. The repeat completed 192/192 cells with zero technical failures and no retries, and it is the frozen primary Stage-B generation dataset. The fixed generator remained `Qwen/Qwen3-8B` with the original prompt and settings.

Completeness of generation is an execution result, not a semantic assessment. Stage B alone provides no estimate of answer correctness, evidence-point coverage, unsupported-claim behavior, safety, general system reliability beyond this execution, clinical value, or handling of incomplete evidence. Those outcomes required the planned Stage-C procedure.

Repository evidence: `stage_b_repeat_execution_v0_1_2_r1/incident.json` and the primary repeat’s `STAGE_B_FROZEN.md`, `stage_b_generation_metrics.json`, and `stage_b_run_manifest.json`.

## 9. Historical automated Stage C

Stage C in Western Formal Study v0.1.5 was designed to produce semantic assessments for W-RQ2 and W-RQ3 using a judge distinct from the generator. The original judge route did not yield a valid formal semantic dataset. Replacement procedures were introduced prospectively under versioned policies; historical incident and qualification artifacts remained immutable, and cross-wave pooling, selective completion or replay, and silent substitution of an unqualified judge were prohibited.

Free-only Wave 1 exhausted its frozen candidate sequence without selecting a Primary Judge. Its qualification outputs were operational/readiness observations rather than formal research data. Wave 2 used timestamped provider-catalog, pricing, and capability records for non-semantic discovery and deterministic offline eligibility processing. Its frozen eligible pool was empty (`complete_eligible_model_ids = []`, `pool_size = 0`, `selected_candidates = []`). Under the stopping rule, automated Stage C terminated with no Primary Judge and no formal run; Wave 3, automatic paid fallback, and in-study judge-interface redesign were prohibited.

This history documents operational governance under the study’s provider, interface, and zero-cost constraints. It is not a comparison of individual judge-model quality. W-RQ2 and W-RQ3 semantic estimates remain unavailable within Western Formal Study v0.1.5.

Repository evidence: `stage_c_judge_wave2_free_v0_1_5/wave1-exhaustion.json` and `stage_c_judge_wave2_free_v0_1_5/{POLICY.md,candidate-pool-freeze.json,wave2-exhaustion.json}`.

## 10. Separate Western Semantic Follow-up v0.2 — methods

Western Semantic Follow-up v0.2 was created after the historical automated Stage C had terminated. It is a separate post-study evaluation, not a resumption or completion of Stage C. The follow-up reused the frozen benchmark, Stage-A retrieval outputs, and all 192 unchanged answers from the frozen primary Stage-B repeat.

The 192 answer-condition cells were assigned opaque IDs. Retrieval-condition identity and original experiment IDs were concealed from GPT-5.6 Sol during annotation, and the blind key was withheld until annotation was complete. The evaluator saw the question, answerability designation, frozen expected evidence points, up to four retrieved evidence passages, and generated answer. The rubric instructed the evaluator to use only those materials and not outside medical knowledge. Because answer and evidence content could still indirectly signal retrieval characteristics, this procedure establishes condition-label concealment rather than perfect perceptual blinding.

For answerable cases, each expected point was labeled `covered`, `partially_covered`, `not_covered`, or `contradicted`. Derived outcomes were `full_coverage_score` (`n_fully_covered / n_expected_points`) and `partial_credit_coverage_score` (`[n_fully_covered + 0.5 × n_partially_covered] / n_expected_points`). The evaluator also recorded `unsupported_claim_present`, `unsupported_claim_count`, and `contradiction_present`. For insufficient-evidence cases, `insufficient_handling` used four frozen labels: `appropriate_abstention`, `appropriate_bounded_insufficiency`, `substantive_answer_without_insufficiency_acknowledgement`, and `overclaim_beyond_pilot_evidence`.

W-RQ2 included the 42 supported or partially supported cases, yielding 168 cells. Full coverage was the primary endpoint and was summarized as the case-level macro mean within each condition. R1, R2, and R3 were paired with R0 by case. Mean paired differences used 10,000 case-level bootstrap resamples with replacement, seed `20260815`, and percentile 95% confidence intervals. Unsupported-claim presence used exact two-sided McNemar tests on paired discordances, with Holm adjustment across the three comparisons. W-RQ3 included the six insufficient-evidence cases, 24 cells, and was descriptive only. No composite score or W-RQ3 hypothesis test was created.

The follow-up is an evidence-grounded semantic assessment under one GPT-5.6 Sol evaluator. It is not human evaluation, clinician evaluation, or expert clinical validation.

Repository evidence: `research/experiments/western_semantic_followup_v0_2/{FROZEN.md,STAGE_C2_RESULTS_v0.2.md,stage_c2_analysis_manifest.json}` and the frozen tables in `tables/`.

## 11. Results

### 11.1 Corpus and benchmark

The frozen evidence base comprised 16 PMC Open Access systematic reviews and 271 deterministic chunks across four topic groups. The benchmark contained 48 cases, including 42 answerable cases used for W-RQ1 and W-RQ2 and six insufficient-evidence cases used for W-RQ3.

### 11.2 Stage-A retrieval experiment

All 192 Stage-A retrieval cells completed with zero technical failures. Table 1 reports the headline metrics over the 42 eligible cases.

**Table 1. Frozen Stage-A headline retrieval metrics**

| Condition | Aggregate primary-gold chunk recall@4 | Aggregate primary-source recall@4 | Hit@4 | MRR |
|---|---:|---:|---:|---:|
| R0 | 0.428571 | 0.890909 | 0.595238 | 0.450397 |
| R1 | 0.634921 | 0.890909 | 0.785714 | 0.605159 |
| R2 | 0.539683 | 0.890909 | 0.738095 | 0.573413 |
| R3 | 0.523810 | 0.836364 | 0.690476 | 0.581349 |

R1 measured higher on the frozen headline retrieval metrics in this pilot. Paired primary-gold chunk-recall comparisons used `n = 42` pairs. R1 − R0 had a mean difference of +0.206349 (95% bootstrap CI [0.083333, 0.333333]) and an exact two-sided McNemar p-value of 0.0385742 for paired Hit@4 discordance. R2 − R0 was +0.0952381 (95% CI [0.0119048, 0.190476]; p = 0.03125), and R3 − R0 was +0.107143 (95% CI [0.0119048, 0.218254]; p = 0.2890625). The p-values are descriptive and are not binary decision labels.

Existing publication figures:

- [Figure 1: Stage-A headline retrieval metrics](../../experiments/western_formal_v0_1/stage_a_publication_v0_1_5/figures/stage_a_headline_metrics.png)
- [Figure 2: Paired primary-gold chunk-recall differences](../../experiments/western_formal_v0_1/stage_a_publication_v0_1_5/figures/stage_a_paired_recall_difference.png)

### 11.3 Stage-B generation execution

The original Stage-B outage attempt remains preserved and excluded from the primary dataset. The prospectively governed full-matrix repeat generated 192/192 answers with the fixed `Qwen/Qwen3-8B` model, zero technical failures, and no reuse of the original attempt’s answers. This establishes a complete generation dataset, not semantic quality.

### 11.4 Historical automated Stage-C termination

Automated Stage C in Western Formal Study v0.1.5 terminated prospectively without a qualified Primary Judge or formal semantic run. Accordingly, W-RQ2 and W-RQ3 remain unavailable within v0.1.5. Stage A and the frozen primary Stage-B dataset remain valid.

### 11.5 Separate Western Semantic Follow-up v0.2

The later follow-up evaluated all 192 frozen Stage-B answers: 168 answerable-case cells for W-RQ2 and 24 insufficient-evidence cells for W-RQ3. There were no missing semantic judgments. These estimates belong to Follow-up v0.2 and do not retroactively alter the v0.1.5 Stage-C outcome.

### 11.6 W-RQ2 full evidence coverage

**Table 2. Full-coverage score by retrieval condition**

| Condition | n | Mean | SD | Median | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| R0 | 42 | 0.543651 | 0.453919 | 0.500000 | 0 | 1 |
| R1 | 42 | 0.805556 | 0.335191 | 1.000000 | 0 | 1 |
| R2 | 42 | 0.626984 | 0.430556 | 1.000000 | 0 | 1 |
| R3 | 42 | 0.710317 | 0.387927 | 1.000000 | 0 | 1 |

Under the blinded evidence-grounded follow-up evaluation, R1 had a higher observed mean full-coverage score than R0. The observed paired mean differences were 0.261905 for R1 − R0 (95% bootstrap CI [0.142857, 0.392857]), 0.083333 for R2 − R0 ([0.000000, 0.178571]), and 0.166667 for R3 − R0 ([0.059524, 0.285714]). These estimates and intervals are descriptive; no binary confidence-interval verdict was applied.

Mean partial-credit coverage was 0.686508, 0.863095, 0.738095, and 0.785714 for R0–R3. Paired mean differences versus R0 were 0.176587 for R1 (95% bootstrap CI [0.087302, 0.277778]), 0.051587 for R2 ([-0.015873, 0.123016]), and 0.099206 for R3 ([0.021825, 0.188492]).

Each condition represented 58 expected evidence points. Covered/partially covered/not covered/contradicted counts were 31/16/8/3 for R0, 44/7/6/1 for R1, 35/13/9/1 for R2, and 38/10/10/0 for R3. These are descriptive counts; individual evidence points were not treated as statistically independent observations.

### 11.7 W-RQ2 unsupported-claim and contradiction behavior

Unsupported-claim presence was 9/42 (0.214286) under R0, 5/42 (0.119048) under R1, and 3/42 (0.071429) under both R2 and R3. It was therefore numerically lower under R1, R2, and R3 than under R0 in this follow-up. Exact two-sided McNemar raw/Holm-adjusted p-values were 0.343750/0.343750 for R1 versus R0, 0.031250/0.093750 for R2 versus R0, and 0.0703125/0.140625 for R3 versus R0. These values are reported without a binary verdict.

Mean unsupported-claim counts were 0.261905, 0.119048, 0.095238, and 0.095238 for R0–R3. Paired mean count differences versus R0 were −0.142857 for R1 (95% bootstrap CI [−0.309524, 0.023810]), −0.166667 for R2 ([−0.285714, −0.071429]), and −0.166667 for R3 ([−0.333333, 0.000000]).

Contradiction presence was 5/42 under R0, 1/42 under R1, 2/42 under R2, and 1/42 under R3. Expected-point contradiction totals were 3, 1, 1, and 0, respectively. These outcomes are descriptive and do not establish clinical safety.

### 11.8 W-RQ3 insufficient-evidence handling

Each condition contributed six insufficient-evidence cases. R0 contained one `appropriate_abstention` and five `appropriate_bounded_insufficiency` labels. R1, R2, and R3 each contained five `appropriate_bounded_insufficiency` labels and one `overclaim_beyond_pilot_evidence` label. No condition contained `substantive_answer_without_insufficiency_acknowledgement`.

W-RQ3 was not subjected to hypothesis testing or collapsed into a binary or composite score. The labels were predominantly `appropriate_bounded_insufficiency`, while isolated overclaim behavior remained under R1, R2, and R3. The small descriptive sample does not support a condition ranking or clinical-safety inference.

## 12. Discussion

The frozen pilot produced measurable retrieval differences across R0–R3. R1 measured higher on the headline Stage-A retrieval metrics in this corpus-benchmark configuration. The separate semantic follow-up also observed condition-level differences in evidence coverage. R1 had the highest observed mean full-coverage score, and its paired difference versus R0 was positive under the frozen bootstrap procedure. The direction of the R1 retrieval and semantic-coverage observations was descriptively aligned, but this pilot does not establish a causal relationship between retrieval performance and generated-answer quality.

Unsupported-claim presence was numerically lower under R1, R2, and R3 than under R0. Contradiction presence was also numerically lower under those conditions. The exact McNemar and Holm-adjusted p-values are retained as descriptive outputs rather than converted into categorical findings. Unsupported-claim annotations are rubric-based judgments against supplied evidence and should not be interpreted as a validated general hallucination measure or as clinical factuality. [CITATION NEEDED: relationship between retrieval metrics and downstream RAG answer quality]

W-RQ3 labels were predominantly `appropriate_bounded_insufficiency`, but isolated `overclaim_beyond_pilot_evidence` labels occurred under R1, R2, and R3. With only six cases per condition and no inferential test, these observations neither rank conditions nor establish safety. They instead show why retrieval metrics alone should not substitute for direct semantic assessment of incomplete-evidence behavior.

The historical Stage-C stopping process remains methodologically informative in a narrower sense. Prospective eligibility criteria, immutable incident records, prohibition of cross-epoch pooling, and an explicit terminal rule explain why v0.1.5 has no formal automated Stage-C dataset. Follow-up v0.2 addresses semantic behavior through a separate design rather than rewriting that outcome. [CITATION NEEDED: governance and reproducibility of automated evaluators]

The follow-up’s single-evaluator design limits interpretation. GPT-5.6 Sol applied the frozen rubric without a second judge, human adjudicator, or clinician. No inter-rater reliability or judge-family robustness estimate exists, and retrieval characteristics might have been indirectly apparent from answer or evidence content despite condition-label concealment. The findings are therefore evaluator- and rubric-dependent. [CITATION NEEDED: reliability and evaluator dependence of LLM-as-judge semantic assessment]

## 13. Limitations

This study has several material limitations:

1. The evidence base contains only 16 systematic reviews and 271 deterministic chunks.
2. The benchmark contains 48 cases across four topic groups and is tailored to the pilot corpus.
3. The generator was fixed to `Qwen/Qwen3-8B`; generator-family variability was not estimated.
4. Follow-up v0.2 used one semantic evaluator, GPT-5.6 Sol.
5. No human, clinician, physician, or independent expert adjudicated the semantic labels.
6. No inter-rater reliability estimate is available.
7. No judge-family robustness assessment is available.
8. Retrieval-condition identity was concealed, but answer and evidence content might indirectly signal retrieval quality or other condition characteristics.
9. Semantic outcomes depend on the frozen rubric and this evaluator’s application of it.
10. Evidence-grounded semantic evaluation does not establish clinical correctness or clinical safety.
11. `unsupported_claim_present` is a rubric-defined annotation and is not equivalent to a validated general hallucination metric.
12. W-RQ3 includes only six cases per condition and is descriptive.
13. The source set is systematic-review based and is not representative of all clinical evidence, including primary studies and guidelines.
14. The design does not support causal inference between retrieval metrics and generated-answer quality.
15. Retrieval latency was confounded by cache state and execution order, and all findings should remain bounded to this frozen pilot.

## 14. Future work

Future work may expand the Western corpus and add medical domains while preserving article- and chunk-level provenance. The benchmark should undergo independent human and clinician adjudication before broader claims are attempted. Retrieval findings could be independently replicated and tested under larger corpora, alternative retrieval configurations, and prespecified generator-family sensitivity analyses.

For semantic evaluation, future studies may prequalify automated judges before formal generation, use prospectively defined multi-judge robustness analyses, estimate inter-rater reliability, and include independent human or clinician evaluation where resources permit. Such work should preserve clear separation between operational qualification data and formal research outcomes. Explicit evaluation of incomplete-evidence behavior remains important, particularly for abstention, bounded responses, and unsupported elaboration. These are prospective directions, not results of the present study.

## 15. Conclusion

The Western evidence pathway produced a complete and reproducible retrieval evaluation for W-RQ1 and a frozen 192-answer Stage-B generation dataset. R1 measured higher on the headline retrieval metrics in this frozen pilot. Automated semantic Stage C in Western Formal Study v0.1.5 terminated under its prospectively governed qualification and stopping procedure, leaving W-RQ2 and W-RQ3 unavailable within that historical study version.

The separate Western Semantic Follow-up v0.2 subsequently observed differences in evidence-grounded semantic coverage and unsupported-claim behavior across retrieval conditions. Within this frozen 16-review, 48-case pilot and under a single blinded GPT-5.6 Sol evidence-grounded evaluator, semantic evidence coverage and unsupported-claim behavior differed descriptively across retrieval conditions. These pilot-scale findings do not establish clinical correctness, clinical safety, or a causal relationship between retrieval performance and generated-answer quality.

## Drafting evidence note

The principal repository anchors for this skeleton are:

- `research/experiments/western_formal_v0_1/WESTERN_FORMAL_STUDY_STATUS_v0.1.5.md`
- `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/`
- `research/experiments/western_formal_v0_1/protocol_v0_1_2/`
- `research/experiments/western_formal_v0_1/stage_b_repeat_execution_v0_1_2_r1/`
- `research/experiments/western_formal_v0_1/runs/western-formal-v0.1.2-stage-b-r1-20260919-01/`
- `research/experiments/western_formal_v0_1/stage_c_judge_wave2_free_v0_1_5/`
- `research/experiments/western_semantic_followup_v0_2/FROZEN.md`
- `research/experiments/western_semantic_followup_v0_2/STAGE_C2_RESULTS_v0.2.md`
- `research/experiments/western_semantic_followup_v0_2/tables/`

External scholarship has not been fabricated. Bracketed citation placeholders identify claims that require later literature review.
