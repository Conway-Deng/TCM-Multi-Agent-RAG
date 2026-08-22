# RQ1 Confirmatory Semantic Review Summary

## Review scope

- Semantic comparison rows reviewed: 422
- Unique benchmark questions represented in the packet: 97
- Anonymous systems: SYSTEM_A, SYSTEM_B

## Labels

- SUPPORTED: 374
- PARTIALLY_SUPPORTED: 7
- NOT_SUPPORTED: 36
- CONTRADICTED: 5
- UNRESOLVED: 0

## Anonymous-system row counts

| anonymous_system_label   |   CONTRADICTED |   NOT_SUPPORTED |   PARTIALLY_SUPPORTED |   SUPPORTED |
|:-------------------------|---------------:|----------------:|----------------------:|------------:|
| SYSTEM_A                 |              2 |              18 |                     4 |         188 |
| SYSTEM_B                 |              3 |              18 |                     3 |         186 |

## Method

Each Gold atomic fact was compared against the supplied answer using the frozen source-grounded semantic rubric. The supplied evidence was treated as the benchmark evidence basis; no external TCM or medical knowledge was used to repair or reinterpret the Gold reference.

This is AI-assisted semantic evaluation, not independent human validation and not clinical/TCM-expert validation.

## Next step

Import `semantic_review_completed.csv` into the frozen confirmatory pipeline. The pipeline should validate the item IDs and labels, unblind the anonymous system mapping only according to the locked experiment manifest, compute the pre-registered paired question-level statistics, and close out RQ1 without changing the benchmark, protocol, or 5-percentage-point practical-effect threshold.
