(function () {
  const toggle = document.querySelector('.view-toggle');
  const buttons = document.querySelectorAll('.toggle-btn');
  const homeView = document.getElementById('home-view');
  const demoView = document.getElementById('demo-view');
  const nav = document.querySelector('.nav');

  if (!toggle || !homeView || !demoView) return;

  function setView(view) {
    const isDemo = view === 'demo';

    document.body.classList.toggle('demo-mode', isDemo);
    toggle.classList.toggle('is-demo', isDemo);

    buttons.forEach(function (btn) {
      const active = btn.dataset.view === view;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    homeView.hidden = isDemo;
    demoView.hidden = !isDemo;

    if (nav) {
      nav.hidden = isDemo;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      setView(btn.dataset.view);
    });
  });

  let currentLanguage = 'en';
  let currentResultData = null;
  const demoOptions = document.querySelector('.demo-options');
  const prototypeStatus = document.querySelector('.prototype-status');
  const tcmConsultation = document.getElementById('tcm-consultation');
  const consensusConsultation = document.getElementById('consensus-consultation');

  function setDemoMode(mode) {
    const selectedMode = ['west', 'tcm', 'both'].includes(mode) ? mode : 'west';
    document.querySelectorAll('.demo-option').forEach(function (el) {
      const active = el.dataset.mode === selectedMode;
      el.classList.toggle('is-selected', active);
      el.setAttribute('aria-checked', active ? 'true' : 'false');
    });

    if (demoOptions) {
      demoOptions.classList.remove('mode-west', 'mode-tcm', 'mode-both');
      demoOptions.classList.add('mode-' + selectedMode);
    }

    const isTcmMode = selectedMode === 'tcm';
    const isWestMode = selectedMode === 'west';
    const isBothMode = selectedMode === 'both';

    if (tcmConsultation) tcmConsultation.hidden = !isTcmMode;
    if (consensusConsultation) consensusConsultation.hidden = !isBothMode;

    const westConsultation = document.getElementById('west-consultation');
    if (westConsultation) westConsultation.hidden = !isWestMode;

    if (prototypeStatus) prototypeStatus.hidden = isTcmMode || isWestMode || isBothMode;
  }

  document.querySelectorAll('.demo-option').forEach(function (option) {
    option.addEventListener('click', function () {
      setDemoMode(option.dataset.mode);
    });
  });

  setDemoMode(document.querySelector('.demo-option.is-selected')?.dataset.mode || 'west');

  const API_BASE_URL = window.MEDIRAG_API_BASE_URL || 'http://localhost:8000';
  const tcmForm = document.getElementById('tcm-consult-form');
  const tcmQuestion = document.getElementById('tcm-question');
  const tcmSubmit = document.getElementById('tcm-submit');
  const tcmFormMessage = document.getElementById('tcm-form-message');
  const tcmResults = document.getElementById('tcm-results');
  const consensusForm = document.getElementById('consensus-form');
  const consensusQuestion = document.getElementById('consensus-question');
  const consensusSubmit = document.getElementById('consensus-submit');
  const consensusMessage = document.getElementById('consensus-message');
  const consensusResults = document.getElementById('consensus-results');

  function uiText() {
    const language = translations[currentLanguage] || translations.en;
    return language.tcm;
  }

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function replaceList(containerId, items, emptyText) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.replaceChildren();
    const values = Array.isArray(items) && items.length ? items : [emptyText];
    values.forEach(function (item) { container.append(makeElement('li', '', String(item))); });
  }

  function renderConsensusResult(data) {
    const integrated = data.integrated_response || {};
    const confidence = integrated.confidence || {};
    document.getElementById('consensus-strategy-badge').textContent = String(data.strategy || '—').replaceAll('_', ' ');
    document.getElementById('consensus-confidence').textContent = Math.round(Number(confidence.score || 0) * 100) + '% ' + String(confidence.level || 'low') + ' confidence';
    document.getElementById('consensus-summary-text').textContent = integrated.summary || 'No integrated response was generated.';

    const agents = document.getElementById('consensus-agents');
    agents.replaceChildren();
    (data.agents || []).forEach(function (agent) {
      const card = makeElement('article', 'consensus-agent-card');
      const header = makeElement('div', 'consensus-agent-header');
      header.append(
        makeElement('strong', '', String(agent.domain || agent.agent_id)),
        makeElement('span', 'consensus-source-badge ' + (agent.source_type === 'fixture' ? 'is-fixture' : 'is-live'), agent.source_type === 'fixture' ? 'Synthetic fixture' : agent.source_type)
      );
      card.append(header, makeElement('p', '', agent.summary || 'No summary.'));
      if (agent.source_type === 'fixture') card.append(makeElement('small', '', 'Experimental fixture — not verified clinical evidence.'));
      agents.append(card);
    });

    replaceList('consensus-agreements', integrated.agreements, 'No agreement was evaluated or identified.');
    replaceList('consensus-disagreements', integrated.disagreements, 'No material disagreement was reported.');
    replaceList('consensus-safety', integrated.safety_notes, 'No additional safety note was generated.');
    replaceList('consensus-limitations', integrated.limitations, 'No limitation metadata was returned.');

    const judgeContainer = document.getElementById('consensus-judges');
    judgeContainer.replaceChildren();
    const judges = data.judges || {};
    Object.keys(judges).forEach(function (name) {
      if (!judges[name]) return;
      const item = makeElement('article', 'consensus-judge-row');
      item.append(makeElement('strong', '', name.replaceAll('_', ' ') + ' judge'));
      const judge = judges[name];
      const detail = judge.reasoning_summary || judge.reason || (judge.conflicts ? judge.conflicts.length + ' conflict(s)' : JSON.stringify(judge));
      item.append(makeElement('span', '', detail));
      judgeContainer.append(item);
    });
    if (!judgeContainer.children.length) judgeContainer.append(makeElement('p', '', 'This baseline does not run judges.'));

    document.getElementById('consensus-latency').textContent = String(data.latency_ms || 0) + ' ms';
    document.getElementById('consensus-api-calls').textContent = String(data.api_call_count || 0);
    document.getElementById('consensus-call-failures').textContent = String(data.model_call_failure_count || 0);
    document.getElementById('consensus-fixture-used').textContent = data.fixture_used ? 'Yes — synthetic Western fixture' : 'No';
    const trace = document.getElementById('consensus-trace');
    trace.replaceChildren();
    (data.model_trace || []).forEach(function (entry) {
      trace.append(makeElement('p', 'consensus-trace-row', entry.role + ' · ' + entry.model + ' · ' + entry.status + ' · ' + entry.latency_ms + ' ms'));
    });
    consensusResults.hidden = false;
    consensusResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  if (consensusForm) {
    consensusForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      const question = consensusQuestion.value.trim();
      if (question.length < 3) {
        consensusMessage.textContent = 'Please enter a health question of at least 3 characters.';
        consensusMessage.hidden = false;
        return;
      }
      consensusMessage.hidden = true;
      consensusResults.hidden = true;
      consensusSubmit.disabled = true;
      consensusSubmit.classList.add('is-loading');
      consensusSubmit.querySelector('span:first-child').textContent = 'Running orchestration…';
      try {
        const response = await fetch(API_BASE_URL + '/api/consensus/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ question: question, context: {}, strategy: document.getElementById('consensus-strategy').value, domains: ['tcm', 'western_fixture'], include_trace: true })
        });
        const data = await response.json();
        if (!response.ok) {
          const detail = data && data.detail;
          const message = detail && typeof detail === 'object' ? detail.message : detail;
          throw new Error(message || 'The consensus pilot could not be completed.');
        }
        renderConsensusResult(data);
      } catch (error) {
        consensusMessage.textContent = error instanceof TypeError ? 'The backend is not reachable. Start it on http://localhost:8000 and try again.' : error.message;
        consensusMessage.hidden = false;
      } finally {
        consensusSubmit.disabled = false;
        consensusSubmit.classList.remove('is-loading');
        consensusSubmit.querySelector('span:first-child').textContent = 'Run MediConsensus';
      }
    });
  }

  function renderEmpty(container, message) {
    container.replaceChildren(makeElement('p', 'tcm-empty', message));
  }

  function localizedDisplay(item) {
    const localized = item && item.localized ? item.localized : {};
    const responseLanguage = currentResultData && currentResultData.response_language;
    return localized[currentLanguage] || localized[responseLanguage] || localized.en || item;
  }

  function localizedResultFor(data) {
    const localized = data && data.localized_result ? data.localized_result : {};
    return localized[currentLanguage] || localized[data.response_language] || localized.en || null;
  }

  function renderPatterns(containerId, patterns) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.replaceChildren();
    if (!patterns.length) {
      renderEmpty(container, uiText().emptyPatterns);
      return;
    }
    patterns.forEach(function (item, index) {
      const display = localizedDisplay(item);
      const article = makeElement('article', 'tcm-list-item');
      const header = makeElement('div', 'tcm-list-item-header');
      header.append(makeElement('span', 'tcm-index', String(index + 1)), makeElement('h4', '', display.name || display.pattern || item.name || item.pattern));
      article.append(header, makeElement('p', '', display.rationale || item.rationale));
      const matchingSymptoms = item.matched_symptoms || item.matching_symptoms || [];
      if (matchingSymptoms.length && (item.matched_symptoms || (currentResultData && currentResultData.response_language === currentLanguage))) {
        const matches = makeElement('div', 'tcm-match-list');
        matchingSymptoms.forEach(function (symptom) {
          matches.append(makeElement('span', '', symptom));
        });
        article.append(matches);
      }
      container.append(article);
    });
  }

  function renderFormulas(containerId, formulas) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.replaceChildren();
    if (!formulas.length) {
      renderEmpty(container, uiText().emptyExamples);
      return;
    }
    formulas.forEach(function (item) {
      const display = localizedDisplay(item);
      const article = makeElement('article', 'tcm-list-item');
      const header = makeElement('div', 'tcm-list-item-header');
      header.append(makeElement('span', 'tcm-type-pill', uiText().exampleTypes[item.type] || item.type), makeElement('h4', '', display.name || item.name));
      article.append(header, makeElement('p', '', display.description || display.purpose || item.description || item.purpose));
      const warning = makeElement('p', 'tcm-inline-warning', display.warning || display.safety_warning || item.warning || item.safety_warning);
      article.append(warning);
      container.append(article);
    });
  }

  function renderEvidence(evidence) {
    const container = document.getElementById('tcm-evidence');
    if (!container) return;
    container.replaceChildren();
    if (!evidence.length) {
      renderEmpty(container, uiText().emptyEvidence);
      return;
    }
    evidence.forEach(function (item, index) {
      const display = localizedDisplay(item);
      const article = makeElement('article', 'tcm-evidence-item');
      const top = makeElement('div', 'tcm-evidence-top');
      const sourceBlock = makeElement('div', '');
      sourceBlock.append(makeElement('span', 'tcm-citation', '[' + (index + 1) + '] ' + (display.source_type || item.source_type)), makeElement('h4', '', display.title || item.title));
      const score = Math.round(Number(item.relevance_score || 0) * 100);
      top.append(sourceBlock, makeElement('strong', 'tcm-relevance', score + '% ' + uiText().match));
      const meter = makeElement('div', 'tcm-relevance-meter');
      const fill = makeElement('span', '');
      fill.style.width = Math.max(2, Math.min(100, score)) + '%';
      meter.append(fill);
      article.append(top, makeElement('p', '', display.snippet || item.snippet), meter, makeElement('cite', '', item.source));
      container.append(article);
    });
  }

  function renderSafety(containerId, notes) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.replaceChildren();
    notes.forEach(function (note) {
      container.append(makeElement('li', '', note));
    });
  }

  function shortenAnswer(text) {
    const limit = /[\u3400-\u9fff\uac00-\ud7af]/.test(text) ? 260 : 420;
    if (text.length <= limit) return { short: text, truncated: false };
    const candidate = text.slice(0, limit);
    const stops = ['。', '！', '？', '. ', '! ', '? '];
    let cut = -1;
    stops.forEach(function (stop) { cut = Math.max(cut, candidate.lastIndexOf(stop)); });
    if (cut < Math.floor(limit * 0.55)) cut = limit;
    return { short: candidate.slice(0, cut + 1).trim() + (cut === limit ? '…' : ''), truncated: true };
  }

  function renderTCMResult(data, shouldScroll) {
    currentResultData = data;
    const t = uiText();
    const localizedResult = localizedResultFor(data);
    const score = Math.round(Number(data.confidence.score || 0) * 100);
    const generationSource = data.generation_source || (data.generation_mode === 'llm' ? 'siliconflow_llm' : data.generation_mode === 'safety' ? 'safety_rule' : 'mock_fallback');
    const modeLabel = localizedResult && localizedResult.status_label ? localizedResult.status_label : (t.status[generationSource] || generationSource);
    const groundingLabel = localizedResult && localizedResult.grounding ? localizedResult.grounding : (t.grounding[generationSource] || '');
    const summaryText = localizedResult && localizedResult.summary ? localizedResult.summary : String(data.tcm_perspective || '');
    const answer = shortenAnswer(summaryText);
    const isAbstained = Boolean(data.abstained) || (data.scope_status && data.scope_status !== 'supported');

    document.getElementById('tcm-summary').textContent = answer.short;
    document.getElementById('tcm-summary-full').textContent = summaryText;
    document.getElementById('tcm-full-answer-details').hidden = !answer.truncated;
    document.getElementById('tcm-grounding-note').textContent = groundingLabel;
    document.getElementById('tcm-confidence-score').textContent = score + '%';
    document.getElementById('tcm-confidence-level').textContent = t.confidence[data.confidence.level] || data.confidence.level;
    document.getElementById('tcm-confidence-reason').textContent = data.confidence.reason;
    document.getElementById('tcm-disclaimer').textContent = t.disclaimer;
    document.getElementById('tcm-generation-mode').textContent = modeLabel;
    document.getElementById('tcm-generation-source').textContent = generationSource;
    document.getElementById('tcm-llm-model').textContent = data.llm_model || 'local';
    document.getElementById('tcm-response-language').textContent = data.response_language || '—';
    document.getElementById('tcm-evidence-count').textContent = String((data.evidence || []).length);
    document.getElementById('tcm-retrieval-method').textContent = data.retrieval_method || (data.retrieval_metadata && data.retrieval_metadata.retrieval_method) || 'not_run';
    document.getElementById('tcm-meaningful-count').textContent = String(data.meaningful_match_count || (data.retrieval_metadata && data.retrieval_metadata.meaningful_match_count) || 0);
    document.getElementById('tcm-top-score').textContent = Math.round(Number(data.top_relevance_score || (data.retrieval_metadata && data.retrieval_metadata.top_relevance_score) || 0) * 100) + '%';
    document.getElementById('tcm-llm-error').textContent = data.llm_error || '—';
    document.getElementById('tcm-llm-error-row').hidden = !data.llm_error;

    const statusBadge = document.getElementById('tcm-generation-mode');
    statusBadge.textContent = modeLabel;
    statusBadge.dataset.source = generationSource;

    const fallbackBanner = document.getElementById('tcm-fallback-banner');
    fallbackBanner.hidden = generationSource !== 'mock_fallback';

    const stateCard = document.getElementById('tcm-state-card');
    const stateTitle = document.getElementById('tcm-state-title');
    const stateBody = document.getElementById('tcm-state-body');
    if (stateCard && stateTitle && stateBody) {
      stateCard.hidden = !isAbstained;
      stateTitle.textContent = (localizedResult && localizedResult.state_title) || (t.stateTitles && t.stateTitles[data.scope_status]) || modeLabel;
      stateBody.textContent = (localizedResult && localizedResult.state_body) || summaryText;
    }

    const urgent = document.getElementById('tcm-urgent');
    urgent.hidden = !data.urgent;
    tcmResults.classList.toggle('is-urgent', Boolean(data.urgent));
    tcmResults.classList.toggle('is-abstained', isAbstained);
    const allPatterns = data.possible_patterns || [];
    const allFormulas = data.related_herbs_or_formulas || [];
    const evidence = data.evidence || [];
    const localizedSafety = data.localized_safety_notes || {};
    const allSafetyNotes = localizedSafety[currentLanguage] || localizedSafety[data.response_language] || localizedSafety.en || data.safety_notes || [];
    const visiblePatterns = localizedResult && Array.isArray(localizedResult.patterns) ? localizedResult.patterns.slice(0, 2) : allPatterns.slice(0, 2);
    const visibleFormulas = localizedResult && Array.isArray(localizedResult.formulas) ? localizedResult.formulas.slice(0, 2) : allFormulas.slice(0, 2);
    const visibleSafetyNotes = localizedResult && Array.isArray(localizedResult.safety_notes) ? localizedResult.safety_notes.slice(0, 3) : allSafetyNotes.slice(0, 3);
    renderPatterns('tcm-patterns', visiblePatterns);
    renderPatterns('tcm-patterns-extra', allPatterns);
    renderFormulas('tcm-formulas', visibleFormulas);
    renderFormulas('tcm-formulas-extra', allFormulas);
    renderEvidence(evidence);
    renderSafety('tcm-safety-notes', visibleSafetyNotes);
    renderSafety('tcm-safety-notes-extra', allSafetyNotes);
    document.querySelector('.tcm-result-grid').hidden = isAbstained;
    document.getElementById('tcm-patterns-extra-details').hidden = isAbstained || allPatterns.length <= visiblePatterns.length;
    document.getElementById('tcm-formulas-extra-details').hidden = isAbstained || allFormulas.length <= visibleFormulas.length;
    document.getElementById('tcm-safety-extra-details').hidden = allSafetyNotes.length <= visibleSafetyNotes.length;
    document.getElementById('tcm-evidence-details').hidden = !evidence.length;
    const meaningfulEvidence = evidence.filter(function (item) { return Number(item.relevance_score || 0) > 0; });
    const strongest = evidence.reduce(function (best, item) { return Math.max(best, Number(item.relevance_score || 0)); }, 0);
    document.getElementById('tcm-evidence-summary').textContent = localizedResult && localizedResult.evidence_summary
      ? localizedResult.evidence_summary
      : t.evidenceSummary(meaningfulEvidence.length, Math.round(strongest * 100));
    if (localizedResult) {
      document.querySelector('.tcm-result-hero h2').textContent = localizedResult.summary_title || t.summaryTitle;
      document.querySelector('.tcm-result-grid section:first-child .tcm-card-heading h3').textContent = localizedResult.patterns_title || t.cardTitles[0];
      document.querySelector('.tcm-result-grid section:nth-child(2) .tcm-card-heading h3').textContent = localizedResult.examples_title || t.cardTitles[1];
      document.querySelector('.tcm-safety-card .tcm-card-heading h3').textContent = localizedResult.safety_title || t.cardTitles[2];
      document.querySelector('#tcm-evidence-details > summary').textContent = localizedResult.evidence_title || t.accordions[2];
    }
    tcmResults.hidden = false;
    tcmResults.setAttribute('aria-busy', 'false');
    if (shouldScroll !== false) tcmResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function showFormMessage(message) {
    tcmFormMessage.textContent = message;
    tcmFormMessage.hidden = false;
  }

  document.querySelectorAll('.tcm-sample').forEach(function (button) {
    button.addEventListener('click', function () {
      tcmQuestion.value = button.dataset.question || '';
      tcmQuestion.focus();
      tcmFormMessage.hidden = true;
    });
  });

  if (tcmForm) {
    tcmForm.addEventListener('submit', async function (event) {
      event.preventDefault();
      const formData = new FormData(tcmForm);
      const question = String(formData.get('question') || '').trim();
      tcmFormMessage.hidden = true;

      if (question.length < 3) {
        showFormMessage(uiText().validation);
        tcmQuestion.focus();
        return;
      }

      const payload = {
        question: question,
        context: {
          age: String(formData.get('age') || '').trim(),
          gender: String(formData.get('gender') || '').trim(),
          duration: String(formData.get('duration') || '').trim(),
          medications: String(formData.get('medications') || '').trim(),
          pregnancy: String(formData.get('pregnancy') || '').trim(),
          allergies: String(formData.get('allergies') || '').trim()
        }
      };

      tcmSubmit.disabled = true;
      tcmSubmit.classList.add('is-loading');
      tcmSubmit.querySelector('.tcm-submit-label').textContent = uiText().loading;
      tcmResults.setAttribute('aria-busy', 'true');

      try {
        const response = await fetch(API_BASE_URL + '/api/tcm/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload)
        });
        let data = {};
        try {
          data = await response.json();
        } catch (_) {
          throw new Error(uiText().unreadable);
        }
        if (!response.ok) {
          throw new Error(typeof data.detail === 'string' ? data.detail : uiText().failed);
        }
        renderTCMResult(data);
      } catch (error) {
        const offline = error instanceof TypeError;
        showFormMessage(offline
          ? uiText().backendOffline
          : error.message || uiText().failed);
        tcmResults.setAttribute('aria-busy', 'false');
      } finally {
        tcmSubmit.disabled = false;
        tcmSubmit.classList.remove('is-loading');
        tcmSubmit.querySelector('.tcm-submit-label').textContent = uiText().submit;
      }
    });
  }

  const languageButtons = document.querySelectorAll('.language-btn');
  const translations = {
    en: {
      lang: 'en',
      title: 'Multi-LLM-as-a-Judge RAG Architecture for Medical Consensus',
      nav: ['About', 'Architecture', 'Research'],
      view: ['Home', 'Demo'],
      ariaLabels: ['Page view', 'Primary navigation', 'Language mode'],
      heroEyebrow: 'University of Nottingham · Research Internship',
      heroTitle: 'Multi-LLM-as-a-Judge RAG Architecture for Medical Consensus',
      heroLead: 'A multi-agent healthcare AI framework combining Retrieval-Augmented Generation, Agentic AI, and LLM-as-a-Judge to deliver evidence-grounded, explainable health information across Western Medicine, Traditional Chinese Medicine, Nutrition, and Lifestyle Medicine.',
      supervisor: 'Supervisor',
      intern: 'Research Intern',
      major: 'BSc (Hons) Computer Science with AI',
      aboutTitle: 'Research Problem',
      aboutLead: 'Current healthcare AI assistants suffer from critical limitations.',
      problems: [
        '<strong>Hallucinations</strong> — Models generate plausible but unsupported medical claims without grounding in authoritative sources.',
        '<strong>Lack of evidence transparency</strong> — Responses rarely cite clinical guidelines, literature, or explain the strength of underlying evidence.',
        '<strong>Conflicting paradigms</strong> — Systems cannot reconcile recommendations from different medical traditions and knowledge bases.',
        '<strong>Poor safety governance</strong> — Unsafe advice, contraindications, and unsupported claims often pass through without automated review.',
        '<strong>Limited explainability</strong> — Users receive single opaque answers rather than transparent reasoning, uncertainty, or disagreement.'
      ],
      visionLabel: 'Research Vision',
      vision: 'To develop a trustworthy and explainable healthcare AI ecosystem that intelligently integrates knowledge from multiple medical paradigms, verifies recommendations through evidence-aware AI judges, and provides transparent, safety-conscious health guidance — transforming healthcare AI from a single-answer chatbot into a virtual multidisciplinary advisory board.',
      archTitle: 'System Architecture',
      archLead: 'From health question to retrieved evidence, specialist debate, safety judging, and final consensus.',
      inputKicker: 'Input',
      inputTitle: 'Question Intake',
      inputLead: 'User context is interpreted and routed into the correct medical knowledge paths.',
      userTitle: 'User',
      userDesc: 'Asks a health question',
      plannerTitle: 'Query Planner',
      plannerDesc: 'Analyzes the question and plans retrieval and agents',
      retrievalKicker: 'Retrieval',
      retrievalTitle: 'Dual Evidence Grounding',
      retrievalLead: 'Western medicine and TCM evidence sources are retrieved separately before being reconciled.',
      westRetrievalDesc: 'Modern medicine retrieval',
      tcmRetrievalDesc: 'Traditional Chinese Medicine retrieval',
      debateKicker: 'Governance',
      debateTitle: 'Debate, Judge, Consensus',
      debateLead: 'Specialist agents propose answers, then SafeJudge checks evidence, risk, conflict, and confidence.',
      debateLabel: 'Multi-Agent Debate',
      debateDesc: 'Domain-specific agents independently generate recommendations and rationales',
      agents: [
        ['Western Medicine Agent', 'Evidence-based modern medicine'],
        ['TCM Agent', 'TCM theory, syndrome differentiation, herbal knowledge'],
        ['Nutrition Agent', 'Dietary guidance'],
        ['Lifestyle Agent', 'Behavioral and wellness guidance']
      ],
      judgeLabel: 'SafeJudge',
      judgeDesc: 'LLM-as-a-Judge evaluates, verifies, and scores all agent outputs',
      judges: [
        ['Evidence Judge', 'Checks citation quality'],
        ['Safety Judge', 'Detects risks and contraindications'],
        ['Conflict Judge', 'Identifies conflicts between paradigms'],
        ['Confidence Judge', 'Estimates uncertainty levels']
      ],
      outputTitle: 'Integrated Response',
      outputDesc: 'Synthesized, evidence-aware, and safety-validated recommendation',
      outputItems: ['Summary of recommendations', 'Evidence & citations', 'Agreements & disagreements', 'Safety notes', 'Confidence score'],
      researchTitle: 'Research Questions',
      researchLead: 'Key questions guiding the investigation.',
      questions: [
        'Can multi-agent retrieval and reasoning improve the factual accuracy and completeness of healthcare question answering compared with conventional RAG systems?',
        'Can LLM-as-a-Judge mechanisms effectively detect hallucinations, unsafe recommendations, and unsupported claims in healthcare AI outputs?',
        'How can AI systems reconcile recommendations from different medical paradigms while maintaining transparency and user trust?',
        'Does multi-agent debate and consensus-building improve healthcare answer quality compared with single-agent generation?',
        'How should healthcare AI communicate evidence strength, uncertainty, and conflicting viewpoints to end users?',
        'Can integrative healthcare AI increase user confidence and perceived trustworthiness without sacrificing scientific rigor?'
      ],
      demoEyebrow: 'MediConsensus Demo',
      demoTitle: 'Choose a consultation mode',
      demoLead: 'Select which medical knowledge base to query for your health question.',
      demoOptions: [
        ['Western Medicine', 'Evidence-based modern medicine via MediRAG-West'],
        ['TCM', 'Traditional Chinese Medicine via TCM-RAG'],
        ['Western Medicine + TCM', 'Integrative dual-paradigm consultation']
      ],
      statusTitle: 'Prototyping in progress',
      statusDesc: 'Consultation workflow and medical retrieval outputs are under active development.',
      footer: '© 2026 University of Nottingham Research Internship',
      footerSub: 'Multi-LLM-as-a-Judge RAG Architecture for Medical Consensus',
      tcm: {
        modeAria: 'Consultation mode', comingSoon: 'Coming soon', kicker: 'TCM-RAG · Research prototype', title: 'Explore a TCM perspective',
        lead: 'Ask a health question. Local TCM evidence is retrieved before a concise, safety-aware educational answer is generated.', live: 'Local RAG ready',
        questionLabel: 'Health question', placeholder: 'e.g. I have trouble sleeping and lower back soreness.', helper: 'Describe what you notice and when it started. Do not include identifying information.',
        samplesLabel: 'Try a sample', samples: [['Trouble sleeping + lower back soreness', 'I have trouble sleeping and lower back soreness'], ['Feverish head + itchy throat', 'I feel feverish and my throat is itchy'], ['Stress + bloating + poor appetite', 'I feel stressed, bloated, and have poor appetite']],
        contextTitle: 'Add optional context', contextHint: 'helps retrieval', fields: ['Age', 'Gender', 'Symptom duration', 'Pregnancy status', 'Current medications', 'Allergies'],
        placeholders: ['e.g. 35', 'e.g. 3 weeks', 'Names only; never stop prescribed medicine based on this demo', 'Medicine, herb, or food allergies'],
        genderOptions: ['Prefer not to say', 'Female', 'Male', 'Non-binary', 'Self-described'], pregnancyOptions: ['Not provided', 'No', 'Pregnant', 'Trying to conceive', 'Breastfeeding', 'Unsure'],
        formSafety: '<strong>Research use only.</strong> Not a diagnosis or prescription. Emergencies require immediate professional care.', submit: 'Run TCM-RAG', loading: 'Retrieving evidence…',
        validation: 'Please enter a health question of at least 3 characters.', unreadable: 'The backend returned an unreadable response.', failed: 'The consultation could not be completed. Please try again.', backendOffline: 'The TCM-RAG backend is not reachable. Start it on http://localhost:8000, then try again.',
        resultLabel: 'TCM-RAG result', summaryTitle: 'TCM perspective summary', fullAnswer: 'View full answer',
        status: { siliconflow_llm: 'AI grounded by retrieved evidence', mock_fallback: 'Local evidence fallback', safety_rule: 'Safety-rule response', scope_rule: 'Scope-rule abstention', evidence_gate: 'Evidence-insufficient abstention' },
        grounding: { siliconflow_llm: 'The LLM answer is grounded only in retrieved local evidence.', mock_fallback: 'AI provider unavailable or not configured; using the local TCM medical library.', safety_rule: 'Safety rules took priority over TCM interpretation.', scope_rule: 'The current TCM-RAG scope took priority over generation.', evidence_gate: 'No meaningful local evidence was retrieved, so generation was blocked.' },
        stateTitles: { supported: '', insufficient_information: 'More symptom detail is needed', out_of_scope: 'Out of current TCM-RAG scope', safety_critical: 'Safety-first response', evidence_insufficient: 'Insufficient retrieved evidence' },
        confidenceAria: 'Confidence score', confidence: { low: 'Low confidence', medium: 'Medium confidence', high: 'High confidence' },
        urgentTitle: 'Urgent safety guidance', urgentText: 'This response prioritises immediate professional care over TCM interpretation.', fallbackTitle: 'Local knowledge mode', fallbackText: 'AI provider unavailable. This result uses the local TCM knowledge base only.',
        cardLabels: ['Pattern hypotheses', 'Educational examples', 'Safety first'], cardTitles: ['Most relevant possibilities', 'Examples from retrieved sources', 'Key safety notes'],
        accordions: ['View all possible patterns', 'View all educational examples', 'View retrieved evidence', 'View all safety notes', 'View technical details'], technicalLabels: ['Source', 'Model', 'Response language', 'Evidence count', 'Error', 'Retrieval method', 'Meaningful matches', 'Top relevance'],
        emptyPatterns: 'No TCM pattern is suggested for this safety-first response.', emptyExamples: 'No herb or formula examples are shown for this response.', emptyEvidence: 'Evidence retrieval was skipped for this safety response.',
        exampleTypes: { herb: 'herb', formula: 'formula' }, match: 'match', evidenceSummary: (count, score) => `Based on ${count} local evidence match${count === 1 ? '' : 'es'}. Strongest match: ${score}%.`,
        disclaimer: 'Educational research prototype only — not a diagnosis or prescription, and not a substitute for qualified medical care.'
      }
    },
    ko: {
      lang: 'ko',
      title: '의료 합의를 위한 Multi-LLM-as-a-Judge RAG 아키텍처',
      nav: ['소개', '아키텍처', '연구'],
      view: ['홈', '데모'],
      ariaLabels: ['페이지 보기', '주요 탐색', '언어 선택'],
      heroEyebrow: '노팅엄 대학교 · 연구 인턴십',
      heroTitle: '의료 합의를 위한 Multi-LLM-as-a-Judge RAG 아키텍처',
      heroLead: '검색 증강 생성, 에이전트 AI, LLM-as-a-Judge를 결합한 다중 에이전트 헬스케어 AI 프레임워크로, 서양의학, 중의학, 영양, 생활의학 전반에서 근거 기반의 설명 가능한 건강 정보를 제공합니다.',
      supervisor: '지도교수',
      intern: '연구 인턴',
      major: '컴퓨터공학 및 AI 학사과정',
      aboutTitle: '연구 문제',
      aboutLead: '현재 헬스케어 AI 어시스턴트는 중요한 한계를 가지고 있습니다.',
      problems: [
        '<strong>환각</strong> — 모델이 권위 있는 근거 없이 그럴듯하지만 뒷받침되지 않는 의학적 주장을 생성합니다.',
        '<strong>근거 투명성 부족</strong> — 답변이 임상 지침, 문헌, 근거의 강도를 충분히 제시하지 못합니다.',
        '<strong>의학 패러다임 충돌</strong> — 서로 다른 의학 전통과 지식 기반의 권고를 조화롭게 다루기 어렵습니다.',
        '<strong>안전성 관리 부족</strong> — 위험한 조언, 금기, 상호작용, 근거 없는 주장이 자동 검증 없이 통과할 수 있습니다.',
        '<strong>설명 가능성 부족</strong> — 사용자는 투명한 추론, 불확실성, 의견 차이가 아닌 단일한 불투명 답변만 받기 쉽습니다.'
      ],
      visionLabel: '연구 비전',
      vision: '여러 의학 패러다임의 지식을 지능적으로 통합하고, 근거 인식형 AI judge로 권고를 검증하며, 투명하고 안전 중심의 건강 안내를 제공하는 신뢰 가능한 헬스케어 AI 생태계를 개발합니다. 단일 답변 챗봇을 가상의 다학제 자문위원회로 확장하는 것이 목표입니다.',
      archTitle: '시스템 아키텍처',
      archLead: '건강 질문에서 근거 검색, 전문가 토론, 안전성 판단, 최종 합의까지 이어지는 흐름입니다.',
      inputKicker: '입력',
      inputTitle: '질문 접수',
      inputLead: '사용자 맥락을 해석하고 알맞은 의학 지식 경로로 라우팅합니다.',
      userTitle: '사용자',
      userDesc: '건강 질문을 입력합니다',
      plannerTitle: '쿼리 플래너',
      plannerDesc: '질문을 분석하고 검색 및 에이전트 구성을 계획합니다',
      retrievalKicker: '검색',
      retrievalTitle: '이중 근거 기반 검색',
      retrievalLead: '서양의학과 중의학 근거를 각각 검색한 뒤 조화롭게 통합합니다.',
      westRetrievalDesc: '현대 의학 검색',
      tcmRetrievalDesc: '중의학 검색',
      debateKicker: '거버넌스',
      debateTitle: '토론, 판단, 합의',
      debateLead: '전문 에이전트가 답변을 제안하고 SafeJudge가 근거, 위험, 충돌, 신뢰도를 점검합니다.',
      debateLabel: '다중 에이전트 토론',
      debateDesc: '분야별 에이전트가 독립적으로 권고와 근거를 생성합니다',
      agents: [
        ['서양의학 에이전트', '근거 기반 현대 의학'],
        ['중의학 에이전트', '변증, 중약 지식, 중의학 이론'],
        ['영양 에이전트', '식이 및 영양 안내'],
        ['생활습관 에이전트', '행동 및 웰니스 안내']
      ],
      judgeLabel: 'SafeJudge',
      judgeDesc: 'LLM-as-a-Judge가 모든 에이전트 출력을 평가, 검증, 점수화합니다',
      judges: [
        ['근거 Judge', '인용 품질 점검'],
        ['안전 Judge', '위험과 금기 탐지'],
        ['충돌 Judge', '패러다임 간 충돌 식별'],
        ['신뢰도 Judge', '불확실성 추정']
      ],
      outputTitle: '통합 응답',
      outputDesc: '근거 인식형, 안전성 검증형 종합 권고',
      outputItems: ['권고 요약', '근거 및 인용', '합의와 불일치', '안전 참고사항', '신뢰도 점수'],
      researchTitle: '연구 질문',
      researchLead: '연구를 이끄는 핵심 질문입니다.',
      questions: [
        '다중 에이전트 검색과 추론은 기존 RAG 시스템보다 헬스케어 질의응답의 정확성과 완성도를 높일 수 있는가?',
        'LLM-as-a-Judge 메커니즘은 헬스케어 AI 출력의 환각, 위험 권고, 근거 없는 주장을 효과적으로 탐지할 수 있는가?',
        'AI 시스템은 투명성과 신뢰를 유지하면서 서로 다른 의학 패러다임의 권고를 어떻게 조화시킬 수 있는가?',
        '다중 에이전트 토론과 합의 형성은 단일 에이전트 생성보다 답변 품질을 개선하는가?',
        '헬스케어 AI는 근거의 강도, 불확실성, 상충되는 관점을 사용자에게 어떻게 전달해야 하는가?',
        '통합 헬스케어 AI는 과학적 엄밀성을 유지하면서 사용자 신뢰와 신뢰감을 높일 수 있는가?'
      ],
      demoEyebrow: 'MediConsensus 데모',
      demoTitle: '상담 모드 선택',
      demoLead: '건강 질문에 사용할 의학 지식 기반을 선택하세요.',
      demoOptions: [
        ['서양의학', 'MediRAG-West 기반 근거 중심 현대 의학'],
        ['중의학', 'TCM-RAG 기반 전통 중의학'],
        ['서양의학 + 중의학', '두 패러다임을 통합한 상담']
      ],
      statusTitle: '프로토타입 제작 중',
      statusDesc: '상담 워크플로우와 의료 검색 출력은 현재 개발 중입니다.',
      footer: '© 2026 노팅엄 대학교 연구 인턴십',
      footerSub: '의료 합의를 위한 Multi-LLM-as-a-Judge RAG 아키텍처',
      tcm: {
        modeAria: '상담 모드', comingSoon: '준비 중', kicker: 'TCM-RAG · 연구 프로토타입', title: '중의학 관점 알아보기',
        lead: '건강 질문을 입력하세요. 간결하고 안전을 고려한 교육용 답변을 생성하기 전에 로컬 중의학 근거를 검색합니다.', live: '로컬 RAG 준비됨',
        questionLabel: '건강 질문', placeholder: '예: 잠을 잘 못 자고 허리가 뻐근해요.', helper: '느끼는 증상과 시작 시점을 적어 주세요. 개인 식별 정보는 입력하지 마세요.',
        samplesLabel: '예시 질문', samples: [['잠을 잘 못 자고 허리가 뻐근해요', '잠을 잘 못 자고 허리가 뻐근해요'], ['머리에 열감이 있고 목이 간질거려요', '머리에 열감이 있고 목이 간질거려요'], ['스트레스와 복부 팽만, 식욕 저하가 있어요', '스트레스와 복부 팽만, 식욕 저하가 있어요']],
        contextTitle: '선택 정보 추가', contextHint: '검색에 도움', fields: ['나이', '성별', '증상 기간', '임신 상태', '복용 중인 약', '알레르기'],
        placeholders: ['예: 35', '예: 3주', '약 이름만 입력하세요. 이 데모를 근거로 처방약을 중단하지 마세요', '약물, 한약재 또는 음식 알레르기'],
        genderOptions: ['응답하지 않음', '여성', '남성', '논바이너리', '직접 설명'], pregnancyOptions: ['입력하지 않음', '아니요', '임신 중', '임신 준비 중', '수유 중', '확실하지 않음'],
        formSafety: '<strong>연구용입니다.</strong> 진단이나 처방이 아닙니다. 응급 상황에는 즉시 전문 의료 도움을 받으세요.', submit: 'TCM-RAG 실행', loading: '근거 검색 중…',
        validation: '건강 질문을 3자 이상 입력해 주세요.', unreadable: '서버 응답을 읽을 수 없습니다.', failed: '상담을 완료하지 못했습니다. 다시 시도해 주세요.', backendOffline: 'TCM-RAG 서버에 연결할 수 없습니다. http://localhost:8000에서 서버를 시작한 뒤 다시 시도하세요.',
        resultLabel: 'TCM-RAG 결과', summaryTitle: '중의학 관점 요약', fullAnswer: '전체 답변 보기',
        status: { siliconflow_llm: '검색 근거 기반 AI 생성', mock_fallback: '로컬 근거 기반 대체 응답', safety_rule: '안전 규칙 응답', scope_rule: '범위 규칙에 따른 답변 보류', evidence_gate: '근거 부족으로 답변 보류' },
        grounding: { siliconflow_llm: 'LLM 답변은 검색된 로컬 근거에만 기반합니다.', mock_fallback: 'AI 제공자가 사용할 수 없거나 설정되지 않아 로컬 한의학 지식베이스로 답변합니다.', safety_rule: '안전 규칙이 한의학적 해석보다 우선 적용되었습니다.', scope_rule: '현재 TCM-RAG 연구 범위가 생성보다 우선 적용되었습니다.', evidence_gate: '의미 있는 로컬 근거가 검색되지 않아 생성이 차단되었습니다.' },
        stateTitles: { supported: '', insufficient_information: '증상 정보가 더 필요합니다', out_of_scope: '현재 TCM-RAG 범위를 벗어남', safety_critical: '안전 우선 응답', evidence_insufficient: '검색 근거 부족' },
        confidenceAria: '신뢰도 점수', confidence: { low: '낮은 신뢰도', medium: '보통 신뢰도', high: '높은 신뢰도' },
        urgentTitle: '긴급 안전 안내', urgentText: '이 답변은 중의학 해석보다 즉각적인 전문 진료를 우선합니다.', fallbackTitle: '로컬 지식 모드', fallbackText: 'AI 서비스를 사용할 수 없어 로컬 TCM 지식베이스만 사용했습니다.',
        cardLabels: ['변증 가설', '교육용 예시', '안전 우선'], cardTitles: ['가장 관련성 높은 가능성', '검색 근거의 교육용 예시', '핵심 안전 안내'],
        accordions: ['가능한 변증 모두 보기', '교육용 예시 모두 보기', '검색 근거 보기', '안전 안내 모두 보기', '기술 정보 보기'], technicalLabels: ['생성 출처', '모델', '응답 언어', '근거 수', '오류', '검색 방식', '유의미한 매칭', '최고 관련도'],
        emptyPatterns: '안전 우선 답변에는 변증 가설을 표시하지 않습니다.', emptyExamples: '이 답변에는 약재 또는 처방 예시를 표시하지 않습니다.', emptyEvidence: '안전 답변에서는 근거 검색을 생략했습니다.',
        exampleTypes: { herb: '약재', formula: '처방 예시' }, match: '일치', evidenceSummary: (count, score) => `로컬 근거 ${count}건을 바탕으로 했습니다. 최고 일치도: ${score}%.`,
        disclaimer: '교육·연구용 프로토타입이며 진단이나 처방이 아닙니다. 전문 의료인의 진료를 대신하지 않습니다.'
      }
    },
    zh: {
      lang: 'zh-Hans',
      title: '面向医疗共识的 Multi-LLM-as-a-Judge RAG 架构',
      nav: ['关于', '架构', '研究'],
      view: ['首页', '演示'],
      ariaLabels: ['页面视图', '主导航', '语言选择'],
      heroEyebrow: '诺丁汉大学 · 研究实习',
      heroTitle: '面向医疗共识的 Multi-LLM-as-a-Judge RAG 架构',
      heroLead: '一个多智能体医疗 AI 框架，结合检索增强生成、智能体 AI 与 LLM-as-a-Judge，为西医、中医、营养和生活方式医学提供有证据支撑、可解释的健康信息。',
      supervisor: '指导老师',
      intern: '研究实习生',
      major: '计算机科学与人工智能荣誉学士',
      aboutTitle: '研究问题',
      aboutLead: '当前医疗 AI 助手仍存在关键限制。',
      problems: [
        '<strong>幻觉</strong> — 模型可能生成看似合理但缺乏权威证据支持的医学说法。',
        '<strong>证据透明度不足</strong> — 回答很少引用临床指南、文献，或解释证据强度。',
        '<strong>医学范式冲突</strong> — 系统难以协调不同医学传统和知识库中的建议。',
        '<strong>安全治理不足</strong> — 不安全建议、禁忌和无证据主张可能未经自动审查就输出。',
        '<strong>可解释性有限</strong> — 用户往往只得到单一且不透明的答案，而非清晰的推理、不确定性或分歧。'
      ],
      visionLabel: '研究愿景',
      vision: '构建可信且可解释的医疗 AI 生态系统，智能整合多种医学范式的知识，通过证据感知的 AI judge 验证建议，并提供透明、注重安全的健康指导，将医疗 AI 从单一答案聊天机器人转变为虚拟的多学科咨询委员会。',
      archTitle: '系统架构',
      archLead: '从健康问题到证据检索、专家讨论、安全评审与最终共识。',
      inputKicker: '输入',
      inputTitle: '问题接入',
      inputLead: '解析用户上下文，并路由到合适的医学知识路径。',
      userTitle: '用户',
      userDesc: '提出健康问题',
      plannerTitle: '查询规划器',
      plannerDesc: '分析问题并规划检索与智能体',
      retrievalKicker: '检索',
      retrievalTitle: '双证据 grounding',
      retrievalLead: '西医与中医证据源分别检索，再进行协调。',
      westRetrievalDesc: '现代医学检索',
      tcmRetrievalDesc: '中医检索',
      debateKicker: '治理',
      debateTitle: '讨论、评审、共识',
      debateLead: '专业智能体提出答案，SafeJudge 检查证据、风险、冲突和置信度。',
      debateLabel: '多智能体讨论',
      debateDesc: '不同领域的智能体独立生成建议与理由',
      agents: [
        ['西医智能体', '循证现代医学'],
        ['中医智能体', '中医理论、辨证、草药知识'],
        ['营养智能体', '饮食指导'],
        ['生活方式智能体', '行为与健康生活指导']
      ],
      judgeLabel: 'SafeJudge',
      judgeDesc: 'LLM-as-a-Judge 对所有智能体输出进行评估、验证和评分',
      judges: [
        ['证据 Judge', '检查引用质量'],
        ['安全 Judge', '检测风险和禁忌'],
        ['冲突 Judge', '识别范式之间的冲突'],
        ['置信度 Judge', '估计不确定性']
      ],
      outputTitle: '综合响应',
      outputDesc: '经过证据感知与安全验证的综合建议',
      outputItems: ['建议摘要', '证据与引用', '一致与分歧', '安全提示', '置信度评分'],
      researchTitle: '研究问题',
      researchLead: '指导本研究的关键问题。',
      questions: [
        '多智能体检索与推理能否相比传统 RAG 系统提升医疗问答的事实准确性和完整性？',
        'LLM-as-a-Judge 机制能否有效检测医疗 AI 输出中的幻觉、不安全建议和无证据主张？',
        'AI 系统如何在保持透明度和用户信任的同时协调不同医学范式的建议？',
        '多智能体讨论与共识构建是否能比单智能体生成提高医疗答案质量？',
        '医疗 AI 应如何向用户传达证据强度、不确定性和相互冲突的观点？',
        '整合式医疗 AI 能否在不牺牲科学严谨性的前提下提升用户信心和可信度感知？'
      ],
      demoEyebrow: 'MediConsensus 演示',
      demoTitle: '选择咨询模式',
      demoLead: '选择用于健康问题的医学知识库。',
      demoOptions: [
        ['西医', '通过 MediRAG-West 提供循证现代医学'],
        ['中医', '通过 TCM-RAG 提供传统中医'],
        ['西医 + 中医', '双范式整合咨询']
      ],
      statusTitle: '原型开发中',
      statusDesc: '咨询流程和医学检索输出仍在积极开发中。',
      footer: '© 2026 诺丁汉大学研究实习',
      footerSub: '面向医疗共识的 Multi-LLM-as-a-Judge RAG 架构',
      tcm: {
        modeAria: '咨询模式', comingSoon: '即将开放', kicker: 'TCM-RAG · 研究原型', title: '了解中医视角',
        lead: '输入健康问题。系统会先检索本地中医证据，再生成简明且注重安全的科普回答。', live: '本地 RAG 已就绪',
        questionLabel: '健康问题', placeholder: '例如：我有点失眠，最近腰酸。', helper: '请描述你感受到的症状和开始时间，不要填写可识别个人身份的信息。',
        samplesLabel: '试试示例', samples: [['有点失眠，最近腰酸', '我有点失眠，最近腰酸'], ['头有点发热，嗓子痒', '我头有点发热，嗓子痒'], ['压力大，腹胀，胃口不好', '压力大，腹胀，胃口不好']],
        contextTitle: '添加可选信息', contextHint: '帮助检索', fields: ['年龄', '性别', '症状持续时间', '怀孕情况', '目前用药', '过敏情况'],
        placeholders: ['例如：35', '例如：3 周', '只填写药名；不要依据本演示停用处方药', '药物、中药材或食物过敏'],
        genderOptions: ['不愿透露', '女性', '男性', '非二元性别', '自行描述'], pregnancyOptions: ['未提供', '否', '怀孕中', '备孕中', '哺乳期', '不确定'],
        formSafety: '<strong>仅供研究。</strong>本系统不提供诊断或处方；紧急情况请立即寻求专业医疗帮助。', submit: '运行 TCM-RAG', loading: '正在检索证据…',
        validation: '请输入至少 3 个字符的健康问题。', unreadable: '后端返回了无法读取的响应。', failed: '本次咨询未能完成，请重试。', backendOffline: '无法连接 TCM-RAG 后端。请先在 http://localhost:8000 启动服务，然后重试。',
        resultLabel: 'TCM-RAG 结果', summaryTitle: '中医视角摘要', fullAnswer: '查看完整回答',
        status: { siliconflow_llm: 'AI 已基于检索证据生成', mock_fallback: '本地证据回退', safety_rule: '安全规则回复', scope_rule: '范围规则回避回答', evidence_gate: '证据不足回避回答' },
        grounding: { siliconflow_llm: '本次 LLM 回答只基于本地检索到的证据生成。', mock_fallback: 'AI 服务暂不可用或未配置，已暂时使用本地中医医学库为您解答。', safety_rule: '安全规则优先于中医辨证解释。', scope_rule: '当前 TCM-RAG 研究范围优先于模型生成。', evidence_gate: '由于没有检索到足够相关的本地证据，系统已阻断生成。' },
        stateTitles: { supported: '', insufficient_information: '需要补充更多症状信息', out_of_scope: '超出当前 TCM-RAG 范围', safety_critical: '安全优先回复', evidence_insufficient: '检索证据不足' },
        confidenceAria: '置信度评分', confidence: { low: '低置信度', medium: '中等置信度', high: '高置信度' },
        urgentTitle: '紧急安全提示', urgentText: '此回答优先建议立即寻求专业医疗帮助，不进行中医辨证解释。', fallbackTitle: '本地知识模式', fallbackText: 'AI 服务暂不可用，以下结果仅基于本地中医知识库生成。',
        cardLabels: ['辨证假设', '科普示例', '安全优先'], cardTitles: ['最相关的可能方向', '检索资料中的科普示例', '关键安全提示'],
        accordions: ['查看全部可能证型', '查看全部科普示例', '查看检索证据', '查看全部安全提示', '查看技术详情'], technicalLabels: ['生成来源', '模型', '回答语言', '证据数量', '错误', '检索方式', '有效匹配数', '最高相关度'],
        emptyPatterns: '安全优先回答不提供中医证型推测。', emptyExamples: '本回答不展示中药材或方剂示例。', emptyEvidence: '安全优先回答已跳过证据检索。',
        exampleTypes: { herb: '中药材', formula: '方剂示例' }, match: '匹配', evidenceSummary: (count, score) => `基于 ${count} 条本地证据匹配，最高匹配度为 ${score}%。`,
        disclaimer: '仅供教育与研究，不构成诊断或处方，也不能替代合格医疗专业人员的诊疗。'
      }
    }
  };

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  }

  function setHTML(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.innerHTML = value;
  }

  function setTextList(selector, values) {
    document.querySelectorAll(selector).forEach(function (element, index) {
      if (values[index] !== undefined) {
        element.textContent = values[index];
      }
    });
  }

  function setSelectOptions(selector, labels) {
    const select = document.querySelector(selector);
    if (!select) return;
    Array.from(select.options).forEach(function (option, index) {
      if (labels[index] !== undefined) option.textContent = labels[index];
    });
  }

  function applyLanguage(lang) {
    const t = translations[lang] || translations.en;
    currentLanguage = lang;
    document.documentElement.lang = t.lang;
    document.title = t.title;

    setTextList('.toggle-btn', t.view);
    setTextList('.nav a', t.nav);
    toggle.setAttribute('aria-label', t.ariaLabels[0]);
    if (nav) nav.setAttribute('aria-label', t.ariaLabels[1]);
    document.querySelector('.language-switch')?.setAttribute('aria-label', t.ariaLabels[2]);
    setText('.hero .eyebrow', t.heroEyebrow);
    setText('.hero h1', t.heroTitle);
    setText('.hero .lead', t.heroLead);
    setText('.team-list li:first-child .member-role', t.supervisor);
    document.querySelectorAll('.team-list li:not(:first-child) .member-role').forEach(function (el) {
      el.textContent = t.intern;
    });
    document.querySelectorAll('.member-major').forEach(function (el) {
      el.textContent = t.major;
    });

    setText('#about h2', t.aboutTitle);
    setText('#about .section-header p', t.aboutLead);
    document.querySelectorAll('#about .plain-list li').forEach(function (el, index) {
      if (t.problems[index]) el.innerHTML = t.problems[index];
    });
    setText('.vision-label', t.visionLabel);
    setText('.vision p:last-child', t.vision);

    setText('#architecture .section-header h2', t.archTitle);
    setText('#architecture .section-header p', t.archLead);
    setText('.arch-stage-input .metric-kicker', t.inputKicker);
    setText('.arch-stage-input h3', t.inputTitle);
    setText('.arch-stage-input .arch-stage-header p', t.inputLead);
    setText('.arch-stage-input [data-layer="1"] strong', t.userTitle);
    setText('.arch-stage-input [data-layer="1"] .node-text span', t.userDesc);
    setText('.arch-stage-input [data-layer="2"] strong', t.plannerTitle);
    setText('.arch-stage-input [data-layer="2"] .node-text span', t.plannerDesc);

    setText('.arch-stage-retrieval .metric-kicker', t.retrievalKicker);
    setText('.arch-stage-retrieval h3', t.retrievalTitle);
    setText('.arch-stage-retrieval .arch-stage-header p', t.retrievalLead);
    setText('.arch-stage-retrieval .node-blue .node-text span', t.westRetrievalDesc);
    setText('.arch-stage-retrieval .node-green .node-text span', t.tcmRetrievalDesc);

    setText('.arch-stage-governance .metric-kicker', t.debateKicker);
    setText('.arch-stage-governance h3', t.debateTitle);
    setText('.arch-stage-governance .arch-stage-header p', t.debateLead);
    setText('.layer-debate .container-label', t.debateLabel);
    setText('.layer-debate .container-desc', t.debateDesc);
    document.querySelectorAll('.layer-debate .arch-node').forEach(function (el, index) {
      if (t.agents[index]) {
        el.querySelector('strong').textContent = t.agents[index][0];
        el.querySelector('span').textContent = t.agents[index][1];
      }
    });
    setText('.layer-judge .container-label', t.judgeLabel);
    setText('.layer-judge .container-desc', t.judgeDesc);
    document.querySelectorAll('.layer-judge .arch-node').forEach(function (el, index) {
      if (t.judges[index]) {
        el.querySelector('strong').textContent = t.judges[index][0];
        el.querySelector('span').textContent = t.judges[index][1];
      }
    });
    setText('.arch-node-output .node-text strong', t.outputTitle);
    setText('.arch-node-output .node-text span', t.outputDesc);
    setTextList('.node-output-list li', t.outputItems);

    setText('#research h2', t.researchTitle);
    setText('#research .section-header p', t.researchLead);
    setTextList('.rq-list li', t.questions);

    setText('.demo-section .eyebrow', t.demoEyebrow);
    setText('.demo-title', t.demoTitle);
    setText('.demo-lead', t.demoLead);
    document.querySelectorAll('.demo-option').forEach(function (el, index) {
      if (t.demoOptions[index]) {
        el.querySelector('.demo-option-label').textContent = t.demoOptions[index][0];
        el.querySelector('.demo-option-desc').textContent = t.demoOptions[index][1];
      }
    });
    setTextList('.demo-coming-soon', [t.tcm.comingSoon, t.tcm.comingSoon]);
    if (demoOptions) demoOptions.setAttribute('aria-label', t.tcm.modeAria);
    setText('.prototype-status strong', t.statusTitle);
    setText('.prototype-status span:last-child', t.statusDesc);
    setText('.tcm-kicker', t.tcm.kicker);
    setText('#tcm-consultation-title', t.tcm.title);
    setText('.tcm-panel-heading > div > p:last-child', t.tcm.lead);
    setText('.tcm-live-label', t.tcm.live);
    setText('.tcm-question-field > span', t.tcm.questionLabel + ' *');
    if (tcmQuestion) tcmQuestion.placeholder = t.tcm.placeholder;
    setText('.tcm-question-field small', t.tcm.helper);
    setText('.tcm-samples > span', t.tcm.samplesLabel);
    document.querySelector('.tcm-samples')?.setAttribute('aria-label', t.tcm.samplesLabel);
    document.querySelectorAll('.tcm-sample').forEach(function (button, index) {
      if (!t.tcm.samples[index]) return;
      button.textContent = t.tcm.samples[index][0];
      button.dataset.question = t.tcm.samples[index][1];
    });
    setText('.tcm-context-title', t.tcm.contextTitle);
    setText('.tcm-context-hint', t.tcm.contextHint);
    setTextList('.tcm-context-grid .tcm-field > span', t.tcm.fields);
    const age = document.getElementById('tcm-age');
    const duration = document.getElementById('tcm-duration');
    const medications = document.getElementById('tcm-medications');
    const allergies = document.getElementById('tcm-allergies');
    if (age) age.placeholder = t.tcm.placeholders[0];
    if (duration) duration.placeholder = t.tcm.placeholders[1];
    if (medications) medications.placeholder = t.tcm.placeholders[2];
    if (allergies) allergies.placeholder = t.tcm.placeholders[3];
    setSelectOptions('#tcm-gender', t.tcm.genderOptions);
    setSelectOptions('#tcm-pregnancy', t.tcm.pregnancyOptions);
    setHTML('.tcm-form-footer p', t.tcm.formSafety);
    setText('.tcm-submit-label', t.tcm.submit);
    setText('.tcm-result-meta > span:first-child', t.tcm.resultLabel);
    setText('.tcm-result-hero h2', t.tcm.summaryTitle);
    setText('#tcm-full-answer-details summary', t.tcm.fullAnswer);
    document.querySelector('.tcm-confidence')?.setAttribute('aria-label', t.tcm.confidenceAria);
    setText('#tcm-urgent strong', t.tcm.urgentTitle);
    setText('#tcm-urgent span', t.tcm.urgentText);
    setText('#tcm-fallback-banner strong', t.tcm.fallbackTitle);
    setText('#tcm-fallback-banner span', t.tcm.fallbackText);
    setTextList('.tcm-result-grid .tcm-card-heading p', t.tcm.cardLabels.slice(0, 2));
    setTextList('.tcm-result-grid .tcm-card-heading h3', t.tcm.cardTitles.slice(0, 2));
    setText('.tcm-safety-card .tcm-card-heading p', t.tcm.cardLabels[2]);
    setText('.tcm-safety-card .tcm-card-heading h3', t.tcm.cardTitles[2]);
    setTextList('.tcm-accordions > details > summary', t.tcm.accordions);
    setText('#tcm-source-label', t.tcm.technicalLabels[0]);
    setText('#tcm-model-label', t.tcm.technicalLabels[1]);
    setText('#tcm-response-language-label', t.tcm.technicalLabels[2]);
    setText('#tcm-evidence-count-label', t.tcm.technicalLabels[3]);
    setText('#tcm-error-label', t.tcm.technicalLabels[4]);
    setText('#tcm-retrieval-method-label', t.tcm.technicalLabels[5] || 'Retrieval method');
    setText('#tcm-meaningful-count-label', t.tcm.technicalLabels[6] || 'Meaningful matches');
    setText('#tcm-top-score-label', t.tcm.technicalLabels[7] || 'Top relevance');
    setText('.site-footer p:first-child', t.footer);
    setText('.footer-sub', t.footerSub);

    languageButtons.forEach(function (button) {
      const active = button.dataset.lang === lang;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });

    if (currentResultData) renderTCMResult(currentResultData, false);
  }

  languageButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      applyLanguage(button.dataset.lang);
    });
  });
  applyLanguage('en');
})();
