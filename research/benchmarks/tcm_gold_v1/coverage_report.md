# TCM Gold Benchmark v1 Coverage Report

Status: `DRAFT_SOURCE_GROUNDED`

## Frozen corpus

- Path: `research/corpus/tcm_v1/chunks.jsonl`
- Version: `tcm-research-corpus-v1`
- Chunks: 4,461
- SHA-256: `316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9`
- Categories: herbal_medicine=4,228; syndrome_differentiation=233; no other active categories.

## Benchmark distribution

- Total questions: 50
- Herbal: 30
- Syndrome: 12
- Multi-target: 8
- Easy: 20
- Medium: 20
- Hard: 10
- Atomic gold facts: 112

## Validation

- Unique question IDs and questions: PASS
- Every gold fact has preferred evidence: PASS
- Every evidence ID exists in Corpus v1: PASS
- Legacy 16-entry IDs: none
- Multi-target target coverage: PASS
- Required regressions included: Red Ginseng control, liver-yang routing (`tcmv1-0246978770d8f37c619dd636`), and Red Ginseng + kidney-yang multi-target (`tcmv1-010f829f0c703d4a98d24324` / `tcmv1-01b61fa93d54e8bdd1c408f6`).
- Multi-target relationship status: `not_established` for all 8; no unsupported relationship encoded as gold
- Secrets scan: PASS
- Contamination: benchmark facts and excerpts were extracted deterministically from corpus JSONL fields; no C1/C2 output, external website, or LLM-generated knowledge was used.

Human review is required before any experimental run.
