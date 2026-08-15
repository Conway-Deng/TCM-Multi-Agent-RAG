# Judge architecture

Judges evaluate structured outputs and never rewrite the answer.

- Evidence: support, citation coverage, source alignment.
- Hallucination: unsupported claims and fabricated evidence IDs.
- Safety: dangerous advice, dosing/prescribing, procedures, emergencies, excessive certainty.
- Conflict: disagreement and unresolved conflict disclosure.
- Confidence/Uncertainty: calibration, uncertainty, abstention preference.
- Citation/Provenance: evidence/source existence and mapping integrity.

No-key judges are deterministic rubrics. Evaluator providers can be added through the provider interface. Scores are predictions and research signals, not objective ground truth; RQ2 classification metrics require legitimate independent labels.
