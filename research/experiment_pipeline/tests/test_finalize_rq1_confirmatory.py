import csv
import hashlib
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'research/experiments/rq1_c1_vs_c2/confirmatory_run_v1_1'
FINAL=RUN/'final_analysis'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_semantic_import_and_unblinding_integrity():
    with (RUN/'semantic_review_for_gpt.csv').open(encoding='utf-8-sig',newline='') as handle:
        packet=list(csv.DictReader(handle))
    with (FINAL/'semantic_review_imported.csv').open(encoding='utf-8-sig',newline='') as handle:
        review=list(csv.DictReader(handle))
    immutable=['item_id','question_id','anonymous_system_label','question','gold_atomic_fact','supplied_evidence','answer']
    assert len(packet)==len(review)==422
    assert len({row['item_id'] for row in review})==422
    assert all(all(left[column]==right[column] for column in immutable) for left,right in zip(packet,review))
    assert sum(row['review_label']=='UNRESOLVED' for row in review)==0
    record=json.loads((FINAL/'semantic_review_import_record.json').read_text(encoding='utf-8'))
    assert record['unblinding']['SYSTEM_A']=='C1 Single-RAG'
    assert record['unblinding']['SYSTEM_B']=='C2 Multi-Agent'


def test_confirmatory_statistics_and_sample_are_frozen():
    stats=json.loads((FINAL/'confirmatory_paired_statistics.json').read_text(encoding='utf-8'))
    full=stats['metrics']['full_recall']
    assert stats['complete_usable_pairs']==92
    assert stats['bootstrap_resamples']==10000
    assert stats['bootstrap_seed']==20260821
    assert abs(full['c1_mean']-0.907608695652174)<1e-15
    assert abs(full['c2_mean']-0.9057971014492754)<1e-15
    assert full['ci_rules_out_at_least_5pp'] is True
    assert full['ci_supports_at_least_5pp'] is False


def test_hashes_and_terminal_state():
    freeze=json.loads((ROOT/'research/benchmarks/tcm_gold_rq1_confirmatory_v1/freeze_manifest_confirmatory_v1_1.json').read_text(encoding='utf-8'))
    manifest=json.loads((FINAL/'confirmatory_analysis_manifest.json').read_text(encoding='utf-8'))
    assert manifest['inputs']['benchmark_sha256']==freeze['final_benchmark_sha256']
    assert manifest['inputs']['corpus_sha256']==freeze['corpus_sha256']
    assert manifest['inputs']['results_jsonl_sha256']==sha(RUN/'results.jsonl')
    assert manifest['inputs']['execution_manifest_sha256']==sha(RUN/'formal_execution_manifest.json')
    state=json.loads((RUN/'pipeline_state.json').read_text(encoding='utf-8'))
    assert state['status']=='RQ1_CONFIRMATORY_COMPLETE'
    assert state['provider_calls_during_analysis']==0


def test_original_closeout_is_preserved_and_extended():
    original=json.loads((ROOT/'research/experiments/rq1_c1_vs_c2/rq1_closeout/rq1_final_manifest.json').read_text(encoding='utf-8'))
    combined=json.loads((ROOT/'research/experiments/rq1_c1_vs_c2/rq1_closeout/rq1_final_manifest_with_confirmatory.json').read_text(encoding='utf-8'))
    assert combined['study_1A']==original
    assert combined['naive_pooled_inference_performed'] is False
    assert combined['status']=='RQ1 COMPLETE — CONFIRMATORY EXTENSION COMPLETE'
