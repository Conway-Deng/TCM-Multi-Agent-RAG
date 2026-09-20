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
    StageBRepeatDirectory,
    StageCDirectory,
    finalize_stage_a_run,
    finalize_stage_b_incident,
    finalize_stage_b_repeat,
    finalize_stage_b_run,
    finalize_stage_c_run,
    finalize_run,
    run_stage_a,
    run_stage_b,
    run_stage_b_repeat,
    run_stage_b_repeat_readiness,
    run_stage_c_primary,
    verify_frozen_inputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a frozen stage of the Western formal v0.1 evaluation.")
    parser.add_argument(
        "--stage",
        choices=(
            "A", "A-finalize", "B", "B-finalize", "B-incident-finalize",
            "B-repeat-readiness", "B-repeat", "B-repeat-finalize", "C", "C-finalize", "finalize",
        ),
        required=True,
    )
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
        run = RunDirectory.resume_stage_a(run_path, repository_root=ROOT) if run_path.exists() else RunDirectory.create(
            runs_root, args.run_id, repository_root=ROOT,
        )
        os.environ["ALLOW_BULK_REMOTE_EMBEDDING"] = "true"
        asyncio.run(run_stage_a(ROOT, run))
    elif args.stage in {"B-repeat-readiness", "B-repeat", "B-repeat-finalize"}:
        repeat = StageBRepeatDirectory(run_path)
        if args.stage == "B-repeat-readiness":
            asyncio.run(run_stage_b_repeat_readiness(ROOT, repeat))
        elif args.stage == "B-repeat":
            asyncio.run(run_stage_b_repeat(ROOT, repeat))
        else:
            finalize_stage_b_repeat(ROOT, repeat)
    elif args.stage in {"C", "C-finalize", "finalize"}:
        stage_c = StageCDirectory(run_path)
        if args.stage == "C":
            asyncio.run(run_stage_c_primary(ROOT, stage_c))
        elif args.stage == "C-finalize":
            finalize_stage_c_run(ROOT, stage_c)
        else:
            finalize_run(ROOT, stage_c)
    else:
        run = RunDirectory.resume(run_path)
        if args.stage == "A-finalize":
            finalize_stage_a_run(ROOT, run)
        elif args.stage == "B":
            asyncio.run(run_stage_b(ROOT, run))
        elif args.stage == "B-finalize":
            finalize_stage_b_run(ROOT, run)
        elif args.stage == "B-incident-finalize":
            finalize_stage_b_incident(ROOT, run)
        else:
            raise SystemExit(f"Unsupported stage: {args.stage}")


if __name__ == "__main__":
    main()
