JUDGE_REGISTRY = [
    {"id": "evidence", "name": "Evidence Judge", "evaluates": ["claim support", "citation coverage", "source alignment"]},
    {"id": "hallucination", "name": "Hallucination Judge", "evaluates": ["unsupported claims", "fabricated citations"]},
    {"id": "safety", "name": "Safety Judge", "evaluates": ["unsafe advice", "dosing", "dangerous instructions", "excess certainty"]},
    {"id": "conflict", "name": "Conflict Judge", "evaluates": ["agent disagreement", "unresolved conflicts", "hidden disagreement"]},
    {"id": "confidence", "name": "Confidence and Uncertainty Judge", "evaluates": ["calibration", "uncertainty", "abstention"]},
    {"id": "provenance", "name": "Citation and Provenance Judge", "evaluates": ["evidence IDs", "source existence", "citation mapping"]},
]
