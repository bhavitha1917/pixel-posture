"""Body landmarks from MediaPipe Pose Landmarker (Tasks API, VIDEO running mode)."""

from __future__ import annotations

from typing import Any

from mediapipe.tasks.python import BaseOptions, vision

from app.posture.features import LandmarkPoint
from app.vision.model_assets import POSE_MODEL, load_model_bytes


class PoseLandmarkExtractor:
    def __init__(self) -> None:
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=load_model_bytes(POSE_MODEL)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def detect(self, image: Any, timestamp_ms: int) -> list[LandmarkPoint] | None:
        """Landmarks of the most prominent person, or None if nobody is detected."""
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        if not result.pose_landmarks:
            return None
        return [
            LandmarkPoint(
                x=float(lm.x),
                y=float(lm.y),
                visibility=float(lm.visibility) if lm.visibility is not None else 0.0,
            )
            for lm in result.pose_landmarks[0]
        ]

    def close(self) -> None:
        self._landmarker.close()
