# Western Stage B Execution Safety Freeze v0.1.2

This directory freezes execution safety controls for Stage B. It does not amend the scientific protocol, execute Stage B, or authorize Stage C.

## Dual anchors

The immutable scientific-input anchor remains:

- protocol version `western_formal_v0.1.2`
- protocol SHA256 `af22119036892abc512c175e071ccdb6e0aa562db53caaabe96bc9e8f735b192`
- Stage A checkpoint commit `5eb40146f026b42547220b0f0cfd077d72a75562`
- Stage A run ID `western-formal-v0.1.2-stage-a-20260918-01`
- Stage A retrieval SHA256 `91749431949c554e8085ef1aae11aede6570c710b1055e1330e5fe452ab2983e`
- 192 frozen experiment IDs in the existing Stage A order

The separate execution-safety anchor is this directory. `execution.json` records Commit 1 and the SHA256 values of the runtime implementation files. The execution-freeze commit is deliberately not embedded in that JSON; the runtime resolves Commit 2 from Git history for `execution.json` and requires current `HEAD` to equal it.

## Implementation anchor

- Commit 1: `de04c2ca1742794206de80e75155aa3d44c47eb4` (`Add Stage B execution safety controls`)
- `backend/western/formal_eval.py`: `9a25c416569c0567bd7610ad70ff156fd3e5c578345c20d7153aeb4dcece9a4d`
- `scripts/run-western-formal-v0.1.py`: `86f5be7f43de38699136058c9abb863eab2335c0c177faf4114e3a37b156bc98`

## Required execution state

Stage B start or resume requires the exact execution-freeze commit at `HEAD`, a clean worktree, all frozen input hashes, the exact sealed Stage A matrix and manifests, and a valid Stage B execution manifest/state.

The state machine supports a fresh start, recovery after manifest creation but before the first provider call, strict frozen-order suffix resume, and zero-call sealing when all 192 valid records already exist. Invalid JSON, invalid terminal records, duplicate or foreign IDs, non-prefix rows, more than 192 rows, or a final ID set unequal to Stage A are fatal and remain unsealed.

Runtime provenance is checked against the matching frozen Stage A retrieval cell before every append and checked again during finalization. Stage B sealing requires exact Stage A/Stage B experiment-ID equality.

Retryable provider errors are limited to connectivity, HTTP 5xx, timeout, and malformed response and receive one retry. Output-quality rejection and rate limiting receive no retry and remain distinct outcomes. Authentication/configuration failures and unexpected programming or invariant exceptions are fatal formal-run errors.

Independent `B-finalize` requires the execution freeze, clean worktree, exact scientific inputs, valid frozen Stage A, sealed Stage B, and no Stage C. It writes only the immutable Stage B raw results, generation metrics, provider metrics, run manifest, and freeze memorandum.

At this freeze, Stage B has not been executed and no provider has been called.
