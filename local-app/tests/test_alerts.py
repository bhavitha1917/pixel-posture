from dataclasses import replace

import pytest
from conftest import make_baseline, obs, short_config, timeline

from app.posture.engine import PostureEngine
from app.posture.models import PetState, PostureResult, SignalKind, SignalLevel
from app.services.alerts import CRITICAL_TITLE, WARNING_TITLE, Alert, AlertPolicy
from app.services.notifications import AlertDispatcher


def run(policy: AlertPolicy, engine: PostureEngine, start, end, back=0.0, head=0.0):
    alerts: list[tuple[float, Alert]] = []
    for t in timeline(start, end, 10):
        alert = policy.evaluate(engine.update(obs(t, back, head)))
        if alert:
            alerts.append((t, alert))
    return alerts


def setup(cooldown=30.0, recovery=False):
    return AlertPolicy(cooldown, recovery), PostureEngine(short_config(), make_baseline())


def test_warning_produces_one_alert_per_episode():
    policy, engine = setup()
    alerts = run(policy, engine, 0, 25, head=2.0)
    assert len(alerts) == 1
    _, alert = alerts[0]
    assert alert.title == WARNING_TITLE
    assert alert.signal is SignalKind.HEAD and alert.level is SignalLevel.WARNING


def test_good_posture_never_alerts():
    policy, engine = setup()
    assert run(policy, engine, 0, 120) == []


def test_brief_deviation_never_alerts():
    policy, engine = setup()
    run(policy, engine, 0, 5)
    assert run(policy, engine, 5, 12, back=2.0) == []
    assert run(policy, engine, 12, 30) == []


def test_critical_escalation_alerts_once_after_cooldown():
    policy, engine = setup(cooldown=30.0)
    alerts = run(policy, engine, 0, 90, back=2.0)
    assert [a.level for _, a in alerts] == [SignalLevel.WARNING, SignalLevel.CRITICAL]
    (t_warn, _), (t_crit, crit) = alerts
    assert crit.title == CRITICAL_TITLE
    # Critical became due ~20 s after the warning but was deferred until the cooldown ended.
    assert t_crit - t_warn == pytest.approx(30.0, abs=0.2)


def test_deferred_alert_dropped_if_condition_resolves():
    policy, engine = setup(cooldown=60.0)
    run(policy, engine, 0, 15, back=2.0)  # back warning sent at ~11 s
    run(policy, engine, 15, 20)  # back recovers
    alerts = run(policy, engine, 20, 34, head=2.0)  # head warning due during cooldown
    assert alerts == []
    run(policy, engine, 34, 40)  # head recovers before cooldown ends
    assert run(policy, engine, 40, 80) == []


def test_new_episode_after_recovery_alerts_again():
    policy, engine = setup(cooldown=10.0)
    first = run(policy, engine, 0, 15, head=2.0)
    run(policy, engine, 15, 20)
    second = run(policy, engine, 20, 35, head=2.0)
    assert len(first) == 1 and len(second) == 1


def test_both_signals_alert_respecting_cooldown():
    policy, engine = setup(cooldown=30.0)
    alerts = run(policy, engine, 0, 50, back=1.2, head=1.2)  # marginal: warnings only
    kinds = [a.signal for _, a in alerts]
    assert sorted(kinds) == [SignalKind.BACK, SignalKind.HEAD]
    assert alerts[1][0] - alerts[0][0] >= 30.0


def test_reset_on_pause_suppresses_and_rearms():
    policy, engine = setup()
    assert len(run(policy, engine, 0, 15, head=2.0)) == 1
    policy.reset()
    engine.reset()  # pause -> resume
    assert len(run(policy, engine, 100, 115, head=2.0)) == 1


def test_unavailable_and_calibrating_suppress_alerts():
    policy, _ = setup()
    engine = PostureEngine()
    result = engine.update(obs(0.0))
    assert result.state is PetState.CALIBRATING
    forced = replace(result, state=PetState.CALIBRATING, timestamp=100.0)
    assert policy.evaluate(forced) is None
    unavailable = PostureEngine(baseline=make_baseline()).unavailable_result(1.0, "Camera lost")
    assert policy.evaluate(unavailable) is None


def test_recovery_alert_only_when_enabled_and_after_an_alert():
    policy, engine = setup(cooldown=10.0, recovery=True)
    run(policy, engine, 0, 15, head=2.0)
    alerts = run(policy, engine, 30, 40)
    assert [a.is_recovery for _, a in alerts] == [True]

    quiet_policy, engine2 = setup(cooldown=10.0, recovery=False)
    run(quiet_policy, engine2, 0, 15, head=2.0)
    assert run(quiet_policy, engine2, 30, 40) == []


class RecordingBackend:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent: list[tuple[str, str, bool]] = []

    def notify(self, title: str, message: str, critical: bool) -> None:
        if self.fail:
            raise RuntimeError("toast service unavailable")
        self.sent.append((title, message, critical))


class CountingSound:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.count = 0

    def play(self) -> None:
        if self.fail:
            raise OSError("no audio device")
        self.count += 1


ALERT = Alert("Time for a posture check!", "msg", SignalLevel.CRITICAL, SignalKind.BACK)


def test_dispatcher_delivers_notification_and_sound():
    backend, sound = RecordingBackend(), CountingSound()
    report = AlertDispatcher(backend, sound).deliver(
        ALERT, notifications_enabled=True, sound_enabled=True
    )
    assert report.notified and report.sound_played and report.error is None
    assert backend.sent == [("Time for a posture check!", "msg", True)]
    assert sound.count == 1


def test_muted_sound_and_disabled_notifications_are_respected():
    backend, sound = RecordingBackend(), CountingSound()
    dispatcher = AlertDispatcher(backend, sound)
    report = dispatcher.deliver(ALERT, notifications_enabled=True, sound_enabled=False)
    assert report.notified and not report.sound_played and sound.count == 0
    report = dispatcher.deliver(ALERT, notifications_enabled=False, sound_enabled=False)
    assert not report.notified and len(backend.sent) == 1


def test_delivery_failures_do_not_raise():
    dispatcher = AlertDispatcher(RecordingBackend(fail=True), CountingSound(fail=True))
    report = dispatcher.deliver(ALERT, notifications_enabled=True, sound_enabled=True)
    assert not report.notified and not report.sound_played
    assert report.error is not None and "toast service unavailable" in report.error


def _result_with_state(state: PetState, t: float) -> PostureResult:
    base = PostureEngine(baseline=make_baseline()).update(obs(t))
    return replace(base, state=state)


def test_tracking_loss_rearms_alerts():
    policy, engine = setup(cooldown=10.0)
    assert len(run(policy, engine, 0, 15, head=2.0)) == 1
    run(policy, engine, 15, 20, back=None, head=None)  # tracking lost > grace -> reset
    assert len(run(policy, engine, 20, 35, head=2.0)) == 1
    assert policy.evaluate(_result_with_state(PetState.UNAVAILABLE, 40.0)) is None
