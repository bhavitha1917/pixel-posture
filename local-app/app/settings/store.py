"""AppSettings and its JSON store. Untrusted input is validated and clamped on load."""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from app.posture.config import PostureConfig, Sensitivity
from app.posture.models import Baseline

log = logging.getLogger(__name__)

MAX_CAMERA_INDEX = 9
MIN_CRITICAL_GAP_S = 5.0


@dataclass(frozen=True)
class AppSettings:
    camera_index: int = 0
    sensitivity: Sensitivity = Sensitivity.BALANCED
    warning_seconds: float = 10.0
    critical_seconds: float = 30.0
    recovery_seconds: float = 3.0
    cooldown_seconds: float = 30.0
    notifications_enabled: bool = True
    notify_on_recovery: bool = False
    sound_enabled: bool = True
    close_to_tray: bool = True
    show_preview: bool = True
    show_landmarks: bool = True
    reduce_motion: bool | None = None  # None = follow Windows animation setting
    tray_hint_shown: bool = False
    baseline: Baseline | None = field(default=None)

    def posture_config(self) -> PostureConfig:
        return PostureConfig(sensitivity=self.sensitivity).with_timing(
            warning_s=self.warning_seconds,
            critical_s=self.critical_seconds,
            recovery_s=self.recovery_seconds,
        )

    def validated(self) -> AppSettings:
        """Clamp every numeric field to its documented range (README section 19)."""
        warning = _clamp(self.warning_seconds, 3.0, 120.0, 10.0)
        return replace(
            self,
            sensitivity=Sensitivity(self.sensitivity),
            camera_index=int(_clamp(self.camera_index, 0, MAX_CAMERA_INDEX, 0)),
            warning_seconds=warning,
            critical_seconds=_clamp(
                self.critical_seconds, warning + MIN_CRITICAL_GAP_S, 600.0, 30.0
            ),
            recovery_seconds=_clamp(self.recovery_seconds, 1.0, 30.0, 3.0),
            cooldown_seconds=_clamp(self.cooldown_seconds, 10.0, 1800.0, 30.0),
        )

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sensitivity"] = self.sensitivity.value
        data["baseline"] = self.baseline.to_dict() if self.baseline else None
        return data

    @classmethod
    def from_json_dict(cls, data: object) -> AppSettings:
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        kwargs: dict[str, Any] = {}
        for name in (
            "notifications_enabled",
            "notify_on_recovery",
            "sound_enabled",
            "close_to_tray",
            "show_preview",
            "show_landmarks",
            "tray_hint_shown",
        ):
            value = data.get(name)
            kwargs[name] = value if isinstance(value, bool) else getattr(defaults, name)
        for name in ("warning_seconds", "critical_seconds", "recovery_seconds", "cooldown_seconds"):
            value = data.get(name)
            if isinstance(value, int | float) and not isinstance(value, bool):
                kwargs[name] = float(value)
            else:
                kwargs[name] = getattr(defaults, name)
        camera = data.get("camera_index")
        kwargs["camera_index"] = (
            camera
            if isinstance(camera, int) and not isinstance(camera, bool)
            else defaults.camera_index
        )
        reduce_motion = data.get("reduce_motion")
        kwargs["reduce_motion"] = reduce_motion if isinstance(reduce_motion, bool) else None
        try:
            kwargs["sensitivity"] = Sensitivity(str(data.get("sensitivity")))
        except ValueError:
            kwargs["sensitivity"] = defaults.sensitivity
        kwargs["baseline"] = Baseline.from_dict(data.get("baseline"))
        return cls(**kwargs).validated()


def _clamp(value: float, low: float, high: float, fallback: float) -> float:
    if not math.isfinite(value):
        return fallback
    return min(max(float(value), low), high)


class SettingsStore:
    """Loads and atomically saves settings at a fixed path inside the app-data folder."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Settings file unreadable (%s); backing up and using defaults", exc)
            self._backup_corrupt()
            return AppSettings()
        return AppSettings.from_json_dict(data)

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(settings.to_json_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def _backup_corrupt(self) -> None:
        try:
            os.replace(self.path, self.path.with_suffix(".json.bak"))
        except OSError as exc:
            log.warning("Could not back up corrupt settings: %s", exc)
