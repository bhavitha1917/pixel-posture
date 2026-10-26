"""MonitorWorker: the single owner of the camera, running on its own QThread.

The worker only captures and analyses frames. It emits immutable ``Observation`` objects
and *copied* preview images through queued signals; all posture logic runs on the UI
thread. Control from other threads goes through ``threading.Event`` / plain flags only.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImage

from app.posture.models import Observation
from app.vision.analyzer import Analyzer, Overlay
from app.vision.camera import CameraError, Frame, FrameSource

log = logging.getLogger(__name__)

MAX_INFERENCE_FPS = 12.0
MAX_PREVIEW_FPS = 10.0
PREVIEW_WIDTH = 480
FRAME_FAILURE_TIMEOUT_S = 3.0  # failed reads for this long -> reopen once, then give up
NO_FRAME_REPORT_INTERVAL_S = 0.25  # how often to report "no frames" while waiting
NO_FRAMES_ISSUE = "Camera is not delivering frames"
MAX_CONSECUTIVE_ANALYSIS_ERRORS = 30

OVERLAY_SHOULDER_BGR = (196, 107, 124)  # lavender-plum
OVERLAY_EAR_BGR = (150, 214, 160)  # mint
OVERLAY_FACE_BGR = (170, 200, 247)  # peach


def draw_overlay(frame: Frame, overlay: Overlay) -> None:
    """Draw landmarks in place on a preview-only copy of the frame."""
    h, w = frame.shape[:2]

    def px(point: tuple[float, float]) -> tuple[int, int]:
        return int(point[0] * w), int(point[1] * h)

    if len(overlay.shoulders) == 2:
        cv2.line(frame, px(overlay.shoulders[0]), px(overlay.shoulders[1]), OVERLAY_SHOULDER_BGR, 2)
    for point in overlay.shoulders:
        cv2.circle(frame, px(point), 6, OVERLAY_SHOULDER_BGR, -1)
    for point in overlay.ears:
        cv2.circle(frame, px(point), 5, OVERLAY_EAR_BGR, -1)
    for point in overlay.face:
        cv2.circle(frame, px(point), 3, OVERLAY_FACE_BGR, -1)


def to_preview_image(frame: Frame, overlay: Overlay | None) -> QImage:
    h, w = frame.shape[:2]
    scale = PREVIEW_WIDTH / w
    small = np.asarray(
        cv2.resize(frame, (PREVIEW_WIDTH, round(h * scale)), interpolation=cv2.INTER_AREA),
        dtype=np.uint8,
    )
    if overlay is not None:
        draw_overlay(small, overlay)
    mirrored = cv2.flip(small, 1)  # mirror so the preview feels like a mirror
    rgb = cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]
    image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888)
    return image.copy()  # detach from the NumPy buffer before crossing threads


class MonitorWorker(QObject):
    camera_started = Signal(int, int)  # actual frame width, height
    observation_ready = Signal(object)  # Observation
    preview_ready = Signal(QImage)
    failed = Signal(str)  # user-facing message
    finished = Signal()

    def __init__(
        self,
        source_factory: Callable[[], FrameSource],
        analyzer_factory: Callable[[], Analyzer],
        clock: Callable[[], float] = time.monotonic,
        max_fps: float = MAX_INFERENCE_FPS,
    ) -> None:
        super().__init__()
        self._source_factory = source_factory
        self._analyzer_factory = analyzer_factory
        self._clock = clock
        self._frame_interval = 1.0 / max_fps
        self._stop = threading.Event()
        # Simple bools are atomic to read/write; the worker only reads them.
        self.preview_enabled = True
        self.overlay_enabled = True

    def stop(self) -> None:
        """Thread-safe request to stop; the loop exits within one frame interval."""
        self._stop.set()

    @Slot()
    def run(self) -> None:
        analyzer: Analyzer | None = None
        source: FrameSource | None = None
        try:
            try:
                analyzer = self._analyzer_factory()
            except Exception as exc:
                log.exception("Model initialisation failed")
                self.failed.emit(f"Posture models could not be loaded: {exc}")
                return
            if self._stop.is_set():
                return
            try:
                source = self._source_factory()
                width, height = source.open()
            except CameraError as exc:
                self.failed.emit(str(exc))
                return
            self.camera_started.emit(width, height)
            self._loop(source, analyzer)
        finally:
            if source is not None:
                source.release()
            if analyzer is not None:
                analyzer.close()
            self.finished.emit()

    def _loop(self, source: FrameSource, analyzer: Analyzer) -> None:
        last_good_frame = self._clock()
        last_gap_report = 0.0
        last_preview = 0.0
        analysis_errors = 0
        reopened = False
        while not self._stop.is_set():
            started = self._clock()
            frame = source.read()
            if frame is None:
                # Report the gap so the UI never keeps showing a stale posture state.
                if started - last_gap_report >= NO_FRAME_REPORT_INTERVAL_S:
                    last_gap_report = started
                    self.observation_ready.emit(
                        Observation(started, None, None, NO_FRAMES_ISSUE, NO_FRAMES_ISSUE)
                    )
                if started - last_good_frame > FRAME_FAILURE_TIMEOUT_S:
                    if reopened:
                        self.failed.emit("The camera stopped delivering frames.")
                        return
                    # Typical after sleep/resume or a USB hiccup: reopen the device once.
                    reopened = True
                    if not self._reopen(source):
                        return
                    last_good_frame = self._clock()
                    continue
                self._stop.wait(0.05)
                continue
            last_good_frame = started
            reopened = False

            try:
                analysis = analyzer.analyze(frame, started)
                analysis_errors = 0
            except Exception:
                analysis_errors += 1
                log.exception("Frame analysis failed")
                if analysis_errors >= MAX_CONSECUTIVE_ANALYSIS_ERRORS:
                    self.failed.emit("Posture analysis keeps failing; monitoring stopped.")
                    return
                self.observation_ready.emit(
                    Observation(started, None, None, "Analysis error", "Analysis error")
                )
                continue

            self.observation_ready.emit(analysis.observation)
            if self.preview_enabled and started - last_preview >= 1.0 / MAX_PREVIEW_FPS:
                last_preview = started
                overlay = analysis.overlay if self.overlay_enabled else None
                self.preview_ready.emit(to_preview_image(frame, overlay))

            remaining = self._frame_interval - (self._clock() - started)
            if remaining > 0:
                self._stop.wait(remaining)

    def _reopen(self, source: FrameSource) -> bool:
        log.warning("No camera frames for %.1f s; reopening the camera", FRAME_FAILURE_TIMEOUT_S)
        source.release()
        try:
            width, height = source.open()
        except CameraError as exc:
            self.failed.emit(str(exc))
            return False
        # Re-announce the size: the controller recalibrates if the resolution changed.
        self.camera_started.emit(width, height)
        return True
