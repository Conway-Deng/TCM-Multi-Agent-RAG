# RQ4 External Source-Grounded Review Summary

## Scope

- Candidate benchmark questions: 100
- Atomic Gold rows reviewed: 232
- Review basis: supplied corpus excerpts only
- Clinical/TCM truth assessment: NOT performed
- External knowledge used: NO

## Row-level result

- APPROVE: 195
- REVISE: 37
- REMOVE: 0
- UNRESOLVED: 0

## Question-level result

- Questions fully APPROVED: 80 / 100
- Questions requiring REVISION: 20 / 100

## Revision reasons

### 1. Cross-reference-only benchmark targets

17 questions contain at least one herb function/indication Gold fact whose source content is only a `See ...` cross-reference rather than substantive function/indication text:

rq4-v1-001, rq4-v1-004, rq4-v1-007, rq4-v1-008, rq4-v1-015, rq4-v1-018, rq4-v1-026, rq4-v1-044, rq4-v1-045, rq4-v1-048, rq4-v1-050, rq4-v1-051, rq4-v1-055, rq4-v1-057, rq4-v1-086, rq4-v1-088, rq4-v1-097

For row-level precision, only the cross-reference Gold rows are marked `REVISE`; directly supported used-part or syndrome rows in those questions remain `APPROVE`. Because each affected question contains at least one `REVISE` row, the question should be replaced or revised before freeze.

Cross-reference rows marked REVISE: 31

### 2. Prompt/Gold completeness mismatch

3 questions ask for **function, indication, and used part**, but the supplied Gold/evidence packet contains only function and indication, with no used-part Gold/evidence fact:

rq4-v1-002, rq4-v1-019, rq4-v1-039

All rows belonging to these questions are marked `REVISE` so that the question is not frozen in an incomplete form.

Rows marked REVISE for this reason: 6

## Overall disposition

The candidate benchmark should **NOT be frozen yet**.

Recommended next state:

`BENCHMARK_REVISION_REQUIRED`

Revise/replace the 20 affected questions, regenerate the external source-review packet, and submit the revised packet for one more source-grounded review cycle.

All other reviewed rows are directly supported by the supplied source excerpts and align with the requested source-recorded field.

This review validates source grounding and prompt/Gold alignment only. It is not clinical validation, TCM-expert validation, or independent human semantic validation.
