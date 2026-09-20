# Prospective Stage C Wave-2 Free-Judge Policy

- Policy: `western-stage-c-judge-wave2-free-v0.1.5`
- Scientific protocol: `western_formal_v0.1.5`
- Policy JSON SHA256: `5ac5b5bab86b853fe719303e92defcadc609015b29648630b29ed5db1191b596`
- Wave-1 exhaustion SHA256: `eead5bc8cbcd8fb27f79ca7095bc8d210d8ba513f2716120c493396ab9155827`
- Provider: `siliconflow`
- Cost constraint: zero input and output price
- Maximum candidates: four
- Wave 3: prohibited

## Timing and scope

Wave 1 exhausted without selecting a Primary Judge. This Wave-2 policy was designed after that exhaustion and before any Wave-2 semantic qualification output. It creates a new scientific protocol identity because the candidate sampling frame, deterministic ordering procedure, and terminal stopping rule change. Wave 1 and every historical qualification artifact remain immutable.

Wave 2 is the one and only additional candidate wave. It does not itself create a candidate list. The candidate registry remains unavailable until operator-supplied catalog, pricing, and capability artifacts are validated offline and atomically frozen as `candidate-pool-freeze.json`.

## Non-semantic discovery

Discovery uses one timestamp shared by three immutable operator-supplied artifacts: a SiliconFlow `/v1/models` catalog snapshot, a manual pricing ledger, and a non-semantic capability/documentation ledger. Completion, generation, benchmark, reputation, family, parameter-size, and expected-performance evidence are prohibited during discovery.

Every catalog model must receive an explicit eligibility or exclusion disposition. Eligibility requires chat-completions use, exact zero input and output prices, documented compatibility with the existing OpenAI-compatible endpoint and JSON-object transport, available account and regional access, a documented `omit` or `send_false` thinking setting, and no candidate-specific interface change. The generator, all previously tested exact models, documented aliases of tested models, unsupported modalities, unknown values, retired or unavailable models, and models requiring interface changes are excluded.

The complete eligible set is preserved. Exact model IDs are sorted by ascending UTF-8 bytes, and the first four—or all if fewer than four—are selected. Manual order overrides and ad-hoc additions are impossible. Immediately before each selected candidate's first live call, zero input and output prices must be manually reconfirmed; a pricing change produces operational ineligibility with zero inference calls.

## Frozen qualification contract

The judge instrument is unchanged: `FormalJudgeOutput`, `JUDGE_SYSTEM_PROMPT`, the six synthetic probes, answerability cases, evidence points, insufficiency labels, validator, enums, and no-repair rules are identical to Wave 1. Transport remains JSON object, temperature `0`, maximum output `1200`, and timeout `120` seconds. Exact provider-reported model identity is required.

Each candidate must independently pass 6/6 probes in Replicate 1 and, after at least 3600 seconds, 6/6 in Replicate 2. The first such candidate becomes Primary Judge and later candidates stop. Candidate/readiness failure has precedence over ambiguous and infrastructure failures.

An infrastructure-only ordinary attempt permits one complete recovery from probe 1. Recovery never pools with the ordinary attempt. A second infrastructure-only incident results in `operationally_unevaluable_under_current_provider_conditions`, prohibits another recovery, and advances mechanically. Partial valid successes are telemetry only.

Qualification outputs are never formal Stage C research data. Formal execution remains blocked until a Wave-2 candidate is selected after two passing replicates.

## Final stopping rule

If no model is eligible at freeze, or every selected Wave-2 candidate reaches a terminal state without qualification, automated semantic Stage C terminates. There is no Wave 3, automatic paid fallback, silent unqualified judge, ad-hoc candidate, or judge-interface redesign within this study. Stage A and Stage B remain completed and valid; W-RQ2 and W-RQ3 semantic estimates remain unavailable.

## Paper-ready methods disclosure

The prospectively frozen first free-judge pool exhausted without a Primary Judge: two candidates were operationally unevaluable under the observed provider conditions and two failed readiness under the frozen interface contract, without global capability conclusions. Before observing any Wave-2 semantic qualification output, we versioned a final zero-cost SiliconFlow candidate wave. Candidates were derived from a timestamped catalog, pricing ledger, and non-semantic capability ledger; all catalog models received recorded dispositions; eligible identifiers were ordered by ascending UTF-8 bytes; and at most four were selected. The original judge instrument, generator, benchmark, Stage A/B data, endpoints, and qualification thresholds were unchanged. Wave-1 and Wave-2 qualification outputs were never pooled or treated as formal research data. Exhaustion of Wave 2 terminated automated semantic Stage C without a third wave.
