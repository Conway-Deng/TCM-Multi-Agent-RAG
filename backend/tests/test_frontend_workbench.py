from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "research-app.js").read_text(encoding="utf-8")


def test_research_selector_uses_controlled_c1_and_separates_legacy_demo() -> None:
    assert "C1 · Single-RAG baseline" in HTML
    assert "Legacy Demo" in HTML
    assert "16-entry compatibility fixture. Not used for formal experiments" in HTML
    assert "/api/research/run" in JS
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


def test_runtime_model_selector_and_payload_contract() -> None:
    assert "<span>Step 4</span>Interactive model configuration" in HTML
    assert "Single-model test" in HTML
    assert "Multi-agent configuration" in HTML
    assert 'id="consensus-model-target"' in HTML
    assert 'id="consensus-model-profile"' in HTML
    assert '<option value="qwen" selected>Qwen · Qwen/Qwen3-8B</option>' in HTML
    assert '<option value="glm">GLM · THUDM/GLM-Z1-9B-0414</option>' in HTML
    assert '<option value="deepseek">DeepSeek · deepseek-ai/DeepSeek-R1-0528-Qwen3-8B</option>' in HTML
    assert HTML.count('name="interactive-model-configuration"') == 5
    assert 'name="interactive-model-configuration" value="target:qwen" checked' in HTML
    assert 'name="interactive-model-configuration" value="target:glm"' in HTML
    assert 'name="interactive-model-configuration" value="target:deepseek"' in HTML
    assert 'name="interactive-model-configuration" value="profile:M1"' in HTML
    assert 'name="interactive-model-configuration" value="profile:M2"' in HTML
    assert "profile ? { model_profile: profile } : { model_target: $('#consensus-model-target').value || 'qwen' }" in JS
    assert "...selectedModelConfigurationPayload()" in JS
    assert "Qwen × 3 specialist seats" in HTML
    assert all(label in HTML for label in ("Qwen ✓", "GLM ✓", "DeepSeek ✓"))
    assert "Interactive multi-model routing; formal A3 results were produced by a separate frozen experimental protocol." in HTML
    assert "Formal A3 reproduction" not in HTML
    assert "Published experiment rerun" not in HTML


def test_multi_model_profile_warning_and_trace_diagnostics() -> None:
    assert "Multi-model profiles are most meaningful with a multi-agent architecture such as C2; C1 has only one active specialist seat." in HTML
    assert "condition === 'C1' && $('#consensus-model-profile').value" in JS
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
