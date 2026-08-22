import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SPEC=importlib.util.spec_from_file_location('rq1_confirmatory',ROOT/'research/experiment_pipeline/rq1_confirmatory.py')
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)

def test_preflight_and_checkpoint():
    config=MOD.load(ROOT/'research/experiments/rq1_c1_vs_c2/confirmatory_protocol/rq1_confirmatory.yaml')
    checks=MOD.preflight(config)
    assert checks['question_count']==100
    assert checks['benchmark_status']=='FROZEN_SOURCE_GROUNDED_RQ1_CONFIRMATORY_V1_1'
    assert checks['provider_ready'] is True
    assert checks['execution_manifest_locked'] is True
    assert config['benchmark_source_review_status']=='APPROVED_AND_FROZEN'

def test_resume_simulation_starts_at_84_without_duplicates():
    result=MOD.simulate_resume()
    assert result=={'completed':83,'next_sequence':84,'duplicates':0,'run_ids_stable':True,'execution_order_stable':True,'passed':True}

def test_benchmark_distribution_and_evidence():
    benchmark=MOD.jsonl(ROOT/'research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1_frozen.jsonl')
    assert len(benchmark)==100
    assert {'herbal_medicine':60,'syndrome_differentiation':25,'herbal_medicine + syndrome_differentiation':15}=={k:sum(x['domain']==k for x in benchmark) for k in ['herbal_medicine','syndrome_differentiation','herbal_medicine + syndrome_differentiation']}
    assert {'easy':40,'medium':40,'hard':20}=={k:sum(x['difficulty']==k for x in benchmark) for k in ['easy','medium','hard']}
    assert all(f['preferred_evidence_ids'] and f['evidence_excerpt'] for x in benchmark for f in x['gold_facts'])

def test_revised_benchmark_has_no_cross_reference_gold_or_prompt_gold_mismatch():
    benchmark=MOD.jsonl(ROOT/'research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1_frozen.jsonl')
    assert all(' see ' not in f" {fact['fact'].lower()} " for item in benchmark for fact in item['gold_facts'])
    for item in benchmark:
        if item['domain']!='herbal_medicine':
            continue
        question=item['question'].lower()
        facts=' '.join(fact['fact'].lower() for fact in item['gold_facts'])
        requested=[]
        if 'function' in question: requested.append('function')
        if 'indication' in question: requested.append('indication')
        if 'used part' in question: requested.append('used part')
        if 'properties' in question: requested.append('traditional properties')
        if 'meridian' in question: requested.append('meridians')
        if 'class' in question: requested.append('traditional class')
        assert all(field in facts for field in requested), item['question_id']

def test_freeze_and_execution_manifests_are_locked():
    config=MOD.load(ROOT/'research/experiments/rq1_c1_vs_c2/confirmatory_protocol/rq1_confirmatory.yaml')
    freeze=json.loads((ROOT/config['freeze_manifest_path']).read_text(encoding='utf-8'))
    execution=json.loads((ROOT/config['output_dir']/'formal_execution_manifest.json').read_text(encoding='utf-8'))
    assert freeze['status']=='FROZEN_SOURCE_GROUNDED_RQ1_CONFIRMATORY_V1_1'
    assert freeze['final_benchmark_sha256']==config['benchmark_sha256']
    assert freeze['corpus_sha256']==config['corpus_sha256']
    assert execution['status']=='LOCKED_BEFORE_PROVIDER_EXECUTION'
    assert len(execution['execution_order'])==200
    assert len({entry['run_id'] for entry in execution['execution_order']})==200
    assert sum(entry['condition']=='C1' for entry in execution['execution_order'])==100
    assert sum(entry['condition']=='C2' for entry in execution['execution_order'])==100
    assert execution['fallback_policy']['count_as_success'] is False

def test_pipeline_stops_for_external_semantic_review():
    source=(ROOT/'research/experiment_pipeline/rq1_confirmatory.py').read_text(encoding='utf-8')
    assert "'status':'SEMANTIC_REVIEW_REQUIRED'" in source
    assert "if not (out/'semantic_review_imported.json').exists()" in source

def test_completed_pipeline_state_is_terminal():
    state=json.loads((ROOT/'research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1/pipeline_state.json').read_text(encoding='utf-8'))
    assert state['status']=='RQ1_CONFIRMATORY_COMPLETE'
    assert state['provider_calls_during_analysis']==0
