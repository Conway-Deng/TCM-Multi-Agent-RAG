# TCM Gold Benchmark v1.2 Coverage Report

Status: **FROZEN_SOURCE_GROUNDED_V1_2**

- Formal semantic-accuracy questions: 50
- Development/regression questions preserved separately: 9
- Herbal questions: 30
- Syndrome questions: 12
- Multi-target questions: 8
- Difficulty: 20 easy, 20 medium, 10 hard
- Unique atomic Gold facts: 108
- Corpus: TCM Research Corpus v1, 4,461 chunks
- Corpus SHA-256: 316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9

## Held-out methodology

All ten pre-pilot smoke questions were compared with v1.1 using canonical corpus entity names. Nine overlapping v1.1 items were removed from formal scoring and preserved in the held-out manifest as development/regression cases. Each was replaced by an unused, substantive Corpus v1 record of the same domain and difficulty role. No C1/C2 output, provider call, LLM call, or external medical knowledge was used.

Multi-target questions test target coverage, specialist routing, evidence separation, and prevention of unsupported relationships. Their relationship status remains not_established because Corpus v1 has no accepted herb-syndrome relation records.
