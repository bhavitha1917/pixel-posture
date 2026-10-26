"""Shared factories for deterministic posture tests.

These build *synthetic observations* that feed the real posture modules; there is no
separate fake posture implementation.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest

# Qt tests run headless (also in CI).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.posture.config import PostureConfig, Tolerances
from app.posture.models import Baseline, BodyFeatures, HeadFeatures, Observation

BASE_NECK = 0.6
BASE_MID_Y = 0.7
BASE_WIDTH = 0.3
BASE_ANGLE = 0.0
BASE_PITCH = 10.0
BASE_YAW = 0.0
TOL = Tolerances()
# Mechanism tests use short timers (the version-1 defaults) so they stay fast and readable.
# test_default_timing.py exercises the shipped defaults.
SHORT = {"warning_s": 10.0, "critical_s": 30.0, "recovery_s": 3.0}


def short_config(**kwargs: object) -> PostureConfig:
    return PostureConfig(**kwargs).with_timing(**SHORT)  # type: ignore[arg-type]


def make_baseline(**overrides: float) -> Baseline:
    values: dict[str, object] = {
        "neck_ratio": BASE_NECK,
        "shoulder_mid_y": BASE_MID_Y,
        "shoulder_width": BASE_WIDTH,
        "shoulder_angle_deg": BASE_ANGLE,
        "pitch_down_deg": BASE_PITCH,
        "yaw_deg": BASE_YAW,
        "camera_index": 0,
        "frame_width": 640,
        "frame_height": 480,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    values.update(overrides)
    return Baseline(**values)  # type: ignore[arg-type]


def body(lean_severity: float = 0.0, **overrides: float) -> BodyFeatures:
    """Body features whose 'leaning in' severity equals ``lean_severity`` (balanced)."""
    values = {
        "shoulder_mid_y": BASE_MID_Y,
        "shoulder_width": BASE_WIDTH * (1 + TOL.forward_lean * lean_severity),
        "shoulder_angle_deg": BASE_ANGLE,
        "neck_ratio": BASE_NECK,
        "min_visibility": 0.99,
    }
    values.update(overrides)
    return BodyFeatures(**values)


def head(pitch_severity: float = 0.0, yaw: float = BASE_YAW) -> HeadFeatures:
    """Head features whose downward-pitch severity equals ``pitch_severity`` (balanced)."""
    return HeadFeatures(
        pitch_down_deg=BASE_PITCH + TOL.head_pitch_deg * pitch_severity, yaw_deg=yaw
    )


def obs(
    t: float,
    back_sev: float | None = 0.0,
    head_sev: float | None = 0.0,
) -> Observation:
    return Observation(
        timestamp=t,
        body=None if back_sev is None else body(back_sev),
        head=None if head_sev is None else head(head_sev),
        body_issue=None if back_sev is not None else "Both shoulders must be visible",
        head_issue=None if head_sev is not None else "Face not detected",
        frame_width=640,
        frame_height=480,
    )


def timeline(start: float, end: float, fps: float) -> Iterator[float]:
    """Evenly spaced timestamps in [start, end)."""
    step = 1.0 / fps
    n = 0
    while (t := start + n * step) < end - 1e-9:
        yield t
        n += 1


ObsFactory = Callable[..., Observation]


@pytest.fixture
def baseline() -> Baseline:
    return make_baseline()
