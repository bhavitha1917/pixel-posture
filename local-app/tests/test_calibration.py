from conftest import BASE_NECK, BASE_PITCH, BASE_WIDTH, body, head, obs, timeline

from app.posture.calibration import Calibrator
from app.posture.config import CalibrationConfig
from app.posture.models import Observation

CFG = CalibrationConfig()


def run(calibrator: Calibrator, observations):
    for o in observations:
        outcome = calibrator.add(o)
        if outcome is not None:
            return outcome
    return None


def test_stable_valid_frames_produce_median_baseline():
    cal = Calibrator(CFG, camera_index=1, started_at=0.0)
    outcome = run(cal, (obs(t) for t in timeline(0, 10, 10)))
    assert outcome is not None and outcome.success
    b = outcome.baseline
    assert b is not None
    assert b.neck_ratio == BASE_NECK
    assert b.shoulder_width == BASE_WIDTH
    assert b.pitch_down_deg == BASE_PITCH
    assert b.camera_index == 1
    assert (b.frame_width, b.frame_height) == (640, 480)
    assert cal.progress == 1.0


def test_succeeds_after_exactly_min_samples():
    cal = Calibrator(CFG, 0, 0.0)
    outcomes = [cal.add(obs(i * 0.1)) for i in range(CFG.min_samples)]
    assert all(o is None for o in outcomes[:-1])
    assert outcomes[-1] is not None and outcomes[-1].success


def test_rejected_when_face_missing():
    cal = Calibrator(CFG, 0, 0.0)
    outcome = run(cal, (obs(t, head_sev=None) for t in timeline(0, 13, 10)))
    assert outcome is not None and not outcome.success
    assert outcome.baseline is None
    assert "face not detected" in (outcome.reason or "")


def test_rejected_when_shoulders_missing():
    cal = Calibrator(CFG, 0, 0.0)
    outcome = run(cal, (obs(t, back_sev=None) for t in timeline(0, 13, 10)))
    assert outcome is not None and not outcome.success
    assert "shoulders" in (outcome.reason or "")


def test_rejected_when_too_much_movement():
    cal = Calibrator(CFG, 0, 0.0)

    def wobbling(t: float, i: int) -> Observation:
        return Observation(
            t, body(), head(2.0 if i % 2 else -2.0), frame_width=640, frame_height=480
        )

    outcome = run(cal, (wobbling(t, i) for i, t in enumerate(timeline(0, 13, 10))))
    assert outcome is not None and not outcome.success
    assert "movement" in (outcome.reason or "").lower()


def test_fidgeting_first_then_holding_still_succeeds():
    cal = Calibrator(CFG, 0, 0.0)
    frames = [
        Observation(t, body(), head(3.0 if i % 2 else -3.0), frame_width=640, frame_height=480)
        for i, t in enumerate(timeline(0, 3, 10))
    ] + [obs(t) for t in timeline(3, 12, 10)]
    outcome = run(cal, frames)
    assert outcome is not None and outcome.success


def test_rejected_when_head_not_above_shoulders():
    cal = Calibrator(CFG, 0, 0.0)
    frames = (
        Observation(t, body(neck_ratio=0.01), head(), frame_width=640, frame_height=480)
        for t in timeline(0, 13, 10)
    )
    outcome = run(cal, frames)
    assert outcome is not None and not outcome.success
    assert "not clearly separated" in (outcome.reason or "")


def test_progress_counts_only_valid_frames():
    cal = Calibrator(CFG, 0, 0.0)
    for t in timeline(0, 1, 10):
        cal.add(obs(t, head_sev=None))
    assert cal.progress == 0.0
    cal.add(obs(1.0))
    assert cal.progress == 1 / CFG.min_samples
