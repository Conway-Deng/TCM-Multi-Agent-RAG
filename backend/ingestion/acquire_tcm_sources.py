from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from ingestion.tcm_v1 import load_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def acquire(config_path: Path, *, download: bool, selected: set[str]) -> dict:
    config = load_config(config_path)
    results: list[dict] = []
    for source in config["sources"]:
        if selected and source["source_id"] not in selected:
            continue
        files = source.get("acquisition", [])
        if not files:
            results.append({"source_id": source["source_id"], "status": "manual_or_deferred", "instruction": f"Review {source['official_url']} and the source audit before placing approved files under research/corpus/raw/{source['source_id']}."})
            continue
        for item in files:
            destination = PROJECT_ROOT / item["destination"]
            if destination.exists():
                results.append({"source_id": source["source_id"], "status": "present", "path": item["destination"], "sha256": _hash(destination)})
                continue
            if not download:
                results.append({"source_id": source["source_id"], "status": "missing", "path": item["destination"], "url": item["url"], "instruction": f"Download {item['filename']} from {item['url']} and save it exactly as {item['destination']}."})
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            request = Request(item["url"], headers={"User-Agent": "TCM-Corpus-v1 academic research acquisition"})
            with urlopen(request, timeout=60) as response, destination.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
            results.append({"source_id": source["source_id"], "status": "downloaded", "path": item["destination"], "sha256": _hash(destination)})
    return {"download_requested": download, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit-aware local acquisition for TCM Corpus v1 sources.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "research/corpus/configs/tcm_v1.yaml")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--download", action="store_true", help="Download only files listed in the audited config; otherwise print exact instructions.")
    args = parser.parse_args()
    print(json.dumps(acquire(args.config.resolve(), download=args.download, selected=set(args.source)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
