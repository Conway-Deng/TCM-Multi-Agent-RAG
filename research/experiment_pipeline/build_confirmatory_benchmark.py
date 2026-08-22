import csv, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CORPUS=ROOT/'research/corpus/tcm_v1/chunks.jsonl'
OUT=ROOT/'research/benchmarks/tcm_gold_rq1_confirmatory_v1'
EXPECTED_SHA='316eade86599c4d59a640020b59a3e153719c962fe20e4953ce36f8ddf8988c9'
STATUS='DRAFT_SOURCE_GROUNDED_CONFIRMATORY_V1'

def rows(path): return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x]
def norm(s): return ' '.join(str(s or '').lower().split())
def collect_banned():
    names={'red ginseng','hongshen','liver yang','gehua','flower bud of lobed kudzuvine'}
    for p in ROOT.glob('research/benchmarks/tcm_gold_v*/benchmark*.jsonl'):
        for x in rows(p):
            names.update(norm(v) for v in x.get('source_entity_names',[]))
    p=ROOT/'research/benchmarks/tcm_gold_v1_2/heldout_manifest_v1_2.json'
    if p.exists():
        data=json.loads(p.read_text(encoding='utf-8'))
        def walk(v):
            if isinstance(v,dict):
                for k,x in v.items():
                    if k in {'entities','source_entity_names'} and isinstance(x,list): names.update(norm(y) for y in x)
                    walk(x)
            elif isinstance(v,list):
                for x in v: walk(x)
        walk(data)
    return {x for x in names if x}

def evidence(c): return f"Source entity: {c['entity_name']}. Source: {c['source_name']}. {c['text']}"
def herb_item(c,qid,difficulty):
    f=c['structured_facts']; facts=[]
    if f.get('properties_english'):
        question=f"What traditional properties, meridians, and class are recorded for {c['entity_name']}?"
        for label,key in [('traditional properties','properties_english'),('meridians','meridians_english'),('traditional class','class_english')]:
            if f.get(key): facts.append({'fact':f"The source records {c['entity_name']} {label}: {f[key]}.",'preferred_evidence_ids':[c['chunk_id']],'acceptable_alternate_evidence_ids':[],'evidence_excerpt':evidence(c)})
    else:
        question=f"What source-recorded functions, indications, and used part are listed for {c['entity_name']}?"
        for label,key in [('function','function'),('indication','indication'),('used part','used_part')]:
            if f.get(key): facts.append({'fact':f"The source records the {label} of {c['entity_name']} as: {f[key]}.",'preferred_evidence_ids':[c['chunk_id']],'acceptable_alternate_evidence_ids':[],'evidence_excerpt':evidence(c)})
    return {'question_id':qid,'question':question,'domain':'herbal_medicine','difficulty':difficulty,'gold_facts':facts,'preferred_evidence_ids':[c['chunk_id']],'acceptable_alternate_evidence_ids':[],'expected_specialists':['herbal'],'unsupported_claim_constraints':[],'status':STATUS,'benchmark_role':'confirmatory_semantic_accuracy','source_entity_names':[c['entity_name']]}

def syndrome_item(c,qid,difficulty):
    definition=c['structured_facts']['definition_original']
    return {'question_id':qid,'question':f"What does TCM Research Corpus v1 record about {c['entity_name']}?",'domain':'syndrome_differentiation','difficulty':difficulty,'gold_facts':[{'fact':f"The source defines {c['entity_name']} as: {definition}",'preferred_evidence_ids':[c['chunk_id']],'acceptable_alternate_evidence_ids':[],'evidence_excerpt':evidence(c)}],'preferred_evidence_ids':[c['chunk_id']],'acceptable_alternate_evidence_ids':[],'expected_specialists':['syndrome'],'unsupported_claim_constraints':[],'status':STATUS,'benchmark_role':'confirmatory_semantic_accuracy','source_entity_names':[c['entity_name']]}

def multi_item(h,s,qid,difficulty):
    hf=herb_item(h,qid,difficulty)['gold_facts'][0]; sf=syndrome_item(s,qid,difficulty)['gold_facts'][0]
    return {'question_id':qid,'question':f"How are {h['entity_name']} and {s['entity_name']} represented separately in TCM Research Corpus v1, and what evidence is recorded for each?",'domain':'herbal_medicine + syndrome_differentiation','difficulty':difficulty,'gold_facts':[hf,sf],'preferred_evidence_ids':[h['chunk_id'],s['chunk_id']],'acceptable_alternate_evidence_ids':[],'expected_specialists':['syndrome','herbal'],'requested_targets':[{'entity_name':h['entity_name'],'category':'herbal_medicine','evidence_ids':[h['chunk_id']]},{'entity_name':s['entity_name'],'category':'syndrome_differentiation','evidence_ids':[s['chunk_id']]}],'relationship_gold_status':'not_established','unsupported_claim_constraints':[f"Do not infer a relationship between {h['entity_name']} and {s['entity_name']}; none is established by the supplied evidence."],'status':STATUS,'benchmark_role':'confirmatory_semantic_accuracy','source_entity_names':[h['entity_name'],s['entity_name']]}

def validate(items,corpus,banned):
    ids={c['chunk_id'] for c in corpus}; assert len(items)==100 and len({x['question'] for x in items})==100
    assert len({tuple(map(norm,x['source_entity_names'])) for x in items})==100
    assert {d:sum(x['domain']==d for x in items) for d in ['herbal_medicine','syndrome_differentiation','herbal_medicine + syndrome_differentiation']}=={'herbal_medicine':60,'syndrome_differentiation':25,'herbal_medicine + syndrome_differentiation':15}
    assert {d:sum(x['difficulty']==d for x in items) for d in ['easy','medium','hard']}=={'easy':40,'medium':40,'hard':20}
    for x in items:
        assert all(norm(e) not in banned for e in x['source_entity_names'])
        assert set(x['expected_specialists'])<= {'herbal','syndrome'}
        if '+' in x['domain']: assert len(x['requested_targets'])==2 and x['relationship_gold_status']=='not_established'
        for f in x['gold_facts']:
            assert f['fact'] and f['evidence_excerpt'] and f['preferred_evidence_ids'] and set(f['preferred_evidence_ids'])<=ids

def main():
    assert hashlib.sha256(CORPUS.read_bytes()).hexdigest()==EXPECTED_SHA
    corpus=rows(CORPUS); banned=collect_banned(); used=set()
    herbs=[c for c in corpus if c['category']=='herbal_medicine' and norm(c['entity_name']) not in banned and c['entity_name'] not in used and (c['structured_facts'].get('properties_english') or c['structured_facts'].get('function'))]
    synd=[c for c in corpus if c['category']=='syndrome_differentiation' and norm(c['entity_name']) not in banned and c['structured_facts'].get('definition_original')]
    herbs.sort(key=lambda c:c['chunk_id']); synd.sort(key=lambda c:c['chunk_id'])
    single_h=herbs[:60]; single_s=synd[:25]; multi_h=herbs[60:75]; multi_s=synd[25:40]
    difficulties=['easy']*25+['medium']*25+['hard']*10+['easy']*10+['medium']*10+['hard']*5+['easy']*5+['medium']*5+['hard']*5
    items=[]; n=1
    for c,d in zip(single_h,difficulties[:60]): items.append(herb_item(c,f'tcmc-v1-{n:03d}',d)); n+=1
    for c,d in zip(single_s,difficulties[60:85]): items.append(syndrome_item(c,f'tcmc-v1-{n:03d}',d)); n+=1
    for h,s,d in zip(multi_h,multi_s,difficulties[85:]): items.append(multi_item(h,s,f'tcmc-v1-{n:03d}',d)); n+=1
    validate(items,corpus,banned); OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'benchmark_confirmatory_v1.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in items)+'\n',encoding='utf-8')
    fields=['question_id','question','domain','difficulty','expected_specialists','source_entity_names','gold_fact_count','preferred_evidence_ids','status']
    with (OUT/'benchmark_confirmatory_v1.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();
        for x in items:w.writerow({**{k:x.get(k,'') for k in fields},'expected_specialists':'|'.join(x['expected_specialists']),'source_entity_names':'|'.join(x['source_entity_names']),'gold_fact_count':len(x['gold_facts']),'preferred_evidence_ids':'|'.join(x['preferred_evidence_ids'])})
    review=[]
    for x in items:
        for i,g in enumerate(x['gold_facts'],1):review.append({'question_id':x['question_id'],'question':x['question'],'domain':x['domain'],'difficulty':x['difficulty'],'canonical_source_entities':'|'.join(x['source_entity_names']),'gold_fact_index':i,'gold_atomic_fact':g['fact'],'preferred_evidence_id':'|'.join(g['preferred_evidence_ids']),'acceptable_alternate_evidence_ids':'|'.join(g['acceptable_alternate_evidence_ids']),'evidence_excerpt':g['evidence_excerpt'],'source_review_status':'','review_reason':'','confidence':''})
    rfields=list(review[0]);
    for name in ['review_sheet_confirmatory_v1.csv','external_source_review_for_gpt.csv']:
        with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=rfields);w.writeheader();w.writerows(review)
    with (OUT/'external_source_review_result_template.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['question_id','gold_fact_index','source_review_status','review_reason','confidence']);w.writerows([[r['question_id'],r['gold_fact_index'],'','',''] for r in review])
    manifest={'status':STATUS,'corpus_sha256':EXPECTED_SHA,'question_count':100,'atomic_gold_fact_count':len(review),'distributions':{'domain':{'herbal':60,'syndrome':25,'multi_target':15},'difficulty':{'easy':40,'medium':40,'hard':20}},'exclusions':sorted(banned),'leakage_checks':{'old_benchmark_entity_overlap':0,'development_entity_overlap':0,'duplicate_questions':0,'duplicate_targets':0,'invalid_evidence_ids':0},'source_review':'PENDING'}
    (OUT/'heldout_manifest_confirmatory_v1.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'coverage_report_confirmatory_v1.md').write_text(f"# Confirmatory benchmark coverage\n\nStatus: {STATUS}\n\n- Questions: 100\n- Atomic Gold facts: {len(review)}\n- Domains: herbal 60, syndrome 25, multi-target 15\n- Difficulty: easy 40, medium 40, hard 20\n- Leakage checks: passed\n- Corpus SHA-256: `{EXPECTED_SHA}`\n",encoding='utf-8')
    instructions='''# External source-grounded review instructions\n\nThe reviewer is not validating clinical TCM truth. Check only: **Does the supplied Corpus evidence directly support the proposed Gold fact?** Use only the supplied question, Gold fact, evidence IDs, and excerpt.\n\nAllowed statuses: APPROVE, REVISE, REMOVE, UNRESOLVED. Return the unchanged question_id and gold_fact_index, a short reason, and confidence HIGH, MEDIUM, or LOW. Do not use external medical knowledge.\n'''
    (OUT/'external_source_review_instructions.md').write_text(instructions,encoding='utf-8')
    md=instructions+'\n# Review items\n\n'+''.join(f"## {r['question_id']} / fact {r['gold_fact_index']}\n\n- Question: {r['question']}\n- Domain: {r['domain']}\n- Difficulty: {r['difficulty']}\n- Entities: {r['canonical_source_entities']}\n- Gold fact: {r['gold_atomic_fact']}\n- Preferred evidence: {r['preferred_evidence_id']}\n- Alternate evidence: {r['acceptable_alternate_evidence_ids'] or 'none'}\n\nEvidence excerpt:\n\n{r['evidence_excerpt']}\n\n---\n\n" for r in review)
    (OUT/'external_source_review_for_gpt.md').write_text(md,encoding='utf-8')
    (OUT/'README.md').write_text(f"# RQ1 confirmatory benchmark v1\n\nStatus: {STATUS}. This 100-question source-grounded draft is awaiting external source review. It is not frozen and must not be used for formal runs yet.\n",encoding='utf-8')
    print(json.dumps({'questions':100,'gold_facts':len(review),'status':STATUS}))
if __name__=='__main__':main()
