"""Calibration: learn the user's neutral posture from many stable frames."""

from __future__ import annotations

from collections import Counter, deque
from datetime import UTC, datetime

import numpy as np

from app.posture.config import CalibrationConfig
from app.posture.models import Baseline, CalibrationOutcome, Observation


def _iqr(values: np.ndarray) -> float:
    q1, q3 = np.percentile(values, [25, 75])
    return float(q3 - q1)


class Calibrator:
    """Collects observations until a stable window of valid frames is found or time runs out.

    Each frame must contain *both* valid body and head features. The most recent
    ``min_samples`` valid frames form a sliding window; calibration succeeds as soon as that
    window is stable, so a user who fidgets at first can still succeed by holding still.
    """

    def __init__(
        self,
        config: CalibrationConfig,
        camera_index: int,
        started_at: float,
    ) -> None:
        self._config = config
        self._camera_index = camera_index
        self._started_at = started_at
        self._window: deque[Observation] = deque(maxlen=config.min_samples)
        self._invalid_reasons: Counter[str] = Counter()
        self._last_unstable_reason: str | None = None

    @property
    def progress(self) -> float:
        return len(self._window) / self._config.min_samples

    def add(self, observation: Observation) -> CalibrationOutcome | None:
        """Feed one observation. Returns an outcome once calibration has finished."""
        if observation.body is not None and observation.head is not None:
            self._window.append(observation)
            if len(self._window) == self._config.min_samples:
                baseline, reason = self._try_build_baseline()
                if baseline is not None:
                    return CalibrationOutcome(success=True, baseline=baseline, reason=None)
                self._last_unstable_reason = reason
        else:
            reason = observation.body_issue or observation.head_issue or "Tracking unavailable"
            self._invalid_reasons[reason] += 1

        if observation.timestamp - self._started_at >= self._config.timeout_s:
            return CalibrationOutcome(success=False, baseline=None, reason=self._failure_reason())
        return None

    def _failure_reason(self) -> str:
        if self._last_unstable_reason is not None:
            return self._last_unstable_reason
        if self._invalid_reasons:
            most_common, _ = self._invalid_reasons.most_common(1)[0]
            return f"Not enough clear frames: {most_common.lower()}."
        return "Not enough clear frames. Make sure your face and both shoulders are visible."

    def _try_build_baseline(self) -> tuple[Baseline | None, str | None]:
        cfg = self._config
        bodies = [o.body for o in self._window if o.body is not None]
        heads = [o.head for o in self._window if o.head is not None]
        neck = np.array([b.neck_ratio for b in bodies])
        mid_y = np.array([b.shoulder_mid_y for b in bodies])
        width = np.array([b.shoulder_width for b in bodies])
        angle = np.array([b.shoulder_angle_deg for b in bodies])
        pitch = np.array([h.pitch_down_deg for h in heads])
        yaw = np.array([h.yaw_deg for h in heads])

        neck_med = float(np.median(neck))
        width_med = float(np.median(width))
        if neck_med < cfg.min_neck_ratio:
            return None, "Head and shoulders are not clearly separated. Sit upright and retry."

        unstable = (
            _iqr(pitch) > cfg.max_pitch_iqr_deg
            or _iqr(angle) > cfg.max_shoulder_angle_iqr_deg
            or _iqr(neck) / neck_med > cfg.max_neck_ratio_rel_iqr
            or _iqr(width) / width_med > cfg.max_shoulder_width_rel_iqr
        )
        if unstable:
            return None, "Too much movement. Please hold still for a few seconds."

        last = self._window[-1]
        return (
            Baseline(
                neck_ratio=neck_med,
                shoulder_mid_y=float(np.median(mid_y)),
                shoulder_width=width_med,
                shoulder_angle_deg=float(np.median(angle)),
                pitch_down_deg=float(np.median(pitch)),
                yaw_deg=float(np.median(yaw)),
                camera_index=self._camera_index,
                frame_width=last.frame_width,
                frame_height=last.frame_height,
                created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            ),
            None,
        )
