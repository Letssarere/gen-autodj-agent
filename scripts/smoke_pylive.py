#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ableton_controller import AbletonController


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for pylive + AbletonOSC connection")
    parser.add_argument(
        "--targets",
        default="config/ableton_targets.json",
        help="Path to logical target mapping JSON (default: Super Rack v1)",
    )
    parser.add_argument(
        "--target",
        default="filter_macro",
        help="Logical target name to test",
    )
    parser.add_argument(
        "--all-targets",
        action="store_true",
        help="Test all targets listed in the mapping file",
    )
    parser.add_argument(
        "--value",
        type=float,
        default=0.8,
        help="Normalized test value for --target (0.0~1.0)",
    )
    parser.add_argument(
        "--tempo-delta",
        type=float,
        default=0.5,
        help="Temporary tempo bump for write/read validation",
    )
    args = parser.parse_args()

    controller = AbletonController(targets_path=args.targets)

    try:
        print("[1/5] Connecting to Ableton via pylive...")
        controller.connect(scan=True)
        print("Connected.")

        print("[2/5] Reading tracks and tempo...")
        track_names = controller.get_track_names()
        tempo_before = controller.get_song_tempo()
        print(f"Tracks ({len(track_names)}): {track_names}")
        print(f"Tempo before: {tempo_before:.3f}")

        print("[3/5] Tempo write/read test...")
        controller.set_song_tempo(tempo_before + args.tempo_delta)
        tempo_mid = controller.get_song_tempo()
        print(f"Tempo after bump: {tempo_mid:.3f}")
        controller.set_song_tempo(tempo_before)
        tempo_restored = controller.get_song_tempo()
        print(f"Tempo restored: {tempo_restored:.3f}")

        print("[4/5] Target write + smoothing test...")
        if args.all_targets:
            target_names = [t.name for t in controller.get_targets()]
            print(f"Testing all targets ({len(target_names)}):")
            for i, target_name in enumerate(target_names, start=1):
                print(f"  [{i}/{len(target_names)}] {target_name}")
                controller.set_normalized(target_name, 0.1)
                controller.set_batch_normalized({target_name: args.value}, smoothing_ms=400)
                controller.set_batch_normalized({target_name: 0.1}, smoothing_ms=400)
                print(f"  -> Target '{target_name}' written successfully.")
        else:
            controller.set_normalized(args.target, 0.1)
            controller.set_batch_normalized({args.target: args.value}, smoothing_ms=400)
            controller.set_batch_normalized({args.target: 0.1}, smoothing_ms=400)
            print(f"Target '{args.target}' written successfully.")

        print("[5/5] Safe reset...")
        controller.safe_reset()
        print("safe_reset() completed.")

        print("Smoke test passed.")
        return 0
    except Exception as exc:
        print("Smoke test failed:")
        print(f"  {exc}")
        if isinstance(exc, IndexError):
            print(
                "\nHint: target indices in the selected targets JSON do not match the current Ableton set.\n"
                "Run this first and update track/device/parameter indices:\n"
                "  python scripts/list_live_structure.py --max-params 24\n"
                "Then retry with:\n"
                "  python scripts/smoke_pylive.py --targets config/ableton_targets.json --all-targets --value 0.8"
            )
        print("\nDetails:")
        traceback.print_exc()
        try:
            controller.safe_reset()
            print("safe_reset() executed after failure.")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
