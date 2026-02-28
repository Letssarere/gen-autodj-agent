from __future__ import annotations

import math

from ableton_controller import AbletonController, AbletonTarget


def _target(*, min_value: float = 0.0, max_value: float = 10.0, invert: bool = False) -> AbletonTarget:
    return AbletonTarget(
        name="t",
        track_index=0,
        device_index=0,
        parameter_index=0,
        min_value=min_value,
        max_value=max_value,
        invert=invert,
    )


def test_clamp_boundaries() -> None:
    assert AbletonController._clamp(-1.0) == 0.0
    assert AbletonController._clamp(0.0) == 0.0
    assert AbletonController._clamp(0.25) == 0.25
    assert AbletonController._clamp(1.0) == 1.0
    assert AbletonController._clamp(5.0) == 1.0


def test_normalized_to_absolute_without_invert() -> None:
    spec = _target(min_value=-12.0, max_value=12.0, invert=False)
    assert AbletonController._normalized_to_absolute(spec, 0.0) == -12.0
    assert AbletonController._normalized_to_absolute(spec, 0.5) == 0.0
    assert AbletonController._normalized_to_absolute(spec, 1.0) == 12.0


def test_normalized_to_absolute_with_invert() -> None:
    spec = _target(min_value=0.0, max_value=100.0, invert=True)
    assert AbletonController._normalized_to_absolute(spec, 0.0) == 100.0
    assert AbletonController._normalized_to_absolute(spec, 0.5) == 50.0
    assert AbletonController._normalized_to_absolute(spec, 1.0) == 0.0


def test_absolute_to_normalized_roundtrip() -> None:
    spec = _target(min_value=-24.0, max_value=6.0, invert=False)
    for normalized in (0.0, 0.1, 0.5, 0.75, 1.0):
        absolute = AbletonController._normalized_to_absolute(spec, normalized)
        restored = AbletonController._absolute_to_normalized(spec, absolute)
        assert math.isclose(restored, normalized, rel_tol=1e-9, abs_tol=1e-9)


def test_absolute_to_normalized_degenerate_range() -> None:
    spec = _target(min_value=3.0, max_value=3.0)
    assert AbletonController._absolute_to_normalized(spec, 3.0) == 0.0
