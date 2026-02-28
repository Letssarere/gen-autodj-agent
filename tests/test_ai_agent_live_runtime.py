from __future__ import annotations

import asyncio
import time

import pytest

from ai_agent import AIAgent, MACRO_FUNCTION_NAME


def test_validate_macro_args_success_updates_cache() -> None:
    agent = AIAgent(live_enabled=False)
    parsed, error = agent._validate_macro_args(  # noqa: SLF001 - internal behavior contract
        MACRO_FUNCTION_NAME,
        {"filter_macro": 0.25, "reverb_macro": -0.5},
    )

    assert error is None
    assert parsed == {"filter_macro": 0.25, "reverb_macro": -0.5}
    assert agent._latest_macro_controls["filter_macro"] == pytest.approx(0.25)  # noqa: SLF001
    assert agent._latest_macro_controls["reverb_macro"] == pytest.approx(-0.5)  # noqa: SLF001
    assert agent._last_tool_call_monotonic is not None  # noqa: SLF001


@pytest.mark.parametrize(
    ("name", "args", "expected_error_prefix"),
    [
        ("wrong_function", {"filter_macro": 0.1}, "unsupported_function"),
        (MACRO_FUNCTION_NAME, None, "invalid_args:object_required"),
        (MACRO_FUNCTION_NAME, {}, "invalid_args:empty_payload"),
        (MACRO_FUNCTION_NAME, {"unknown": 0.1}, "invalid_args:unknown_fields"),
        (MACRO_FUNCTION_NAME, {"filter_macro": "nope"}, "invalid_args:not_number"),
        (MACRO_FUNCTION_NAME, {"filter_macro": 9.9}, "invalid_args:out_of_range"),
    ],
)
def test_validate_macro_args_rejects_invalid_payload(
    name: str,
    args: object,
    expected_error_prefix: str,
) -> None:
    agent = AIAgent(live_enabled=False)
    parsed, error = agent._validate_macro_args(name, args)  # noqa: SLF001 - internal behavior contract

    assert parsed == {}
    assert isinstance(error, str)
    assert error.startswith(expected_error_prefix)


def test_controls_for_time_hold_and_ramp() -> None:
    agent = AIAgent(live_enabled=False, hold_sec=2.0, neutral_ramp_sec=1.0)
    agent._latest_macro_controls = {"filter_macro": 1.0, "eq_low_macro": -0.5}  # noqa: SLF001
    agent._last_tool_call_monotonic = 100.0  # noqa: SLF001

    held = agent._controls_for_time(101.0)  # noqa: SLF001
    ramp_half = agent._controls_for_time(102.5)  # noqa: SLF001
    ramp_done = agent._controls_for_time(103.5)  # noqa: SLF001

    assert held == {"filter_macro": 1.0, "eq_low_macro": -0.5}

    assert ramp_half["filter_macro"] == pytest.approx(0.5)
    assert ramp_half["eq_low_macro"] == pytest.approx(-0.25)
    assert ramp_half["beat_repeat_macro"] == pytest.approx(0.0)
    assert ramp_half["reverb_macro"] == pytest.approx(0.0)

    assert ramp_done["filter_macro"] == pytest.approx(0.0)
    assert ramp_done["eq_low_macro"] == pytest.approx(0.0)
    assert ramp_done["beat_repeat_macro"] == pytest.approx(0.0)
    assert ramp_done["reverb_macro"] == pytest.approx(0.0)


def test_infer_is_non_blocking_and_enqueues_prompt_context() -> None:
    agent = AIAgent(live_enabled=False, context_push_interval_sec=999.0)

    async def _run() -> None:
        start = time.monotonic()
        state = await asyncio.wait_for(
            agent.infer(prompt="drop", context={"vision_ts": 123.4}),
            timeout=0.05,
        )
        elapsed = time.monotonic() - start

        assert elapsed < 0.05
        assert state.controls == {}
        assert agent._text_queue.qsize() == 2  # noqa: SLF001 - one prompt + one context

    asyncio.run(_run())

