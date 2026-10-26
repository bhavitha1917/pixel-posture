"""Head pose from MediaPipe Face Landmarker's facial transformation matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from app.posture.features import head_angles_from_matrix
from app.posture.models import HeadFeatures
from app.vision.model_assets import FACE_MODEL, load_model_bytes

# Face-mesh indices drawn on the preview: forehead, nose tip, chin, outer eye corners.
OVERLAY_FACE_POINTS = (10, 1, 152, 33, 263)


@dataclass(frozen=True)
class HeadPoseResult:
    features: HeadFeatures | None
    issue: str | None
    overlay_points: tuple[tuple[float, float], ...] = ()


class HeadPoseEstimator:
    def __init__(self) -> None:
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=load_model_bytes(FACE_MODEL)),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def estimate(self, image: Any, timestamp_ms: int) -> HeadPoseResult:
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        if not result.face_landmarks or not result.facial_transformation_matrixes:
            return HeadPoseResult(None, "Face not detected")
        features = head_angles_from_matrix(np.asarray(result.facial_transformation_matrixes[0]))
        landmarks = result.face_landmarks[0]
        points = tuple(
            (float(landmarks[i].x), float(landmarks[i].y))
            for i in OVERLAY_FACE_POINTS
            if i < len(landmarks)
        )
        if features is None:
            return HeadPoseResult(None, "Head pose could not be estimated", points)
        return HeadPoseResult(features, None, points)

    def close(self) -> None:
        self._landmarker.close()
