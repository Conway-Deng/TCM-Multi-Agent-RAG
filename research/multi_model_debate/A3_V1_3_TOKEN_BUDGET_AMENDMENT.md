# A3 v1.3 pre-formal token-budget compatibility amendment

Status: pre-formal. No A3 v1.3 formal provider call is authorized by this amendment.

## Operational history

A3 v1.1 was stopped as `ABORTED_PRE_FINAL_MAX_TOKENS_VALIDATION`. Its common 384-token revision allowance produced repeated revision-stage truncation, including 14 Qwen length finishes and five terminal conditions. A3 v1.2 therefore changed only revision from 384 to 512 and restarted from zero.

A3 v1.2 was stopped as `ABORTED_PER_PROTOCOL` after 6 of 200 canonical conditions. It recorded six length finishes: one DeepSeek initial, one DeepSeek revision, and four Qwen revisions. Three conditions were terminally unusable. The run is permanently excluded from final inference.

Only operational provider and stage metadata from the aborted runs were inspected. No A3 semantic outcome metric was inspected or used to choose these limits.

## v1.3 budgets

| Stage | v1.2 | v1.3 | Decision |
|---|---:|---:|---|
| Initial | 384 | 512 | Smallest standard increase supported by one observed DeepSeek length finish at 384. |
| Critique | 512 | 512 | Unchanged; no observed length finish. |
| Revision | 512 | 768 | Smallest standard increase above the demonstrably insufficient 512 allowance. |
| Consensus | 512 | 512 | Unchanged; no observed length finish. |

The same stage-level values apply to Qwen, GLM, and DeepSeek in both M1 and M2. Model-specific and condition-specific overrides are forbidden. The change increases only the maximum visible generation allowance. Provider completion-token totals for GLM and DeepSeek can include reasoning tokens; this remains a provider/model behavior confound and is not addressed with model-specific budgets.

Reasoning content from GLM or DeepSeek remains excluded from peer prompts, consensus prompts, and semantic review. Only visible structured content is shared or reviewed.

## Unchanged scientific protocol

The benchmark, Gold facts, evidence, R0 retrieval, roles, prompts, schemas, three-agent design, critique graph, one debate round, fixed Qwen consensus, model IDs, role rotation, statistical plan, sample size, and primary outcome are unchanged. The clean design remains 100 questions × 2 conditions = 200 canonical executions and 2,000 nominal provider generations.

## Preregistered systemic truncation stop rule

After every canonical checkpoint and before starting the next one, the runner counts all `finish_reason=length` attempts and terminal conditions caused by truncation, grouped only by stage and pooled across conditions and models. It must stop and mark the run `ABORTED_SYSTEMIC_TRUNCATION` if either threshold is reached at any stage:

1. 10 length-finish attempts at the same stage; or
2. 3 terminal truncation conditions at the same stage.

The rule is condition-blind and applies identically to M1 and M2 and to initial, critique, revision, and consensus. A normal individual truncation receives the frozen retry policy at the same budget. No adaptive token increase or fallback is permitted.

## Restart rule

Formal v1.3 must start from zero. No answer, provider attempt, stage output, or terminal record from v1.1 or v1.2 may be copied into `formal_v1_3`.
