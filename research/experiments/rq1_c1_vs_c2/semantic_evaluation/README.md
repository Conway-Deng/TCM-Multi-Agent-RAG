# Frozen semantic review instructions

This packet is for AI-assisted semantic evaluation using the same frozen source-grounded rubric as Formal Pass 1. The reviewer is NOT judging whether the TCM knowledge is clinically true. Judge only: “Does the Answer express the substantive meaning of the Gold atomic fact?” Use only the Question, Gold atomic fact, supplied evidence, and Answer. Do not use external medical/TCM knowledge. Paraphrases are allowed; exact wording is not required.

Allowed labels:
- SUPPORTED: full substantive meaning expressed
- PARTIALLY_SUPPORTED: meaningful portion expressed but an important component is missing
- NOT_SUPPORTED: Gold meaning is absent
- CONTRADICTED: Answer conflicts with Gold
- UNRESOLVED: genuinely ambiguous

Leave review_label, review_reason, and confidence blank in this export. Future confidence values are HIGH, MEDIUM, or LOW. Preserve item_id. SYSTEM_A and SYSTEM_B are anonymous. Do not infer relationships not established by Gold.

Files: repeat_2_for_gpt.csv, repeat_3_for_gpt.csv, repeats_2_and_3_for_gpt.csv.
