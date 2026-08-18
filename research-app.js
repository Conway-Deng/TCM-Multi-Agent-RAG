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
      const header = element('div', 'evidence-row-header'); header.append(element('strong', '', '#' + item.rank)); header.append(element('span', 'muted-badge', item.source_metadata?.title || item.source_id || 'Source')); header.append(element('code', '', item.chunk_id)); card.append(header);
      const meta = element('div', 'evidence-row-meta'); meta.append(element('span', '', 'Method: ' + (item.retrieval_method || '—'))); meta.append(element('span', '', 'Score: ' + (item.lexical_score ?? item.rerank_score ?? item.semantic_score ?? item.fusion_score ?? '—'))); meta.append(element('span', '', 'Category: ' + ((item.topics || []).join(', ') || '—'))); card.append(meta);
      const details = element('details', 'evidence-details'); const summary = element('summary', '', 'View excerpt'); details.append(summary); details.append(element('p', '', item.chunk_text || 'Evidence excerpt unavailable.')); card.append(details);
      const copy = element('button', 'text-action', 'Copy Chunk ID'); copy.type = 'button'; copy.addEventListener('click', () => navigator.clipboard?.writeText(item.chunk_id)); card.append(copy); container.append(card);
    });
    setText('#evidence-count-badge', (data.retrieval || []).length + ' item' + ((data.retrieval || []).length === 1 ? '' : 's'));
  }
  function renderResearchRun(data) {
    currentResearchRun = data; const traceData = data.trace || {}; const outputs = data.agent_outputs || []; const active = outputs.filter((agent) => !agent.abstained); const abstained = outputs.filter((agent) => agent.abstained);
    const selectedCount = (traceData.active_agents || outputs).length || 1; const coverage = Math.round((active.length / selectedCount) * 100); const activeSupport = active.length ? Math.round(active.reduce((sum, agent) => sum + (agent.confidence || 0), 0) / active.length * 100) : 0;
    setText('#consensus-strategy-badge', data.condition_id + ' · ' + data.condition_name); setText('#consensus-run-id', data.run_id); setText('#summary-retrieval', (traceData.retrieval_strategy || '—') + ' · ' + ({ R0: 'Lexical', R1: 'Dense', R2: 'Hybrid', R3: 'Hybrid + rerank' }[traceData.retrieval_strategy] || ''));
    setText('#summary-corpus', (traceData.corpus_name || '—') + ' · ' + (traceData.corpus_chunk_count || 0).toLocaleString() + ' chunks'); setText('#summary-model', traceData.model !== 'none' ? (traceData.model || '—') : 'Not called'); setText('#summary-calls', (traceData.provider_calls || 0) + ' / ' + (traceData.successful_provider_calls || 0) + ' succeeded'); setText('#summary-latency', ((traceData.latency_ms || 0) / 1000).toFixed(1) + ' s'); setText('#summary-generation', traceData.generation_mode || data.generation_mode || '—'); setText('#summary-fallback', traceData.fallback_usage ? 'Yes' : 'No'); setText('#summary-participants', active.map((agent) => readableAgent(agent.agent_id, agent.agent_name)).join(', ') || 'None');
    setText('#active-agent-support', activeSupport + '%'); setText('#specialist-coverage', active.length + ' / ' + selectedCount); setText('#specialist-coverage-note', abstained.length + ' specialist' + (abstained.length === 1 ? '' : 's') + ' abstained'); setText('#consensus-confidence', Math.round((data.confidence || 0) * 100) + '%'); setText('#consensus-generation-badge', traceData.generation_mode === 'llm' && !traceData.fallback_usage ? 'Real LLM response' : (traceData.fallback_usage ? 'Deterministic fallback' : (traceData.generation_mode || 'Deterministic'))); renderCitedText($('#consensus-summary-text'), data.final_answer);
    $('#research-fallback-banner').hidden = !traceData.fallback_usage;
    const agents = $('#consensus-agents'); agents.replaceChildren(); active.forEach((agent) => { const card = element('article', 'specialist-card'); const heading = element('div', 'specialist-card-heading'); heading.append(element('div', 'specialist-card-title', readableAgent(agent.agent_id, agent.agent_name))); heading.append(element('span', 'status-badge status-active', 'ACTIVE')); card.append(heading); const meta = element('div', 'specialist-card-meta'); meta.append(element('span', '', 'Evidence support ' + Math.round((agent.confidence || 0) * 100) + '%')); meta.append(element('span', '', agent.generation_mode === 'llm' ? 'LLM' : 'Deterministic')); card.append(meta); const answer = element('p', 'specialist-answer'); renderCitedText(answer, (agent.claims || []).map((claim) => claim.text).join(' ') || 'No evidence-linked claim.'); card.append(answer); agents.append(card); });
    const abstainDetails = $('#abstained-specialists'); abstainDetails.hidden = !abstained.length; setText('#abstained-count', abstained.length + ' specialist' + (abstained.length === 1 ? '' : 's') + ' abstained'); const abstainList = $('#consensus-abstaining-list'); abstainList.replaceChildren(); abstained.forEach((agent) => { const row = element('div', 'abstained-row'); row.append(element('strong', '', readableAgent(agent.agent_id, agent.agent_name))); row.append(element('span', '', agent.abstention_reason || 'No scoped evidence matched.')); abstainList.append(row); });
    const debateVisible = Boolean(traceData.debate_enabled) || (data.agreements || []).length || (data.disagreements || []).length; $('#consensus-debate-section').hidden = !debateVisible; if (debateVisible) { renderList($('#consensus-agreements'), data.agreements || [], 'No explicit agreement detected.'); renderList($('#consensus-disagreements'), data.disagreements || [], 'No explicit disagreement detected.'); }
    const judgesVisible = Boolean(traceData.judges_enabled) || (data.judge_outputs || []).length; $('#consensus-judge-section').hidden = !judgesVisible; const judges = $('#consensus-judges'); judges.replaceChildren(); (data.judge_outputs || []).forEach((judge) => { const card = element('article', 'judge-card'); card.append(element('strong', '', judge.judge_name + ' · ' + Math.round((judge.score || 0) * 100) + '%')); card.append(element('p', '', (judge.findings || []).join(' ') || judge.reasoning_summary)); judges.append(card); });
    renderList($('#consensus-safety'), data.safety_flags || [], 'No structured safety flag.'); renderList($('#consensus-limitations'), data.limitations || [], 'No additional limitation.'); renderEvidence(data);
    setText('#consensus-latency', (traceData.latency_ms || 0) + ' ms'); setText('#consensus-api-calls', (traceData.provider_calls || 0) + ' attempted · ' + (traceData.successful_provider_calls || 0) + ' succeeded'); setText('#consensus-call-failures', (traceData.failed_provider_calls || 0) + ' failed · fallback=' + Boolean(traceData.fallback_usage)); setText('#consensus-generation-mode', traceData.generation_mode || data.generation_mode || 'deterministic'); setText('#consensus-corpus', (traceData.corpus_name || 'unknown') + ' · ' + (traceData.corpus_chunk_count || 0) + ' chunks · mode=' + (traceData.corpus_mode || 'unknown')); setText('#consensus-provider', traceData.provider_configured || 'unknown'); setText('#consensus-model', traceData.model || 'none'); setText('#consensus-fixture-used', traceData.retrieval_strategy || 'not run'); setText('#consensus-embedding', (traceData.embedding_provider || 'none') + ' · ' + (traceData.embedding_model || 'none')); setText('#consensus-reranker', (traceData.reranker_provider || 'none') + ' · ' + (traceData.reranker || 'none')); const systemAbstained = traceData.termination_stage === 'planner_scope_gate'; setText('#consensus-participating', (traceData.participating_agents || []).map((id) => readableAgent(id)).join(', ') || (systemAbstained ? 'none · system stopped before specialists' : 'none')); setText('#consensus-abstaining', (traceData.abstaining_agents || []).map((id) => readableAgent(id)).join(', ') || (systemAbstained ? 'not run · system-level abstention' : 'none')); setText('#consensus-stages', 'termination=' + (traceData.termination_stage || 'completed') + ' · debate=' + Boolean(traceData.debate_enabled) + ' · judges=' + Boolean(traceData.judges_enabled)); setText('#consensus-score-formula', traceData.support_score_formula || 'Evidence support across selected agents; not medical correctness'); $('#consensus-trace').textContent = JSON.stringify(safeRunExport(data), null, 2);
    $('#consensus-results').hidden = false; $('#consensus-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  function setResearchProgress(stage) { researchProgressStage = stage; const labels = copy[language].researchProgress; setText('#consensus-progress-status', labels[stage] || labels.connecting); }
  function startResearchProgress() { researchProgressStarted = performance.now(); $('#consensus-progress').hidden = false; setResearchProgress('connecting'); setText('#consensus-progress-elapsed', '0.0 s'); clearInterval(researchProgressTimer); researchProgressTimer = setInterval(() => setText('#consensus-progress-elapsed', ((performance.now() - researchProgressStarted) / 1000).toFixed(1) + ' s'), 100); }
  function stopResearchProgress(stage = 'complete') { clearInterval(researchProgressTimer); researchProgressTimer = null; setResearchProgress(stage); }
  function updateConditionHelp() { const condition = $('#consensus-strategy').value; setText('#condition-help', conditionDescriptions[condition]); setText('#retrieval-help', retrievalDescriptions[$('#consensus-retrieval').value]); }
  $('#consensus-strategy').addEventListener('change', updateConditionHelp); $('#consensus-retrieval').addEventListener('change', updateConditionHelp);
  $('#consensus-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (researchRequestActive) return; const message = $('#consensus-message'); const button = $('#consensus-submit'); const question = $('#consensus-question').value.trim(); if (question.length < 3) return showMessage(message, 'Please enter a longer question.');
    researchRequestActive = true; showMessage(message, ''); button.disabled = true; button.classList.add('is-loading'); event.currentTarget.setAttribute('aria-busy', 'true'); startResearchProgress();
    try { setResearchProgress('retrieving'); const data = await api('/api/research/run', { question, condition_id: $('#consensus-strategy').value, retrieval_strategy: $('#consensus-retrieval').value, active_agents: ['syndrome', 'herbal', 'acupuncture_meridian', 'constitution', 'dietary_therapy', 'lifestyle_yangsheng'], active_judges: ['evidence', 'hallucination', 'safety', 'conflict', 'confidence', 'provenance'], top_k: 4, debate_rounds: 1, include_trace: true }, () => setResearchProgress('generating')); setResearchProgress('evaluating'); renderResearchRun(data); setResearchProgress('rendering'); }
    catch (error) { stopResearchProgress('failed'); showMessage(message, error.message + '. The research interface remains available.'); } finally { researchRequestActive = false; button.disabled = false; button.classList.remove('is-loading'); event.currentTarget.setAttribute('aria-busy', 'false'); }
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
  $('#download-run-json').addEventListener('click', () => { if (currentResearchRun) { const exported = safeRunExport(currentResearchRun); exported.question = $('#consensus-question').value; downloadText('tcm-run_' + currentResearchRun.condition_id + '_' + (currentResearchRun.trace?.retrieval_strategy || 'R0') + '_' + currentResearchRun.run_id + '.json', JSON.stringify(exported, null, 2), 'application/json;charset=utf-8'); } });
  $('#download-run-csv').addEventListener('click', () => { if (currentResearchRun) downloadText('tcm-run_' + currentResearchRun.condition_id + '_' + (currentResearchRun.trace?.retrieval_strategy || 'R0') + '_' + currentResearchRun.run_id + '.csv', runCsv(currentResearchRun), 'text/csv;charset=utf-8'); });
  $('#download-compare-json').addEventListener('click', () => { if (currentComparison) downloadText('tcm-comparison_' + currentComparison.comparison_id + '.json', JSON.stringify(safeRunExport(currentComparison), null, 2), 'application/json;charset=utf-8'); });
  $('#download-compare-csv').addEventListener('click', () => { if (currentComparison) { const rows = [['condition', 'condition_name', 'run_id', 'model', 'provider_calls', 'successful_calls', 'latency_ms', 'fallback', 'evidence_ids']]; (currentComparison.results || []).forEach((result) => { const trace = result.trace || {}; rows.push([result.condition_id, result.condition_name, result.run_id, trace.model || '', trace.provider_calls || 0, trace.successful_provider_calls || 0, trace.latency_ms || 0, Boolean(trace.fallback_usage), (trace.retrieved_evidence_ids || []).join('; ')]); }); downloadText('tcm-comparison_' + currentComparison.comparison_id + '.csv', rows.map((row) => row.map((value) => '"' + String(value).replace(/"/g, '""') + '"').join(',')).join('\r\n'), 'text/csv;charset=utf-8'); } });
  window.addEventListener('popstate', () => {
    if (location.hash === '#workbench' || location.hash === '#legacy-demo' || location.hash === '#research-workbench' || location.hash === '#research-compare') {
      setView('workbench');
      setMode(location.hash === '#research-compare' ? 'compare' : location.hash === '#legacy-demo' ? 'single' : 'multi');
    } else setView('home');
  });
  fetch(API + '/health').then((response) => response.json()).then((data) => {
    const profile = data.runtime_profile === 'local_research' ? 'Local research' : 'Public demo';
    const corpusLabel = (data.corpus_name || data.active_corpus) + ' · ' + (data.corpus_chunk_count || 0) + ' chunks';
    const providerLabel = 'provider configured=' + data.provider_configured + ' · LLM execution=' + (data.llm_execution_enabled ? 'enabled' : 'disabled');
    setText('.prototype-status span:last-child', profile + ' · ' + corpusLabel + ' · ' + providerLabel);
    setText('#consensus-corpus-status', profile + ' uses ' + corpusLabel + '. Scores below are evidence-support signals, not medical correctness.');
    setText('#compare-corpus-status', profile + ' · ' + corpusLabel + '.');
    $('.prototype-status').classList.toggle('is-live', true);
  }).catch(() => setText('.prototype-status span:last-child', 'Backend offline · static interface remains available'));

  applyLanguage('en'); updateConditionHelp();
  if (location.hash === '#workbench' || location.hash === '#legacy-demo' || location.hash === '#research-workbench' || location.hash === '#research-compare') {
    setView('workbench');
    setMode(location.hash === '#research-compare' ? 'compare' : location.hash === '#legacy-demo' ? 'single' : 'multi');
  } else setView('home');
}());
