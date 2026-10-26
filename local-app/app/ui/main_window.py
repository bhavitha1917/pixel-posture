"""Main dashboard window. A view: it renders state and emits user intents as signals."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent, QImage, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME
from app.posture.config import Sensitivity
from app.posture.models import PetState, PostureResult, SignalKind, SignalLevel
from app.services.alerts import Alert
from app.services.monitor import MonitorStatus
from app.services.session import SessionStats
from app.settings.store import AppSettings
from app.ui.pet_widget import PetWidget, pet_icon
from app.ui.settings_dialog import SENSITIVITY_LABELS
from app.ui.theme import STATE_COLORS
from app.ui.widgets import Banner, Card, Chip, PreviewView, SignalPanel, StatTile, label
from app.ui.widgets import format_duration as fmt

CAMERA_CHOICES = 5
FIRST_RUN_TEXT = (
    "Camera is off.\n\n"
    "1. Pick your camera and sit comfortably upright.\n"
    "2. Press Start Monitoring. Pip calibrates to your usual posture first.\n"
    "3. Minimize or close this window. Pip keeps watch from the system tray.\n\n"
    "Frames are analysed on this computer only and never saved."
)

STATUS_CHIPS: dict[MonitorStatus, tuple[str, str, str, str]] = {
    # status: (camera text, camera tone, monitoring text, monitoring tone)
    MonitorStatus.IDLE: ("Camera off", "neutral", "Not monitoring", "neutral"),
    MonitorStatus.STARTING: ("Camera starting…", "info", "Starting", "info"),
    MonitorStatus.RUNNING: ("Camera on", "good", "Monitoring", "good"),
    MonitorStatus.PAUSED: ("Camera off", "neutral", "Paused", "warn"),
    MonitorStatus.ERROR: ("Camera problem", "bad", "Stopped", "bad"),
}


class MainWindow(QMainWindow):
    start_clicked = Signal()
    pause_clicked = Signal()
    resume_clicked = Signal()
    stop_clicked = Signal()
    calibrate_clicked = Signal()
    settings_clicked = Signal()
    detect_cameras_clicked = Signal()
    camera_selected = Signal(int)
    sound_toggled = Signal(bool)
    preview_toggled = Signal(bool)
    landmarks_toggled = Signal(bool)
    sensitivity_selected = Signal(object)  # Sensitivity
    close_requested = Signal()
    visibility_changed = Signal(bool)

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.allow_close = False
        self._status = MonitorStatus.IDLE
        self._models_ok = True
        self._show_preview = settings.show_preview
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(pet_icon(PetState.THRIVING))
        self.setMinimumSize(1000, 700)
        self.resize(1120, 760)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 18, 24, 20)
        outer.setSpacing(14)
        outer.addLayout(self._build_header())

        self.banner = Banner()
        self.reminder = Banner()
        outer.addWidget(self.banner)
        outer.addWidget(self.reminder)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addLayout(self._build_left_column(settings), 5)
        columns.addLayout(self._build_right_column(settings), 6)
        outer.addLayout(columns, 1)

        self.apply_settings(settings)
        self.set_status(MonitorStatus.IDLE)

    # ------------------------------------------------------------------ layout
    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(pet_icon(PetState.THRIVING).pixmap(44, 44))
        logo.setAccessibleName("Pixel Posture logo")
        header.addWidget(logo)
        brand = QVBoxLayout()
        brand.setSpacing(4)
        brand.addWidget(label("PIXEL POSTURE", "brand"))
        brand.addWidget(label("Your posture. Your pixel pal. Your gentle reminder.", "tagline"))
        header.addLayout(brand)
        header.addStretch()
        self.camera_chip = Chip()
        self.monitor_chip = Chip()
        header.addWidget(self.camera_chip)
        header.addWidget(self.monitor_chip)
        settings_button = QPushButton("Settings")
        settings_button.setObjectName("ghost")
        settings_button.setToolTip("Open settings (Ctrl+,)")
        settings_button.setShortcut("Ctrl+,")
        settings_button.clicked.connect(self.settings_clicked.emit)
        header.addWidget(settings_button)
        return header

    def _build_left_column(self, settings: AppSettings) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(16)

        pet_card = Card()
        top = QHBoxLayout()
        top.addWidget(label("YOUR PIXEL PAL", "eyebrow"))
        top.addStretch()
        top.addWidget(label("PIP", "petName"))
        pet_card.body.addLayout(top)
        self.pet = PetWidget()
        pet_card.body.addWidget(self.pet, 1)
        self.state_title = label("", "stateTitle")
        self.state_message = label("", "message", wrap=True)
        self.state_message.setMinimumHeight(40)
        self.state_message.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        pet_card.body.addWidget(self.state_title)
        pet_card.body.addWidget(self.state_message)
        self.calibration_progress = QProgressBar()
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setAccessibleName("Calibration progress")
        self.calibration_progress.hide()
        pet_card.body.addWidget(self.calibration_progress)

        controls = QHBoxLayout()
        self.start_button = QPushButton("Start Monitoring")
        self.start_button.setObjectName("primary")
        self.pause_button = QPushButton("Pause")
        self.resume_button = QPushButton("Resume")
        self.resume_button.setObjectName("primary")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("ghost")
        self.calibrate_button = QPushButton("Calibrate")
        self.calibrate_button.setObjectName("ghost")
        self.calibrate_button.setToolTip("Learn your comfortable neutral posture")
        for button, signal in (
            (self.start_button, self.start_clicked),
            (self.pause_button, self.pause_clicked),
            (self.resume_button, self.resume_clicked),
            (self.stop_button, self.stop_clicked),
            (self.calibrate_button, self.calibrate_clicked),
        ):
            button.clicked.connect(signal.emit)
            controls.addWidget(button)
        pet_card.body.addLayout(controls)
        column.addWidget(pet_card, 1)

        quick = Card()
        quick.body.addWidget(label("Quick settings", "cardTitle"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Camera"), 0, 0)
        self.camera_combo = QComboBox()
        self.camera_combo.setAccessibleName("Camera")
        self.set_camera_choices(list(range(CAMERA_CHOICES)), settings.camera_index, detected=False)
        self.camera_combo.activated.connect(
            lambda _: self.camera_selected.emit(int(self.camera_combo.currentData()))
        )
        grid.addWidget(self.camera_combo, 0, 1)
        self.detect_button = QPushButton("Detect")
        self.detect_button.setObjectName("ghost")
        self.detect_button.setToolTip(
            "Briefly opens each camera to see which ones work (the camera light may flash)"
        )
        self.detect_button.clicked.connect(self.detect_cameras_clicked.emit)
        grid.addWidget(self.detect_button, 0, 2)
        grid.addWidget(QLabel("Sensitivity"), 1, 0)
        self.sensitivity_combo = QComboBox()
        self.sensitivity_combo.setAccessibleName("Sensitivity")
        for value, text in SENSITIVITY_LABELS.items():
            self.sensitivity_combo.addItem(text, value)
        self.sensitivity_combo.activated.connect(
            lambda _: self.sensitivity_selected.emit(self.current_sensitivity())
        )
        grid.addWidget(self.sensitivity_combo, 1, 1, 1, 2)
        self.sound_check = QCheckBox("Sound with reminders")
        self.sound_check.toggled.connect(self.sound_toggled.emit)
        grid.addWidget(self.sound_check, 2, 0, 1, 3)
        grid.setColumnStretch(1, 1)
        quick.body.addLayout(grid)
        self.alert_timing = label("", "hint", wrap=True)
        quick.body.addWidget(self.alert_timing)
        column.addWidget(quick)
        return column

    def _build_right_column(self, settings: AppSettings) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(16)

        preview_card = Card()
        head = QHBoxLayout()
        head.addWidget(label("Camera preview", "cardTitle"))
        head.addStretch()
        self.preview_check = QCheckBox("Preview")
        self.landmarks_check = QCheckBox("Landmarks")
        self.preview_check.setChecked(settings.show_preview)
        self.landmarks_check.setChecked(settings.show_landmarks)
        self.preview_check.toggled.connect(self.preview_toggled.emit)
        self.landmarks_check.toggled.connect(self.landmarks_toggled.emit)
        head.addWidget(self.preview_check)
        head.addWidget(self.landmarks_check)
        preview_card.body.addLayout(head)
        self.preview = PreviewView()
        self.preview.show_placeholder(FIRST_RUN_TEXT)
        preview_card.body.addWidget(self.preview, 1)
        preview_card.body.addWidget(
            label("Mirrored view. Processed locally and never recorded.", "hint")
        )
        column.addWidget(preview_card, 1)

        signals = QHBoxLayout()
        signals.setSpacing(16)
        self.back_panel = SignalPanel(SignalKind.BACK)
        self.head_panel = SignalPanel(SignalKind.HEAD)
        signals.addWidget(self.back_panel)
        signals.addWidget(self.head_panel)
        column.addLayout(signals)

        session = Card()
        session.body.addWidget(label("This session", "cardTitle"))
        tiles = QHBoxLayout()
        self.monitored_tile = StatTile("monitored")
        self.share_tile = StatTile("within your usual range")
        self.alerts_tile = StatTile("reminders")
        for tile in (self.monitored_tile, self.share_tile, self.alerts_tile):
            tiles.addWidget(tile)
        session.body.addLayout(tiles)
        column.addWidget(session)
        return column

    # ------------------------------------------------------------------ updates
    def apply_settings(self, settings: AppSettings) -> None:
        index = self.camera_combo.findData(settings.camera_index)
        if index < 0:
            self.camera_combo.addItem(f"Camera {settings.camera_index}", settings.camera_index)
            index = self.camera_combo.count() - 1
        self.camera_combo.setCurrentIndex(index)
        self.sensitivity_combo.setCurrentIndex(list(SENSITIVITY_LABELS).index(settings.sensitivity))
        self.sound_check.blockSignals(True)
        self.sound_check.setChecked(settings.sound_enabled)
        self.sound_check.blockSignals(False)
        for check, value in (
            (self.preview_check, settings.show_preview),
            (self.landmarks_check, settings.show_landmarks),
        ):
            check.blockSignals(True)
            check.setChecked(value)
            check.blockSignals(False)
        self.alert_timing.setText(
            f"Warning after {fmt(settings.warning_seconds)} of sustained deviation, critical "
            f"after {fmt(settings.critical_seconds)}. Notifications at most every "
            f"{fmt(settings.cooldown_seconds)}."
        )
        self._show_preview = settings.show_preview
        if self._status is MonitorStatus.RUNNING:
            self._show_running_placeholder()

    def set_camera_choices(self, indices: list[int], current: int, detected: bool) -> None:
        self.camera_combo.clear()
        for i in sorted(set(indices) | {current}):
            suffix = " ✓" if detected and i in indices else ""
            self.camera_combo.addItem(f"Camera {i}{suffix}", i)
        self.camera_combo.setCurrentIndex(self.camera_combo.findData(current))

    def set_models_ok(self, ok: bool) -> None:
        self._models_ok = ok
        self.set_status(self._status)

    def set_status(self, status: MonitorStatus) -> None:
        self._status = status
        camera_text, camera_tone, monitor_text, monitor_tone = STATUS_CHIPS[status]
        self.camera_chip.set(camera_text, camera_tone)
        self.monitor_chip.set(monitor_text, monitor_tone)

        active = status in (MonitorStatus.RUNNING, MonitorStatus.STARTING)
        self.start_button.setVisible(status in (MonitorStatus.IDLE, MonitorStatus.ERROR))
        self.start_button.setText(
            "Try Again" if status is MonitorStatus.ERROR else "Start Monitoring"
        )
        self.start_button.setEnabled(self._models_ok)
        self.pause_button.setVisible(active)
        self.pause_button.setEnabled(status is MonitorStatus.RUNNING)
        self.resume_button.setVisible(status is MonitorStatus.PAUSED)
        self.stop_button.setEnabled(status is not MonitorStatus.IDLE)
        self.calibrate_button.setEnabled(self._models_ok and status is not MonitorStatus.STARTING)
        self.detect_button.setEnabled(not active)

        if status is MonitorStatus.IDLE:
            self._show_state(PetState.CALIBRATING, "Hi, I'm Pip!",
                             "Press Start Monitoring when you're ready. "
                             "The camera stays off until you do.")  # fmt: skip
            self.preview.show_placeholder(FIRST_RUN_TEXT)
            self._reset_signal_panels("Not measuring")
        elif status is MonitorStatus.PAUSED:
            self._show_state(PetState.UNAVAILABLE, "Paused",
                             "Monitoring is paused and the camera is off. Resume whenever "
                             "you like.")  # fmt: skip
            self.preview.show_placeholder("Paused. The camera is off.")
            self._reset_signal_panels("Paused")
        elif status is MonitorStatus.STARTING:
            self.preview.show_placeholder("Starting the camera and loading models…")
        elif status is MonitorStatus.RUNNING:
            self._show_running_placeholder()
        elif status is MonitorStatus.ERROR:
            self.preview.show_placeholder("Camera unavailable.")
            self._reset_signal_panels("Unavailable")

    def _show_running_placeholder(self) -> None:
        if self._show_preview:
            self.preview.show_placeholder("Waiting for the first camera frame…")
        else:
            self.preview.show_placeholder("Preview hidden. Monitoring is unaffected.")

    def _reset_signal_panels(self, text: str) -> None:
        self.back_panel.set_inactive(text)
        self.head_panel.set_inactive(text)
        self.calibration_progress.hide()

    def _show_state(self, state: PetState, title: str, message: str) -> None:
        self.pet.set_state(state)
        _, color = STATE_COLORS[state]
        self.state_title.setText(title)
        self.state_title.setStyleSheet(f"color: {color};")
        self.state_message.setText(message)

    def show_result(self, result: PostureResult) -> None:
        self._show_state(result.state, result.title, result.message)
        if result.calibration_progress is not None and result.calibration_outcome is None:
            self.calibration_progress.setValue(int(result.calibration_progress * 100))
            self.calibration_progress.show()
            self.calibrate_button.setEnabled(False)
        else:
            self.calibration_progress.hide()
            self.calibrate_button.setEnabled(self._models_ok)
        if result.state is PetState.CALIBRATING:
            self._reset_signal_panels("Calibrating" if result.calibration_progress else "Waiting")
            if result.calibration_progress is not None and result.calibration_outcome is None:
                self.calibration_progress.show()
        else:
            self.back_panel.set_status(result.back)
            self.head_panel.set_status(result.head)
        outcome = result.calibration_outcome
        if outcome is not None:
            if outcome.success:
                self.banner.show_message(
                    "Calibration saved. Pip now knows your comfortable posture. Recalibrate "
                    "any time you move your laptop or chair.",
                    "good",
                )
            else:
                self.banner.show_message(f"Calibration didn't succeed: {outcome.reason}", "warn")

    def show_preview(self, image: QImage) -> None:
        if self._status is MonitorStatus.RUNNING and self._show_preview:
            self.preview.show_image(image)

    def show_alert(self, alert: Alert) -> None:
        if alert.is_recovery:
            tone = "good"
        else:
            tone = "bad" if alert.level is SignalLevel.CRITICAL else "warn"
        self.reminder.show_message(f"{alert.title} {alert.message}", tone)

    def update_stats(self, stats: SessionStats) -> None:
        self.monitored_tile.value.setText(fmt(stats.monitored_s))
        share = stats.good_posture_share
        self.share_tile.value.setText("–" if share is None else f"{share:.0%}")
        self.alerts_tile.value.setText(str(stats.alerts_sent))

    def current_sensitivity(self) -> Sensitivity:
        # Qt hands StrEnum item data back as a plain str.
        return Sensitivity(self.sensitivity_combo.currentData())

    # ------------------------------------------------------------------ window events
    def closeEvent(self, event: QCloseEvent) -> None:
        if self.allow_close:
            event.accept()
            return
        event.ignore()
        self.close_requested.emit()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.visibility_changed.emit(not self.isMinimized() and self.isVisible())

    def bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
