from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.stage_c_free_judge import (  # noqa: E402
    get_free_candidate,
    record_zero_cost_ineligibility,
    run_free_judge_preflight,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the prospective free-only Stage C primary-judge preflight state machine.",
    )
    parser.add_argument("--candidate", type=int, required=True, choices=[1, 2, 3, 4])
    parser.add_argument("--replicate", type=int, choices=[1, 2])
    parser.add_argument("--recovery", type=int, choices=[1])
    parser.add_argument(
        "--confirm-zero-cost",
        action="store_true",
        help="Confirm manual zero-input/output-price verification immediately before this execution.",
    )
    parser.add_argument(
        "--execute-candidate-preflight",
        action="store_true",
        help="Acknowledge that the authorized six-probe preflight will contact the provider.",
    )
    parser.add_argument(
        "--record-not-zero-cost",
        action="store_true",
        help="Record pre-call operational ineligibility with zero provider calls.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    candidate = get_free_candidate(args.candidate)
    if args.record_not_zero_cost:
        if args.confirm_zero_cost or args.execute_candidate_preflight or args.recovery is not None:
            raise SystemExit(
                "--record-not-zero-cost cannot be combined with execution, confirmation, or recovery flags."
            )
        note = record_zero_cost_ineligibility(ROOT, candidate_number=args.candidate)
        print(
            f"Candidate {candidate.candidate_number:02d} ({candidate.model_id}) recorded as operationally ineligible under the zero-cost policy; provider calls: {note['provider_calls_made']}."
        )
        return

    if args.replicate is None:
        raise SystemExit("--replicate is required for candidate preflight execution.")
    if not args.confirm_zero_cost or not args.execute_candidate_preflight:
        raise SystemExit(
            "Refusing provider execution: both --confirm-zero-cost and --execute-candidate-preflight are required."
        )
    result = asyncio.run(run_free_judge_preflight(
        ROOT,
        candidate_number=args.candidate,
        replicate_number=args.replicate,
        recovery_number=args.recovery or 0,
        zero_cost_confirmed=True,
    ))
    if result["replicate_passed"] is not True:
        raise SystemExit(
            f"Candidate {candidate.candidate_number:02d} ({candidate.model_id}) attempt ended as {result['execution_classification']}; inspect the immutable manifest before any next action."
        )
    print(
        f"Candidate {candidate.candidate_number:02d} ({candidate.model_id}) replicate {args.replicate:02d} passed."
    )


if __name__ == "__main__":
    main()
