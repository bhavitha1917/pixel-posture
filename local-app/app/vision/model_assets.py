"""MediaPipe model bundles: location, provenance and integrity verification.

Both models are published by Google under the Apache License 2.0 at
https://storage.googleapis.com/mediapipe-models/ (see the MediaPipe model cards). They are
downloaded by ``local-app/scripts/download_models.py`` and are not committed to Git.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelAsset:
    filename: str
    url: str
    sha256: str
    description: str


POSE_MODEL = ModelAsset(
    filename="pose_landmarker_lite.task",
    url=(
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
    ),
    sha256="59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
    description="MediaPipe Pose Landmarker (lite, float16)",
)

FACE_MODEL = ModelAsset(
    filename="face_landmarker.task",
    url=(
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/1/face_landmarker.task"
    ),
    sha256="64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    description="MediaPipe Face Landmarker (float16)",
)

ALL_MODELS = (POSE_MODEL, FACE_MODEL)


def resources_dir() -> Path:
    """``app/resources`` both from source and inside a PyInstaller bundle."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root) / "app" / "resources"
    return Path(__file__).resolve().parent.parent / "resources"


def models_dir() -> Path:
    return resources_dir() / "models"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def missing_or_invalid(directory: Path | None = None) -> list[ModelAsset]:
    """Models that are absent or fail their hash check."""
    directory = directory or models_dir()
    bad = []
    for asset in ALL_MODELS:
        path = directory / asset.filename
        if not path.is_file() or sha256_of(path) != asset.sha256:
            bad.append(asset)
    return bad


def load_model_bytes(asset: ModelAsset, directory: Path | None = None) -> bytes:
    """Read a verified model into memory (avoids MediaPipe path-encoding issues on Windows)."""
    path = (directory or models_dir()) / asset.filename
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != asset.sha256:
        raise ValueError(f"{asset.filename} failed integrity check; re-run download_models.py")
    return data
