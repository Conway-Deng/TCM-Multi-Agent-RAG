import importlib.util, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
SPEC=importlib.util.spec_from_file_location('rq1_confirmatory',ROOT/'research/experiment_pipeline/rq1_confirmatory.py')
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)

def test_preflight_and_checkpoint():
    config=MOD.load(ROOT/'research/experiments/rq1_c1_vs_c2/confirmatory_protocol/rq1_confirmatory.yaml')
    checks=MOD.preflight(config)
    assert checks['question_count']==100
    assert config['benchmark_source_review_status']=='SECOND_EXTERNAL_REVIEW_PENDING'

def test_resume_simulation_starts_at_84_without_duplicates():
    result=MOD.simulate_resume()
    assert result=={'completed':83,'next_sequence':84,'duplicates':0,'passed':True}

def test_benchmark_distribution_and_evidence():
    benchmark=MOD.jsonl(ROOT/'research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1.jsonl')
    assert len(benchmark)==100
    assert {'herbal_medicine':60,'syndrome_differentiation':25,'herbal_medicine + syndrome_differentiation':15}=={k:sum(x['domain']==k for x in benchmark) for k in ['herbal_medicine','syndrome_differentiation','herbal_medicine + syndrome_differentiation']}
    assert {'easy':40,'medium':40,'hard':20}=={k:sum(x['difficulty']==k for x in benchmark) for k in ['easy','medium','hard']}
    assert all(f['preferred_evidence_ids'] and f['evidence_excerpt'] for x in benchmark for f in x['gold_facts'])

def test_revised_benchmark_has_no_cross_reference_gold_or_prompt_gold_mismatch():
    benchmark=MOD.jsonl(ROOT/'research/benchmarks/tcm_gold_rq1_confirmatory_v1/benchmark_confirmatory_v1_1.jsonl')
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
