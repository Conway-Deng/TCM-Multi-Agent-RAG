# TCM-RAG Evaluation Plan

Evaluation focuses on system behavior, not clinical correctness.

Metrics:

- retrieval hit rate for expected topic
- irrelevant evidence rate
- abstention accuracy
- safety routing accuracy
- unsupported claim flag
- citation coverage
- language consistency
- generation source correctness
- response schema validity

Human review is still required for:

- clinical validity of pattern mappings
- appropriateness of safety language
- source verification
- whether summaries remain grounded in evidence

Automated metrics do not prove medical correctness.
