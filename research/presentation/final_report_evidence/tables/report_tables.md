# Report tables

The CSV files in this directory are the machine-readable versions. Values are rounded only for presentation and were checked against the frozen source artifacts listed in `../README.md`.

## Dataset / setup

| Study | N | Conditions | Setup |
|---|---:|---|---|
| RQ1 confirmatory | 100 | C1 / C2 | Qwen/Qwen3-8B |
| RQ4 | 80 complete pairs; 90 represented | C2 / C4 | same-model structured debate |
| Research B | 240 | J1 / J2 | claim-only vs claim + evidence |
| Research C | 132 | K1 / K2 | conflict classification |
| A3 v1.3 | 76 complete pairs; 100 executions/condition | M1 / M2 | homogeneous vs tested heterogeneous configuration |

## Architecture results

| Metric | C1 | C2 | Difference |
|---|---:|---:|---:|
| RQ1 confirmatory Full Recall | 90.76% | 90.58% | −0.18 pp |
| RQ4 Full Recall | — | 83.75% (C4 81.25%) | −2.50 pp |
| RQ4 usability | — | 88/100 (C4 80/100) | −8 pp |

## Retrieval ablation

| Stage | R0 | R1 | R2 | R3 |
|---|---:|---:|---:|---:|
| Selection Recall@4 | 95.00% | 95.00% | 97.50% | 100.00% |
| Confirmation Full Recall | 80.00% | — | — | 76.67% |

## Evidence and conflict judges

| Metric | J1 | J2 | K1 | K2 |
|---|---:|---:|---:|---:|
| Accuracy | 35.56% | 82.92% | — | — |
| Macro-F1 | 29.03% | 79.75% | 77.97% | 75.89% |
| Citation coverage | — | — | 0.00% | 73.48% |

## A3 final results

| Metric | M1 | M2 | Difference |
|---|---:|---:|---:|
| Strict Gold Fact Full Recall (N=76) | 73.7% | 81.6% | +7.9 pp |
| Usability (N=100) | 96.0% | 78.0% | −18.0 pp |
| Mean latency | 115.12 s | 391.46 s | +276.34 s |

## Conflict interpretation

Research C K2 did not improve aggregate conflict Macro-F1 over K1. Its observed benefit was transparency and evidence/citation handling (K2 citation coverage 73.48%, viewpoint preservation 67.42%, uncertainty rate 84.09%), with higher latency. This is not a claim of clinical or medical truth.
