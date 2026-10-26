"""FrameAnalyzer: one BGR frame -> one immutable Observation (+ points for the preview)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2
import mediapipe as mp
import numpy as np

from app.posture.config import LandmarkQuality
from app.posture.features import (
    LEFT_EAR,
    LEFT_SHOULDER,
    RIGHT_EAR,
    RIGHT_SHOULDER,
    compute_body_features,
)
from app.posture.models import Observation
from app.vision.camera import Frame
from app.vision.head_pose import HeadPoseEstimator
from app.vision.landmarks import PoseLandmarkExtractor

OVERLAY_POSE_POINTS = (LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_EAR, RIGHT_EAR)


@dataclass(frozen=True)
class Overlay:
    """Normalized (x, y) points to draw on the preview. Never persisted or logged."""

    shoulders: tuple[tuple[float, float], ...] = ()
    ears: tuple[tuple[float, float], ...] = ()
    face: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class Analysis:
    observation: Observation
    overlay: Overlay


class Analyzer(Protocol):
    def analyze(self, frame: Frame, timestamp: float) -> Analysis: ...
    def close(self) -> None: ...


class FrameAnalyzer:
    """Runs pose + face models. Not thread-safe: create and use it on the worker thread."""

    def __init__(self, quality: LandmarkQuality | None = None) -> None:
        self._quality = quality or LandmarkQuality()
        self._pose = PoseLandmarkExtractor()
        try:
            self._face = HeadPoseEstimator()
        except Exception:
            self._pose.close()
            raise
        self._last_ts_ms = -1

    def analyze(self, frame: Frame, timestamp: float) -> Analysis:
        height, width = frame.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode requires strictly increasing integer timestamps.
        ts_ms = max(int(timestamp * 1000), self._last_ts_ms + 1)
        self._last_ts_ms = ts_ms

        landmarks = self._pose.detect(image, ts_ms)
        body_issue: str | None
        if landmarks is None:
            body, body_issue = None, "No person detected"
            shoulders: tuple[tuple[float, float], ...] = ()
            ears: tuple[tuple[float, float], ...] = ()
        else:
            body, body_issue = compute_body_features(landmarks, width, height, self._quality)
            visible = [
                i
                for i in OVERLAY_POSE_POINTS
                if landmarks[i].visibility >= self._quality.min_visibility
            ]
            shoulders = tuple(
                (landmarks[i].x, landmarks[i].y)
                for i in visible
                if i in (LEFT_SHOULDER, RIGHT_SHOULDER)
            )
            ears = tuple(
                (landmarks[i].x, landmarks[i].y) for i in visible if i in (LEFT_EAR, RIGHT_EAR)
            )

        head = self._face.estimate(image, ts_ms)
        observation = Observation(
            timestamp=timestamp,
            body=body,
            head=head.features,
            body_issue=body_issue,
            head_issue=head.issue,
            frame_width=width,
            frame_height=height,
        )
        return Analysis(observation, Overlay(shoulders, ears, head.overlay_points))

    def close(self) -> None:
        self._pose.close()
        self._face.close()
