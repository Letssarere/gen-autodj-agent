from __future__ import annotations

import pytest

from control_contract import (
    ALL_TARGETS,
    DEADZONE,
    ONE_SIDED_TARGETS,
    SYMMETRIC_TARGETS,
    to_backend_normalized,
)


def test_target_partition_is_frozen() -> None:
    assert SYMMETRIC_TARGETS == {"filter_macro", "eq_low_macro"}
    assert ONE_SIDED_TARGETS == {"beat_repeat_macro", "reverb_macro"}
    assert ALL_TARGETS == {"filter_macro", "eq_low_macro", "beat_repeat_macro", "reverb_macro"}


def test_deadzone_constant_is_frozen() -> None:
    assert DEADZONE == 0.05


@pytest.mark.parametrize(
    ("name", "x", "expected"),
    [
        ("filter_macro", -1.0, 0.0),
        ("filter_macro", -0.05, 0.475),
        ("filter_macro", -0.049, 0.5),
        ("filter_macro", 0.0, 0.5),
        ("filter_macro", 0.049, 0.5),
        ("filter_macro", 0.05, 0.525),
        ("filter_macro", 1.0, 1.0),
    ],
)
def test_symmetric_mapping_boundaries(name: str, x: float, expected: float) -> None:
    assert to_backend_normalized(name, x) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("name", "x", "expected"),
    [
        ("reverb_macro", -1.0, 0.0),
        ("reverb_macro", -0.05, 0.0),
        ("reverb_macro", -0.049, 0.0),
        ("reverb_macro", 0.0, 0.0),
        ("reverb_macro", 0.049, 0.0),
        ("reverb_macro", 0.05, 0.05),
        ("reverb_macro", 1.0, 1.0),
    ],
)
def test_one_sided_mapping_boundaries(name: str, x: float, expected: float) -> None:
    assert to_backend_normalized(name, x) == pytest.approx(expected)


def test_unknown_target_rejected() -> None:
    with pytest.raises(KeyError):
        to_backend_normalized("unknown", 0.2)
