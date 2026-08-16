from __future__ import annotations

import argparse
import json
from pathlib import Path

from corpus.v1_models import ResearchChunk
from ingestion.contamination import check_contamination
from ingestion.tcm_v1 import load_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check corpus/benchmark exact, high-similarity, and source-ID overlap.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "research/corpus/configs/tcm_v1.yaml")
    parser.add_argument("--benchmark", type=Path, action="append", default=[])
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    chunks_path = PROJECT_ROOT / config["outputs"]["chunks"]
    chunks = [ResearchChunk.model_validate_json(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    benchmark_paths = args.benchmark or [
        *sorted((PROJECT_ROOT / "research/datasets").glob("*.json*")),
        *sorted((PROJECT_ROOT / "research/benchmarks/external").rglob("*.json*")),
    ]
    report = check_contamination(chunks, benchmark_paths)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["exact_text_overlap_count"] or report["source_record_leakage_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
