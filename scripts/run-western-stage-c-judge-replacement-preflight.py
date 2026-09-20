from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.stage_c_judge_replacement import (  # noqa: E402
    REPLACEMENT_TIMEOUT_SECONDS,
    candidate_manifest_name,
    get_candidate,
    run_stage_c_judge_replacement_preflight,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run prospective Stage C judge replacement preflight replicate for a candidate.",
    )
    parser.add_argument(
        "--candidate",
        type=int,
        required=True,
        choices=[1, 2, 3],
        help="Frozen candidate number in registry (1: DeepSeek-V3.2, 2: gpt-oss-120b, 3: Qwen3.5-35B-A3B)",
    )
    parser.add_argument(
        "--replicate",
        type=int,
        required=True,
        choices=[1, 2],
        help="Replicate number (1 or 2). Replicate 2 requires >=3600s elapsed since replicate 1 completion.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path. Defaults to research/experiments/western_formal_v0_1/<deterministic_manifest_name>",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=REPLACEMENT_TIMEOUT_SECONDS,
        help=f"Client timeout in seconds (frozen at {REPLACEMENT_TIMEOUT_SECONDS}s)",
    )
    parser.add_argument(
        "--execute-candidate-preflight",
        action="store_true",
        help="Required acknowledgement that six non-formal synthetic readiness calls will contact the configured candidate provider.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute_candidate-preflight if hasattr(args, "execute_candidate-preflight") else not args.execute_candidate_preflight:
        raise SystemExit(
            "Refusing to call the provider: pass --execute-candidate-preflight only after separately authorizing live replacement candidate readiness calls."
        )

    candidate = get_candidate(args.candidate)
    default_name = candidate_manifest_name(candidate.candidate_number, args.replicate)
    output_path = (
        args.output
        if args.output is not None
        else ROOT / "research/experiments/western_formal_v0_1" / default_name
    )
    if not output_path.is_absolute():
        output_path = ROOT / output_path

    result = asyncio.run(
        run_stage_c_judge_replacement_preflight(
            ROOT,
            output_path,
            candidate_number=args.candidate,
            replicate_number=args.replicate,
            timeout_seconds=args.timeout_seconds,
        )
    )

    if result.get("replicate_passed") is not True:
        raise SystemExit(
            f"Candidate {candidate.candidate_number:02d} ({candidate.model_id}) replicate {args.replicate:02d} FAILED synthetic readiness gate."
        )

    print(
        f"Candidate {candidate.candidate_number:02d} ({candidate.model_id}) replicate {args.replicate:02d} PASSED synthetic readiness gate."
    )


if __name__ == "__main__":
    main()
