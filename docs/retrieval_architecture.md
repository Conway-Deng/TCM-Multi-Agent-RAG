# Retrieval architecture

- R0 lexical: deterministic BM25-like scoring.
- R1 dense: embedding similarity; the current safe default is deterministic `local-hash-embedding-v1`.
- R2 hybrid: reciprocal-rank fusion of lexical and dense ranks.
- R3 hybrid + reranking: hybrid candidates followed by `local-overlap-reranker-v1` by default.

Every result exposes chunk/source IDs, topic metadata, rank, applicable component scores, method, text, and source metadata. Non-applicable scores are null. Local dense/rerank implementations are reproducible engineering baselines, not neural models. `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3` can be configured, but they are not used in the default research path; bulk remote document embedding additionally requires explicit `ALLOW_BULK_REMOTE_EMBEDDING=true` approval.

Optional self-reflection checks sufficiency, reformulates a weak query, retrieves again, merges deterministically, and records whether iteration occurred.

With reviewed gold evidence, evaluation supports Precision@K, Recall@K, Hit Rate@K, MRR, and nDCG@K.
