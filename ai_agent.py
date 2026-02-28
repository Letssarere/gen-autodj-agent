from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping


MACRO_TARGETS = (
    "filter_macro",
    "beat_repeat_macro",
    "reverb_macro",
    "eq_low_macro",
)
MACRO_TARGET_SET = frozenset(MACRO_TARGETS)
MACRO_FUNCTION_NAME = "set_macro_controls"
MACRO_FIELD_ALIASES = {
    # filter family
    "filter": "filter_macro",
    "filter_cutoff": "filter_macro",
    # beat-repeat family
    "beat_repeat": "beat_repeat_macro",
    "beatrepeat": "beat_repeat_macro",
    "repeat": "beat_repeat_macro",
    "stutter": "beat_repeat_macro",
    "glitch": "beat_repeat_macro",
    "delay": "beat_repeat_macro",
    # reverb family
    "reverb": "reverb_macro",
    "room": "reverb_macro",
    # EQ low family
    "eq_low": "eq_low_macro",
    "low_eq": "eq_low_macro",
    "bass": "eq_low_macro",
    "low": "eq_low_macro",
}


@dataclass
class MacroState:
    """Macro-control payload in bipolar range (-1.0 ~ 1.0)."""

    timestamp: float
    controls: dict[str, float]


class AIAgent:
    """Gemini Live adapter for Macro-First control.

    Runtime behavior:
    - start(): opens persistent Gemini Live session in background.
    - infer(): non-blocking snapshot read of most recent macro controls.
    - stop(): tears down all background tasks and I/O resources.
    """

    def __init__(
        self,
        *,
        live_enabled: bool = False,
        model: str = "gemini-2.5-flash-native-audio-preview-12-2025",
        audio_rate_hz: int = 16000,
        audio_frames_per_chunk: int = 1024,
        video_fps: float = 1.0,
        hold_sec: float = 2.0,
        neutral_ramp_sec: float = 1.0,
        context_push_interval_sec: float = 1.0,
    ) -> None:
        self._live_enabled = live_enabled
        self._model = model
        self._audio_rate_hz = max(8000, int(audio_rate_hz))
        self._audio_frames_per_chunk = max(128, int(audio_frames_per_chunk))
        self._video_fps = max(0.1, float(video_fps))
        self._hold_sec = max(0.0, float(hold_sec))
        self._neutral_ramp_sec = max(0.01, float(neutral_ramp_sec))
        self._context_push_interval_sec = max(0.1, float(context_push_interval_sec))

        self._stop_event = asyncio.Event()
        self._supervisor_task: asyncio.Task[None] | None = None

        self._text_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)

        self._latest_macro_controls: dict[str, float] = {}
        self._last_tool_call_monotonic: float | None = None

        self._session_handle: str | None = None
        self._connection_state = "idle"
        self._last_server_text = ""
        self._last_error: str | None = None

        self._last_prompt_sent: str | None = None
        self._last_context_push_monotonic = 0.0
        self._pending_partial_args: dict[str, str] = {}

    @property
    def session_handle(self) -> str | None:
        return self._session_handle

    @property
    def connection_state(self) -> str:
        return self._connection_state

    @property
    def last_server_text(self) -> str:
        return self._last_server_text

    @property
    def last_error(self) -> str | None:
        return self._last_error

    async def start(self) -> None:
        if not self._live_enabled:
            self._connection_state = "disabled"
            return

        if self._supervisor_task is not None and not self._supervisor_task.done():
            return

        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Export GEMINI_API_KEY before running with --gemini-live."
            )

        self._stop_event = asyncio.Event()
        self._connection_state = "starting"
        self._last_error = None
        self._supervisor_task = asyncio.create_task(
            self._run_supervisor(),
            name="ai_agent_live_supervisor",
        )

    async def stop(self) -> None:
        self._stop_event.set()

        tasks = [self._supervisor_task]
        for task in tasks:
            if task is not None and not task.done():
                task.cancel()

        for task in tasks:
            if task is None:
                continue
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._supervisor_task = None
        self._connection_state = "stopped"

    async def infer(self, prompt: str | None = None, context: dict[str, Any] | None = None) -> MacroState:
        # Prompt and context are pushed asynchronously; infer() itself stays non-blocking.
        if prompt and prompt != self._last_prompt_sent:
            self._last_prompt_sent = prompt
            self._enqueue_text(f"user_prompt: {prompt}")

        now_monotonic = time.monotonic()
        if context is not None and (
            now_monotonic - self._last_context_push_monotonic >= self._context_push_interval_sec
        ):
            self._last_context_push_monotonic = now_monotonic
            context_json = json.dumps(context, ensure_ascii=False, default=str)
            self._enqueue_text(f"runtime_context: {context_json}")

        controls = self._controls_for_time(now_monotonic)
        return MacroState(timestamp=time.time(), controls=controls)

    async def _run_supervisor(self) -> None:
        backoff_sec = 0.5

        while not self._stop_event.is_set():
            try:
                self._connection_state = "connecting"
                await self._run_session()
                backoff_sec = 0.5
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._connection_state = f"error:{exc.__class__.__name__}"
                self._last_error = str(exc)
                await asyncio.sleep(backoff_sec)
                backoff_sec = min(5.0, backoff_sec * 2.0)
            else:
                # Session closed gracefully (ex: go_away/rotation). Reconnect quickly.
                if not self._stop_event.is_set():
                    self._connection_state = "reconnecting"
                    await asyncio.sleep(0.2)

    async def _run_session(self) -> None:
        from google import genai
        from google.genai import types

        audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=64)
        video_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=4)
        session_stop = asyncio.Event()

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        config = self._build_live_config(types)

        async with client.aio.live.connect(model=self._model, config=config) as session:
            self._connection_state = "connected"
            self._last_error = None
            self._pending_partial_args.clear()

            # Prime tool-use behavior early to reduce natural-language drift.
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text=(
                                "Operate autonomously from live audio/video input. "
                                "Prioritize tool use over natural language. "
                                "Call set_macro_controls repeatedly (roughly every 1-2 seconds) "
                                "with meaningful parameter updates in [-1, 1]. "
                                "Only valid keys are: filter_macro, beat_repeat_macro, reverb_macro, eq_low_macro. "
                                "Do not use keys like filter, volume, pitch, tempo, eq_high, eq_mid, crossfade. "
                                "Interpret body language strongly: repeated fist pumping, rapid arm pushes, large up/down movement, "
                                "high facial excitement, and strong vocal energy mean build-up/high energy. "
                                "For high energy: push filter_macro up (0.5~1.0), reverb_macro up (0.2~0.8), "
                                "and pulse beat_repeat_macro (0.1~0.7) briefly. "
                                "Interpret pre-drop tension cues (focused face, preparing posture, reduced movement, anticipation) "
                                "as controlled build: keep filter high, reverb moderate, beat repeat restrained. "
                                "Interpret calm/down energy (small movement, relaxed posture, low vocal intensity) "
                                "as low intensity: reduce effects and move toward neutral. "
                                "Do not output long explanations; prefer tool calls."
                            )
                        )
                    ],
                ),
                turn_complete=True,
            )

            tasks = [
                asyncio.create_task(
                    self._listen_audio(audio_queue=audio_queue, session_stop=session_stop),
                    name="ai_agent_listen_audio",
                ),
                asyncio.create_task(
                    self._listen_video(video_queue=video_queue, session_stop=session_stop),
                    name="ai_agent_listen_video",
                ),
                asyncio.create_task(
                    self._send_realtime(
                        session=session,
                        types_mod=types,
                        audio_queue=audio_queue,
                        video_queue=video_queue,
                        session_stop=session_stop,
                    ),
                    name="ai_agent_send_realtime",
                ),
                asyncio.create_task(
                    self._receive_from_gemini(
                        session=session,
                        types_mod=types,
                        session_stop=session_stop,
                    ),
                    name="ai_agent_receive",
                ),
            ]

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            session_stop.set()

            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise exc

    def _build_live_config(self, types_mod: Any) -> Any:
        properties = {name: {"type": "number", "minimum": -1.0, "maximum": 1.0} for name in MACRO_TARGETS}
        function_schema = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }

        function_decl = types_mod.FunctionDeclaration(
            name=MACRO_FUNCTION_NAME,
            description=(
                "Set one or more DJ macro controls in bipolar range [-1.0, 1.0]. "
                "0.0 means neutral."
            ),
            parameters_json_schema=function_schema,
        )

        tool = types_mod.Tool(function_declarations=[function_decl])

        session_resumption = (
            types_mod.SessionResumptionConfig(handle=self._session_handle)
            if self._session_handle
            else None
        )
        compression = types_mod.ContextWindowCompressionConfig(
            trigger_tokens=24000,
            sliding_window=types_mod.SlidingWindow(target_tokens=12000),
        )

        system_instruction = (
            "You are an AI DJ macro controller. "
            "Prioritize tool call 'set_macro_controls' over natural language. "
            "Only emit values in [-1.0, 1.0]. "
            "Do not narrate internal reasoning when tool call is applicable. "
            "Valid argument keys are strictly: filter_macro, beat_repeat_macro, reverb_macro, eq_low_macro. "
            "Do not stay static at neutral unless the live scene is truly static. "
            "Map energetic gestures (fist pumps, push-up motions, fast movement) to stronger macro changes. "
            "Map calm pre-drop anticipation to controlled tension, not random spikes."
        )

        # Native-audio preview models are configured with AUDIO response modality.
        # We keep text observability via output_audio_transcription.
        if "native-audio" in self._model:
            response_modalities = ["AUDIO"]
            output_audio_transcription = types_mod.AudioTranscriptionConfig()
        else:
            response_modalities = ["TEXT"]
            output_audio_transcription = None

        return types_mod.LiveConnectConfig(
            response_modalities=response_modalities,
            system_instruction=system_instruction,
            tools=[tool],
            session_resumption=session_resumption,
            context_window_compression=compression,
            output_audio_transcription=output_audio_transcription,
        )

    async def _listen_audio(self, *, audio_queue: asyncio.Queue[bytes], session_stop: asyncio.Event) -> None:
        try:
            import pyaudio
        except ImportError as exc:
            raise RuntimeError(
                "PyAudio is required for --gemini-live audio input. "
                "Install portaudio and pyaudio (brew install portaudio && pip install pyaudio)."
            ) from exc

        loop = asyncio.get_running_loop()
        audio = pyaudio.PyAudio()

        def _on_audio(in_data: bytes, frame_count: int, time_info: Any, status_flags: int) -> tuple[None, int]:
            _ = frame_count, time_info, status_flags
            loop.call_soon_threadsafe(self._queue_put_latest, audio_queue, in_data)
            return (None, pyaudio.paContinue)

        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._audio_rate_hz,
            input=True,
            frames_per_buffer=self._audio_frames_per_chunk,
            stream_callback=_on_audio,
        )

        try:
            stream.start_stream()
            while not self._stop_event.is_set() and not session_stop.is_set():
                await asyncio.sleep(0.05)
        finally:
            with contextlib.suppress(Exception):
                stream.stop_stream()
            with contextlib.suppress(Exception):
                stream.close()
            with contextlib.suppress(Exception):
                audio.terminate()

    async def _listen_video(self, *, video_queue: asyncio.Queue[bytes], session_stop: asyncio.Event) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("opencv-python is required for --gemini-live video input.") from exc

        capture = cv2.VideoCapture(0)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("Could not open default camera for Gemini Live video input.")

        frame_interval_sec = 1.0 / self._video_fps
        last_frame_at = 0.0

        try:
            while not self._stop_event.is_set() and not session_stop.is_set():
                now = time.monotonic()
                wait_sec = frame_interval_sec - (now - last_frame_at)
                if wait_sec > 0:
                    await asyncio.sleep(wait_sec)

                ok, frame = capture.read()
                if not ok:
                    await asyncio.sleep(0.05)
                    continue

                encoded_ok, encoded = cv2.imencode(".jpg", frame)
                if not encoded_ok:
                    continue

                self._queue_put_latest(video_queue, encoded.tobytes())
                last_frame_at = time.monotonic()
        finally:
            with contextlib.suppress(Exception):
                capture.release()

    async def _send_realtime(
        self,
        *,
        session: Any,
        types_mod: Any,
        audio_queue: asyncio.Queue[bytes],
        video_queue: asyncio.Queue[bytes],
        session_stop: asyncio.Event,
    ) -> None:
        while not self._stop_event.is_set() and not session_stop.is_set():
            await self._flush_text_queue(session=session, types_mod=types_mod)

            audio_chunk: bytes | None = None
            video_frame: bytes | None = None

            with contextlib.suppress(asyncio.QueueEmpty):
                audio_chunk = audio_queue.get_nowait()

            with contextlib.suppress(asyncio.QueueEmpty):
                while True:
                    video_frame = video_queue.get_nowait()

            if audio_chunk is None and video_frame is None:
                await asyncio.sleep(0.01)
                continue

            if audio_chunk is not None:
                await session.send_realtime_input(
                    audio=types_mod.Blob(
                        data=audio_chunk,
                        mime_type=f"audio/pcm;rate={self._audio_rate_hz}",
                    )
                )
            if video_frame is not None:
                await session.send_realtime_input(
                    video=types_mod.Blob(
                        data=video_frame,
                        mime_type="image/jpeg",
                    )
                )

    async def _flush_text_queue(self, *, session: Any, types_mod: Any) -> None:
        while True:
            try:
                text = self._text_queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            turn_complete = True
            body = text

            if text.startswith("runtime_context:"):
                turn_complete = False
                body = text[len("runtime_context:") :].strip()
            elif text.startswith("user_prompt:"):
                turn_complete = True
                body = text[len("user_prompt:") :].strip()

            await session.send_client_content(
                turns=types_mod.Content(
                    role="user",
                    parts=[types_mod.Part(text=body)],
                ),
                turn_complete=turn_complete,
            )

    async def _receive_from_gemini(self, *, session: Any, types_mod: Any, session_stop: asyncio.Event) -> None:
        async for message in session.receive():
            if self._stop_event.is_set() or session_stop.is_set():
                return

            if message.session_resumption_update and message.session_resumption_update.new_handle:
                self._session_handle = message.session_resumption_update.new_handle

            if message.go_away is not None:
                self._connection_state = "go_away"
                return

            if message.server_content and message.server_content.model_turn:
                text_parts: list[str] = []
                for part in message.server_content.model_turn.parts or []:
                    if part.text:
                        text_parts.append(part.text)
                if text_parts:
                    self._last_server_text = "".join(text_parts)
                    self._last_error = None

            if message.server_content and message.server_content.output_transcription:
                text = getattr(message.server_content.output_transcription, "text", None)
                if text:
                    self._last_server_text = text
                    self._last_error = None

            tool_call = message.tool_call
            if tool_call is None or not tool_call.function_calls:
                continue

            function_responses = []
            for call in tool_call.function_calls:
                call_id = call.id or ""

                # Live may stream function arguments incrementally.
                if call.will_continue:
                    if isinstance(call.partial_args, str):
                        self._pending_partial_args[call_id] = self._pending_partial_args.get(call_id, "") + call.partial_args
                    continue

                parsed_args: Mapping[str, Any] | None = call.args if isinstance(call.args, Mapping) else None
                if parsed_args is None:
                    partial_text = self._pending_partial_args.pop(call_id, "")
                    if isinstance(call.partial_args, str):
                        partial_text += call.partial_args
                    if partial_text:
                        try:
                            loaded = json.loads(partial_text)
                        except json.JSONDecodeError:
                            loaded = None
                        if isinstance(loaded, Mapping):
                            parsed_args = loaded

                accepted, error = self._validate_macro_args(call.name, parsed_args)
                if error is None:
                    payload = {"status": "ok", "accepted": accepted}
                else:
                    payload = {"status": "error", "error": error}
                    self._last_error = payload["error"]
                function_responses.append(
                    types_mod.FunctionResponse(
                        id=call.id,
                        name=call.name,
                        response=payload,
                    )
                )

            if function_responses:
                await session.send_tool_response(function_responses=function_responses)

    def _validate_macro_args(self, function_name: str | None, args: Mapping[str, Any] | None) -> tuple[dict[str, float], str | None]:
        if function_name != MACRO_FUNCTION_NAME:
            return {}, f"unsupported_function:{function_name}"

        if not isinstance(args, Mapping):
            return {}, "invalid_args:object_required"

        if not args:
            return {}, "invalid_args:empty_payload"

        parsed: dict[str, float] = {}
        unknown_fields: list[str] = []
        for key, raw in args.items():
            canonical = MACRO_FIELD_ALIASES.get(key, key)
            if canonical not in MACRO_TARGET_SET:
                unknown_fields.append(key)
                continue

            try:
                value = float(raw)
            except (TypeError, ValueError):
                return {}, f"invalid_args:not_number:{canonical}"

            if value < -1.0 or value > 1.0:
                return {}, f"invalid_args:out_of_range:{canonical}"
            parsed[canonical] = value

        if not parsed:
            unknown_csv = ",".join(sorted(unknown_fields))
            return {}, f"invalid_args:unknown_fields:{unknown_csv}"

        self._latest_macro_controls.update(parsed)
        self._last_tool_call_monotonic = time.monotonic()
        return parsed, None

    def _controls_for_time(self, now_monotonic: float) -> dict[str, float]:
        if not self._latest_macro_controls or self._last_tool_call_monotonic is None:
            return {}

        elapsed = now_monotonic - self._last_tool_call_monotonic
        if elapsed <= self._hold_sec:
            return dict(self._latest_macro_controls)

        ramp_elapsed = elapsed - self._hold_sec
        alpha = min(1.0, max(0.0, ramp_elapsed / self._neutral_ramp_sec))

        return {
            name: self._latest_macro_controls.get(name, 0.0) * (1.0 - alpha)
            for name in MACRO_TARGETS
        }

    def _enqueue_text(self, text: str) -> None:
        self._queue_put_latest(self._text_queue, text)

    @staticmethod
    def _queue_put_latest(queue: asyncio.Queue[Any], item: Any) -> None:
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(item)
