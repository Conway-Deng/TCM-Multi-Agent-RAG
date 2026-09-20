# Western Stage C execution freeze v0.1.2-r1

This directory prospectively freezes the Stage C execution pathway and statistical analysis plan. Stage C had not been executed when this freeze was committed.

## Identity and immutable parents

- Protocol: `western_formal_v0.1.2`
- Protocol SHA256: `af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192`
- Stage C run ID: `western-formal-v0.1.2-stage-c-r1-20260919-01`
- Stage C execution version: `western-stage-c-execution-v0.1.2-r1`
- Frozen Stage A run: `western-formal-v0.1.2-stage-a-20260918-01`
- Frozen Stage A retrieval SHA256: `91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e`
- Primary Stage B run: `western-formal-v0.1.2-stage-b-r1-20260919-01`
- Primary Stage B SHA256: `afc0665858b0493d9c4dfbc2d8990ccd89c663f2b63278221407cb876feaf17c`
- Original outage attempt: incident-only, preservation-only, and prohibited as Stage C input
- Implementation commit: `20f4a7075109b5c39116d2aed8f70a3a77de38ec`
- Analysis JSON SHA256: `123322b8a416697cd814561b66b3722291d421206ff6310de6667b9d31b79ec8`

## Frozen judge settings

- Provider: `siliconflow`
- Model: `THUDM/GLM-Z1-9B-0414`
- Temperature: `0.0`
- Maximum output tokens: `1200`
- Timeout: `120.0` seconds
- Thinking: disabled

## Preregistered analysis

W-RQ2 uses the 42 evidence-answerable cases. Its primary endpoint is per-answer full evidence-point coverage, summarized by condition as a macro mean. The three comparisons are R1-R0, R2-R0, and R3-R0 using case-paired mean differences and deterministic 10,000-resample percentile bootstrap intervals with seed `20260815`. No primary binary significance decision is defined.

Unsupported-claim presence is the key secondary endpoint, with exact two-sided McNemar tests and Holm correction across only the three R0 comparisons. All other endpoints are descriptive. No composite clinical safety score is defined.

Generation technical missingness, judge technical missingness, and semantic missingness are reported separately and excluded from their relevant semantic denominators. Each pairwise endpoint uses its own successful-pair intersection. There is no imputation, no pooling with the original outage attempt, and no shared complete-case denominator across unrelated endpoints.

W-RQ3 analyzes the six insufficient cases separately. A successful judgment must select exactly one of the four preregistered insufficiency outcomes; `not_applicable` is invalid. No W-RQ3 hypothesis test is defined.

## Execution and finalization safety

The runtime must verify the exact freeze commit and a clean worktree before any provider call. It independently verifies the frozen Stage A, finalized primary Stage B repeat, all pinned hashes and manifests, non-outage classification, and exact ordered 192-cell identity.

Resume is restricted to a validated exact prefix. Duplicate, foreign, or out-of-order records are fatal. Retry is limited to one second attempt for connectivity, timeout, HTTP 5xx, or malformed transport response. Model-output JSON and schema failures do not retry. Authentication, configuration, provider-setting, model, hash, freeze, repository-state, and invariant failures are fatal.

Stage C finalization and merged finalization are separate, immutable operations. They revalidate parent anchors, ordered identities, raw and manifest hashes, the analysis-plan hash, and exclusion of the original outage answers. Existing artifacts are never overwritten.

## Launch status at freeze

`STAGE C NOT EXECUTED`
