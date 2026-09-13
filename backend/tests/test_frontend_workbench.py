from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "research-app.js").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


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


def test_custom_question_textarea_has_multi_question_helper() -> None:
    assert "For multiple questions, enter one question per line in this box." in HTML
    textarea_position = HTML.index('id="consensus-question"')
    helper_position = HTML.index("For multiple questions, enter one question per line in this box.")
    assert helper_position > textarea_position
    assert "For multiple questions, enter one question per line above. The selected count determines how many lines are run." in HTML


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


def test_custom_cloud_result_renders_persisted_evidence_and_runtime_metadata() -> None:
    rendering = JS[JS.index("function renderResearchRun(data)"):JS.index("function renderCompare(data)")]
    assert "const integratedPanel = $('#integrated-judge-panel')" in rendering
    assert "if (integratedPanel)" in rendering
    assert rendering.index("renderEvidence(data)") < rendering.index("setText('#consensus-latency'")
    assert "(data.retrieval || []).forEach" in JS
    assert "card.id = item.chunk_id" in JS
    assert "(data.retrieval || []).length" in JS
    for selector in (
        "#consensus-latency", "#consensus-requested-model", "#consensus-model",
        "#consensus-attempted-models", "#consensus-provider", "#consensus-api-calls",
        "#consensus-successful-calls", "#consensus-call-failures",
        "#consensus-generation-mode", "#consensus-fallback", "#consensus-corpus",
        "#consensus-fixture-used", "#consensus-embedding", "#consensus-reranker",
        "#consensus-participating", "#consensus-abstaining", "#consensus-stages",
        "#consensus-score-formula",
    ):
        assert f"setText('{selector}'" in rendering


def test_custom_runtime_renderer_does_not_fabricate_missing_metadata() -> None:
    rendering = JS[JS.index("function renderResearchRun(data)"):JS.index("function renderCompare(data)")]
    assert "const requestedModel = requestedModelParts.join(' · ') || '—'" in rendering
    assert "attemptedModels.join(', ') || '—'" in rendering
    assert "typeof traceData.fallback_usage === 'boolean'" in rendering
    assert "typeof traceData.latency_ms === 'number'" in rendering
    assert "traceData.support_score_formula || '—'" in rendering
    assert "Provider not reported" not in rendering
    assert "traceData.experiment_config?.specialist_model_targets || [$('#specialist-model-a').value" not in rendering


def test_guided_and_custom_runs_expose_graceful_stop_and_partial_downloads() -> None:
    assert 'id="stop-formal-run"' in HTML
    assert 'id="stop-custom-run"' in HTML
    assert 'id="formal-stop-summary"' in HTML
    assert 'id="custom-partial-downloads"' in HTML
    assert "/api/formal-runs/" in JS and "+ '/stop'" in JS
    assert "/api/custom-runs/" in JS
    assert "Download Partial Report" in JS
    assert "Partial replay — not directly comparable to the complete paper result." in JS
    assert "['queued', 'running', 'stop_requested']" in JS


def test_saved_custom_run_restore_distinguishes_active_and_terminal_states() -> None:
    refresh = JS[JS.index("async function refreshCustomRun"):JS.index("async function resumeSavedCustomRun")]
    resume = JS[JS.index("async function resumeSavedCustomRun"):JS.index("async function stopCustomRun")]
    assert "refreshCustomRun(restored = false)" in refresh
    assert "['queued', 'running', 'stop_requested'].includes(status.status)" in refresh
    assert "if (customActive && !researchProgressTimer) startResearchProgress()" in refresh
    assert "setResearchControlsDisabled(false)" in refresh
    assert "Restored completed run." in refresh
    assert "setResearchProgressVisualState('restoring')" in resume
    assert "await refreshCustomRun(true)" in resume


def test_new_custom_run_clears_previous_result_before_queueing() -> None:
    clearing = JS[JS.index("function clearCustomResultDisplay"):JS.index("let activeCustomRunId")]
    submit = JS[JS.index("$('#consensus-form').addEventListener('submit'"):JS.index("$('#research-compare-form')")]
    assert "currentResearchRun = null" in clearing
    assert "$('#consensus-results').hidden = true" in clearing
    assert "$('#consensus-trace').textContent = ''" in clearing
    assert "'#consensus-evidence'" in clearing
    assert "'#consensus-agents'" in clearing
    assert submit.index("clearCustomResultDisplay()") < submit.index("startResearchProgress()")
    assert submit.index("clearCustomResultDisplay()") < submit.index("await api('/api/custom-runs'")


def test_custom_progress_animates_only_for_active_states() -> None:
    assert "new Set(['queued', 'running', 'stop_requested'])" in JS
    assert "setResearchProgressVisualState('queued')" in JS
    assert "progress.classList.toggle('is-terminal', !active)" in JS
    assert "stopResearchProgress(status.status === 'complete' ? 'complete' : status.status === 'stopped' ? 'stopped' : 'failed')" in JS
    assert ".research-progress-bar span" in CSS and "animation: research-progress" in CSS
    assert ".research-progress.is-terminal .research-progress-bar span { animation: none; transform: none; }" in CSS
    assert ".research-progress.is-complete .research-progress-bar span { width: 100%; }" in CSS
    assert ".research-progress.is-stopped .research-progress-bar span" in CSS
    assert ".research-progress.is-failed .research-progress-bar span" in CSS


def test_guided_progress_and_rendering_contract_remain_separate() -> None:
    assert "function refreshFormalRun" in JS
    assert "function renderFormalStatus" in JS
    assert "Run Paper Experiment" in HTML
    assert "clearCustomResultDisplay()" not in JS[JS.index("function refreshFormalRun"):JS.index("function selectFormalExperiment")]
