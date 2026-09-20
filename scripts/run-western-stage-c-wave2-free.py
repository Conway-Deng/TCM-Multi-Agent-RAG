from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.stage_c_wave2_free import (  # noqa: E402
    StageCWave2Error,
    create_wave2_exhaustion_artifact,
    create_wave2_operational_adjudication,
    freeze_wave2_candidate_pool,
    inspect_wave2_state,
    record_wave2_zero_cost_ineligibility,
    run_wave2_candidate_preflight,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline discovery freeze and later frozen-registry Wave-2 judge qualification.",
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--freeze-candidate-pool", action="store_true")
    modes.add_argument("--inspect", action="store_true")
    modes.add_argument("--record-not-zero-cost", action="store_true")
    modes.add_argument("--adjudicate-operationally-unevaluable", action="store_true")
    modes.add_argument("--finalize-exhaustion", action="store_true")
    modes.add_argument("--execute-candidate-preflight", action="store_true")
    parser.add_argument("--candidate", type=int, choices=[1, 2, 3, 4])
    parser.add_argument("--replicate", type=int, choices=[1, 2])
    parser.add_argument("--recovery", type=int, choices=[1])
    parser.add_argument("--confirm-zero-cost", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.freeze_candidate_pool:
        if any(
            value is not None
            for value in (args.candidate, args.replicate, args.recovery)
        ) or args.confirm_zero_cost:
            raise SystemExit("Freeze mode accepts no candidate or execution arguments.")
        freeze = freeze_wave2_candidate_pool(ROOT)
        print(
            f"Wave-2 pool frozen offline with {freeze['pool_size']} candidate(s); no provider inference call made."
        )
        return
    if args.inspect:
        if any(
            value is not None
            for value in (args.candidate, args.replicate, args.recovery)
        ) or args.confirm_zero_cost:
            raise SystemExit("Inspect mode accepts no candidate or execution arguments.")
        state = inspect_wave2_state(ROOT)
        statuses = [
            f"{candidate.candidate_number}:{state['attempts'][candidate.candidate_number]}"
            for candidate in state["registry"].candidates
        ]
        print(f"Wave-2 frozen candidates: {len(statuses)}; state loaded successfully.")
        return
    if args.finalize_exhaustion:
        if any(
            value is not None
            for value in (args.candidate, args.replicate, args.recovery)
        ) or args.confirm_zero_cost:
            raise SystemExit("Exhaustion mode accepts no candidate or execution arguments.")
        artifact = create_wave2_exhaustion_artifact(ROOT)
        print(
            f"Wave-2 exhausted with pool size {artifact['pool_size']}; Wave 3 remains prohibited."
        )
        return
    if args.candidate is None:
        raise SystemExit("The selected operation requires --candidate.")
    if args.record_not_zero_cost:
        if args.replicate is not None or args.recovery is not None or args.confirm_zero_cost:
            raise SystemExit("Zero-cost ineligibility accepts only --candidate.")
        note = record_wave2_zero_cost_ineligibility(
            ROOT,
            candidate_number=args.candidate,
        )
        print(
            f"Wave-2 candidate {args.candidate:02d} recorded as zero-cost ineligible; provider calls: {note['provider_calls_made']}."
        )
        return
    if args.adjudicate_operationally_unevaluable:
        if args.replicate is None or args.recovery is not None or args.confirm_zero_cost:
            raise SystemExit("Operational adjudication requires --candidate and --replicate only.")
        result = create_wave2_operational_adjudication(
            ROOT,
            candidate_number=args.candidate,
            replicate_number=args.replicate,
        )
        print(
            f"Wave-2 candidate {args.candidate:02d} adjudicated as {result['adjudication_state']}."
        )
        return
    if args.replicate is None:
        raise SystemExit("Preflight execution requires --candidate and --replicate.")
    if not args.confirm_zero_cost:
        raise SystemExit("Preflight execution requires --confirm-zero-cost.")
    result = asyncio.run(
        run_wave2_candidate_preflight(
            ROOT,
            candidate_number=args.candidate,
            replicate_number=args.replicate,
            recovery_number=args.recovery or 0,
            zero_cost_confirmed=True,
        )
    )
    if result["replicate_passed"] is not True:
        raise SystemExit(
            f"Wave-2 candidate attempt ended as {result['execution_classification']}; inspect immutable artifacts."
        )
    print(
        f"Wave-2 candidate {args.candidate:02d} Replicate {args.replicate:02d} passed."
    )


if __name__ == "__main__":
    try:
        main()
    except StageCWave2Error as exc:
        raise SystemExit(str(exc)) from exc
