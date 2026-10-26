import pytest
from conftest import make_baseline, obs, short_config, timeline

from app.posture.config import PostureConfig, Sensitivity
from app.posture.engine import (
    HEAD_MESSAGE,
    NEEDS_CALIBRATION_MESSAGE,
    RECOVERY_MESSAGE,
    PostureEngine,
    next_pet_state,
)
from app.posture.models import PetState, PostureResult, SignalKind, SignalLevel


def feed(engine: PostureEngine, start, end, back=0.0, head=0.0, fps=10.0) -> PostureResult:
    result = None
    for t in timeline(start, end, fps):
        result = engine.update(obs(t, back, head))
    assert result is not None
    return result


def calibrated_engine(config: PostureConfig | None = None) -> PostureEngine:
    return PostureEngine(config or short_config(), baseline=make_baseline())


def test_without_baseline_engine_asks_for_calibration():
    result = PostureEngine().update(obs(0.0))
    assert result.state is PetState.CALIBRATING
    assert result.message == NEEDS_CALIBRATION_MESSAGE
    assert result.calibration_progress is None


def test_calibration_flow_then_thriving():
    engine = PostureEngine()
    engine.start_calibration(0.0, camera_index=0)
    result = engine.update(obs(0.0))
    assert result.state is PetState.CALIBRATING
    assert result.calibration_progress is not None and 0 < result.calibration_progress < 1

    outcome = None
    for t in timeline(0.1, 5, 10):
        result = engine.update(obs(t))
        outcome = outcome or result.calibration_outcome
    assert outcome is not None and outcome.success
    assert engine.baseline is not None and not engine.is_calibrating
    assert feed(engine, 5, 6).state is PetState.THRIVING


def test_failed_calibration_keeps_old_baseline_and_explains():
    engine = calibrated_engine()
    old = engine.baseline
    engine.start_calibration(0.0, 0)
    finished = [
        r
        for t in timeline(0, 13, 10)
        if (r := engine.update(obs(t, head_sev=None))).calibration_outcome
    ]
    assert engine.baseline is old
    assert len(finished) == 1
    outcome = finished[0].calibration_outcome
    assert outcome is not None and not outcome.success
    assert finished[0].message.startswith("Calibration didn't succeed")


def test_stable_good_posture_thrives():
    result = feed(calibrated_engine(), 0, 60)
    assert result.state is PetState.THRIVING
    assert result.active_issue is None


def test_persistent_head_tilt_is_tracked_independently_of_back():
    engine = calibrated_engine()
    result = feed(engine, 0, 15, back=0.0, head=2.0)
    assert result.state is PetState.WARNING
    assert result.active_issue is SignalKind.HEAD
    assert result.head.level is SignalLevel.WARNING
    assert result.back.level is SignalLevel.OK
    assert result.message == HEAD_MESSAGE


def test_back_and_head_timers_are_independent():
    engine = calibrated_engine()
    feed(engine, 0, 20, back=2.0, head=0.0)  # back episode ~19 s old
    result = feed(engine, 20, 25, back=2.0, head=2.0)  # head episode only ~4 s old
    assert result.back.level is SignalLevel.WARNING
    assert result.head.level is SignalLevel.DEVIATING
    assert result.back.issue_duration_s > result.head.issue_duration_s + 10
    assert result.active_issue is SignalKind.BACK


def test_persistent_slouch_escalates_to_critical():
    result = feed(calibrated_engine(), 0, 40, back=2.0)
    assert result.state is PetState.CRITICAL
    assert result.active_issue is SignalKind.BACK
    assert "leaning forward" in result.message


def test_recovery_returns_to_thriving_with_message():
    engine = calibrated_engine()
    feed(engine, 0, 15, back=2.0)
    assert feed(engine, 15, 18, back=0.0).state is PetState.WARNING  # not yet confirmed
    result = feed(engine, 18, 20, back=0.0)
    assert result.state is PetState.THRIVING
    assert result.message == RECOVERY_MESSAGE


def test_unavailable_when_both_signals_missing():
    engine = calibrated_engine()
    feed(engine, 0, 5)
    result = feed(engine, 5, 9, back=None, head=None)
    assert result.state is PetState.UNAVAILABLE
    assert not result.tracking_available
    assert "Both shoulders must be visible" in result.message


def test_one_missing_signal_keeps_other_signal_working():
    engine = calibrated_engine()
    result = feed(engine, 0, 15, back=None, head=2.0)
    assert result.state is PetState.WARNING
    assert result.back.level is SignalLevel.UNAVAILABLE
    assert not result.body_valid and result.head_valid


def test_low_confidence_head_pose_is_unavailable_not_good():
    engine = calibrated_engine()
    feed(engine, 0, 2)
    result = None
    from conftest import body, head

    from app.posture.models import Observation

    for t in timeline(2, 6, 10):
        result = engine.update(Observation(t, body(), head(3.0, yaw=60.0)))
    assert result is not None
    assert result.head.level is SignalLevel.UNAVAILABLE
    assert result.back.level is SignalLevel.OK


def test_reset_on_pause_resume_starts_timers_fresh():
    engine = calibrated_engine()
    feed(engine, 0, 15, head=2.0)
    engine.reset()
    result = feed(engine, 100, 105, head=2.0)
    assert result.head.level is SignalLevel.DEVIATING
    assert result.head.issue_duration_s < 5


def test_sensitivity_changes_tolerance():
    severity_1_2_balanced = 1.2
    balanced = feed(calibrated_engine(), 0, 15, head=severity_1_2_balanced)
    relaxed = feed(
        calibrated_engine(short_config(sensitivity=Sensitivity.RELAXED)),
        0,
        15,
        head=severity_1_2_balanced,
    )
    assert balanced.state is PetState.WARNING
    assert relaxed.state is PetState.THRIVING
    assert relaxed.head.severity == pytest.approx(1.2 / 1.35, rel=0.01)


def test_unavailable_result_for_camera_failure():
    engine = calibrated_engine()
    feed(engine, 0, 15, back=2.0)
    result = engine.unavailable_result(16.0, "Camera disconnected")
    assert result.state is PetState.UNAVAILABLE
    assert result.message == "Camera disconnected"
    # Timers were cleared: no stale warning when frames return.
    assert feed(engine, 17, 18, back=2.0).back.level is SignalLevel.DEVIATING


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"has_baseline": False, "calibrating": False}, PetState.CALIBRATING),
        ({"has_baseline": True, "calibrating": True}, PetState.CALIBRATING),
        ({"back": SignalLevel.UNAVAILABLE, "head": SignalLevel.UNAVAILABLE}, PetState.UNAVAILABLE),
        ({"back": SignalLevel.CRITICAL, "head": SignalLevel.WARNING}, PetState.CRITICAL),
        ({"back": SignalLevel.UNAVAILABLE, "head": SignalLevel.WARNING}, PetState.WARNING),
        ({"back": SignalLevel.DEVIATING, "head": SignalLevel.OK}, PetState.THRIVING),
        ({"back": SignalLevel.OK, "head": SignalLevel.UNAVAILABLE}, PetState.THRIVING),
    ],
)
def test_pet_state_transition_table(kwargs, expected):
    args = {
        "has_baseline": True,
        "calibrating": False,
        "back": SignalLevel.OK,
        "head": SignalLevel.OK,
    }
    args.update(kwargs)
    assert next_pet_state(**args) is expected


def test_configured_warning_duration_is_respected():
    from app.settings.store import AppSettings

    config = AppSettings(warning_seconds=20, critical_seconds=60).posture_config()
    engine = PostureEngine(config, baseline=make_baseline())
    assert feed(engine, 0, 15, head=2.0).state is PetState.THRIVING  # ~14 s episode: below 20 s
    assert feed(engine, 15, 23, head=2.0).state is PetState.WARNING
    assert feed(engine, 23, 50, head=2.0).state is PetState.WARNING  # critical needs 60 s
    assert feed(engine, 50, 65, head=2.0).state is PetState.CRITICAL
