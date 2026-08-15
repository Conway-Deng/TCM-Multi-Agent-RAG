RETRIEVER_REGISTRY = [
    {"id": "R0", "name": "lexical", "description": "Deterministic BM25-like lexical baseline."},
    {"id": "R1", "name": "dense", "description": "Embedding similarity; local deterministic embeddings by default."},
    {"id": "R2", "name": "hybrid", "description": "Reciprocal-rank fusion of lexical and dense retrieval."},
    {"id": "R3", "name": "hybrid_reranked", "description": "Hybrid candidates with a separate reranking stage."},
]
