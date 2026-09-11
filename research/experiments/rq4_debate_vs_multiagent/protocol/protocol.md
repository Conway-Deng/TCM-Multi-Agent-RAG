# Frozen RQ4 platform protocol

Platform protocol status: `FROZEN_BEFORE_PROVIDER_EXECUTION`. The independent benchmark gate is complete: RQ4 candidate v1.2 received 232/232 source-grounded Gold-row approvals and is frozen as `FROZEN_SOURCE_GROUNDED_RQ4_V1` with SHA-256 `744298bc007aad562dab62268c0b887642e288408cd7cec87c8d03fb90aa21a4`.

## Question and controlled comparison

RQ4 asks whether genuine LLM-mediated structured debate, peer critique, revision, and consensus (C4) improves corpus-source-grounded answer quality relative to ordinary independent-specialist Multi-Agent C2.

- C2 is the unchanged ordinary Multi-Agent baseline.
- C4 shares C2 planner, specialist definitions, corpus, R0 retrieval, retrieved evidence, model, initial specialist generation, safety constraints, and answer contract.
- C4 adds exactly one model-mediated round: structured peer critique, specialist revision, then model-generated consensus.
- With one routed specialist, an evidence-only Grounding Critic reviews that output. It may identify unsupported claims, omissions, contradictions, and citation problems but may not introduce outside TCM knowledge.
- Required C4 stage failure after at most one retry is `FAIL_PROVIDER`; it never silently becomes C2.
- Stored fields contain task-relevant claims/evidence/critique only, never hidden chain-of-thought.

## Fixed formal setup

- Model/provider: `Qwen/Qwen3-8B` through the configured SiliconFlow endpoint.
- Corpus: TCM Research Corpus v1, 4,461 chunks, SHA-256 `316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9`.
- Retrieval: R0; top-k 4; iterative retrieval off.
- New source-reviewed held-out benchmark: 100 questions.
- One pass: 100 C2 and 100 C4 executions; paired deterministic order, seed 20260824, alternating pair order after deterministic question shuffle.
- Hard provider/request timeout: 120 seconds at the runner and configured provider timeout inside the backend.
- Retry: maximum two attempts total per specialist/debate provider stage.
- Primary unit: question. Internal model calls are diagnostics, not independent observations.

## Outcomes and analysis

Primary metric is question-level Gold Fact Full Recall; estimand is mean paired C4-C2 difference among complete usable pairs. The pre-registered practical interpretation threshold is +5 percentage points. Analysis uses 10,000 paired question bootstrap resamples with 95% CI and Wilcoxon signed-rank where applicable. Reliability uses all 100 planned pairs and McNemar exact where applicable. Latency uses paired usable questions.

Secondary measures: Partial-or-Better Recall, Missing Gold Rate, Contradiction Rate, retrieval recall, citation recall/precision, usable rate, provider failures/retries/stage failures, latency and provider-call counts, and objective debate diagnostics. No subjective debate-quality score is created.

Semantic evaluation is deterministic-order blinded AI-assisted review using SYSTEM_A/SYSTEM_B. Mapping is kept only in the locked formal manifest. Claims are described as source-grounded, never clinical or medical accuracy.
