from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "ableton_targets.json"
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "ableton_targets.super_rack_v1.example.json"

REQUIRED_FIELDS = {
    "name",
    "track_index",
    "device_index",
    "parameter_index",
    "min_value",
    "max_value",
}
EXPECTED_TARGETS = {
    "filter_macro",
    "beat_repeat_macro",
    "reverb_macro",
    "eq_low_macro",
}


def _validate_config(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert len(raw) == 4

    names = set()
    for item in raw:
        assert isinstance(item, dict)
        assert REQUIRED_FIELDS.issubset(item.keys())

        names.add(item["name"])

        assert isinstance(item["track_index"], int)
        assert isinstance(item["device_index"], int)
        assert isinstance(item["parameter_index"], int)

        min_value = float(item["min_value"])
        max_value = float(item["max_value"])
        assert min_value < max_value

        invert = item.get("invert", False)
        assert isinstance(invert, bool)

    assert names == EXPECTED_TARGETS
    return raw


def test_super_rack_configs_exist() -> None:
    assert DEFAULT_CONFIG.exists(), f"Missing config file: {DEFAULT_CONFIG}"
    assert EXAMPLE_CONFIG.exists(), f"Missing config file: {EXAMPLE_CONFIG}"


def test_default_and_example_configs_follow_contract() -> None:
    default_raw = _validate_config(DEFAULT_CONFIG)
    example_raw = _validate_config(EXAMPLE_CONFIG)
    assert default_raw == example_raw
