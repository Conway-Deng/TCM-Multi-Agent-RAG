# TCM Retrieval Experiments

Implemented retrieval modes:

- `lexical`
- `semantic` hook, optional and disabled unless explicitly configured
- `hybrid`
- `hybrid_reranked` hook, optional and disabled unless a remote reranker endpoint is verified

Current default:

```dotenv
RETRIEVAL_MODE=hybrid
ENABLE_SEMANTIC_RETRIEVAL=false
ENABLE_REMOTE_RERANK=false
MIN_RELEVANCE_SCORE=0.18
TOP_K_CANDIDATES=10
TOP_K_EVIDENCE=4
```

Because semantic retrieval is disabled by default, the system reports `retrieval_method = "lexical"` instead of pretending embeddings were used.

The threshold is experimental. The evaluation dataset measures retrieval hit rate, irrelevant evidence rate, and evidence-insufficient abstention behavior.
