const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const BENCHMARK_PATH = path.join(ROOT, 'research/benchmarks/tcm_gold_v1_2/benchmark_v1_2.jsonl');
const RESULTS_PATH = path.join(ROOT, 'research/experiments/rq1_c1_vs_c2/formal_pass_1_retry_20260821/results.jsonl');
const MANIFEST_PATH = path.join(ROOT, 'research/experiments/rq1_c1_vs_c2/formal_pass_1_retry_20260821/manifest.json');
const OUT = path.join(ROOT, 'research/experiments/rq1_c1_vs_c2/formal_pass_1_retry_20260821/evaluation');
const EXPECTED_BENCHMARK_SHA = '24077270355234c3e53226e22692c1c705daa10dea35f54dc40c7e6ba30224a1';
const EXPECTED_CORPUS_SHA = '316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9';

const readJsonl = file => fs.readFileSync(file, 'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const benchmark = readJsonl(BENCHMARK_PATH);
const results = readJsonl(RESULTS_PATH);
const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
if (sha256(BENCHMARK_PATH) !== EXPECTED_BENCHMARK_SHA) throw new Error('Benchmark hash mismatch');
if (manifest.benchmark_sha256 !== EXPECTED_BENCHMARK_SHA) throw new Error('Manifest benchmark hash mismatch');
if (manifest.corpus_sha256 !== EXPECTED_CORPUS_SHA) throw new Error('Manifest corpus hash mismatch');
if (benchmark.length !== 50 || results.length !== 100) throw new Error('Expected 50 benchmark rows and 100 result rows');
const conditions = results.reduce((acc, row) => ((acc[row.condition] ||= []).push(row), acc), {});
if ((conditions.C1 || []).length !== 50 || (conditions.C2 || []).length !== 50) throw new Error('Condition counts are not 50/50');
const pairs = new Map();
for (const row of results) { const key = row.question_id; if (!pairs.has(key)) pairs.set(key, new Set()); const set = pairs.get(key); if (set.has(row.condition)) throw new Error(`Duplicate pair ${key}/${row.condition}`); set.add(row.condition); }
if (pairs.size !== 50 || [...pairs.values()].some(set => set.size !== 2)) throw new Error('Pair coverage is incomplete');
if (results.some(row => row.benchmark_sha256 !== EXPECTED_BENCHMARK_SHA || row.corpus_sha256 !== EXPECTED_CORPUS_SHA)) throw new Error('Result-level frozen hashes mismatch');
const byQuestion = new Map(benchmark.map(row => [row.question_id, row]));

function median(values) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  return sorted.length % 2 ? sorted[(sorted.length - 1) / 2] : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
}
function mean(values) {
  const usable = values.filter(Number.isFinite);
  return usable.length ? usable.reduce((a, b) => a + b, 0) / usable.length : null;
}
function acceptableIds(fact) { return new Set([...(fact.preferred_evidence_ids || []), ...(fact.acceptable_alternate_evidence_ids || [])]); }
function semanticFacts(item) {
  return (item.gold_facts || []).map(fact => ({
    fact: fact.fact,
    preferred_evidence_ids: fact.preferred_evidence_ids || [],
    acceptable_alternate_evidence_ids: fact.acceptable_alternate_evidence_ids || [],
    evidence_excerpt: fact.evidence_excerpt,
  }));
}

function score(row) {
  const item = byQuestion.get(row.question_id);
  const usable = row.provider_succeeded > 0 && row.generation_mode === 'llm' && row.fallback === false && row.output_quality_pass === true;
  const retrieved = new Set(row.retrieved_evidence_ids || []);
  const cited = new Set(row.citation_ids || []);
  const facts = item.gold_facts || [];
  let retrievedFacts = 0; let citedFacts = 0;
  for (const fact of facts) {
    const accepted = acceptableIds(fact);
    if ([...accepted].some(id => retrieved.has(id))) retrievedFacts += 1;
    if ([...accepted].some(id => cited.has(id))) citedFacts += 1;
  }
  const supportedCitations = [...cited].filter(id => facts.some(fact => acceptableIds(fact).has(id)));
  const multiTarget = Array.isArray(item.requested_targets) && item.requested_targets.length > 0;
  const targetCoverage = multiTarget ? item.requested_targets.map(target => {
    const ids = new Set((target.gold_facts || []).flatMap(fact => [...acceptableIds(fact)]));
    return {target: target.target, retrieved: [...ids].some(id => retrieved.has(id)), cited: [...ids].some(id => cited.has(id))};
  }) : [];
  return {
    experiment_id: row.experiment_id,
    question_id: row.question_id,
    question: row.question,
    condition: row.condition,
    execution_sequence: row.execution_sequence,
    run_id: row.run_id,
    run_status: row.run_status,
    usable_real_provider_output: usable,
    provider_failure: !usable,
    retry_required: row.retry_count > 0,
    fallback: Boolean(row.fallback),
    provider_attempted: row.provider_attempted,
    provider_succeeded: row.provider_succeeded,
    latency_ms: row.latency_ms,
    model: row.model,
    provider: row.provider,
    retrieved_evidence_ids: row.retrieved_evidence_ids || [],
    citation_ids: row.citation_ids || [],
    gold_fact_count: facts.length,
    gold_facts_retrieved: usable ? retrievedFacts : null,
    gold_facts_cited: usable ? citedFacts : null,
    gold_evidence_retrieval_recall: usable ? retrievedFacts / facts.length : null,
    gold_evidence_citation_recall: usable ? citedFacts / facts.length : null,
    citation_precision: usable ? (cited.size ? supportedCitations.length / cited.size : 0) : null,
    multi_target: multiTarget,
    multi_target_target_coverage: usable && multiTarget ? targetCoverage : null,
    multi_target_both_targets_retrieved: usable && multiTarget ? targetCoverage.every(target => target.retrieved) : null,
    multi_target_both_targets_cited: usable && multiTarget ? targetCoverage.every(target => target.cited) : null,
    cross_target_relation_flag: null,
    expected_specialists: row.expected_specialists || [],
    actual_participating_specialists: row.actual_participating_specialists || [],
    routing_correctness: row.condition === 'C2' ? row.routing_correctness : null,
    failure_reason: row.failure_reason,
  };
}
const scored = results.map(score);
const usable = scored.filter(row => row.usable_real_provider_output);
const paired = [...pairs.keys()].filter(questionId => {
  const rows = scored.filter(row => row.question_id === questionId);
  return rows.length === 2 && rows.every(row => row.usable_real_provider_output);
}).map(questionId => {
  const c1 = scored.find(row => row.question_id === questionId && row.condition === 'C1');
  const c2 = scored.find(row => row.question_id === questionId && row.condition === 'C2');
  return {
    question_id: questionId,
    question: c1.question,
    c1_gold_evidence_retrieval_recall: c1.gold_evidence_retrieval_recall,
    c2_gold_evidence_retrieval_recall: c2.gold_evidence_retrieval_recall,
    delta_gold_evidence_retrieval_recall_c2_minus_c1: c2.gold_evidence_retrieval_recall - c1.gold_evidence_retrieval_recall,
    c1_gold_evidence_citation_recall: c1.gold_evidence_citation_recall,
    c2_gold_evidence_citation_recall: c2.gold_evidence_citation_recall,
    delta_gold_evidence_citation_recall_c2_minus_c1: c2.gold_evidence_citation_recall - c1.gold_evidence_citation_recall,
    c1_citation_precision: c1.citation_precision,
    c2_citation_precision: c2.citation_precision,
    delta_citation_precision_c2_minus_c1: c2.citation_precision - c1.citation_precision,
    c1_latency_ms: c1.latency_ms,
    c2_latency_ms: c2.latency_ms,
    delta_latency_ms_c2_minus_c1: c2.latency_ms - c1.latency_ms,
    c1_multi_target_both_targets_retrieved: c1.multi_target_both_targets_retrieved,
    c2_multi_target_both_targets_retrieved: c2.multi_target_both_targets_retrieved,
  };
});

function conditionSummary(condition) {
  const all = scored.filter(row => row.condition === condition);
  const real = all.filter(row => row.usable_real_provider_output);
  const metric = key => mean(real.map(row => row[key]));
  const multi = real.filter(row => row.multi_target);
  return {
    total: all.length,
    usable_real_provider_outputs: real.length,
    provider_failures: all.filter(row => row.provider_failure).length,
    PASS: all.filter(row => row.run_status === 'PASS').length,
    PASS_WITH_RETRY: all.filter(row => row.run_status === 'PASS_WITH_RETRY').length,
    CORRECT_ABSTENTION: all.filter(row => row.run_status === 'CORRECT_ABSTENTION').length,
    COVERAGE_GAP: all.filter(row => row.run_status === 'COVERAGE_GAP').length,
    FAIL_PROVIDER: all.filter(row => row.run_status === 'FAIL_PROVIDER').length,
    FAIL_OUTPUT_QUALITY: all.filter(row => row.run_status === 'FAIL_OUTPUT_QUALITY').length,
    FAIL_ROUTING: all.filter(row => row.run_status === 'FAIL_ROUTING').length,
    FAIL_GROUNDING: all.filter(row => row.run_status === 'FAIL_GROUNDING').length,
    retry_rate: all.length ? all.filter(row => row.retry_required).length / all.length : null,
    retry_records: all.filter(row => row.retry_required).length,
    mean_latency_ms: mean(all.map(row => row.latency_ms)),
    median_latency_ms: median(all.map(row => row.latency_ms)),
    usable_mean_latency_ms: mean(real.map(row => row.latency_ms)),
    usable_median_latency_ms: median(real.map(row => row.latency_ms)),
    gold_evidence_retrieval_recall: metric('gold_evidence_retrieval_recall'),
    gold_evidence_citation_recall: metric('gold_evidence_citation_recall'),
    citation_precision: metric('citation_precision'),
    multi_target_questions_usable: multi.length,
    multi_target_target_coverage: multi.length ? mean(multi.flatMap(row => row.multi_target_target_coverage.map(target => target.retrieved ? 1 : 0))) : null,
    multi_target_both_targets_retrieved: multi.length ? mean(multi.map(row => row.multi_target_both_targets_retrieved ? 1 : 0)) : null,
    routing_accuracy: condition === 'C2' ? mean(all.map(row => row.routing_correctness === true ? 1 : 0)) : null,
  };
}
const c1Summary = conditionSummary('C1'); const c2Summary = conditionSummary('C2');
const pairedSummary = {
  complete_usable_pairs: paired.length,
  mean_delta_c2_minus_c1: {
    gold_evidence_retrieval_recall: mean(paired.map(row => row.delta_gold_evidence_retrieval_recall_c2_minus_c1)),
    gold_evidence_citation_recall: mean(paired.map(row => row.delta_gold_evidence_citation_recall_c2_minus_c1)),
    citation_precision: mean(paired.map(row => row.delta_citation_precision_c2_minus_c1)),
    latency_ms: mean(paired.map(row => row.delta_latency_ms_c2_minus_c1)),
  },
  statistical_preparation: ['paired bootstrap confidence intervals', 'Wilcoxon signed-rank where appropriate', 'McNemar test for paired binary outcomes'],
  significance_tests_run: false,
};

const semanticPacket = usable.map(row => {
  const item = byQuestion.get(row.question_id);
  return {
    experiment_id: row.experiment_id,
    question_id: row.question_id,
    question: row.question,
    condition: row.condition,
    run_id: row.run_id,
    answer: results.find(raw => raw.run_id === row.run_id)?.full_answer || '',
    atomic_gold_facts: semanticFacts(item).map(fact => ({...fact, semantic_status: 'UNRESOLVED'})),
    instruction: 'Semantic paraphrase/support labels are intentionally unresolved; do not infer correctness from exact-string comparison.',
  };
});

fs.mkdirSync(OUT, {recursive: true});
fs.writeFileSync(path.join(OUT, 'objective_scores.jsonl'), scored.map(row => JSON.stringify(row)).join('\n') + '\n');
const csvHeaders = ['execution_sequence','question_id','condition','run_status','usable_real_provider_output','provider_failure','retry_required','fallback','provider_attempted','provider_succeeded','latency_ms','gold_fact_count','gold_facts_retrieved','gold_facts_cited','gold_evidence_retrieval_recall','gold_evidence_citation_recall','citation_precision','multi_target','multi_target_both_targets_retrieved','multi_target_both_targets_cited','routing_correctness','failure_reason'];
const esc = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
fs.writeFileSync(path.join(OUT, 'objective_scores.csv'), [csvHeaders.join(','), ...scored.map(row => csvHeaders.map(key => esc(row[key])).join(','))].join('\n') + '\n');
const pairHeaders = Object.keys(paired[0] || {question_id:''});
fs.writeFileSync(path.join(OUT, 'paired_objective_scores.csv'), [pairHeaders.join(','), ...paired.map(row => pairHeaders.map(key => esc(row[key])).join(','))].join('\n') + '\n');
fs.writeFileSync(path.join(OUT, 'semantic_review_packet.jsonl'), semanticPacket.map(row => JSON.stringify(row)).join('\n') + '\n');
const evaluationSummary = {
  evaluation_id: 'rq1_c1_vs_c2_formal_pass_1_objective_evaluation_20260821',
  experiment_id: manifest.experiment_id,
  benchmark_sha256: EXPECTED_BENCHMARK_SHA,
  corpus_sha256: EXPECTED_CORPUS_SHA,
  integrity: {benchmark_questions: benchmark.length, result_records: results.length, c1: conditions.C1.length, c2: conditions.C2.length, unique_question_pairs: pairs.size, gold_content_changed: false},
  C1: c1Summary,
  C2: c2Summary,
  paired: pairedSummary,
  semantic_gold: {resolved_atomic_facts: 0, unresolved_atomic_facts: semanticPacket.reduce((n, row) => n + row.atomic_gold_facts.length, 0), method: 'No validated deterministic semantic comparison was available; all labels remain UNRESOLVED.'},
  no_generation_calls_during_evaluation: true,
};
fs.writeFileSync(path.join(OUT, 'evaluation_summary.json'), JSON.stringify(evaluationSummary, null, 2) + '\n');
const md = `# RQ1 formal pass 1 objective evaluation\n\nThis evaluation uses only stored formal outputs and frozen Gold metadata. No C1/C2/provider calls were made.\n\n- C1 usable real-provider outputs: ${c1Summary.usable_real_provider_outputs}/50\n- C2 usable real-provider outputs: ${c2Summary.usable_real_provider_outputs}/50\n- Complete usable pairs: ${paired.length}\n- C1 Gold evidence retrieval recall: ${c1Summary.gold_evidence_retrieval_recall}\n- C2 Gold evidence retrieval recall: ${c2Summary.gold_evidence_retrieval_recall}\n- C1 Gold evidence citation recall: ${c1Summary.gold_evidence_citation_recall}\n- C2 Gold evidence citation recall: ${c2Summary.gold_evidence_citation_recall}\n- C1 citation precision: ${c1Summary.citation_precision}\n- C2 citation precision: ${c2Summary.citation_precision}\n\nSemantic Gold-fact labels are unresolved and require a frozen semantic judge or human validation stage. These objective metrics do not establish which condition is better.\n`;
fs.writeFileSync(path.join(OUT, 'evaluation_summary.md'), md);
fs.writeFileSync(path.join(OUT, 'README.md'), '# Formal RQ1 pass 1 evaluation\n\nObjective metrics were computed deterministically from stored outputs and frozen Gold evidence. Semantic fact judgments remain UNRESOLVED. No generation or provider calls were made.\n');
console.log(JSON.stringify(evaluationSummary, null, 2));
