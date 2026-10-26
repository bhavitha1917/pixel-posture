"""Renders Pip with QPainter: nearest-neighbour scaling keeps pixels crisp."""

from __future__ import annotations

import ctypes
import sys
from functools import lru_cache

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.posture.models import PetState
from app.ui.sprites import CANVAS_HEIGHT, CANVAS_WIDTH, PALETTE, sprite
from app.ui.theme import STATE_COLORS

ANIMATION_INTERVAL_MS = 450
SPI_GETCLIENTAREAANIMATION = 0x1042


def system_prefers_reduced_motion() -> bool:
    """Windows: 'Animation effects' off in Settings > Accessibility > Visual effects."""
    if sys.platform != "win32":
        return False
    enabled = ctypes.c_int(1)
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0
        )
    except (AttributeError, OSError):
        return False
    return bool(ok) and not enabled.value


@lru_cache(maxsize=32)
def sprite_image(state: PetState, frame: int) -> QImage:
    image = QImage(CANVAS_WIDTH, CANVAS_HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for y, row in enumerate(sprite(state, frame)):
        for x, key in enumerate(row):
            if key != ".":
                image.setPixelColor(x, y, QColor(PALETTE[key]))
    return image


def pet_icon(state: PetState) -> QIcon:
    """Multi-size icon (tray, window, taskbar) from frame 0 of the state's sprite."""
    icon = QIcon()
    source = sprite_image(state, 0)
    for size in (16, 24, 32, 48, 64, 128, 256):
        scaled = source.scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
        )
        canvas = QPixmap(size, size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
        painter.end()
        icon.addPixmap(canvas)
    return icon


class PetWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = PetState.CALIBRATING
        self._frame = 0
        self._reduce_motion = False
        self._timer = QTimer(self)
        self._timer.setInterval(ANIMATION_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)
        self.setMinimumSize(200, 170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Pip the pixel pet")
        self._update_timer()

    @property
    def state(self) -> PetState:
        return self._state

    def sizeHint(self) -> QSize:
        return QSize(280, 240)

    def set_state(self, state: PetState) -> None:
        if state is not self._state:
            self._state = state
            self._frame = 0
            self.setAccessibleDescription(f"Pip is {state.value}")
            self.update()

    def set_reduce_motion(self, reduce: bool) -> None:
        self._reduce_motion = reduce
        self._frame = 0
        self._update_timer()
        self.update()

    def set_animating(self, visible: bool) -> None:
        """Stop the animation timer while the window is hidden (no wasted work)."""
        if visible:
            self._update_timer()
        else:
            self._timer.stop()

    def _update_timer(self) -> None:
        if self._reduce_motion:
            self._timer.stop()
        else:
            self._timer.start()

    def _advance(self) -> None:
        self._frame = (self._frame + 1) % 2
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        tint, _ = STATE_COLORS[self._state]
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tint))
        painter.drawRoundedRect(rect, 20, 20)

        scale = max(
            1, int(min(rect.width() * 0.8 / CANVAS_WIDTH, rect.height() * 0.8 / CANVAS_HEIGHT))
        )
        width, height = CANVAS_WIDTH * scale, CANVAS_HEIGHT * scale
        x = rect.center().x() - width / 2
        y = rect.center().y() - height / 2 - scale

        shadow = QColor("#2E2240")
        shadow.setAlpha(28)
        painter.setBrush(shadow)
        painter.drawEllipse(QRectF(x + width * 0.22, y + height - scale, width * 0.56, scale * 2))

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        frame = 0 if self._reduce_motion else self._frame
        painter.drawImage(QRectF(x, y, width, height), sprite_image(self._state, frame))
        painter.end()
