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
    assert "<span>Step 4</span>Runtime model" in HTML
    assert 'id="consensus-model-target"' in HTML
    assert '<option value="qwen" selected>Qwen · Qwen/Qwen3-8B</option>' in HTML
    assert '<option value="glm">GLM · THUDM/GLM-Z1-9B-0414</option>' in HTML
    assert '<option value="deepseek">DeepSeek · deepseek-ai/DeepSeek-R1-0528-Qwen3-8B</option>' in HTML
    assert HTML.count('name="runtime-model"') == 3
    assert 'name="runtime-model" value="qwen" checked' in HTML
    assert 'name="runtime-model" value="glm"' in HTML
    assert 'name="runtime-model" value="deepseek"' in HTML
    assert "bindChoiceGroup('runtime-model', '#consensus-model-target')" in JS
    assert "model_target: $('#consensus-model-target').value" in JS
    assert "model_profile" not in JS
    assert "Manual runtime selection for interactive demonstration; formal experiment configurations are reported separately." in HTML


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
