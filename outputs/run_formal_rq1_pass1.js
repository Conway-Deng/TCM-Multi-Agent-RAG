const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const BENCHMARK_PATH = path.join(ROOT, 'research/benchmarks/tcm_gold_v1_2/benchmark_v1_2.jsonl');
const CORPUS_PATH = path.join(ROOT, 'research/corpus/tcm_v1/chunks.jsonl');
const OUTPUT = path.join(ROOT, 'research/experiments/rq1_c1_vs_c2/formal_pass_1_20260821');
const API_URL = process.env.FORMAL_API_URL || 'http://127.0.0.1:8002/api/research/run';
const EXPERIMENT_ID = 'rq1_c1_vs_c2_formal_pass_1_20260821';
const RANDOM_SEED = 20260821;
const MODEL = 'Qwen/Qwen3-8B';
const RETRIEVAL = 'R0';
const BENCHMARK_SHA = '24077270355234c3e53226e22692c1c705daa10dea35f54dc40c7e6ba30224a1';
const CORPUS_SHA = '316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9';
const GIT_REVISION = require('child_process').execFileSync('git', ['rev-parse', 'HEAD'], {cwd: ROOT, encoding: 'utf8'}).trim();

if (fs.existsSync(OUTPUT)) throw new Error(`Output directory already exists: ${OUTPUT}`);
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
if (sha256(BENCHMARK_PATH) !== BENCHMARK_SHA) throw new Error('Frozen benchmark SHA256 mismatch');
if (sha256(CORPUS_PATH) !== CORPUS_SHA) throw new Error('Frozen corpus SHA256 mismatch');
const benchmark = fs.readFileSync(BENCHMARK_PATH, 'utf8').trim().split(/\r?\n/).map(JSON.parse);
if (benchmark.length !== 50) throw new Error(`Expected 50 benchmark questions, got ${benchmark.length}`);
const corpus = fs.readFileSync(CORPUS_PATH, 'utf8').trim().split(/\r?\n/).map(JSON.parse);
if (corpus.length !== 4461) throw new Error(`Expected 4461 corpus chunks, got ${corpus.length}`);

function rng(seed) {
  let state = seed >>> 0;
  return () => {
    state ^= state << 13; state >>>= 0;
    state ^= state >>> 17; state >>>= 0;
    state ^= state << 5; state >>>= 0;
    return state >>> 0;
  };
}
const nextRandom = rng(RANDOM_SEED);
const executionOrder = [];
let sequence = 0;
for (const item of benchmark) {
  const first = nextRandom() % 2 === 0 ? 'C1' : 'C2';
  const second = first === 'C1' ? 'C2' : 'C1';
  for (const condition of [first, second]) executionOrder.push({sequence: ++sequence, question_id: item.question_id, condition});
}

fs.mkdirSync(OUTPUT, {recursive: true});
const manifest = {
  experiment_id: EXPERIMENT_ID,
  purpose: 'First formal controlled RQ1 C1 vs C2 experiment; one interleaved pass only.',
  started_at: new Date().toISOString(),
  benchmark_version: 'v1.2',
  benchmark_status: 'FROZEN_SOURCE_GROUNDED_V1_2',
  benchmark_sha256: BENCHMARK_SHA,
  corpus_version: 'TCM Research Corpus v1',
  corpus_chunk_count: 4461,
  corpus_sha256: CORPUS_SHA,
  model: MODEL,
  provider: 'siliconflow',
  retrieval: RETRIEVAL,
  conditions: ['C1', 'C2'],
  formal_runs_expected: 100,
  c1_runs_expected: 50,
  c2_runs_expected: 50,
  random_seed: RANDOM_SEED,
  execution_order: 'execution_order.json',
  git_revision: GIT_REVISION,
  api_url: API_URL,
  request_parameters: {
    top_k: 4,
    debate_rounds: 1,
    iterative_retrieval: false,
    include_trace: true,
    active_agents: ['syndrome', 'herbal', 'acupuncture_meridian', 'constitution', 'dietary_therapy', 'lifestyle_yangsheng'],
    active_judges: ['evidence', 'hallucination', 'safety', 'conflict', 'confidence', 'provenance'],
    timeout_ms: 180000,
    retry_policy: 'application-configured; identical for C1 and C2',
  },
};
fs.writeFileSync(path.join(OUTPUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
fs.writeFileSync(path.join(OUTPUT, 'execution_order.json'), JSON.stringify({random_seed: RANDOM_SEED, order: executionOrder}, null, 2) + '\n');

function quality(answer, evidenceIds) {
  const citations = [...new Set((String(answer).match(/\[(tcmv1-[0-9a-f]+)\]/g) || []).map(x => x.slice(1, -1)))];
  const validIds = evidenceIds.every(id => /^tcmv1-[0-9a-f]+$/.test(id));
  const citationSubset = citations.every(id => evidenceIds.includes(id));
  const repeated = /\b(\w+)(?:\s+\1){3,}\b/i.test(answer) || /(.{8,})\1{2,}/.test(answer);
  const malformed = String(answer).includes('�') || [...String(answer)].some(c => c.charCodeAt(0) < 9);
  const pass = Boolean(String(answer).trim()) && String(answer).split(/\s+/).length <= 400 && !repeated && !malformed && validIds && citationSubset && citations.length > 0;
  return {pass, citations, reasons: [
    !String(answer).trim() ? 'empty answer' : null,
    String(answer).split(/\s+/).length > 400 ? 'answer over 400 words' : null,
    repeated ? 'repeated text' : null,
    malformed ? 'malformed text' : null,
    !validIds ? 'invalid evidence ID' : null,
    !citationSubset ? 'citation not in retrieved evidence' : null,
    citations.length === 0 ? 'no citations' : null,
  ].filter(Boolean)};
}

function classify({condition, trace, evidenceIds, qualityResult, httpStatus, expectedSpecialists, answer}) {
  if (httpStatus !== 200) return 'FAIL_PROVIDER';
  const attempted = Number(trace?.provider_calls || 0);
  const succeeded = Number(trace?.successful_provider_calls || 0);
  const fallback = Boolean(trace?.fallback_usage);
  if (fallback || (attempted > 0 && succeeded === 0)) return 'FAIL_PROVIDER';
  if (!qualityResult.pass && trace?.generation_mode === 'llm') return 'FAIL_OUTPUT_QUALITY';
  if (condition === 'C2') {
    const actual = new Set(trace?.participating_agents || []);
    const routingCorrect = expectedSpecialists.every(id => actual.has(id));
    if (trace?.generation_mode === 'llm' && !routingCorrect) return 'FAIL_ROUTING';
  }
  if (trace?.generation_mode === 'llm' && succeeded > 0) return attempted > succeeded ? 'PASS_WITH_RETRY' : 'PASS';
  if (trace?.generation_mode === 'abstention') return evidenceIds.length ? 'FAIL_OUTPUT_QUALITY' : (trace?.termination_stage?.includes('routing') ? 'FAIL_ROUTING' : 'COVERAGE_GAP');
  return 'FAIL_OUTPUT_QUALITY';
}

async function runOne(item, condition, sequenceNumber) {
  const started = Date.now();
  const payload = {
    question: item.question,
    condition_id: condition,
    retrieval_strategy: RETRIEVAL,
    active_agents: manifest.request_parameters.active_agents,
    active_judges: manifest.request_parameters.active_judges,
    top_k: 4,
    debate_rounds: 1,
    iterative_retrieval: false,
    include_trace: true,
    random_seed: RANDOM_SEED,
  };
  let httpStatus = 0; let body = null; let error = null;
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 180000);
  try {
    const response = await fetch(API_URL, {method: 'POST', headers: {'Content-Type': 'application/json', Accept: 'application/json'}, body: JSON.stringify(payload), signal: controller.signal});
    httpStatus = response.status;
    const text = await response.text();
    try { body = JSON.parse(text); } catch { body = {raw_body: text}; }
  } catch (err) { error = `${err.name}: ${err.message}`; }
  clearTimeout(timer);
  const trace = body?.trace || {};
  const evidence = Array.isArray(body?.retrieval) ? body.retrieval : [];
  const evidenceIds = [...new Set((trace.retrieved_evidence_ids || evidence.map(x => x.chunk_id)).filter(Boolean))];
  const answer = String(body?.final_answer || trace.final_answer || '');
  const qualityResult = quality(answer, evidenceIds);
  const attempts = Array.isArray(trace.provider_attempts) ? trace.provider_attempts : [];
  const expectedSpecialists = item.expected_specialists || [];
  const actualSpecialists = trace.participating_agents || [];
  const routingCorrect = condition === 'C2' ? expectedSpecialists.every(id => actualSpecialists.includes(id)) : null;
  const record = {
    experiment_id: EXPERIMENT_ID,
    question_id: item.question_id,
    question: item.question,
    condition,
    retrieval_mode: RETRIEVAL,
    model: trace.model || 'none',
    provider: trace.provider || 'none',
    corpus_version: trace.corpus_version || 'unknown',
    corpus_name: trace.corpus_name || 'unknown',
    corpus_sha256: CORPUS_SHA,
    benchmark_version: 'v1.2',
    benchmark_sha256: BENCHMARK_SHA,
    git_revision: trace.git_commit || GIT_REVISION,
    random_seed: RANDOM_SEED,
    execution_sequence: sequenceNumber,
    timestamp: trace.timestamp || new Date().toISOString(),
    run_id: body?.run_id || trace.run_id || null,
    http_status: httpStatus,
    client_latency_ms: Date.now() - started,
    latency_ms: trace.latency_ms ?? Date.now() - started,
    participating_agents: actualSpecialists,
    abstaining_agents: trace.abstaining_agents || [],
    retrieved_evidence_ids: evidenceIds,
    citation_ids: qualityResult.citations,
    full_answer: answer,
    provider_attempted: Number(trace.provider_calls || 0),
    provider_succeeded: Number(trace.successful_provider_calls || 0),
    failed_provider_calls: Number(trace.failed_provider_calls || 0),
    retry_count: attempts.filter(x => x.retry_performed).length,
    retry_reasons: attempts.filter(x => !x.success && (x.error_type || x.error)).map(x => ({attempt: x.attempt, error_type: x.error_type || 'unknown', http_status: x.http_status ?? null, error: x.error || null, retry_performed: Boolean(x.retry_performed)})),
    provider_attempts: attempts,
    fallback: Boolean(trace.fallback_usage),
    generation_mode: trace.generation_mode || null,
    output_quality_pass: qualityResult.pass,
    output_quality_reasons: qualityResult.reasons,
    run_status: classify({condition, trace, evidenceIds, qualityResult, httpStatus, expectedSpecialists, answer}),
    failure_reason: error || trace.system_abstention_reason || (trace.provider_errors || []).join('; ') || qualityResult.reasons.join('; ') || null,
    token_usage: trace.token_usage || {},
    cost: null,
    expected_specialists: expectedSpecialists,
    actual_participating_specialists: actualSpecialists,
    routing_correctness: routingCorrect,
    stage_timings: trace.stage_timings || [],
    termination_stage: trace.termination_stage || null,
    raw_response: body,
  };
  return record;
}

(async () => {
  const results = [];
  const resultsPath = path.join(OUTPUT, 'results.jsonl');
  for (const order of executionOrder) {
    const item = benchmark.find(row => row.question_id === order.question_id);
    const record = await runOne(item, order.condition, order.sequence);
    results.push(record);
    fs.appendFileSync(resultsPath, JSON.stringify(record) + '\n');
    console.log(`${order.sequence}/100 ${order.question_id} ${order.condition} ${record.run_status} ${record.latency_ms}ms`);
  }
  const summary = {};
  for (const condition of ['C1', 'C2']) {
    const subset = results.filter(row => row.condition === condition); const latencies = subset.map(row => Number(row.latency_ms)).filter(Number.isFinite);
    summary[condition] = {runs: subset.length};
    for (const status of ['PASS','PASS_WITH_RETRY','CORRECT_ABSTENTION','COVERAGE_GAP','FAIL_PROVIDER','FAIL_OUTPUT_QUALITY','FAIL_ROUTING','FAIL_GROUNDING']) summary[condition][status] = subset.filter(row => row.run_status === status).length;
    summary[condition].mean_latency_ms = latencies.length ? Math.round(latencies.reduce((a,b)=>a+b,0)/latencies.length*10)/10 : null;
    const sorted = [...latencies].sort((a,b)=>a-b); summary[condition].median_latency_ms = sorted.length ? (sorted.length%2 ? sorted[(sorted.length-1)/2] : (sorted[sorted.length/2-1]+sorted[sorted.length/2])/2) : null;
    summary[condition].provider_retry_count = subset.filter(row => row.retry_count > 0).length;
    summary[condition].provider_retry_attempts = subset.reduce((n,row)=>n+row.retry_count,0);
    summary[condition].fallback_count = subset.filter(row => row.fallback).length;
    summary[condition].routing_correct = condition === 'C2' ? subset.filter(row => row.routing_correctness === true).length : null;
    summary[condition].routing_evaluable = condition === 'C2' ? subset.filter(row => row.routing_correctness !== null).length : null;
  }
  manifest.completed_at = new Date().toISOString(); manifest.actual_runs = results.length;
  fs.writeFileSync(path.join(OUTPUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  fs.writeFileSync(path.join(OUTPUT, 'results.json'), JSON.stringify(results, null, 2) + '\n');
  fs.writeFileSync(path.join(OUTPUT, 'summary.json'), JSON.stringify({experiment_id: EXPERIMENT_ID, ...summary}, null, 2) + '\n');
  const csvHeaders = ['execution_sequence','question_id','condition','run_id','run_status','model','provider','retrieval_mode','latency_ms','provider_attempted','provider_succeeded','retry_count','fallback','generation_mode','output_quality_pass','routing_correctness','retrieved_evidence_ids','citation_ids','failure_reason'];
  const csvEscape = value => `"${String(value ?? '').replace(/"/g,'""')}"`;
  const csv = [csvHeaders.join(','), ...results.map(row => csvHeaders.map(key => csvEscape(Array.isArray(row[key]) ? row[key].join(';') : row[key])).join(','))].join('\n') + '\n';
  fs.writeFileSync(path.join(OUTPUT, 'summary.csv'), csv);
  const readme = `# ${EXPERIMENT_ID}\n\nFirst formal controlled RQ1 pass. Exactly 50 frozen benchmark questions were run once under C1 and once under C2 in deterministic interleaved order (seed ${RANDOM_SEED}), using ${MODEL}, SiliconFlow, and ${RETRIEVAL}.\n\nGold facts were not supplied to generation and no tuning or system changes were performed during execution. This artifact is raw experimental output; Gold-based scoring is a separate next stage.\n`;
  fs.writeFileSync(path.join(OUTPUT, 'README.md'), readme);
  console.log(JSON.stringify(summary, null, 2));
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
