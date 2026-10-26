"""Notification delivery: native Windows notifications via the tray icon, plus sound.

``QSystemTrayIcon.showMessage`` uses ``Shell_NotifyIcon`` on Windows; Windows 10/11 render
these as native toast notifications attributed to the tray icon's process. This needs no
AppUserModelID registration and follows the user's Do Not Disturb / Focus settings.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from app.posture.models import SignalLevel
from app.services.alerts import Alert

log = logging.getLogger(__name__)

NOTIFICATION_TIMEOUT_MS = 8000


class NotificationBackend(Protocol):
    def notify(self, title: str, message: str, critical: bool) -> None: ...


class SoundPlayer(Protocol):
    def play(self) -> None: ...


class TrayNotificationBackend:
    def __init__(self, tray: QSystemTrayIcon) -> None:
        self._tray = tray

    def notify(self, title: str, message: str, critical: bool) -> None:
        if not QSystemTrayIcon.supportsMessages() or not self._tray.isVisible():
            raise RuntimeError("System tray notifications are not available")
        icon = (
            QSystemTrayIcon.MessageIcon.Warning
            if critical
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._tray.showMessage(title, message, icon, NOTIFICATION_TIMEOUT_MS)


class SystemSoundPlayer:
    """Plays the Windows 'asterisk' sound asynchronously (``MessageBeep`` does not block)."""

    def play(self) -> None:
        if sys.platform == "win32":
            import winsound  # noqa: PLC0415 - Windows-only stdlib module

            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            QApplication.beep()


@dataclass(frozen=True)
class DeliveryReport:
    notified: bool
    sound_played: bool
    error: str | None = None


class AlertDispatcher:
    """Delivers alerts and swallows delivery failures so monitoring always continues."""

    def __init__(self, backend: NotificationBackend, sound: SoundPlayer) -> None:
        self._backend = backend
        self._sound = sound

    def deliver(
        self, alert: Alert, *, notifications_enabled: bool, sound_enabled: bool
    ) -> DeliveryReport:
        notified = sound_played = False
        errors: list[str] = []
        if notifications_enabled:
            try:
                self._backend.notify(
                    alert.title, alert.message, alert.level is SignalLevel.CRITICAL
                )
                notified = True
            except Exception as exc:
                log.warning("Notification delivery failed: %s", exc)
                errors.append(f"notification: {exc}")
        if sound_enabled:
            try:
                self._sound.play()
                sound_played = True
            except Exception as exc:
                log.warning("Alert sound failed: %s", exc)
                errors.append(f"sound: {exc}")
        return DeliveryReport(notified, sound_played, "; ".join(errors) or None)
