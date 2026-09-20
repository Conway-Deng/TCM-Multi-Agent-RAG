# Operator-supplied discovery inputs

This directory intentionally contains no current provider data. Before Wave-2 discovery is frozen, an operator must supply all three artifacts with one identical timezone-aware `snapshot_timestamp`:

- `provider-model-catalog.json`: `artifact_type`, `provider="siliconflow"`, `snapshot_timestamp`, `source_endpoint="/v1/models"`, `semantic_or_generation_outputs_used=false`, `live_completion_calls_used=false`, and `models`, each containing exactly one non-empty `model_id`.
- `pricing-ledger.json`: matching identity fields and one entry per catalog model with exact string-valued `input_price` and `output_price`; unknown prices are represented by `null`.
- `capability-ledger.json`: matching identity fields, `non_semantic_evidence_only=true`, and one entry per catalog model documenting model type, endpoint and JSON-object compatibility, availability/access, required thinking toggle, aliases, evidence reference, and whether a candidate-specific interface change is required.

No completion or generation output may be included or used. The offline freeze tooling rejects duplicate IDs, mismatched timestamps, incomplete ledgers, extra ledger entries, omitted dispositions, and unknown eligibility facts.
