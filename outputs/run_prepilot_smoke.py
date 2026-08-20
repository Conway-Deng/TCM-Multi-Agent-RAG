import csv, json, re, statistics, time, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research' / 'smoke_tests' / 'prepilot-20260818'; OUT.mkdir(parents=True, exist_ok=True)
rows = [json.loads(x) for x in (ROOT / 'research/corpus/tcm_v1/chunks.jsonl').read_text(encoding='utf8').splitlines()]
by_name = {x['entity_name'].lower(): x for x in rows}
questions = [
 ('smoke-01','What are the traditional TCM properties, meridian associations, and traditional uses of Red Ginseng (Hongshen)?','herbal_medicine',['Red Ginseng'],False),
 ('smoke-02','What are the traditional TCM properties, meridian associations, and traditional class of flower bud of lobed kudzuvine (Gehua)?','herbal_medicine',['flower bud of lobed kudzuvine'],False),
 ('smoke-03','What source-recorded functions and indications are listed for Common Javatea?','herbal_medicine',['Common Javatea'],False),
 ('smoke-04','What source-recorded functions and indications are listed for Evergreen Mucuna?','herbal_medicine',['Evergreen Mucuna'],False),
 ('smoke-05','What traditional properties, meridians, and class are recorded for Chinese Waxgourd Peel?','herbal_medicine',['Chinese Waxgourd Peel'],False),
 ('smoke-06','What source-recorded function and indication are listed for Polyporus grifolia, Umbellate pore-fungus?','herbal_medicine',['Polyporus grifolia, Umbellate pore-fungus'],False),
 ('smoke-07','What does the TCM Research Corpus record about deficiency of the kidney-yang?','syndrome_differentiation',['deficiency of the kidney-yang'],False),
 ('smoke-08','What does the TCM Research Corpus record about liver yang?','syndrome_differentiation',['liver yang'],False),
 ('smoke-09','What does the TCM Research Corpus record about phlegm fire?','syndrome_differentiation',['phlegm fire'],False),
 ('smoke-10','How are Red Ginseng and deficiency of the kidney-yang represented in the TCM corpus, and what evidence is recorded for each?','herbal_medicine + syndrome_differentiation',['Red Ginseng','deficiency of the kidney-yang'],True),
]
manifest=[]
for sid,q,domain,names,multi in questions:
    expected=[by_name[n.lower()] for n in names]
    manifest.append({'smoke_id':sid,'question':q,'expected_main_domain':domain,'expected_entities':names,'expected_chunk_ids':[x['chunk_id'] for x in expected],'expected_source_names':[x['source_name'] for x in expected],'multiple_specialists_expected':multi})
(OUT/'manifest.json').write_text(json.dumps({'purpose':'temporary pre-pilot stability smoke test','corpus':'TCM Research Corpus v1','chunk_count':4461,'questions':manifest},indent=2),encoding='utf8')
agents=['syndrome','herbal','acupuncture_meridian','constitution','dietary_therapy','lifestyle_yangsheng']; results=[]
for item in manifest:
  for condition in ('C1','C2'):
    payload={'question':item['question'],'condition_id':condition,'retrieval_strategy':'R0','active_agents':agents,'active_judges':['evidence','hallucination','safety','conflict','confidence','provenance'],'top_k':4,'debate_rounds':1,'include_trace':True}; started=time.perf_counter()
    rec={'smoke_id':item['smoke_id'],'question':item['question'],'expected_domain':item['expected_main_domain'],'condition':condition,'retrieval':'R0','expected_chunk_ids':item['expected_chunk_ids'],'expected_multiple_specialists':item['multiple_specialists_expected']}
    try:
      req=urllib.request.Request('http://127.0.0.1:8000/api/research/run',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Accept':'application/json'},method='POST')
      try:
        response=urllib.request.urlopen(req,timeout=180); status=response.status; body=response.read().decode('utf8')
      except urllib.error.HTTPError as exc:
        status=exc.code; body=exc.read().decode('utf8','replace')
      elapsed=round((time.perf_counter()-started)*1000); rec.update({'http_status':status,'client_latency_ms':elapsed})
      if status != 200: rec.update({'run_status':'FAIL','failure_reason':f'HTTP {status}: {body[:300]}','output_quality_pass':False}); results.append(rec); continue
      data=json.loads(body); trace=data.get('trace') or {}; answer=str(data.get('final_answer') or ''); evidence=data.get('retrieval') or []; ids=[str(x.get('chunk_id','')) for x in evidence]; citations=set(re.findall(r'\[(tcmv1-[0-9a-f]+)\]',answer)); valid=all(re.fullmatch(r'tcmv1-[0-9a-f]+',x or '') for x in ids); cite_ok=citations.issubset(set(ids)) and bool(citations); repeat=bool(re.search(r'\b(\w+)(?:\s+\1){3,}\b',answer,re.I)) or bool(re.search(r'(.{8,})\1{2,}',answer)); malformed='\ufffd' in answer or '�' in answer or any(ord(c)<9 for c in answer); quality=bool(answer.strip()) and len(answer.split())<=400 and not repeat and not malformed and valid and cite_ok
      attempted=int(trace.get('provider_calls') or 0); succeeded=int(trace.get('successful_provider_calls') or 0); fallback=bool(trace.get('fallback_usage')); model=trace.get('model') or 'none'; generation=trace.get('generation_mode') or data.get('generation_mode'); provider=trace.get('provider') or trace.get('provider_configured'); failures=[]
      if trace.get('corpus_name')!='TCM Research Corpus v1' or int(trace.get('corpus_chunk_count') or 0)!=4461: failures.append('corpus metadata')
      if attempted and model!='Qwen/Qwen3-8B': failures.append('actual model')
      if attempted and provider!='siliconflow': failures.append('provider')
      if attempted!=succeeded: failures.append('provider failure')
      if attempted and generation!='llm': failures.append('generation mode')
      if fallback: failures.append('fallback')
      if not quality: failures.append('output quality/citations')
      if not evidence: failures.append('no retrieved evidence')
      rec.update({'run_id':data.get('run_id'),'trace':trace,'answer':answer,'evidence_ids':ids,'citation_ids':sorted(citations),'model':model,'provider':provider,'provider_attempted':attempted,'provider_succeeded':succeeded,'generation_mode':generation,'fallback':fallback,'latency_ms':trace.get('latency_ms') or elapsed,'participating_agents':trace.get('participating_agents') or [],'abstaining_agents':trace.get('abstaining_agents') or [],'evidence_count':len(evidence),'output_quality_pass':quality,'run_status':'PASS' if not failures else 'FAIL','failure_reason':'; '.join(failures)})
    except Exception as exc: rec.update({'run_status':'FAIL','failure_reason':f'API exception: {type(exc).__name__}: {exc}','output_quality_pass':False})
    results.append(rec)
(OUT/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf8')
fields=['smoke_id','question','expected_domain','condition','retrieval','model','participating_agents','provider_attempted','provider_succeeded','generation_mode','fallback','latency_ms','evidence_count','output_quality_pass','run_status','failure_reason']
with (OUT/'summary.csv').open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); [w.writerow({k:';'.join(r[k]) if isinstance(r.get(k),list) else r.get(k,'') for k in fields}) for r in results]
summary={'total_runs':len(results),'passed_runs':sum(r.get('run_status')=='PASS' for r in results),'failed_runs':sum(r.get('run_status')!='PASS' for r in results),'fallback_runs':sum(bool(r.get('fallback')) for r in results),'provider_failures':sum('provider failure' in r.get('failure_reason','') for r in results),'corrupted_outputs':sum('output quality' in r.get('failure_reason','') for r in results)}
for c in ('C1','C2'):
  vals=[r['latency_ms'] for r in results if r.get('condition')==c and r.get('latency_ms')]; summary[c+'_mean_latency_ms']=round(statistics.mean(vals),1) if vals else None; summary[c+'_median_latency_ms']=round(statistics.median(vals),1) if vals else None
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8'); print(json.dumps(summary,indent=2))
