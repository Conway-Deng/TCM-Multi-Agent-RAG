# MediRAG-West Pilot Benchmark v0.1 — Draft Annotation Guide

## Scope

This draft benchmark is restricted to the frozen MediRAG-West pilot corpus: 16 reusable PMC Open Access systematic-review sources and 271 chunks across cough, dyspepsia/digestive symptoms, headache/migraine, and constipation.

It measures retrieval within that corpus and prepares later evaluation of evidence support, abstention, provenance integrity, reliability, and latency. It does not measure comprehensive Western medical knowledge, clinical correctness, diagnosis, treatment quality, safety, guideline adherence, or physician performance.

## Construction policy

- Questions and gold annotations are an AI-assisted draft grounded in deterministic inspection of local chunk text and bibliographic metadata.
- A secondary AI model (GPT-5.6 Sol) reviewed the frozen pilot-corpus review packet; its prescribed adjudications were applied mechanically and recorded in `reports/secondary_model_adjudication.json`.
- This process is not human clinical review or domain-expert verification. Human and domain-expert verification remain false and pending.
- Questions must be educational, must not request personalized diagnosis, prescribing, or dosing, and must not expose internal or bibliographic identifiers.
- Retrieval output may help locate candidates, but it never defines gold evidence.
- Questions are not rewritten after observing R0 results merely to improve retrieval metrics.

## Required distribution

Each canonical topic has 12 cases: four `direct_evidence`, three `paraphrased_retrieval`, three `multi_source_synthesis`, and two `difficult_or_insufficient`. No mandatory easy/medium/hard quota exists. The optional `difficulty` field is descriptive only.

## Question types

- `direct_evidence`: one or a small number of chunks directly addresses the information need, without copying titles or source sentences.
- `paraphrased_retrieval`: evidence exists, but the question uses meaningfully different wording to test lexical robustness.
- `multi_source_synthesis`: primary support normally spans at least two source records or clearly distinct evidence contexts.
- `difficult_or_insufficient`: the question remains in-topic but the pilot provides incomplete evidence or cannot support a complete answer.

## Answerability

- `supported`: primary gold evidence supports the requested information within the pilot's scope.
- `partially_supported`: gold evidence supports only part of the information need or leaves a material uncertainty.
- `insufficient`: the pilot cannot support a complete answer. Notes must say “Insufficient within the current pilot corpus” and must never imply that no medical evidence exists elsewhere.

## Gold evidence

- `gold_source_ids` identifies primary source records.
- `gold_chunk_ids` contains required or strongly relevant primary chunks.
- `optional_secondary_chunk_ids` contains genuinely useful but non-required context.
- Every declared chunk must exist, match its source, belong to the case topic, and support an expected evidence point or a documented insufficiency boundary.
- Gold sets are kept small and are not expanded to improve Recall@4.

## Expected evidence points

Evidence points are short semantic descriptions, not generated answers. They remain close to source meaning, preserve uncertainty, avoid individualized recommendations, and do not add causal claims unsupported by the source.

## Validation and leakage review

Hard validation covers size, distribution, uniqueness, enums, referential integrity, topic consistency, supported-case evidence, evidence-point support, and corpus-bounded insufficiency language. Deterministic leakage checks examine identifiers, article-title overlap, contiguous source-text overlap, and section-heading overlap. Flags require review and are not silently repaired.

## Retrieval diagnostics

The current unchanged R0 lexical retriever is run with `top_k=4`. Recall@4, source recall, MRR, and Hit@4 are labelled **DRAFT DIAGNOSTIC — NOT FORMAL PAPER RESULTS**. These diagnostics must not be used to tune RetrievalEngine or rewrite questions to improve the scores.
