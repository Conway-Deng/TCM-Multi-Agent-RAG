from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.stage_c_preflight import (  # noqa: E402
    R3_PREFLIGHT_PROBE_COUNT,
    R3_PREFLIGHT_TIMEOUT_SECONDS,
    run_stage_c_r3_structured_output_preflight,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run synthetic, non-formal Stage C r3 structured-output readiness probes.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-count", type=int, default=R3_PREFLIGHT_PROBE_COUNT)
    parser.add_argument("--timeout-seconds", type=float, default=R3_PREFLIGHT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--execute-synthetic-preflight",
        action="store_true",
        help="Required acknowledgement that synthetic readiness calls will contact the configured judge provider.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute_synthetic_preflight:
        raise SystemExit(
            "Refusing to call the provider: pass --execute-synthetic-preflight after confirming this is non-formal readiness only."
        )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = asyncio.run(run_stage_c_r3_structured_output_preflight(
        ROOT,
        output,
        probe_count=args.probe_count,
        timeout_seconds=args.timeout_seconds,
    ))
    if result["all_required_probes_passed"] is not True:
        raise SystemExit("Synthetic Stage C r3 readiness failed; formal r3 freeze is not authorized.")


if __name__ == "__main__":
    main()
