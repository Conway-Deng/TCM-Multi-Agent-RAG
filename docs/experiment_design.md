# Experiment design

Configs select dataset, C0-C6 conditions, R0-R3 retrieval, top-k, agents, debate rounds, judges, repeats, bounded parallelism, and seed.

| RQ | Implemented experiment | Limitation |
|---|---|---|
| RQ1 | C1 vs C2 vs C5 vs C6 | accuracy claims require expert ground truth |
| RQ2 | labelled benchmark structure and judge outputs | synthetic labels are not objective truth |
| RQ3 | within-TCM specialist disagreement proxy | not Western-vs-TCM conflict |
| RQ4 | C2/C3/C4/C5/C6 ablation | conclusions need adequate sample and labels |
| RQ5 | machine fields plus reviewer ratings | communication quality needs human review |
| RQ6 | reviewer schema, CSV workflow, agreement utilities | unanswered until real human data exists |

Do not claim significance from the seed dataset. Traces record provider calls, tokens, latency, failures, fallback, and stages when available.

In C1-C6 the planner, evidence mapping, debate, judge rubrics, and final aggregation are deterministic. When `RESEARCH_REAL_LLM_ENABLED=true` and a real provider is configured, each evidence-participating specialist makes one constrained LLM call; abstaining specialists make none. C0 makes one direct call when enabled. Therefore call count is an observed runtime value, not proof inferred from provider configuration.
