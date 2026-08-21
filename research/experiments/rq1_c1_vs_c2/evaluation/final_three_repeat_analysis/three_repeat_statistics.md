# Final three-repeat RQ1 analysis

Methodology: AI-assisted semantic evaluation using the same frozen source-grounded rubric as Formal Pass 1. Primary unit is the benchmark question; repeats are repeated measurements. Human and clinical validation were not performed.

Three-repeat per-question paired averages used 45 questions with at least one paired repeat.

## full_recall
- C1 mean: 0.9037037037037037
- C2 mean: 0.9234567901234568
- Mean C2-C1: 0.019753086419753093
- 95% bootstrap CI: [-0.02716049382716049, 0.07407407407407408]
- Wilcoxon p: 0.5505326538097681

## partial_or_better
- C1 mean: 0.9666666666666667
- C2 mean: 0.9753086419753085
- Mean C2-C1: 0.00864197530864198
- 95% bootstrap CI: [-0.009876543209876543, 0.029629629629629638]
- Wilcoxon p: 0.583882368919237

## missing_rate
- C1 mean: 0.02592592592592593
- C2 mean: 0.01728395061728395
- Mean C2-C1: -0.008641975308641976
- 95% bootstrap CI: [-0.029629629629629627, 0.009876543209876543]
- Wilcoxon p: 0.583882368919237

## contradiction_rate
- C1 mean: 0.007407407407407407
- C2 mean: 0.007407407407407407
- Mean C2-C1: 0
- 95% bootstrap CI: [0, 0]
- Wilcoxon p: 0

Repeat direction is documented in three_repeat_statistics.json and repeat_level_semantic_summary.csv. Retrieval/citation metrics were not recomputed for Repeats 2/3 and are not claimed here. Reliability and latency are descriptive.
