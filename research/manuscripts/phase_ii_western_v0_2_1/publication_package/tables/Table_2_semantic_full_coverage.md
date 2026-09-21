# Table 2: Semantic Evidence Full Coverage by Retrieval Condition

| Condition | n | Mean Full-Coverage Score | SD | Median | Min | Max |
|---|---|---|---|---|---|---|
| R0 | 42 | 0.543651 | 0.453919 | 0.500 | 0.0 | 1.0 |
| R1 | 42 | 0.805556 | 0.335191 | 1.000 | 0.0 | 1.0 |
| R2 | 42 | 0.626984 | 0.430556 | 1.000 | 0.0 | 1.0 |
| R3 | 42 | 0.710317 | 0.387927 | 1.000 | 0.0 | 1.0 |

**Note:** Separate Western Semantic Follow-up v0.2. Evaluates 42 answerable benchmark cases per retrieval condition using fixed Qwen/Qwen3-8B answers. Full-coverage score is the primary semantic endpoint (macro mean of `n_fully_covered / n_expected_points` judged against frozen expected points). Evaluated by a single GPT-5.6 Sol evidence-grounded evaluator with condition identity concealed. Does not represent clinical validation or patient safety.
