from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion.tcm_v1 import (
    build_manifest, deduplicate_and_flag, import_configured_sources, load_config, record_to_chunk, write_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build(config_path: Path) -> dict:
    config = load_config(config_path)
    imported, import_report = import_configured_sources(config, PROJECT_ROOT)
    if import_report["missing_inputs"]:
        instructions = "\n".join(
            f"- {item['source_id']}: {item['instruction']} Expected destination: {item['path']}"
            for item in import_report["missing_inputs"]
        )
        raise FileNotFoundError(
            "Required audited corpus inputs are missing. No partial corpus was built.\n" + instructions
        )
    records, dedup_report = deduplicate_and_flag(imported)
    records.sort(key=lambda item: (item.source_id, item.entity_type, item.source_record_id))
    chunks = [record_to_chunk(item) for item in records]
    chunks.sort(key=lambda item: item.chunk_id)

    normalized_path = PROJECT_ROOT / config["outputs"]["normalized_records"]
    chunks_path = PROJECT_ROOT / config["outputs"]["chunks"]
    manifest_path = PROJECT_ROOT / config["outputs"]["manifest"]
    dedup_path = PROJECT_ROOT / config["outputs"]["dedup_report"]
    write_jsonl(normalized_path, records)
    write_jsonl(chunks_path, chunks)
    manifest = build_manifest(config, PROJECT_ROOT, records, chunks, import_report, dedup_report)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # The full groups contain source-derived names and record identifiers. Keep
    # those details beside the gitignored normalized data; publish aggregates only.
    private_dedup_path = normalized_path.parent / "tcm_v1_deduplication_details.json"
    private_dedup_path.write_text(json.dumps(dedup_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public_dedup_report = {
        key: value for key, value in dedup_report.items()
        if key not in {"alias_groups", "conflict_groups", "exact_duplicate_records", "near_duplicate_groups"}
    }
    dedup_path.parent.mkdir(parents=True, exist_ok=True)
    dedup_path.write_text(json.dumps(public_dedup_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {"manifest": manifest, "import_report": import_report, "paths": {
        "normalized": str(normalized_path), "chunks": str(chunks_path), "manifest": str(manifest_path),
        "dedup": str(dedup_path), "dedup_details_local": str(private_dedup_path),
    }}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic, provenance-aware TCM Research Corpus v1.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "research/corpus/configs/tcm_v1.yaml")
    args = parser.parse_args()
    try:
        result = build(args.config.resolve())
    except FileNotFoundError as exc:
        print(str(exc))
        return 2
    print(json.dumps({"status": "built", **result["manifest"], "paths": result["paths"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
