# Retrieval architecture

- R0 lexical: deterministic BM25-like scoring.
- R1 dense: embedding similarity; deterministic local hash embeddings are the no-key fallback.
- R2 hybrid: reciprocal-rank fusion of lexical and dense ranks.
- R3 hybrid + reranking: hybrid candidates followed by a separate local overlap reranker.

Every result exposes chunk/source IDs, rank, applicable component scores, method, text, and source metadata. Non-applicable scores are null. Local dense/rerank fallbacks are reproducible engineering baselines, not production neural models.

Optional self-reflection checks sufficiency, reformulates a weak query, retrieves again, merges deterministically, and records whether iteration occurred.

With reviewed gold evidence, evaluation supports Precision@K, Recall@K, Hit Rate@K, MRR, and nDCG@K.
