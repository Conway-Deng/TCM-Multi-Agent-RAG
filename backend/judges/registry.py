JUDGE_REGISTRY = [
    {"id": "evidence", "name": "Evidence Judge", "evaluates": ["claim support", "citation coverage", "source alignment"]},
    {"id": "hallucination", "name": "Hallucination Judge", "evaluates": ["unsupported claims", "fabricated citations"]},
    {"id": "safety", "name": "Source-Grounded Safety Judge", "evaluates": ["source-grounded safety flags", "evidence-supported caution assessment"]},
    {"id": "conflict", "name": "Conflict Judge", "evaluates": ["agent disagreement", "unresolved conflicts", "hidden disagreement"]},
    {"id": "confidence", "name": "Evidence Confidence Judge", "evaluates": ["evidence confidence", "response reliability indicators"]},
    {"id": "provenance", "name": "Citation and Provenance Judge", "evaluates": ["evidence IDs", "source existence", "citation mapping"]},
]
