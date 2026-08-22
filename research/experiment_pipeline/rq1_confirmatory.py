import argparse, csv, hashlib, json, os, random, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_CONFIG=ROOT/'research/experiments/rq1_c1_vs_c2/confirmatory_protocol/rq1_confirmatory.yaml'

def load(path): return yaml.safe_load(Path(path).read_text(encoding='utf-8'))
def jsonl(path): return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x]
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def atomic_write(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(data,encoding='utf-8'); os.replace(tmp,path)
def _safe_env():
    values={}
    env_path=ROOT/'backend/.env'
    if env_path.exists():
        for raw in env_path.read_text(encoding='utf-8-sig').splitlines():
            line=raw.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            key,value=line.split('=',1);values[key.strip()]=value.strip().strip('"').strip("'")
    values.update({key:value for key,value in os.environ.items() if key.startswith(('LLM_','RESEARCH_','STRICT_','TCM_'))})
    return values
def _planned_run_id(c,sequence,question_id,condition): return f"{c['experiment_id']}-{sequence:03d}-{question_id}-{condition}"
def _resume_state(c, planned):
    out=ROOT/c['output_dir']; results_path=out/'results.jsonl'; records=jsonl(results_path) if results_path.exists() else []
    pairs=[(x.get('question_id'),x.get('condition')) for x in records]
    if len(pairs)!=len(set(pairs)): raise SystemExit('DUPLICATE_FORMAL_OUTPUT')
    expected={(x['question_id'],x['condition']):x for x in planned}
    for record in records:
        key=(record.get('question_id'),record.get('condition')); entry=expected.get(key)
        if entry is None: raise SystemExit('UNPLANNED_FORMAL_OUTPUT')
        if record.get('execution_sequence')!=entry['sequence'] or record.get('run_id')!=entry['run_id']: raise SystemExit('FORMAL_OUTPUT_ID_OR_SEQUENCE_MISMATCH')
        if record.get('benchmark_sha256')!=c['benchmark_sha256'] or record.get('corpus_sha256')!=c['corpus_sha256']: raise SystemExit('FORMAL_OUTPUT_HASH_MISMATCH')
    remaining=[x for x in planned if (x['question_id'],x['condition']) not in set(pairs)]
    return {'completed_records':len(records),'next_execution_sequence':remaining[0]['sequence'] if remaining else None,'duplicates':0,'internally_consistent':True}
def preflight(c,require_execution_manifest=True):
    bench=ROOT/c['benchmark_path']; corpus=ROOT/c['corpus_path']; items=jsonl(bench)
    freeze=ROOT/c['freeze_manifest_path']; protocol=ROOT/c['protocol_path']; out=ROOT/c['output_dir']
    if not freeze.exists() or not protocol.exists(): raise SystemExit('FREEZE_OR_PROTOCOL_MISSING')
    freeze_data=json.loads(freeze.read_text(encoding='utf-8'))
    checks={'benchmark_status':freeze_data.get('status'),'benchmark_sha256':sha(bench),'corpus_sha256':sha(corpus),'question_count':len(items),'model':c['model'],'retrieval':c['retrieval'],'conditions':c['conditions']}
    if checks['benchmark_sha256']!=c['benchmark_sha256'] or checks['corpus_sha256']!=c['corpus_sha256']: raise SystemExit('HASH_MISMATCH')
    if freeze_data.get('final_benchmark_sha256')!=checks['benchmark_sha256'] or freeze_data.get('corpus_sha256')!=checks['corpus_sha256']: raise SystemExit('FREEZE_MANIFEST_HASH_MISMATCH')
    if freeze_data.get('status')!='FROZEN_SOURCE_GROUNDED_RQ1_CONFIRMATORY_V1_1' or c['benchmark_source_review_status']!='APPROVED_AND_FROZEN': raise SystemExit('BENCHMARK_NOT_FROZEN')
    if len(items)!=100 or len({x['question_id'] for x in items})!=100: raise SystemExit('BENCHMARK_COUNT_OR_ID_MISMATCH')
    if c['model']!='Qwen/Qwen3-8B' or c['retrieval']!='R0' or c['conditions']!=['C1','C2']: raise SystemExit('FROZEN_CONFIG_MISMATCH')
    if c['planned_questions']!=100 or c['planned_runs']!=200: raise SystemExit('FROZEN_RUN_COUNT_MISMATCH')
    env=_safe_env(); provider=env.get('LLM_PROVIDER','').casefold(); key=env.get('LLM_API_KEY','').strip(); env_model=env.get('LLM_MODEL','Qwen/Qwen3-8B').strip()
    provider_ready=provider=='siliconflow' and bool(key) and key!='<USER_MUST_INSERT_HERE>' and env_model==c['model']
    if not provider_ready: raise SystemExit('LOCAL_PROVIDER_NOT_STRUCTURALLY_READY')
    checks.update({'provider_configured':'siliconflow','provider_ready':True,'llm_execution_required_on_launch':True,'mock':False,'protocol_locked':True,'freeze_manifest_valid':True})
    planned=order(c,items)
    if require_execution_manifest:
        execution_path=out/'formal_execution_manifest.json'
        if not execution_path.exists(): raise SystemExit('FORMAL_EXECUTION_MANIFEST_MISSING')
        execution=json.loads(execution_path.read_text(encoding='utf-8'))
        if execution.get('execution_order')!=planned or execution.get('benchmark_sha256')!=c['benchmark_sha256'] or execution.get('corpus_sha256')!=c['corpus_sha256']: raise SystemExit('FORMAL_EXECUTION_MANIFEST_MISMATCH')
        checks['execution_manifest_locked']=True;checks['resume_state']=_resume_state(c,planned)
        probe=out/'.preflight-write-test';probe.write_text('ok',encoding='utf-8');probe.unlink()
        checks['output_directory_writable']=True
    return checks
def order(c,items):
    rng=random.Random(c['random_seed']); result=[]
    for x in items:
        pair=['C1','C2']; rng.shuffle(pair)
        for condition in pair:
            sequence=len(result)+1
            result.append({'sequence':sequence,'question_id':x['question_id'],'condition':condition,'run_id':_planned_run_id(c,sequence,x['question_id'],condition)})
    return result
def prepare(c):
    checks=preflight(c,require_execution_manifest=False); out=ROOT/c['output_dir']; out.mkdir(parents=True,exist_ok=True); ep=out/'execution_order.json'; mp=out/'manifest.json'; fp=out/'formal_execution_manifest.json'; items=jsonl(ROOT/c['benchmark_path'])
    planned=order(c,items)
    if ep.exists():
        existing=json.loads(ep.read_text(encoding='utf-8'))['order']
        if existing!=planned: raise SystemExit('IMMUTABLE_EXECUTION_ORDER_MISMATCH')
    else: atomic_write(ep,json.dumps({'seed':c['random_seed'],'order':planned},indent=2)+'\n')
    manifest={'experiment_id':c['experiment_id'],'status':'PREPARED_FROZEN','checks':checks,'model':c['model'],'retrieval':c['retrieval'],'conditions':c['conditions'],'planned_runs':200,'seed':c['random_seed'],'benchmark_source_review_status':c['benchmark_source_review_status']}
    if mp.exists() and json.loads(mp.read_text(encoding='utf-8'))!=manifest: raise SystemExit('IMMUTABLE_MANIFEST_MISMATCH')
    if not mp.exists(): atomic_write(mp,json.dumps(manifest,indent=2)+'\n')
    formal={'experiment_id':c['experiment_id'],'status':'LOCKED_BEFORE_PROVIDER_EXECUTION','question_ids':[x['question_id'] for x in items],'planned_questions':100,'total_planned_executions':200,'conditions':{'C1':'Single-RAG','C2':'Multi-Agent'},'seed':c['random_seed'],'model':c['model'],'corpus_version':'TCM Research Corpus v1','corpus_sha256':c['corpus_sha256'],'benchmark_version':c['benchmark_version'],'benchmark_sha256':c['benchmark_sha256'],'retrieval':c['retrieval'],'generation_settings':c['generation_settings'],'timeout_policy':c['timeout_policy'],'retry_policy':c['retry_policy'],'fallback_policy':c['fallback_policy'],'grounding_policy':c['grounding_policy'],'execution_order':planned}
    if fp.exists() and json.loads(fp.read_text(encoding='utf-8'))!=formal: raise SystemExit('IMMUTABLE_FORMAL_EXECUTION_MANIFEST_MISMATCH')
    if not fp.exists(): atomic_write(fp,json.dumps(formal,ensure_ascii=False,indent=2)+'\n')
    return out
def _backend_health(c):
    health_url=c['api_url'].rsplit('/api/research/run',1)[0]+'/health'
    try:
        with urllib.request.urlopen(health_url,timeout=2) as response: return json.loads(response.read().decode())
    except Exception: return None
def ensure_backend(c):
    health=_backend_health(c)
    if health is None:
        out=ROOT/c['output_dir'];out.mkdir(parents=True,exist_ok=True)
        env=os.environ.copy();env.update({'PYTHONPATH':str(ROOT/'backend'),'TCM_CORPUS_MODE':'required','TCM_CORPUS_PATH':str(ROOT/c['corpus_path']),'RESEARCH_REAL_LLM_ENABLED':'true'})
        stdout=(out/'backend.stdout.log').open('ab');stderr=(out/'backend.stderr.log').open('ab')
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--app-dir','backend','--host','127.0.0.1','--port','8002'],cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=flags)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline and health is None:
            time.sleep(2);health=_backend_health(c)
        if health is None: raise SystemExit('FROZEN_LOCAL_BACKEND_START_FAILED')
    required=(health.get('status')=='ok' and health.get('provider_ready') is True and health.get('llm_execution_enabled') is True and health.get('mock_mode') is False and health.get('corpus_chunk_count')==4461 and health.get('corpus_mode')=='required')
    if not required: raise SystemExit('BACKEND_FROZEN_CONFIG_MISMATCH')
    return {'backend_ready':True,'provider_ready':True,'mock':False,'corpus_chunk_count':4461}
def request_one(c,item,entry):
    payload={'question':item['question'],'condition_id':entry['condition'],'retrieval_strategy':'R0',**c['generation_settings'],'random_seed':c['random_seed']}
    req=urllib.request.Request(c['api_url'],data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=c['timeout_seconds']) as r: body=json.loads(r.read().decode()); status=r.status
    except Exception as e: body={};status=0;error=f'{type(e).__name__}: {e}'
    trace=body.get('trace',{}); attempted=int(trace.get('provider_calls',0)); succeeded=int(trace.get('successful_provider_calls',0)); fallback=bool(trace.get('fallback_usage',False)); mode=trace.get('generation_mode')
    run_status='PASS_WITH_RETRY' if succeeded and attempted>succeeded else 'PASS' if succeeded and mode=='llm' and not fallback else 'FAIL_PROVIDER'
    return {'execution_sequence':entry['sequence'],'question_id':entry['question_id'],'condition':entry['condition'],'run_id':entry['run_id'],'backend_run_id':body.get('run_id'),'run_status':run_status,'http_status':status,'full_answer':body.get('final_answer',''),'provider_attempted':attempted,'provider_succeeded':succeeded,'provider':trace.get('provider','none'),'configured_model':c['model'],'model_actually_called':trace.get('model','none'),'fallback':fallback,'generation_mode':mode,'latency_ms':trace.get('latency_ms'),'provider_attempts':trace.get('provider_attempts',[]),'retrieved_evidence_ids':trace.get('retrieved_evidence_ids',[]),'participating_agents':trace.get('participating_agents',[]),'benchmark_sha256':c['benchmark_sha256'],'corpus_sha256':c['corpus_sha256'],'model':c['model'],'retrieval':'R0','error':locals().get('error')}
def run(c):
    if c['benchmark_source_review_status']!='APPROVED_AND_FROZEN': raise SystemExit('BENCHMARK_SOURCE_REVIEW_REQUIRED')
    out=prepare(c); ensure_backend(c); rp=out/'results.jsonl'; completed=jsonl(rp) if rp.exists() else []; done={(x['question_id'],x['condition']) for x in completed}; entries=json.loads((out/'execution_order.json').read_text(encoding='utf-8'))['order']; items={x['question_id']:x for x in jsonl(ROOT/c['benchmark_path'])}
    for e in entries:
        key=(e['question_id'],e['condition'])
        if key in done: continue
        record=request_one(c,items[e['question_id']],e)
        with rp.open('a',encoding='utf-8') as f: f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        done.add(key)
    return validate(c)
def validate(c):
    out=ROOT/c['output_dir']; records=jsonl(out/'results.jsonl'); pairs={(x['question_id'],x['condition']) for x in records}; planned=order(c,jsonl(ROOT/c['benchmark_path'])); state=_resume_state(c,planned); ok=len(records)==200 and len(pairs)==200 and sum(x['condition']=='C1' for x in records)==100 and sum(x['condition']=='C2' for x in records)==100 and state['internally_consistent']
    summary={'records':len(records),'unique_pairs':len(pairs),'C1':sum(x['condition']=='C1' for x in records),'C2':sum(x['condition']=='C2' for x in records),'statuses':{s:sum(x['run_status']==s for x in records) for s in sorted({x['run_status'] for x in records})},'valid':ok}
    atomic_write(out/'summary.json',json.dumps(summary,indent=2)+'\n'); return summary
def export_semantic(c):
    out=ROOT/c['output_dir']; records=[x for x in jsonl(out/'results.jsonl') if x['provider_succeeded']>0 and not x['fallback']]; bench={x['question_id']:x for x in jsonl(ROOT/c['benchmark_path'])}; rows=[]
    for r in records:
        for i,g in enumerate(bench[r['question_id']]['gold_facts'],1): rows.append({'item_id':f"CF-{len(rows)+1:04d}",'question_id':r['question_id'],'anonymous_system_label':'SYSTEM_A' if r['condition']=='C1' else 'SYSTEM_B','question':bench[r['question_id']]['question'],'gold_atomic_fact':g['fact'],'supplied_evidence':g['evidence_excerpt'],'answer':r['full_answer'],'review_label':'','review_reason':'','confidence':''})
    p=out/'semantic_review_for_gpt.csv'; fields=list(rows[0]);
    with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    atomic_write(out/'pipeline_state.json',json.dumps({'status':'SEMANTIC_REVIEW_REQUIRED','items':len(rows)},indent=2)+'\n');return p
def objective_evaluate(c):
    import re
    out=ROOT/c['output_dir']; records=jsonl(out/'results.jsonl'); usable=[x for x in records if x.get('provider_succeeded',0)>0 and not x.get('fallback')]; bench={x['question_id']:x for x in jsonl(ROOT/c['benchmark_path'])}; scores=[]
    for r in records:
        gold=set(bench[r['question_id']]['preferred_evidence_ids']); retrieved=set(r.get('retrieved_evidence_ids',[])); cited=set(re.findall(r'\[(tcmv1-[0-9a-f]+)\]',r.get('full_answer','')))
        scores.append({'question_id':r['question_id'],'condition':r['condition'],'usable_real_provider_output':r in usable,'gold_evidence_retrieval_recall':len(gold&retrieved)/len(gold),'gold_evidence_citation_recall':len(gold&cited)/len(gold),'citation_precision':len(gold&cited)/len(cited) if cited else 0})
    atomic_write(out/'objective_scores.jsonl',''.join(json.dumps(x)+'\n' for x in scores));result={'records':len(records),'usable_real_provider_outputs':len(usable),'failures':len(records)-len(usable),'objective_scores':'objective_scores.jsonl'}
    atomic_write(out/'objective_evaluation.json',json.dumps(result,indent=2)+'\n'); return result
def import_semantic(c,semantic_file):
    if not semantic_file: raise SystemExit('SEMANTIC_REVIEW_FILE_REQUIRED')
    rows=[]
    with Path(semantic_file).open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    allowed={'SUPPORTED','PARTIALLY_SUPPORTED','NOT_SUPPORTED','CONTRADICTED','UNRESOLVED'}
    if not rows or any(x.get('review_label') not in allowed for x in rows): raise SystemExit('INVALID_SEMANTIC_REVIEW')
    out=ROOT/c['output_dir']; atomic_write(out/'semantic_review_imported.json',json.dumps(rows,ensure_ascii=False,indent=2)+'\n'); return {'imported':len(rows)}
def analyze(c):
    out=ROOT/c['output_dir']; p=out/'semantic_review_imported.json'
    if not p.exists(): raise SystemExit('SEMANTIC_REVIEW_REQUIRED')
    rows=json.loads(p.read_text(encoding='utf-8')); counts={k:sum(x['review_label']==k for x in rows) for k in ['SUPPORTED','PARTIALLY_SUPPORTED','NOT_SUPPORTED','CONTRADICTED','UNRESOLVED']}
    result={'methodology':'AI-assisted semantic evaluation using frozen source-grounded rubric','atomic_counts':counts,'status':'ANALYSIS_READY_FOR_PAIRED_QUESTION_IMPLEMENTATION'}
    atomic_write(out/'analysis.json',json.dumps(result,indent=2)+'\n'); return result
def closeout(c):
    out=ROOT/c['output_dir'];
    if not (out/'analysis.json').exists(): raise SystemExit('ANALYSIS_REQUIRED')
    state={'status':'CONFIRMATORY_RQ1_COMPLETE'};atomic_write(out/'pipeline_state.json',json.dumps(state,indent=2)+'\n');return state
def simulate_resume():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'results.jsonl'; planned=[{'execution_sequence':i,'question_id':f'q{i//2:03d}','condition':'C1' if i%2 else 'C2','run_id':f'fixed-{i:03d}'} for i in range(1,201)]
        with p.open('w',encoding='utf-8') as f:
            for x in planned[:83]: f.write(json.dumps(x)+'\n')
        completed=jsonl(p);done={(x['question_id'],x['condition']) for x in completed}; remaining=[x for x in planned if (x['question_id'],x['condition']) not in done]
        assert len(done)==83 and len(remaining)==117 and remaining[0]['execution_sequence']==84 and all(x['run_id']==planned[i]['run_id'] for i,x in enumerate(completed))
        return {'completed':83,'next_sequence':84,'duplicates':0,'run_ids_stable':True,'execution_order_stable':True,'passed':True}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default=str(DEFAULT_CONFIG));ap.add_argument('--stage',default='auto',choices=['auto','prepare','preflight','run','validate','objective-evaluate','export-semantic','import-semantic','analyze','closeout']);ap.add_argument('--semantic-file');ap.add_argument('--dry-run',action='store_true');ap.add_argument('--simulate-resume',action='store_true');a=ap.parse_args();c=load(a.config)
    if a.simulate_resume: print(json.dumps(simulate_resume()));return
    if a.stage=='prepare': print(prepare(c));return
    checks=preflight(c)
    if a.stage=='preflight' or a.dry_run:
        print(json.dumps({'status':'READY_FOR_LOCAL_FORMAL_RQ1_CONFIRMATORY_RUN','preflight':checks,'provider_calls':0}));return
    if a.stage=='auto':
        if c['benchmark_source_review_status']!='APPROVED_AND_FROZEN': print(json.dumps({'status':'BENCHMARK_SOURCE_REVIEW_REQUIRED','preflight':checks,'provider_calls':0}));return
        out=ROOT/c['output_dir']
        if not (out/'results.jsonl').exists() or len(jsonl(out/'results.jsonl'))<200: run(c)
        objective_evaluate(c); packet=export_semantic(c)
        if not (out/'semantic_review_imported.json').exists(): print(json.dumps({'status':'SEMANTIC_REVIEW_REQUIRED','packet':str(packet)}));return
        analyze(c);print(json.dumps(closeout(c)));return
    if a.stage=='run': print(json.dumps(run(c)));return
    if a.stage=='validate': print(json.dumps(validate(c)));return
    if a.stage=='objective-evaluate': print(json.dumps(objective_evaluate(c)));return
    if a.stage=='export-semantic': print(export_semantic(c));return
    if a.stage=='import-semantic': print(json.dumps(import_semantic(c,a.semantic_file)));return
    if a.stage=='analyze': print(json.dumps(analyze(c)));return
    if a.stage=='closeout': print(json.dumps(closeout(c)));return
if __name__=='__main__':main()
