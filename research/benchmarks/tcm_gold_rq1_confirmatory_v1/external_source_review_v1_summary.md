# External GPT Source-Grounded Review Summary

- Questions reviewed: 100
- Atomic Gold rows reviewed: 223
- Question-level APPROVE: 77
- Question-level REVISE: 23
- Row-level APPROVE: 167
- Row-level REVISE: 56
- REMOVE: 0
- UNRESOLVED: 0

## Key finding

All 223 displayed Gold atomic facts are directly supported by their supplied Corpus evidence excerpts.

However, 13 questions use cross-reference-only source records such as "See ...", which are source-grounded but non-substantive for the confirmatory benchmark and should be replaced/revised before freeze.

A further 10 questions ask for fields that are not all represented in the proposed Gold/evidence set, so their question wording or source item should be revised before freeze.

## Cross-reference-only questions

- tcmc-v1-001
- tcmc-v1-003
- tcmc-v1-004
- tcmc-v1-010
- tcmc-v1-015
- tcmc-v1-017
- tcmc-v1-028
- tcmc-v1-033
- tcmc-v1-034
- tcmc-v1-052
- tcmc-v1-054
- tcmc-v1-057
- tcmc-v1-100

## Prompt/Gold completeness mismatch questions

- tcmc-v1-002
- tcmc-v1-005
- tcmc-v1-008
- tcmc-v1-009
- tcmc-v1-018
- tcmc-v1-020
- tcmc-v1-024
- tcmc-v1-025
- tcmc-v1-032
- tcmc-v1-042

## Methodology

This review checks source grounding only: whether the proposed Gold fact is supported by the supplied frozen Corpus v1 evidence. It is not clinical, medical, or TCM expert validation.
