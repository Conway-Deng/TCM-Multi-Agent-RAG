# MediRAG-West Pilot Benchmark v0.1 — Frozen Research Checkpoint

## Freeze identity

- Benchmark name: MediRAG-West Pilot Benchmark v0.1
- Benchmark version: `western-pilot-v0.1`
- Freeze date/time: `2026-09-18T15:50:36+08:00`
- Freeze Git branch: `feature/medirag-west-v0.1`
- Western runtime checkpoint commit: `e6b02f6e37534008427cb18cd06ce7f086153103`
- Benchmark SHA256: `29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6`
- Benchmark manifest SHA256: `bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae`
- Western corpus chunks SHA256: `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b`
- Western source registry SHA256: `722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703`

## Frozen distribution

- Cases: 48
- Gold-source coverage: 16/16 Western pilot sources (100%)
- Distinct primary gold chunks: 47
- Distinct primary plus secondary gold chunks: 58

### Topics

- `cough`: 12
- `dyspepsia_digestive_symptoms`: 12
- `headache`: 12
- `constipation`: 12

### Question types

- `direct_evidence`: 16
- `paraphrased_retrieval`: 12
- `multi_source_synthesis`: 12
- `difficult_or_insufficient`: 8

### Answerability

- `supported`: 38
- `partially_supported`: 4
- `insufficient`: 6

## Review methodology

The benchmark is an AI-assisted draft whose 48 cases were subsequently reviewed by a secondary AI model against the frozen pilot-corpus review packet. The prescribed adjudications were applied mechanically and are recorded in `reports/secondary_model_adjudication.json`.

- `generation_policy=ai_assisted_draft_secondary_model_reviewed`
- `secondary_reviewer_type=ai_model`
- `secondary_reviewer_model=GPT-5.6 Sol`
- `review_basis=frozen_pilot_corpus_review_packet`
- `human_verified=false`
- `domain_expert_verified=false`

This process is not clinician review, physician validation, medical-expert validation, or human gold annotation.

## Scientific scope limitation

MediRAG-West Pilot Benchmark v0.1 evaluates performance only within the frozen 16-source, 271-chunk MediRAG-West pilot corpus. It does not evaluate or claim coverage of general Western medicine knowledge, comprehensive medical correctness, diagnosis quality, treatment quality, clinical safety, physician performance, or comprehensive guideline adherence.

## Freeze and versioning policy

After the freeze commit, `benchmark.jsonl` and `benchmark_manifest.json` are immutable for v0.1. Any later scientific change to a question, answerability label, question type, gold source, gold chunk, or expected evidence point requires a new benchmark version, such as `western_pilot_v0_2`. v0.1 must not be silently modified after freeze.

Diagnostic and run-output artifacts may be added later without modifying the frozen benchmark content. Existing R0 values remain labeled **DRAFT DIAGNOSTIC — NOT FORMAL PAPER RESULTS**. Freezing this benchmark does not convert those diagnostics into formal results.
