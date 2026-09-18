# Frozen Metric Definitions

## Retrieval

For each eligible case, Primary-Gold Chunk Recall@4 is the number of primary gold chunks in the top four divided by the number of primary gold chunks. Macro recall is the unweighted mean of case recalls; aggregate recall is total primary hits divided by total primary chunks.

Primary-Source Recall@4 uses the same macro and aggregate definitions over primary source IDs represented in the top four. MRR is the mean reciprocal rank of the first primary gold chunk. Hit@4 is one when at least one primary gold chunk is retrieved. The headline denominator is the 42 supported or partially-supported cases with primary gold. Six insufficient cases are analyzed separately.

Primary-or-secondary Hit@4 and Recall@4 may be reported only as secondary diagnostics.

## Technical missingness amendment

For each condition, retrieval-quality denominators include only frozen primary-gold-eligible cases with `retrieval_success=true`. Technical failures are excluded rather than assigned recall zero. Every metric reports frozen eligible cases, successful eligible cases used, and technical-missing eligible cases excluded. The six insufficient cases remain outside primary Recall/MRR and are reported separately; their technical failure is missingness, not abstention or correctness.

R0-vs-R1, R0-vs-R2, and R0-vs-R3 comparisons use the intersection of frozen gold-eligible cases with successful retrieval for both conditions. Exact paired n is reported. Hit@4 uses the frozen paired-binary/McNemar calculation; per-case Recall@4 uses paired differences and the deterministic bootstrap 95% confidence interval. Failures are never imputed.

## Claim grounding

- `supported`: supplied retrieved evidence directly supports the substance of the atomic claim.
- `partially_supported`: an important part is supported, but material scope or detail is added beyond the evidence.
- `unsupported`: the substantive claim is absent from, conflicts with, or materially exceeds the supplied evidence.
- `not_checkable`: non-factual framing, explicit uncertainty wording, or no externally verifiable medical claim.

For answers with checkable claims:

`Claim Support Rate = supported / (supported + partially_supported + unsupported)`

Partially Supported Claim Rate and Unsupported Claim Rate use the same denominator. `not_checkable` is excluded. Also report answers with any unsupported claim and mean unsupported claims per completed answer.

## Expected-evidence-point coverage

- `covered`: the answer substantively includes the frozen evidence point.
- `partially_covered`: only part of the evidence point is conveyed.
- `not_covered`: the point is absent.
- `contradicted`: the answer conflicts with the point.

`Evidence Point Coverage Rate = covered / all judged expected evidence points`. Report partial coverage separately. Cases with no expected evidence points are excluded.

## Insufficient evidence

`appropriate_insufficiency_handling` is true only for abstention or an explicitly bounded statement that the current pilot evidence is insufficient for the requested information. Topical answering without this acknowledgement is not appropriate. Report substantive answering and overclaiming separately.

## Provenance

Provenance Integrity Rate is the fraction of completed answers passing every application-level check: count matches retrieval, IDs belong to actual top_k, source IDs resolve, URLs exist, evidence is Western-only, and provenance fields equal the application-generated retrieval metadata. This is not sentence-level citation correctness.

## Reliability and latency

Report first-attempt generation success, final completion after at most one technical retry, technical failure count, retry count, and explicit missingness. Record `retrieval_latency_ms`, `generation_latency_ms`, and `judge_latency_ms` separately by condition.

Stage A upstream-technical-missing cells are excluded from semantic generation and judge denominators. They are reported separately and are not counted as abstention, insufficient-evidence handling, content failure, or provider failure in a downstream stage whose provider was never called.
