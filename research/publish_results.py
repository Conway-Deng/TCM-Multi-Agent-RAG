from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def main() -> int:
    parser = argparse.ArgumentParser(description="Intentionally copy selected, reviewed result files into a publishable directory.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--confirm-reviewed", action="store_true")
    args = parser.parse_args()
    if not args.confirm_reviewed:
        raise SystemExit("Refusing to publish without --confirm-reviewed")
    args.destination.mkdir(parents=True, exist_ok=True)
    for name in ("manifest.json", "condition_summary.csv", "report.md"):
        source = args.source / name
        if source.exists():
            shutil.copy2(source, args.destination / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
