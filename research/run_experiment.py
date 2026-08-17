from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from evaluation.human import write_template
from evaluation.research_metrics import result_metrics
from evaluation.statistics import summarize
from orchestration import ResearchWorkbench
from schemas.research import ConditionId, DatasetItem, ResearchRequest, RetrievalStrategy
from tcm.language import detect_language


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("YAML config requires PyYAML, or use JSON syntax in the config file.") from exc
        return yaml.safe_load(text)


def load_dataset(path: Path) -> list[DatasetItem]:
    if path.suffix.casefold() == ".jsonl":
        return [DatasetItem.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DatasetItem.model_validate(item) for item in data]


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


async def execute(config: dict, *, no_llm: bool, output: Path, resume: bool, question: str | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / "raw_results.jsonl"
    completed: set[tuple[str, str, int]] = set()
    if resume and raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            completed.add((item["question_id"], item["condition_id"], item["repeat"]))
    dataset = [DatasetItem(
        question_id="ad-hoc-001",
        question=question,
        language=detect_language(question),
        category="ad_hoc",
        difficulty="medium",
        reference_notes="Ad-hoc CLI question; no gold labels.",
        expert_review_status="unlabelled_ad_hoc",
    )] if question else load_dataset(PROJECT_ROOT / config["dataset"])
    conditions = [ConditionId(item) for item in config.get("conditions", [config.get("condition", "C1")])]
    retrieval_modes = [RetrievalStrategy(item) for item in config.get("retrieval_modes", [config.get("retrieval_mode", "R2")])]
    repeats = int(config.get("repeat_count", 1))
    semaphore = asyncio.Semaphore(int(config.get("max_parallel_calls", 4)))
    workbench = ResearchWorkbench(force_mock=no_llm)

    async def one(item: DatasetItem, condition: ConditionId, retrieval: RetrievalStrategy, repeat: int):
        key = (item.question_id, condition.value, repeat)
        if key in completed:
            return None
        async with semaphore:
            result = await workbench.run(ResearchRequest(
                question=item.question,
                condition_id=condition,
                retrieval_strategy=retrieval,
                active_agents=config.get("active_agents", []),
                active_judges=config.get("judges", []),
                top_k=int(config.get("top_k_evidence", 4)),
                debate_rounds=int(config.get("debate_rounds", 1)),
                iterative_retrieval=bool(config.get("iterative_retrieval", False)),
                random_seed=int(config.get("seed", 20260815)) + repeat,
            ))
            metrics = result_metrics(result, gold_evidence_ids=item.gold_evidence_ids, required_concepts=item.required_concepts)
            return {"question_id": item.question_id, "repeat": repeat, "retrieval_mode": retrieval.value, "result": result, "metrics": metrics}

    tasks = [one(item, condition, retrieval, repeat) for item in dataset for condition in conditions for retrieval in retrieval_modes for repeat in range(repeats)]
    records = [record for record in await asyncio.gather(*tasks) if record is not None]
    mode = "a" if resume and raw_path.exists() else "w"
    with raw_path.open(mode, encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps({
                "question_id": record["question_id"], "condition_id": record["result"].condition_id.value,
                "repeat": record["repeat"], "retrieval_mode": record["retrieval_mode"],
                "result": record["result"].model_dump(mode="json"), "metrics": record["metrics"],
            }, ensure_ascii=False) + "\n")
    all_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    per_question = [{"question_id": row["question_id"], "condition_id": row["condition_id"], "repeat": row["repeat"], "retrieval_mode": row["retrieval_mode"], **row["metrics"]} for row in all_rows]
    _write_csv(output / "per_question.csv", per_question)
    _write_csv(output / "metrics.csv", per_question)
    grouped: dict[str, list[dict]] = {}
    for row in per_question:
        grouped.setdefault(row["condition_id"], []).append(row)
    summaries = []
    for condition, rows in grouped.items():
        summary: dict[str, object] = {"condition_id": condition, "runs": len(rows)}
        for metric in ("citation_coverage", "unsupported_claim_rate", "completeness", "confidence", "latency_ms", "provider_calls"):
            values = [float(row[metric]) for row in rows if row.get(metric) is not None]
            stats = summarize(values)
            summary[f"{metric}_mean"] = stats["mean"]
            summary[f"{metric}_median"] = stats["median"]
            summary[f"{metric}_sd"] = stats["standard_deviation"]
        summaries.append(summary)
    _write_csv(output / "condition_summary.csv", summaries)
    _write_csv(output / "failures.csv", [])
    write_template(output / "human_review_template.csv", [{"run_id": row["result"]["run_id"], "question_id": row["question_id"]} for row in all_rows])
    manifest = {
        "schema_version": "1.0.0", "experiment_id": config.get("experiment_id", output.name),
        "created_at": datetime.now(timezone.utc).isoformat(), "config": config,
        "runtime_model": {
            "provider": workbench.providers.llm.name,
            "model": workbench.providers.llm.model,
            "enable_thinking": getattr(workbench.providers.llm, "enable_thinking", None),
        },
        "synthetic_dataset_warning": "Seed labels are provisional researcher-created data, not expert ground truth.",
        "run_count": len(all_rows), "no_llm": no_llm,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        f"# Experiment report: {manifest['experiment_id']}", "", f"Runs: {len(all_rows)}", "",
        "This automated report is descriptive. It does not establish clinical validity, statistical significance, user trust, or judge ground-truth accuracy.", "",
        "## Condition summaries", "",
        *[f"- {row['condition_id']}: {row['runs']} runs; citation coverage mean={row.get('citation_coverage_mean')}" for row in summaries],
    ]
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reproducible TCM multi-agent RAG experiments.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--question")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.dry_run:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0
    run_id = f"exp-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    output = args.output or PROJECT_ROOT / "research" / "results" / run_id
    manifest = asyncio.run(execute(config, no_llm=args.no_llm, output=output, resume=args.resume, question=args.question))
    print(json.dumps({"status": "complete", "output": str(output), "runs": manifest["run_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
