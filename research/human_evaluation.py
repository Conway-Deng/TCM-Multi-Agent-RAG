from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from evaluation.human import aggregate_reviews, validate_import


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and aggregate completed human-review CSV files.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reviews, errors = validate_import(args.csv_path)
    payload = {"validation_errors": errors, "aggregate": aggregate_reviews(reviews)}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
