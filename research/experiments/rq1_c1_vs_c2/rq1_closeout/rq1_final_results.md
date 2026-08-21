# RQ1 final results

## Scope

- Benchmark: TCM Gold Benchmark v1.2, 50 questions
- C1: controlled Single-RAG
- C2: controlled Multi-Agent
- Model: Qwen/Qwen3-8B
- Retrieval: R0
- Formal repeats: 3 × 100 runs = 300 total
- Statistical unit: question; repeats treated as repeated measurements

## Final repeated-measures comparison

| Metric | C1 | C2 | C2 − C1 | 95% bootstrap CI | p |
|---|---:|---:|---:|---:|---:|
| Full Recall | 90.37% | 92.35% | +1.98 pp | −2.72 to +7.41 pp | 0.5505 |
| Partial-or-Better Recall | 96.67% | 97.53% | +0.86 pp | −0.99 to +2.96 pp | 0.5839 |
| Missing Gold Rate | 2.59% | 1.73% | −0.86 pp | −2.96 to +0.99 pp | 0.5839 |
| Contradiction Rate | 0.74% | 0.74% | 0 pp | 0 to 0 pp | not informative (all ties) |

Bootstrap used 10,000 question-level resamples with seed `20260821`.

## Reliability and efficiency

- C1 usable real-provider outputs: 140/150 (93.33%).
- C2 usable real-provider outputs: 135/150 (90.00%).
- C2 mean latency was higher than C1 in all three repeats.
- Full Recall favored C2 in 3/3 repeats; Partial-or-Better and Missing Rate favored C2 in 2/3; contradiction was effectively tied.

## Interpretation and limitations

RQ1 is COMPLETE for this scope. The results do not establish statistically significant semantic superiority, clinical superiority, medical accuracy, or human-validated superiority for C2.

Limitations: the same 50 questions were repeated; R0 only; Qwen/Qwen3-8B only; Corpus v1 only; AI-assisted semantic evaluation with the frozen source-grounded rubric; independent human and clinical/TCM expert validation were not performed; RQ2 human-vs-LLM Judge validation remains incomplete; Repeat 2/3 retrieval/citation objective metrics were not recomputed.
