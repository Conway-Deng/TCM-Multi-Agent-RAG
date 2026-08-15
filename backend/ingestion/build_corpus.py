from __future__ import annotations

import argparse
import json
from pathlib import Path

from corpus.models import SourceRecord
from ingestion.pipeline import build_corpus_from_directory, corpus_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic TCM research corpus from researcher-provided files.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_items = json.loads(args.sources.read_text(encoding="utf-8"))
    sources = {item["source_id"]: SourceRecord.model_validate(item) for item in source_items}
    chunks, issues = build_corpus_from_directory(args.input, sources)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "chunks.jsonl").write_text("\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in chunks) + "\n", encoding="utf-8")
    (args.output / "manifest.json").write_text(json.dumps(corpus_manifest(sources, chunks), ensure_ascii=False, indent=2), encoding="utf-8")
    if issues:
        (args.output / "issues.json").write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"chunks": len(chunks), "issues": len(issues), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
