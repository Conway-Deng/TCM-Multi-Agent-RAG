from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from western.stage_c_preflight import R3_PREFLIGHT_PROBE_COUNT, R3_PREFLIGHT_TIMEOUT_SECONDS  # noqa: E402
from western.stage_c_preflight_v3 import run_stage_c_r3_json_mode_preflight_v3  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the synthetic, non-formal Stage C r3 JSON Mode preflight v3.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help=(
            "Path for the future synthetic readiness manifest, normally "
            "research/experiments/western_formal_v0_1/stage_c_r3_preflight_readiness_v3.json"
        ),
    )
    parser.add_argument("--probe-count", type=int, default=R3_PREFLIGHT_PROBE_COUNT)
    parser.add_argument("--timeout-seconds", type=float, default=R3_PREFLIGHT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--execute-synthetic-preflight",
        action="store_true",
        help="Required acknowledgement that six non-formal calls will contact the configured judge provider.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.execute_synthetic_preflight:
        raise SystemExit(
            "Refusing to call the provider: pass --execute-synthetic-preflight only after separately authorizing live v3 readiness calls."
        )
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = asyncio.run(run_stage_c_r3_json_mode_preflight_v3(
        ROOT,
        output,
        probe_count=args.probe_count,
        timeout_seconds=args.timeout_seconds,
    ))
    if result["eligible_to_propose_formal_r3_freeze"] is not True:
        raise SystemExit(
            "Synthetic Stage C r3 JSON Mode readiness failed; formal r3 freeze is not authorized."
        )


if __name__ == "__main__":
    main()
