(function () {
  'use strict';

  const isLocalDevelopment = ['localhost', '127.0.0.1'].includes(window.location.hostname);
  const API = window.MEDIRAG_API_BASE_URL || (isLocalDevelopment ? 'http://localhost:8000' : 'https://tcm-multi-agent-rag-api.onrender.com');
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  let language = 'en';

  const copy = {
    en: {
      home: 'Home', demo: 'Workbench', title: 'TCM Research Workbench', lead: 'Run a conventional TCM RAG baseline, a specialist multi-agent condition, or a controlled comparison.',
      modes: [['Standard TCM consultation', 'Legacy Demo · 16-entry compatibility fixture · not used for formal experiments'], ['TCM Research Workbench', 'C1-C6 controlled research conditions over the active corpus'], ['Research Compare', 'Same-question controlled conditions']],
      status: 'Backend status', question: 'TCM educational question *', helper: 'Do not include identifying information. Emergencies require immediate professional help.',
      submit: 'Run TCM Single RAG', samples: 'Try a sample', context: 'Optional context', contextHint: 'used only for this request',
      result: 'Evidence-grounded TCM perspective', patterns: 'Possible educational patterns', examples: 'Educational source examples', safety: 'Safety notes', evidence: 'Retrieved evidence', technical: 'Technical details',
      progress: { connecting: 'Connecting to backend', processing: 'Processing on backend', rendering: 'Rendering response', complete: 'Response ready', detail: 'Scope and safety checks run first; evidence retrieval and generation follow when applicable.' },
      researchProgress: { connecting: 'Connecting to backend', retrieving: 'Retrieving evidence', generating: 'Generating specialist responses', evaluating: 'Evaluating result', rendering: 'Rendering response', complete: 'Response ready', failed: 'Request failed' }
    },
    zh: {
      home: '首页', demo: '研究台', title: '中医多智能体 RAG 研究台', lead: '运行中医单路 RAG、多智能体条件或同题对照实验。',
      modes: [['标准中医咨询', '旧版演示 · 16 条兼容性样例 · 不用于正式实验'], ['中医研究台', '基于当前语料库的 C1-C6 受控研究条件'], ['研究对照', '同一问题的受控条件比较']],
      status: '后端状态', question: '中医教学研究问题 *', helper: '请勿填写可识别个人身份的信息。紧急情况请立即寻求专业帮助。',
      submit: '运行中医单路 RAG', samples: '示例问题', context: '可选背景', contextHint: '仅用于本次请求',
      result: '基于证据的中医视角', patterns: '教学性辨证方向', examples: '资料中的教学示例', safety: '安全提示', evidence: '检索证据', technical: '技术详情',
      progress: { connecting: '正在连接后端', processing: '后端正在处理请求', rendering: '正在渲染结果', complete: '结果已就绪', detail: '后端会先进行范围与安全检查，并在适用时继续检索证据和生成回答。' },
      researchProgress: { connecting: '正在连接后端', retrieving: '正在检索证据', generating: '正在生成专家回答', evaluating: '正在评估结果', rendering: '正在渲染结果', complete: '结果已就绪', failed: '请求失败' }
    },
    ko: {
      home: '홈', demo: '연구대', title: 'TCM 멀티에이전트 RAG 연구대', lead: 'TCM 단일 RAG, 전문 에이전트 조건 또는 동일 질문 비교를 실행합니다.',
      modes: [['표준 TCM 상담', '레거시 데모 · 16개 호환 fixture · 공식 실험에 사용하지 않음'], ['TCM 연구대', '현재 코퍼스의 C1-C6 통제 연구 조건'], ['연구 비교', '동일 질문 통제 비교']],
      status: '백엔드 상태', question: 'TCM 교육 연구 질문 *', helper: '식별 가능한 개인정보를 입력하지 마세요. 응급 상황에서는 즉시 전문 도움을 받으세요.',
      submit: 'TCM 단일 RAG 실행', samples: '예시 질문', context: '선택 배경', contextHint: '이번 요청에만 사용',
      result: '근거 기반 TCM 관점', patterns: '교육용 변증 방향', examples: '자료의 교육 예시', safety: '안전 안내', evidence: '검색 근거', technical: '기술 세부정보',
      progress: { connecting: '백엔드에 연결 중', processing: '백엔드에서 요청 처리 중', rendering: '응답 렌더링 중', complete: '응답 준비 완료', detail: '범위와 안전 검사를 먼저 수행하고, 해당되는 경우 근거 검색과 답변 생성을 이어갑니다.' },
      researchProgress: { connecting: '백엔드에 연결 중', retrieving: '근거 검색 중', generating: '전문가 답변 생성 중', evaluating: '결과 평가 중', rendering: '응답 렌더링 중', complete: '응답 준비 완료', failed: '요청 실패' }
    }
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function setText(selector, text) {
    const node = $(selector);
    if (node) node.textContent = text;
  }

  function setView(view, { push = false } = {}) {
    const workbench = view === 'workbench';
    $('#home-view').hidden = workbench;
    $('#demo-view').hidden = !workbench;
    $$('.toggle-btn').forEach((button) => {
      const active = button.dataset.view === (workbench ? 'workbench' : 'home');
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
      button.setAttribute('aria-current', active ? 'page' : 'false');
    });
    $('.view-toggle').classList.toggle('is-workbench', workbench);
    $('.nav').hidden = workbench;
    if (push) history.pushState({ view: workbench ? 'workbench' : 'home' }, '', workbench ? '#workbench' : '#home');
  }

  function setMode(mode, { push = false } = {}) {
    const active = ['single', 'multi', 'compare'].includes(mode) ? mode : 'single';
    setView('workbench');
    $('#tcm-consultation').hidden = active !== 'single';
    $('#consensus-consultation').hidden = active !== 'multi';
    $('#research-compare-consultation').hidden = active !== 'compare';
    $('#west-consultation').hidden = true;
    $$('.demo-option').forEach((button) => {
      const selected = button.dataset.mode === active;
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-checked', String(selected));
    });
    $('.demo-options').className = 'demo-options glass mode-' + ({ single: 'west', multi: 'tcm', compare: 'both' }[active]);
    $$('.demo-option').forEach((button) => button.setAttribute('tabindex', button.dataset.mode === active ? '0' : '-1'));
    if (push) history.pushState({ view: 'workbench', mode: active }, '', '#' + (active === 'single' ? 'legacy-demo' : active === 'multi' ? 'research-workbench' : 'research-compare'));
  }

  function applyLanguage(next) {
    language = copy[next] ? next : 'en';
    const t = copy[language];
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : language;
    $$('.language-btn').forEach((button) => {
      const active = button.dataset.lang === language;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    const toggles = $$('.toggle-btn');
    if (toggles[0]) toggles[0].textContent = t.home;
    if (toggles[1]) toggles[1].textContent = t.demo;
    setText('.demo-title', t.title);
    setText('.demo-lead', t.lead);
    $$('.demo-option').forEach((button, index) => {
      const values = t.modes[index];
      button.querySelector('.demo-option-label').textContent = values[0];
      button.querySelector('.demo-option-desc').textContent = values[1];
    });
    setText('.prototype-status strong', t.status);
    setText('.tcm-kicker', language === 'zh' ? 'TCM 标准咨询 · 遗留演示' : language === 'ko' ? 'TCM 표준 상담 · 레거시 데모' : 'TCM standard consultation · legacy demo');
    setText('#tcm-consultation-title', t.modes[0][0]);
    setText('.tcm-panel-heading p:last-child', t.modes[0][1]);
    setText('.tcm-question-field > span', t.question);
    setText('.tcm-question-field small', t.helper);
    setText('.tcm-submit-label', t.submit);
    setText('.tcm-samples > span', t.samples);
    setText('.tcm-context-title', t.context);
    setText('.tcm-context-hint', t.contextHint);
    setText('.tcm-result-hero h2', t.result);
    if (!$('#tcm-run-progress').hidden) updateTcmProgress(tcmProgressStage);
    if (!$('#consensus-progress').hidden) setResearchProgress(researchProgressStage);
    const headings = $$('.tcm-result-card h3');
    if (headings[0]) headings[0].textContent = t.patterns;
    if (headings[1]) headings[1].textContent = t.examples;
    if (headings[2]) headings[2].textContent = t.safety;
    const detailSummaries = $$('.tcm-result-details > summary');
    if (detailSummaries[0]) detailSummaries[0].textContent = t.patterns;
    if (detailSummaries[1]) detailSummaries[1].textContent = t.examples;
    if (detailSummaries[2]) detailSummaries[2].textContent = t.evidence;
    if (detailSummaries[4]) detailSummaries[4].textContent = t.technical;
    const samples = language === 'zh'
      ? ['最近失眠、心悸、健忘，中医教学如何区分？', '最近压力大、腹胀、胃口不好', '只从教学角度解释体质概念，不给处方']
      : language === 'ko'
        ? ['요즘 잠을 잘 못 자고 두근거립니다. TCM 교육에서는 어떻게 설명하나요?', '스트레스와 더부룩함이 함께 있습니다.', '처방 없이 체질 이론을 교육적으로 설명해 주세요.']
        : ['I have trouble sleeping, palpitations, and forgetfulness.', 'I feel stressed, bloated, and have a poor appetite.', 'Explain TCM constitution theory educationally without prescribing.'];
    $$('.tcm-sample').forEach((button, index) => { button.textContent = samples[index]; button.dataset.question = samples[index]; });
  }

  async function api(path, body, onRequestSent) {
    const started = performance.now();
    const pending = fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body) });
    if (onRequestSent) onRequestSent();
    const response = await pending;
    const headersReceived = performance.now();
    const data = await response.json();
    const parsed = performance.now();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed (' + response.status + ')');
    const serverTiming = response.headers.get('Server-Timing') || '';
    const serverDuration = Number((serverTiming.match(/dur=([\d.]+)/) || [])[1] || 0);
    Object.defineProperty(data, '__clientTimings', { value: {
      request_ms: parsed - started,
      time_to_headers_ms: headersReceived - started,
      json_parse_ms: parsed - headersReceived,
      server_ms: serverDuration,
    } });
    return data;
  }

  async function apiGet(path, signal) {
    const response = await fetch(API + path, { headers: { Accept: 'application/json' }, signal });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed (' + response.status + ')');
    return data;
  }

  let formalExperiments = [];
  let selectedFormalExperiment = null;
  let activeFormalRunId = null;
  let formalRunTimer = null;
  let formalResultCursor = 0;
  const formalResultRows = new Map();
  let formalResultRevision = 0;
  let formalRenderedRevision = -1;
  let formalRenderedStatusKey = '';
  let formalSummaryLoad = null;
  let formalSummaryLoadToken = 0;
  let selectedFormalSequence = null;
  let selectedFormalDetail = null;
  let formalDetailRequestToken = 0;
  let formalDetailAbortController = null;
  let formalDetailPanel = null;
  let paperConfigurationApplied = false;

  const FORMAL_SUMMARY_FIELDS = [
    'sequence', 'case_id', 'condition', 'status', 'summary_type', 'stage',
    'chunk_recall_at_4', 'gold_evidence_recall', 'hit_at_4', 'retrieved_count', 'citation_count',
    'answer_excerpt', 'latency_ms', 'latency_seconds', 'usable', 'fallback', 'provider', 'model',
    'debate_enabled', 'prediction', 'confidence', 'reason_excerpt', 'preserves_both_viewpoints',
    'cites_both_sources', 'expresses_uncertainty', 'consensus_model', 'citation_precision', 'citation_recall',
  ];

  function orderedFormalResultRows() { return [...formalResultRows.values()].sort((left, right) => Number(left.sequence) - Number(right.sequence)); }

  function compactFormalSummary(execution) {
    const summary = {};
    FORMAL_SUMMARY_FIELDS.forEach((field) => {
      if (Object.prototype.hasOwnProperty.call(execution, field)) summary[field] = execution[field];
    });
    return summary;
  }

  function clearFormalResultRows() {
    clearFormalExecutionDetail();
    formalSummaryLoadToken += 1;
    formalSummaryLoad = null;
    formalResultCursor = 0;
    formalResultRows.clear();
    formalResultRevision += 1;
    formalRenderedRevision = -1;
    formalRenderedStatusKey = '';
    $('#formal-execution-stream').replaceChildren();
  }

  function setFormalSummaryFeedback(message, restoring = false) {
    const node = $('#formal-run-message');
    node.dataset.formalSummaryFeedback = message ? 'true' : 'false';
    node.classList.toggle('is-formal-restoring', Boolean(message && restoring));
    showMessage(node, message);
  }

  function clearFormalSummaryFeedback() {
    const node = $('#formal-run-message');
    if (node.dataset.formalSummaryFeedback === 'true') setFormalSummaryFeedback('');
  }

  function formalBoolean(value) { return value === true ? 'Yes' : value === false ? 'No' : null; }

  function formalEvidenceSummary(execution) {
    const values = [];
    if (execution.retrieved_count !== undefined) values.push(execution.retrieved_count + ' retrieved');
    if (execution.citation_count !== undefined) values.push(execution.citation_count + ' cited');
    return values.join(' · ') || null;
  }

  function formalSummaryFields(execution) {
    const fields = [];
    const add = (label, value, wide = false) => {
      if (value !== undefined && value !== null && value !== '') fields.push({ label, value: String(value), wide });
    };
    const addBoolean = (label, value) => add(label, formalBoolean(value));
    switch (execution.summary_type) {
      case 'retrieval':
        add('Stage', execution.stage);
        add('Answer', execution.answer_excerpt, true);
        add('Recall@4', execution.chunk_recall_at_4);
        add('Gold evidence recall', execution.gold_evidence_recall);
        add('Hit@4', execution.hit_at_4);
        add('Evidence', formalEvidenceSummary(execution));
        add('Latency', execution.latency_ms === undefined ? null : execution.latency_ms + ' ms');
        addBoolean('Usable', execution.usable);
        addBoolean('Fallback', execution.fallback);
        break;
      case 'architecture':
        add('Answer', execution.answer_excerpt, true);
        add('Evidence', formalEvidenceSummary(execution));
        add('Model', execution.model);
        add('Provider', execution.provider);
        add('Latency', execution.latency_ms === undefined ? null : execution.latency_ms + ' ms');
        addBoolean('Usable', execution.usable);
        addBoolean('Fallback', execution.fallback);
        break;
      case 'debate':
        add('Answer', execution.answer_excerpt, true);
        addBoolean('Debate enabled', execution.debate_enabled);
        add('Evidence', formalEvidenceSummary(execution));
        add('Latency', execution.latency_ms === undefined ? null : execution.latency_ms + ' ms');
        addBoolean('Usable', execution.usable);
        addBoolean('Fallback', execution.fallback);
        break;
      case 'judgment':
        add('Prediction', execution.prediction);
        add('Confidence', execution.confidence);
        add('Reason', execution.reason_excerpt, true);
        addBoolean('Usable', execution.usable);
        add('Latency', execution.latency_ms === undefined ? null : execution.latency_ms + ' ms');
        break;
      case 'conflict': {
        add('Prediction', execution.prediction);
        add('Answer', execution.answer_excerpt, true);
        const governance = [
          formalBoolean(execution.preserves_both_viewpoints) === null ? null : (execution.preserves_both_viewpoints ? '✓' : '✗') + ' viewpoints',
          formalBoolean(execution.cites_both_sources) === null ? null : (execution.cites_both_sources ? '✓' : '✗') + ' citations',
          formalBoolean(execution.expresses_uncertainty) === null ? null : (execution.expresses_uncertainty ? '✓' : '✗') + ' uncertainty',
        ].filter(Boolean).join(' · ');
        add('Governance', governance);
        add('Confidence', execution.confidence);
        addBoolean('Usable', execution.usable);
        add('Latency', execution.latency_ms === undefined ? null : execution.latency_ms + ' ms');
        break;
      }
      case 'multi_model_consensus': {
        add('Final consensus', execution.answer_excerpt, true);
        add('Consensus model', execution.consensus_model);
        const citationMetrics = [];
        if (execution.citation_precision !== undefined) citationMetrics.push('precision ' + execution.citation_precision);
        if (execution.citation_recall !== undefined) citationMetrics.push('recall ' + execution.citation_recall);
        const evidence = formalEvidenceSummary(execution); if (evidence) citationMetrics.push(evidence);
        add('Citations', citationMetrics.join(' · '));
        addBoolean('Usable', execution.usable);
        add('Latency', execution.latency_seconds === undefined ? null : execution.latency_seconds + ' s');
        break;
      }
      default:
        break;
    }
    return fields;
  }

  function ensureFormalDetailPanel() {
    if (formalDetailPanel) return formalDetailPanel;
    const panel = element('li', 'formal-execution-detail');
    panel.id = 'formal-execution-detail';
    const heading = element('div', 'formal-execution-detail-heading');
    heading.append(element('span', 'section-eyebrow', 'Selected execution'), element('h4', '', 'Full execution details'));
    const loading = element('div', 'formal-execution-detail-loading'); loading.id = 'formal-detail-loading';
    loading.append(element('span', 'formal-detail-spinner'), element('strong', '', 'Loading execution details…'));
    const error = element('div', 'formal-execution-detail-error'); error.id = 'formal-detail-error'; error.hidden = true;
    const errorText = element('p', '', 'Could not load execution details.');
    const retry = element('button', 'secondary-action', 'Retry'); retry.type = 'button'; retry.id = 'formal-detail-retry';
    retry.addEventListener('click', () => { if (selectedFormalSequence !== null) loadFormalExecutionDetail(selectedFormalSequence); });
    error.append(errorText, retry);
    const content = element('div', 'formal-execution-detail-content'); content.id = 'formal-detail-content'; content.hidden = true;
    panel.append(heading, loading, error, content);
    formalDetailPanel = panel;
    return panel;
  }

  function setFormalDetailPanelState(state) {
    const panel = ensureFormalDetailPanel();
    panel.querySelector('h4').textContent = selectedFormalSequence === null ? 'Full execution details' : 'Execution ' + String(selectedFormalSequence).padStart(3, '0') + ' details';
    const loading = panel.querySelector('#formal-detail-loading');
    const error = panel.querySelector('#formal-detail-error');
    const content = panel.querySelector('#formal-detail-content');
    loading.hidden = state !== 'loading';
    error.hidden = state !== 'error';
    content.hidden = state !== 'loaded';
    if (state !== 'loaded') content.replaceChildren();
  }

  function syncFormalDetailSelection() {
    $$('.formal-detail-toggle').forEach((button) => {
      const expanded = Number(button.dataset.sequence) === selectedFormalSequence;
      button.textContent = expanded ? 'Hide full details' : 'View full details';
      button.setAttribute('aria-expanded', String(expanded));
      button.closest('.formal-execution-card')?.classList.toggle('is-selected', expanded);
    });
    if (selectedFormalSequence === null) {
      if (formalDetailPanel?.isConnected) formalDetailPanel.remove();
      return;
    }
    const card = $('#formal-execution-stream').querySelector('[data-formal-sequence="' + selectedFormalSequence + '"]');
    if (card) card.after(ensureFormalDetailPanel());
    else if (formalDetailPanel?.isConnected) formalDetailPanel.remove();
  }

  function clearFormalExecutionDetail() {
    formalDetailRequestToken += 1;
    if (formalDetailAbortController) formalDetailAbortController.abort();
    formalDetailAbortController = null;
    selectedFormalSequence = null;
    selectedFormalDetail = null;
    if (formalDetailPanel) formalDetailPanel.querySelector('#formal-detail-content')?.replaceChildren();
    syncFormalDetailSelection();
  }

  function formalDetailText(value) {
    if (Array.isArray(value)) return value.map((item) => String(item)).join(', ');
    return String(value);
  }

  function appendFormalDetailField(container, label, value, { wide = false, cited = false } = {}) {
    if (value === undefined || value === null || value === '' || (Array.isArray(value) && !value.length)) return;
    const wrapper = element('div', wide ? 'is-wide' : '');
    const description = element('dd');
    if (cited) renderCitedText(description, value);
    else description.textContent = formalDetailText(value);
    wrapper.append(element('dt', '', label), description);
    container.append(wrapper);
  }

  function sanitizedFormalTechnical(value) {
    if (Array.isArray(value)) return value.map(sanitizedFormalTechnical);
    if (!value || typeof value !== 'object') return value;
    return Object.fromEntries(Object.entries(value)
      .filter(([key]) => !/(api[_-]?key|authorization|password|secret|token|credential)/i.test(key))
      .map(([key, item]) => [key, sanitizedFormalTechnical(item)]));
  }

  function formalTechnicalData(result) {
    const keys = [
      'run_status', 'http_status', 'generation_mode', 'fallback', 'error', 'retry_count', 'retries_count',
      'provider_attempts', 'provider_attempts_count', 'model_call_counts', 'debate', 'process_data',
      'initial_stage', 'initial_audits', 'critique_stage', 'critique_audits', 'revision_stage',
      'revision_audits', 'consensus_stage', 'consensus_audit', 'stage_statuses',
    ];
    Object.keys(result).filter((key) => /sha256|_hash$/.test(key)).forEach((key) => keys.push(key));
    return sanitizedFormalTechnical(Object.fromEntries(keys
      .filter((key, index) => keys.indexOf(key) === index && Object.prototype.hasOwnProperty.call(result, key))
      .map((key) => [key, result[key]])));
  }

  function renderFormalExecutionDetail(row) {
    const result = row?.result && typeof row.result === 'object' ? row.result : {};
    const summaryType = formalResultRows.get(Number(row.sequence))?.summary_type || 'execution';
    const content = ensureFormalDetailPanel().querySelector('#formal-detail-content');
    content.replaceChildren();
    const fields = element('dl', 'formal-execution-detail-fields');
    appendFormalDetailField(fields, 'Execution', row.sequence);
    appendFormalDetailField(fields, 'Case', row.case_id || result.case_id || result.question_id);
    appendFormalDetailField(fields, 'Condition', row.condition || result.condition || result.condition_id || result.retrieval_condition);
    appendFormalDetailField(fields, 'Status', row.status);
    if (summaryType === 'retrieval') {
      appendFormalDetailField(fields, 'Stage', result.stage);
      appendFormalDetailField(fields, 'Retrieval condition', result.retrieval_condition || result.condition);
      ['chunk_recall_at_1', 'chunk_recall_at_4', 'chunk_recall_at_8', 'gold_evidence_recall', 'hit_at_1', 'hit_at_4', 'hit_at_8', 'source_recall'].forEach((key) => appendFormalDetailField(fields, key.replaceAll('_', ' '), result[key]));
      appendFormalDetailField(fields, 'Retrieved evidence IDs', result.retrieved_ids || result.retrieved_chunk_ids, { wide: true });
      appendFormalDetailField(fields, 'Answer', result.answer, { wide: true, cited: true });
      appendFormalDetailField(fields, 'Citation IDs', result.citation_ids, { wide: true });
      appendFormalDetailField(fields, 'Usable', formalBoolean(result.usable));
      appendFormalDetailField(fields, 'Fallback', formalBoolean(result.fallback));
      appendFormalDetailField(fields, 'Latency', result.retrieval_latency_ms !== undefined ? result.retrieval_latency_ms + ' ms' : result.latency_ms !== undefined ? result.latency_ms + ' ms' : null);
      appendFormalDetailField(fields, 'Model', result.model_actually_called || result.model);
      appendFormalDetailField(fields, 'Provider', result.provider);
    } else if (summaryType === 'architecture' || summaryType === 'debate') {
      appendFormalDetailField(fields, 'Full answer', result.full_answer, { wide: true, cited: true });
      appendFormalDetailField(fields, 'Retrieved evidence IDs', result.retrieved_evidence_ids, { wide: true });
      appendFormalDetailField(fields, 'Model', result.model_actually_called || result.model);
      appendFormalDetailField(fields, 'Provider', result.provider);
      appendFormalDetailField(fields, 'Participating agents', result.participating_agents, { wide: true });
      appendFormalDetailField(fields, 'Debate enabled', formalBoolean(result.debate?.enabled));
      appendFormalDetailField(fields, 'Debate rounds', result.debate?.rounds);
      appendFormalDetailField(fields, 'Consensus answer', result.debate?.final_consensus?.answer, { wide: true, cited: true });
      appendFormalDetailField(fields, 'Usable', formalBoolean(result.usable));
      appendFormalDetailField(fields, 'Fallback', formalBoolean(result.fallback));
      appendFormalDetailField(fields, 'Latency', result.latency_ms !== undefined ? result.latency_ms + ' ms' : null);
    } else if (summaryType === 'judgment') {
      appendFormalDetailField(fields, 'Prediction', result.prediction);
      appendFormalDetailField(fields, 'Confidence', result.confidence);
      appendFormalDetailField(fields, 'Reason', result.reason, { wide: true });
      appendFormalDetailField(fields, 'Reference label', result.reference_label);
      appendFormalDetailField(fields, 'Usable', formalBoolean(result.usable));
      appendFormalDetailField(fields, 'Latency', result.latency_ms !== undefined ? result.latency_ms + ' ms' : null);
      appendFormalDetailField(fields, 'Model', result.model_actually_called || result.model);
      appendFormalDetailField(fields, 'Provider', result.provider);
    } else if (summaryType === 'conflict') {
      appendFormalDetailField(fields, 'Prediction', result.prediction);
      appendFormalDetailField(fields, 'Answer', result.answer, { wide: true, cited: true });
      appendFormalDetailField(fields, 'Confidence', result.confidence);
      appendFormalDetailField(fields, 'Preserves both viewpoints', formalBoolean(result.preserves_both_viewpoints));
      appendFormalDetailField(fields, 'Cites both sources', formalBoolean(result.cites_both_sources));
      appendFormalDetailField(fields, 'Expresses uncertainty', formalBoolean(result.expresses_uncertainty));
      appendFormalDetailField(fields, 'Reason', result.reason, { wide: true });
      appendFormalDetailField(fields, 'Reference label', result.reference_label);
      appendFormalDetailField(fields, 'Usable', formalBoolean(result.usable));
      appendFormalDetailField(fields, 'Latency', result.latency_ms !== undefined ? result.latency_ms + ' ms' : null);
      appendFormalDetailField(fields, 'Model', result.model_actually_called || result.model);
      appendFormalDetailField(fields, 'Provider', result.provider);
    } else if (summaryType === 'multi_model_consensus') {
      appendFormalDetailField(fields, 'Final answer', result.final_answer, { wide: true, cited: true });
      appendFormalDetailField(fields, 'Evidence IDs', result.evidence_ids, { wide: true });
      appendFormalDetailField(fields, 'Cited evidence IDs', result.citations?.cited_evidence_ids, { wide: true });
      appendFormalDetailField(fields, 'Retrieved evidence IDs', result.citations?.retrieved_evidence_ids, { wide: true });
      appendFormalDetailField(fields, 'Citation precision', result.citations?.citation_precision);
      appendFormalDetailField(fields, 'Citation recall', result.citations?.citation_recall);
      appendFormalDetailField(fields, 'Consensus model', result.consensus_model);
      appendFormalDetailField(fields, 'Usable', formalBoolean(result.usable));
      appendFormalDetailField(fields, 'Latency', result.total_latency_seconds !== undefined ? result.total_latency_seconds + ' s' : null);
    }
    content.append(fields);
    const technical = formalTechnicalData(result);
    if (Object.keys(technical).length) {
      const details = element('details', 'formal-execution-technical');
      details.append(element('summary', '', 'Technical details'), element('pre', '', JSON.stringify(technical, null, 2)));
      content.append(details);
    }
    setFormalDetailPanelState('loaded');
  }

  function yieldForFormalDetailPaint() {
    return new Promise((resolve) => {
      if (typeof requestAnimationFrame === 'function') requestAnimationFrame(resolve);
      else setTimeout(resolve, 0);
    });
  }

  async function loadFormalExecutionDetail(sequence) {
    const requestedSequence = Number(sequence);
    const requestedRunId = activeFormalRunId;
    if (!requestedRunId || selectedFormalSequence !== requestedSequence) return;
    const token = ++formalDetailRequestToken;
    if (formalDetailAbortController) formalDetailAbortController.abort();
    const controller = new AbortController();
    formalDetailAbortController = controller;
    selectedFormalDetail = null;
    setFormalDetailPanelState('loading');
    try {
      await yieldForFormalDetailPaint();
      if (token !== formalDetailRequestToken || requestedRunId !== activeFormalRunId || requestedSequence !== selectedFormalSequence) return;
      const row = await apiGet('/api/formal-runs/' + encodeURIComponent(requestedRunId) + '/results/' + requestedSequence, controller.signal);
      if (token !== formalDetailRequestToken || requestedRunId !== activeFormalRunId || requestedSequence !== selectedFormalSequence || Number(row.sequence) !== requestedSequence) return;
      selectedFormalDetail = row;
      renderFormalExecutionDetail(row);
    } catch (error) {
      if (error.name !== 'AbortError' && token === formalDetailRequestToken && requestedRunId === activeFormalRunId && requestedSequence === selectedFormalSequence) setFormalDetailPanelState('error');
    } finally {
      if (formalDetailRequestToken === token) formalDetailAbortController = null;
    }
  }

  function toggleFormalExecutionDetail(sequence) {
    const nextSequence = Number(sequence);
    if (selectedFormalSequence === nextSequence) {
      clearFormalExecutionDetail();
      return;
    }
    formalDetailRequestToken += 1;
    if (formalDetailAbortController) formalDetailAbortController.abort();
    formalDetailAbortController = null;
    selectedFormalSequence = nextSequence;
    selectedFormalDetail = null;
    syncFormalDetailSelection();
    setFormalDetailPanelState('loading');
    loadFormalExecutionDetail(nextSequence);
  }

  function renderFormalExecutionCards(total, status) {
    const stream = $('#formal-execution-stream');
    const statusKey = [total, status?.status, status?.current_case, status?.current_condition].join('|');
    if (formalRenderedRevision === formalResultRevision && formalRenderedStatusKey === statusKey) return;
    const scrollTop = stream.scrollTop;
    stream.replaceChildren();
    orderedFormalResultRows().forEach((execution) => {
      const item = element('li', 'formal-execution-card');
      item.classList.toggle('is-failed', String(execution.status || '').toLowerCase() === 'failed');
      const heading = element('div', 'formal-execution-card-heading');
      heading.append(element('span', 'formal-execution-number', String(execution.sequence).padStart(3, '0') + ' / ' + total), element('strong', 'formal-execution-identity', (execution.case_id || '—') + ' · ' + (execution.condition || '—')), element('span', 'formal-execution-status', execution.status || 'Completed'));
      item.append(heading);
      const summary = element('dl', 'formal-scientific-summary');
      formalSummaryFields(execution).forEach((field) => {
        const wrapper = element('div', field.wide ? 'is-wide' : '');
        wrapper.append(element('dt', '', field.label), element('dd', '', field.value));
        summary.append(wrapper);
      });
      if (summary.children.length) item.append(summary);
      item.dataset.formalSequence = String(execution.sequence);
      const detailButton = element('button', 'secondary-action formal-detail-toggle', selectedFormalSequence === execution.sequence ? 'Hide full details' : 'View full details');
      detailButton.type = 'button'; detailButton.dataset.sequence = String(execution.sequence); detailButton.setAttribute('aria-controls', 'formal-execution-detail'); detailButton.setAttribute('aria-expanded', String(selectedFormalSequence === execution.sequence));
      detailButton.addEventListener('click', () => toggleFormalExecutionDetail(execution.sequence));
      item.append(detailButton);
      stream.append(item);
    });
    if (status && ['running', 'stop_requested'].includes(status.status)) {
      const running = element('li', 'formal-execution-card is-running');
      const heading = element('div', 'formal-execution-card-heading');
      heading.append(element('span', 'formal-execution-number', String(formalResultRows.size + 1).padStart(3, '0') + ' / ' + total), element('strong', 'formal-execution-identity', (status.current_case || '—') + ' · ' + (status.current_condition || '—')), element('span', 'formal-execution-status', status.status === 'stop_requested' ? 'Finishing safely' : 'Running'));
      running.append(heading);
      stream.append(running);
    }
    syncFormalDetailSelection();
    stream.scrollTop = scrollTop;
    formalRenderedRevision = formalResultRevision;
    formalRenderedStatusKey = statusKey;
  }

  function setPaperWorkbenchMode(mode) {
    const guided = mode === 'guided';
    $('#guided-paper-experiments').hidden = !guided;
    $('#consensus-form').hidden = guided;
    $('#custom-question-results').hidden = guided || $('#custom-question-results').dataset.hasResults !== 'true';
    $('#consensus-results').hidden = guided || $('#consensus-results').dataset.hasResult !== 'true';
    $('#guided-mode-tab').setAttribute('aria-selected', String(guided));
    $('#custom-mode-tab').setAttribute('aria-selected', String(!guided));
    $('#guided-mode-tab').tabIndex = guided ? 0 : -1;
    $('#custom-mode-tab').tabIndex = guided ? -1 : 0;
  }

  function lockedField(label, value) {
    const wrapper = element('div');
    wrapper.append(element('dt', '', label), element('dd', '', value || 'Not applicable'));
    return wrapper;
  }

  function formalConditionLabel(condition) {
    return condition.id + ' · ' + condition.name + (condition.stage ? ' · ' + condition.stage : '');
  }

  function selectFormalExperiment(item) {
    clearFormalExecutionDetail();
    selectedFormalExperiment = item;
    paperConfigurationApplied = true;
    activeFormalRunId = null;
    $$('.formal-experiment-card').forEach((card) => card.setAttribute('aria-pressed', String(card.dataset.experimentId === item.experiment_id)));
    $('#paper-configuration').hidden = false;
    setText('#paper-config-title', item.number + ' · ' + item.title);
    const fields = $('#paper-config-fields'); fields.replaceChildren();
    [
      ['Research question', item.research_question], ['Dataset', item.dataset],
      ['Original questions / cases', String(item.dataset_size)], ['Scheduled executions', String(item.scheduled_executions || item.planned_executions)],
      ['Paper conditions', item.conditions.map(formalConditionLabel).join(' | ')], ['Model(s)', item.models.join(' | ')],
      ['Retrieval', item.retrieval], ['Architecture', item.architecture],
    ].forEach(([label, value]) => fields.append(lockedField(label, value)));
    $('#formal-job-panel').hidden = true;
    $('#formal-empty-state').hidden = false;
    const canRun = (item.available_run_modes || []).includes('full_benchmark');
    $('#run-paper-experiment').disabled = !canRun;
    showMessage($('#formal-run-message'), item.disabled_reason || (canRun ? '' : 'Paper replay service is not currently available.'));
  }

  function renderFormalRegistry(items) {
    formalExperiments = items;
    const container = $('#formal-experiment-cards'); container.replaceChildren();
    items.forEach((item) => {
      const card = element('button', 'formal-experiment-card'); card.type = 'button'; card.dataset.experimentId = item.experiment_id; card.setAttribute('aria-pressed', 'false');
      card.append(element('span', '', item.number + ' · ' + item.paper_label), element('strong', '', item.title), element('small', '', item.research_question));
      card.addEventListener('click', () => selectFormalExperiment(item)); container.append(card);
    });
    if (items.length) selectFormalExperiment(items[0]);
  }

  async function loadFormalRegistry() {
    try {
      renderFormalRegistry(await apiGet('/api/formal-experiments'));
      const savedRun = localStorage.getItem('medirag-formal-run-id');
      if (savedRun) {
        clearFormalResultRows();
        activeFormalRunId = savedRun;
        setFormalSummaryFeedback('Restoring saved experiment results…', true);
        await refreshFormalRun({ restoring: true });
      }
    }
    catch (error) { $('#formal-experiment-cards').replaceChildren(element('p', 'consensus-message', 'Formal experiment registry unavailable: ' + error.message)); }
  }

  function elapsedClock(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds || 0)));
    const hours = String(Math.floor(total / 3600)).padStart(2, '0');
    const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
    const remainder = String(total % 60).padStart(2, '0');
    return hours + ':' + minutes + ':' + remainder;
  }

  function renderFormalStatus(status, options = {}) {
    if (activeFormalRunId && activeFormalRunId !== status.run_id) clearFormalExecutionDetail();
    activeFormalRunId = status.run_id;
    localStorage.setItem('medirag-formal-run-id', status.run_id);
    $('#formal-empty-state').hidden = true;
    $('#formal-job-panel').hidden = false;
    const stopped = status.status === 'stopped';
    const stopping = status.status === 'stop_requested';
    const active = status.status === 'queued' || status.status === 'running' || stopping;
    const resultLabel = stopped ? 'Partial replay result' : 'New replay result';
    setText('#formal-job-result-label', resultLabel); setText('#formal-download-result-label', resultLabel);
    setText('#formal-job-title', status.experiment_id + ' · ' + status.run_id); setText('#formal-job-status', stopping ? 'stop requested' : status.status);
    const completed = Number(status.completed || 0); const total = Number(status.total || 0); const percent = total ? Math.min(100, Math.round(completed / total * 100)) : 0;
    setText('#formal-job-progress', completed + ' / ' + total + ' completed'); setText('#formal-job-percent', percent + '%');
    $('#formal-progress-bar').max = Math.max(1, total); $('#formal-progress-bar').value = completed;
    setText('#formal-job-current', [status.current_case, status.current_condition].filter(Boolean).join(' · ') || 'Waiting for worker');
    setText('#formal-job-outcomes', status.successful + ' / ' + status.failed); setText('#formal-job-elapsed', elapsedClock(status.elapsed_seconds));
    $('#stop-formal-run').hidden = !active;
    $('#stop-formal-run').disabled = stopping;
    $('#stop-formal-run').textContent = stopping ? 'Stopping after current execution…' : 'Stop Run';
    $('#formal-stop-summary').hidden = !stopped;
    if (stopped) setText('#formal-stop-summary', 'Stopped after ' + completed + ' / ' + total + ' executions · Partial replay — not directly comparable to the complete paper result.');
    $$('.formal-experiment-card').forEach((card) => { card.disabled = active; });
    if (status.status === 'complete' || status.status === 'failed' || stopped) $('#run-paper-experiment').disabled = false;
    loadFormalResults(options);
    if (formalRunTimer) { clearTimeout(formalRunTimer); formalRunTimer = null; }
    if (active) formalRunTimer = setTimeout(refreshFormalRun, 2500);
  }

  async function refreshFormalRun(options = {}) {
    if (!activeFormalRunId) return;
    const requestedRunId = activeFormalRunId;
    try {
      const status = await apiGet('/api/formal-runs/' + encodeURIComponent(requestedRunId));
      if (requestedRunId !== activeFormalRunId) return;
      renderFormalStatus(status, options);
    }
    catch (error) {
      if (requestedRunId === activeFormalRunId) setFormalSummaryFeedback(error.message);
    }
  }

  function loadFormalResults({ restoring = false } = {}) {
    if (!activeFormalRunId) return;
    const requestedRunId = activeFormalRunId;
    if (formalSummaryLoad?.runId === requestedRunId) return formalSummaryLoad.promise;
    const token = ++formalSummaryLoadToken;
    if (restoring && formalResultRows.size === 0) setFormalSummaryFeedback('Restoring saved experiment results…', true);
    const promise = (async () => {
      try {
        let after = formalResultCursor;
        let data;
        do {
          const pageStart = after;
          data = await apiGet('/api/formal-runs/' + encodeURIComponent(requestedRunId) + '/summaries?after=' + after + '&limit=50');
          if (token !== formalSummaryLoadToken || requestedRunId !== activeFormalRunId) return;
          (data.results || []).forEach((execution) => {
            const sequence = Number(execution.sequence);
            if (!Number.isInteger(sequence)) return;
            const summary = compactFormalSummary({ ...execution, sequence });
            const previous = formalResultRows.get(sequence);
            if (!previous || JSON.stringify(previous) !== JSON.stringify(summary)) {
              formalResultRows.set(sequence, summary);
              formalResultRevision += 1;
            }
            after = Math.max(after, sequence);
          });
          const nextCursor = Number(data.next_cursor);
          if (Number.isInteger(nextCursor)) after = Math.max(after, nextCursor);
          if (data.has_more && after <= pageStart) throw new Error('Formal summary cursor did not advance.');
          formalResultCursor = Math.max(formalResultCursor, after);
        } while (data.has_more);
        if (token !== formalSummaryLoadToken || requestedRunId !== activeFormalRunId) return;
        const orderedRows = orderedFormalResultRows();
        setText('#formal-job-results', JSON.stringify({ status: data.status, final_metrics: data.final_metrics || {} }, null, 2));
        setText('#formal-historical-results', JSON.stringify(data.historical_paper_results || { label: 'Historical paper result', status: 'frozen_read_only' }, null, 2));
        renderFormalExecutionCards(Number(data.status?.total || orderedRows.length), data.status);
        const downloads = $('#formal-job-downloads'); downloads.replaceChildren();
        (data.downloads || []).forEach((file) => { const labels = { 'partial_report.md': 'Download Partial Report', 'partial_results.csv': 'Download CSV', 'partial_results.json': 'Download JSON' }; const link = element('a', 'secondary-action', labels[file.name] || file.name); link.href = API + '/api/formal-runs/' + encodeURIComponent(requestedRunId) + '/files/' + file.name.split('/').map(encodeURIComponent).join('/'); downloads.append(link); });
        clearFormalSummaryFeedback();
      }
      catch (error) {
        if (token === formalSummaryLoadToken && requestedRunId === activeFormalRunId) {
          setFormalSummaryFeedback('Could not refresh experiment results. Existing cards are preserved; reload to retry.');
        }
      }
      finally {
        if (formalSummaryLoad?.token === token) formalSummaryLoad = null;
      }
    })();
    formalSummaryLoad = { runId: requestedRunId, token, promise };
    return promise;
  }

  async function startFormalRun() {
    if (!selectedFormalExperiment || !paperConfigurationApplied) return;
    const button = $('#run-paper-experiment'); button.disabled = true;
    const body = { experiment_id: selectedFormalExperiment.experiment_id, run_mode: 'full_benchmark', confirm_full_benchmark: true };
    setFormalSummaryFeedback('');
    try { clearFormalResultRows(); renderFormalStatus(await api('/api/formal-runs', body)); }
    catch (error) { showMessage($('#formal-run-message'), error.message); button.disabled = false; }
  }

  async function stopFormalRun() {
    if (!activeFormalRunId) return;
    const button = $('#stop-formal-run'); button.disabled = true; button.textContent = 'Requesting stop…';
    try { renderFormalStatus(await api('/api/formal-runs/' + encodeURIComponent(activeFormalRunId) + '/stop')); }
    catch (error) { showMessage($('#formal-run-message'), error.message); button.disabled = false; button.textContent = 'Stop Run'; }
  }

  function showMessage(node, message) {
    node.textContent = message;
    node.hidden = !message;
  }

  let tcmRequestActive = false;
  let tcmProgressStarted = 0;
  let tcmProgressTimer = null;
  let tcmProgressStage = 'connecting';

  function updateTcmElapsed(elapsedMs) {
    $('#tcm-progress-elapsed').textContent = (elapsedMs / 1000).toFixed(1) + ' s';
  }

  function updateTcmProgress(stage) {
    tcmProgressStage = stage;
    const progressCopy = copy[language].progress;
    setText('#tcm-progress-status', progressCopy[stage]);
    setText('#tcm-progress-detail', progressCopy.detail);
  }

  function startTcmProgress() {
    const progress = $('#tcm-run-progress');
    tcmProgressStarted = performance.now();
    progress.hidden = false;
    progress.classList.remove('is-complete');
    progress.removeAttribute('data-frontend-total-ms');
    progress.dataset.requestStartedAt = new Date().toISOString();
    updateTcmProgress('connecting');
    updateTcmElapsed(0);
    clearInterval(tcmProgressTimer);
    tcmProgressTimer = setInterval(() => updateTcmElapsed(performance.now() - tcmProgressStarted), 100);
  }

  function finishTcmProgress(data, renderMs) {
    const progress = $('#tcm-run-progress');
    const totalMs = performance.now() - tcmProgressStarted;
    clearInterval(tcmProgressTimer);
    tcmProgressTimer = null;
    updateTcmProgress('complete');
    updateTcmElapsed(totalMs);
    progress.classList.add('is-complete');
    progress.dataset.frontendTotalMs = totalMs.toFixed(3);
    progress.dataset.renderMs = renderMs.toFixed(3);
    progress.dataset.networkAndParseMs = String(data.__clientTimings?.request_ms?.toFixed(3) || '0');
    progress.dataset.timeToHeadersMs = String(data.__clientTimings?.time_to_headers_ms?.toFixed(3) || '0');
    progress.dataset.jsonParseMs = String(data.__clientTimings?.json_parse_ms?.toFixed(3) || '0');
    progress.dataset.serverMs = String(data.__clientTimings?.server_ms?.toFixed(3) || '0');
    progress.dataset.backendTotalMs = String(data.timings?.total_ms || 0);
    progress.dataset.preprocessingMs = String(data.timings?.preprocessing_ms || 0);
    progress.dataset.retrievalMs = String(data.timings?.retrieval_ms || 0);
    progress.dataset.embeddingMs = String(data.timings?.embedding_ms || 0);
    progress.dataset.rerankingMs = String(data.timings?.reranking_ms || 0);
    progress.dataset.llmMs = String(data.timings?.llm_ms || 0);
    progress.dataset.postProcessingMs = String(data.timings?.post_processing_ms || 0);
    progress.dataset.serializationMs = Math.max(0, (data.__clientTimings?.server_ms || 0) - (data.timings?.total_ms || 0)).toFixed(3);
  }

  function cancelTcmProgress() {
    clearInterval(tcmProgressTimer);
    tcmProgressTimer = null;
    $('#tcm-run-progress').hidden = true;
  }

  function renderList(container, items, empty) {
    container.replaceChildren();
    (items.length ? items : [empty]).forEach((item) => container.append(element('li', '', String(item))));
  }

  function renderTcm(data) {
    const local = data.localized_result && (data.localized_result[language] || data.localized_result[data.response_language] || data.localized_result.en);
    setText('#tcm-summary', (local && local.summary) || data.summary || data.tcm_perspective);
    setText('#tcm-summary-full', (local && local.summary) || data.summary || data.tcm_perspective);
    setText('#tcm-confidence-score', Math.round((data.confidence?.score || 0) * 100) + '%');
    setText('#tcm-confidence-level', data.confidence?.level || 'low');
    setText('#tcm-generation-mode', data.generation_source || data.generation_mode);
    setText('#tcm-grounding-note', (local && local.grounding) || 'Educational research output grounded in the visible local corpus.');
    const patterns = $('#tcm-patterns'); patterns.replaceChildren();
    (data.possible_patterns || []).slice(0, 3).forEach((item) => {
      const localized = item.localized && (item.localized[language] || item.localized.en);
      const card = element('article', 'tcm-list-item');
      card.append(element('strong', '', localized?.pattern || item.pattern));
      card.append(element('p', '', localized?.rationale || item.rationale));
      patterns.append(card);
    });
    const formulas = $('#tcm-formulas'); formulas.replaceChildren();
    (data.related_herbs_or_formulas || []).slice(0, 3).forEach((item) => {
      const localized = item.localized && (item.localized[language] || item.localized.en);
      const card = element('article', 'tcm-list-item');
      card.append(element('strong', '', localized?.name || item.name));
      card.append(element('p', '', localized?.purpose || item.purpose));
      card.append(element('p', 'tcm-inline-warning', localized?.safety_warning || item.safety_warning));
      formulas.append(card);
    });
    renderList($('#tcm-safety-notes'), (data.localized_safety_notes && (data.localized_safety_notes[language] || data.localized_safety_notes.en)) || data.safety_notes || [], 'No additional safety note.');
    const evidence = $('#tcm-evidence'); evidence.replaceChildren();
    (data.evidence || []).forEach((item) => {
      const localized = item.localized && (item.localized[language] || item.localized.en);
      const card = element('article', 'tcm-evidence-item');
      card.append(element('strong', '', localized?.title || item.title));
      card.append(element('p', '', localized?.snippet || item.snippet));
      card.append(element('small', '', item.evidence_id + ' · ' + Math.round((item.relevance_score || 0) * 100) + '%'));
      evidence.append(card);
    });
    setText('#tcm-evidence-summary', (local && local.evidence_summary) || (data.evidence || []).length + ' evidence item(s)');
    setText('#tcm-generation-source', data.generation_source);
    setText('#tcm-llm-model', data.llm_model);
    setText('#tcm-response-language', data.response_language);
    setText('#tcm-evidence-count', String((data.evidence || []).length));
    setText('#tcm-retrieval-method', data.retrieval_method);
    setText('#tcm-meaningful-count', String(data.meaningful_match_count || 0));
    setText('#tcm-top-score', Math.round((data.top_relevance_score || 0) * 100) + '%');
    setText('#tcm-llm-error', data.llm_error || '—');
    setText('#tcm-confidence-reason', data.confidence?.reason || '');
    setText('#tcm-disclaimer', data.disclaimer || 'Research use only.');
    $('#tcm-results').hidden = false;
    $('#tcm-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const agentLabels = {
    single_rag: 'Single-RAG Baseline', syndrome: 'Syndrome Differentiation', herbal: 'Herbal Knowledge',
    acupuncture_meridian: 'Acupuncture & Meridian', constitution: 'Constitution', dietary_therapy: 'Dietary Therapy', lifestyle_yangsheng: 'Lifestyle & Yangsheng'
  };
  const conditionDescriptions = {
    C1: 'One evidence-backed specialist baseline using the active research corpus.', C2: 'Independent evidence-scoped specialists; irrelevant domains may abstain.',
    C3: 'Specialist outputs with deterministic weighted aggregation.', C4: 'Specialist outputs followed by structured deterministic debate.',
    C5: 'Specialist outputs evaluated by deterministic judge rubrics.', C6: 'Specialists, deterministic debate, and deterministic judge rubrics.'
  };
  const retrievalDescriptions = { R0: 'Deterministic lexical retrieval over the active corpus.', R1: 'Dense local-hash retrieval over the active corpus.', R2: 'Hybrid lexical and dense retrieval.', R3: 'Hybrid retrieval with local overlap reranking.' };
  const runtimeModels = {
    qwen: 'Qwen · Qwen/Qwen3-8B',
    glm: 'GLM · THUDM/GLM-Z1-9B-0414',
    deepseek: 'DeepSeek · deepseek-ai/DeepSeek-R1-0528-Qwen3-8B'
  };
  const runtimeModelProfiles = { M1: 'M1 · Homogeneous Qwen', M2: 'M2 · Heterogeneous' };
  let currentResearchRun = null;
  let currentComparison = null;

  function readableAgent(id, fallback) { return agentLabels[id] || fallback || id || 'Specialist'; }
  function renderCitedText(container, text) {
    container.replaceChildren();
    const parts = String(text || '').split(/(\[tcmv1-[^\]]+\])/g);
    parts.forEach((part) => {
      const match = part.match(/^\[(tcmv1-[^\]]+)\]$/);
      if (!match) container.append(document.createTextNode(part));
      else {
        const link = element('a', 'evidence-citation', part); link.href = '#' + match[1]; link.dataset.evidenceId = match[1];
        link.addEventListener('click', (event) => { event.preventDefault(); const target = document.getElementById(match[1]); if (target) { target.scrollIntoView({ behavior: 'smooth', block: 'center' }); target.classList.add('is-highlighted'); setTimeout(() => target.classList.remove('is-highlighted'), 1600); } });
        container.append(link);
      }
    });
  }
  function downloadText(filename, content, type) {
    const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([content], { type })); link.download = filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }
  function safeRunExport(data) {
    const copy = JSON.parse(JSON.stringify(data));
    if (copy.trace) { delete copy.trace.raw_query; delete copy.trace.api_key; delete copy.trace.environment; }
    return copy;
  }
  function runCsv(data) {
    const trace = data.trace || {}; const rows = [['run_id', 'condition', 'retrieval', 'corpus', 'model', 'provider_calls', 'successful_calls', 'generation_mode', 'fallback', 'latency_ms', 'participating_agents', 'evidence_ids']];
    rows.push([data.run_id, data.condition_id, trace.retrieval_strategy || '', trace.corpus_name || '', trace.model || '', trace.provider_calls || 0, trace.successful_provider_calls || 0, data.generation_mode || '', Boolean(trace.fallback_usage), trace.latency_ms || 0, (trace.participating_agents || []).join('; '), (trace.retrieved_evidence_ids || []).join('; ')]);
    return rows.map((row) => row.map((value) => '"' + String(value).replace(/"/g, '""') + '"').join(',')).join('\r\n');
  }
  function renderEvidence(data) {
    const container = $('#consensus-evidence'); container.replaceChildren();
    (data.retrieval || []).forEach((item) => {
      const card = element('article', 'evidence-row'); card.id = item.chunk_id;
      const score = item.rerank_score ?? item.fusion_score ?? item.semantic_score ?? item.lexical_score;
      const header = element('div', 'evidence-row-header'); header.append(element('strong', 'evidence-rank', '#' + item.rank)); header.append(element('span', 'evidence-source', item.source_metadata?.title || item.source_id || 'Source')); card.append(header);
      const meta = element('div', 'evidence-row-meta'); meta.append(element('span', '', item.retrieval_method || 'retrieval')); meta.append(element('span', '', typeof score === 'number' ? 'Relevance ' + Math.round(score * 100) + '%' : 'Relevance —')); card.append(meta);
      card.append(element('p', 'evidence-excerpt', item.chunk_text || 'Evidence excerpt unavailable.'));
      const details = element('details', 'evidence-details'); const summary = element('summary', '', 'Evidence details'); details.append(summary);
      const technical = element('div', 'evidence-technical'); technical.append(element('div', '', 'Chunk ID: ' + item.chunk_id)); technical.append(element('div', '', 'Source ID: ' + (item.source_id || '—'))); technical.append(element('div', '', 'Retrieval method: ' + (item.retrieval_method || '—'))); technical.append(element('div', '', 'Technical score: ' + (score ?? '—'))); technical.append(element('div', '', 'Topics: ' + ((item.topics || []).join(', ') || '—'))); technical.append(element('p', '', item.chunk_text || 'Evidence excerpt unavailable.'));
      const copy = element('button', 'text-action', 'Copy Chunk ID'); copy.type = 'button'; copy.addEventListener('click', async () => { try { await navigator.clipboard?.writeText(item.chunk_id); copy.textContent = 'Copied'; setTimeout(() => { copy.textContent = 'Copy Chunk ID'; }, 1400); } catch (_) { copy.textContent = 'Copy unavailable'; } }); technical.append(copy); details.append(technical); card.append(details); container.append(card);
    });
    setText('#evidence-count-badge', (data.retrieval || []).length + ' item' + ((data.retrieval || []).length === 1 ? '' : 's'));
  }

  function researchRunPresentation(traceData, data) {
    const generationMode = traceData.generation_mode || data.generation_mode || 'deterministic';
    const fallback = traceData.fallback_usage === true;
    if (fallback) return { label: 'Fallback', badge: 'Deterministic fallback', className: 'research-alert-warning', title: 'Live model output was unavailable or rejected.', detail: 'Deterministic fallback was used.' };
    if (generationMode === 'llm') return { label: 'Live LLM', badge: 'Live LLM response', className: 'research-alert-success', title: 'Live LLM response', detail: 'The configured model completed this run without fallback.' };
    return { label: 'Deterministic', badge: 'Deterministic mode', className: 'research-alert-neutral', title: 'Deterministic mode', detail: 'This run intentionally used deterministic processing; no failed live-model fallback is implied.' };
  }
  function renderIntegratedJudges(data) {
    const support = data.evidence_support;
    const conflict = data.conflict_status;
    const safety = data.safety_assessment;
    const confidence = data.evidence_confidence;
    const unavailable = 'Not available for this condition';
    const pct = (value) => typeof value === 'number' ? Math.round(value * 100) + '%' : '—';
    const supportNode = $('#integrated-evidence-support'); supportNode.replaceChildren();
    if (support) {
      [['Evidence coverage', support.evidence_coverage], ['Citation coverage', support.citation_coverage], ['Retrieval sufficiency', support.retrieval_sufficiency], ['Verified evidence ratio', support.verified_evidence_ratio]].forEach(([label, value]) => supportNode.append(element('div', 'integrated-judge-row', label + ': ' + pct(value))));
    } else supportNode.append(element('p', 'muted-note', unavailable));
    const conflictNode = $('#integrated-conflict'); conflictNode.replaceChildren();
    if (conflict) {
      conflictNode.append(element('div', 'integrated-judge-row', 'Status: ' + (conflict.has_unresolved_conflict ? 'Unresolved conflict' : 'No unresolved conflict')));
      conflictNode.append(element('div', 'integrated-judge-row', 'Score: ' + pct(conflict.conflict_score)));
      [...(conflict.unresolved_conflicts || [])].forEach((item) => conflictNode.append(element('div', 'integrated-judge-row', item)));
    } else conflictNode.append(element('p', 'muted-note', unavailable));
    const safetyNode = $('#integrated-safety'); safetyNode.replaceChildren();
    if (safety) {
      safetyNode.append(element('div', 'integrated-judge-row', 'Evidence-supported caution assessment: ' + safety.assessment));
      safetyNode.append(element('div', 'integrated-judge-row', 'Safety score: ' + pct(safety.source_grounded_safety_score)));
      if (safety.findings?.length) safety.findings.forEach((finding) => safetyNode.append(element('div', 'integrated-judge-row', finding.rule_id + ' · ' + finding.severity + ' · ' + finding.explanation)));
      else safetyNode.append(element('div', 'integrated-judge-row', 'No source-grounded safety flags'));
    } else safetyNode.append(element('p', 'muted-note', unavailable));
    const confidenceNode = $('#integrated-confidence'); confidenceNode.replaceChildren();
    if (confidence) {
      confidenceNode.append(element('div', 'integrated-judge-row', 'Evidence confidence: ' + pct(confidence.score) + ' · band: ' + confidence.band));
      (confidence.signal_contributions || []).forEach((signal) => confidenceNode.append(element('div', 'integrated-judge-row', 'Signal · ' + signal.signal + ': +' + pct(signal.contribution))));
      (confidence.penalties || []).forEach((penalty) => confidenceNode.append(element('div', 'integrated-judge-row', 'Penalty · ' + penalty.signal + ': −' + pct(penalty.applied_penalty))));
      const caps = confidence.caps_applied || [];
      caps.forEach((cap) => confidenceNode.append(element('div', 'integrated-judge-row', 'Cap · ' + cap)));
      if (!caps.length) confidenceNode.append(element('div', 'integrated-judge-row', 'Caps applied: none'));
    } else confidenceNode.append(element('p', 'muted-note', unavailable));
  }
  function renderResearchRun(data, options = {}) {
    const detailLoading = $('#custom-detail-loading'); const detailContent = $('#custom-detail-content');
    if (detailLoading) detailLoading.hidden = true;
    if (detailContent) detailContent.hidden = false;
    currentResearchRun = data; const traceData = data.trace || {}; const outputs = data.agent_outputs || []; const active = outputs.filter((agent) => !agent.abstained); const abstained = outputs.filter((agent) => agent.abstained);
    const selectedCount = (traceData.active_agents || outputs).length || 1; const coverage = Math.round((active.length / selectedCount) * 100); const activeSupport = active.length ? Math.round(active.reduce((sum, agent) => sum + (agent.confidence || 0), 0) / active.length * 100) : 0;
    const presentation = researchRunPresentation(traceData, data);
    const configuredSpecialists = Array.isArray(traceData.experiment_config?.specialist_model_targets) ? traceData.experiment_config.specialist_model_targets : [];
    const configuredConsensus = traceData.experiment_config?.consensus_model_target;
    const requestedModelParts = [];
    if (configuredSpecialists.length) requestedModelParts.push('Specialists: ' + configuredSpecialists.map((target) => runtimeModels[target] || target).join(' / '));
    if (configuredConsensus) requestedModelParts.push('Consensus: ' + (runtimeModels[configuredConsensus] || configuredConsensus));
    const requestedModel = requestedModelParts.join(' · ') || '—';
    const attemptedModels = [...new Set((traceData.provider_attempts || []).map((attempt) => attempt.model).filter(Boolean))];
    const attemptedProvider = (traceData.provider_attempts || []).find((attempt) => attempt.provider)?.provider;
    const runProvider = traceData.provider && traceData.provider !== 'none' ? traceData.provider : attemptedProvider || (traceData.provider_configured && traceData.provider_configured !== 'none' ? traceData.provider_configured : '—');
    const runModel = traceData.model && traceData.model !== 'none' ? traceData.model : typeof traceData.provider_calls === 'number' && traceData.provider_calls > 0 ? 'No successful model output' : '—';
    setText('#runtime-provider', runProvider === 'siliconflow' ? 'SiliconFlow' : runProvider); setText('#runtime-model', runModel); setText('#runtime-llm', presentation.label === 'Live LLM' ? 'Live LLM' : presentation.label === 'Fallback' ? 'Fallback' : 'Deterministic mode'); $('#runtime-llm').classList.toggle('is-success', presentation.label === 'Live LLM');
    setText('#consensus-strategy-badge', data.condition_id + ' · ' + data.condition_name); setText('#consensus-run-id', data.run_id); setText('#summary-retrieval', (traceData.retrieval_strategy || '—') + ' · ' + ({ R0: 'Lexical', R1: 'Dense', R2: 'Hybrid', R3: 'Hybrid + rerank' }[traceData.retrieval_strategy] || ''));
    setText('#summary-condition', data.condition_id + ' · ' + data.condition_name); setText('#summary-corpus', (traceData.corpus_name || '—') + ' · ' + (traceData.corpus_chunk_count || 0).toLocaleString() + ' chunks'); setText('#summary-model', runModel); setText('#summary-calls', (traceData.provider_calls || 0) + ' / ' + (traceData.successful_provider_calls || 0) + ' succeeded'); setText('#summary-latency', ((traceData.latency_ms || 0) / 1000).toFixed(1) + ' s'); setText('#summary-status', presentation.label); setText('#summary-fallback', traceData.fallback_usage === true ? 'Yes' : 'No'); setText('#summary-participants', active.map((agent) => readableAgent(agent.agent_id, agent.agent_name)).join(', ') || 'None');
    const summaryStatus = $('#summary-status'); summaryStatus.className = 'status-badge ' + (traceData.fallback_usage === true ? 'status-warning' : presentation.label === 'Live LLM' ? 'status-success' : 'status-neutral');
    setText('#active-agent-support', activeSupport + '%'); setText('#specialist-coverage', active.length + ' / ' + selectedCount); setText('#specialist-coverage-note', abstained.length + ' specialist' + (abstained.length === 1 ? '' : 's') + ' abstained'); setText('#consensus-confidence', Math.round((data.confidence || 0) * 100) + '%'); setText('#consensus-generation-badge', presentation.badge); setText('#integrated-answer-heading', data.condition_id === 'C1' ? 'Final answer' : 'Final integrated answer'); renderCitedText($('#consensus-summary-text'), data.final_answer);
    const runStatus = $('#research-fallback-banner'); runStatus.className = 'research-alert ' + presentation.className; setText('#research-run-status-title', presentation.title); setText('#research-run-status-detail', presentation.detail); runStatus.hidden = false;
    const agents = $('#consensus-agents'); agents.replaceChildren(); active.forEach((agent) => { const card = element('article', 'specialist-card'); const heading = element('div', 'specialist-card-heading'); heading.append(element('div', 'specialist-card-title', readableAgent(agent.agent_id, agent.agent_name))); heading.append(element('span', 'status-badge status-active', 'ACTIVE')); card.append(heading); const meta = element('div', 'specialist-card-meta'); if (agent.model) meta.append(element('span', '', 'Model: ' + agent.model)); meta.append(element('span', '', 'Generation: ' + (agent.generation_mode === 'llm' ? 'LLM' : 'Deterministic'))); meta.append(element('span', '', 'Evidence support: ' + Math.round((agent.confidence || 0) * 100) + '%')); card.append(meta); const answer = element('p', 'specialist-answer'); renderCitedText(answer, (agent.claims || []).map((claim) => claim.text).join(' ') || 'No evidence-linked claim.'); card.append(answer); agents.append(card); });
    const abstainDetails = $('#abstained-specialists'); abstainDetails.hidden = !abstained.length; setText('#abstained-count', abstained.length + ' specialist' + (abstained.length === 1 ? '' : 's') + ' abstained'); const abstainList = $('#consensus-abstaining-list'); abstainList.replaceChildren(); abstained.forEach((agent) => { const row = element('div', 'abstained-row'); row.append(element('strong', '', readableAgent(agent.agent_id, agent.agent_name))); row.append(element('span', 'status-badge status-warning', 'ABSTAINED')); row.append(element('span', '', agent.abstention_reason || 'No scoped evidence matched.')); abstainList.append(row); });
    const debateVisible = Boolean(traceData.debate_enabled) || (data.agreements || []).length || (data.disagreements || []).length; $('#consensus-debate-section').hidden = !debateVisible; if (debateVisible) { renderList($('#consensus-agreements'), data.agreements || [], 'No explicit agreement detected.'); renderList($('#consensus-disagreements'), data.disagreements || [], 'No explicit disagreement detected.'); }
    const judgesVisible = Boolean(traceData.judges_enabled) || (data.judge_outputs || []).length; $('#consensus-judge-section').hidden = !judgesVisible; const judges = $('#consensus-judges'); judges.replaceChildren(); (data.judge_outputs || []).forEach((judge) => { const card = element('article', 'judge-card'); card.append(element('strong', '', judge.judge_name + ' · ' + Math.round((judge.score || 0) * 100) + '%')); card.append(element('p', '', (judge.findings || []).join(' ') || judge.reasoning_summary)); judges.append(card); });
    const integratedVisible = Boolean(data.evidence_support || data.conflict_status || data.safety_assessment || data.evidence_confidence); const integratedPanel = $('#integrated-judge-panel'); if (integratedPanel) { integratedPanel.hidden = !integratedVisible; if (integratedVisible) renderIntegratedJudges(data); }
    renderList($('#consensus-safety'), data.safety_flags || [], 'No structured safety flag.'); renderList($('#consensus-limitations'), data.limitations || [], 'No additional limitation.'); renderEvidence(data);
    const reportedNumber = (value) => typeof value === 'number' && Number.isFinite(value) ? String(value) : '—';
    const reportedPair = (left, right) => left && right ? left + ' · ' + right : left || right || '—';
    const systemAbstained = traceData.termination_stage === 'planner_scope_gate';
    const participating = Array.isArray(traceData.participating_agents) ? traceData.participating_agents.map((id) => readableAgent(id)).join(', ') || (systemAbstained ? 'none · system stopped before specialists' : 'none') : '—';
    const abstaining = Array.isArray(traceData.abstaining_agents) ? traceData.abstaining_agents.map((id) => readableAgent(id)).join(', ') || (systemAbstained ? 'not run · system-level abstention' : 'none') : '—';
    const stageSummary = typeof traceData.debate_enabled === 'boolean' && typeof traceData.judges_enabled === 'boolean' ? 'termination=' + (traceData.termination_stage || 'completed') + ' · debate=' + traceData.debate_enabled + ' · judges=' + traceData.judges_enabled : '—';
    const corpusSummary = traceData.corpus_name ? traceData.corpus_name + (typeof traceData.corpus_chunk_count === 'number' ? ' · ' + traceData.corpus_chunk_count.toLocaleString() + ' chunks' : '') + (traceData.corpus_mode ? ' · mode=' + traceData.corpus_mode : '') : '—';
    setText('#consensus-latency', typeof traceData.latency_ms === 'number' ? traceData.latency_ms + ' ms' : '—'); setText('#consensus-requested-model', requestedModel); setText('#consensus-model', runModel); setText('#consensus-attempted-models', attemptedModels.join(', ') || '—'); setText('#consensus-provider', runProvider === 'siliconflow' ? 'SiliconFlow' : runProvider); setText('#consensus-api-calls', reportedNumber(traceData.provider_calls)); setText('#consensus-successful-calls', reportedNumber(traceData.successful_provider_calls)); setText('#consensus-call-failures', reportedNumber(traceData.failed_provider_calls)); setText('#consensus-generation-mode', traceData.generation_mode || data.generation_mode || '—'); setText('#consensus-fallback', typeof traceData.fallback_usage === 'boolean' ? traceData.fallback_usage ? 'Yes' : 'No' : '—'); setText('#consensus-corpus', corpusSummary); setText('#consensus-fixture-used', traceData.retrieval_strategy || '—'); setText('#consensus-embedding', reportedPair(traceData.embedding_provider, traceData.embedding_model)); setText('#consensus-reranker', reportedPair(traceData.reranker_provider, traceData.reranker)); setText('#consensus-participating', participating); setText('#consensus-abstaining', abstaining); setText('#consensus-stages', stageSummary); setText('#consensus-score-formula', traceData.support_score_formula || '—'); $('#consensus-trace').textContent = JSON.stringify(safeRunExport(data), null, 2);
    $('#consensus-results').dataset.hasResult = 'true'; $('#consensus-results').hidden = $('#custom-mode-tab').getAttribute('aria-selected') !== 'true'; if (options.scroll !== false) $('#consensus-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderCompare(data) {
    currentComparison = data; const grid = $('#research-compare-grid'); grid.replaceChildren();
    (data.results || []).forEach((result) => {
      const trace = result.trace || {}; const outputs = result.agent_outputs || []; const activeOutputs = outputs.filter((agent) => !agent.abstained); const active = activeOutputs.length || (trace.participating_agents || []).length; const selected = (trace.active_agents || outputs).length || 1; const activeSupport = activeOutputs.length ? activeOutputs.reduce((sum, agent) => sum + (agent.confidence || 0), 0) / activeOutputs.length : 0;
      const card = element('article', 'research-compare-card glass'); const heading = element('div', 'compare-card-heading'); heading.append(element('span', 'consensus-experimental-badge', result.condition_id)); heading.append(element('span', 'muted-badge', result.generation_mode || 'deterministic')); card.append(heading); card.append(element('h3', '', result.condition_name));
      const answer = element('p', 'compare-answer'); renderCitedText(answer, result.final_answer); card.append(answer);
      const metrics = element('div', 'compare-metrics'); [['Active support', Math.round(activeSupport * 100) + '%'], ['Coverage', active + ' / ' + selected], ['Evidence', (trace.retrieved_evidence_ids || []).length + ' chunks'], ['Calls', (trace.provider_calls || 0) + ' / ' + (trace.successful_provider_calls || 0)], ['Latency', ((trace.latency_ms || 0) / 1000).toFixed(1) + ' s'], ['Fallback', trace.fallback_usage ? 'Yes' : 'No']].forEach(([label, value]) => { const item = element('div'); item.append(element('span', '', label)); item.append(element('strong', '', value)); metrics.append(item); }); card.append(metrics);
      const details = element('details', 'research-card-details'); details.append(element('summary', '', 'Technical details')); details.append(element('pre', '', JSON.stringify(safeRunExport(result), null, 2))); card.append(details); grid.append(card);
    });
    setText('#research-compare-metrics', JSON.stringify({ comparison_id: data.comparison_id, metrics: data.metric_comparison, limitations: data.limitations }, null, 2));
    $('#research-compare-results').hidden = false;
  }

  $$('.toggle-btn').forEach((button) => button.addEventListener('click', () => {
    if (button.dataset.view === 'workbench') { setMode('multi'); setView('workbench', { push: true }); }
    else setView('home', { push: true });
  }));
  $$('.demo-option').forEach((button) => {
    button.addEventListener('click', () => setMode(button.dataset.mode, { push: true }));
    button.addEventListener('keydown', (event) => { if (event.key === 'ArrowRight' || event.key === 'ArrowDown') { event.preventDefault(); const next = button.nextElementSibling || $$('.demo-option')[0]; next.focus(); setMode(next.dataset.mode, { push: true }); } if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') { event.preventDefault(); const options = $$('.demo-option'); const previous = button.previousElementSibling || options[options.length - 1]; previous.focus(); setMode(previous.dataset.mode, { push: true }); } });
  });
  $$('.language-btn').forEach((button) => button.addEventListener('click', () => applyLanguage(button.dataset.lang)));
  $('#guided-mode-tab').addEventListener('click', () => setPaperWorkbenchMode('guided'));
  $('#custom-mode-tab').addEventListener('click', () => setPaperWorkbenchMode('custom'));
  $('#run-paper-experiment').addEventListener('click', startFormalRun);
  $('#stop-formal-run').addEventListener('click', stopFormalRun);
  $$('.tcm-sample').forEach((button) => button.addEventListener('click', () => { $('#tcm-question').value = button.dataset.question; $('#tcm-question').focus(); }));

  $('#tcm-consult-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (tcmRequestActive) return;
    const form = event.currentTarget;
    const message = $('#tcm-form-message');
    const question = $('#tcm-question').value.trim();
    if (question.length < 3) return showMessage(message, 'Please enter a longer question.');
    tcmRequestActive = true;
    showMessage(message, '');
    $('#tcm-submit').disabled = true;
    $('#tcm-submit').classList.add('is-loading');
    form.setAttribute('aria-busy', 'true');
    startTcmProgress();
    try {
      const values = Object.fromEntries(new FormData(form));
      const data = await api('/api/tcm/consult', { question, context: { age: values.age || '', gender: values.gender || '', duration: values.duration || '', medications: values.medications || '', pregnancy: values.pregnancy || '', allergies: values.allergies || '' } }, () => updateTcmProgress('processing'));
      updateTcmProgress('rendering');
      const renderStarted = performance.now();
      renderTcm(data);
      finishTcmProgress(data, performance.now() - renderStarted);
    } catch (error) {
      cancelTcmProgress();
      showMessage(message, error.message + '. The static website remains available; start the backend to run research.');
    } finally {
      tcmRequestActive = false;
      $('#tcm-submit').disabled = false;
      $('#tcm-submit').classList.remove('is-loading');
      form.setAttribute('aria-busy', 'false');
    }
  });

  let researchRequestActive = false; let researchProgressTimer = null; let researchProgressStarted = 0; let researchProgressStage = 'connecting';
  const activeResearchProgressStates = new Set(['queued', 'running', 'stop_requested']);
  function setResearchProgressVisualState(status) {
    const progress = $('#consensus-progress'); const active = activeResearchProgressStates.has(status);
    progress.classList.toggle('is-active', active); progress.classList.toggle('is-terminal', !active);
    ['complete', 'stopped', 'failed'].forEach((terminalStatus) => progress.classList.toggle('is-' + terminalStatus, status === terminalStatus));
  }
  function setResearchProgress(stage) {
    researchProgressStage = stage;
    const messages = {
      connecting: ['Connecting to research backend…', 'Elapsed time is measured directly; no percentage is estimated.'],
      waking: ['Backend may be waking from an idle state.', 'Your experiment is still running.'],
      processing: ['Processing retrieved evidence and model output…', 'The backend response has returned and the workbench is preparing the result.'],
      queued: ['Run queued', 'The cloud worker will begin this custom experiment shortly.'],
      running: ['Run in progress', 'Completed rows will appear as the cloud worker finishes them.'],
      stop_requested: ['Stop requested', 'The current atomic execution will finish before the run stops.'],
      restoring: ['Restoring saved run', 'Checking its durable status before marking it active or complete.'],
      complete: ['Run complete', 'The completed response and trace are shown below.'],
      stopped: ['Run stopped', 'Completed rows remain available as a partial replay result.'],
      failed: ['Request failed', 'Check the message below, then retry when the backend is available.'],
    };
    const message = messages[stage] || messages.connecting;
    setText('#consensus-progress-status', message[0]); setText('#consensus-progress-detail', message[1]);
  }
  function startResearchProgress() {
    researchProgressStarted = performance.now(); $('#consensus-progress').hidden = false; setResearchProgressVisualState('queued'); setResearchProgress('connecting'); setText('#consensus-progress-elapsed', '0.0 s'); clearInterval(researchProgressTimer);
    researchProgressTimer = setInterval(() => { const elapsed = performance.now() - researchProgressStarted; setText('#consensus-progress-elapsed', (elapsed / 1000).toFixed(1) + ' s'); if (elapsed >= 8000 && researchProgressStage === 'connecting') setResearchProgress('waking'); }, 250);
  }
  function stopResearchProgress(stage = 'complete') { clearInterval(researchProgressTimer); researchProgressTimer = null; setResearchProgressVisualState(stage); setResearchProgress(stage); setText('#consensus-progress-elapsed', ((performance.now() - researchProgressStarted) / 1000).toFixed(1) + ' s'); }
  function setResearchControlsDisabled(disabled) {
    $$('#consensus-form textarea, #consensus-form select, #consensus-form input').forEach((control) => { control.disabled = disabled; });
    if (!disabled) updateCustomQuestionCount();
    setText('#consensus-submit-label', disabled ? 'Running custom experiment…' : 'Run Custom Experiment');
  }
  function updateConditionHelp() { const condition = $('#consensus-strategy').value; setText('#condition-help', conditionDescriptions[condition]); setText('#retrieval-help', retrievalDescriptions[$('#consensus-retrieval').value]); }
  function bindChoiceGroup(name, selectSelector) {
    const select = $(selectSelector);
    const radios = $$('input[name="' + name + '"]');
    const syncFromSelect = () => { radios.forEach((input) => { input.checked = input.value === select.value; }); updateConditionHelp(); };
    radios.forEach((input) => input.addEventListener('change', () => { if (input.checked) { select.value = input.value; syncFromSelect(); } }));
    select.addEventListener('change', syncFromSelect);
    syncFromSelect();
  }
  function selectedModelConfigurationPayload() {
    return {
      specialist_model_targets: [$('#specialist-model-a').value, $('#specialist-model-b').value, $('#specialist-model-c').value],
      consensus_model_target: $('#custom-consensus-model').value,
    };
  }
  function selectedCustomQuestionCount() {
    const selected = $('#custom-question-count').value;
    return selected === 'custom' ? Number($('#custom-question-count-value').value) : Number(selected);
  }
  function updateCustomQuestionCount() {
    const custom = $('#custom-question-count').value === 'custom'; const label = $('#custom-question-count-label'); const input = $('#custom-question-count-value');
    label.hidden = false; label.classList.toggle('is-disabled', !custom); label.setAttribute('aria-disabled', String(!custom)); input.disabled = !custom;
    if (custom) input.removeAttribute('tabindex'); else input.tabIndex = -1;
  }
  function clearCustomResultDisplay() {
    currentResearchRun = null;
    currentCustomSummary = null;
    $('#consensus-results').hidden = true;
    $('#consensus-results').dataset.hasResult = 'false';
    $('#custom-detail-loading').hidden = true;
    $('#custom-detail-content').hidden = true;
    $('#research-fallback-banner').hidden = true;
    ['#consensus-summary-text', '#consensus-evidence', '#consensus-agents', '#consensus-abstaining-list', '#consensus-agreements', '#consensus-disagreements', '#consensus-judges', '#consensus-safety', '#consensus-limitations'].forEach((selector) => $(selector).replaceChildren());
    $('#consensus-trace').textContent = '';
    $('#consensus-debate-section').hidden = true;
    $('#consensus-judge-section').hidden = true;
    $('#abstained-specialists').hidden = true;
    setText('#evidence-count-badge', '0 items');
    ['#summary-condition', '#summary-retrieval', '#summary-model', '#summary-status', '#summary-corpus', '#summary-calls', '#summary-latency', '#summary-fallback', '#summary-participants', '#consensus-run-id', '#consensus-generation-badge', '#active-agent-support', '#specialist-coverage', '#consensus-confidence', '#consensus-latency', '#consensus-requested-model', '#consensus-model', '#consensus-attempted-models', '#consensus-provider', '#consensus-api-calls', '#consensus-successful-calls', '#consensus-call-failures', '#consensus-generation-mode', '#consensus-fallback', '#consensus-corpus', '#consensus-fixture-used', '#consensus-embedding', '#consensus-reranker', '#consensus-participating', '#consensus-abstaining', '#consensus-stages', '#consensus-score-formula'].forEach((selector) => setText(selector, '—'));
  }
  let activeCustomRunId = null;
  let customRunTimer = null;
  let customResultCursor = 0;
  const customResultSummaries = new Map();
  let customRunStatusSnapshot = null;
  let selectedCustomSequence = null;
  let currentCustomSummary = null;
  let customSelectionManual = false;
  let customDetailRequestToken = 0;

  function orderedCustomResultSummaries() { return [...customResultSummaries.values()].sort((left, right) => Number(left.sequence) - Number(right.sequence)); }
  function customSummaryGeneration(summary) {
    if (summary.fallback === true) return 'Fallback';
    if (summary.generation_mode === 'llm') return 'Live LLM';
    return summary.generation_mode || '—';
  }
  function customSummaryLatency(summary) { return typeof summary.latency_ms === 'number' ? (summary.latency_ms / 1000).toFixed(1) + ' s' : '—'; }

  function placeCustomDetail() {
    const section = $('#custom-question-results'); const container = $('#custom-question-results-list'); const detail = $('#consensus-results');
    if (!section || !container || !detail) return;
    if (selectedCustomSequence === null) { section.after(detail); return; }
    const card = [...container.querySelectorAll('.custom-question-result-card')].find((item) => Number(item.dataset.sequence) === selectedCustomSequence);
    if (card) card.after(detail); else section.after(detail);
  }

  function renderCustomQuestionResults() {
    const rows = orderedCustomResultSummaries(); const total = Number(customRunStatusSnapshot?.total || rows.length);
    const section = $('#custom-question-results'); const container = $('#custom-question-results-list'); const detail = $('#consensus-results'); const fragment = document.createDocumentFragment();
    rows.forEach((summary) => {
      const card = element('article', 'custom-question-result-card' + (summary.status === 'Failed' ? ' is-failed' : '') + (Number(summary.sequence) === selectedCustomSequence ? ' is-selected' : '')); card.dataset.sequence = String(summary.sequence);
      const header = element('div', 'custom-question-result-heading'); header.append(element('span', 'muted-badge', summary.sequence + ' of ' + total), element('span', 'status-badge', summary.status || 'Completed')); card.append(header);
      card.append(element('h3', '', summary.question || summary.question_id || 'Question unavailable'));
      card.append(element('span', 'custom-final-answer-label', summary.condition === 'C1' ? 'Final answer' : 'Final integrated answer'));
      card.append(element('p', summary.error ? 'custom-result-error' : 'custom-final-answer', summary.error || summary.final_answer || 'Final answer unavailable.'));
      const metadata = element('div', 'custom-question-result-meta');
      [customSummaryGeneration(summary), (summary.models || []).join(' / ') || summary.model || null, customSummaryLatency(summary), summary.fallback === true ? 'Fallback: Yes' : null].filter(Boolean).forEach((value) => metadata.append(element('span', '', value)));
      card.append(metadata);
      if (!summary.error && summary.status !== 'Failed') {
        const expanded = Number(summary.sequence) === selectedCustomSequence;
        const button = element('button', 'secondary-action', expanded ? 'Hide full details' : 'View full details'); button.type = 'button'; button.setAttribute('aria-expanded', String(expanded)); button.setAttribute('aria-controls', 'consensus-results'); button.addEventListener('click', () => expanded ? collapseCustomResult() : selectCustomResult(Number(summary.sequence), true)); card.append(button);
      }
      fragment.append(card);
    });
    if (detail && detail.parentElement === container) section.after(detail);
    container.replaceChildren(fragment);
    setText('#custom-question-results-count', rows.length + ' persisted question' + (rows.length === 1 ? '' : 's'));
    section.dataset.hasResults = String(rows.length > 0);
    section.hidden = rows.length === 0 || $('#custom-mode-tab').getAttribute('aria-selected') !== 'true';
    ['#print-custom-qa', '#download-custom-qa-json', '#download-custom-qa-csv'].forEach((selector) => { $(selector).disabled = rows.length === 0; });
    placeCustomDetail();
  }

  function clearCustomBatchDisplay() {
    customDetailRequestToken += 1;
    customResultSummaries.clear(); customRunStatusSnapshot = null; selectedCustomSequence = null; customSelectionManual = false;
    const detail = $('#consensus-results'); if (detail && detail.parentElement === $('#custom-question-results-list')) $('#custom-question-results').after(detail);
    $('#custom-question-results-list').replaceChildren(); $('#custom-question-results').dataset.hasResults = 'false'; $('#custom-question-results').hidden = true;
    setText('#custom-question-results-count', '0 persisted questions'); clearCustomResultDisplay(); $('#custom-question-results').after($('#consensus-results'));
  }

  function collapseCustomResult() {
    customDetailRequestToken += 1;
    selectedCustomSequence = null;
    currentCustomSummary = null;
    clearCustomResultDisplay();
    renderCustomQuestionResults();
  }

  async function selectCustomResult(sequence, manual = false) {
    const summary = customResultSummaries.get(Number(sequence));
    if (!summary || summary.error || summary.status === 'Failed') return;
    if (manual) customSelectionManual = true;
    selectedCustomSequence = Number(sequence); renderCustomQuestionResults();
    if (currentCustomSummary?.sequence === selectedCustomSequence && currentResearchRun) return;
    const requestToken = ++customDetailRequestToken;
    clearCustomResultDisplay();
    setText('#selected-question-position', 'Question ' + summary.sequence + ' of ' + Number(customRunStatusSnapshot?.total || customResultSummaries.size));
    setText('#selected-question-text', summary.question || summary.question_id || 'Question unavailable');
    placeCustomDetail();
    const loading = $('#custom-detail-loading'); loading.hidden = false; setText('#custom-detail-loading-title', 'Loading question details…'); setText('#custom-detail-loading-detail', 'Retrieving the saved answer, evidence, and specialist outputs.'); $('#custom-detail-retry').hidden = true; $('#consensus-results').hidden = false;
    try {
      await yieldForCustomDetailPaint();
      if (requestToken !== customDetailRequestToken) return;
      const row = await apiGet('/api/custom-runs/' + encodeURIComponent(activeCustomRunId) + '/results/' + selectedCustomSequence);
      if (requestToken !== customDetailRequestToken || Number(row.sequence) !== selectedCustomSequence) return;
      currentCustomSummary = summary;
      renderResearchRun(row.result, { scroll: manual });
      setText('#selected-question-position', 'Question ' + summary.sequence + ' of ' + Number(customRunStatusSnapshot?.total || customResultSummaries.size));
      setText('#selected-question-text', summary.question || summary.question_id || 'Question unavailable');
    } catch (error) {
      if (requestToken === customDetailRequestToken) { loading.hidden = false; setText('#custom-detail-loading-title', 'Unable to load question details'); setText('#custom-detail-loading-detail', error.message || 'The saved result could not be retrieved.'); const retry = $('#custom-detail-retry'); retry.hidden = false; retry.onclick = () => selectCustomResult(selectedCustomSequence, true); $('#custom-detail-content').hidden = true; $('#consensus-results').hidden = false; }
    }
  }

  function customQaExport() {
    const rows = orderedCustomResultSummaries(); const first = rows[0] || {};
    return {
      run_id: activeCustomRunId,
      result_origin: customRunStatusSnapshot?.status === 'stopped' ? 'partial_replay_result' : 'new_exploratory_run',
      formal_paper_reproduction: false,
      status: customRunStatusSnapshot?.status || null,
      completed: Number(customRunStatusSnapshot?.completed || rows.length),
      total: Number(customRunStatusSnapshot?.total || rows.length),
      condition: first.condition || null,
      retrieval: first.retrieval || null,
      models: [...new Set(rows.flatMap((row) => row.models || (row.model ? [row.model] : [])))],
      questions: rows.map((row) => ({ sequence: row.sequence, question_id: row.question_id, question: row.question, final_answer: row.final_answer, status: row.status, error: row.error, condition: row.condition, retrieval: row.retrieval, model: row.model, models: row.models || [], generation_mode: row.generation_mode, fallback: row.fallback, latency_ms: row.latency_ms, evidence_count: row.evidence_count })),
    };
  }

  function customQaCsv() {
    const rows = [['sequence', 'question_id', 'question', 'final_answer', 'status', 'error', 'condition', 'retrieval', 'model', 'generation_mode', 'fallback', 'latency_ms', 'evidence_count']];
    orderedCustomResultSummaries().forEach((item) => rows.push([item.sequence, item.question_id || '', item.question || '', item.final_answer || '', item.status || '', item.error || '', item.condition || '', item.retrieval || '', item.model || '', item.generation_mode || '', typeof item.fallback === 'boolean' ? item.fallback : '', typeof item.latency_ms === 'number' ? item.latency_ms : '', item.evidence_count ?? '']));
    return rows.map((row) => row.map((value) => '"' + String(value).replace(/"/g, '""') + '"').join(',')).join('\r\n');
  }

  function buildCustomPrintReport() {
    const data = customQaExport(); const report = $('#custom-print-report'); report.replaceChildren();
    report.append(element('h1', '', 'TCM Custom Research Workbench'));
    const metadata = element('div', 'custom-print-metadata');
    [['Run ID', data.run_id || '—'], ['Condition', data.condition || '—'], ['Retrieval', data.retrieval || '—'], ['Models', data.models.join(', ') || '—'], ['Completed', data.completed + ' / ' + data.total]].forEach(([label, value]) => { const row = element('p'); row.append(element('strong', '', label + ': '), document.createTextNode(String(value))); metadata.append(row); });
    report.append(metadata);
    data.questions.forEach((item) => { const section = element('section', 'custom-print-question'); section.append(element('h2', '', 'Question ' + item.sequence), element('p', 'custom-print-question-text', item.question || item.question_id || 'Question unavailable'), element('h3', '', item.condition === 'C1' ? 'Final answer' : 'Final integrated answer'), element('p', '', item.error || item.final_answer || 'Final answer unavailable.')); report.append(section); });
    return report;
  }

  function printCustomQaReport() {
    if (!customResultSummaries.size) return;
    const report = buildCustomPrintReport(); report.hidden = false; report.setAttribute('aria-hidden', 'false'); document.body.classList.add('is-printing-custom-qa');
    try { window.print(); }
    finally { document.body.classList.remove('is-printing-custom-qa'); report.hidden = true; report.setAttribute('aria-hidden', 'true'); report.replaceChildren(); }
  }

  function setCustomRestoreLoading(visible) { $('#custom-restore-loading').hidden = !visible; }
  function yieldForCustomDetailPaint() {
    return new Promise((resolve) => {
      if (typeof requestAnimationFrame === 'function') requestAnimationFrame(resolve);
      else setTimeout(resolve, 0);
    });
  }
  function yieldForCustomRestorePaint() {
    return new Promise((resolve) => {
      if (typeof requestAnimationFrame === 'function') requestAnimationFrame(resolve);
      else setTimeout(resolve, 0);
    });
  }

  async function refreshCustomRun(restored = false) {
    if (!activeCustomRunId) return;
    try {
      const status = await apiGet('/api/custom-runs/' + encodeURIComponent(activeCustomRunId));
      const results = await apiGet('/api/custom-runs/' + encodeURIComponent(activeCustomRunId) + '/results/summary?after=' + customResultCursor);
      const newRows = results.results || [];
      if (newRows.length) {
        customResultCursor = Math.max(customResultCursor, ...newRows.map((row) => Number(row.sequence || 0)));
        newRows.forEach((row) => customResultSummaries.set(Number(row.sequence), row));
      }
      customRunStatusSnapshot = status;
      renderCustomQuestionResults();
      const persistedCount = customResultSummaries.size;
      const totalCount = Number(status.total || persistedCount);
      const customActive = ['queued', 'running', 'stop_requested'].includes(status.status);
      if (customActive && !researchProgressTimer) startResearchProgress();
      setResearchProgressVisualState(status.status);
      const activeStatus = status.status === 'queued' ? 'Queued for cloud worker…' : status.status === 'running' ? persistedCount >= totalCount ? 'Finalizing custom run…' : 'Running question ' + (persistedCount + 1) + ' of ' + totalCount + '…' : status.status === 'stop_requested' ? 'Stopping after the active question…' : status.status === 'complete' ? 'Run complete' : status.status === 'stopped' ? 'Partial replay result' : 'Run failed';
      setText('#consensus-progress-status', activeStatus);
      setText('#consensus-progress-detail', persistedCount + ' / ' + totalCount + ' persisted · ' + (persistedCount >= totalCount && status.status === 'running' ? 'waiting for terminal status' : (status.current_stage || status.status)));
      $('#stop-custom-run').hidden = !customActive;
      $('#stop-custom-run').disabled = status.status === 'stop_requested';
      $('#stop-custom-run').textContent = status.status === 'stop_requested' ? 'Stopping after current question…' : 'Stop Run';
      const partialDownloads = $('#custom-partial-downloads'); partialDownloads.replaceChildren();
      if (status.status === 'stopped') {
        const labels = { 'partial_report.md': 'Download Partial Report', 'partial_results.csv': 'Download CSV', 'partial_results.json': 'Download JSON' };
        (results.downloads || []).filter((file) => labels[file.name]).forEach((file) => { const link = element('a', 'secondary-action', labels[file.name]); link.href = API + '/api/custom-runs/' + encodeURIComponent(activeCustomRunId) + '/files/' + file.name.split('/').map(encodeURIComponent).join('/'); partialDownloads.append(link); });
        partialDownloads.hidden = false;
      } else partialDownloads.hidden = true;
      if (customActive) {
        showMessage($('#consensus-message'), persistedCount + ' of ' + totalCount + ' custom questions completed so far. Persisted answers are shown below as they finish.');
        clearTimeout(customRunTimer);
        customRunTimer = setTimeout(refreshCustomRun, 2500);
        return;
      }
      researchRequestActive = false;
      setResearchControlsDisabled(false);
      $('#consensus-submit').disabled = false;
      $('#consensus-submit').classList.remove('is-loading');
      $('#consensus-form').setAttribute('aria-busy', 'false');
      stopResearchProgress(status.status === 'complete' ? 'complete' : status.status === 'stopped' ? 'stopped' : 'failed');
      if (typeof status.elapsed_seconds === 'number') setText('#consensus-progress-elapsed', elapsedClock(status.elapsed_seconds));
      setText('#consensus-progress-status', status.status === 'complete' ? 'Run complete' : status.status === 'stopped' ? 'Partial replay result' : 'Run failed');
      setText('#consensus-progress-detail', persistedCount + ' / ' + totalCount + ' persisted · ' + (status.status === 'complete' ? 'complete' : status.status === 'stopped' ? 'stopped' : (status.current_stage || status.status)));
      showMessage($('#consensus-message'), status.status === 'complete'
        ? (restored ? 'Restored completed run. ' : '') + persistedCount + ' of ' + totalCount + ' custom questions completed in the cloud. All persisted answers are shown below.'
        : status.status === 'stopped'
        ? (restored ? 'Restored partial run. ' : '') + 'Stopped after ' + persistedCount + ' / ' + totalCount + ' executions. Partial replay — not directly comparable to the complete paper result.'
        : status.error || 'The Custom experiment failed.');
    }
    catch (error) {
      if (String(error.message).includes('Custom run not found')) {
        localStorage.removeItem('medirag-custom-run-id'); activeCustomRunId = null; researchRequestActive = false;
        clearCustomBatchDisplay(); setResearchControlsDisabled(false); $('#consensus-submit').disabled = false; $('#consensus-submit').classList.remove('is-loading'); $('#consensus-form').setAttribute('aria-busy', 'false'); stopResearchProgress('failed');
        return showMessage($('#consensus-message'), 'The previous Custom run is no longer retained. Start a new experiment when ready.');
      }
      clearTimeout(customRunTimer);
      customRunTimer = setTimeout(refreshCustomRun, 5000);
      showMessage($('#consensus-message'), 'Waiting to reconnect to the queued Custom experiment: ' + error.message);
    }
  }

  async function resumeSavedCustomRun() {
    const saved = localStorage.getItem('medirag-custom-run-id');
    if (!saved) { setCustomRestoreLoading(false); return; }
    setCustomRestoreLoading(true);
    try {
      await yieldForCustomRestorePaint();
      clearCustomBatchDisplay(); customResultCursor = 0;
      activeCustomRunId = saved;
      researchRequestActive = true;
      setResearchControlsDisabled(true);
      $('#consensus-submit').disabled = true;
      $('#consensus-submit').classList.add('is-loading');
      $('#consensus-form').setAttribute('aria-busy', 'true');
      researchProgressStarted = performance.now(); $('#consensus-progress').hidden = false; clearInterval(researchProgressTimer); researchProgressTimer = null; setResearchProgressVisualState('restoring'); setResearchProgress('restoring'); setText('#consensus-progress-elapsed', '—');
      await refreshCustomRun(true);
    } finally {
      setCustomRestoreLoading(false);
    }
  }

  async function stopCustomRun() {
    if (!activeCustomRunId) return;
    const button = $('#stop-custom-run'); button.disabled = true; button.textContent = 'Requesting stop…';
    try { await api('/api/custom-runs/' + encodeURIComponent(activeCustomRunId) + '/stop'); await refreshCustomRun(); }
    catch (error) { showMessage($('#consensus-message'), error.message); button.disabled = false; button.textContent = 'Stop Run'; }
  }

  bindChoiceGroup('architecture-condition', '#consensus-strategy'); bindChoiceGroup('retrieval-strategy', '#consensus-retrieval');
  $('#custom-question-count').addEventListener('change', updateCustomQuestionCount); updateCustomQuestionCount();
  $('#stop-custom-run').addEventListener('click', stopCustomRun);
  $('#consensus-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (researchRequestActive) return; const message = $('#consensus-message'); const button = $('#consensus-submit'); const questionText = $('#consensus-question').value.trim(); const questions = questionText.split(/\r?\n/).map((question) => question.trim()).filter(Boolean); const requestedCount = selectedCustomQuestionCount();
    if (!Number.isInteger(requestedCount) || requestedCount < 1 || requestedCount > 100) return showMessage(message, 'Choose a question count from 1 to 100.');
    if (questions.length < requestedCount || questions.slice(0, requestedCount).some((question) => question.length < 3)) return showMessage(message, 'Enter at least ' + requestedCount + ' valid question' + (requestedCount === 1 ? '' : 's') + ', one per line.');
    clearTimeout(customRunTimer); customRunTimer = null; activeCustomRunId = null; customResultCursor = 0; clearCustomBatchDisplay();
    researchRequestActive = true; showMessage(message, ''); setResearchControlsDisabled(true); button.disabled = true; button.classList.add('is-loading'); event.currentTarget.setAttribute('aria-busy', 'true'); startResearchProgress();
    try {
      const status = await api('/api/custom-runs', { questions: questions.slice(0, requestedCount), condition_id: $('#consensus-strategy').value, retrieval_strategy: $('#consensus-retrieval').value, ...selectedModelConfigurationPayload(), active_agents: ['syndrome', 'herbal', 'acupuncture_meridian', 'constitution', 'dietary_therapy', 'lifestyle_yangsheng'], active_judges: ['evidence', 'hallucination', 'safety', 'conflict', 'confidence', 'provenance'], top_k: 4, debate_rounds: 1, include_trace: true });
      activeCustomRunId = status.run_id;
      localStorage.setItem('medirag-custom-run-id', activeCustomRunId);
      setText('#consensus-progress-status', 'Queued for cloud worker…');
      await refreshCustomRun();
    }
    catch (error) { researchRequestActive = false; stopResearchProgress('failed'); showMessage(message, error.message + '. Verify the research backend is online and try again.'); setResearchControlsDisabled(false); button.disabled = false; button.classList.remove('is-loading'); event.currentTarget.setAttribute('aria-busy', 'false'); }
  });

  $('#research-compare-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const message = $('#research-compare-message'); const button = event.currentTarget.querySelector('button[type="submit"]');
    const question = $('#research-compare-question').value.trim(); const conditions = $$('input[name="condition"]:checked').map((item) => item.value);
    if (question.length < 3 || !conditions.length) return showMessage(message, 'Enter a question and select at least one condition.');
    showMessage(message, ''); button.disabled = true;
    try { renderCompare(await api('/api/research/compare', { question, conditions, retrieval_strategy: $('#research-compare-retrieval').value, top_k: Number($('#research-compare-top-k').value), iterative_retrieval: $('#research-compare-reflection').checked, active_agents: ['syndrome', 'herbal', 'acupuncture_meridian', 'constitution', 'dietary_therapy', 'lifestyle_yangsheng'], active_judges: ['evidence', 'hallucination', 'safety', 'conflict', 'confidence', 'provenance'] })); }
    catch (error) { showMessage(message, error.message); } finally { button.disabled = false; }
  });

  $('#copy-run-id').addEventListener('click', () => { if (currentResearchRun?.run_id) navigator.clipboard?.writeText(currentResearchRun.run_id); });
  $('#copy-run-json').addEventListener('click', async (event) => { if (!currentResearchRun) return; const button = event.currentTarget; try { await navigator.clipboard?.writeText(JSON.stringify(safeRunExport(currentResearchRun), null, 2)); button.textContent = 'Copied'; setTimeout(() => { button.textContent = 'Copy JSON'; }, 1400); } catch (_) { button.textContent = 'Copy unavailable'; } });
  $('#download-run-json').addEventListener('click', () => { if (currentResearchRun) { const exported = safeRunExport(currentResearchRun); exported.question = currentCustomSummary?.question || currentResearchRun.question || ''; downloadText('tcm-run_' + currentResearchRun.condition_id + '_' + (currentResearchRun.trace?.retrieval_strategy || 'R0') + '_' + currentResearchRun.run_id + '.json', JSON.stringify(exported, null, 2), 'application/json;charset=utf-8'); } });
  $('#download-run-csv').addEventListener('click', () => { if (currentResearchRun) downloadText('tcm-run_' + currentResearchRun.condition_id + '_' + (currentResearchRun.trace?.retrieval_strategy || 'R0') + '_' + currentResearchRun.run_id + '.csv', runCsv(currentResearchRun), 'text/csv;charset=utf-8'); });
  $('#print-custom-qa').addEventListener('click', printCustomQaReport);
  $('#download-custom-qa-json').addEventListener('click', () => { if (customResultSummaries.size) downloadText('tcm-custom-qa_' + activeCustomRunId + '.json', JSON.stringify(customQaExport(), null, 2), 'application/json;charset=utf-8'); });
  $('#download-custom-qa-csv').addEventListener('click', () => { if (customResultSummaries.size) downloadText('tcm-custom-qa_' + activeCustomRunId + '.csv', customQaCsv(), 'text/csv;charset=utf-8'); });
  $('#download-compare-json').addEventListener('click', () => { if (currentComparison) downloadText('tcm-comparison_' + currentComparison.comparison_id + '.json', JSON.stringify(safeRunExport(currentComparison), null, 2), 'application/json;charset=utf-8'); });
  $('#download-compare-csv').addEventListener('click', () => { if (currentComparison) { const rows = [['condition', 'condition_name', 'run_id', 'model', 'provider_calls', 'successful_calls', 'latency_ms', 'fallback', 'evidence_ids']]; (currentComparison.results || []).forEach((result) => { const trace = result.trace || {}; rows.push([result.condition_id, result.condition_name, result.run_id, trace.model || '', trace.provider_calls || 0, trace.successful_provider_calls || 0, trace.latency_ms || 0, Boolean(trace.fallback_usage), (trace.retrieved_evidence_ids || []).join('; ')]); }); downloadText('tcm-comparison_' + currentComparison.comparison_id + '.csv', rows.map((row) => row.map((value) => '"' + String(value).replace(/"/g, '""') + '"').join(',')).join('\r\n'), 'text/csv;charset=utf-8'); } });
  window.addEventListener('popstate', () => {
    if (location.hash === '#workbench' || location.hash === '#legacy-demo' || location.hash === '#research-workbench' || location.hash === '#research-compare') {
      setView('workbench');
      setMode(location.hash === '#research-compare' ? 'compare' : location.hash === '#legacy-demo' ? 'single' : 'multi');
    } else setView('home');
  });
  const locationLabel = isLocalDevelopment ? 'Local' : 'Online';
  setText('#workbench-location-label', locationLabel + ' Research Workbench'); setText('#runtime-location', 'Checking backend');
  fetch(API + '/health').then((response) => { if (!response.ok) throw new Error('Health check failed (' + response.status + ')'); return response.json(); }).then((data) => {
    const profile = locationLabel;
    const corpusLabel = (data.corpus_name || data.active_corpus) + ' · ' + (data.corpus_chunk_count || 0) + ' chunks';
    const providerLabel = 'provider configured=' + data.provider_configured + ' · LLM execution=' + (data.llm_execution_enabled ? 'enabled' : 'disabled');
    setText('.prototype-status span:last-child', profile + ' · ' + corpusLabel + ' · ' + providerLabel);
    setText('#consensus-corpus-status', profile + ' uses ' + corpusLabel + '. Scores below are evidence-support signals, not medical correctness.');
    setText('#compare-corpus-status', profile + ' · ' + corpusLabel + '.');
    setText('#runtime-corpus', data.corpus_name || data.active_corpus || 'Corpus unavailable'); setText('#runtime-chunks', Number(data.corpus_chunk_count || 0).toLocaleString() + ' chunks');
    const configuredProvider = String(data.provider_configured || 'Provider not reported'); setText('#runtime-provider', configuredProvider === 'siliconflow' ? 'SiliconFlow' : configuredProvider); setText('#runtime-model', data.llm_model || '—'); setText('#runtime-llm', data.llm_execution_enabled ? 'Live LLM' : 'Deterministic mode');
    $('#workbench-runtime-strip').classList.toggle('is-online', !isLocalDevelopment); $('#runtime-llm').classList.toggle('is-success', Boolean(data.llm_execution_enabled));
    $('.prototype-status').classList.toggle('is-live', true);
  }).catch(() => { setText('.prototype-status span:last-child', 'Backend offline · static interface remains available'); setText('#runtime-location', 'Backend unavailable'); setText('#runtime-corpus', 'Corpus not confirmed'); setText('#runtime-chunks', '— chunks'); setText('#runtime-provider', 'Provider not confirmed'); setText('#runtime-model', '—'); setText('#runtime-llm', 'Backend unavailable'); $('#runtime-llm').classList.remove('is-success'); $('#workbench-runtime-strip').classList.add('is-offline'); });

  applyLanguage('en'); updateConditionHelp(); setPaperWorkbenchMode('guided'); loadFormalRegistry(); resumeSavedCustomRun();
  if (location.hash === '#workbench' || location.hash === '#legacy-demo' || location.hash === '#research-workbench' || location.hash === '#research-compare') {
    setView('workbench');
    setMode(location.hash === '#research-compare' ? 'compare' : location.hash === '#legacy-demo' ? 'single' : 'multi');
  } else setView('home');
}());
