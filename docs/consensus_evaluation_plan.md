# ARCHIVED PRE-V1: Consensus Evaluation Plan

Inactive historical design. Use `docs/evaluation_methodology.md`.

The synthetic benchmark covers evidence-supported, insufficient-information, out-of-scope, urgent-safety, deliberate-conflict, unsupported-claim, and agreement cases.

Automated metrics:

- schema validity rate
- evidence-ID coverage
- unsupported-claim detection rate
- urgent-safety detection rate
- abstention preservation rate
- disagreement preservation rate
- fixture-label accuracy
- pipeline success rate
- fallback rate
- mean latency
- API-call count
- model-call failure count

The manual-review CSV includes factual accuracy, completeness, relevance, explainability, safety, evidence support, and preference columns. Those fields require qualified human review; they are intentionally not auto-scored.

Run deterministic CI mode:

```powershell
cd backend
python -m evaluation.run_consensus_evaluation --no-llm
```

No-LLM mode is a reproducible orchestration test, not a clinical benchmark. Future experiments should compare repeated runs, judge-human agreement, order sensitivity, and evidence-fixed same-model versus heterogeneous-model conditions.
