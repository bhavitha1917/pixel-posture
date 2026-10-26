"""Typed data structures shared by the vision layer, the posture engine and the UI.

Conventions
-----------
* Timestamps are seconds from a monotonic clock (``time.monotonic``).
* Body geometry uses aspect-corrected image coordinates: x and y are both expressed in
  units of frame *height*, y points down. Values are relative proxies, not anatomy.
* Head angles are degrees. ``pitch_down_deg`` is positive when the face points downward.
* Severity is ``deviation / tolerance``: 0 = at baseline, 1.0 = at the edge of tolerance.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class SignalKind(StrEnum):
    BACK = "back"
    HEAD = "head"


class SignalLevel(StrEnum):
    UNAVAILABLE = "unavailable"  # no reliable measurement
    OK = "ok"  # within tolerance (or recovered)
    DEVIATING = "deviating"  # issue episode started, shorter than the warning duration
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _LEVEL_RANK[self]


_LEVEL_RANK = {
    SignalLevel.UNAVAILABLE: 0,
    SignalLevel.OK: 1,
    SignalLevel.DEVIATING: 2,
    SignalLevel.WARNING: 3,
    SignalLevel.CRITICAL: 4,
}


class PetState(StrEnum):
    CALIBRATING = "calibrating"
    THRIVING = "thriving"
    WARNING = "warning"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


class BackComponent(StrEnum):
    HUNCHING = "hunching"  # ear-to-shoulder gap shrinking
    SINKING = "sinking"  # shoulders lower in the frame
    LEANING_IN = "leaning_in"  # closer to the screen
    SIDE_LEAN = "side_lean"  # shoulder line tilted


@dataclass(frozen=True)
class BodyFeatures:
    shoulder_mid_y: float
    shoulder_width: float
    shoulder_angle_deg: float
    neck_ratio: float  # vertical ear-to-shoulder gap / shoulder width
    min_visibility: float


@dataclass(frozen=True)
class HeadFeatures:
    pitch_down_deg: float
    yaw_deg: float


@dataclass(frozen=True)
class Observation:
    """What the vision layer saw in one frame. Immutable, so it is safe to pass across threads."""

    timestamp: float
    body: BodyFeatures | None
    head: HeadFeatures | None
    body_issue: str | None = None  # why ``body`` is None
    head_issue: str | None = None  # why ``head`` is None
    frame_width: int = 0
    frame_height: int = 0

    @property
    def tracking_available(self) -> bool:
        return self.body is not None or self.head is not None


@dataclass(frozen=True)
class Baseline:
    """Calibrated neutral posture (medians over many frames). Numbers only, no images."""

    neck_ratio: float
    shoulder_mid_y: float
    shoulder_width: float
    shoulder_angle_deg: float
    pitch_down_deg: float
    yaw_deg: float
    camera_index: int
    frame_width: int
    frame_height: int
    created_at: str  # ISO-8601

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: object) -> Baseline | None:
        """Build a baseline from untrusted JSON; returns None if anything is invalid."""
        if not isinstance(data, dict):
            return None
        try:
            baseline = cls(
                neck_ratio=float(data["neck_ratio"]),
                shoulder_mid_y=float(data["shoulder_mid_y"]),
                shoulder_width=float(data["shoulder_width"]),
                shoulder_angle_deg=float(data["shoulder_angle_deg"]),
                pitch_down_deg=float(data["pitch_down_deg"]),
                yaw_deg=float(data["yaw_deg"]),
                camera_index=int(data["camera_index"]),
                frame_width=int(data["frame_width"]),
                frame_height=int(data["frame_height"]),
                created_at=str(data["created_at"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        numbers = (
            baseline.neck_ratio,
            baseline.shoulder_mid_y,
            baseline.shoulder_width,
            baseline.shoulder_angle_deg,
            baseline.pitch_down_deg,
            baseline.yaw_deg,
        )
        if not all(math.isfinite(n) for n in numbers):
            return None
        if baseline.neck_ratio <= 0 or baseline.shoulder_width <= 0 or baseline.camera_index < 0:
            return None
        return baseline

    def matches_camera(self, camera_index: int, frame_width: int, frame_height: int) -> bool:
        return (
            self.camera_index == camera_index
            and self.frame_width == frame_width
            and self.frame_height == frame_height
        )


@dataclass(frozen=True)
class SignalStatus:
    kind: SignalKind
    level: SignalLevel
    severity: float | None  # smoothed; None when unavailable
    issue_duration_s: float  # 0 when there is no issue episode
    dominant_component: BackComponent | None = None  # back signal only

    @property
    def available(self) -> bool:
        return self.level is not SignalLevel.UNAVAILABLE

    @property
    def in_episode(self) -> bool:
        return self.level.rank >= SignalLevel.DEVIATING.rank


@dataclass(frozen=True)
class CalibrationOutcome:
    success: bool
    baseline: Baseline | None
    reason: str | None  # user-facing explanation when unsuccessful


@dataclass(frozen=True)
class PostureResult:
    """Everything the UI and alert policy need for one update."""

    timestamp: float
    state: PetState
    tracking_available: bool
    body_valid: bool
    head_valid: bool
    back: SignalStatus
    head: SignalStatus
    active_issue: SignalKind | None
    title: str
    message: str
    calibration_progress: float | None = None  # 0..1 while calibrating
    calibration_outcome: CalibrationOutcome | None = None  # set on the update that finished it

    def signal(self, kind: SignalKind) -> SignalStatus:
        return self.back if kind is SignalKind.BACK else self.head
