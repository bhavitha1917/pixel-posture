"""Session statistics derived from real posture results (kept in memory only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.posture.models import PetState, PostureResult

# Gaps longer than this (e.g. laptop sleep) are not counted as monitored time.
MAX_COUNTED_GAP_S = 2.0


@dataclass
class SessionStats:
    monitored_s: float = 0.0
    thriving_s: float = 0.0
    tracked_s: float = 0.0  # time with a posture judgement (not calibrating / unavailable)
    alerts_sent: int = 0
    _last_timestamp: float | None = None

    def update(self, result: PostureResult) -> None:
        if self._last_timestamp is not None:
            dt = result.timestamp - self._last_timestamp
            if 0 < dt <= MAX_COUNTED_GAP_S:
                self.monitored_s += dt
                if result.state in (PetState.THRIVING, PetState.WARNING, PetState.CRITICAL):
                    self.tracked_s += dt
                if result.state is PetState.THRIVING:
                    self.thriving_s += dt
        self._last_timestamp = result.timestamp

    def mark_gap(self) -> None:
        """Called on pause so paused time is not counted."""
        self._last_timestamp = None

    @property
    def good_posture_share(self) -> float | None:
        if self.tracked_s < 1.0:
            return None
        return self.thriving_s / self.tracked_s
