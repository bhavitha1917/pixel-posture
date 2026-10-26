"""Temporal filtering for one posture signal: smoothing, hysteresis, timers and recovery."""

from __future__ import annotations

import math

from app.posture.config import SeverityLevels, TimingConfig
from app.posture.models import BackComponent, SignalKind, SignalLevel, SignalStatus


class SignalTracker:
    """Turns a stream of raw severities into a debounced :class:`SignalStatus`.

    * Smoothing is a time-based EMA, so irregular frame intervals are handled correctly.
    * An *issue episode* starts when the smoothed severity reaches ``levels.enter`` and ends
      only after it has stayed below ``levels.exit`` for ``timing.recovery_s``.
    * Critical needs a clearly larger deviation (``levels.critical``) that has itself lasted
      ``timing.critical_s``; it falls back to Warning below ``levels.critical_exit``.
    * An episode is not escalated to Warning while the user is visibly improving (severity
      below ``levels.exit``), so a short slouch that is already being corrected never warns.
    * Missing measurements are never treated as good posture: they do not advance recovery,
      and after ``timing.missing_grace_s`` the tracker resets and reports UNAVAILABLE.
    """

    def __init__(self, kind: SignalKind, timing: TimingConfig, levels: SeverityLevels) -> None:
        self.kind = kind
        self._timing = timing
        self._levels = levels
        self.reset()

    def configure(self, timing: TimingConfig, levels: SeverityLevels) -> None:
        """Apply new thresholds without discarding the current episode."""
        self._timing = timing
        self._levels = levels

    def reset(self) -> None:
        self._smoothed: float | None = None
        self._last_seen: float | None = None
        self._episode_start: float | None = None
        self._improving_since: float | None = None
        self._severe_since: float | None = None
        self._critical = False
        self._warned = False
        self._component: BackComponent | None = None

    def update(
        self,
        now: float,
        severity: float | None,
        component: BackComponent | None = None,
    ) -> SignalStatus:
        if severity is None or not math.isfinite(severity):
            return self._handle_missing(now)

        # A silent gap (e.g. laptop sleep: no observations at all) is missing data too.
        if self._last_seen is not None and now - self._last_seen > self._timing.missing_grace_s:
            self.reset()

        if self._smoothed is None or self._last_seen is None:
            self._smoothed = severity
        else:
            dt = max(0.0, now - self._last_seen)
            alpha = 1.0 - math.exp(-dt / self._timing.smoothing_tau_s)
            self._smoothed += alpha * (severity - self._smoothed)
        self._last_seen = now
        if component is not None:
            self._component = component

        self._advance_episode(now, self._smoothed)
        return self._status(now)

    def _handle_missing(self, now: float) -> SignalStatus:
        if self._last_seen is None or now - self._last_seen > self._timing.missing_grace_s:
            self.reset()
            return SignalStatus(self.kind, SignalLevel.UNAVAILABLE, None, 0.0)
        # Short gap: hold the current state, but recovery must start over.
        self._improving_since = None
        return self._status(now)

    def _advance_episode(self, now: float, smoothed: float) -> None:
        levels, timing = self._levels, self._timing
        if self._episode_start is None:
            if smoothed >= levels.enter:
                self._episode_start = now
                self._improving_since = None
                self._severe_since = None
                self._critical = False
                self._warned = False
            return

        if smoothed < levels.exit:
            if self._improving_since is None:
                self._improving_since = now
            elif now - self._improving_since >= timing.recovery_s:
                self._episode_start = None
                self._improving_since = None
                self._severe_since = None
                self._critical = False
                self._warned = False
                return
        else:
            self._improving_since = None

        duration = now - self._episode_start
        if duration >= timing.warning_s and self._improving_since is None:
            self._warned = True
        # The severe run starts at levels.critical and survives dips down to critical_exit.
        if smoothed < levels.critical_exit:
            self._severe_since = None
            self._critical = False
        elif self._severe_since is None:
            if smoothed >= levels.critical:
                self._severe_since = now
        elif not self._critical and now - self._severe_since >= timing.critical_s:
            self._critical = True

    def _status(self, now: float) -> SignalStatus:
        if self._episode_start is None:
            level = SignalLevel.OK
            duration = 0.0
        else:
            duration = now - self._episode_start
            if self._critical:
                level = SignalLevel.CRITICAL
            elif self._warned:
                level = SignalLevel.WARNING
            else:
                level = SignalLevel.DEVIATING
        component = self._component if self.kind is SignalKind.BACK else None
        return SignalStatus(self.kind, level, self._smoothed, duration, component)
