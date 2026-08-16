# TCM Corpus v1 retrieval-only pilot

The existing repository registry is preserved: R0=lexical, R1=dense, R2=hybrid, R3=hybrid+rerank.

Dense/hybrid pilot used deterministic local hash embeddings. No remote or paid embedding call was made.

| Method | Registry ID | Hit@K | MRR | Provenance | Source diversity | Duplicate rate | Mean latency (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexical | R0 | 1.000 | 1.000 | 1.000 | 1.250 | 0.000 | 23.747 |
| dense_local_hash | R1 | 0.250 | 0.250 | 1.000 | 1.250 | 0.000 | 143.699 |
| hybrid | R2 | 1.000 | 0.613 | 1.000 | 1.250 | 0.000 | 100.731 |
| hybrid_local_reranked | R3 | 1.000 | 0.521 | 1.000 | 1.250 | 0.000 | 116.730 |

This is a small retrieval-only pipeline pilot. It is not a final research conclusion and does not establish clinical correctness.
