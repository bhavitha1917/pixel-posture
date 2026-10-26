"""Lifecycle tests for MonitorController + MonitorWorker on a real QThread.

Only the hardware boundary is faked (camera frames and model inference); the real
engine, alert policy, threading and signal plumbing are exercised.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest
from conftest import make_baseline, obs

from app.posture.models import PetState
from app.services import worker as worker_module
from app.services.alerts import Alert
from app.services.monitor import MonitorController, MonitorStatus
from app.services.notifications import AlertDispatcher
from app.settings.store import AppSettings
from app.vision.analyzer import Analysis, Overlay
from app.vision.camera import CameraError

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


class FakeSource:
    def __init__(self, registry: Registry, fail_open=False, frames_before_failure=None):
        self.registry = registry
        self.fail_open = fail_open
        self.frames_left = frames_before_failure
        self.is_open = False

    def open(self):
        if self.fail_open or (self.registry.open_count >= 1 and self.registry.fail_reopen):
            raise CameraError("Camera 0 could not be opened.")
        if self.registry.open_count >= 1 and self.registry.restore_on_reopen:
            self.registry.frames_on = True
        self.is_open = True
        with self.registry.lock:
            self.registry.open_count += 1
            self.registry.active += 1
            self.registry.max_active = max(self.registry.max_active, self.registry.active)
        return 640, 480

    def read(self):
        if not self.registry.frames_on:
            return None
        if self.frames_left is not None:
            if self.frames_left <= 0:
                return None
            self.frames_left -= 1
        return FRAME.copy()

    def release(self):
        if not self.is_open:
            return
        self.is_open = False
        with self.registry.lock:
            self.registry.active -= 1
            self.registry.release_count += 1


class FakeAnalyzer:
    """Produces synthetic observations on an accelerated clock (0.5 s per frame)."""

    def __init__(self, registry: Registry):
        self.registry = registry
        self.n = 0

    def analyze(self, frame, timestamp):
        self.n += 1
        t = timestamp if self.registry.real_time else self.n * 0.5
        return Analysis(obs(t, *self.registry.severities), Overlay())

    def close(self):
        self.registry.closed += 1


class Registry:
    def __init__(self):
        self.lock = threading.Lock()
        self.open_count = self.release_count = self.active = self.max_active = self.closed = 0
        self.severities: tuple[float | None, float | None] = (0.0, 0.0)
        self.frames_on = True  # False simulates a camera that stops delivering frames
        self.real_time = False  # True: observations use the worker's real timestamps
        self.restore_on_reopen = False  # frames resume once the camera is reopened
        self.fail_reopen = False  # reopening the camera fails


class RecordingBackend:
    def __init__(self):
        self.sent = []

    def notify(self, title, message, critical):
        self.sent.append(title)


class SilentSound:
    def play(self):
        pass


@pytest.fixture
def registry():
    return Registry()


def make_controller(registry, settings=None, **source_kwargs):
    backend = RecordingBackend()
    controller = MonitorController(
        settings or AppSettings(baseline=make_baseline(), sound_enabled=False),
        source_factory=lambda index: FakeSource(registry, **source_kwargs),
        analyzer_factory=lambda: FakeAnalyzer(registry),
        dispatcher=AlertDispatcher(backend, SilentSound()),
    )
    return controller, backend


def test_start_produces_results_and_stop_releases_camera(qtbot, registry):
    controller, _ = make_controller(registry)
    results = []
    controller.result_ready.connect(results.append)
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.RUNNING, timeout=3000)
    qtbot.waitUntil(lambda: len(results) >= 3, timeout=3000)
    assert results[-1].state is PetState.THRIVING

    controller.stop()
    assert controller.status is MonitorStatus.IDLE
    assert not controller.has_worker
    assert registry.active == 0 and registry.release_count == 1 and registry.closed == 1


def test_duplicate_start_does_not_open_camera_twice(qtbot, registry):
    controller, _ = make_controller(registry)
    controller.start()
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.RUNNING, timeout=3000)
    controller.start()
    qtbot.wait(200)
    assert registry.open_count == 1 and registry.max_active == 1
    controller.shutdown()
    assert registry.active == 0


def test_pause_releases_camera_and_resume_reopens(qtbot, registry):
    controller, _ = make_controller(registry)
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.RUNNING, timeout=3000)
    controller.pause()
    assert controller.status is MonitorStatus.PAUSED
    assert registry.active == 0

    results = []
    controller.result_ready.connect(results.append)
    qtbot.wait(200)
    assert results == []  # no posture judgements while paused

    controller.resume()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.RUNNING, timeout=3000)
    assert registry.open_count == 2 and registry.max_active == 1
    controller.shutdown()
    assert registry.active == 0


def test_camera_open_failure_reports_unavailable(qtbot, registry):
    controller, _ = make_controller(registry, fail_open=True)
    results = []
    controller.result_ready.connect(results.append)
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.ERROR, timeout=3000)
    assert not controller.has_worker
    assert results and results[-1].state is PetState.UNAVAILABLE
    assert "could not be opened" in (controller.last_error or "")
    assert registry.closed == 1  # models released even though the camera failed


def test_camera_that_stops_delivering_frames_is_reported(qtbot, registry, monkeypatch):
    monkeypatch.setattr(worker_module, "FRAME_FAILURE_TIMEOUT_S", 0.3)
    controller, _ = make_controller(registry, frames_before_failure=3)
    results = []
    controller.result_ready.connect(results.append)
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.ERROR, timeout=3000)
    assert results[-1].state is PetState.UNAVAILABLE  # no stale posture state
    assert registry.active == 0


def test_model_failure_is_reported(qtbot, registry):
    def broken():
        raise RuntimeError("model file missing")

    controller = MonitorController(
        AppSettings(baseline=make_baseline()),
        source_factory=lambda i: FakeSource(registry),
        analyzer_factory=broken,
    )
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.ERROR, timeout=3000)
    assert "model file missing" in (controller.last_error or "")
    assert registry.open_count == 0  # camera never opened


def test_first_start_calibrates_and_persists_baseline(qtbot, registry):
    controller, _ = make_controller(registry, settings=AppSettings(sound_enabled=False))
    saved: list[AppSettings] = []
    controller.settings_changed.connect(saved.append)
    controller.start()
    qtbot.waitUntil(lambda: bool(saved), timeout=6000)
    assert saved[-1].baseline is not None
    assert controller.settings.baseline is not None
    controller.shutdown()


def test_sustained_issue_sends_one_notification_and_pause_suppresses(qtbot, registry):
    controller, backend = make_controller(registry)
    alerts: list[Alert] = []
    controller.alert_raised.connect(alerts.append)
    registry.severities = (0.0, 2.0)  # head tilted, accelerated 0.5 s per frame
    controller.start()
    qtbot.waitUntil(lambda: len(backend.sent) >= 1, timeout=6000)
    controller.pause()
    count = len(backend.sent)
    qtbot.wait(300)
    assert len(backend.sent) == count == 1
    assert alerts[0].message.startswith("Your head has been tilted downward")
    assert controller.stats.alerts_sent == 1
    controller.shutdown()


def test_shutdown_is_idempotent(qtbot, registry):
    controller, _ = make_controller(registry)
    controller.shutdown()
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.RUNNING, timeout=3000)
    controller.shutdown()
    controller.shutdown()
    assert registry.active == 0 and not controller.has_worker


def test_frame_outage_reports_unavailable_instead_of_stale_state(qtbot, registry, monkeypatch):
    """Regression: while no frames arrive, the UI must not keep showing the last posture."""
    monkeypatch.setattr(worker_module, "FRAME_FAILURE_TIMEOUT_S", 30.0)
    registry.real_time = True
    controller, _ = make_controller(registry)
    results = []
    controller.result_ready.connect(results.append)
    controller.start()
    qtbot.waitUntil(lambda: bool(results) and results[-1].state is PetState.THRIVING, timeout=3000)
    registry.frames_on = False
    qtbot.waitUntil(lambda: results[-1].state is PetState.UNAVAILABLE, timeout=4000)
    assert "not delivering frames" in results[-1].message
    assert controller.status is MonitorStatus.RUNNING  # a short gap is not an error
    registry.frames_on = True
    qtbot.waitUntil(lambda: results[-1].state is PetState.THRIVING, timeout=3000)
    controller.shutdown()
    assert registry.active == 0


def test_camera_is_reopened_once_after_a_lasting_outage(qtbot, registry, monkeypatch):
    """Regression: e.g. after sleep/resume, try reopening the camera before giving up."""
    monkeypatch.setattr(worker_module, "FRAME_FAILURE_TIMEOUT_S", 0.4)
    registry.real_time = True
    registry.restore_on_reopen = True
    controller, _ = make_controller(registry)
    results = []
    controller.result_ready.connect(results.append)
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.RUNNING, timeout=3000)
    registry.frames_on = False
    qtbot.waitUntil(lambda: registry.open_count == 2, timeout=4000)
    qtbot.waitUntil(lambda: results[-1].state is PetState.THRIVING, timeout=3000)
    assert controller.status is MonitorStatus.RUNNING
    assert registry.max_active == 1  # the old handle was released before reopening
    controller.shutdown()
    assert registry.active == 0


def test_failed_reopen_reports_camera_error(qtbot, registry, monkeypatch):
    monkeypatch.setattr(worker_module, "FRAME_FAILURE_TIMEOUT_S", 0.4)
    registry.fail_reopen = True
    controller, _ = make_controller(registry)
    controller.start()
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.RUNNING, timeout=3000)
    registry.frames_on = False
    qtbot.waitUntil(lambda: controller.status is MonitorStatus.ERROR, timeout=4000)
    assert "could not be opened" in (controller.last_error or "")
    assert registry.active == 0
