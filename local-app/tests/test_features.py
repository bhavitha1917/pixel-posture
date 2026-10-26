import math

import numpy as np
import pytest
from conftest import BASE_PITCH, TOL, body, head, make_baseline

from app.posture.config import LandmarkQuality
from app.posture.features import (
    LEFT_EAR,
    LEFT_SHOULDER,
    POSE_LANDMARK_COUNT,
    RIGHT_EAR,
    RIGHT_SHOULDER,
    LandmarkPoint,
    back_deviation,
    compute_body_features,
    head_angles_from_matrix,
    head_severity,
)
from app.posture.models import BackComponent

Q = LandmarkQuality()


def pose(**points: tuple[float, float, float]) -> list[LandmarkPoint]:
    """33 landmarks, all invisible except the named ones."""
    lms = [LandmarkPoint(0.5, 0.5, 0.0) for _ in range(POSE_LANDMARK_COUNT)]
    index = {
        "left_sh": LEFT_SHOULDER,
        "right_sh": RIGHT_SHOULDER,
        "left_ear": LEFT_EAR,
        "right_ear": RIGHT_EAR,
    }
    for name, (x, y, v) in points.items():
        lms[index[name]] = LandmarkPoint(x, y, v)
    return lms


UPRIGHT = {
    "left_sh": (0.65, 0.8, 0.99),
    "right_sh": (0.35, 0.8, 0.99),
    "left_ear": (0.56, 0.5, 0.95),
    "right_ear": (0.44, 0.5, 0.95),
}


def test_upright_features_use_aspect_corrected_units():
    feats, reason = compute_body_features(pose(**UPRIGHT), 640, 480, Q)
    assert reason is None and feats is not None
    # 0.3 of width at 4:3 aspect is 0.4 frame heights.
    assert feats.shoulder_width == pytest.approx(0.4)
    assert feats.shoulder_angle_deg == pytest.approx(0.0)
    assert feats.neck_ratio == pytest.approx(0.3 / 0.4)
    assert feats.shoulder_mid_y == pytest.approx(0.8)


def test_shoulder_tilt_changes_angle():
    tilted = dict(UPRIGHT, left_sh=(0.65, 0.85, 0.99))
    feats, _ = compute_body_features(pose(**tilted), 640, 480, Q)
    assert feats is not None
    assert abs(feats.shoulder_angle_deg) == pytest.approx(math.degrees(math.atan2(0.05, 0.4)))


@pytest.mark.parametrize(
    ("change", "expected_reason"),
    [
        ({"left_sh": (0.65, 0.8, 0.2)}, "Both shoulders must be visible"),
        ({"right_sh": (0.35, 1.2, 0.9)}, "Shoulders are outside the camera view"),
        (
            {"left_ear": (0.5, 0.5, 0.1), "right_ear": (0.5, 0.5, 0.1)},
            "Head is not clearly visible",
        ),
        ({"left_sh": (0.51, 0.8, 0.99), "right_sh": (0.49, 0.8, 0.99)}, "Too far from the camera"),
        ({"left_sh": (float("nan"), 0.8, 0.99)}, "Invalid landmark values"),
    ],
)
def test_untrustworthy_landmarks_are_rejected(change, expected_reason):
    feats, reason = compute_body_features(pose(**dict(UPRIGHT, **change)), 640, 480, Q)
    assert feats is None
    assert reason == expected_reason


def test_missing_landmarks_mean_no_person():
    assert compute_body_features([], 640, 480, Q) == (None, "No person detected")


def test_one_visible_ear_is_enough():
    one_ear = dict(UPRIGHT, right_ear=(0.44, 0.5, 0.1))
    feats, _ = compute_body_features(pose(**one_ear), 640, 480, Q)
    assert feats is not None


def rot_x(deg: float) -> np.ndarray:
    a = math.radians(deg)
    m = np.eye(4)
    m[1:3, 1:3] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
    return m


def rot_y(deg: float) -> np.ndarray:
    a = math.radians(deg)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    return m


def test_identity_matrix_is_facing_camera():
    angles = head_angles_from_matrix(np.eye(4))
    assert angles is not None
    assert angles.pitch_down_deg == pytest.approx(0.0)
    assert angles.yaw_deg == pytest.approx(0.0)


def test_rotation_that_points_face_down_is_positive_pitch():
    # Rx(+20) maps the face's forward axis (0,0,1) to (0,-sin20,cos20): pointing downward.
    angles = head_angles_from_matrix(rot_x(20))
    assert angles is not None
    assert angles.pitch_down_deg == pytest.approx(20.0)
    up = head_angles_from_matrix(rot_x(-15))
    assert up is not None and up.pitch_down_deg == pytest.approx(-15.0)


def test_pitch_ignores_scale_and_translation_and_reports_yaw():
    m = rot_y(30) @ rot_x(10)
    m[:3, :3] *= 1.7
    m[:3, 3] = [3.0, -2.0, -40.0]
    angles = head_angles_from_matrix(m)
    assert angles is not None
    assert angles.yaw_deg == pytest.approx(30.0, abs=0.5)
    assert angles.pitch_down_deg == pytest.approx(10.0, abs=0.5)


def test_invalid_matrix_is_rejected():
    assert head_angles_from_matrix(np.zeros((3, 3))) is None
    assert head_angles_from_matrix(np.full((4, 4), np.nan)) is None
    assert head_angles_from_matrix(np.zeros((4, 4))) is None


def test_baseline_comparison_is_zero_at_baseline():
    dev = back_deviation(body(), make_baseline(), TOL)
    assert dev.severity == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("features", "component"),
    [
        (body(neck_ratio=0.6 * (1 - 0.3)), BackComponent.HUNCHING),
        (body(shoulder_mid_y=0.7 + 0.3 * 0.4), BackComponent.SINKING),
        (body(lean_severity=2.0), BackComponent.LEANING_IN),
        (body(shoulder_angle_deg=14.0), BackComponent.SIDE_LEAN),
    ],
)
def test_each_back_component_produces_severity_two(features, component):
    dev = back_deviation(features, make_baseline(), TOL)
    assert dev.dominant is component
    assert dev.severity == pytest.approx(2.0)


def test_improvements_beyond_baseline_do_not_count_as_deviation():
    # Sitting taller / further back than baseline is not a problem.
    better = body(neck_ratio=0.8, shoulder_mid_y=0.6, shoulder_width=0.25)
    assert back_deviation(better, make_baseline(), TOL).severity == pytest.approx(0.0)


def test_head_severity_counts_only_downward_pitch():
    b = make_baseline()
    assert head_severity(head(1.5), b, TOL, Q) == pytest.approx(1.5)
    assert head_severity(head(-2.0), b, TOL, Q) == 0.0
    assert b.pitch_down_deg == BASE_PITCH


def test_head_severity_unavailable_when_turned_away():
    assert head_severity(head(3.0, yaw=50.0), make_baseline(), TOL, Q) is None
