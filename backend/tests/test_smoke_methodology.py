from smoke_classification import classify_smoke_run


def test_clean_retry_is_not_a_provider_failure() -> None:
    assert classify_smoke_run(generation_mode="llm", fallback=False, provider_attempted=2, provider_succeeded=1, output_quality_pass=True, evidence_count=4, expected_evidence=True) == "PASS_WITH_RETRY"


def test_empty_intentional_abstention_is_not_corruption() -> None:
    assert classify_smoke_run(generation_mode="abstention", fallback=False, provider_attempted=0, provider_succeeded=0, output_quality_pass=False, evidence_count=0, expected_evidence=False) == "CORRECT_ABSTENTION"


def test_supported_entity_scope_gate_is_routing_failure() -> None:
    assert classify_smoke_run(generation_mode="abstention", fallback=False, provider_attempted=0, provider_succeeded=0, output_quality_pass=False, evidence_count=0, expected_evidence=True, termination_stage="planner_scope_gate") == "FAIL_ROUTING"
