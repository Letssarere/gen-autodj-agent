from __future__ import annotations

import argparse
import asyncio
from typing import Any

from ableton_controller import AbletonController
from ai_agent import AIAgent
from control_contract import to_backend_batch
from vision_engine import VisionEngine


def merge_controls(micro: dict[str, float], macro: dict[str, float]) -> dict[str, float]:
    """Merge policy: macro base + micro override for same keys."""
    merged = dict(macro)
    merged.update(micro)
    return merged


def _run_auto_play(
    controller: AbletonController,
    *,
    mode: str,
    track_index: int,
    slot_index: int,
) -> None:
    if mode == "song":
        controller.start_song_playback()
        return

    try:
        controller.fire_clip(track_index=track_index, slot_index=slot_index)
    except Exception as exc:
        raise RuntimeError(
            "Auto-play clip failed for "
            f"track={track_index}, slot={slot_index}. "
            "Use --auto-play-mode song or verify slot content."
        ) from exc


async def run(
    control_interval_sec: float,
    prompt: str | None,
    targets_path: str,
    auto_play: bool,
    auto_play_mode: str,
    auto_play_track: int,
    auto_play_slot: int,
    gemini_live: bool,
    gemini_model: str,
    gemini_video_fps: float,
    gemini_hold_sec: float,
    gemini_neutral_ramp_sec: float,
    dry_run_controls: bool,
) -> None:
    controller = AbletonController(targets_path=targets_path)

    vision = VisionEngine()
    ai_agent = AIAgent(
        live_enabled=gemini_live,
        model=gemini_model,
        video_fps=gemini_video_fps,
        hold_sec=gemini_hold_sec,
        neutral_ramp_sec=gemini_neutral_ramp_sec,
    )

    if not dry_run_controls:
        controller.connect(scan=True)

        if auto_play:
            _run_auto_play(
                controller,
                mode=auto_play_mode,
                track_index=auto_play_track,
                slot_index=auto_play_slot,
            )

    await ai_agent.start()
    last_dry_run: dict[str, float] = {}
    last_live_applied: dict[str, float] = {}
    last_heartbeat = 0.0

    try:
        while True:
            vision_state = vision.poll()
            macro_state = await ai_agent.infer(prompt=prompt, context={"vision_ts": vision_state.timestamp})

            merged = merge_controls(vision_state.controls, macro_state.controls)
            if merged:
                normalized = to_backend_batch(merged)
                if dry_run_controls:
                    if normalized != last_dry_run:
                        print(f"[dry-run] normalized controls: {normalized}")
                        last_dry_run = dict(normalized)
                else:
                    controller.set_batch_normalized(normalized, smoothing_ms=250)
                    if gemini_live and normalized != last_live_applied:
                        print(f"[live] applied controls: {normalized}")
                        last_live_applied = dict(normalized)

            if dry_run_controls or gemini_live:
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat >= 2.0:
                    snippet = ai_agent.last_server_text.strip().replace("\n", " ")
                    if len(snippet) > 80:
                        snippet = f"{snippet[:77]}..."
                    prefix = "[dry-run]" if dry_run_controls else "[live]"
                    print(
                        f"{prefix} "
                        f"live_state={ai_agent.connection_state} "
                        f"handle={ai_agent.session_handle or '-'} "
                        f"last_text={snippet or '-'} "
                        f"last_error={ai_agent.last_error or '-'}"
                    )
                    last_heartbeat = now

            await asyncio.sleep(control_interval_sec)
    finally:
        await ai_agent.stop()


def _parse_args() -> Any:
    parser = argparse.ArgumentParser(description="gen-autodj-agent runtime skeleton")
    parser.add_argument("--targets", default="config/ableton_targets.json", help="Path to target map JSON")
    parser.add_argument("--interval", type=float, default=0.05, help="Main loop interval (seconds)")
    parser.add_argument("--prompt", default=None, help="Optional high-level user prompt")
    parser.add_argument(
        "--auto-play",
        action="store_true",
        help="Trigger initial playback automatically (opt-in)",
    )
    parser.add_argument(
        "--auto-play-mode",
        choices=("clip", "song"),
        default="clip",
        help="Auto-play mode: launch a clip slot or trigger global song playback",
    )
    parser.add_argument(
        "--auto-play-track",
        type=int,
        default=0,
        help="Track index for clip auto-play mode",
    )
    parser.add_argument(
        "--auto-play-slot",
        type=int,
        default=0,
        help="Slot index for clip auto-play mode",
    )
    parser.add_argument(
        "--gemini-live",
        action="store_true",
        help="Enable Gemini Live audio/video/text streaming mode",
    )
    parser.add_argument(
        "--gemini-model",
        default="gemini-2.5-flash-native-audio-preview-12-2025",
        help="Gemini Live model name",
    )
    parser.add_argument(
        "--gemini-video-fps",
        type=float,
        default=1.0,
        help="Camera frame rate sent to Gemini Live",
    )
    parser.add_argument(
        "--gemini-hold-sec",
        type=float,
        default=2.0,
        help="Hold previous controls this long after last tool call",
    )
    parser.add_argument(
        "--gemini-neutral-ramp-sec",
        type=float,
        default=1.0,
        help="Neutral ramp duration after hold window",
    )
    parser.add_argument(
        "--dry-run-controls",
        action="store_true",
        help="Skip Ableton writes and print normalized control values",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        run(
            control_interval_sec=args.interval,
            prompt=args.prompt,
            targets_path=args.targets,
            auto_play=args.auto_play,
            auto_play_mode=args.auto_play_mode,
            auto_play_track=args.auto_play_track,
            auto_play_slot=args.auto_play_slot,
            gemini_live=args.gemini_live,
            gemini_model=args.gemini_model,
            gemini_video_fps=args.gemini_video_fps,
            gemini_hold_sec=args.gemini_hold_sec,
            gemini_neutral_ramp_sec=args.gemini_neutral_ramp_sec,
            dry_run_controls=args.dry_run_controls,
        )
    )
