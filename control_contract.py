from __future__ import annotations

from collections.abc import Mapping

DEADZONE = 0.05

SYMMETRIC_TARGETS = frozenset({"filter_macro", "eq_low_macro"})
ONE_SIDED_TARGETS = frozenset({"beat_repeat_macro", "reverb_macro"})
ALL_TARGETS = SYMMETRIC_TARGETS | ONE_SIDED_TARGETS


def clamp_bipolar(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def to_backend_normalized(target_name: str, value: float) -> float:
    if target_name not in ALL_TARGETS:
        known = ", ".join(sorted(ALL_TARGETS))
        raise KeyError(f"Unknown target '{target_name}'. Known targets: [{known}]")

    x = clamp_bipolar(value)

    if abs(x) < DEADZONE:
        return 0.5 if target_name in SYMMETRIC_TARGETS else 0.0

    if target_name in ONE_SIDED_TARGETS:
        if x < 0.0:
            return 0.0
        return x

    return (x + 1.0) / 2.0


def to_backend_batch(controls: Mapping[str, float]) -> dict[str, float]:
    return {name: to_backend_normalized(name, value) for name, value in controls.items()}
