"""Posture-engine configuration.

Every threshold is an *experimental default*, not a clinically validated value. The README
(sections 10-12) explains what each one means.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum


class Sensitivity(StrEnum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    STRICT = "strict"

    @property
    def tolerance_multiplier(self) -> float:
        # Larger tolerances = fewer reminders.
        return {"relaxed": 1.35, "balanced": 1.0, "strict": 0.75}[self.value]


@dataclass(frozen=True)
class Tolerances:
    """How far each feature may drift from the baseline before it counts as a deviation."""

    neck_drop: float = 0.15  # relative shortening of the ear-to-shoulder gap
    torso_drop: float = 0.20  # downward shoulder movement, in baseline shoulder-widths
    forward_lean: float = 0.15  # relative increase in apparent shoulder width
    side_lean_deg: float = 7.0  # change in shoulder-line angle
    head_pitch_deg: float = 12.0  # additional downward head pitch

    def scaled(self, multiplier: float) -> Tolerances:
        return Tolerances(
            neck_drop=self.neck_drop * multiplier,
            torso_drop=self.torso_drop * multiplier,
            forward_lean=self.forward_lean * multiplier,
            side_lean_deg=self.side_lean_deg * multiplier,
            head_pitch_deg=self.head_pitch_deg * multiplier,
        )


@dataclass(frozen=True)
class TimingConfig:
    warning_s: float = 10.0  # issue-episode duration before Warning
    critical_s: float = 30.0  # issue-episode duration before Critical (severity also required)
    recovery_s: float = 3.0  # sustained improvement needed to end an episode
    smoothing_tau_s: float = 1.0  # EMA time constant; time-based so frame rate does not matter
    missing_grace_s: float = 2.0  # how long missing data is tolerated before a tracker resets


@dataclass(frozen=True)
class SeverityLevels:
    """Severity is deviation / tolerance, so 1.0 means 'at the edge of the tolerance'."""

    enter: float = 1.0  # start an issue episode
    exit: float = 0.7  # below this counts as improvement (hysteresis gap 0.7-1.0)
    critical: float = 1.3  # needed (with critical_s) to escalate to Critical
    critical_exit: float = 1.1  # Critical falls back to Warning below this


@dataclass(frozen=True)
class LandmarkQuality:
    min_visibility: float = 0.5
    min_shoulder_width: float = 0.08  # in frame heights; smaller means too far away or garbage
    max_yaw_deviation_deg: float = 35.0  # beyond this, the head-pitch estimate is unreliable


@dataclass(frozen=True)
class CalibrationConfig:
    min_samples: int = 25
    timeout_s: float = 12.0
    # Stability limits use the interquartile range (IQR): robust to a few outlier frames,
    # unlike the standard deviation, and unlike the MAD it still catches a user alternating
    # between two poses.
    max_pitch_iqr_deg: float = 8.0
    max_shoulder_angle_iqr_deg: float = 6.0
    max_neck_ratio_rel_iqr: float = 0.16
    max_shoulder_width_rel_iqr: float = 0.12
    min_neck_ratio: float = 0.05  # ears must sit clearly above the shoulders


@dataclass(frozen=True)
class PostureConfig:
    tolerances: Tolerances = field(default_factory=Tolerances)
    sensitivity: Sensitivity = Sensitivity.BALANCED
    timing: TimingConfig = field(default_factory=TimingConfig)
    levels: SeverityLevels = field(default_factory=SeverityLevels)
    quality: LandmarkQuality = field(default_factory=LandmarkQuality)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)

    def effective_tolerances(self) -> Tolerances:
        return self.tolerances.scaled(self.sensitivity.tolerance_multiplier)

    def with_timing(self, **changes: float) -> PostureConfig:
        return replace(self, timing=replace(self.timing, **changes))
