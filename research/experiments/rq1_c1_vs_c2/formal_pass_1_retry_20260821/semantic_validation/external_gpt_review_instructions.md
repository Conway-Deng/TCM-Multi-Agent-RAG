# External GPT semantic review instructions

This packet contains the existing frozen 60-item blinded sample. Do not change item_id values.

The reviewer is NOT evaluating whether the TCM/medical information is clinically true.

The only question is:

"Does the supplied ANSWER express the meaning of the supplied GOLD ATOMIC FACT?"

Use only the Question, Gold atomic fact, supplied evidence, and Answer. Do NOT use external medical knowledge.

Labels:

- SUPPORTED: The answer clearly expresses the full substantive meaning of the Gold fact. Paraphrases are allowed.
- PARTIALLY_SUPPORTED: The answer expresses a meaningful part of the Gold fact but omits an important component.
- NOT_SUPPORTED: The Gold fact is absent from the answer.
- CONTRADICTED: The answer states something incompatible with the Gold fact.
- UNRESOLVED: The comparison is genuinely ambiguous.

For each item return item_id, review_label, short review_reason, and confidence (HIGH, MEDIUM, or LOW). Leave no item out and do not alter item_id. Do not infer an herb–syndrome relationship that is not established by the supplied material.

This is AI-assisted semantic review, not automatically human validation. A later owner confirmation must be recorded separately.
