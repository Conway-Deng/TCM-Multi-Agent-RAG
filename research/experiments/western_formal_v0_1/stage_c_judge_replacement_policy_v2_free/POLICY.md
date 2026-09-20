# Prospective Free-Only Stage C Primary-Judge Policy

- Policy: `western-stage-c-judge-replacement-policy-v2-free`
- Protocol amendment: `western_formal_v0.1.4`
- Policy JSON SHA256: `1e77ab1a85ab54e155926c0c9c2b6a7e26728243415d6ccc484cc81c47f89648`
- Documentation snapshot: `2026-09-20`

## Scope and preserved study structure

This policy is a prospective extension of the existing Western MediRAG study. Stage A retrieval and Stage B generation are complete and frozen. The Western generator remains `Qwen/Qwen3-8B`. TCM is a separate existing system and is unchanged. Only Stage C primary-judge qualification is extended.

The original GLM Stage C incident, all three GLM preflights, replacement policy v1, and the paid `deepseek-ai/DeepSeek-V3.2` Candidate 01 incident remain immutable. The paid attempt is anchored by SHA256 `9f445fa65b134c754c0ea5ff6235ebc0a3c5f570f37b09e1676d2492bf620563`; it is historical only and must never be pooled with or counted as qualification evidence for this free pool.

This v2-free policy was created after that HTTP 402 incident and is frozen before any candidate in the free pool is tested. It introduces a prospective zero-cost operational constraint. No formal or semantic Stage C result was used to choose or order the free candidates.

## Zero-cost constraint and frozen candidate order

The operator manually observed input and output prices of `¥0.000000 / K tokens` for all four candidates in SiliconFlow Model Plaza on 2026-09-20. This is a dated documentation snapshot, not a permanent factual guarantee. Immediately before the first live call to each candidate, the operator must manually recheck both prices. If either is no longer zero, the candidate must not be called; an immutable operational-ineligibility note is recorded and the next candidate becomes eligible. A pricing change is not model-quality evidence.

The exact order is:

1. `XingChenAGI/Xing4.0-29B` — different family from the Qwen generator, large context capacity, and zero-cost at the snapshot.
2. `THUDM/GLM-4-9B-0414` — different-family fallback. This is not historical `THUDM/GLM-Z1-9B-0414`.
3. `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` — Qwen3-8B-based and therefore placed after different-family candidates.
4. `Qwen/Qwen3.5-4B` — smaller Qwen-family final fallback.

This order is methodological, not a capability ranking, and cannot be changed in response to results.

## Frozen execution contract

Every attempt uses the existing six synthetic probes in their frozen order, the case-specific JSON Mode prompt, `FormalJudgeOutput`, `JUDGE_SYSTEM_PROMPT`, strict raw-type validation, Pydantic validation, `_validate_completed_judge_output`, and the existing no-repair rules. Transport is exactly `{"type":"json_object"}`, temperature is `0`, maximum output is `1200` tokens, and timeout is `120` seconds. No synonym mapping, coercion, schema repair, or post-hoc correction is permitted.

Candidate-specific thinking transport is frozen:

- Candidates 01, 02, and 04 omit the `enable_thinking` field because their established local provider contract does not use that toggle.
- Candidate 03 sends `enable_thinking=false`, matching its established provider contract.

The runner may not dynamically add, remove, or change the field after a failure.

Every successful provider response must report the exact frozen candidate model ID in its top-level `model` field. Missing, null, empty, or non-string model identity is a malformed provider response. A different valid string is an exact identity mismatch. Aliases and substitutions are prohibited.

## Sequential primary-judge qualification

Candidate 01 begins eligible. Later candidates remain blocked while an earlier candidate is unresolved.

Each ordinary replicate runs all six probes from probe 1. Replicate 1 must pass 6/6, including 2/2 in each answerability class, zero timeouts, exact insufficiency labels, exact model identity, and all latencies within 120 seconds. If effective Replicate 1 passes, effective Replicate 2 may start only after at least 3600 seconds from its completion. Replicate 2 must independently pass the same gate.

The first candidate passing two effective replicates becomes the Primary Judge. Selection then stops, and later candidates remain untested. An ordinary third replicate is prohibited.

## Failure classification and infrastructure recovery

Candidate/readiness failures include strict output-contract failure, identity mismatch, unsupported finish reason, rejection of a deterministic required request parameter, and a completed response exceeding 120 seconds. Such a failure terminally fails the candidate and unlocks the next candidate.

Infrastructure incidents include HTTP 402 payment/account rejection, authentication/account-access failure, rate limiting, connectivity failure, provider/server 5xx, provider timeout without a completed response, and provider/model unavailability. An infrastructure incident does not fail the candidate and does not unlock the next candidate.

If one attempt contains both a candidate/readiness failure and an infrastructure incident, candidate/readiness failure takes precedence. This prevents infrastructure recovery from erasing an already observed contract failure. An ambiguous or unclassified technical failure fails closed for manual methodology review and authorizes neither recovery nor advancement.

At most one full recovery is allowed for an ordinary replicate classified solely as an infrastructure incident. The original incident manifest is permanent. Recovery uses a new deterministic filename, begins at probe 1, reruns all six probes, and uses identical candidate, prompt, schema, transport, timeout, and identity rules. Probe-level retry, selective filling, and pooling with the partial attempt are prohibited.

If recovery passes, it becomes the effective replicate; the Replicate 2 clock starts from recovery completion. If recovery has a candidate/readiness failure, the candidate terminally fails. A second infrastructure incident during recovery stops automatic execution and requires manual methodology review. No further recovery or automatic candidate advancement is allowed.

## Immutable manifests

Canonical manifests live only under `stage_c_judge_replacement_policy_v2_free/manifests/`. Ordinary and recovery attempts have deterministic names, are atomically created, and cannot be overwritten. The loader validates policy and historical hashes, candidate metadata, all six probes, execution settings, classifications, and internal state. Raw provider text is never stored; a response SHA256 may be recorded. No artifact is eligible as formal Stage C data.

The production CLI accepts candidate and replicate numbers from the frozen registry only. It accepts no model ID, output path, timeout, prompt, or schema override. Live execution requires both `--confirm-zero-cost` and `--execute-candidate-preflight`. Recovery additionally requires `--recovery 1` and must already be authorized by the state machine.

## Future sensitivity analysis

After the Primary Judge is frozen and the primary formal Stage C evaluation is complete, a second judge from another model family may be introduced only under a separately versioned prospective amendment. It must not affect, replace, or be pooled with the Primary Judge and must not change the main estimand. Such a judge would assess only whether major Stage C patterns are robust to evaluator choice. No sensitivity runner is implemented by this policy.

## Reserved formal identity

This implementation creates no formal run. A future qualified run is reserved as `western-formal-v0.1.4-stage-c-free-jrv1-YYYYMMDD-01` with freeze directory `stage_c_execution_v0_1_4_free_jrv1`.
