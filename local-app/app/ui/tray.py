"""System tray icon and menu. Actions only emit signals; the application decides."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app import APP_NAME
from app.posture.models import PetState
from app.services.monitor import MonitorStatus
from app.ui.pet_widget import pet_icon

STATUS_TEXT = {
    MonitorStatus.IDLE: "Not monitoring (camera off)",
    MonitorStatus.STARTING: "Starting camera…",
    MonitorStatus.RUNNING: "Monitoring",
    MonitorStatus.PAUSED: "Paused (camera off)",
    MonitorStatus.ERROR: "Camera problem",
}


def pet_state_for_status(status: MonitorStatus) -> PetState | None:
    """Pip's look when not monitoring; None while posture results should drive it."""
    if status in (MonitorStatus.RUNNING, MonitorStatus.STARTING):
        return None
    return PetState.CALIBRATING if status is MonitorStatus.IDLE else PetState.UNAVAILABLE


class TrayController(QObject):
    open_requested = Signal()
    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    settings_requested = Signal()
    floating_pet_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.icon = QSystemTrayIcon(pet_icon(PetState.CALIBRATING), parent)
        self.menu = QMenu()
        self.open_action = self.menu.addAction(f"Open {APP_NAME}")
        self.menu.addSeparator()
        self.start_action = self.menu.addAction("Start Monitoring")
        self.pause_action = self.menu.addAction("Pause Monitoring")
        self.resume_action = self.menu.addAction("Resume Monitoring")
        self.menu.addSeparator()
        self.floating_pet_action = self.menu.addAction("Show Pip on Desktop")
        self.floating_pet_action.setCheckable(True)
        self.settings_action = self.menu.addAction("Settings…")
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction(f"Quit {APP_NAME}")

        self.open_action.triggered.connect(self.open_requested.emit)
        self.start_action.triggered.connect(self.start_requested.emit)
        self.pause_action.triggered.connect(self.pause_requested.emit)
        self.resume_action.triggered.connect(self.resume_requested.emit)
        self.settings_action.triggered.connect(self.settings_requested.emit)
        self.floating_pet_action.toggled.connect(self.floating_pet_toggled.emit)
        self.quit_action.triggered.connect(self.quit_requested.emit)
        self.icon.activated.connect(self._on_activated)
        self.icon.setContextMenu(self.menu)

        self._status = MonitorStatus.IDLE
        self._pet_state = PetState.CALIBRATING
        self.update_status(MonitorStatus.IDLE)

    def show(self) -> None:
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.icon.show()

    def hide(self) -> None:
        self.icon.hide()

    @property
    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable() and self.icon.isVisible()

    def update_status(self, status: MonitorStatus) -> None:
        self._status = status
        active = status in (MonitorStatus.RUNNING, MonitorStatus.STARTING)
        self.start_action.setVisible(status in (MonitorStatus.IDLE, MonitorStatus.ERROR))
        self.pause_action.setVisible(active)
        self.resume_action.setVisible(status is MonitorStatus.PAUSED)
        idle_state = pet_state_for_status(status)
        if idle_state is not None:
            self.update_pet_state(idle_state)
        self._refresh_tooltip()

    def set_floating_pet_checked(self, checked: bool) -> None:
        self.floating_pet_action.blockSignals(True)
        self.floating_pet_action.setChecked(checked)
        self.floating_pet_action.blockSignals(False)

    def update_pet_state(self, state: PetState) -> None:
        if state is not self._pet_state:
            self._pet_state = state
            self.icon.setIcon(pet_icon(state))
        self._refresh_tooltip()

    def _refresh_tooltip(self) -> None:
        text = f"{APP_NAME} – {STATUS_TEXT[self._status]}"
        if self._status is MonitorStatus.RUNNING:
            text += f" · Pip is {self._pet_state.value}"
        self.icon.setToolTip(text)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_requested.emit()
