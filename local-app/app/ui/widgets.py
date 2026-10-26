"""Small reusable widgets for the dashboard."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.posture.models import BackComponent, SignalKind, SignalLevel, SignalStatus
from app.ui import theme

SEVERITY_SCALE_MAX = 2.0  # the bar shows 0..2x the tolerance

LEVEL_LABELS: dict[SignalLevel, tuple[str, str]] = {
    SignalLevel.UNAVAILABLE: ("Unavailable", "neutral"),
    SignalLevel.OK: ("Within range", "good"),
    SignalLevel.DEVIATING: ("Drifting", "info"),
    SignalLevel.WARNING: ("Warning", "warn"),
    SignalLevel.CRITICAL: ("Critical", "bad"),
}

COMPONENT_LABELS: dict[BackComponent, str] = {
    BackComponent.LEANING_IN: "leaning in toward the screen",
    BackComponent.HUNCHING: "shoulders rounding / neck shortening",
    BackComponent.SINKING: "sinking lower in the seat",
    BackComponent.SIDE_LEAN: "leaning to one side",
}


def repolish(widget: QWidget) -> None:
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(10)


class Chip(QLabel):
    def __init__(self, text: str = "", tone: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_tone(tone)

    def set(self, text: str, tone: str) -> None:
        self.setText(text)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        if self.property("tone") != tone:
            self.setProperty("tone", tone)
            repolish(self)


def label(text: str, object_name: str, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(object_name)
    widget.setWordWrap(wrap)
    return widget


class SeverityBar(QWidget):
    """Estimated deviation relative to tolerance, with a marker at the tolerance edge."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value: float | None = None
        self._level = SignalLevel.UNAVAILABLE
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value: float | None, level: SignalLevel) -> None:
        self._value, self._level = value, level
        if value is None:
            self.setAccessibleDescription("No measurement available")
        else:
            self.setAccessibleDescription(f"Estimated deviation {value:.1f} times your tolerance")
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = QRectF(0, 3, self.width(), 8)
        painter.setBrush(QColor(theme.NEUTRAL_CHIP))
        painter.drawRoundedRect(track, 4, 4)
        if self._value is not None:
            fraction = min(max(self._value, 0.0), SEVERITY_SCALE_MAX) / SEVERITY_SCALE_MAX
            color = {
                SignalLevel.OK: theme.MINT_TEXT,
                SignalLevel.DEVIATING: theme.LAVENDER_DEEP,
                SignalLevel.WARNING: "#D88A4E",
                SignalLevel.CRITICAL: "#D65B4F",
            }.get(self._level, theme.TEXT_MUTED)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(0, 3, max(8.0, track.width() * fraction), 8), 4, 4)
        marker_x = self.width() / SEVERITY_SCALE_MAX
        painter.setBrush(QColor(theme.TEXT))
        painter.drawRect(QRectF(marker_x - 1, 0, 2, 14))
        painter.end()


class SignalPanel(Card):
    def __init__(self, kind: SignalKind, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        header = QHBoxLayout()
        title = "Back & shoulders" if kind is SignalKind.BACK else "Head tilt"
        header.addWidget(label(title, "cardTitle"))
        header.addStretch()
        self.chip = Chip("Not measuring")
        header.addWidget(self.chip)
        self.body.addLayout(header)

        self.bar = SeverityBar()
        self.body.addWidget(self.bar)
        scale = QHBoxLayout()
        scale.addWidget(label("your baseline", "hint"))
        scale.addStretch()
        scale.addWidget(label("tolerance ▏", "hint"))
        scale.addStretch()
        scale.addWidget(label("2×", "hint"))
        self.body.addLayout(scale)

        self.detail = label("", "muted", wrap=True)
        self.duration = label("", "muted")
        self.body.addWidget(self.detail)
        self.body.addWidget(self.duration)
        self.set_inactive()

    def set_inactive(self, text: str = "Not measuring") -> None:
        self.chip.set(text, "neutral")
        self.bar.set_value(None, SignalLevel.UNAVAILABLE)
        self.detail.setText("Estimate relative to your calibrated baseline.")
        self.duration.setText("")

    def set_status(self, status: SignalStatus) -> None:
        text, tone = LEVEL_LABELS[status.level]
        self.chip.set(text, tone)
        self.bar.set_value(status.severity, status.level)
        if not status.available:
            what = "shoulders and ears" if self.kind is SignalKind.BACK else "face"
            self.detail.setText(f"Can't measure: make sure your {what} are visible.")
            self.duration.setText("")
            return
        if self.kind is SignalKind.BACK and status.dominant_component and status.in_episode:
            self.detail.setText(f"Main factor: {COMPONENT_LABELS[status.dominant_component]}.")
        elif self.kind is SignalKind.HEAD and status.in_episode:
            self.detail.setText("Head tilted further down than your baseline.")
        else:
            self.detail.setText("Estimate relative to your calibrated baseline.")
        if status.in_episode:
            self.duration.setText(f"Ongoing for {format_duration(status.issue_duration_s)}")
        else:
            self.duration.setText("No ongoing issue")


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {seconds:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


class PreviewView(QLabel):
    """Shows the latest preview frame scaled to fit, or a placeholder text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setMinimumSize(320, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Camera preview")
        self._image: QImage | None = None

    def sizeHint(self) -> QSize:
        return QSize(480, 300)

    def show_placeholder(self, text: str) -> None:
        self._image = None
        self.setPixmap(QPixmap())
        self.setText(text)

    def show_image(self, image: QImage) -> None:
        self._image = image
        self._render()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._image is not None:
            self._render()

    def _render(self) -> None:
        if self._image is None:
            return
        pixmap = QPixmap.fromImage(self._image).scaled(
            self.width() - 8,
            self.height() - 8,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)


class Banner(QFrame):
    """Dismissible in-app message (reminders, errors, notices)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("banner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        self.text = label("", "message", wrap=True)
        layout.addWidget(self.text, 1)
        self.close_button = QPushButton("Dismiss")
        self.close_button.setObjectName("link")
        self.close_button.clicked.connect(self.hide)
        layout.addWidget(self.close_button)
        self.hide()

    def show_message(self, text: str, tone: str = "info") -> None:
        self.text.setText(text)
        if self.property("tone") != tone:
            self.setProperty("tone", tone)
            repolish(self)
        self.show()


class StatTile(QWidget):
    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.value = label("–", "statValue")
        layout.addWidget(self.value)
        layout.addWidget(label(caption, "statLabel"))
