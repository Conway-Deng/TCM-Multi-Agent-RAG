from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "research-app.js").read_text(encoding="utf-8")


def test_research_selector_uses_controlled_c1_and_separates_legacy_demo() -> None:
    assert "C1 · Single-RAG baseline" in HTML
    assert "Legacy Demo" in HTML
    assert "16-entry compatibility fixture. Not used for formal experiments" in HTML
    assert "/api/custom-runs" in JS
    assert "Use Research Compare C1" not in HTML


def test_navigation_and_results_contract_is_present() -> None:
    assert 'data-view="home"' in HTML
    assert 'data-view="workbench"' in HTML
    assert "setView('home'" in JS
    assert "setView('workbench'" in JS
    assert "is-workbench" in JS
    assert "history.pushState" in JS
    assert "popstate" in JS
    assert "aria-selected" in JS
    assert "cursor: pointer" in (ROOT / "styles.css").read_text(encoding="utf-8")
    assert "Active-agent evidence support" in HTML
    assert "Specialist coverage" in HTML
    assert "not medical correctness" in HTML
    assert "consensus-evidence" in HTML
    assert "evidence-citation" in JS


def test_export_contract_is_secret_safe_and_supports_run_and_compare() -> None:
    assert "Download JSON" in HTML
    assert "Download CSV" in HTML
    assert "Download Comparison JSON" in HTML
    assert "Download Comparison CSV" in HTML
    assert "safeRunExport" in JS
    assert "API_KEY" not in JS
    assert "backend/.env" not in JS


def test_custom_model_assignment_and_batch_payload_contract() -> None:
    assert "<span>Step 4</span>Model assignments" in HTML
    assert all(f'id="specialist-model-{seat}"' in HTML for seat in ("a", "b", "c"))
    assert 'id="custom-consensus-model"' in HTML
    assert 'id="custom-question-count"' in HTML
    for count in ("1", "5", "10", "20", "50", "100", "custom"):
        assert f'<option value="{count}"' in HTML
    assert "specialist_model_targets:" in JS
    assert "consensus_model_target:" in JS
    assert "...selectedModelConfigurationPayload()" in JS
    payload_source = JS[JS.index("function selectedModelConfigurationPayload"):JS.index("function selectedCustomQuestionCount")]
    assert "model_profile:" not in payload_source
    assert "\n      model_target:" not in payload_source
    assert "questions: questions.slice(0, requestedCount)" in JS
    assert "await api('/api/custom-runs'" in JS
    assert "Run Custom Experiment" in HTML


def test_custom_mode_remains_exploratory_and_trace_diagnostics_remain() -> None:
    assert "C1 uses only Specialist A" in HTML
    assert "Custom runs are exploratory and do not reproduce a formal paper experiment." in HTML
    assert "Models in provider attempts" in HTML
    assert "attemptedModels" in JS
    assert ".map((attempt) => attempt.model).filter(Boolean)" in JS


def test_runtime_result_diagnostics_are_truthful_and_complete() -> None:
    for label in (
        "Requested model",
        "Actual model",
        "Provider calls",
        "Successful provider calls",
        "Failed provider calls",
        "Generation mode",
        "Fallback",
        "Run trace, including provider attempts",
    ):
        assert label in HTML
    assert "traceData.provider_attempts" in JS
    assert "traceData.fallback_usage === true ? 'Yes' : 'No'" in JS
    assert "No successful model output" in JS
    assert "JSON.stringify(safeRunExport(data), null, 2)" in JS
