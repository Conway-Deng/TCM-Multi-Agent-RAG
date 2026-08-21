# Project-owner GPT review spot-check

This is an AI-assisted semantic evaluation with project-owner spot-check. It is not independent human ground truth or clinical/TCM expert validation.

The owner checks whether the existing GPT comparison appears reasonable based on Gold versus Answer. No medical correctness judgment is required.

Launch from the repository root:

    .\.venv\Scripts\python.exe research\experiments\rq1_c1_vs_c2\formal_pass_1_retry_20260821\semantic_validation\owner_audit_20\reviewer\reviewer_server.py

Open http://127.0.0.1:8767. Save to owner_audit_results.json. Choices are AGREE, DISAGREE, and UNSURE.
