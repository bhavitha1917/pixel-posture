"""Settings dialog. Returns a new, validated ``AppSettings``; it never mutates the old one."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.posture.config import Sensitivity
from app.settings.store import MAX_CAMERA_INDEX, MIN_CRITICAL_GAP_S, AppSettings

SENSITIVITY_LABELS = {
    Sensitivity.RELAXED: "Relaxed (fewer reminders)",
    Sensitivity.BALANCED: "Balanced",
    Sensitivity.STRICT: "Strict (more reminders)",
}
MOTION_CHOICES: list[tuple[str, bool | None]] = [
    ("Follow Windows setting", None),
    ("Animate Pip", False),
    ("Reduce motion", True),
]


def seconds_box(low: float, high: float, value: float, step: float = 1.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(low, high)
    box.setDecimals(0)
    box.setSingleStep(step)
    box.setSuffix(" s")
    box.setValue(value)
    return box


class SettingsDialog(QDialog):
    test_notification_requested = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pixel Posture Settings")
        self.setMinimumWidth(460)
        self._original = settings
        self._forget_baseline = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        detection = QGroupBox("Detection")
        form = QFormLayout(detection)
        self.camera = QSpinBox()
        self.camera.setRange(0, MAX_CAMERA_INDEX)
        self.camera.setValue(settings.camera_index)
        form.addRow("Camera index", self.camera)
        self.sensitivity = QComboBox()
        for value, text in SENSITIVITY_LABELS.items():
            self.sensitivity.addItem(text, value)
        self.sensitivity.setCurrentIndex(list(SENSITIVITY_LABELS).index(settings.sensitivity))
        form.addRow("Sensitivity", self.sensitivity)
        self.warning = seconds_box(3, 120, settings.warning_seconds)
        form.addRow("Warning after", self.warning)
        self.critical = seconds_box(8, 600, settings.critical_seconds, 5)
        form.addRow("Critical after", self.critical)
        self.recovery = seconds_box(1, 30, settings.recovery_seconds)
        form.addRow("Recovery confirmation", self.recovery)
        note = QLabel(
            "Critical also requires a clearly larger deviation, not just more time. "
            "These are experimental defaults, not medical thresholds."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)
        self.warning.valueChanged.connect(self._sync_critical_minimum)
        self._sync_critical_minimum()
        layout.addWidget(detection)

        alerts = QGroupBox("Reminders")
        alerts_form = QFormLayout(alerts)
        self.notifications = QCheckBox("Show Windows notifications")
        self.notifications.setChecked(settings.notifications_enabled)
        self.recovery_notify = QCheckBox("Also notify when posture recovers")
        self.recovery_notify.setChecked(settings.notify_on_recovery)
        self.sound = QCheckBox("Play a short sound")
        self.sound.setChecked(settings.sound_enabled)
        self.cooldown = seconds_box(10, 1800, settings.cooldown_seconds, 10)
        alerts_form.addRow(self.notifications)
        alerts_form.addRow(self.recovery_notify)
        alerts_form.addRow(self.sound)
        alerts_form.addRow("Minimum gap between notifications", self.cooldown)
        test = QPushButton("Send test notification")
        test.setObjectName("ghost")
        test.clicked.connect(self.test_notification_requested.emit)
        alerts_form.addRow(test)
        layout.addWidget(alerts)

        app_box = QGroupBox("App")
        app_form = QFormLayout(app_box)
        self.close_to_tray = QCheckBox("Close button keeps Pixel Posture running in the tray")
        self.close_to_tray.setChecked(settings.close_to_tray)
        self.preview = QCheckBox("Show camera preview")
        self.preview.setChecked(settings.show_preview)
        self.landmarks = QCheckBox("Draw landmarks on the preview")
        self.landmarks.setChecked(settings.show_landmarks)
        self.motion = QComboBox()
        for text, motion in MOTION_CHOICES:
            self.motion.addItem(text, motion)
        self.motion.setCurrentIndex([v for _, v in MOTION_CHOICES].index(settings.reduce_motion))
        app_form.addRow(self.close_to_tray)
        app_form.addRow(self.preview)
        app_form.addRow(self.landmarks)
        app_form.addRow("Pet animation", self.motion)
        layout.addWidget(app_box)

        calibration_row = QHBoxLayout()
        baseline = settings.baseline
        status = (
            f"Calibrated {baseline.created_at[:10]} (camera {baseline.camera_index})"
            if baseline
            else "Not calibrated yet"
        )
        self.calibration_label = QLabel(status)
        self.calibration_label.setObjectName("muted")
        calibration_row.addWidget(self.calibration_label, 1)
        self.forget = QPushButton("Forget calibration")
        self.forget.setObjectName("ghost")
        self.forget.setEnabled(settings.baseline is not None)
        self.forget.clicked.connect(self._on_forget)
        calibration_row.addWidget(self.forget)
        layout.addLayout(calibration_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_critical_minimum(self) -> None:
        self.critical.setMinimum(self.warning.value() + MIN_CRITICAL_GAP_S)

    def _on_forget(self) -> None:
        self._forget_baseline = True
        self.calibration_label.setText("Calibration will be cleared when you save")
        self.forget.setEnabled(False)

    def result_settings(self) -> AppSettings:
        return replace(
            self._original,
            camera_index=self.camera.value(),
            sensitivity=Sensitivity(self.sensitivity.currentData()),
            warning_seconds=self.warning.value(),
            critical_seconds=self.critical.value(),
            recovery_seconds=self.recovery.value(),
            cooldown_seconds=self.cooldown.value(),
            notifications_enabled=self.notifications.isChecked(),
            notify_on_recovery=self.recovery_notify.isChecked(),
            sound_enabled=self.sound.isChecked(),
            close_to_tray=self.close_to_tray.isChecked(),
            show_preview=self.preview.isChecked(),
            show_landmarks=self.landmarks.isChecked(),
            reduce_motion=self.motion.currentData(),
            baseline=None if self._forget_baseline else self._original.baseline,
        ).validated()
