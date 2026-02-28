from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class AbletonTarget:
    name: str
    track_index: int
    device_index: int
    parameter_index: int
    min_value: float
    max_value: float
    invert: bool = False


class AbletonController:
    """Single adapter layer for all Ableton (LOM) interactions via pylive.

    This class is the only place in the project that should directly touch
    pylive/live objects.
    """

    def __init__(
        self,
        targets_path: str | Path | None = "config/ableton_targets.json",
        smoothing_hz: float = 50.0,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._targets_path = Path(targets_path) if targets_path is not None else None
        self._targets: dict[str, AbletonTarget] = {}
        self._resolved_parameters: dict[str, Any] = {}
        self._baseline_absolute: dict[str, float] = {}
        self._current_normalized: dict[str, float] = {}

        self._set: Any | None = None
        self._live_module: Any | None = None
        self._connected: bool = False

        self._smoothing_hz = max(1.0, smoothing_hz)
        self._sleep = sleep_fn

    # ------------------------------------------------------------------
    # Fixed API
    # ------------------------------------------------------------------
    def connect(self, scan: bool = True) -> None:
        """Connect to Ableton via pylive and optionally scan the current Live set."""
        try:
            import live as live_module
        except ImportError as exc:
            raise RuntimeError(
                "pylive is not installed (module 'live' not found). "
                "Install with: pip install pylive"
            ) from exc

        self._live_module = live_module
        self._set = live_module.Set(scan=scan)
        if self._targets_path is None:
            self._targets = {}
        else:
            self._targets = self._load_targets(self._targets_path)

        if scan and self._targets:
            self._resolve_targets()

        self._connected = True

    def refresh(self) -> None:
        """Rescan Ableton set and refresh target resolution/cache."""
        self._ensure_connected()
        assert self._set is not None
        self._set.scan()
        self._resolve_targets()

    def set_normalized(self, target_name: str, value: float) -> None:
        """Set one logical target value with 0.0~1.0 normalized input."""
        self._ensure_connected()
        self._ensure_resolved()

        spec = self._require_target(target_name)
        parameter = self._require_parameter(target_name)
        normalized = self._clamp(value)
        absolute = self._normalized_to_absolute(spec, normalized)

        parameter.value = absolute
        self._current_normalized[target_name] = normalized

    def set_batch_normalized(self, values: dict[str, float], smoothing_ms: int = 250) -> None:
        """Set multiple target values with optional smoothing interpolation."""
        self._ensure_connected()
        self._ensure_resolved()

        if not values:
            return

        normalized_targets = {name: self._clamp(v) for name, v in values.items()}

        for name in normalized_targets:
            self._require_target(name)
            self._require_parameter(name)

        if smoothing_ms <= 0:
            for name, value in normalized_targets.items():
                self.set_normalized(name, value)
            return

        duration_sec = smoothing_ms / 1000.0
        steps = max(1, int(duration_sec * self._smoothing_hz))
        step_sleep = duration_sec / steps if steps > 0 else 0.0

        start_values = {
            name: self._current_normalized.get(name, self._infer_current_normalized(name))
            for name in normalized_targets
        }

        for step in range(1, steps + 1):
            alpha = step / steps
            for name, end_value in normalized_targets.items():
                start_value = start_values[name]
                interpolated = start_value + (end_value - start_value) * alpha
                self.set_normalized(name, interpolated)
            if step_sleep > 0:
                self._sleep(step_sleep)

    def get_song_tempo(self) -> float:
        self._ensure_connected()
        assert self._set is not None
        return float(self._set.tempo)

    def set_song_tempo(self, bpm: float) -> None:
        self._ensure_connected()
        if bpm <= 0:
            raise ValueError("bpm must be > 0")
        assert self._set is not None
        self._set.tempo = float(bpm)

    def safe_reset(self) -> None:
        """Reset all known logical targets to baseline values captured at connect/refresh."""
        self._ensure_connected()
        self._ensure_resolved()

        for name, spec in self._targets.items():
            parameter = self._require_parameter(name)
            baseline_abs = self._baseline_absolute.get(name)
            if baseline_abs is None:
                baseline_abs = self._normalized_to_absolute(spec, 0.5)
            parameter.value = baseline_abs
            self._current_normalized[name] = self._absolute_to_normalized(spec, baseline_abs)

    # ------------------------------------------------------------------
    # Playback helpers
    # ------------------------------------------------------------------

    def start_song_playback(self) -> None:
        self._ensure_connected()
        assert self._set is not None

        if not hasattr(self._set, "start_playing"):
            raise RuntimeError("Current pylive Set object does not support start_playing().")

        self._set.start_playing()

    def fire_clip(self, track_index: int, slot_index: int) -> None:
        self._ensure_connected()
        assert self._set is not None

        if not getattr(self._set, "scanned", False):
            self._set.scan()

        try:
            track = self._set.tracks[track_index]
        except IndexError as exc:
            raise IndexError(
                f"Invalid track_index={track_index}. Available tracks: 0..{len(self._set.tracks) - 1}"
            ) from exc

        clip_slots = getattr(track, "clip_slots", None)
        if clip_slots is not None:
            try:
                slot = clip_slots[slot_index]
            except IndexError as exc:
                raise IndexError(
                    f"Invalid slot_index={slot_index} for track[{track_index}] '{track.name}'. "
                    f"Available slots: 0..{len(clip_slots) - 1}"
                ) from exc

            slot_clip = getattr(slot, "clip", None)
            if slot_clip is None and not hasattr(slot, "fire"):
                raise RuntimeError(f"track[{track_index}] slot[{slot_index}] has no clip to fire.")

            if hasattr(slot, "fire"):
                slot.fire()
                return

            if slot_clip is not None and hasattr(slot_clip, "fire"):
                slot_clip.fire()
                return

            if slot_clip is not None and hasattr(slot_clip, "play"):
                slot_clip.play()
                return

        clips = getattr(track, "clips", None)
        if clips is not None:
            try:
                clip = clips[slot_index]
            except IndexError as exc:
                raise IndexError(
                    f"Invalid slot_index={slot_index} for track[{track_index}] '{track.name}'. "
                    f"Available clips: 0..{len(clips) - 1}"
                ) from exc

            if clip is None:
                raise RuntimeError(f"track[{track_index}] clip[{slot_index}] is empty.")

            if hasattr(clip, "fire"):
                clip.fire()
                return

            if hasattr(clip, "play"):
                clip.play()
                return

        if hasattr(track, "fire_clip"):
            track.fire_clip(slot_index)
            return

        if hasattr(track, "play_clip"):
            track.play_clip(slot_index)
            return

        raise RuntimeError(
            "Could not fire clip with current pylive track object. "
            "Try --auto-play-mode song or upgrade pylive."
        )
    # ------------------------------------------------------------------
    # Extra helpers (for diagnostics / smoke scripts)
    # ------------------------------------------------------------------
    def get_track_names(self) -> list[str]:
        self._ensure_connected()
        assert self._set is not None
        if not getattr(self._set, "scanned", False):
            self._set.scan()
        return [track.name for track in self._set.tracks]

    def get_targets(self) -> list[AbletonTarget]:
        return list(self._targets.values())

    def describe_structure(self, max_parameters_per_device: int = 16) -> str:
        """Return a human-readable snapshot of tracks/devices/parameters in the current set."""
        self._ensure_connected()
        assert self._set is not None
        if not getattr(self._set, "scanned", False):
            self._set.scan()

        lines: list[str] = []
        lines.append("Ableton Set Structure")
        lines.append("=====================")
        for t_idx, track in enumerate(self._set.tracks):
            lines.append(f"[Track {t_idx}] {track.name} | devices={len(track.devices)}")
            for d_idx, device in enumerate(track.devices):
                lines.append(f"  - [Device {d_idx}] {device.name} | parameters={len(device.parameters)}")
                for p_idx, parameter in enumerate(device.parameters[:max_parameters_per_device]):
                    lines.append(
                        "      "
                        f"[Param {p_idx}] {parameter.name} "
                        f"(min={parameter.min}, max={parameter.max}, quantized={parameter.is_quantized})"
                    )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------
    def _ensure_connected(self) -> None:
        if not self._connected or self._set is None:
            raise RuntimeError("AbletonController is not connected. Call connect() first.")

    def _ensure_resolved(self) -> None:
        if not self._targets:
            raise RuntimeError(
                "No targets are configured. Provide config/ableton_targets.json "
                "or initialize with a targets path."
            )
        if self._resolved_parameters:
            return
        assert self._set is not None
        if not getattr(self._set, "scanned", False):
            self._set.scan()
        self._resolve_targets()

    def _resolve_targets(self) -> None:
        assert self._set is not None

        resolved: dict[str, Any] = {}
        baseline_abs: dict[str, float] = {}
        current_norm: dict[str, float] = {}

        for name, spec in self._targets.items():
            try:
                track = self._set.tracks[spec.track_index]
            except IndexError as exc:
                raise IndexError(
                    f"Target '{name}' has invalid track_index={spec.track_index}. "
                    f"Available tracks: 0..{len(self._set.tracks) - 1}"
                ) from exc

            try:
                device = track.devices[spec.device_index]
            except IndexError as exc:
                raise IndexError(
                    f"Target '{name}' has invalid device_index={spec.device_index} for "
                    f"track[{spec.track_index}] '{track.name}'. "
                    f"Available devices: 0..{len(track.devices) - 1}"
                ) from exc

            try:
                parameter = device.parameters[spec.parameter_index]
            except IndexError as exc:
                raise IndexError(
                    f"Target '{name}' has invalid parameter_index={spec.parameter_index} for "
                    f"track[{spec.track_index}] '{track.name}', device[{spec.device_index}] '{device.name}'. "
                    f"Available parameters: 0..{len(device.parameters) - 1}"
                ) from exc

            resolved[name] = parameter

            baseline = float(getattr(parameter, "_value", spec.min_value))
            baseline_abs[name] = baseline
            current_norm[name] = self._absolute_to_normalized(spec, baseline)

        self._resolved_parameters = resolved
        self._baseline_absolute = baseline_abs
        self._current_normalized = current_norm

    def _require_target(self, target_name: str) -> AbletonTarget:
        try:
            return self._targets[target_name]
        except KeyError as exc:
            known = ", ".join(sorted(self._targets.keys()))
            raise KeyError(f"Unknown target '{target_name}'. Known targets: [{known}]") from exc

    def _require_parameter(self, target_name: str) -> Any:
        try:
            return self._resolved_parameters[target_name]
        except KeyError as exc:
            raise KeyError(
                f"Target '{target_name}' is not resolved. "
                "Check track/device/parameter indices and call refresh()."
            ) from exc

    def _infer_current_normalized(self, target_name: str) -> float:
        spec = self._require_target(target_name)
        parameter = self._require_parameter(target_name)

        current_abs = float(getattr(parameter, "_value", spec.min_value))
        return self._absolute_to_normalized(spec, current_abs)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @classmethod
    def _normalized_to_absolute(cls, spec: AbletonTarget, normalized: float) -> float:
        n = cls._clamp(normalized)
        if spec.invert:
            n = 1.0 - n
        return spec.min_value + (spec.max_value - spec.min_value) * n

    @classmethod
    def _absolute_to_normalized(cls, spec: AbletonTarget, absolute: float) -> float:
        if spec.max_value == spec.min_value:
            return 0.0
        normalized = (float(absolute) - spec.min_value) / (spec.max_value - spec.min_value)
        normalized = cls._clamp(normalized)
        if spec.invert:
            normalized = 1.0 - normalized
        return normalized

    @staticmethod
    def _load_targets(path: Path) -> dict[str, AbletonTarget]:
        if not path.exists():
            raise FileNotFoundError(
                f"Targets file not found: {path}. "
                "Create config/ableton_targets.json first."
            )

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("config/ableton_targets.json must be a JSON array")

        targets: dict[str, AbletonTarget] = {}
        required = {
            "name",
            "track_index",
            "device_index",
            "parameter_index",
            "min_value",
            "max_value",
        }

        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Each target entry must be an object")
            missing = required - item.keys()
            if missing:
                raise ValueError(f"Missing required fields in target entry: {sorted(missing)}")

            target = AbletonTarget(
                name=str(item["name"]),
                track_index=int(item["track_index"]),
                device_index=int(item["device_index"]),
                parameter_index=int(item["parameter_index"]),
                min_value=float(item["min_value"]),
                max_value=float(item["max_value"]),
                invert=bool(item.get("invert", False)),
            )
            targets[target.name] = target

        return targets
