# RQ4 v1.1 Second External Review Summary

## Source-grounding result

- Candidate questions: 100
- Atomic Gold rows: 232
- Every Gold atomic fact is directly present in its supplied corpus excerpt: YES
- Cross-reference-only `See ...` targets remaining: 0
- Prompt/Gold completeness mismatches remaining: 0
- Rewritten questions `rq4-v1-002`, `rq4-v1-019`, `rq4-v1-039`: source-grounded and aligned

## Row-level disposition

- APPROVE: 187
- REVISE: 45
- REMOVE: 0
- UNRESOLVED: 0

## Question-level disposition

- Fully approved questions: 83 / 100
- Questions requiring revision: 17 / 100

## Blocking benchmark-integrity issue

The first-round source-grounding defects were fixed, but the 17 replacement questions were not built from genuinely unused corpus targets.

Fourteen replacement questions are exact intra-benchmark duplicates of already-present questions (same question/entity/evidence):

- `rq4-v1-001` duplicates `rq4-v1-003`
- `rq4-v1-004` duplicates `rq4-v1-005`
- `rq4-v1-007` duplicates `rq4-v1-006`
- `rq4-v1-008` duplicates `rq4-v1-009`
- `rq4-v1-015` duplicates `rq4-v1-010`
- `rq4-v1-018` duplicates `rq4-v1-012`
- `rq4-v1-026` duplicates `rq4-v1-013`
- `rq4-v1-044` duplicates `rq4-v1-014`
- `rq4-v1-045` duplicates `rq4-v1-017`
- `rq4-v1-048` duplicates `rq4-v1-020`
- `rq4-v1-050` duplicates `rq4-v1-022`
- `rq4-v1-051` duplicates `rq4-v1-023`
- `rq4-v1-055` duplicates `rq4-v1-024`
- `rq4-v1-057` duplicates `rq4-v1-025`

Three multi-target replacement questions reuse an herb evidence record already used by an existing herbal question:

- `rq4-v1-086` reuses herb evidence from `rq4-v1-027`
- `rq4-v1-088` reuses herb evidence from `rq4-v1-028`
- `rq4-v1-097` reuses herb evidence from `rq4-v1-030`

This leaves only 86 unique question texts among 100 question IDs, with 14 exact duplicate question pairs. Because QUESTION is the planned primary statistical unit, freezing the benchmark in this form would overstate the effective number of distinct test questions.

## Review interpretation

The duplicated rows are marked `REVISE` not because their Gold facts lack source support—they are source-supported—but because the replacement step explicitly required an UNUSED substantive Corpus v1 record and the current v1.1 candidate violates that requirement.

Recommended state:

`BENCHMARK_REVISION_REQUIRED`

Preserve the 83 fully approved questions. Replace only the 17 replacement questions listed above with genuinely unused substantive Corpus v1 records while preserving the 60/25/15 domain and 40/40/20 difficulty distributions. Then generate one final review packet.

This is source-grounded / benchmark-integrity review only. It is not clinical validation, TCM-expert validation, or independent human semantic validation.
