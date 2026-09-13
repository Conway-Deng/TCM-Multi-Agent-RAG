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
    assert "Download Selected JSON" in HTML
    assert "Download Selected CSV" in HTML
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
    assert 'class="selection-help custom-question-helper"' in HTML
    assert ".custom-question-helper" in CSS
    assert "font-weight: 600" in CSS
    assert "background: rgba(39,95,131,.05)" in CSS
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


def test_guided_formal_results_use_incremental_lightweight_execution_cards() -> None:
    formal = JS[JS.index("let formalExperiments"):JS.index("async function startFormalRun")]
    loading = JS[JS.index("async function loadFormalResults"):JS.index("async function startFormalRun")]
    assert "let formalResultCursor = 0" in formal
    assert "const formalResultRows = new Map()" in formal
    assert "const FORMAL_SUMMARY_FIELDS" in formal
    assert "compactFormalSummary({ ...execution, sequence })" in loading
    assert "orderedFormalResultRows()" in formal
    assert "formalResultRows.set(sequence" in loading
    assert "formalResultCursor = Math.max(formalResultCursor, after)" in loading
    assert "'/summaries?after=' + after + '&limit=50'" in loading
    assert "do {" in loading and "} while (data.has_more)" in loading
    assert "requestedRunId !== activeFormalRunId" in loading
    assert "renderFormalExecutionCards(Number(data.status?.total || orderedRows.length), data.status)" in loading
    assert "String(execution.sequence).padStart(3, '0') + ' / ' + total" in formal
    assert "execution.case_id || '—'" in formal and "execution.condition || '—'" in formal and "execution.status || 'Completed'" in formal
    assert "orderedFormalResultRows().forEach" in formal
    assert "stream.scrollTop = scrollTop" in formal
    assert "result:" not in loading
    assert "/results/' + encodeURIComponent(activeFormalRunId) + '/" not in loading
    for forbidden in ("provider_attempts", "initial_stage", "critique_stage", "revision_stage", "retrieved_evidence_ids"):
        assert forbidden not in formal


def test_guided_formal_scientific_cards_map_six_experiment_families() -> None:
    mapping = JS[JS.index("function formalSummaryFields"):JS.index("function renderFormalExecutionCards")]
    for summary_type in ("retrieval", "architecture", "debate", "judgment", "conflict", "multi_model_consensus"):
        assert f"case '{summary_type}'" in mapping
    for label in (
        "Recall@4", "Gold evidence recall", "Hit@4", "Evidence", "Provider", "Debate enabled",
        "Prediction", "Confidence", "Reason", "Governance", "Final consensus", "Consensus model", "Citations",
    ):
        assert f"'{label}'" in mapping
    judgment = mapping[mapping.index("case 'judgment'"):mapping.index("case 'conflict'")]
    assert "execution.prediction" in judgment and "execution.confidence" in judgment and "execution.reason_excerpt" in judgment
    assert "Final answer" not in judgment and "answer_excerpt" not in judgment
    retrieval = mapping[mapping.index("case 'retrieval'"):mapping.index("case 'architecture'")]
    assert "execution.answer_excerpt" in retrieval
    conflict = mapping[mapping.index("case 'conflict'"):mapping.index("case 'multi_model_consensus'")]
    assert "execution.preserves_both_viewpoints" in conflict
    assert "execution.cites_both_sources" in conflict and "execution.expresses_uncertainty" in conflict
    multi_model = mapping[mapping.index("case 'multi_model_consensus'"):mapping.index("default:")]
    assert "execution.answer_excerpt" in multi_model and "execution.consensus_model" in multi_model
    assert "initial_stage" not in mapping and "critique_stage" not in mapping and "revision_stage" not in mapping


def test_guided_execution_cards_keep_run_and_historical_metrics_separate() -> None:
    cards = JS[JS.index("function renderFormalExecutionCards"):JS.index("function setPaperWorkbenchMode")]
    loading = JS[JS.index("async function loadFormalResults"):JS.index("async function startFormalRun")]
    assert "final_metrics" not in cards and "historical_paper_results" not in cards
    assert "JSON.stringify({ status: data.status, final_metrics: data.final_metrics || {} }" in loading
    assert "results: orderedRows" not in loading
    assert "#formal-historical-results" in loading and "data.historical_paper_results" in loading
    assert "/results/" not in loading


def test_guided_formal_cards_clear_on_restore_and_new_run() -> None:
    registry = JS[JS.index("async function loadFormalRegistry"):JS.index("function elapsedClock")]
    start = JS[JS.index("async function startFormalRun"):JS.index("async function stopFormalRun")]
    assert "clearFormalResultRows(); activeFormalRunId = savedRun" in registry
    assert start.index("clearFormalResultRows()") < start.index("await api('/api/formal-runs'")
    render = JS[JS.index("function renderFormalExecutionCards"):JS.index("function lockedField")]
    assert "['running', 'stop_requested'].includes(status.status)" in render
    assert "formalResultRows.size + 1" in render


def test_custom_cloud_result_renders_persisted_evidence_and_runtime_metadata() -> None:
    rendering = JS[JS.index("function renderResearchRun(data, options = {})"):JS.index("function renderCompare(data)")]
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
    rendering = JS[JS.index("function renderResearchRun(data, options = {})"):JS.index("function renderCompare(data)")]
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


def test_custom_polling_never_auto_opens_question_details() -> None:
    refresh = JS[JS.index("async function refreshCustomRun"):JS.index("async function resumeSavedCustomRun")]
    assert "latestSelectable" not in refresh
    assert "selectCustomResult(" not in refresh
    assert "renderCustomQuestionResults()" in refresh
    assert "persistedCount = customResultSummaries.size" in refresh
    assert "persistedCount + ' of ' + totalCount + ' custom questions completed so far." in refresh
    assert "setText('#consensus-progress-detail', persistedCount + ' / ' + totalCount" in refresh
    assert "customResultSummaries.size" in JS
    restore = JS[JS.index("async function resumeSavedCustomRun"):JS.index("async function stopCustomRun")]
    assert "await refreshCustomRun(true)" in restore
    assert "selectCustomResult(" not in restore


def test_custom_progress_uses_persisted_cards_and_has_finalizing_state() -> None:
    refresh = JS[JS.index("async function refreshCustomRun"):JS.index("async function resumeSavedCustomRun")]
    assert "persistedCount + 1" in refresh
    assert "persistedCount >= totalCount ? 'Finalizing custom run…'" in refresh
    assert "waiting for terminal status" in refresh
    assert "Running question ' + (persistedCount + 1) + ' of ' + totalCount" in refresh
    assert "status.completed" not in refresh


def test_new_custom_run_clears_previous_result_before_queueing() -> None:
    clearing = JS[JS.index("function clearCustomResultDisplay"):JS.index("let activeCustomRunId")]
    submit = JS[JS.index("$('#consensus-form').addEventListener('submit'"):JS.index("$('#research-compare-form')")]
    assert "currentResearchRun = null" in clearing
    assert "$('#consensus-results').hidden = true" in clearing
    assert "$('#consensus-trace').textContent = ''" in clearing
    assert "'#consensus-evidence'" in clearing
    assert "'#consensus-agents'" in clearing
    assert submit.index("clearCustomBatchDisplay()") < submit.index("startResearchProgress()")
    assert submit.index("clearCustomBatchDisplay()") < submit.index("await api('/api/custom-runs'")


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


def test_custom_restore_loading_paints_and_always_clears() -> None:
    resume = JS[JS.index("async function resumeSavedCustomRun"):JS.index("async function stopCustomRun")]
    assert 'id="custom-restore-loading"' in HTML
    assert 'class="custom-restore-spinner"' in HTML
    assert "if (!saved) { setCustomRestoreLoading(false); return; }" in resume
    assert "setCustomRestoreLoading(true)" in resume
    assert "await yieldForCustomRestorePaint()" in resume
    assert "await refreshCustomRun(true)" in resume
    assert "finally" in resume
    assert "setCustomRestoreLoading(false)" in resume
    assert "typeof requestAnimationFrame === 'function'" in JS
    assert "if (customActive && !researchProgressTimer) startResearchProgress()" in JS
    assert "stopResearchProgress(status.status === 'complete' ? 'complete' : status.status === 'stopped' ? 'stopped' : 'failed')" in JS


def test_custom_question_results_use_lightweight_summaries_and_one_detail_panel() -> None:
    assert 'id="custom-question-results"' in HTML
    assert 'id="custom-question-results-list"' in HTML
    assert HTML.count('id="consensus-results"') == 1
    assert "const customResultSummaries = new Map()" in JS
    assert "orderedCustomResultSummaries()" in JS
    assert "/results/summary?after=" in JS
    assert "/results/' + selectedCustomSequence" in JS
    assert "newRows.forEach((row) => customResultSummaries.set(Number(row.sequence), row))" in JS
    assert "container.replaceChildren(fragment)" in JS
    assert "clearCustomResultDisplay()" in JS
    assert "customSelectionManual" in JS
    assert "if (manual) customSelectionManual = true" in JS
    refresh = JS[JS.index("async function refreshCustomRun"):JS.index("async function resumeSavedCustomRun")]
    assert "selectCustomResult(" not in refresh


def test_custom_question_count_uses_preset_as_source_of_truth() -> None:
    count_logic = JS[JS.index("function selectedCustomQuestionCount"):JS.index("function clearCustomResultDisplay")]
    assert "return selected === 'custom' ? Number($('#custom-question-count-value').value) : Number(selected);" in count_logic
    assert "label.hidden = false" in count_logic
    assert "input.disabled = !custom" in count_logic
    assert "label.classList.toggle('is-disabled', !custom)" in count_logic
    assert "input.tabIndex = -1" in count_logic
    assert "questions: questions.slice(0, requestedCount)" in JS
    assert '#custom-question-count-label" hidden' not in HTML
    assert "custom-question-count-row input:disabled" in CSS


def test_selected_custom_detail_is_inline_single_tree_with_loading_and_retry() -> None:
    assert 'id="custom-detail-loading"' in HTML
    assert 'Loading question details…' in HTML
    assert 'Retrieving the saved answer, evidence, and specialist outputs.' in HTML
    assert 'id="custom-detail-content"' in HTML
    assert HTML.count('id="consensus-results"') == 1
    placement = JS[JS.index("function placeCustomDetail"):JS.index("function renderCustomQuestionResults")]
    assert "card.after(detail)" in placement
    assert "section.after(detail)" in placement
    render = JS[JS.index("function renderCustomQuestionResults"):JS.index("function clearCustomBatchDisplay")]
    assert "if (detail && detail.parentElement === container) section.after(detail);" in render
    assert render.index("section.after(detail)") < render.index("container.replaceChildren(fragment)")
    selection = JS[JS.index("async function selectCustomResult"):JS.index("function customQaExport")]
    assert "card.dataset.sequence" in JS
    assert "loading.hidden = false" in selection
    assert "await yieldForCustomDetailPaint()" in selection
    assert "requestToken !== customDetailRequestToken" in selection
    assert "retry.onclick = () => selectCustomResult(selectedCustomSequence, true)" in selection
    assert "renderResearchRun(row.result, { scroll: manual })" in selection
    assert ".custom-detail-loading" in CSS
    assert ".custom-detail-content[hidden]" in CSS


def test_custom_detail_toggle_collapses_without_fetching() -> None:
    render = JS[JS.index("function renderCustomQuestionResults"):JS.index("function clearCustomBatchDisplay")]
    assert "const expanded = Number(summary.sequence) === selectedCustomSequence" in render
    assert "expanded ? 'Hide full details' : 'View full details'" in render
    assert "button.setAttribute('aria-expanded', String(expanded))" in render
    assert "expanded ? collapseCustomResult() : selectCustomResult(Number(summary.sequence), true)" in render
    collapse = JS[JS.index("function collapseCustomResult"):JS.index("async function selectCustomResult")]
    assert "customDetailRequestToken += 1" in collapse
    assert "selectedCustomSequence = null" in collapse
    assert "clearCustomResultDisplay()" in collapse
    assert "renderCustomQuestionResults()" in collapse
    assert "apiGet(" not in collapse


def test_custom_detail_switch_and_restore_do_not_duplicate_full_result_trees() -> None:
    render = JS[JS.index("function renderCustomQuestionResults"):JS.index("function clearCustomBatchDisplay")]
    assert "container.replaceChildren(fragment)" in render
    assert "placeCustomDetail()" in render
    assert "customResultSummaries.set(Number(row.sequence), row)" in JS
    clear = JS[JS.index("function clearCustomBatchDisplay"):JS.index("async function selectCustomResult")]
    assert "selectedCustomSequence = null" in clear
    assert "if (detail && detail.parentElement === $('#custom-question-results-list')) $('#custom-question-results').after(detail);" in clear
    assert "$('#custom-question-results').after($('#consensus-results'))" in clear


def test_reenabling_custom_controls_reapplies_preset_count_disabled_state() -> None:
    controls = JS[JS.index("function setResearchControlsDisabled"):JS.index("function updateConditionHelp")]
    assert "if (!disabled) updateCustomQuestionCount();" in controls


def test_custom_cards_exports_and_print_keep_question_answer_pairs_lightweight() -> None:
    assert "Question results" in HTML
    assert "Print Q&amp;A Report" in HTML
    assert "Download All Q&amp;A JSON" in HTML
    assert "Download All Q&amp;A CSV" in HTML
    assert "Download Selected JSON" in HTML and "Download Selected CSV" in HTML
    cards = JS[JS.index("function renderCustomQuestionResults"):JS.index("function clearCustomBatchDisplay")]
    assert "summary.question" in cards and "summary.final_answer" in cards
    assert "summary.condition === 'C1' ? 'Final answer' : 'Final integrated answer'" in cards
    assert "summary.error || summary.final_answer" in cards
    export = JS[JS.index("function customQaExport"):JS.index("function customQaCsv")]
    assert "question: row.question" in export and "final_answer: row.final_answer" in export
    assert "trace" not in export and "provider_attempts" not in export
    csv = JS[JS.index("function customQaCsv"):JS.index("function buildCustomPrintReport")]
    assert "'sequence', 'question_id', 'question', 'final_answer'" in csv
    printing = JS[JS.index("function buildCustomPrintReport"):JS.index("function printCustomQaReport")]
    assert "data.questions.forEach" in printing
    assert "item.question" in printing and "item.final_answer" in printing
    assert "trace" not in printing and "provider_attempts" not in printing


def test_selected_multi_agent_detail_keeps_semantic_outputs_separate() -> None:
    rendering = JS[JS.index("function renderResearchRun(data, options = {})"):JS.index("function renderCompare(data)")]
    assert "const outputs = data.agent_outputs || []" in rendering
    assert "Model: ' + agent.model" in rendering
    assert "ABSTAINED" in rendering
    assert "agent.abstention_reason" in rendering
    assert "data.condition_id === 'C1' ? 'Final answer' : 'Final integrated answer'" in rendering
    assert "traceData.provider_attempts" in rendering
    assert rendering.index("const outputs = data.agent_outputs || []") < rendering.index("traceData.provider_attempts")
