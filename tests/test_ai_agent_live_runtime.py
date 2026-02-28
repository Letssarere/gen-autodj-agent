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


def test_validate_macro_args_accepts_alias_and_ignores_unknown_when_valid_present() -> None:
    agent = AIAgent(live_enabled=False)
    parsed, error = agent._validate_macro_args(  # noqa: SLF001 - internal behavior contract
        MACRO_FUNCTION_NAME,
        {"filter": 0.3, "pitch": 0.9, "volume": 0.1},
    )

    assert error is None
    assert parsed == {"filter_macro": 0.3}
    assert agent._latest_macro_controls["filter_macro"] == pytest.approx(0.3)  # noqa: SLF001


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


def test_flush_text_queue_uses_client_content_path() -> None:
    agent = AIAgent(live_enabled=False)
    agent._enqueue_text("user_prompt: 드랍 터뜨려줘")  # noqa: SLF001
    agent._enqueue_text('runtime_context: {"vision_ts": 1.23}')  # noqa: SLF001

    class _FakePart:
        def __init__(self, text: str | None = None) -> None:
            self.text = text

    class _FakeContent:
        def __init__(self, role: str, parts: list[_FakePart]) -> None:
            self.role = role
            self.parts = parts

    class _FakeTypes:
        Content = _FakeContent
        Part = _FakePart

    class _FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, bool]] = []

        async def send_client_content(self, *, turns: _FakeContent, turn_complete: bool) -> None:
            text = turns.parts[0].text if turns.parts else ""
            self.calls.append((text or "", turn_complete))

    async def _run() -> None:
        session = _FakeSession()
        await agent._flush_text_queue(session=session, types_mod=_FakeTypes)  # noqa: SLF001
        assert session.calls == [
            ("드랍 터뜨려줘", True),
            ('{"vision_ts": 1.23}', False),
        ]

    asyncio.run(_run())


def test_validate_macro_args_accepts_mapping_from_partial_completion_path() -> None:
    agent = AIAgent(live_enabled=False)
    agent._pending_partial_args["call-1"] = '{"filter_macro": 0.4, "reverb_macro": -0.2'  # noqa: SLF001

    partial_tail = "}"
    parsed = None
    text = agent._pending_partial_args.pop("call-1", "") + partial_tail  # noqa: SLF001
    loaded = None
    try:
        loaded = __import__("json").loads(text)
    except Exception:
        loaded = None
    if isinstance(loaded, dict):
        parsed = loaded

    accepted, error = agent._validate_macro_args(MACRO_FUNCTION_NAME, parsed)  # noqa: SLF001
    assert error is None
    assert accepted["filter_macro"] == pytest.approx(0.4)
    assert accepted["reverb_macro"] == pytest.approx(-0.2)
