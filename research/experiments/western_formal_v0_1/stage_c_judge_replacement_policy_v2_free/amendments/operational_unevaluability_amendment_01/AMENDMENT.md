# Stage C Operational-Unevaluability Amendment 01

- Amendment: `western-stage-c-judge-replacement-policy-v2-free-amendment-01`
- Amendment type: operational execution policy only
- Scientific protocol identity: `western_formal_v0.1.4` (unchanged)
- Source policy: `western-stage-c-judge-replacement-policy-v2-free` (immutable)
- Effective timestamp: `2026-09-20T11:10:00+00:00`
- Amendment JSON SHA256: `87d237841b747fef74d1ed7d39ac99e2a0c8a84bf7ec57bc10222e399192bfc9`

## Timing and purpose

This amendment was adopted after Candidate 01 (`XingChenAGI/Xing4.0-29B`) produced two complete infrastructure-only incidents and before Candidate 02 was tested. It resolves the manual-review state created when the one permitted complete infrastructure recovery also ends solely in recognized infrastructure failures. It does not reinterpret a semantic result and does not alter the scientific protocol identity.

Candidate 01's ordinary Replicate 1 and recovery-01 each attempted all six frozen probes. Both returned six HTTP 500 responses, zero successful provider calls, zero provider-reported model identities, and zero valid semantic qualification outputs. These incidents do not show that Candidate 01 is poor or unsuitable as a judge. They show only that it was operationally unevaluable through the frozen provider conditions during the recorded attempts.

The immutable historical manifests are:

- Ordinary: `manifests/candidate-01-replicate-01.json`, SHA256 `1f0a64a7b698e2d49c84f8f0b113d9f492ed4c40e742e4e664d8d0557efb8bf6`
- Recovery: `manifests/candidate-01-replicate-01-recovery-01.json`, SHA256 `dff39085c3d9091b76a40634eadbf167cfc0ef8e360e79a863f399d0c92a33a2`

## General terminal operational state

The amendment adds the scientific state `operationally_unevaluable_under_current_provider_conditions`, represented internally as `terminal_operational_unevaluable`. It applies identically to Candidates 01–04 and to either required replicate.

The state is available only after a complete ordinary attempt and its single complete recovery both fail to independently pass 6/6 solely because of recognized infrastructure incidents. Neither attempt may contain a candidate/readiness failure or an ambiguous or unclassified failure. Both attempts must contain the complete frozen six-probe plan, recovery must begin at probe 1 under the identical execution contract, and the recovery budget must be exhausted.

Valid partial successes may occur. Each must independently satisfy identity, schema, and readiness validation. Partial outputs never carry across attempts, cannot form a partial qualification, and are never pooled. Any candidate/readiness failure in either attempt takes absolute precedence and terminally fails the candidate. An ambiguous or unclassified failure remains `manual_review_unresolved` and never authorizes automatic advancement.

The same rule applies when Replicate 1 passed but Replicate 2 ordinary and recovery attempts end solely in infrastructure incidents. Replicate 1 remains preserved but cannot substitute for Replicate 2.

Operational unevaluability is not candidate failure, semantic failure, Primary Judge selection, or evidence about model capability. It prohibits another recovery and permits only the next candidate in the already-frozen order to become eligible. No force-advance, model override, candidate-order override, or environment-variable bypass is permitted.

## Preserved scientific and execution contract

This amendment does not change Stage A, Stage B, TCM, the `Qwen/Qwen3-8B` generator, benchmark, estimands, judge schema, judge system prompt, six synthetic probes, candidate order, two-replicate requirement, 6/6 gate, 3600-second spacing, one-recovery maximum, zero-cost requirement, response format, temperature, maximum tokens, timeout, exact provider-model identity requirement, validators, enums, insufficiency behavior, or no-repair rules.

Candidate 02 becomes eligible only because it is the next already-frozen candidate after a valid immutable amendment and adjudication. Its zero input/output price must still be verified manually immediately before its first live call.

## Paper-ready disclosure

After the free-candidate order and qualification procedure were frozen, Candidate 01's ordinary six-probe qualification attempt and its single permitted complete recovery each ended in six provider HTTP 500 responses. Neither attempt produced a completed provider response, model identity, or semantic qualification output. We subsequently froze an operational clarification—before testing Candidate 02—that classifies a candidate as operationally unevaluable under the current provider conditions when an ordinary attempt and its one permitted complete recovery both contain only recognized infrastructure failures and neither contains readiness or ambiguous failures. This state makes no claim about candidate capability, prohibits further recovery and cross-attempt pooling, and advances only to the next prospectively ordered candidate. Both Candidate 01 incident manifests and their hashes were retained permanently and excluded from formal Stage C analysis. Stage A, Stage B, TCM, the generator, benchmark, judge contract, and scientific estimands were unchanged.
