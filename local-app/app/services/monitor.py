"""MonitorController: owns the monitoring lifecycle (start / pause / resume / stop / quit).

Lives on the UI thread. Guarantees a single worker (and therefore a single camera owner)
at a time, runs the posture engine and alert policy, and emits results for the UI.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import replace
from enum import StrEnum

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage

from app.posture.engine import PostureEngine
from app.posture.models import Observation, PostureResult
from app.services.alerts import Alert, AlertPolicy
from app.services.notifications import AlertDispatcher
from app.services.session import SessionStats
from app.services.worker import MonitorWorker
from app.settings.store import AppSettings
from app.vision.analyzer import Analyzer
from app.vision.camera import FrameSource

log = logging.getLogger(__name__)

THREAD_STOP_TIMEOUT_MS = 5000


class MonitorStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


SourceFactory = Callable[[int], FrameSource]
AnalyzerFactory = Callable[[], Analyzer]


class MonitorController(QObject):
    status_changed = Signal(object)  # MonitorStatus
    result_ready = Signal(object)  # PostureResult
    preview_ready = Signal(QImage)
    alert_raised = Signal(object)  # Alert
    settings_changed = Signal(object)  # AppSettings (e.g. new baseline) -> persist
    notice = Signal(str)  # informational message for the UI

    def __init__(
        self,
        settings: AppSettings,
        source_factory: SourceFactory,
        analyzer_factory: AnalyzerFactory,
        dispatcher: AlertDispatcher | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._source_factory = source_factory
        self._analyzer_factory = analyzer_factory
        self._dispatcher = dispatcher
        self._clock = clock
        self._engine = PostureEngine(settings.posture_config(), settings.baseline)
        self._policy = AlertPolicy(settings.cooldown_seconds, settings.notify_on_recovery)
        self._thread: QThread | None = None
        self._worker: MonitorWorker | None = None
        self._status = MonitorStatus.IDLE
        self._calibrate_on_start = False
        self._preview_wanted = True
        self.stats = SessionStats()
        self.last_error: str | None = None

    # ----------------------------------------------------------------- properties
    @property
    def status(self) -> MonitorStatus:
        return self._status

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def is_calibrating(self) -> bool:
        return self._engine.is_calibrating

    @property
    def has_worker(self) -> bool:
        return self._thread is not None

    def set_dispatcher(self, dispatcher: AlertDispatcher) -> None:
        self._dispatcher = dispatcher

    # ----------------------------------------------------------------- commands
    def start(self, calibrate: bool = False) -> None:
        """Start monitoring (no-op if a session is already active)."""
        if self._status in (MonitorStatus.RUNNING, MonitorStatus.STARTING):
            if calibrate:
                self.calibrate()
            return
        if self._status is MonitorStatus.IDLE or self._status is MonitorStatus.ERROR:
            self.stats = SessionStats()
        self._calibrate_on_start = calibrate or self._settings.baseline is None
        self._engine.reset()
        self._policy.reset()
        self._start_worker()

    def pause(self) -> None:
        if self._status not in (MonitorStatus.RUNNING, MonitorStatus.STARTING):
            return
        self._stop_worker()
        self._engine.cancel_calibration()
        self._engine.reset()
        self._policy.reset()
        self.stats.mark_gap()
        self._set_status(MonitorStatus.PAUSED)

    def resume(self) -> None:
        if self._status is MonitorStatus.PAUSED:
            self.start()

    def stop(self) -> None:
        self._stop_worker()
        self._engine.cancel_calibration()
        self._engine.reset()
        self._policy.reset()
        self.stats.mark_gap()
        self._set_status(MonitorStatus.IDLE)

    def calibrate(self) -> None:
        """Recalibrate now, starting the camera first if needed."""
        if self._status is MonitorStatus.RUNNING:
            self._engine.start_calibration(self._clock(), self._settings.camera_index)
            self._policy.reset()
        else:
            self.start(calibrate=True)

    def shutdown(self) -> None:
        """Release everything before the application exits."""
        self._stop_worker()
        self._set_status(MonitorStatus.IDLE)

    def apply_settings(self, settings: AppSettings) -> None:
        camera_changed = settings.camera_index != self._settings.camera_index
        self._settings = settings
        self._engine.update_config(settings.posture_config())
        if settings.baseline is not self._engine.baseline:
            self._engine.set_baseline(settings.baseline)
        self._policy.cooldown_s = settings.cooldown_seconds
        self._policy.notify_on_recovery = settings.notify_on_recovery
        self._apply_worker_flags()
        if camera_changed and self._status in (MonitorStatus.RUNNING, MonitorStatus.STARTING):
            self.notice.emit("Switching camera…")
            self._stop_worker()
            self.start()

    def set_preview_wanted(self, wanted: bool) -> None:
        """The UI asks for preview frames only while the window is visible."""
        self._preview_wanted = wanted
        self._apply_worker_flags()

    # ----------------------------------------------------------------- worker management
    def _start_worker(self) -> None:
        if self._thread is not None:
            log.warning("Refusing to start a second monitoring worker")
            return
        index = self._settings.camera_index
        thread = QThread()
        thread.setObjectName("PixelPostureVision")
        worker = MonitorWorker(lambda: self._source_factory(index), self._analyzer_factory)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.camera_started.connect(self._on_camera_started)
        worker.observation_ready.connect(self._on_observation)
        worker.preview_ready.connect(self._on_preview)
        worker.failed.connect(self._on_failed)
        self._thread, self._worker = thread, worker
        self._apply_worker_flags()
        self.last_error = None
        self._set_status(MonitorStatus.STARTING)
        thread.start()
        log.info("Monitoring worker started (camera %d)", index)

    def _stop_worker(self) -> None:
        thread, worker = self._thread, self._worker
        if thread is None or worker is None:
            return
        self._thread = self._worker = None
        # Disconnect first so late queued signals from this worker are ignored.
        for signal, slot in (
            (worker.camera_started, self._on_camera_started),
            (worker.observation_ready, self._on_observation),
            (worker.preview_ready, self._on_preview),
            (worker.failed, self._on_failed),
        ):
            with contextlib.suppress(RuntimeError, TypeError):
                signal.disconnect(slot)
        worker.stop()
        thread.quit()
        if not thread.wait(THREAD_STOP_TIMEOUT_MS):
            log.error("Vision thread did not stop in time; terminating it")
            thread.terminate()
            thread.wait()
        worker.deleteLater()
        thread.deleteLater()
        log.info("Monitoring worker stopped; camera released")

    def _apply_worker_flags(self) -> None:
        if self._worker is not None:
            self._worker.preview_enabled = self._preview_wanted and self._settings.show_preview
            self._worker.overlay_enabled = self._settings.show_landmarks

    def _set_status(self, status: MonitorStatus) -> None:
        if status is not self._status:
            self._status = status
            log.info("Monitoring status: %s", status.value)
            self.status_changed.emit(status)

    # ----------------------------------------------------------------- worker slots
    @Slot(int, int)
    def _on_camera_started(self, width: int, height: int) -> None:
        self._set_status(MonitorStatus.RUNNING)
        baseline = self._settings.baseline
        if baseline is not None and not baseline.matches_camera(
            self._settings.camera_index, width, height
        ):
            self.notice.emit(
                "Your camera or resolution changed since the last calibration, so I'm "
                "recalibrating. Sit comfortably and hold still."
            )
            self._calibrate_on_start = True
        if self._calibrate_on_start:
            self._calibrate_on_start = False
            self._engine.start_calibration(self._clock(), self._settings.camera_index)

    @Slot(object)
    def _on_observation(self, observation: Observation) -> None:
        if self._status is not MonitorStatus.RUNNING:
            return
        result = self._engine.update(observation)
        self.stats.update(result)
        outcome = result.calibration_outcome
        if outcome is not None and outcome.success and outcome.baseline is not None:
            self._settings = replace(self._settings, baseline=outcome.baseline)
            self.settings_changed.emit(self._settings)
        self.result_ready.emit(result)
        self._handle_alert(result)

    def _handle_alert(self, result: PostureResult) -> None:
        alert: Alert | None = self._policy.evaluate(result)
        if alert is None:
            return
        self.stats.alerts_sent += 1
        self.alert_raised.emit(alert)
        if self._dispatcher is not None:
            self._dispatcher.deliver(
                alert,
                notifications_enabled=self._settings.notifications_enabled,
                sound_enabled=self._settings.sound_enabled,
            )

    @Slot(QImage)
    def _on_preview(self, image: QImage) -> None:
        self.preview_ready.emit(image)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        log.warning("Monitoring failed: %s", message)
        self._stop_worker()
        self._engine.cancel_calibration()
        self._policy.reset()
        self.last_error = message
        self._set_status(MonitorStatus.ERROR)
        self.result_ready.emit(self._engine.unavailable_result(self._clock(), message))
