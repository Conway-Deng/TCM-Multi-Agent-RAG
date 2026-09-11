# RQ4 protocol implementation amendment: post-fix validation smoke v1

Status: approved implementation-validity amendment before further provider execution.

Implementation repair commit: `4f8134f20439f8888a0e2836295c1eb2a7cbfe9a`.

Smoke passes 1 and 2 remain final under their original two-pass limit. Pass 1 exposed stale-backend reuse; pass 2 exercised the intended C4 implementation but exposed structured-output and timing defects that prevented C4 from reliably instantiating the frozen experimental condition.

This amendment authorizes exactly one development-only validation named `POST_FIX_VALIDATION_SMOKE_V1`, using the unchanged 10 development questions once under C2 and once under C4. It is not “Smoke Pass 3” and is not an attempt to improve semantic scores. It may only verify the repaired condition's operational validity.

Implementation corrections:

- flat, strict critique/revision/consensus JSON contracts;
- conservative extraction of one complete unambiguous JSON object, followed by strict schema validation;
- exact peer specialist outputs supplied to multi-specialist critique and revision, with trace-preserved payload evidence;
- revised positions supplied to consensus and recorded in the trace;
- 50-second stage wrapper around the configured 45-second provider timeout;
- 300-second whole-debate timeout and condition-specific runner bounds (120 seconds C2, 420 seconds C4);
- at most one retry per required stage, with no whole-execution retry and no C2 fallback;
- concurrent independent critique calls and concurrent independent revision calls to avoid an impossible sequential global budget.

The current OpenAI-compatible SiliconFlow adapter does not expose or send a provider-level `response_format`/JSON-schema parameter. The repaired path therefore uses strict JSON-only prompts, conservative single-object extraction, and local Pydantic validation; it does not assume an unsupported provider feature.

The frozen benchmark, Gold facts, questions, evidence, RQ4 hypothesis, C2 definition, model, corpus, retrieval, primary metric, +5 percentage-point interpretation threshold, formal execution order, and semantic-performance prompts are unchanged. The changes address runtime validity only.
