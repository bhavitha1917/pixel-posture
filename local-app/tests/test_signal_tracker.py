import random

import pytest
from conftest import SHORT, timeline

from app.posture.config import SeverityLevels, TimingConfig
from app.posture.models import SignalKind, SignalLevel, SignalStatus
from app.posture.signal_tracker import SignalTracker

TIMING = TimingConfig(**SHORT)
LEVELS = SeverityLevels()


def tracker() -> SignalTracker:
    return SignalTracker(SignalKind.HEAD, TIMING, LEVELS)


def feed(tr: SignalTracker, start: float, end: float, severity: float | None, fps=10.0):
    status: SignalStatus | None = None
    for t in timeline(start, end, fps):
        status = tr.update(t, severity)
    assert status is not None
    return status


def test_stable_good_posture_stays_ok():
    status = feed(tracker(), 0, 120, 0.2)
    assert status.level is SignalLevel.OK
    assert status.issue_duration_s == 0.0


def test_brief_deviation_never_warns():
    tr = tracker()
    feed(tr, 0, 5, 0.0)
    levels = {tr.update(t, 2.0).level for t in timeline(5, 11, 10)}
    assert SignalLevel.WARNING not in levels
    assert SignalLevel.DEVIATING in levels
    status = feed(tr, 11, 20, 0.0)
    assert status.level is SignalLevel.OK


def test_single_frame_spike_is_smoothed_away():
    tr = tracker()
    feed(tr, 0, 5, 0.0)
    assert tr.update(5.0, 5.0).level is SignalLevel.OK  # EMA after 0.1 s is well below 1.0
    assert feed(tr, 5.1, 8, 0.0).level is SignalLevel.OK


def test_persistent_deviation_warns_then_goes_critical():
    tr = tracker()
    feed(tr, 0, 2, 0.0)
    status_9 = feed(tr, 2, 11, 2.0)  # ~8.5 s into episode (smoothing delays onset)
    assert status_9.level is SignalLevel.DEVIATING
    status_14 = feed(tr, 11, 14, 2.0)
    assert status_14.level is SignalLevel.WARNING
    assert 10.0 <= status_14.issue_duration_s < 13.0
    status_35 = feed(tr, 14, 35, 2.0)
    assert status_35.level is SignalLevel.CRITICAL


def test_marginal_deviation_never_escalates_to_critical():
    status = feed(tracker(), 0, 120, 1.15)
    assert status.level is SignalLevel.WARNING
    assert status.issue_duration_s > 100


def test_recovery_requires_sustained_improvement():
    tr = tracker()
    feed(tr, 0, 15, 2.0)
    status = feed(tr, 15, 17.5, 0.0)  # improvement not yet confirmed
    assert status.level is SignalLevel.WARNING
    status = feed(tr, 17.5, 21, 0.0)
    assert status.level is SignalLevel.OK


def test_hysteresis_fluctuations_do_not_reset_timer():
    tr = tracker()
    feed(tr, 0, 3, 1.5)
    rng = random.Random(7)
    status = None
    for t in timeline(3, 25, 10):
        status = tr.update(t, rng.uniform(0.75, 1.3))  # dips below 1.0 but stays above 0.7
    assert status is not None
    assert status.level is SignalLevel.WARNING
    assert status.issue_duration_s > 20


def test_brief_dips_below_exit_do_not_end_episode():
    tr = tracker()
    feed(tr, 0, 12, 2.0)
    for start in (12, 16, 20):
        feed(tr, start, start + 2, 0.0)  # 2 s of improvement < 3 s recovery
        feed(tr, start + 2, start + 4, 2.0)
    status = feed(tr, 24, 25, 2.0)
    assert status.level in (SignalLevel.WARNING, SignalLevel.CRITICAL)
    assert status.issue_duration_s > 20


def test_no_new_warning_while_already_improving():
    tr = tracker()
    feed(tr, 0, 1, 0.0)
    feed(tr, 1, 9, 2.0)  # episode starts ~1.7 s
    levels = {tr.update(t, 0.0).level for t in timeline(9, 16, 10)}  # 10 s mark at ~11.7 s
    assert SignalLevel.WARNING not in levels
    assert tr.update(16.0, 0.0).level is SignalLevel.OK


def test_critical_drops_back_to_warning_when_severity_falls():
    tr = tracker()
    assert feed(tr, 0, 40, 2.0).level is SignalLevel.CRITICAL
    assert feed(tr, 40, 50, 0.9).level is SignalLevel.WARNING


def test_missing_data_is_not_good_posture():
    tr = tracker()
    feed(tr, 0, 15, 2.0)
    status = feed(tr, 15, 16.5, None)  # short gap: state held
    assert status.level is SignalLevel.WARNING
    status = feed(tr, 16.5, 20, None)  # long gap: reset to unavailable, not OK
    assert status.level is SignalLevel.UNAVAILABLE
    assert status.severity is None


def test_missing_data_does_not_advance_recovery():
    tr = tracker()
    feed(tr, 0, 15, 2.0)
    feed(tr, 15, 17, 0.0)  # 2 s improving
    tr.update(17.0, None)  # gap restarts recovery confirmation
    status = feed(tr, 17.1, 19.5, 0.0)  # 2.4 s since gap
    assert status.level is SignalLevel.WARNING
    assert feed(tr, 19.5, 21, 0.0).level is SignalLevel.OK


def test_never_seen_signal_is_unavailable():
    assert tracker().update(0.0, None).level is SignalLevel.UNAVAILABLE


@pytest.mark.parametrize("fps", [4.0, 12.0, 30.0])
def test_timers_are_frame_rate_independent(fps):
    tr = tracker()
    feed(tr, 0, 1, 0.0, fps)
    status = feed(tr, 1, 15, 2.0, fps)
    assert status.level is SignalLevel.WARNING
    assert status.issue_duration_s == pytest.approx(13.3, abs=0.6)


def test_irregular_frame_intervals():
    rng = random.Random(3)
    tr = tracker()
    t, status = 0.0, None
    while t < 40:
        status = tr.update(t, 2.0)
        t += rng.uniform(0.02, 0.6)
    assert status is not None and status.level is SignalLevel.CRITICAL
    assert status.issue_duration_s == pytest.approx(t - 0.0, abs=1.0)


def test_reconfigure_keeps_episode():
    tr = tracker()
    feed(tr, 0, 8, 2.0)
    tr.configure(TimingConfig(**{**SHORT, "warning_s": 5.0}), LEVELS)
    assert feed(tr, 8, 9, 2.0).level is SignalLevel.WARNING


def test_long_silent_gap_starts_fresh_instead_of_counting_the_gap():
    """Regression: after laptop sleep no observations arrive at all; the time asleep must not
    count as a sustained posture issue when frames resume."""
    tr = tracker()
    feed(tr, 0, 8, 2.0)  # episode ~7 s old, not yet a warning
    status = tr.update(608.0, 2.0)  # first frame after 10 minutes of sleep
    assert status.level is SignalLevel.DEVIATING
    assert status.issue_duration_s < 1.0
