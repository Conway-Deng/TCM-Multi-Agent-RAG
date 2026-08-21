# Frozen semantic Gold scoring protocol

## Atomic labels

- **SUPPORTED** — the answer clearly expresses the full substantive meaning of the Gold fact; paraphrases are allowed.
- **PARTIALLY_SUPPORTED** — a meaningful part is expressed, but an important component is omitted.
- **NOT_SUPPORTED** — the Gold fact is absent.
- **CONTRADICTED** — the answer states information incompatible with the Gold fact.
- **UNRESOLVED** — the supplied material is too ambiguous to assign another label safely.

Review only the frozen Gold fact, supplied evidence excerpt, and answer. Do not use external medical knowledge, reward plausible-sounding claims, require exact strings, or infer an herb–syndrome relationship when the Gold relationship is not established. Judge each target independently.

## Metrics

For each of C1, C2, and the paired usable subset:

- Full recall = SUPPORTED / evaluable Gold facts
- Partial-or-better recall = (SUPPORTED + PARTIALLY_SUPPORTED) / evaluable Gold facts
- Contradiction rate = CONTRADICTED / evaluable Gold facts
- Missing Gold rate = NOT_SUPPORTED / evaluable Gold facts

UNRESOLVED facts are excluded from evaluable denominators and reported separately.

## Blinded human validation

The 60-item sample uses a fixed seed (20260821), randomized order, and anonymous SYSTEM_A/SYSTEM_B labels. Human labels must be collected before any Judge predictions are revealed. No C1/C2 identity or aggregate result is shown in the reviewer.

## Judge protocol (defined, not run)

Input: QUESTION, GOLD FACT, GOLD EVIDENCE, ANSWER. Output strict JSON only with keys label, reason, and quoted_answer_support. The label must be one of the five allowed labels. The Judge uses only supplied material, treats paraphrases semantically, avoids unsupported relationships, and gives a short reason. judge_model=TO_BE_FROZEN; no Judge call has been executed. After human labels, measure accuracy, macro F1, confusion matrix, Cohen's kappa, and per-label performance where sample size permits.
