from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "study_config.json"
sys.path.insert(0,str(ROOT/"backend"))
if "TCM_CORPUS_MODE" not in os.environ:
    os.environ["TCM_CORPUS_MODE"] = "v1"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def load_config() -> dict[str, Any]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))

def validate_protected() -> None:
    guard=json.loads((HERE/"protected_artifacts.json").read_text(encoding="utf-8")); inherited=ROOT/guard["inherited_guard"]["path"]
    if sha(inherited)!=guard["inherited_guard"]["sha256"]: raise RuntimeError("inherited protected-artifact guard changed")
    base=json.loads(inherited.read_text(encoding="utf-8"))["artifacts"]
    for item in [*base,*guard["additional_artifacts"]]:
        path=ROOT/item["path"]
        if not path.exists() or sha(path)!=item["sha256"]: raise RuntimeError(f"protected artifact changed: {item['path']}")

def build_evidence_manifest() -> dict[str, Any]:
    c=load_config(); benchmark=jsonl(ROOT/c["benchmark"]["path"]); source=ROOT/c["evidence"]["source_results"]
    if sha(ROOT/c["benchmark"]["path"])!=c["benchmark"]["sha256"] or sha(ROOT/c["corpus"]["path"])!=c["corpus"]["sha256"] or sha(source)!=c["evidence"]["source_results_sha256"]: raise RuntimeError("frozen input hash mismatch")
    rows=jsonl(source); by={}
    for row in rows: by.setdefault(row["question_id"],{})[row["condition"]]=row["retrieved_evidence_ids"]
    corpus={x["chunk_id"]:x for x in jsonl(ROOT/c["corpus"]["path"])}; items=[]; recovered=[]
    missing=[q for q in benchmark if not by.get(q["question_id"],{}).get("C4")]
    recovered_ids={}
    if missing:
        from retrieval import RetrievalEngine
        from schemas.research import RetrievalStrategy
        engine=RetrievalEngine()
        async def recover():
            for q in missing:
                topics=["herbal","syndrome"] if "+" in q["domain"] else ["herbal"] if q["domain"]=="herbal_medicine" else ["syndrome"]
                got=await engine.search(q["question"],strategy=RetrievalStrategy.R0,top_k=4,topics=topics)
                recovered_ids[q["question_id"]]=[x.chunk_id for x in got]
        asyncio.run(recover())
    for q in benchmark:
        pair=by.get(q["question_id"],{})
        if pair.get("C2") or pair.get("C4"):
            if set(pair)!={"C2","C4"} or pair["C2"]!=pair["C4"] or len(pair["C4"])!=4: raise RuntimeError(f"A2 evidence identity mismatch: {q['question_id']}")
            ids=pair["C4"]; source="exact_A2_C2_C4_identity"
        else:
            ids=recovered_ids[q["question_id"]]; source="deterministic_R0_recovery_for_A2_pre_retrieval_abstention"; recovered.append(q["question_id"])
        if len(ids)!=4 or any(i not in corpus for i in ids): raise RuntimeError(f"invalid frozen evidence: {q['question_id']}")
        items.append({"question_id":q["question_id"],"retrieval":"R0","evidence_origin":source,"ordered_chunk_ids":ids,"source_ids":[corpus[i]["source_id"] for i in ids],"evidence":[{"evidence_id":i,"text":corpus[i]["text"]} for i in ids]})
    return {"status":"FROZEN_FOR_A3_GENERATION","benchmark_sha256":c["benchmark"]["sha256"],"corpus_sha256":c["corpus"]["sha256"],"source_A2_results_sha256":c["evidence"]["source_results_sha256"],"retrieval":"R0","top_k":4,"questions":len(items),"exact_A2_evidence_questions":len(items)-len(recovered),"offline_R0_recovered_questions":recovered,"items":items}

def write_evidence_manifest() -> Path:
    data=build_evidence_manifest(); path=HERE/"frozen_evidence_manifest.json"; path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); return path

def role_models(config: dict[str, Any], condition: str, rotation_id: int) -> list[dict[str,str]]:
    roles=config["agent_roles"]; models=config["conditions"][condition]["agent_models"]; families=config["conditions"][condition]["model_families"]
    shift=0 if condition=="M1" else rotation_id-1
    return [{"role":role,"model":models[(i+shift)%3],"family":families[(i+shift)%3]} for i,role in enumerate(roles)]

def write_role_rotation_manifest() -> Path:
    c=load_config(); bench=jsonl(ROOT/c["benchmark"]["path"]); assignments=[]
    for i,q in enumerate(bench):
        rid=i%3+1; assignments.append({"question_id":q["question_id"],"benchmark_index":i+1,"rotation_id":rid,"M2_assignment":role_models(c,"M2",rid)})
    counts={str(r):sum(x["rotation_id"]==r for x in assignments) for r in (1,2,3)}
    if counts!={"1":34,"2":33,"3":33}: raise RuntimeError("rotation distribution invariant")
    path=HERE/"role_rotation_manifest.json"; path.write_text(json.dumps({"status":"FROZEN_BEFORE_FORMAL_EXECUTION","algorithm":"benchmark file order; rotation_id = zero_based_index mod 3 + 1","distribution":counts,"assignments":assignments},indent=2)+"\n",encoding="utf-8"); return path

def execution_plan() -> list[dict[str, Any]]:
    c=load_config(); bench=jsonl(ROOT/c["benchmark"]["path"]); ids=[x["question_id"] for x in bench]; random.Random(c["seed"]).shuffle(ids); plan=[]
    rotations=json.loads((HERE/"role_rotation_manifest.json").read_text(encoding="utf-8")); rotation_by_id={x["question_id"]:x["rotation_id"] for x in rotations["assignments"]}
    for i,qid in enumerate(ids):
        conditions=("M1","M2") if i%2==0 else ("M2","M1")
        for cond in conditions:
            rid=rotation_by_id[qid]; assignment=role_models(c,cond,rid); identity={"question_id":qid,"condition":cond,"stage":"A3_formal","benchmark_sha256":c["benchmark"]["sha256"],"evidence_manifest_sha256":sha(HERE/"frozen_evidence_manifest.json") if (HERE/"frozen_evidence_manifest.json").exists() else canonical_hash(build_evidence_manifest()),"rotation_id":rid,"model_assignment":assignment,"fixed_consensus_model":c["fixed_consensus_model"]}
            plan.append({"sequence":len(plan)+1,"question_id":qid,"condition":cond,"rotation_id":rid,"agent_assignment":assignment,"consensus_model":c["fixed_consensus_model"],"resume_identity":canonical_hash(identity)})
    if len(plan)!=200 or len({x["resume_identity"] for x in plan})!=200: raise RuntimeError("paired plan identity invariant")
    return plan

def write_design_manifests() -> None:
    from prompt_templates import canonical_prompt_bundle
    plan=execution_plan(); evidence=HERE/"frozen_evidence_manifest.json"
    (HERE/"execution_plan.json").write_text(json.dumps({"status":"PLANNED_NOT_EXECUTED","seed":load_config()["seed"],"order":plan},indent=2)+"\n",encoding="utf-8")
    c=load_config(); manifest={"status":c["status"],"study_config_sha256":sha(CONFIG),"benchmark_sha256":c["benchmark"]["sha256"],"corpus_sha256":c["corpus"]["sha256"],"evidence_manifest_sha256":sha(evidence),"role_rotation_manifest_sha256":sha(HERE/"role_rotation_manifest.json"),"execution_plan_sha256":sha(HERE/"execution_plan.json"),"prompt_bundle_sha256":hashlib.sha256(canonical_prompt_bundle().encode()).hexdigest(),"planned_executions":200,"nominal_formal_provider_calls":2000,"recorded_nonformal_smoke_calls":c["design_phase_provider_calls"],"formal_provider_calls":0}
    (HERE/"preregistration_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")

def validate_no_gold_leakage(payload: Any) -> None:
    text=json.dumps(payload,ensure_ascii=False).casefold()
    forbidden=("gold_facts","gold_atomic_fact","review_label","expected winner","m1 homogeneous","m2 heterogeneous")
    if any(x in text for x in forbidden): raise ValueError("Gold/condition leakage detected")

def formal_execute(*, authorized: bool = False, resume: bool = False) -> None:
    if not authorized and os.getenv("A3_FORMAL_EXECUTION_AUTHORIZED") != "1":
        raise RuntimeError("FORMAL_EXECUTION_LOCKED_PENDING_SEPARATE_USER_AUTHORIZATION")
    from formal_runner import run_formal_experiment
    run_formal_experiment(resume=resume)

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--prepare-evidence",action="store_true"); p.add_argument("--refresh-design-manifests",action="store_true"); p.add_argument("--prepare-clean-restart",action="store_true"); p.add_argument("--plan",action="store_true"); p.add_argument("--execute",action="store_true"); p.add_argument("--resume",action="store_true"); p.add_argument("--authorized",action="store_true"); a=p.parse_args(); validate_protected()
    if a.resume and not a.execute: raise RuntimeError("--resume requires --execute")
    if a.execute: formal_execute(authorized=a.authorized,resume=a.resume)
    if a.prepare_clean_restart:
        from formal_runner import prepare_clean_restart
        prepare_clean_restart()
    if a.prepare_evidence: write_evidence_manifest(); write_role_rotation_manifest(); write_design_manifests()
    elif a.refresh_design_manifests: write_design_manifests()
    c=load_config(); plan=execution_plan(); print(json.dumps({"status":c["status"],"planned_executions":len(plan),"nominal_formal_provider_calls":len(plan)*10,"provider_calls_this_command":0,"recorded_nonformal_smoke_calls":c["design_phase_provider_calls"],"formal_provider_calls":0,"unique_resume_identities":len({x['resume_identity'] for x in plan})},indent=2))

if __name__=="__main__": main()
