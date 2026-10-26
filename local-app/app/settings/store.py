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
SETTINGS_VERSION = 2
# Version 1 defaults. A version-1 file still holding exactly these values never had them
# customised (every save writes every field), so it is moved to the gentler v2 defaults.
V1_TIMING_DEFAULTS = {"warning_seconds": 10.0, "critical_seconds": 30.0, "recovery_seconds": 3.0}
V1_COOLDOWN_DEFAULT = 30.0


@dataclass(frozen=True)
class AppSettings:
    camera_index: int = 0
    sensitivity: Sensitivity = Sensitivity.BALANCED
    warning_seconds: float = 30.0
    critical_seconds: float = 60.0
    recovery_seconds: float = 5.0
    cooldown_seconds: float = 60.0
    notifications_enabled: bool = True
    notify_on_recovery: bool = False
    sound_enabled: bool = True
    sound_volume: int = 70  # percent
    floating_pet_enabled: bool = True
    floating_pet_position: tuple[int, int] | None = None  # top-left, virtual desktop coords
    close_to_tray: bool = True
    show_preview: bool = True
    show_landmarks: bool = True
    reduce_motion: bool | None = None  # None = follow Windows animation setting
    tray_hint_shown: bool = False
    baseline: Baseline | None = field(default=None)
    settings_version: int = SETTINGS_VERSION

    def posture_config(self) -> PostureConfig:
        return PostureConfig(sensitivity=self.sensitivity).with_timing(
            warning_s=self.warning_seconds,
            critical_s=self.critical_seconds,
            recovery_s=self.recovery_seconds,
        )

    def validated(self) -> AppSettings:
        """Clamp every numeric field to its documented range (README section 19)."""
        defaults = AppSettings()
        warning = _clamp(self.warning_seconds, 3.0, 120.0, defaults.warning_seconds)
        return replace(
            self,
            sensitivity=Sensitivity(self.sensitivity),
            camera_index=int(_clamp(self.camera_index, 0, MAX_CAMERA_INDEX, 0)),
            warning_seconds=warning,
            critical_seconds=_clamp(
                self.critical_seconds,
                warning + MIN_CRITICAL_GAP_S,
                600.0,
                max(defaults.critical_seconds, warning + MIN_CRITICAL_GAP_S),
            ),
            recovery_seconds=_clamp(self.recovery_seconds, 1.0, 30.0, defaults.recovery_seconds),
            cooldown_seconds=_clamp(self.cooldown_seconds, 10.0, 1800.0, defaults.cooldown_seconds),
            sound_volume=int(_clamp(self.sound_volume, 0, 100, defaults.sound_volume)),
            settings_version=SETTINGS_VERSION,
        )

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sensitivity"] = self.sensitivity.value
        data["baseline"] = self.baseline.to_dict() if self.baseline else None
        position = self.floating_pet_position
        data["floating_pet_position"] = list(position) if position else None
        return data

    @classmethod
    def from_json_dict(cls, data: object) -> AppSettings:
        return cls.load_json_dict(data)[0]

    @classmethod
    def load_json_dict(cls, data: object) -> tuple[AppSettings, list[str]]:
        """Parse untrusted JSON. Also returns user-facing notes about any migration."""
        if not isinstance(data, dict):
            return cls(), []
        data, notes = _migrate(data)
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
            "floating_pet_enabled",
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
        volume = data.get("sound_volume")
        kwargs["sound_volume"] = (
            volume
            if isinstance(volume, int) and not isinstance(volume, bool)
            else defaults.sound_volume
        )
        kwargs["floating_pet_position"] = _position(data.get("floating_pet_position"))
        reduce_motion = data.get("reduce_motion")
        kwargs["reduce_motion"] = reduce_motion if isinstance(reduce_motion, bool) else None
        try:
            kwargs["sensitivity"] = Sensitivity(str(data.get("sensitivity")))
        except ValueError:
            kwargs["sensitivity"] = defaults.sensitivity
        kwargs["baseline"] = Baseline.from_dict(data.get("baseline"))
        return cls(**kwargs).validated(), notes


def _migrate(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Upgrade a version-1 file. Values the user changed are kept exactly as they were."""
    version = data.get("settings_version")
    if isinstance(version, int) and not isinstance(version, bool) and version >= 2:
        return data, []
    data = dict(data)
    notes: list[str] = []
    defaults = AppSettings()
    if all(data.get(name) == old for name, old in V1_TIMING_DEFAULTS.items()):
        for name in V1_TIMING_DEFAULTS:
            data[name] = getattr(defaults, name)
        notes.append(
            f"Reminders are now gentler: Warning after {defaults.warning_seconds:.0f} s, "
            f"Critical after {defaults.critical_seconds:.0f} s of clear slouching, "
            f"recovery after {defaults.recovery_seconds:.0f} s."
        )
    if data.get("cooldown_seconds") == V1_COOLDOWN_DEFAULT:
        data["cooldown_seconds"] = defaults.cooldown_seconds
        notes.append(f"Notifications now come at most every {defaults.cooldown_seconds:.0f} s.")
    if notes:
        log.info("Migrated version-1 settings to the new reminder defaults")
    return data, notes


def _position(value: object) -> tuple[int, int] | None:
    if (
        isinstance(value, list | tuple)
        and len(value) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
        and all(abs(v) <= 100_000 for v in value)
    ):
        return (value[0], value[1])
    return None


def _clamp(value: float, low: float, high: float, fallback: float) -> float:
    if not math.isfinite(value):
        return fallback
    return min(max(float(value), low), high)


class SettingsStore:
    """Loads and atomically saves settings at a fixed path inside the app-data folder."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.migration_notes: list[str] = []  # filled by load(), shown once by the app

    def load(self) -> AppSettings:
        self.migration_notes = []
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Settings file unreadable (%s); backing up and using defaults", exc)
            self._backup_corrupt()
            return AppSettings()
        settings, self.migration_notes = AppSettings.load_json_dict(data)
        return settings

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
