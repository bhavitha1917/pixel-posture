"""Pure geometry: landmarks -> posture features -> deviation from a baseline.

See ``models.py`` for the coordinate conventions.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.posture.config import LandmarkQuality, Tolerances
from app.posture.models import BackComponent, Baseline, BodyFeatures, HeadFeatures

# MediaPipe Pose landmark indices (33-point topology).
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
POSE_LANDMARK_COUNT = 33


@dataclass(frozen=True)
class LandmarkPoint:
    """A normalized image landmark (x, y in [0, 1] of width/height) with a visibility score."""

    x: float
    y: float
    visibility: float


def compute_body_features(
    landmarks: Sequence[LandmarkPoint],
    frame_width: int,
    frame_height: int,
    quality: LandmarkQuality,
) -> tuple[BodyFeatures | None, str | None]:
    """Return body features, or ``(None, reason)`` when the landmarks are not trustworthy."""
    if len(landmarks) < POSE_LANDMARK_COUNT or frame_width <= 0 or frame_height <= 0:
        return None, "No person detected"

    aspect = frame_width / frame_height
    left_sh, right_sh = landmarks[LEFT_SHOULDER], landmarks[RIGHT_SHOULDER]

    for point in (left_sh, right_sh):
        if not all(math.isfinite(v) for v in (point.x, point.y, point.visibility)):
            return None, "Invalid landmark values"
        if point.visibility < quality.min_visibility:
            return None, "Both shoulders must be visible"
        if not (0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0):
            return None, "Shoulders are outside the camera view"

    ears = [
        landmarks[i]
        for i in (LEFT_EAR, RIGHT_EAR)
        if landmarks[i].visibility >= quality.min_visibility
        and math.isfinite(landmarks[i].x)
        and math.isfinite(landmarks[i].y)
    ]
    if not ears:
        return None, "Head is not clearly visible"

    # Aspect-corrected coordinates: everything in units of frame height.
    lx, ly = left_sh.x * aspect, left_sh.y
    rx, ry = right_sh.x * aspect, right_sh.y
    shoulder_width = math.hypot(lx - rx, ly - ry)
    if shoulder_width < quality.min_shoulder_width:
        return None, "Too far from the camera"

    shoulder_mid_y = (ly + ry) / 2.0
    ear_mid_y = sum(e.y for e in ears) / len(ears)
    # The subject's left shoulder appears on the image right in an un-mirrored frame, so
    # this is ~0 deg when the shoulders are level. Only changes relative to baseline matter.
    shoulder_angle = math.degrees(math.atan2(ly - ry, lx - rx))

    return (
        BodyFeatures(
            shoulder_mid_y=shoulder_mid_y,
            shoulder_width=shoulder_width,
            shoulder_angle_deg=shoulder_angle,
            neck_ratio=(shoulder_mid_y - ear_mid_y) / shoulder_width,
            min_visibility=min(left_sh.visibility, right_sh.visibility),
        ),
        None,
    )


def head_angles_from_matrix(matrix: npt.ArrayLike) -> HeadFeatures | None:
    """Extract head pitch/yaw from MediaPipe's 4x4 facial transformation matrix.

    The matrix maps the canonical face model (right-handed, y up, face looking along +z;
    checked against ``canonical_face_model.obj``: nose tip z=+7.5, forehead y=+8.3) into the
    camera's metric space. The face's forward axis in camera space is column 2 of the
    rotation. Looking down tips that axis toward -y, so ``asin(-R[1][2])`` is positive when
    the head is pitched downward.
    """
    m = np.asarray(matrix, dtype=float)
    if m.shape != (4, 4) or not np.all(np.isfinite(m)):
        return None
    rotation = m[:3, :3]
    # Remove any uniform scale so the columns are unit vectors.
    norms = np.linalg.norm(rotation, axis=0)
    if np.any(norms < 1e-9):
        return None
    rotation = rotation / norms
    forward = rotation[:, 2]
    pitch_down = math.degrees(math.asin(float(np.clip(-forward[1], -1.0, 1.0))))
    yaw = math.degrees(math.atan2(float(forward[0]), float(forward[2])))
    return HeadFeatures(pitch_down_deg=pitch_down, yaw_deg=yaw)


@dataclass(frozen=True)
class BackDeviation:
    """Per-component deviation (positive = worse) and the combined severity."""

    hunching: float
    sinking: float
    leaning_in: float
    side_lean_deg: float
    severity: float
    dominant: BackComponent


def back_deviation(
    features: BodyFeatures, baseline: Baseline, tolerances: Tolerances
) -> BackDeviation:
    hunching = (baseline.neck_ratio - features.neck_ratio) / baseline.neck_ratio
    sinking = (features.shoulder_mid_y - baseline.shoulder_mid_y) / baseline.shoulder_width
    leaning_in = features.shoulder_width / baseline.shoulder_width - 1.0
    side_lean = abs(features.shoulder_angle_deg - baseline.shoulder_angle_deg)

    ratios = {
        BackComponent.HUNCHING: max(0.0, hunching) / tolerances.neck_drop,
        BackComponent.SINKING: max(0.0, sinking) / tolerances.torso_drop,
        BackComponent.LEANING_IN: max(0.0, leaning_in) / tolerances.forward_lean,
        BackComponent.SIDE_LEAN: side_lean / tolerances.side_lean_deg,
    }
    dominant = max(ratios, key=lambda c: ratios[c])
    return BackDeviation(
        hunching=hunching,
        sinking=sinking,
        leaning_in=leaning_in,
        side_lean_deg=side_lean,
        severity=ratios[dominant],
        dominant=dominant,
    )


def head_severity(
    features: HeadFeatures,
    baseline: Baseline,
    tolerances: Tolerances,
    quality: LandmarkQuality,
) -> float | None:
    """Downward-pitch severity, or None when the user is turned too far for a reliable pitch."""
    if abs(features.yaw_deg - baseline.yaw_deg) > quality.max_yaw_deviation_deg:
        return None
    extra_pitch = features.pitch_down_deg - baseline.pitch_down_deg
    return max(0.0, extra_pitch) / tolerances.head_pitch_deg
