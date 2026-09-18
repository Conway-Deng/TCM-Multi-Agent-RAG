# MediRAG-West Formal Evaluation Protocol v0.1 — Frozen

## Freeze identity

- Freeze date/time: `2026-09-18T16:09:39+08:00`
- Protocol version: `western-formal-v0.1`
- Protocol SHA256 (`protocol.json`): `f7ff69020dac14491569b1764aef1bd0638e9dd15717af6ca16d75835cf35ec5`
- Runtime checkpoint: `e6b02f6e37534008427cb18cd06ce7f086153103`
- Benchmark checkpoint: `bc1b389bdb6c4eb0c5c4c629af549a6904a37477`
- Benchmark SHA256: `29d4a2c08bd8529f77d7d9faff7e739a5c60775dd04d99711d0e254a7aa200c6`
- Benchmark manifest SHA256: `bd8fc5105329d5d325fa8910b8a642bac6ddc954a25df6b9e299158aa29a22ae`
- Western corpus chunks SHA256: `8c53511e6193ebccea70c59f121fd456b5749b1e40a16eaeda3a4e53515a752b`
- Western source registry SHA256: `722273140906b238e88cfdab4ddbb12d73c478f686ae23d0f501738ee6820703`

## Formal matrix

- Frozen cases: 48
- Retrieval conditions: R0, R1, R2, R3
- Intended generation cells: 192
- Generations per cell: 1
- Final retrieval `top_k`: 4
- Headline retrieval denominator: 42 supported or partially-supported cases with non-empty primary gold
- Insufficient-evidence stress subset: 6 cases, reported separately

## Retrieval conditions

- **R0:** existing deterministic BM25-like lexical retrieval.
- **R1:** existing dense cosine pathway using SiliconFlow `BAAI/bge-m3`.
- **R2:** existing lexical+dense reciprocal-rank fusion with constant 60.
- **R3:** existing R2 hybrid candidates, fixed candidate/rerank depth 12, followed by SiliconFlow `BAAI/bge-reranker-v2-m3`.

No new retrieval algorithm is introduced by this protocol.

## Fixed generator

- Provider: SiliconFlow
- Model: `Qwen/Qwen3-8B`
- Temperature: 0
- Maximum tokens: 256
- Evidence excerpt maximum: 1000 characters per retrieved item
- Timeout: 120 seconds
- Prompt/contract: current frozen `WesternEvidenceAgent` prompt and contract, unchanged

## Fixed automated judge

- `judge_type=automated_secondary_model`
- Provider: SiliconFlow
- Model: `THUDM/GLM-Z1-9B-0414`
- Temperature: 0
- Maximum tokens: 1200
- Timeout: 120 seconds
- `human_verified=false`
- `domain_expert_verified=false`

The judge is not a human, clinician, physician, or domain expert. Synthetic non-benchmark preflight confirmed provider reachability, actual model identity, raw structured-JSON compliance, and parsing of supported, unsupported, and insufficient labels.

## Frozen metrics

Primary retrieval metrics are macro and aggregate Primary-Gold Chunk Recall@4, macro and aggregate Primary-Source Recall@4, MRR of the first primary gold chunk, and Hit@4. Primary-or-secondary gold metrics are secondary diagnostics only.

Generation evaluation freezes claim-support, partial-support, unsupported-claim, expected-evidence-point coverage, appropriate insufficiency handling, deterministic provenance integrity, observable scope behavior, separate retrieval/generation/judge latency, and provider reliability metrics as defined in `metric_definitions.md`.

Primary paired comparisons are R0–R1, R0–R2, and R0–R3. The protocol reports paired differences, exact sample sizes, McNemar for applicable paired binary outcomes, and 95% paired bootstrap confidence intervals where implemented, without winner language.

## Retry, ordering, and immutable stages

At most one retry is permitted only for connectivity failure, HTTP 5xx, timeout, or malformed transport response. Content or quality failures are never retried. The committed balanced rotation in `execution_order.json` is immutable.

Stage A retrieval is sealed before Stage B generation. Stage B is sealed before Stage C judging. Each stage is hash-verified, resumable by unique `(case_id, retrieval_condition)`, and rejects duplicate cells. Formal outputs are never overwritten; a repeated run requires a new `run_id`.

## Scope and execution status

This protocol evaluates only the frozen 16-source, 271-chunk Western pilot corpus. It does not measure general medical competence, comprehensive medical correctness, diagnosis or treatment quality, clinical safety, physician performance, or comprehensive guideline adherence.

No formal benchmark case or formal generation cell was executed while designing, validating, or freezing this protocol.
