# Prospective Stage C Judge Replacement Policy v1

- **Policy Version**: `western-stage-c-judge-replacement-policy-v1`
- **Protocol Amendment Version**: `western_formal_v0.1.3`
- **Documentation Snapshot Date**: `2026-09-20`
- **Target Component**: Stage C Evaluator / LLM-as-a-Judge
- **Generator Model**: `Qwen/Qwen3-8B` (Permanently Unchanged)

---

## 1. Context & Replacement Rationale

The original Stage C judge specified in `western_formal_v0.1.2`, **`THUDM/GLM-Z1-9B-0414`**, encountered systematic technical failures during formal execution (run `western-formal-v0.1.2-stage-c-r2-20260920-01`), culminating in 39 rows attempted (0 completed, 19 output schema failures, 20 technical timeout failures). The incident was preserved immutably.

Subsequently, three successive synthetic execution-readiness preflights were evaluated for `THUDM/GLM-Z1-9B-0414`:
1. **Preflight v1** (`stage_c_r3_preflight_readiness.json`, SHA256 `4129c0fae0ddf8f8da3d81bc6e18e673bdd71b5d512ff4c97fc01973a530d9e3`): Structured Outputs failed due to provider serverless incompatibility.
2. **Preflight v2** (`stage_c_r3_preflight_readiness_v2.json`, SHA256 `1a70f189b52cb9f539807b0f8fa172be6a47ced21d384bcca7db0b81a514df94`): Case-specific prompt schemas in Structured Outputs mode similarly failed.
3. **Preflight v3** (`stage_c_r3_preflight_readiness_v3.json`, SHA256 `b864d2dd45120eade9b7f4ff8688eb35ce7ba9c75262d6eddd365c90dc58b3d2`): JSON Mode transport (`{"type": "json_object"}`) yielded only 1/6 JSON-contract success (0/2 supported, 1/2 partially supported, 0/2 insufficient), with 0 timeouts and all probes <=120s latency.

Because `THUDM/GLM-Z1-9B-0414` failed three preserved synthetic readiness preflights and is listed as deprecated on the provider platform, formal execution readiness cannot be achieved with this model. A prospective replacement policy is enacted **prior to testing any candidate**.

---

## 2. Absence of Formal Semantic Stage C Dataset

No valid formal Stage C judgment dataset exists in `western_formal_v0.1.2`. The historical r2 run was terminated as an infrastructure and execution incident. Its outputs (SHA256 `fd3544854e4eadfbb498cf9ab5329cee0fb45a03380b25b2c82fabef03ed5363`) and incident manifest (SHA256 `24577b182eb9ba0c5a68d88419eac27fab4ab1709f19d850f050ae225dda9531`) remain frozen and ineligible for primary analysis. No completed rows were produced.

---

## 3. Candidate Registry and Frozen Order

The replacement candidate sequence is permanently fixed and immutable. It is defined before any candidate call is executed and cannot be reordered or bypassed:

| Candidate | Model ID | Slug | Context Window | Transport | Thinking Mode |
|---|---|---|---|---|---|
| `candidate-01` | `deepseek-ai/DeepSeek-V3.2` | `deepseek-v3-2` | 164,000 | `{"type": "json_object"}` | `enable_thinking=false` |
| `candidate-02` | `openai/gpt-oss-120b` | `gpt-oss-120b` | 131,000 | `{"type": "json_object"}` | `enable_thinking=false` |
| `candidate-03` | `Qwen/Qwen3.5-35B-A3B` | `qwen3-5-35b-a3b` | 262,000 | `{"type": "json_object"}` | `enable_thinking=false` (Strict) |

Provider for all candidates: `siliconflow`.
Arbitrary `--model` input that bypasses this registry is strictly prohibited.
Candidate order is strictly sequential: candidate 01 must be tested first. Candidate 02 is attempted only if candidate 01 terminally fails. Candidate 03 is attempted only if candidate 02 terminally fails.

*Candidate performance is characterized purely in terms of technical execution readiness and interface contract fulfillment. No candidate is asserted to be "clinically better" or scientifically superior a priori.*

---

## 4. Selection & Failover State Machine

A candidate qualifies to serve as the formal Stage C judge if and only if it completes **two successful independent replicates**:

1. **Replicate 1**: Must achieve 6/6 JSON contract pass under the 120s timeout.
   - If Replicate 1 fails: candidate fails terminally; Replicate 2 is prohibited; the replicate artifact is preserved; the next registered candidate becomes eligible.
2. **Replicate 2 Spacing**:
   - Replicate 2 cannot be scheduled at an arbitrary or concurrent time.
   - Replicate 2 requires an elapsed time of at least **60 minutes** (>=3600 seconds) between the recorded completion timestamp (`completed_at`) of Replicate 1 and the start timestamp (`started_at`) of Replicate 2.
3. **Replicate 2 Evaluation**:
   - If Replicate 2 passes: candidate is selected; execution preflight stops immediately; all later candidates remain permanently untested.
   - If Replicate 2 fails: candidate fails terminally; no third replicate or tie-breaker is permitted; both replicate artifacts are preserved; the next registered candidate becomes eligible.

### Advancement Criteria
Advancement to the next candidate in the registry is authorized **strictly and exclusively** for:
- Candidate/model unavailable on provider;
- Exact provider/model identity mismatch;
- JSON contract failure (malformed JSON, invalid raw types, missing fields, wrong enums);
- Timeout (>120.0 seconds);
- Predefined synthetic readiness failure (e.g. failure to support `enable_thinking=false`).

Advancement is **strictly prohibited** based on:
- Formal Stage C score or accuracy;
- Empirical claim label distribution;
- Treatment effect estimate;
- Any semantic judgment output or post-hoc preference.

---

## 5. Replicate Readiness Gate (6 Frozen Probes)

Each replicate executes the exact 6-probe matrix frozen in `western-stage-c-r3-preflight-matrix-v1`:
- Probe 1: `synthetic-supported-probe-01` (`supported`, expected insufficiency: `not_applicable`)
- Probe 2: `synthetic-supported-probe-02` (`supported`, expected insufficiency: `not_applicable`)
- Probe 3: `synthetic-partially-supported-probe-01` (`partially_supported`, expected insufficiency: `not_applicable`, all enums exercised)
- Probe 4: `synthetic-partially-supported-probe-02` (`partially_supported`, expected insufficiency: `not_applicable`)
- Probe 5: `synthetic-insufficient-probe-01` (`insufficient`, expected insufficiency: `appropriate_abstention`)
- Probe 6: `synthetic-insufficient-probe-02` (`insufficient`, expected insufficiency: `appropriate_bounded_insufficiency`)

Each replicate passes if and only if:
- **6/6 JSON-contract success**
- Supported 2/2 pass
- Partially supported 2/2 pass
- Insufficient 2/2 pass
- Zero timeouts
- Every probe latency <= 120.0 seconds
- Exact fixture insufficiency labels
- Exact provider-reported model identity
- Strict raw JSON types verified before Pydantic parsing
- No coercion, no synonym repair, no semantic normalization, and no post-hoc repair

Timeout contract:
- Client timeout: **120.0 seconds** (directly formal-compatible; 300-second diagnostic timeout is discontinued).

---

## 6. Execution Constraints & Methodological Governance

1. **No Cross-Model Pooling**: Judgments from different candidates must never be pooled, averaged, or concatenated across cells.
2. **No Selective Retry**: Probes cannot be rerun individually. Each replicate must run all 6 probes sequentially as a unified trial.
3. **No Raw Responses Stored**: In compliance with execution safety, manifests record SHA256 hashes of model responses (`response_sha256`), setting `raw_response_stored = false`.
4. **Instrument Continuity**: Replacing the judge model changes the operational measurement instrument while strictly preserving the conceptual estimand and evaluation protocol.
5. **Paper Disclosure**: Full transparency is mandatory. The publication/report must disclose:
   - Initial GLM-Z1 failure across r2 and synthetic preflights v1, v2, v3;
   - Machine-readable replacement policy frozen prior to candidate testing;
   - Results of candidate preflight replicates;
   - Final selected judge model.

6. **Canonical Manifest Directory & Path Immutability**:
   - All replacement preflight manifests must be written to and inspected from the canonical directory: `research/experiments/western_formal_v0_1/stage_c_judge_replacement_policy_v1/manifests/`.
   - Arbitrary output path overrides that could bypass the candidate state machine are strictly prohibited.
7. **Timeout Contract & Override Prohibition**:
   - Client timeout is frozen at exactly **120.0 seconds** (formal-compatible directly).
   - Runtime timeout overrides are strictly prohibited.
8. **Fail-Closed Prior Manifest Verification**:
   - The state machine strictly verifies the structural and scientific validity of prior candidate manifests rather than trusting summary flags.
   - Forged, inconsistent, or altered manifests fail closed immediately and block advancement.
9. **Policy SHA256 Pinning**:
   - The machine-readable `policy.json` is hashed and pinned (`d17d538bcb650965ccbef817ceeff0f554f15a082a6461d6b99fcd81961eaae1`).
   - The runner verifies policy SHA integrity before any provider execution.

---

## 7. Reserved Formal Identities

Upon successful qualification of a replacement candidate through 2 consecutive preflight replicates, formal execution will be scheduled under:
- Formal Run ID template: `western-formal-v0.1.3-stage-c-jrv1-YYYYMMDD-01`
- Formal Execution Directory: `stage_c_execution_v0_1_3_jrv1`

Neither the formal run nor the execution directory will be instantiated during this implementation task.
