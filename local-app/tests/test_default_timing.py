"""The shipped reminder timing: Warning 30 s, Critical 60 s (severe), recovery 5 s, cooldown 60 s.

Synthetic observations at 10 fps drive the real engine and alert policy. The EMA smoothing
(tau 1 s) delays onsets by under a second, so the windows below allow for that.
"""

from __future__ import annotations

import itertools

import pytest
from conftest import make_baseline, obs, timeline

from app.posture.config import PostureConfig, TimingConfig
from app.posture.engine import PostureEngine
from app.posture.models import PetState, PostureResult, SignalLevel
from app.services.alerts import Alert, AlertPolicy
from app.settings.store import AppSettings

SEVERE = 2.0  # clearly past the critical level (1.3)
MILD = 1.15  # an issue (>= 1.0) but never severe enough for Critical


def engine() -> PostureEngine:
    return PostureEngine(AppSettings().posture_config(), make_baseline())


def feed(eng: PostureEngine, start, end, back=0.0, head=0.0) -> list[PostureResult]:
    return [eng.update(obs(t, back, head)) for t in timeline(start, end, 10)]


def first_time(results: list[PostureResult], level: SignalLevel, attr="back") -> float | None:
    return next((r.timestamp for r in results if getattr(r, attr).level is level), None)


def test_shipped_defaults():
    s = AppSettings()
    assert (s.warning_seconds, s.critical_seconds, s.recovery_seconds) == (30, 60, 5)
    assert s.cooldown_seconds == 60
    assert TimingConfig() == s.posture_config().timing
    assert PostureConfig().timing.warning_s == 30


def test_short_movement_never_warns():
    eng = engine()
    feed(eng, 0, 5)
    for start in (5, 60, 120):  # repeated 20 s slouches separated by good posture
        results = feed(eng, start, start + 20, back=SEVERE)
        assert {r.back.level for r in results} <= {SignalLevel.OK, SignalLevel.DEVIATING}
        results = feed(eng, start + 20, start + 40)
        assert results[-1].state is PetState.THRIVING


def test_warning_only_after_30_s_of_sustained_deviation():
    results = feed(eng := engine(), 0, 5) + feed(eng, 5, 45, back=SEVERE)
    onset = first_time(results, SignalLevel.DEVIATING)
    warned = first_time(results, SignalLevel.WARNING)
    assert onset is not None and warned is not None
    assert 30.0 <= warned - onset < 30.5
    assert 30.0 <= warned - 5 < 31.5  # measured from when the slouch actually began


def test_critical_needs_severe_deviation_for_60_s():
    results = feed(eng := engine(), 0, 5) + feed(eng, 5, 80, back=SEVERE)
    critical = first_time(results, SignalLevel.CRITICAL)
    assert critical is not None and 60.0 <= critical - 5 < 61.5
    assert results[-1].state is PetState.CRITICAL


def test_mild_deviation_never_becomes_critical():
    results = feed(eng := engine(), 0, 5) + feed(eng, 5, 300, back=MILD)
    assert first_time(results, SignalLevel.WARNING) is not None
    assert first_time(results, SignalLevel.CRITICAL) is None


def test_long_mild_episode_does_not_shortcut_critical():
    """A severe slouch after a long mild one still has to last the full 60 s itself."""
    eng = engine()
    feed(eng, 0, 5)
    feed(eng, 5, 125, back=MILD)  # 2 minutes of mild Warning
    results = feed(eng, 125, 200, back=SEVERE)
    critical = first_time(results, SignalLevel.CRITICAL)
    assert critical is not None and critical - 125 >= 60.0


def test_recovery_needs_5_s_of_improvement():
    eng = engine()
    feed(eng, 0, 5)
    feed(eng, 5, 45, back=SEVERE)
    results = feed(eng, 45, 60)
    ok = first_time(results, SignalLevel.OK)
    # Smoothing takes about 1 s to fall below the exit level, then 5 s must pass.
    assert ok is not None and 6.0 <= ok - 45 < 7.0
    assert results[-1].state is PetState.THRIVING


def test_brief_improvement_does_not_end_the_episode():
    eng = engine()
    feed(eng, 0, 5)
    feed(eng, 5, 45, back=SEVERE)
    feed(eng, 45, 49)  # 4 s of better posture: not enough
    results = feed(eng, 49, 52, back=SEVERE)
    assert results[-1].back.level is SignalLevel.WARNING
    assert results[-1].back.issue_duration_s > 45


def test_back_and_head_are_tracked_independently():
    eng = engine()
    feed(eng, 0, 5)
    back_only = feed(eng, 5, 25, back=SEVERE)
    both = feed(eng, 25, 70, back=SEVERE, head=SEVERE)
    results = back_only + both
    back_warn = first_time(results, SignalLevel.WARNING, "back")
    head_warn = first_time(results, SignalLevel.WARNING, "head")
    assert back_warn is not None and head_warn is not None
    assert 30 <= back_warn - 5 < 31.5
    assert 30 <= head_warn - 25 < 31.5


@pytest.mark.parametrize("gap", [5.0, 600.0])  # lost landmarks / laptop sleep
def test_missing_data_and_silent_gaps_do_not_count_as_slouching(gap):
    eng = engine()
    feed(eng, 0, 5)
    feed(eng, 5, 25, back=SEVERE)  # 20 s
    if gap < 60:
        missing = [eng.update(obs(t, None, None)) for t in timeline(25, 25 + gap, 10)]
        assert missing[-1].state is PetState.UNAVAILABLE
    # gap >= 60: no observations at all, as during sleep
    results = feed(eng, 25 + gap, 45 + gap, back=SEVERE)  # another 20 s
    assert first_time(results, SignalLevel.WARNING) is None


def test_missing_data_alone_never_alerts():
    policy, eng = AlertPolicy(60.0), engine()
    alerts = [policy.evaluate(eng.update(obs(t, None, None))) for t in timeline(0, 300, 10)]
    assert not any(alerts)


def run_alerts(policy, eng, start, end, back=0.0, head=0.0) -> list[tuple[float, Alert]]:
    out = []
    for t in timeline(start, end, 10):
        alert = policy.evaluate(eng.update(obs(t, back, head)))
        if alert:
            out.append((t, alert))
    return out


def test_cooldown_spaces_alerts_at_least_60_s_apart():
    policy, eng = AlertPolicy(AppSettings().cooldown_seconds), engine()
    run_alerts(policy, eng, 0, 5)
    alerts = run_alerts(policy, eng, 5, 200, back=SEVERE, head=SEVERE)
    times = [t for t, _ in alerts]
    assert len(alerts) >= 2
    assert all(b - a >= 60.0 - 1e-9 for a, b in itertools.pairwise(times))
    assert alerts[0][1].level is SignalLevel.WARNING
    assert SignalLevel.CRITICAL in {a.level for _, a in alerts}


def test_one_alert_per_level_per_episode():
    policy, eng = AlertPolicy(60.0), engine()
    run_alerts(policy, eng, 0, 5)
    alerts = run_alerts(policy, eng, 5, 600, back=MILD)
    assert [a.level for _, a in alerts] == [SignalLevel.WARNING]
