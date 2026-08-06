# TCM-RAG Evaluation

Run from `backend/` or the project root with backend dependencies available:

```powershell
python -m evaluation.run_evaluation --no-llm
```

Outputs:

- `backend/evaluation/results/last_results.json`
- `backend/evaluation/results/manual_review.csv`

The automated metrics cover routing, abstention, citation structure, retrieval behavior, and language consistency. They do not prove medical correctness.

For the synthetic consensus-orchestration benchmark:

```powershell
python -m evaluation.run_consensus_evaluation --no-llm
```

This compares TCM-only, direct combination, deterministic weighted aggregation, same-model debate, and same-model debate-plus-judge configurations. Western outputs are synthetic fixtures for orchestration testing, not verified medical evidence.
