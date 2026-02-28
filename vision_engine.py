from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass
class VisionState:
    """Micro-control payload in bipolar range (-1.0 ~ 1.0)."""

    timestamp: float
    controls: dict[str, float]


class VisionEngine:
    """Local MediaPipe-facing adapter (placeholder).

    Macro-First phase keeps micro controls disabled by default.
    Re-enable gesture-to-control mapping in the next integration phase.
    """

    def __init__(self) -> None:
        self._last = VisionState(timestamp=time(), controls={})

    def poll(self) -> VisionState:
        # TODO (next phase): map gesture landmarks to bipolar controls.
        # Example output:
        # {
        #   "filter_macro": 0.4,
        #   "eq_low_macro": -0.25,
        # }
        return self._last
