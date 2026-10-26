"""Webcam capture through OpenCV. One ``CameraSource`` owns one device at a time."""

from __future__ import annotations

import logging
import sys
from typing import Protocol

import cv2
import numpy as np
import numpy.typing as npt

log = logging.getLogger(__name__)

Frame = npt.NDArray[np.uint8]

REQUESTED_WIDTH = 640
REQUESTED_HEIGHT = 480
MAX_PROBE_INDEX = 5


class CameraError(RuntimeError):
    """Camera could not be opened or stopped delivering frames."""


class FrameSource(Protocol):
    """A camera-like source. ``release()`` must be idempotent (safe to call twice)."""

    def open(self) -> tuple[int, int]: ...
    def read(self) -> Frame | None: ...
    def release(self) -> None: ...


def _backends() -> list[int]:
    # DirectShow opens quickly on Windows; fall back to OpenCV's default (MSMF).
    if sys.platform == "win32":
        return [cv2.CAP_DSHOW, cv2.CAP_ANY]
    return [cv2.CAP_ANY]


class CameraSource:
    def __init__(self, index: int) -> None:
        self.index = index
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> tuple[int, int]:
        """Open the device and return the actual (width, height). Raises CameraError."""
        if self._capture is not None:
            raise CameraError("Camera is already open")
        for backend in _backends():
            capture = cv2.VideoCapture(self.index, backend)
            if not capture.isOpened():
                capture.release()
                continue
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, REQUESTED_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, REQUESTED_HEIGHT)
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.release()
                continue
            self._capture = capture
            height, width = frame.shape[:2]
            log.info("Camera %d opened at %dx%d", self.index, width, height)
            return width, height
        raise CameraError(
            f"Camera {self.index} could not be opened. It may be in use by another app, "
            "disconnected, or blocked in Windows camera privacy settings."
        )

    def read(self) -> Frame | None:
        if self._capture is None:
            return None
        ok, frame = self._capture.read()
        if not ok or frame is None:
            return None
        return np.asarray(frame, dtype=np.uint8)

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            log.info("Camera %d released", self.index)


def probe_cameras(max_index: int = MAX_PROBE_INDEX) -> list[int]:
    """Indices that open and return a frame.

    This briefly opens each device (the camera light may flash), so it is only ever run
    when the user explicitly asks to detect cameras.
    """
    found = []
    for index in range(max_index):
        source = CameraSource(index)
        try:
            source.open()
        except CameraError:
            continue
        finally:
            source.release()
        found.append(index)
    return found
