"""AlertPolicy: decides *when* a reminder should be sent. Pure logic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass

from app.posture.engine import RECOVERY_MESSAGE, issue_message
from app.posture.models import PetState, PostureResult, SignalKind, SignalLevel

WARNING_TITLE = "Time for a posture check!"
CRITICAL_TITLE = "It's been a while. Time for a quick reset"
RECOVERY_TITLE = "Nice recovery!"

_ALERT_LEVELS = (SignalLevel.WARNING, SignalLevel.CRITICAL)


@dataclass(frozen=True)
class Alert:
    title: str
    message: str
    level: SignalLevel | None  # None for recovery alerts
    signal: SignalKind | None
    is_recovery: bool = False


class AlertPolicy:
    """Rate-limits and de-duplicates alerts.

    * Each (signal, level) fires at most once per issue episode.
    * A global cooldown separates alerts. An alert that becomes due during the cooldown is
      deferred, then delivered after the cooldown only if the condition still holds.
    * Calibrating / unavailable states suppress alerts; ``reset()`` (pause/stop) clears all.
    """

    def __init__(self, cooldown_s: float, notify_on_recovery: bool = False) -> None:
        self.cooldown_s = cooldown_s
        self.notify_on_recovery = notify_on_recovery
        self.reset()

    def reset(self) -> None:
        self._notified: dict[SignalKind, SignalLevel | None] = {k: None for k in SignalKind}
        self._last_sent: float | None = None
        self._prev_state: PetState | None = None
        self._episode_alerted = False

    def _cooldown_over(self, now: float) -> bool:
        return self._last_sent is None or now - self._last_sent >= self.cooldown_s

    def evaluate(self, result: PostureResult) -> Alert | None:
        now = result.timestamp
        prev_state, self._prev_state = self._prev_state, result.state

        # An episode that ended (or lost tracking) re-arms that signal's alerts.
        for kind in SignalKind:
            if not result.signal(kind).in_episode:
                self._notified[kind] = None

        if result.state in (PetState.CALIBRATING, PetState.UNAVAILABLE):
            self._episode_alerted = False
            return None

        if result.state is PetState.THRIVING and prev_state in (
            PetState.WARNING,
            PetState.CRITICAL,
        ):
            alerted, self._episode_alerted = self._episode_alerted, False
            if self.notify_on_recovery and alerted and self._cooldown_over(now):
                self._last_sent = now
                return Alert(RECOVERY_TITLE, RECOVERY_MESSAGE, None, None, is_recovery=True)
            return None

        due = [
            status
            for status in (result.back, result.head)
            if status.level in _ALERT_LEVELS
            and (
                (notified := self._notified[status.kind]) is None
                or status.level.rank > notified.rank
            )
        ]
        if not due or not self._cooldown_over(now):
            return None

        status = max(due, key=lambda s: (s.level.rank, s.issue_duration_s))
        self._notified[status.kind] = status.level
        self._last_sent = now
        self._episode_alerted = True
        title = CRITICAL_TITLE if status.level is SignalLevel.CRITICAL else WARNING_TITLE
        return Alert(title, issue_message(status), status.level, status.kind)
