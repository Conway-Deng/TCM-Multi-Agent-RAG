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
      modes: [['TCM Single RAG', 'Conventional evidence-grounded baseline'], ['TCM Multi-Agent', 'Specialists, debate, and judges'], ['Research Compare', 'Same-question controlled conditions']],
      status: 'Backend status', question: 'TCM educational question *', helper: 'Do not include identifying information. Emergencies require immediate professional help.',
      submit: 'Run TCM Single RAG', samples: 'Try a sample', context: 'Optional context', contextHint: 'used only for this request',
      result: 'Evidence-grounded TCM perspective', patterns: 'Possible educational patterns', examples: 'Educational source examples', safety: 'Safety notes', evidence: 'Retrieved evidence', technical: 'Technical details'
    },
    zh: {
      home: '首页', demo: '研究台', title: '中医多智能体 RAG 研究台', lead: '运行中医单路 RAG、多智能体条件或同题对照实验。',
      modes: [['中医单路 RAG', '常规证据检索基线'], ['中医多智能体', '专科智能体、辩论与评审'], ['研究对照', '同一问题的受控条件比较']],
      status: '后端状态', question: '中医教学研究问题 *', helper: '请勿填写可识别个人身份的信息。紧急情况请立即寻求专业帮助。',
      submit: '运行中医单路 RAG', samples: '示例问题', context: '可选背景', contextHint: '仅用于本次请求',
      result: '基于证据的中医视角', patterns: '教学性辨证方向', examples: '资料中的教学示例', safety: '安全提示', evidence: '检索证据', technical: '技术详情'
    },
    ko: {
      home: '홈', demo: '연구대', title: 'TCM 멀티에이전트 RAG 연구대', lead: 'TCM 단일 RAG, 전문 에이전트 조건 또는 동일 질문 비교를 실행합니다.',
      modes: [['TCM 단일 RAG', '근거 검색 기준선'], ['TCM 멀티에이전트', '전문가, 토론, 심사'], ['연구 비교', '동일 질문 통제 비교']],
      status: '백엔드 상태', question: 'TCM 교육 연구 질문 *', helper: '식별 가능한 개인정보를 입력하지 마세요. 응급 상황에서는 즉시 전문 도움을 받으세요.',
      submit: 'TCM 단일 RAG 실행', samples: '예시 질문', context: '선택 배경', contextHint: '이번 요청에만 사용',
      result: '근거 기반 TCM 관점', patterns: '교육용 변증 방향', examples: '자료의 교육 예시', safety: '안전 안내', evidence: '검색 근거', technical: '기술 세부정보'
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

  function setView(view) {
    const demo = view === 'demo';
    $('#home-view').hidden = demo;
    $('#demo-view').hidden = !demo;
    $$('.toggle-btn').forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-selected', String(active));
    });
    $('.nav').hidden = demo;
  }

  function setMode(mode) {
    const active = ['single', 'multi', 'compare'].includes(mode) ? mode : 'single';
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
    setText('.tcm-kicker', 'TCM-RAG · C1');
    setText('#tcm-consultation-title', t.modes[0][0]);
    setText('.tcm-panel-heading p:last-child', t.modes[0][1]);
    setText('.tcm-question-field > span', t.question);
    setText('.tcm-question-field small', t.helper);
    setText('.tcm-submit-label', t.submit);
    setText('.tcm-samples > span', t.samples);
    setText('.tcm-context-title', t.context);
    setText('.tcm-context-hint', t.contextHint);
    setText('.tcm-result-hero h2', t.result);
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

  async function api(path, body) {
    const response = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed (' + response.status + ')');
    return data;
  }

  function showMessage(node, message) {
    node.textContent = message;
    node.hidden = !message;
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

  function renderResearchRun(data) {
    setText('#consensus-strategy-badge', data.condition_id + ' · ' + data.condition_name);
    setText('#consensus-confidence', Math.round((data.confidence || 0) * 100) + '% confidence');
    setText('#consensus-run-id', data.run_id);
    setText('#consensus-summary-text', data.final_answer);
    const agents = $('#consensus-agents'); agents.replaceChildren();
    (data.agent_outputs || []).forEach((agent) => {
      const card = element('article', 'consensus-agent-card');
      card.append(element('strong', '', agent.agent_name));
      card.append(element('p', '', (agent.claims || []).map((claim) => claim.text).join(' ') || agent.abstention_reason));
      card.append(element('small', '', agent.subdomain + ' · ' + Math.round(agent.confidence * 100) + '% · ' + agent.evidence_ids.join(', ')));
      agents.append(card);
    });
    renderList($('#consensus-agreements'), data.agreements || [], 'No measured agreement.');
    renderList($('#consensus-disagreements'), data.disagreements || [], 'No explicit disagreement.');
    const judges = $('#consensus-judges'); judges.replaceChildren();
    (data.judge_outputs || []).forEach((judge) => {
      const card = element('article', 'consensus-judge-row');
      card.append(element('strong', '', judge.judge_name + ' · ' + Math.round(judge.score * 100) + '%'));
      card.append(element('p', '', (judge.findings || []).join(' ') || judge.reasoning_summary));
      judges.append(card);
    });
    renderList($('#consensus-safety'), data.safety_flags || [], 'No structured safety flag.');
    renderList($('#consensus-limitations'), data.limitations || [], 'No additional limitation.');
    setText('#consensus-latency', (data.trace?.latency_ms || 0) + ' ms');
    setText('#consensus-api-calls', String(data.trace?.provider_calls || 0));
    setText('#consensus-call-failures', data.mock_mode ? 'mock/local' : 'live provider');
    setText('#consensus-fixture-used', data.trace?.retrieval_strategy || 'not run');
    const trace = $('#consensus-trace'); trace.replaceChildren();
    (data.retrieval || []).forEach((item) => trace.append(element('p', '', '#' + item.rank + ' ' + item.chunk_id + ' · ' + item.retrieval_method)));
    $('#consensus-results').hidden = false;
    $('#consensus-results').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderCompare(data) {
    const grid = $('#research-compare-grid'); grid.replaceChildren();
    (data.results || []).forEach((result) => {
      const card = element('article', 'research-compare-card glass');
      card.append(element('span', 'consensus-experimental-badge', result.condition_id));
      card.append(element('h3', '', result.condition_name));
      card.append(element('p', '', result.final_answer));
      card.append(element('small', '', result.run_id + ' · confidence ' + Math.round(result.confidence * 100) + '% · ' + (result.trace?.latency_ms || 0) + ' ms'));
      const details = element('details', 'research-card-details');
      details.append(element('summary', '', 'Agents, judges, evidence'));
      details.append(element('pre', '', JSON.stringify({ agents: result.trace?.active_agents || [], judges: result.trace?.active_judges || [], evidence: result.trace?.retrieved_evidence_ids || [], metrics: result.metrics }, null, 2)));
      card.append(details); grid.append(card);
    });
    setText('#research-compare-metrics', JSON.stringify({ comparison_id: data.comparison_id, metrics: data.metric_comparison, limitations: data.limitations }, null, 2));
    $('#research-compare-results').hidden = false;
  }

  $$('.toggle-btn').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
  $$('.demo-option').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mode)));
  $$('.language-btn').forEach((button) => button.addEventListener('click', () => applyLanguage(button.dataset.lang)));
  $$('.tcm-sample').forEach((button) => button.addEventListener('click', () => { $('#tcm-question').value = button.dataset.question; $('#tcm-question').focus(); }));

  $('#tcm-consult-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const message = $('#tcm-form-message');
    const question = $('#tcm-question').value.trim();
    if (question.length < 3) return showMessage(message, 'Please enter a longer question.');
    showMessage(message, ''); $('#tcm-submit').disabled = true;
    try {
      const values = Object.fromEntries(new FormData(form));
      renderTcm(await api('/api/tcm/consult', { question, context: { age: values.age || '', gender: values.gender || '', duration: values.duration || '', medications: values.medications || '', pregnancy: values.pregnancy || '', allergies: values.allergies || '' } }));
    } catch (error) { showMessage(message, error.message + '. The static website remains available; start the backend to run research.'); }
    finally { $('#tcm-submit').disabled = false; }
  });

  $('#consensus-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const message = $('#consensus-message'); const button = $('#consensus-submit');
    const question = $('#consensus-question').value.trim(); if (question.length < 3) return showMessage(message, 'Please enter a longer question.');
    showMessage(message, ''); button.disabled = true;
    try { renderResearchRun(await api('/api/tcm/multi-agent/consult', { question, condition_id: $('#consensus-strategy').value, retrieval_strategy: $('#consensus-retrieval').value, active_agents: ['syndrome', 'herbal', 'acupuncture_meridian', 'constitution', 'dietary_therapy', 'lifestyle_yangsheng'], active_judges: ['evidence', 'hallucination', 'safety', 'conflict', 'confidence', 'provenance'], top_k: 4, debate_rounds: 1, include_trace: true })); }
    catch (error) { showMessage(message, error.message); } finally { button.disabled = false; }
  });

  $('#research-compare-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const message = $('#research-compare-message'); const button = event.currentTarget.querySelector('button[type="submit"]');
    const question = $('#research-compare-question').value.trim(); const conditions = $$('input[name="condition"]:checked').map((item) => item.value);
    if (question.length < 3 || !conditions.length) return showMessage(message, 'Enter a question and select at least one condition.');
    showMessage(message, ''); button.disabled = true;
    try { renderCompare(await api('/api/research/compare', { question, conditions, retrieval_strategy: $('#research-compare-retrieval').value, top_k: Number($('#research-compare-top-k').value), iterative_retrieval: $('#research-compare-reflection').checked, active_agents: ['syndrome', 'herbal', 'acupuncture_meridian', 'constitution', 'dietary_therapy', 'lifestyle_yangsheng'], active_judges: ['evidence', 'hallucination', 'safety', 'conflict', 'confidence', 'provenance'] })); }
    catch (error) { showMessage(message, error.message); } finally { button.disabled = false; }
  });

  fetch(API + '/health').then((response) => response.json()).then((data) => {
    setText('.prototype-status span:last-child', data.scope + ' · ' + (data.mock_mode ? 'mock/local fallback' : data.provider_mode));
    $('.prototype-status').classList.toggle('is-live', true);
  }).catch(() => setText('.prototype-status span:last-child', 'Backend offline · static interface remains available'));

  applyLanguage('en'); setMode('single'); setView('home');
}());
