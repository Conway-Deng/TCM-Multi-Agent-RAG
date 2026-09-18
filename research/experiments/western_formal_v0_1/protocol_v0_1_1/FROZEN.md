# MediRAG-West Formal Evaluation Protocol v0.1.1 — Frozen

## Freeze identity

- Protocol version: `western_formal_v0.1.1`
- Protocol SHA256 (`protocol.json`): `a91f855f5707e07efeb7e460f11e2290f6fb5c282da942ab9b9b4f75360e77c8`
- Supersedes: `western-formal-v0.1`
- Superseded before formal execution: `true`
- Formal cells executed under v0.1: `0`
- Original v0.1 commit: `c1a8d0658fc334d70f50d6b688de5b40bf0f99a6`
- Original v0.1 protocol SHA256: `f7ff69020dac14491569b1764aef1bd0638e9dd15717af6ca16d75835cf35ec5`
- Runtime checkpoint: `e6b02f6e37534008427cb18cd06ce7f086153103`
- Benchmark checkpoint: `bc1b389bdb6c4eb0c5c4c629af549a6904a37477`
- Benchmark SHA256: `29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6`
- Benchmark manifest SHA256: `bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae`
- Western corpus chunks SHA256: `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b`
- Western source registry SHA256: `722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703`
- Protocol freeze commit: resolved deterministically from Git history for this immutable `protocol.json`; Stage A requires HEAD to equal that commit and the worktree to be clean.

## Amendment scope

This is a pre-execution safety amendment. It repairs formal retrieval retry records, terminal-cell sealing, Stage-A-only finalization, complete run identity, exact-matrix validation, and downstream propagation of retrieval technical missingness.

No formal v0.1 result existed or was inspected. No benchmark question or formal cell was executed while preparing this amendment. The scientific design is unchanged: W-RQ1/W-RQ2/W-RQ3; all 48 cases and gold evidence; R0–R3 definitions, top-k, candidate depth, models, prompts, metrics, insufficient-evidence definitions, balanced 192-cell order, and planned comparison families remain frozen.

## Execution safety

- Every Stage A cell terminates as `success` or `technical_failure` with a complete retry/provider trace.
- One technical retry event is permitted per cell, scoped to the failed dense or reranker operation.
- An R0/local defect, invariant failure, corrupt checkpoint, input mismatch, or protocol-path violation stops the run unsealed.
- Stage A seals only with the exact 192 frozen `(case_id, retrieval_condition)` pairs in terminal states.
- Retrieval quality excludes technical failures without zero imputation and reports exact missingness denominators.
- Pairwise statistics use the successful-pair intersection.
- Stage A finalizes independently into immutable Stage-A-only artifacts.
- Stage A technical failures are retained downstream without calling Qwen or GLM and are not interpreted as abstention, insufficiency handling, content failure, or model failure.
- A sealed Stage A cannot resume or overwrite; a repeat requires a new run ID.

The original v0.1 protocol directory and freeze record remain unchanged as historical evidence of the unused, superseded protocol.
