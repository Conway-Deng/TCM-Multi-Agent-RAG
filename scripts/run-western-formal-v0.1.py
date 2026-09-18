from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.formal_eval import (  # noqa: E402
    RunDirectory,
    finalize_run,
    run_stage_a,
    run_stage_b,
    run_stage_c,
    verify_frozen_inputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a frozen stage of the Western formal v0.1 evaluation.")
    parser.add_argument("--stage", choices=("A", "B", "C", "finalize"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--execute-formal",
        action="store_true",
        help="Required acknowledgement that a formal stage may call configured providers.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute_formal:
        raise SystemExit("Refusing to execute: pass --execute-formal after confirming the frozen protocol.")
    verify_frozen_inputs(ROOT)
    runs_root = ROOT / "research/experiments/western_formal_v0_1/runs"
    run_path = runs_root / args.run_id
    if args.stage == "A":
        run = RunDirectory.resume(run_path) if run_path.exists() else RunDirectory.create(runs_root, args.run_id)
        os.environ["ALLOW_BULK_REMOTE_EMBEDDING"] = "true"
        asyncio.run(run_stage_a(ROOT, run))
    else:
        run = RunDirectory.resume(run_path)
        if args.stage == "B":
            asyncio.run(run_stage_b(ROOT, run))
        elif args.stage == "C":
            asyncio.run(run_stage_c(ROOT, run))
        else:
            finalize_run(ROOT, run)


if __name__ == "__main__":
    main()
