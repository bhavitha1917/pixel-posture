"""PixelPostureApp: wires the controller, main window, tray, settings and notifications."""

from __future__ import annotations

import logging
import threading
from dataclasses import replace

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from app import APP_NAME
from app.posture.config import Sensitivity
from app.posture.models import PostureResult
from app.services.alerts import Alert
from app.services.monitor import MonitorController, MonitorStatus
from app.services.notifications import AlertDispatcher, TrayNotificationBackend
from app.services.sound import ChimePlayer
from app.settings.store import AppSettings, SettingsStore
from app.ui.floating_pet import FloatingPet
from app.ui.main_window import CAMERA_CHOICES, MainWindow
from app.ui.pet_widget import system_prefers_reduced_motion
from app.ui.settings_dialog import SettingsDialog
from app.ui.tray import TrayController
from app.vision.analyzer import FrameAnalyzer
from app.vision.camera import CameraSource, probe_cameras
from app.vision.model_assets import missing_or_invalid

log = logging.getLogger(__name__)

STATS_REFRESH_MS = 1000
TEST_ALERT = Alert(
    "Pixel Posture test",
    "Notifications are working. Pip will remind you like this.",
    None,
    None,
)


class PixelPostureApp(QObject):
    cameras_detected = Signal(list)

    def __init__(self, qt_app: QApplication, store: SettingsStore, settings: AppSettings) -> None:
        super().__init__()
        self._qt_app = qt_app
        self._store = store
        self._settings = settings
        self._quitting = False

        self.controller = MonitorController(settings, CameraSource, FrameAnalyzer)
        self.tray = TrayController(self)
        self.tray.show()
        self.chime = ChimePlayer(store.path.parent / "cache" / "sounds", settings.sound_volume)
        self.dispatcher = AlertDispatcher(TrayNotificationBackend(self.tray.icon), self.chime)
        self.controller.set_dispatcher(self.dispatcher)
        self.window = MainWindow(settings)
        self.pet_window = FloatingPet()
        self._apply_motion_preference()
        self._apply_floating_pet()

        missing = missing_or_invalid()
        if missing:
            names = ", ".join(m.filename for m in missing)
            self.window.set_models_ok(False)
            self.window.banner.show_message(
                f"Model files missing or damaged ({names}). Run "
                "'python local-app/scripts/download_models.py' and restart Pixel Posture.",
                "bad",
            )
        if not self.tray.available:
            self.window.banner.show_message(
                "The system tray is unavailable, so closing the window will ask before quitting "
                "and notifications appear in this window only.",
                "warn",
            )
        if store.migration_notes:
            if self.window.banner.isHidden():  # a problem banner above takes priority
                self.window.banner.show_message(" ".join(store.migration_notes), "info")
            self._save()  # record the migration so the note is shown only once
        self._connect()

        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(STATS_REFRESH_MS)
        self._stats_timer.timeout.connect(lambda: self.window.update_stats(self.controller.stats))
        self._stats_timer.start()

    def _connect(self) -> None:
        c, w, t = self.controller, self.window, self.tray
        c.status_changed.connect(self._on_status)
        c.result_ready.connect(self._on_result)
        c.preview_ready.connect(w.show_preview)
        c.alert_raised.connect(w.show_alert)
        c.settings_changed.connect(self._on_controller_settings)
        c.notice.connect(lambda text: w.banner.show_message(text, "info"))

        w.start_clicked.connect(c.start)
        w.pause_clicked.connect(c.pause)
        w.resume_clicked.connect(c.resume)
        w.stop_clicked.connect(c.stop)
        w.calibrate_clicked.connect(c.calibrate)
        w.settings_clicked.connect(self.open_settings)
        w.detect_cameras_clicked.connect(self._detect_cameras)
        w.camera_selected.connect(lambda i: self._update_settings(camera_index=i))
        w.sound_toggled.connect(lambda on: self._update_settings(sound_enabled=on))
        w.preview_toggled.connect(lambda on: self._update_settings(show_preview=on))
        w.landmarks_toggled.connect(lambda on: self._update_settings(show_landmarks=on))
        w.sensitivity_selected.connect(self._on_sensitivity)
        w.close_requested.connect(self._on_close_requested)
        w.visibility_changed.connect(self._on_visibility)
        self.cameras_detected.connect(self._on_cameras_detected)

        t.open_requested.connect(self.show_window)
        t.start_requested.connect(c.start)
        t.pause_requested.connect(c.pause)
        t.resume_requested.connect(c.resume)
        t.settings_requested.connect(self.open_settings)
        t.floating_pet_toggled.connect(lambda on: self._update_settings(floating_pet_enabled=on))
        t.quit_requested.connect(self.quit)

        p = self.pet_window
        p.open_dashboard_requested.connect(self.show_window)
        p.start_requested.connect(c.start)
        p.pause_requested.connect(c.pause)
        p.resume_requested.connect(c.resume)
        p.hide_requested.connect(self._hide_floating_pet)
        p.quit_requested.connect(self.quit)
        p.moved.connect(lambda x, y: self._update_settings(floating_pet_position=(x, y)))
        w.floating_pet_toggled.connect(lambda on: self._update_settings(floating_pet_enabled=on))
        self._qt_app.aboutToQuit.connect(self._on_about_to_quit)

    # ------------------------------------------------------------------ settings
    @property
    def settings(self) -> AppSettings:
        return self._settings

    def _update_settings(self, **changes: object) -> None:
        self._set_settings(replace(self._settings, **changes).validated())  # type: ignore[arg-type]

    def _set_settings(self, settings: AppSettings) -> None:
        self._settings = settings
        self.controller.apply_settings(settings)
        self.window.apply_settings(settings)
        self.chime.volume = settings.sound_volume
        self._apply_motion_preference()
        self._apply_floating_pet()
        self._save()

    def _on_sensitivity(self, value: Sensitivity) -> None:
        self._update_settings(sensitivity=value)

    def _on_controller_settings(self, settings: AppSettings) -> None:
        # The controller only changes the baseline; keep every other field from the app.
        self._settings = replace(self._settings, baseline=settings.baseline)
        self._save()

    def _save(self) -> None:
        try:
            self._store.save(self._settings)
        except OSError as exc:
            log.error("Could not save settings: %s", exc)
            self.window.banner.show_message(f"Settings could not be saved: {exc}", "bad")

    def _apply_motion_preference(self) -> None:
        reduce = self._settings.reduce_motion
        if reduce is None:
            reduce = system_prefers_reduced_motion()
        self.window.pet.set_reduce_motion(reduce)

    def _apply_floating_pet(self) -> None:
        enabled = self._settings.floating_pet_enabled and not self._quitting
        self.tray.set_floating_pet_checked(enabled)
        if enabled and not self.pet_window.isVisible():
            self.pet_window.show_at(self._settings.floating_pet_position)
        elif not enabled and self.pet_window.isVisible():
            self.pet_window.hide()

    def _hide_floating_pet(self) -> None:
        self._update_settings(floating_pet_enabled=False)
        hint = "Pip is hidden. Show it again from the tray menu or Quick settings."
        self.window.banner.show_message(hint, "info")
        if self.tray.available and not self.window.isVisible():
            self.tray.icon.showMessage("Pip is hidden", hint, self.tray.icon.icon(), 6000)

    def open_settings(self) -> None:
        self.show_window()
        dialog = SettingsDialog(self._settings, self.window, self.chime.asset_available)
        dialog.test_notification_requested.connect(self._send_test_notification)
        dialog.sound_preview_requested.connect(self.chime.preview)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self._set_settings(dialog.result_settings())

    def _send_test_notification(self) -> None:
        report = self.dispatcher.deliver(
            TEST_ALERT, notifications_enabled=True, sound_enabled=self._settings.sound_enabled
        )
        if report.error:
            self.window.banner.show_message(f"Test notification failed: {report.error}", "bad")
        else:
            self.window.banner.show_message(
                "Test notification sent. If nothing appeared, check Windows notification and "
                "Do Not Disturb settings.",
                "info",
            )

    # ------------------------------------------------------------------ camera detection
    def _detect_cameras(self) -> None:
        if self.controller.has_worker:
            return
        self.window.detect_button.setEnabled(False)
        self.window.detect_button.setText("Detecting…")
        threading.Thread(
            target=lambda: self.cameras_detected.emit(probe_cameras(CAMERA_CHOICES)),
            name="CameraProbe",
            daemon=True,
        ).start()

    def _on_cameras_detected(self, found: list[int]) -> None:
        self.window.detect_button.setText("Detect")
        self.window.detect_button.setEnabled(not self.controller.has_worker)
        current = self._settings.camera_index
        if found and current not in found:
            current = found[0]
            self._update_settings(camera_index=current)
        self.window.set_camera_choices(found or [current], current, detected=bool(found))
        if found:
            listed = ", ".join(str(i) for i in found)
            self.window.banner.show_message(f"Working cameras: {listed}.", "good")
        else:
            self.window.banner.show_message(
                "No working camera found. Check the connection, close apps using the camera, "
                "and allow desktop apps in Windows camera privacy settings.",
                "warn",
            )

    # ------------------------------------------------------------------ status / results
    def _on_status(self, status: MonitorStatus) -> None:
        self.window.set_status(status)
        self.tray.update_status(status)
        self.pet_window.set_monitor_status(status)
        if status is MonitorStatus.ERROR and self.controller.last_error:
            self.window.banner.show_message(self.controller.last_error, "bad")
            if not self.window.isVisible():
                try:
                    TrayNotificationBackend(self.tray.icon).notify(
                        "Pixel Posture stopped monitoring", self.controller.last_error, True
                    )
                except RuntimeError:
                    log.warning("Could not notify about the camera error")
        elif status is MonitorStatus.RUNNING:
            self.window.reminder.hide()

    def _on_result(self, result: PostureResult) -> None:
        self.window.show_result(result)
        if self.controller.status is MonitorStatus.RUNNING:
            self.tray.update_pet_state(result.state)
            self.pet_window.set_state(result.state)

    def _on_visibility(self, visible: bool) -> None:
        self.controller.set_preview_wanted(visible)
        self.window.pet.set_animating(visible)

    # ------------------------------------------------------------------ window lifecycle
    def show_window(self) -> None:
        self.window.bring_to_front()

    def _on_close_requested(self) -> None:
        if self._settings.close_to_tray and self.tray.available:
            self.window.hide()
            if not self._settings.tray_hint_shown:
                self.tray.icon.showMessage(
                    f"{APP_NAME} is still running",
                    "Monitoring continues in the system tray. Right-click Pip's icon to pause "
                    "or quit.",
                    self.tray.icon.icon(),
                    8000,
                )
                self._update_settings(tray_hint_shown=True)
            return

        box = QMessageBox(self.window)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Quit Pixel Posture?")
        box.setInformativeText("Quitting stops monitoring and turns the camera off.")
        quit_button = box.addButton("Quit", QMessageBox.ButtonRole.AcceptRole)
        tray_button = None
        if self.tray.available:
            tray_button = box.addButton("Keep running in tray", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is quit_button:
            self.quit()
        elif tray_button is not None and box.clickedButton() is tray_button:
            self.window.hide()

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        log.info("Quitting")
        self._stats_timer.stop()
        self.controller.shutdown()
        self._save()
        self.tray.hide()
        self.pet_window.hide()
        self.pet_window.close()
        self.window.allow_close = True
        self.window.close()
        self._qt_app.quit()

    def _on_about_to_quit(self) -> None:
        # Also covers Windows logoff/shutdown, which quits the event loop directly.
        self.controller.shutdown()
