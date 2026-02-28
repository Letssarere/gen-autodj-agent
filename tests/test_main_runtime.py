from __future__ import annotations

import argparse
import asyncio
import sys

import pytest

import main
from ai_agent import MacroState


class _FakeController:
    def __init__(self) -> None:
        self.song_calls = 0
        self.clip_calls: list[tuple[int, int]] = []
        self.raise_clip = False

    def start_song_playback(self) -> None:
        self.song_calls += 1

    def fire_clip(self, track_index: int, slot_index: int) -> None:
        if self.raise_clip:
            raise RuntimeError("no clip")
        self.clip_calls.append((track_index, slot_index))


def test_parse_args_autoplay_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "--auto-play",
            "--auto-play-mode",
            "clip",
            "--auto-play-track",
            "2",
            "--auto-play-slot",
            "5",
        ],
    )

    args = main._parse_args()

    assert isinstance(args, argparse.Namespace)
    assert args.auto_play is True
    assert args.auto_play_mode == "clip"
    assert args.auto_play_track == 2
    assert args.auto_play_slot == 5
    assert args.gemini_live is False
    assert args.gemini_model == "gemini-2.5-flash-native-audio-preview-12-2025"
    assert args.dry_run_controls is False


def test_run_auto_play_song_mode() -> None:
    c = _FakeController()
    main._run_auto_play(c, mode="song", track_index=0, slot_index=0)

    assert c.song_calls == 1
    assert c.clip_calls == []


def test_run_auto_play_clip_mode() -> None:
    c = _FakeController()
    main._run_auto_play(c, mode="clip", track_index=3, slot_index=4)

    assert c.song_calls == 0
    assert c.clip_calls == [(3, 4)]


def test_run_auto_play_clip_mode_failure_message() -> None:
    c = _FakeController()
    c.raise_clip = True

    with pytest.raises(RuntimeError, match="Auto-play clip failed"):
        main._run_auto_play(c, mode="clip", track_index=1, slot_index=1)


def test_run_dry_run_starts_and_stops_ai_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeControllerRuntime:
        instances: list["_FakeControllerRuntime"] = []

        def __init__(self, targets_path: str) -> None:
            self.targets_path = targets_path
            self.connect_calls = 0
            self.batch_calls: list[dict[str, float]] = []
            self.__class__.instances.append(self)

        def connect(self, scan: bool = True) -> None:
            self.connect_calls += 1

        def set_batch_normalized(self, values: dict[str, float], smoothing_ms: int = 250) -> None:
            self.batch_calls.append(values)

    class _FakeVisionState:
        timestamp = 123.0
        controls = {}

    class _FakeVisionEngine:
        def poll(self) -> _FakeVisionState:
            return _FakeVisionState()

    class _FakeAIAgent:
        instances: list["_FakeAIAgent"] = []

        def __init__(self, **_: object) -> None:
            self.started = 0
            self.stopped = 0
            self.last_server_text = ""
            self.connection_state = "disabled"
            self.session_handle = None
            self.last_error = None
            self.__class__.instances.append(self)

        async def start(self) -> None:
            self.started += 1

        async def stop(self) -> None:
            self.stopped += 1

        async def infer(self, prompt: str | None = None, context: dict[str, float] | None = None) -> MacroState:
            _ = prompt, context
            return MacroState(timestamp=1.0, controls={"filter_macro": 0.2})

    async def _cancel_sleep(_: float) -> None:
        raise asyncio.CancelledError()

    monkeypatch.setattr(main, "AbletonController", _FakeControllerRuntime)
    monkeypatch.setattr(main, "VisionEngine", _FakeVisionEngine)
    monkeypatch.setattr(main, "AIAgent", _FakeAIAgent)
    monkeypatch.setattr(main.asyncio, "sleep", _cancel_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            main.run(
                control_interval_sec=0.05,
                prompt="drop",
                targets_path="config/ableton_targets.json",
                auto_play=False,
                auto_play_mode="clip",
                auto_play_track=0,
                auto_play_slot=0,
                gemini_live=False,
                gemini_model="gemini-2.5-flash-native-audio-preview-12-2025",
                gemini_video_fps=1.0,
                gemini_hold_sec=2.0,
                gemini_neutral_ramp_sec=1.0,
                dry_run_controls=True,
            )
        )

    assert len(_FakeControllerRuntime.instances) == 1
    assert _FakeControllerRuntime.instances[0].connect_calls == 0
    assert _FakeControllerRuntime.instances[0].batch_calls == []

    assert len(_FakeAIAgent.instances) == 1
    assert _FakeAIAgent.instances[0].started == 1
    assert _FakeAIAgent.instances[0].stopped == 1
