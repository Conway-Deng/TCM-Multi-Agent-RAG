# Table 1: Stage-A Headline Retrieval Metrics

| Condition | n | Chunk Recall@4 | Source Recall@4 | Hit@4 | MRR |
|---|---|---|---|---|---|
| R0 | 42 | 0.428571 | 0.890909 | 0.595238 | 0.450397 |
| R1 | 42 | 0.634921 | 0.890909 | 0.785714 | 0.605159 |
| R2 | 42 | 0.539683 | 0.890909 | 0.738095 | 0.573413 |
| R3 | 42 | 0.523810 | 0.836364 | 0.690476 | 0.581349 |

**Note:** Frozen Western Formal Study v0.1.5. Headline retrieval denominator is 42 supported or partially supported cases with non-empty primary gold evidence. Six insufficient-evidence cases were excluded from the headline retrieval denominator and not imputed as failures. All conditions evaluated at top-4 retrieval depth. Recalls represent micro-aggregates across primary-gold items.
