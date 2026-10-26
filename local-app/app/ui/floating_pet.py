"""Floating Pip: a small, frameless, always-on-top desktop pet.

The window is a view like the others: it shows the posture state it is given and emits
user intents. It never takes keyboard focus, has no taskbar button, repaints only when the
state changes, and is masked to Pip's own pixels so clicks elsewhere reach the windows
underneath.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QBitmap,
    QColor,
    QContextMenuEvent,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QRegion,
    QScreen,
)
from PySide6.QtWidgets import QMenu, QWidget

from app import APP_NAME
from app.posture.models import PetState
from app.services.monitor import MonitorStatus
from app.ui.pet_widget import sprite_image
from app.ui.sprites import CANVAS_HEIGHT, CANVAS_WIDTH
from app.ui.tray import STATUS_TEXT, pet_state_for_status

PIXEL_SCALE = 5  # 26x22 sprite -> 130x110 logical pixels
SHADOW_HEIGHT = 8
SCREEN_MARGIN = 24
SPRITE_SIZE = QSize(CANVAS_WIDTH * PIXEL_SCALE, CANVAS_HEIGHT * PIXEL_SCALE)
WINDOW_SIZE = QSize(SPRITE_SIZE.width(), SPRITE_SIZE.height() + SHADOW_HEIGHT)


def default_position(size: QSize, area: QRect) -> QPoint:
    """Bottom-right corner of ``area`` (above the taskbar when given the available area)."""
    return QPoint(
        area.x() + area.width() - size.width() - SCREEN_MARGIN,
        area.y() + area.height() - size.height() - SCREEN_MARGIN,
    )


def clamp_into(pos: QPoint, size: QSize, area: QRect) -> QPoint:
    """Move a ``size`` rectangle at ``pos`` the minimum distance to lie fully inside ``area``."""
    x = min(max(pos.x(), area.x()), area.x() + area.width() - size.width())
    y = min(max(pos.y(), area.y()), area.y() + area.height() - size.height())
    return QPoint(x, y)


def place_on_screens(
    pos: QPoint | None, size: QSize, screens: list[QRect], primary: QRect
) -> QPoint:
    """Where the pet should go, given each screen's available (taskbar-free) area.

    A position on a monitor that no longer exists falls back to the primary screen, and
    a position half off a screen edge is pulled fully onto the screen it mostly covers.
    """
    if pos is None:
        return default_position(size, primary)
    rect = QRect(pos, size)
    target = next((s for s in screens if s.contains(rect.center())), None)
    if target is None:
        overlaps = [(s.intersected(rect), s) for s in screens]
        best = max(overlaps, key=lambda o: o[0].width() * o[0].height(), default=None)
        if best is None or best[0].isEmpty():
            return default_position(size, primary)
        target = best[1]
    return clamp_into(pos, size, target)


class FloatingPet(QWidget):
    open_dashboard_requested = Signal()
    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    hide_requested = Signal()
    quit_requested = Signal()
    moved = Signal(int, int)  # new top-left after the user dragged Pip

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool  # no taskbar button
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(WINDOW_SIZE)
        self.setWindowTitle(f"{APP_NAME} – Pip")
        self.setAccessibleName("Pip, floating posture pet")

        self.menu = QMenu(self)
        self.open_action = self.menu.addAction("Open Dashboard")
        self.menu.addSeparator()
        self.start_action = self.menu.addAction("Start Monitoring")
        self.pause_action = self.menu.addAction("Pause Monitoring")
        self.resume_action = self.menu.addAction("Resume Monitoring")
        self.menu.addSeparator()
        self.hide_action = self.menu.addAction("Hide Pip")
        self.quit_action = self.menu.addAction(f"Quit {APP_NAME}")
        for action, signal in (
            (self.open_action, self.open_dashboard_requested),
            (self.start_action, self.start_requested),
            (self.pause_action, self.pause_requested),
            (self.resume_action, self.resume_requested),
            (self.hide_action, self.hide_requested),
            (self.quit_action, self.quit_requested),
        ):
            action.triggered.connect(signal.emit)

        self._state = PetState.CALIBRATING
        self._status = MonitorStatus.IDLE
        self._preferred: QPoint | None = None  # where the user put Pip
        self._drag_offset: QPoint | None = None
        self._dragged = False
        self._update_menu()
        self._update_look()

        app = QGuiApplication.instance()
        if isinstance(app, QGuiApplication):
            app.screenAdded.connect(self._watch_screen)
            app.screenRemoved.connect(lambda _: self.reposition())
            app.primaryScreenChanged.connect(lambda _: self.reposition())
            for screen in app.screens():
                self._watch_screen(screen)

    # ------------------------------------------------------------------ state
    @property
    def state(self) -> PetState:
        return self._state

    def set_state(self, state: PetState) -> None:
        if state is self._state:
            return  # nothing changed: no repaint, no new mask
        self._state = state
        self._update_look()

    def set_monitor_status(self, status: MonitorStatus) -> None:
        if status is not self._status:
            self._status = status
            self._update_menu()
            self._update_tooltip()
        idle_state = pet_state_for_status(status)
        if idle_state is not None:
            self.set_state(idle_state)

    def _update_look(self) -> None:
        self._update_tooltip()
        self.setAccessibleDescription(f"Pip is {self._state.value}")
        self.setMask(self._hit_region())
        self.update()

    def _update_tooltip(self) -> None:
        self.setToolTip(
            f"Pip is {self._state.value} · {STATUS_TEXT[self._status]}\n"
            "Drag to move · double-click for the dashboard · right-click for options"
        )

    def _update_menu(self) -> None:
        status = self._status
        self.start_action.setVisible(status in (MonitorStatus.IDLE, MonitorStatus.ERROR))
        self.pause_action.setVisible(status in (MonitorStatus.RUNNING, MonitorStatus.STARTING))
        self.resume_action.setVisible(status is MonitorStatus.PAUSED)

    def _hit_region(self) -> QRegion:
        """Pip's opaque pixels plus the shadow: the only area that takes mouse input."""
        alpha = sprite_image(self._state, 0).createAlphaMask()
        scaled = alpha.scaled(
            SPRITE_SIZE,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        region = QRegion(QBitmap.fromImage(scaled))
        return region.united(QRegion(self._shadow_rect(), QRegion.RegionType.Ellipse))

    def _shadow_rect(self) -> QRect:
        width = SPRITE_SIZE.width() // 2
        return QRect(
            (WINDOW_SIZE.width() - width) // 2,
            WINDOW_SIZE.height() - SHADOW_HEIGHT * 2,
            width,
            SHADOW_HEIGHT * 2,
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        shadow = QColor("#2E2240")
        shadow.setAlpha(40)
        painter.setBrush(shadow)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawEllipse(self._shadow_rect())
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(QRect(QPoint(0, 0), SPRITE_SIZE), sprite_image(self._state, 0))
        painter.end()

    # ------------------------------------------------------------------ placement
    def show_at(self, preferred: tuple[int, int] | None) -> None:
        """Show Pip (without taking focus) at the saved spot, or bottom-right by default."""
        self._preferred = QPoint(*preferred) if preferred else None
        self.reposition()
        self.show()

    def reposition(self) -> None:
        """Keep Pip fully on a connected screen, e.g. after a monitor is unplugged."""
        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            return
        primary = app.primaryScreen()
        if primary is None:
            return
        areas = [s.availableGeometry() for s in app.screens()]
        primary_area = primary.availableGeometry()
        self.move(place_on_screens(self._preferred, WINDOW_SIZE, areas, primary_area))

    def _watch_screen(self, screen: QScreen) -> None:
        screen.availableGeometryChanged.connect(lambda _: self.reposition())

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._dragged = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._dragged = True
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            if self._dragged:
                self._preferred = self.pos()
                self.reposition()  # pull it back fully onto the screen it was dropped on
                self._preferred = self.pos()
                self.moved.emit(self.x(), self.y())
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.open_dashboard_requested.emit()
            event.accept()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.menu.popup(event.globalPos())
        event.accept()
