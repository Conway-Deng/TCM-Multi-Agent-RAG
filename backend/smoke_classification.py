from __future__ import annotations


def classify_smoke_run(
    *, generation_mode: str, fallback: bool, provider_attempted: int,
    provider_succeeded: int, output_quality_pass: bool, evidence_count: int,
    expected_evidence: bool, termination_stage: str = "completed",
) -> str:
    """Classify a completed smoke run without treating abstention as corruption."""
    if generation_mode == "abstention" and evidence_count == 0:
        if expected_evidence and termination_stage == "planner_scope_gate":
            return "FAIL_ROUTING"
        return "COVERAGE_GAP" if expected_evidence else "CORRECT_ABSTENTION"
    if generation_mode == "llm" and not fallback and output_quality_pass and provider_succeeded:
        return "PASS_WITH_RETRY" if provider_attempted > provider_succeeded else "PASS"
    if fallback or (provider_attempted > provider_succeeded and not provider_succeeded):
        return "FAIL_PROVIDER"
    if not output_quality_pass:
        return "FAIL_OUTPUT_QUALITY"
    return "FAIL_PROVIDER" if provider_attempted > provider_succeeded else "COVERAGE_GAP"
