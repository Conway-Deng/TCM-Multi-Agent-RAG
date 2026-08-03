/* ============================================================
   MediRAG-West · Western Medicine Prototype
   Multi-LLM-as-a-Judge RAG Architecture Research Prototype
   University of Nottingham — Research Internship 2026
   ============================================================ */
(function () {
  'use strict';

  /* ─── Sample scenarios ──────────────────────────────────── */
  const SAMPLES = [
    {
      label: 'Persistent headache + fatigue',
      question: 'I have been getting frequent headaches and feeling unusually tired for the past 3 weeks.'
    },
    {
      label: 'Chest tightness on exertion',
      question: 'I experience tightness in my chest when climbing stairs or walking fast. It goes away with rest.'
    },
    {
      label: 'Elevated blood pressure',
      question: 'My blood pressure reading was 145/92. I am 48 years old. Should I be concerned?'
    }
  ];

  /* ─── Multi-LLM mock pipeline ───────────────────────────── */
  const MOCK_PIPELINE = {
    headache: {
      agents: [
        {
          id: 'west_agent',
          label: 'Western Medicine Agent',
          color: '#3b82f6',
          answer: 'Persistent headache with fatigue lasting >3 weeks warrants evaluation for tension-type headache (TTH), anaemia, thyroid dysfunction, or sleep disorders. NICE CG150 recommends a structured headache diary and basic blood panel before imaging.',
          confidence: 0.81,
          citations: ['NICE CG150 – Headache disorders', 'BMJ 2021 – Fatigue in primary care'],
          strength: 'Moderate'
        },
        {
          id: 'nutrition_agent',
          label: 'Nutrition Agent',
          color: '#f59e0b',
          answer: 'Dehydration, low magnesium, and iron deficiency are common dietary triggers for headache and fatigue. Ensuring 2L water intake, dietary iron, and magnesium-rich foods (leafy greens, nuts) may reduce symptom frequency.',
          confidence: 0.72,
          citations: ['Nutrients 2020 – Dietary magnesium and headache'],
          strength: 'Low–Moderate'
        },
        {
          id: 'lifestyle_agent',
          label: 'Lifestyle Agent',
          color: '#8b5cf6',
          answer: 'Consistent sleep schedule (7–9 hrs), aerobic exercise 150 min/week, and stress management techniques (CBT or mindfulness) have Level 1 evidence for reducing tension headache frequency.',
          confidence: 0.78,
          citations: ['Cochrane 2023 – Non-pharmacological headache management'],
          strength: 'Moderate'
        }
      ],
      judges: [
        { id: 'evidence_judge', label: 'Evidence Judge', score: 0.84, note: 'Citations from peer-reviewed guidelines. Moderate evidence level.' },
        { id: 'safety_judge', label: 'Safety Judge', score: 0.96, note: 'No contraindications identified. Safe to provide general guidance.' },
        { id: 'conflict_judge', label: 'Conflict Judge', score: 0.71, note: 'Minor overlap between nutrition and lifestyle agents. No material conflict.' },
        { id: 'confidence_judge', label: 'Confidence Judge', score: 0.78, note: 'Moderate confidence. Symptoms are non-specific; GP review recommended.' }
      ],
      consensus: {
        summary: 'Your symptoms are consistent with tension-type headache combined with fatigue — both common and manageable presentations. A GP visit is advisable to rule out anaemia or thyroid dysfunction. Meanwhile, optimise sleep, hydration, and dietary magnesium.',
        confidence: 0.79,
        level: 'medium',
        urgent: false,
        safety_notes: [
          'Seek immediate care if headache is sudden and severe ("thunderclap"), or accompanied by vision changes, weakness, or fever.',
          'Do not self-diagnose; these recommendations are educational only.'
        ],
        evidence_count: 4,
        sources: ['NICE CG150', 'BMJ 2021', 'Nutrients 2020', 'Cochrane 2023']
      }
    },
    chest: {
      agents: [
        {
          id: 'west_agent',
          label: 'Western Medicine Agent',
          color: '#3b82f6',
          answer: 'Exertional chest tightness relieved by rest is a cardinal symptom of stable angina. ESC 2019 guidelines recommend a resting ECG, exercise tolerance test, and cardiac risk stratification. Urgent same-day assessment if symptoms are new or worsening.',
          confidence: 0.91,
          citations: ['ESC 2019 – Chronic Coronary Syndrome Guidelines', 'NICE CG95 – Chest pain'],
          strength: 'High'
        },
        {
          id: 'nutrition_agent',
          label: 'Nutrition Agent',
          color: '#f59e0b',
          answer: 'Mediterranean diet adherence is associated with 30% lower cardiovascular event risk (PREDIMED trial). Reduce saturated fat, increase omega-3 intake (oily fish 2×/week), and limit processed sodium.',
          confidence: 0.77,
          citations: ['NEJM 2013 – PREDIMED study'],
          strength: 'Moderate'
        },
        {
          id: 'lifestyle_agent',
          label: 'Lifestyle Agent',
          color: '#8b5cf6',
          answer: 'Supervised cardiac rehabilitation exercise programmes improve functional capacity and quality of life. Smoking cessation is the single highest-impact lifestyle intervention for coronary risk reduction.',
          confidence: 0.83,
          citations: ['Cochrane 2021 – Cardiac rehabilitation'],
          strength: 'High'
        }
      ],
      judges: [
        { id: 'evidence_judge', label: 'Evidence Judge', score: 0.91, note: 'High-quality RCT and guideline evidence across agents.' },
        { id: 'safety_judge', label: 'Safety Judge', score: 0.62, note: 'URGENT FLAG: Exertional chest tightness requires same-day medical evaluation to exclude ACS.' },
        { id: 'conflict_judge', label: 'Conflict Judge', score: 0.88, note: 'Agents are consistent. Lifestyle and nutrition advice complementary to clinical pathway.' },
        { id: 'confidence_judge', label: 'Confidence Judge', score: 0.86, note: 'High confidence in urgent referral recommendation.' }
      ],
      consensus: {
        summary: 'Exertional chest tightness relieved by rest strongly suggests a cardiac cause. Please seek same-day medical evaluation — do not delay. An ECG and risk assessment are the appropriate first steps per ESC and NICE guidelines.',
        confidence: 0.87,
        level: 'high',
        urgent: true,
        safety_notes: [
          'URGENT: Seek immediate emergency care if symptoms occur at rest, last >15 minutes, or are accompanied by sweating, jaw/arm pain, or breathlessness.',
          'Do not exercise strenuously until medically evaluated.'
        ],
        evidence_count: 4,
        sources: ['ESC 2019', 'NICE CG95', 'NEJM 2013 PREDIMED', 'Cochrane 2021']
      }
    },
    bp: {
      agents: [
        {
          id: 'west_agent',
          label: 'Western Medicine Agent',
          color: '#3b82f6',
          answer: 'A reading of 145/92 in a 48-year-old falls into Stage 1 hypertension (NICE NG136). Confirm with ambulatory blood pressure monitoring (ABPM) before diagnosis. Lifestyle optimisation is first-line; pharmacotherapy if CV risk is ≥10% at 10 years.',
          confidence: 0.88,
          citations: ['NICE NG136 – Hypertension in adults', 'WHO 2023 Hypertension Guidelines'],
          strength: 'High'
        },
        {
          id: 'nutrition_agent',
          label: 'Nutrition Agent',
          color: '#f59e0b',
          answer: 'DASH diet reduces systolic BP by 8–14 mmHg. Limit sodium to <2.3 g/day, increase potassium (bananas, spinach), and reduce alcohol to <14 units/week.',
          confidence: 0.86,
          citations: ['NEJM 1997 – DASH diet', 'Hypertension 2018 – Sodium restriction'],
          strength: 'High'
        },
        {
          id: 'lifestyle_agent',
          label: 'Lifestyle Agent',
          color: '#8b5cf6',
          answer: 'Regular aerobic exercise (30 min, 5×/week) lowers BP by 4–9 mmHg. Weight loss of 1 kg reduces systolic BP by ~1 mmHg. Stress reduction (mindfulness, yoga) provides an additional 3–4 mmHg benefit.',
          confidence: 0.84,
          citations: ['Hypertension 2013 – Exercise and BP meta-analysis'],
          strength: 'Moderate–High'
        }
      ],
      judges: [
        { id: 'evidence_judge', label: 'Evidence Judge', score: 0.89, note: 'Strong evidence base; all agents cite landmark trials.' },
        { id: 'safety_judge', label: 'Safety Judge', score: 0.93, note: 'No immediate danger. Lifestyle changes are safe. Monitor BP regularly.' },
        { id: 'conflict_judge', label: 'Conflict Judge', score: 0.94, note: 'Strong agent agreement. Lifestyle + nutrition + monitoring are convergent.' },
        { id: 'confidence_judge', label: 'Confidence Judge', score: 0.87, note: 'High confidence. ABPM confirmation is the appropriate next step.' }
      ],
      consensus: {
        summary: 'Your reading of 145/92 is in the Stage 1 hypertension range. NICE guidelines recommend confirming with ambulatory monitoring before starting medication. The DASH diet, regular aerobic exercise, sodium reduction, and limiting alcohol are proven first-line interventions.',
        confidence: 0.88,
        level: 'high',
        urgent: false,
        safety_notes: [
          'A single reading is not sufficient for diagnosis. Ambulatory monitoring is needed.',
          'Seek urgent care if BP exceeds 180/120 or you experience headache, chest pain, or visual disturbance.'
        ],
        evidence_count: 6,
        sources: ['NICE NG136', 'WHO 2023', 'NEJM DASH trial', 'Hypertension 2013', 'Hypertension 2018']
      }
    }
  };

  /* ─── Simulation timing (ms) ────────────────────────────── */
  var TIMING = {
    queryPlan: 700,
    retrieval: 1100,
    agentBase: 1400,
    agentStagger: 400,
    judgingBase: 1200,
    judgingStagger: 300,
    consensus: 800
  };

  /* ─── DOM refs ──────────────────────────────────────────── */
  var westConsultation = document.getElementById('west-consultation');
  var westForm = document.getElementById('west-consult-form');
  var westQuestion = document.getElementById('west-question');
  var westSubmit = document.getElementById('west-submit');
  var westFormMsg = document.getElementById('west-form-message');
  var westResults = document.getElementById('west-results');
  var vizCanvas = document.getElementById('west-viz-canvas');
  var vizSection = document.getElementById('west-viz');

  if (!westConsultation) return;

  /* ─── Sample buttons ─────────────────────────────────────── */
  document.querySelectorAll('.west-sample').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (westQuestion) westQuestion.value = btn.dataset.question || '';
      if (westQuestion) westQuestion.focus();
      if (westFormMsg) westFormMsg.hidden = true;
    });
  });

  /* ─── Pipeline step tracker ─────────────────────────────── */
  var stepEls = {
    query: document.getElementById('wstep-query'),
    retrieval: document.getElementById('wstep-retrieval'),
    debate: document.getElementById('wstep-debate'),
    judging: document.getElementById('wstep-judging'),
    consensus: document.getElementById('wstep-consensus')
  };

  function setStep(key, status) {
    var el = stepEls[key];
    if (!el) return;
    el.dataset.status = status;
  }

  function resetSteps() {
    Object.keys(stepEls).forEach(function (k) { setStep(k, 'waiting'); });
  }

  /* ─── Neural-net canvas visualisation ──────────────────── */
  var animFrameId = null;
  var vizState = null;

  function initViz(agentCount) {
    if (!vizCanvas) return;
    var W = vizCanvas.offsetWidth || 760;
    var H = vizCanvas.offsetHeight || 300;
    vizCanvas.width = W;
    vizCanvas.height = H;

    // Layers: Input → RAG → Agents → Judges → Output
    var layers = [
      { label: 'Query', nodes: 1, color: '#60a5fa' },
      { label: 'RAG', nodes: 4, color: '#34d399' },
      { label: 'Agents', nodes: agentCount || 3, color: '#a78bfa' },
      { label: 'Judges', nodes: 4, color: '#f59e0b' },
      { label: 'Consensus', nodes: 1, color: '#3b82f6' }
    ];

    var padX = 64, padY = 44;
    var layerXs = layers.map(function (_, i) {
      return padX + (i / (layers.length - 1)) * (W - padX * 2);
    });

    var nodes = [];
    layers.forEach(function (layer, li) {
      var n = layer.nodes;
      for (var ni = 0; ni < n; ni++) {
        var y = n === 1 ? H / 2 : padY + ni * ((H - padY * 2) / Math.max(n - 1, 1));
        nodes.push({
          x: layerXs[li], y: y,
          layer: li, color: layer.color,
          activation: 0, targetActivation: 0,
          pulse: Math.random() * Math.PI * 2
        });
      }
    });

    var edges = [];
    var prevNodes = null;
    layers.forEach(function (_, li) {
      var thisNodes = nodes.filter(function (n) { return n.layer === li; });
      if (prevNodes) {
        prevNodes.forEach(function (src) {
          thisNodes.forEach(function (dst) {
            edges.push({ src: src, dst: dst, weight: (Math.random() - 0.5) * 2, signalPos: Math.random(), active: false, color: src.color });
          });
        });
      }
      prevNodes = thisNodes;
    });

    vizState = { nodes: nodes, edges: edges, layers: layers, W: W, H: H, phase: 'idle', tick: 0 };
  }

  function activateViz(phase) {
    if (!vizState) return;
    vizState.phase = phase;
    var layerMap = { retrieval: 1, debate: 2, judging: 3, consensus: 4 };
    var targetLayer = layerMap[phase] !== undefined ? layerMap[phase] : 0;

    vizState.nodes.forEach(function (n) {
      n.targetActivation = n.layer <= targetLayer ? 0.7 + Math.random() * 0.3 : 0.05;
    });
    vizState.edges.forEach(function (e) {
      e.active = e.dst.layer <= targetLayer;
      if (e.active) e.signalPos = Math.random();
    });
  }

  function hexToRgba(hex, a) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + a.toFixed(2) + ')';
  }

  function drawViz() {
    if (!vizCanvas || !vizState) return;
    var ctx = vizCanvas.getContext('2d');
    var nodes = vizState.nodes, edges = vizState.edges, W = vizState.W, H = vizState.H;

    ctx.clearRect(0, 0, W, H);

    nodes.forEach(function (n) {
      n.activation += (n.targetActivation - n.activation) * 0.06;
      n.pulse += 0.04;
    });

    // Draw edges
    edges.forEach(function (e) {
      if (!e.active) {
        ctx.beginPath();
        ctx.moveTo(e.src.x, e.src.y);
        ctx.lineTo(e.dst.x, e.dst.y);
        ctx.strokeStyle = 'rgba(148,163,184,0.06)';
        ctx.lineWidth = 0.7;
        ctx.stroke();
        return;
      }
      var alpha = 0.1 + e.src.activation * 0.35;
      ctx.beginPath();
      ctx.moveTo(e.src.x, e.src.y);
      ctx.lineTo(e.dst.x, e.dst.y);
      ctx.strokeStyle = hexToRgba(e.color, alpha);
      ctx.lineWidth = 0.8 + e.src.activation * 1.4;
      ctx.stroke();

      // Signal dot
      e.signalPos = (e.signalPos + 0.009) % 1;
      var sx = e.src.x + (e.dst.x - e.src.x) * e.signalPos;
      var sy = e.src.y + (e.dst.y - e.src.y) * e.signalPos;
      ctx.beginPath();
      ctx.arc(sx, sy, 2.2, 0, Math.PI * 2);
      ctx.fillStyle = hexToRgba(e.color, 0.82);
      ctx.fill();
    });

    // Draw nodes
    nodes.forEach(function (n) {
      var act = n.activation;
      var r = 7 + act * 5;

      if (act > 0.2) {
        var grad = ctx.createRadialGradient(n.x, n.y, r * 0.4, n.x, n.y, r + act * 22);
        grad.addColorStop(0, hexToRgba(n.color, act * 0.48));
        grad.addColorStop(1, hexToRgba(n.color, 0));
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + act * 22, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = hexToRgba(n.color, 0.12 + act * 0.55);
      ctx.fill();
      ctx.strokeStyle = hexToRgba(n.color, 0.4 + act * 0.55);
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (act > 0.3) {
        var pr = r + Math.sin(n.pulse) * 4;
        ctx.beginPath();
        ctx.arc(n.x, n.y, pr, 0, Math.PI * 2);
        ctx.strokeStyle = hexToRgba(n.color, 0.18 * act);
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    });

    // Layer labels
    if (vizState.layers) {
      ctx.font = '600 10px Inter, sans-serif';
      ctx.textAlign = 'center';
      var drawnLayers = {};
      vizState.nodes.forEach(function (n) {
        if (drawnLayers[n.layer]) return;
        drawnLayers[n.layer] = true;
        var lbl = vizState.layers[n.layer] ? vizState.layers[n.layer].label : '';
        ctx.fillStyle = hexToRgba(n.color, 0.55 + n.activation * 0.45);
        ctx.fillText(lbl, n.x, H - 10);
      });
    }

    animFrameId = requestAnimationFrame(drawViz);
  }

  function startVizLoop() {
    if (animFrameId) cancelAnimationFrame(animFrameId);
    animFrameId = requestAnimationFrame(drawViz);
  }

  function stopVizLoop() {
    if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }
  }

  /* ─── Delay helper ───────────────────────────────────────── */
  function delay(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  /* ─── Get mock data ──────────────────────────────────────── */
  function getMockData(question) {
    var q = question.toLowerCase();
    if (q.includes('headache') || q.includes('tired') || q.includes('fatigue') || q.includes('sleep')) return MOCK_PIPELINE.headache;
    if (q.includes('chest') || q.includes('tightness') || q.includes('heart') || q.includes('breath')) return MOCK_PIPELINE.chest;
    if (q.includes('blood pressure') || q.includes('bp') || q.includes('hypert') || q.includes('145') || q.includes('92')) return MOCK_PIPELINE.bp;
    // Default
    return MOCK_PIPELINE.bp;
  }

  /* ─── Run simulated pipeline ─────────────────────────────── */
  async function runPipeline(question) {
    var data = getMockData(question);

    if (vizSection) vizSection.hidden = false;
    initViz(data.agents.length);
    startVizLoop();

    resetSteps();
    setStep('query', 'active');
    await delay(TIMING.queryPlan);
    setStep('query', 'done');

    setStep('retrieval', 'active');
    activateViz('retrieval');
    await delay(TIMING.retrieval);
    setStep('retrieval', 'done');

    setStep('debate', 'active');
    activateViz('debate');
    await delay(TIMING.agentBase + TIMING.agentStagger * data.agents.length);
    setStep('debate', 'done');

    setStep('judging', 'active');
    activateViz('judging');
    await delay(TIMING.judgingBase + TIMING.judgingStagger * data.judges.length);
    setStep('judging', 'done');

    setStep('consensus', 'active');
    activateViz('consensus');
    await delay(TIMING.consensus);
    setStep('consensus', 'done');

    return data;
  }

  /* ─── Render helpers ─────────────────────────────────────── */
  function mk(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined) e.textContent = txt;
    return e;
  }

  function renderAgents(agents) {
    var container = document.getElementById('west-agents-grid');
    if (!container) return;
    container.replaceChildren();

    agents.forEach(function (agent) {
      var card = mk('article', 'west-agent-card');
      card.style.setProperty('--agent-color', agent.color);

      var head = mk('div', 'west-agent-head');
      var dot = mk('span', 'west-agent-dot');
      dot.style.background = agent.color;
      var title = mk('h4', 'west-agent-title', agent.label);
      var conf = mk('span', 'west-conf-badge', Math.round(agent.confidence * 100) + '%');
      conf.style.setProperty('--agent-color', agent.color);
      head.append(dot, title, conf);

      var body = mk('p', 'west-agent-body', agent.answer);

      var foot = mk('div', 'west-agent-foot');
      foot.append(mk('span', 'west-strength-pill', 'Evidence: ' + agent.strength));
      if (agent.citations && agent.citations.length) {
        var cites = mk('div', 'west-citations');
        agent.citations.forEach(function (c) { cites.append(mk('span', 'west-cite', c)); });
        foot.append(cites);
      }

      card.append(head, body, foot);
      container.append(card);
    });
  }

  var JUDGE_COLORS = {
    evidence_judge: '#60a5fa',
    safety_judge: '#34d399',
    conflict_judge: '#f59e0b',
    confidence_judge: '#a78bfa'
  };
  var JUDGE_ICONS = {
    evidence_judge: '📋',
    safety_judge: '🛡',
    conflict_judge: '⚖',
    confidence_judge: '📊'
  };

  function renderJudges(judges) {
    var container = document.getElementById('west-judges-grid');
    if (!container) return;
    container.replaceChildren();

    judges.forEach(function (judge) {
      var card = mk('article', 'west-judge-card');
      var color = JUDGE_COLORS[judge.id] || '#64748b';
      var pct = Math.round(judge.score * 100);
      card.style.setProperty('--judge-color', color);

      var head = mk('div', 'west-judge-head');
      head.append(mk('span', 'west-judge-icon', JUDGE_ICONS[judge.id] || '🔍'), mk('span', 'west-judge-title', judge.label));

      // SVG score ring
      var NS = 'http://www.w3.org/2000/svg';
      var svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('viewBox', '0 0 44 44');
      svg.classList.add('west-score-ring');
      var circ = 2 * Math.PI * 18;
      var bgC = document.createElementNS(NS, 'circle');
      bgC.setAttribute('cx', '22'); bgC.setAttribute('cy', '22'); bgC.setAttribute('r', '18');
      bgC.setAttribute('fill', 'none'); bgC.setAttribute('stroke', 'rgba(0,0,0,0.07)'); bgC.setAttribute('stroke-width', '4');
      var fgC = document.createElementNS(NS, 'circle');
      fgC.setAttribute('cx', '22'); fgC.setAttribute('cy', '22'); fgC.setAttribute('r', '18');
      fgC.setAttribute('fill', 'none'); fgC.setAttribute('stroke', color); fgC.setAttribute('stroke-width', '4');
      fgC.setAttribute('stroke-linecap', 'round');
      fgC.setAttribute('stroke-dasharray', circ.toFixed(1));
      fgC.setAttribute('stroke-dashoffset', (circ * (1 - judge.score)).toFixed(1));
      fgC.setAttribute('transform', 'rotate(-90 22 22)');
      var txt = document.createElementNS(NS, 'text');
      txt.setAttribute('x', '22'); txt.setAttribute('y', '27');
      txt.setAttribute('text-anchor', 'middle'); txt.setAttribute('font-size', '11');
      txt.setAttribute('font-weight', '700'); txt.setAttribute('fill', color);
      txt.textContent = pct + '%';
      svg.append(bgC, fgC, txt);

      card.append(head, svg, mk('p', 'west-judge-note', judge.note));
      container.append(card);
    });
  }

  function renderConsensus(consensus) {
    var summaryEl = document.getElementById('west-consensus-summary');
    var confScore = document.getElementById('west-conf-score');
    var confLabel = document.getElementById('west-conf-label');
    var sourcesEl = document.getElementById('west-sources-list');
    var safetyEl = document.getElementById('west-safety-list');
    var urgentEl = document.getElementById('west-urgent-banner');
    var evCount = document.getElementById('west-evidence-count');

    if (summaryEl) summaryEl.textContent = consensus.summary;
    if (confScore) confScore.textContent = Math.round(consensus.confidence * 100) + '%';
    if (confLabel) {
      var labels = { low: 'Low confidence', medium: 'Moderate confidence', high: 'High confidence' };
      confLabel.textContent = labels[consensus.level] || 'Confidence';
    }
    if (evCount) evCount.textContent = consensus.evidence_count + ' evidence sources';

    if (sourcesEl) {
      sourcesEl.replaceChildren();
      (consensus.sources || []).forEach(function (s) { sourcesEl.append(mk('li', '', s)); });
    }
    if (safetyEl) {
      safetyEl.replaceChildren();
      (consensus.safety_notes || []).forEach(function (n) { safetyEl.append(mk('li', 'west-safety-note', n)); });
    }
    if (urgentEl) {
      urgentEl.hidden = !consensus.urgent;
      if (westResults) westResults.classList.toggle('west-is-urgent', Boolean(consensus.urgent));
    }
  }

  function renderResults(data) {
    if (!westResults) return;
    renderAgents(data.agents);
    renderJudges(data.judges);
    renderConsensus(data.consensus);
    westResults.hidden = false;
    westResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* ─── Form submit ────────────────────────────────────────── */
  if (westForm) {
    westForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var question = westQuestion ? westQuestion.value.trim() : '';
      if (question.length < 3) {
        if (westFormMsg) { westFormMsg.textContent = 'Please enter a health question of at least 3 characters.'; westFormMsg.hidden = false; }
        if (westQuestion) westQuestion.focus();
        return;
      }
      if (westFormMsg) westFormMsg.hidden = true;
      if (westResults) westResults.hidden = true;

      if (westSubmit) {
        westSubmit.disabled = true;
        westSubmit.classList.add('is-loading');
        var lbl = westSubmit.querySelector('.west-submit-label');
        if (lbl) lbl.textContent = 'Running pipeline…';
      }

      runPipeline(question).then(function (data) {
        renderResults(data);
      }).catch(function () {
        if (westFormMsg) { westFormMsg.textContent = 'Something went wrong. Please try again.'; westFormMsg.hidden = false; }
      }).finally(function () {
        if (westSubmit) {
          westSubmit.disabled = false;
          westSubmit.classList.remove('is-loading');
          var lbl = westSubmit.querySelector('.west-submit-label');
          if (lbl) lbl.textContent = 'Run MediRAG-West';
        }
      });
    });
  }

  /* ─── Expose for app.js mode-switching ──────────────────── */
  window._westConsultation = westConsultation;

  /* ─── Resize → redraw ────────────────────────────────────── */
  var resizeTimer;
  window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      if (vizState && vizCanvas) {
        var agentCount = vizState.nodes.filter(function (n) { return n.layer === 2; }).length || 3;
        stopVizLoop();
        initViz(agentCount);
        if (animFrameId !== null || vizSection && !vizSection.hidden) startVizLoop();
      }
    }, 200);
  });
})();
