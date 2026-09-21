# Provisional title

**Corpus-Bounded Western Evidence Retrieval in MediRAG: A Reproducible Pilot Evaluation and Governance of Automated Semantic Assessment**

> **Draft status:** Phase-II manuscript skeleton for scientific review, derived from the Western Formal Study v0.1.5. This document is separate from the frozen earlier paper/report. Repository artifacts, rather than this draft, remain authoritative.

## Abstract

**Background:** Retrieval-augmented generation (RAG) depends on the evidence made available to generation as well as on the generator itself. Medical information systems therefore require explicit control of corpus scope, evidence provenance, and evaluation boundaries. [CITATION NEEDED: retrieval quality in medical RAG] [CITATION NEEDED: provenance and traceability for evidence-grounded medical information systems]

**Objective:** This Phase-II study examined a separate Western-evidence extension of MediRAG. It asked how four frozen retrieval conditions affected gold-evidence retrieval in a bounded pilot corpus and planned downstream evaluation of fixed-generator answers and incomplete-evidence behavior.

**Methods:** The Western pilot corpus comprised 16 PubMed Central Open Access systematic reviews, four in each of four topic domains—cough, dyspepsia/digestive symptoms, headache, and constipation—segmented into 271 deterministic chunks. The frozen benchmark contained 48 cases. Four retrieval conditions were evaluated: lexical retrieval (R0), dense retrieval (R1), lexical–dense reciprocal-rank fusion (R2), and fusion followed by reranking (R3), each returning four chunks. Headline Stage-A retrieval metrics used the 42 supported or partially supported cases with non-empty primary gold evidence. Generation used the fixed `Qwen/Qwen3-8B` model. Automated semantic judging was governed through prospectively frozen qualification and stopping procedures.

**Results:** Stage A completed all 192 retrieval cells without technical failure. Aggregate primary-gold chunk recall@4 was 0.428571, 0.634921, 0.539683, and 0.523810 for R0–R3, respectively; Hit@4 was 0.595238, 0.785714, 0.738095, and 0.690476. R1 measured higher on the headline retrieval metrics in this frozen pilot. A complete primary Stage-B generation dataset was obtained for 192/192 cells after a separately preserved provider-outage attempt. Stage C automated semantic evaluation terminated prospectively without a qualified Primary Judge. Consequently, W-RQ1 is estimable, whereas W-RQ2 and W-RQ3 semantic estimates are unavailable in this study version.

**Limitations and conclusion:** The corpus, topics, benchmark, generator, and provider environment were narrowly bounded; benchmark drafting and secondary review were AI-assisted, without clinician or human-expert adjudication. Retrieval latency was confounded by cache state and execution order. The study provides a complete, reproducible pilot retrieval evaluation, but it does not provide clinical validation or semantic estimates of answer quality, evidence coverage, unsupported claims, or incomplete-evidence behavior.

## 1. Introduction

RAG systems combine retrieval from an external corpus with language-model generation. Their behavior is shaped by which documents are eligible for retrieval, how evidence is ranked, and how retrieved material is passed to generation—not only by the generator. In medical information settings, weak or opaque retrieval can limit the evidence available to an otherwise fixed generator, while incomplete provenance can make outputs difficult to audit. [CITATION NEEDED: retrieval quality in medical RAG] [CITATION NEEDED: provenance and traceability for evidence-grounded medical information systems]

MediRAG Phase II extends the project with a Western-evidence pathway that is separate from the existing traditional Chinese medicine (TCM) pathway. The separation is architectural and evidentiary: the Western runtime loads a dedicated Western pilot corpus, routes questions to one of four Western topic domains, retrieves only from that injected corpus, and exposes source and chunk provenance. The TCM runtime and its specialist-oriented research workflow are not treated as interchangeable with the Western pathway. This separation supports corpus-bounded evaluation without implying that either evidence tradition is comprehensive or that the two pathways were compared clinically.

The formal Western pilot focused on retrieval and controlled evidence-grounded generation. Stage A compared four frozen retrieval conditions. Stage B generated one answer for each benchmark-condition cell with a fixed generator. Stage C was intended to evaluate evidence coverage, unsupported-claim behavior, and incomplete-evidence responses with a separately qualified automated judge. The qualification process ultimately reached its prospectively specified stopping rule without selecting a Primary Judge. The study therefore has a complete retrieval result for W-RQ1 and a complete generation dataset, but no formal semantic estimates for W-RQ2 or W-RQ3.

This manuscript skeleton reports what the frozen artifacts support and makes unavailable analyses explicit. It does not treat provider availability, judge qualification, or the absence of a semantic dataset as evidence about the medical quality of generated answers or the general capability of any candidate model. [CITATION NEEDED: transparent reporting of missing or unevaluable outcomes in computational studies]

## 2. Research questions

The protocol defined three Western research questions. Their planned analyses and final estimability must be kept distinct.

| RQ | Question | Planned analysis | Final status |
|---|---|---|---|
| W-RQ1 | How do retrieval strategies affect gold-evidence retrieval within the frozen MediRAG-West pilot corpus? | Stage-A retrieval metrics and paired comparisons across R0–R3 | **Estimable** from the frozen Stage-A results |
| W-RQ2 | With the generator held fixed, how do retrieval strategies affect evidence coverage and unsupported-claim behavior in generated Western pilot answers? | Stage-B generation followed by qualified Stage-C semantic judging | **Semantic estimate unavailable** in this study version |
| W-RQ3 | How does the system behave when the frozen pilot corpus provides incomplete or insufficient evidence? | Stage-C semantic evaluation of partial and insufficient cases | **Semantic estimate unavailable** in this study version |

Unavailable semantic estimates are not null effects and do not indicate that retrieval had no effect. Stage B supplies generated answers but, without the prespecified semantic assessment, does not by itself answer W-RQ2 or W-RQ3.

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

## 9. Stage C automated semantic evaluation

Stage C was designed to produce semantic assessments for W-RQ2 and W-RQ3 using a judge distinct from the generator. The original judge route did not yield a valid formal semantic dataset. Replacement procedures were introduced prospectively under versioned policies; historical incident and qualification artifacts remained immutable, and cross-wave pooling, selective completion or replay, and silent substitution of an unqualified judge were prohibited.

Free-only Wave 1 exhausted its frozen candidate sequence without selecting a Primary Judge. Its qualification outputs were operational/readiness observations, not formal research data. They are not interpreted as comparative model-quality evidence. Wave 2 then used timestamped provider-catalog, pricing, and capability records for non-semantic discovery and deterministic offline eligibility processing. It made no semantic or generation probes. The final frozen Wave-2 eligible pool was empty (`complete_eligible_model_ids = []`, `pool_size = 0`, `selected_candidates = []`).

Under the frozen stopping rule, automated semantic Stage C terminated. The final state is: `primary_judge_selected = false`; `formal_stage_c_run_created = false`; Wave 3 prohibited; automatic paid fallback prohibited; and in-study judge-interface redesign prohibited. There was no post-hoc pooling or unqualified replacement.

This history documents operational governance and reproducibility under the study’s provider, interface, and zero-cost constraints. It is not an experiment comparing the quality of individual judge models. The absence of a qualified Primary Judge means that no formal Stage-C semantic dataset exists and no W-RQ2 or W-RQ3 semantic estimate is available.

Repository evidence: `stage_c_judge_replacement_policy_v2_free/wave1-exhaustion.json` and `stage_c_judge_wave2_free_v0_1_5/{POLICY.md,candidate-pool-freeze.json,wave2-exhaustion.json}`.

## 10. Results — W-RQ1

All 192 Stage-A retrieval cells completed with zero technical failures. Table 1 reports the four headline metrics over the 42 eligible cases.

**Table 1. Frozen Stage-A headline retrieval metrics**

| Condition | Aggregate primary-gold chunk recall@4 | Aggregate primary-source recall@4 | Hit@4 | MRR |
|---|---:|---:|---:|---:|
| R0 | 0.428571 | 0.890909 | 0.595238 | 0.450397 |
| R1 | 0.634921 | 0.890909 | 0.785714 | 0.605159 |
| R2 | 0.539683 | 0.890909 | 0.738095 | 0.573413 |
| R3 | 0.523810 | 0.836364 | 0.690476 | 0.581349 |

R1 measured higher on the headline retrieval metrics in this frozen pilot. This is a descriptive observation within the frozen corpus and benchmark, not a general retrieval-method conclusion.

Paired primary-gold chunk-recall comparisons used `n = 42` successful pairs in every contrast. R1 − R0 had a mean difference of +0.206349 (95% bootstrap CI [0.083333, 0.333333]); the exact two-sided McNemar p-value for paired Hit@4 discordance was 0.0385742. R2 − R0 had a mean difference of +0.0952381 (95% CI [0.0119048, 0.190476]) and McNemar p = 0.03125. R3 − R0 had a mean difference of +0.107143 (95% CI [0.0119048, 0.218254]) and McNemar p = 0.2890625. These p-values are descriptive and are not used as binary decision labels.

Existing publication figures:

- [Figure 1: Stage-A headline retrieval metrics](../../experiments/western_formal_v0_1/stage_a_publication_v0_1_5/figures/stage_a_headline_metrics.png)
- [Figure 2: Paired primary-gold chunk-recall differences](../../experiments/western_formal_v0_1/stage_a_publication_v0_1_5/figures/stage_a_paired_recall_difference.png)

Authoritative derived results: `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/`.

## 11. Results — execution and research-question availability

Execution status is reported separately from retrieval findings and semantic outcomes.

| Component | Final execution state | Scientific availability |
|---|---|---|
| Stage A | Complete and frozen; 192/192 retrieval cells | W-RQ1 estimable |
| Stage B | Complete and frozen primary repeat; 192/192 generations | Generation dataset available; no standalone semantic conclusion |
| Stage C | Prospectively terminated without a qualified Primary Judge; no formal run created | W-RQ2 semantic estimate unavailable; W-RQ3 semantic estimate unavailable |

The unavailability of W-RQ2 and W-RQ3 is missing evaluation, not an estimated zero effect. Stage A and the primary Stage-B dataset remain valid despite termination of automated semantic Stage C.

## 12. Discussion

The frozen pilot produced different observed retrieval values across R0–R3. R1 had higher measured headline values in this corpus-benchmark configuration. The hybrid R2 condition and reranked R3 condition did not automatically yield higher measured headline values than R1 in this specific pilot. These observations motivate investigation of retrieval design under larger corpora, additional domains, and independent replication; they do not establish that dense retrieval is generally preferable or that reranking is generally less effective.

The retrieval results also cannot be carried forward into claims about generated-answer quality. Higher gold-evidence retrieval in a bounded benchmark may change what evidence is available to a generator, but W-RQ2 required formal assessment of evidence coverage and unsupported claims, while W-RQ3 required formal assessment of incomplete-evidence behavior. Because Stage C did not produce a valid semantic dataset, this study does not estimate improved answer quality, reduced hallucination, clinical safety, diagnostic correctness, or clinical utility. [CITATION NEEDED: relationship between retrieval metrics and downstream RAG answer quality]

The Stage-C stopping process is methodologically informative in a narrower sense. Prospective eligibility criteria, immutable incident records, prohibition of cross-epoch pooling, and an explicit terminal rule make clear why planned semantic outcomes are absent. Reporting this boundary prevents operational events from being recast as model-quality findings or silently resolved through post-hoc substitution. Future evaluations should qualify judge resources and access conditions before formal generation where feasible. [CITATION NEEDED: governance and reproducibility of automated evaluators]

The study’s strongest supported contribution is therefore a transparent corpus-bounded retrieval evaluation with preserved provenance and reproducibility anchors. Its scope is deliberately narrower than clinical evaluation. Any later manuscript expansion should retain that distinction.

## 13. Limitations

This study has several material limitations:

1. The evidence base contains only 16 source reviews, four topic domains, and 271 deterministic chunks.
2. The 48-case benchmark and `n = 42` headline Stage-A denominator are tailored to the pilot corpus.
3. Benchmark drafting and secondary review were AI-assisted. No clinician, physician, human expert, or independent domain expert completed benchmark adjudication.
4. The generator was fixed to `Qwen/Qwen3-8B`; generator-family variability was not estimated.
5. Provider availability, account access, cost restrictions, and interface compatibility constrained automated judge selection.
6. No valid formal Stage-C semantic dataset was created; W-RQ2 and W-RQ3 semantic estimates are unavailable.
7. Stage-B completion does not establish evidence coverage, unsupported-claim behavior, handling of incomplete evidence, or medical correctness.
8. Retrieval latency was confounded by cache state and execution order, preventing a clean speed comparison.
9. The observed retrieval results are pilot-specific and are not general model rankings.
10. The study includes no clinical validation and does not measure diagnostic or treatment utility.

## 14. Future work

Future work may expand the Western corpus and add medical domains while preserving article- and chunk-level provenance. The benchmark should undergo independent human and clinician adjudication before broader claims are attempted. Retrieval findings could be independently replicated and tested under larger corpora, alternative retrieval configurations, and prespecified generator-family sensitivity analyses.

For semantic evaluation, future studies may prequalify automated judges before formal generation, use prospectively defined dual-judge robustness analyses, or use independent human evaluation where resources permit. Such work should preserve clear separation between operational qualification data and formal research outcomes. Explicit evaluation of incomplete-evidence behavior remains important, particularly for abstention, bounded responses, and unsupported elaboration. These are prospective directions, not results of the present study.

## 15. Conclusion

The Western pilot produced a complete and reproducible retrieval evaluation for W-RQ1. R1 measured higher on the headline retrieval metrics in this frozen pilot. The fixed-generator primary Stage-B dataset was completed for 192/192 cells. Automated semantic Stage C could not be completed under the prospectively governed qualification and stopping procedure; therefore, W-RQ2 and W-RQ3 semantic estimates remain unavailable. The findings are limited to the frozen corpus and benchmark and do not establish clinical improvement.

## Drafting evidence note

The principal repository anchors for this skeleton are:

- `research/experiments/western_formal_v0_1/WESTERN_FORMAL_STUDY_STATUS_v0.1.5.md`
- `research/experiments/western_formal_v0_1/stage_a_publication_v0_1_5/`
- `research/experiments/western_formal_v0_1/protocol_v0_1_2/`
- `research/experiments/western_formal_v0_1/stage_b_repeat_execution_v0_1_2_r1/`
- `research/experiments/western_formal_v0_1/runs/western-formal-v0.1.2-stage-b-r1-20260919-01/`
- `research/experiments/western_formal_v0_1/stage_c_judge_wave2_free_v0_1_5/`

External scholarship has not been fabricated. Bracketed citation placeholders identify claims that require later literature review.
