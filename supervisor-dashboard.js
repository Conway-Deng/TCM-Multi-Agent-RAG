(() => {
  'use strict';

  const root = document.querySelector('#supervisor-dashboard');
  if (!root) return;

  const API = window.MEDIRAG_API_BASE_URL;
  const QUESTIONS = [
    'What are the traditional properties, functions, and source-grounded uses of Ren Shen (Ginseng)?',
    'What are the traditional functions and indications of Huang Qi (Astragalus) in the TCM corpus?',
    'What does the TCM corpus say about the properties and functions of Bai Zhu?',
    'How is Liver qi stagnation described in traditional syndrome knowledge?',
    'What are the traditional properties and indications of Dang Gui?'
  ];
  const AGENTS = ['syndrome', 'herbal', 'acupuncture_meridian', 'constitution', 'dietary_therapy', 'lifestyle_yangsheng'];
  const STATUS_ORDER = ['WAITING', 'RUNNING', 'PASS', 'RETRY', 'FAIL'];
  const state = { running: false, rows: [], results: [], latest: null, startedAt: 0, timer: null, conditions: ['C1', 'C2'] };

  const $ = (selector) => root.querySelector(selector);
  const $$ = (selector) => Array.from(root.querySelectorAll(selector));
  const text = (selector, value) => { const node = $(selector); if (node) node.textContent = value; };
  const escapeCsv = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`;
  const percent = (value, digits = 1) => `${Number(value).toFixed(digits)}%`;
  const seconds = (milliseconds) => Number.isFinite(milliseconds) ? `${(milliseconds / 1000).toFixed(1)} s` : '—';
  const finite = (value) => typeof value === 'number' && Number.isFinite(value);

  function setView(view, options = {}) {
    const target = view === 'workbench' ? '#live-demo' : '#overview';
    document.body.classList.toggle('is-workbench', view === 'workbench');
    $$('[data-view]').forEach((link) => {
      const active = link.dataset.view === view;
      link.classList.toggle('is-active', active);
      link.setAttribute('aria-selected', String(active));
    });
    if (options.push) history.pushState({ view }, '', target);
    if (options.scroll !== false) document.querySelector(target)?.scrollIntoView({ behavior: 'smooth' });
  }

  $$('[data-view]').forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
    setView(link.dataset.view, { push: true });
  }));
  window.addEventListener('popstate', () => setView(window.location.hash === '#live-demo' ? 'workbench' : 'home', { scroll: true }));
  setView('home', { push: false, scroll: false });

  function download(name, content, type) {
    const blob = new Blob([content], { type });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  function safeRunExport(result) {
    if (!result) return null;
    return {
      demo_only: true,
      run_id: result.run_id,
      condition_id: result.condition_id,
      condition_name: result.condition_name,
      final_answer: result.final_answer,
      abstention: result.abstention,
      retrieval: result.retrieval,
      agent_outputs: result.agent_outputs,
      metrics: result.metrics,
      trace: result.trace,
      limitations: result.limitations
    };
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    let payload = {};
    try { payload = await response.json(); } catch (_) { /* readable HTTP error below */ }
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : `HTTP ${response.status}`);
    return payload;
  }

  async function checkApi() {
    const badge = $('#dashboard-api-status');
    try {
      const health = await fetchJson(`${API}/health`);
      badge.className = 'dashboard-status is-online';
      badge.textContent = `${health.llm_execution_enabled ? 'Real API ready' : 'API online · LLM disabled'} · ${(health.corpus_chunk_count || 0).toLocaleString()} chunks`;
    } catch (_) {
      badge.className = 'dashboard-status is-offline';
      badge.textContent = 'Local API offline';
    }
  }

  function formalChart(title, subtitle, values, unit, scaleMax = 100) {
    const card = document.createElement('article');
    card.className = 'chart-card';
    const heading = document.createElement('h3'); heading.textContent = title; card.append(heading);
    const description = document.createElement('p'); description.textContent = subtitle; card.append(description);
    Object.entries(values).forEach(([label, value]) => {
      const row = document.createElement('div'); row.className = 'bar-row';
      const key = document.createElement('span'); key.textContent = label;
      const track = document.createElement('div'); track.className = 'bar-track';
      const fill = document.createElement('div'); fill.className = 'bar-fill'; fill.style.width = `${Math.max(0, Math.min(100, value / scaleMax * 100))}%`; track.append(fill);
      const output = document.createElement('output'); output.textContent = unit === '%' ? `${value.toFixed(2)}%` : unit === '/100' ? `${value}/100` : `${value.toFixed(2)} s`;
      row.append(key, track, output); card.append(row);
    });
    const scale = document.createElement('div'); scale.className = 'chart-scale'; scale.innerHTML = `<span>0</span><span>${scaleMax}${unit === '%' ? '%' : unit === '/100' ? '' : ' s'}</span>`; card.append(scale);
    return card;
  }

  function renderFormalResults(data) {
    const rq1 = data.rq1; const rq4 = data.rq4;
    $('#results-provenance-status').textContent = 'Verified aggregate data loaded';
    $('#results-provenance-status').className = 'status-pill is-complete';
    $('#formal-result-summary').innerHTML = `
      <article class="formal-summary-card"><p class="dashboard-eyebrow">RQ1 · Confirmatory</p><h3>C1 Single-RAG vs C2 Multi-Agent</h3><div class="headline-metric"><strong>${rq1.difference_c2_minus_c1_pp.toFixed(2)} pp</strong><span>C2 − C1 Full Recall</span></div><p>C1 ${rq1.full_recall_pct.C1.toFixed(2)}% · C2 ${rq1.full_recall_pct.C2.toFixed(2)}%</p><small>95% CI ${rq1.bootstrap_95_ci_pp[0].toFixed(2)} to +${rq1.bootstrap_95_ci_pp[1].toFixed(2)} pp · ${rq1.complete_usable_pairs} paired questions</small><p>${rq1.conclusion}</p></article>
      <article class="formal-summary-card"><p class="dashboard-eyebrow">RQ4 · Final</p><h3>C2 Multi-Agent vs C4 Debate</h3><div class="headline-metric"><strong>${rq4.difference_c4_minus_c2_pp.toFixed(2)} pp</strong><span>C4 − C2 Full Recall</span></div><p>C2 ${rq4.full_recall_pct.C2.toFixed(2)}% · C4 ${rq4.full_recall_pct.C4.toFixed(2)}%</p><small>95% CI ${rq4.bootstrap_95_ci_pp[0].toFixed(2)} to +${rq4.bootstrap_95_ci_pp[1].toFixed(2)} pp · ${rq4.complete_usable_pairs} paired questions</small><p>${rq4.conclusion}</p></article>`;

    const charts = $('#result-charts'); charts.replaceChildren(
      formalChart('RQ1 Full Recall', 'Honest 0–100% scale', rq1.full_recall_pct, '%'),
      formalChart('RQ4 Full Recall', 'Honest 0–100% scale', rq4.full_recall_pct, '%'),
      formalChart('RQ4 Reliability', 'Usable executions out of 100', rq4.reliability_usable, '/100'),
      formalChart('RQ4 Mean latency', 'Seconds per complete usable execution', rq4.mean_latency_seconds, 's', 45),
      formalChart('RQ4 Partial-or-Better', 'Honest 0–100% scale', rq4.partial_or_better_pct, '%')
    );
    $('#rq4-result-table').innerHTML = `
      <tr><th scope="row">Full Recall</th><td>${rq4.full_recall_pct.C2.toFixed(2)}%</td><td>${rq4.full_recall_pct.C4.toFixed(2)}%</td></tr>
      <tr><th scope="row">Partial-or-Better</th><td>${rq4.partial_or_better_pct.C2.toFixed(2)}%</td><td>${rq4.partial_or_better_pct.C4.toFixed(2)}%</td></tr>
      <tr><th scope="row">Missing</th><td>${rq4.missing_pct.C2.toFixed(2)}%</td><td>${rq4.missing_pct.C4.toFixed(2)}%</td></tr>
      <tr><th scope="row">Contradiction</th><td>${rq4.contradiction_pct.C2.toFixed(2)}%</td><td>${rq4.contradiction_pct.C4.toFixed(2)}%</td></tr>
      <tr><th scope="row">Usable / reliability</th><td>${rq4.reliability_usable.C2}/100</td><td>${rq4.reliability_usable.C4}/100</td></tr>
      <tr><th scope="row">Mean latency</th><td>${rq4.mean_latency_seconds.C2.toFixed(2)} s</td><td>${rq4.mean_latency_seconds.C4.toFixed(2)} s</td></tr>`;
  }

  async function loadFormalResults() {
    try { renderFormalResults(await fetchJson('frontend/data/research_results.json')); }
    catch (error) {
      $('#results-provenance-status').textContent = 'Aggregate data unavailable';
      $('#results-provenance-status').className = 'status-pill is-warning';
      $('#formal-result-summary').textContent = error.message;
    }
  }

  function statusPill(status) {
    const normalized = STATUS_ORDER.includes(status) ? status : 'FAIL';
    return `<span class="run-status ${normalized.toLowerCase()}">${normalized}</span>`;
  }

  function initializeRows(questions, conditions) {
    state.rows = questions.map((question, index) => ({
      index: index + 1,
      question,
      cells: Object.fromEntries(conditions.map((condition) => [condition, { status: 'WAITING', latency: null }]))
    }));
    text('#live-condition-a-head', `${conditions[0]} status`); text('#live-condition-a-latency', `${conditions[0]} latency`);
    text('#live-condition-b-head', `${conditions[1]} status`); text('#live-condition-b-latency', `${conditions[1]} latency`);
    renderRows();
  }

  function renderRows() {
    const body = $('#live-result-rows'); body.replaceChildren();
    state.rows.forEach((row) => {
      const tr = document.createElement('tr');
      const question = document.createElement('td'); question.className = 'question-cell';
      const qStrong = document.createElement('strong'); qStrong.textContent = `Q${row.index}`;
      const qSmall = document.createElement('small'); qSmall.textContent = row.question;
      question.append(qStrong, qSmall); tr.append(question);
      state.conditions.forEach((condition) => {
        const cell = row.cells[condition];
        const status = document.createElement('td'); status.innerHTML = statusPill(cell.status);
        const latency = document.createElement('td'); latency.textContent = seconds(cell.latency);
        tr.append(status, latency);
      });
      body.append(tr);
    });
  }

  function classify(result) {
    const trace = result.trace || {};
    const failed = Number(trace.failed_provider_calls || 0);
    const successful = Number(trace.successful_provider_calls || 0);
    if (trace.fallback_usage || result.abstention || !result.final_answer) return 'FAIL';
    if (failed > 0 && successful > 0) return 'RETRY';
    return 'PASS';
  }

  function mean(values) { return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null; }
  function metricFrom(result, names) {
    const metrics = result.metrics || {};
    for (const name of names) if (finite(metrics[name])) return metrics[name];
    return null;
  }

  function renderAggregates(totalPerCondition) {
    const cards = [];
    const completed = state.results.length;
    cards.push({ label: 'Completion rate', value: percent(completed / (totalPerCondition * 2) * 100), note: `${completed} / ${totalPerCondition * 2} executions` });
    state.conditions.forEach((condition) => {
      const results = state.results.filter((item) => item.condition === condition);
      const usable = results.filter((item) => ['PASS', 'RETRY'].includes(item.status)).length;
      const latency = mean(results.map((item) => item.latency).filter(finite));
      const attempts = mean(results.map((item) => item.providerAttempts).filter(finite));
      cards.push({ label: `${condition} usable so far`, value: `${usable} / ${results.length || 0}`, note: results.length ? percent(usable / results.length * 100) : 'Waiting' });
      cards.push({ label: `${condition} mean latency`, value: latency === null ? '—' : seconds(latency), note: `${results.length} completed` });
      cards.push({ label: `${condition} provider attempts`, value: attempts === null ? '—' : attempts.toFixed(1), note: 'Mean attempts per execution' });
      const retrieval = results.map((item) => item.retrievalRecall).filter(finite);
      const citation = results.map((item) => item.citationRecall).filter(finite);
      if (retrieval.length) cards.push({ label: `${condition} retrieval recall`, value: percent(mean(retrieval) * 100), note: 'Deterministic objective metric' });
      if (citation.length) cards.push({ label: `${condition} citation recall`, value: percent(mean(citation) * 100), note: 'Deterministic objective metric' });
    });
    $('#live-aggregate-cards').innerHTML = cards.map((card) => `<article class="live-metric-card"><span>${card.label}</span><strong>${card.value}</strong><small>${card.note}</small></article>`).join('');
  }

  function renderLatest(result, question) {
    state.latest = result;
    $('.demo-details').open = true;
    text('#latest-question', question);
    text('#latest-answer', result.final_answer || 'No usable answer returned.');
    const trace = result.trace || {};
    const agents = trace.participating_agents || (result.agent_outputs || []).filter((item) => !item.abstained).map((item) => item.agent_name || item.agent_id);
    text('#latest-agent-path', agents.length ? agents.join(' → ') : 'No participating specialist reported');
    const support = result.metrics?.active_agent_evidence_support ?? result.metrics?.citation_support;
    text('#latest-evidence-support', finite(support) ? percent(support * 100) : 'not provided by this response');
    const evidence = $('#latest-evidence'); evidence.replaceChildren();
    (result.retrieval || []).forEach((item) => {
      const card = document.createElement('article'); card.className = 'evidence-citation';
      const title = document.createElement('strong'); title.textContent = `#${item.rank || '—'} · ${item.chunk_id || 'Evidence'}`;
      const snippet = document.createElement('p'); snippet.textContent = item.chunk_text || item.snippet || 'Evidence text not returned.';
      const meta = document.createElement('small'); meta.textContent = `${item.retrieval_method || trace.retrieval_strategy || 'R0'} · source reference retained in run trace`;
      card.append(title, snippet, meta); evidence.append(card);
    });
    if (!evidence.children.length) evidence.textContent = 'No evidence items were returned.';
  }

  function updateProgress(completed, total, questionIndex, condition, stage) {
    const value = total ? completed / total * 100 : 0;
    text('#live-progress-title', `${completed} / ${total} completed`);
    text('#live-progress-percent', `${value.toFixed(1)}%`);
    text('#live-current-question', questionIndex ? `Question ${questionIndex} / ${state.rows.length}` : 'Complete');
    text('#live-current-condition', condition || 'Complete');
    text('#live-current-stage', stage || 'Complete');
    const track = $('.live-progress-track'); track.setAttribute('aria-valuenow', String(value));
    $('#live-progress-bar').style.width = `${value}%`;
  }

  function conditionStage(condition) {
    if (condition === 'C4') return 'Server-side: initial specialists → critique → revision → consensus';
    if (condition === 'C2') return 'Server-side: retrieval → planner → independent specialists';
    return 'Server-side: retrieval → single specialist → answer';
  }

  async function runExecution(question, questionIndex, condition, total) {
    const cell = state.rows[questionIndex - 1].cells[condition];
    cell.status = 'RUNNING'; renderRows();
    updateProgress(state.results.length, total, questionIndex, condition, conditionStage(condition));
    const started = performance.now();
    try {
      const result = await fetchJson(`${API}/api/research/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          question,
          condition_id: condition,
          retrieval_strategy: 'R0',
          active_agents: AGENTS,
          active_judges: [],
          top_k: 4,
          debate_rounds: 1,
          include_trace: true
        })
      });
      const trace = result.trace || {};
      const latency = finite(trace.latency_ms) ? trace.latency_ms : performance.now() - started;
      const status = classify(result);
      cell.status = status; cell.latency = latency;
      state.results.push({
        condition, status, latency, result,
        providerAttempts: finite(trace.provider_calls) ? trace.provider_calls : null,
        retrievalRecall: metricFrom(result, ['retrieval_recall', 'gold_evidence_retrieval_recall']),
        citationRecall: metricFrom(result, ['citation_recall', 'gold_evidence_citation_recall'])
      });
      renderLatest(result, question);
    } catch (error) {
      cell.status = 'FAIL'; cell.latency = performance.now() - started;
      state.results.push({ condition, status: 'FAIL', latency: cell.latency, providerAttempts: null, retrievalRecall: null, citationRecall: null, error: error.message });
      text('#live-demo-message', `${condition} on Q${questionIndex}: ${error.message}`);
    }
    renderRows(); renderAggregates(state.rows.length);
    updateProgress(state.results.length, total, questionIndex, condition, 'Execution complete');
  }

  async function startDemo(event) {
    event.preventDefault();
    if (state.running || !isLocal) return;
    const mode = new FormData(event.currentTarget).get('demo-mode');
    const count = Number(new FormData(event.currentTarget).get('question-count'));
    const questions = QUESTIONS.slice(0, count);
    state.conditions = mode === 'rq4' ? ['C2', 'C4'] : ['C1', 'C2'];
    state.running = true; state.results = []; state.latest = null; state.startedAt = performance.now();
    initializeRows(questions, state.conditions);
    $('#live-progress-panel').hidden = false; $('#live-results-panel').hidden = false;
    $('#start-live-demo').disabled = true; text('#live-demo-message', 'Starting sequential demo executions. No formal files are written.');
    const total = count * 2; updateProgress(0, total, 1, state.conditions[0], 'Preparing request'); renderAggregates(count);
    state.timer = setInterval(() => text('#live-elapsed', `${((performance.now() - state.startedAt) / 1000).toFixed(1)} s`), 100);
    for (let index = 0; index < questions.length; index += 1) {
      for (const condition of state.conditions) await runExecution(questions[index], index + 1, condition, total);
    }
    clearInterval(state.timer); state.timer = null; state.running = false;
    $('#start-live-demo').disabled = false;
    updateProgress(total, total, 0, '', 'Complete');
    text('#live-demo-message', 'Demo complete. These operational results are temporary and are not included in formal statistics.');
  }

  $('#live-demo-form').addEventListener('submit', startDemo);
  $('#live-download-json').addEventListener('click', () => {
    if (state.latest) download(`tcm-demo-${state.latest.run_id || 'run'}.json`, JSON.stringify(safeRunExport(state.latest), null, 2), 'application/json;charset=utf-8');
  });
  $('#live-download-csv').addEventListener('click', () => {
    if (!state.latest) return;
    const trace = state.latest.trace || {};
    const rows = [['run_id', 'condition', 'retrieval', 'latency_ms', 'provider_calls', 'fallback'], [state.latest.run_id, state.latest.condition_id, trace.retrieval_strategy, trace.latency_ms, trace.provider_calls, trace.fallback_usage]];
    download(`tcm-demo-${state.latest.run_id || 'run'}.csv`, rows.map((row) => row.map(escapeCsv).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
  });

  if (!isLocal) {
    $('#demo-local-only-note').hidden = false;
    $('#start-live-demo').disabled = true;
    $('#start-live-demo').textContent = 'Live demo available locally';
  }

  checkApi();
  loadFormalResults();
})();
