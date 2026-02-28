#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ableton_controller import AbletonController


def main() -> int:
    parser = argparse.ArgumentParser(description="Print Ableton tracks/devices/parameters via pylive")
    parser.add_argument(
        "--max-params",
        type=int,
        default=16,
        help="Max parameters to print per device",
    )
    args = parser.parse_args()

    controller = AbletonController(targets_path=None)
    controller.connect(scan=True)
    print(controller.describe_structure(max_parameters_per_device=max(1, args.max_params)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
