"""Design tokens and the Qt stylesheet (soft pixel-tech: lavender, mint, peach, coral)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen

from app.posture.models import PetState
from app.vision.model_assets import resources_dir

log = logging.getLogger(__name__)

LAVENDER = "#E1D8FF"
LAVENDER_DEEP = "#6E5BC7"
LAVENDER_DEEPER = "#5A48AE"
BACKGROUND = "#F7F4FF"
SURFACE = "#FFFEFC"
BORDER = "#E6DFF7"
MINT = "#CBE8D4"
MINT_TEXT = "#24613A"
PEACH = "#F7D7BE"
PEACH_TEXT = "#86471B"
CORAL = "#F6C1BA"
CORAL_TEXT = "#9C2F25"
TEXT = "#2E2240"
TEXT_MUTED = "#6B5F80"
NEUTRAL_CHIP = "#EEEAF7"

# (background, foreground) for each pet state; foregrounds meet WCAG AA on their tint.
STATE_COLORS: dict[PetState, tuple[str, str]] = {
    PetState.CALIBRATING: (LAVENDER, LAVENDER_DEEPER),
    PetState.THRIVING: (MINT, MINT_TEXT),
    PetState.WARNING: (PEACH, PEACH_TEXT),
    PetState.CRITICAL: (CORAL, CORAL_TEXT),
    PetState.UNAVAILABLE: (NEUTRAL_CHIP, TEXT_MUTED),
}

PIXEL_FONT_FAMILY = "Press Start 2P"


def load_fonts() -> tuple[str, str]:
    """Register the bundled pixel font; pick Inter if installed, else Segoe UI."""
    pixel_family = PIXEL_FONT_FAMILY
    font_path = resources_dir() / "fonts" / "PressStart2P-Regular.ttf"
    if QFontDatabase.addApplicationFont(str(font_path)) < 0:
        log.warning("Pixel font could not be loaded from %s", font_path)
        pixel_family = "Consolas"
    families = set(QFontDatabase.families())
    ui_family = (
        "Inter"
        if "Inter" in families
        else ("Segoe UI" if sys.platform == "win32" else QFont().defaultFamily())
    )
    return ui_family, pixel_family


def write_icons(directory: Path) -> Path:
    """Draw the checkbox tick and combo chevron as PNGs (QtSvg is not in PySide6-Essentials)."""
    directory.mkdir(parents=True, exist_ok=True)
    shapes = {
        "check.png": ("#FFFFFF", [(3.5, 8.5), (6.5, 11.5), (12.5, 4.5)]),
        "chevron.png": (LAVENDER_DEEPER, [(3.5, 6.0), (8.0, 10.5), (12.5, 6.0)]),
    }
    scale = 2  # crisp on high-DPI screens
    for name, (color, points) in shapes.items():
        image = QImage(16 * scale, 16 * scale, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color), 2.2 * scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(x * scale, y * scale) for x, y in points])
        painter.end()
        image.save(str(directory / name))
    return directory


def stylesheet(ui_family: str, pixel_family: str, icon_dir: Path) -> str:
    icons = icon_dir.as_posix()
    return f"""
* {{ font-family: "{ui_family}"; color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BACKGROUND}; }}
QWidget#root {{ background: {BACKGROUND}; }}
QToolTip {{ background: {TEXT}; color: white; border: none; padding: 6px; }}

QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QLabel {{ background: transparent; }}
QLabel#brand {{ font-family: "{pixel_family}"; font-size: 15px; color: {TEXT}; }}
QLabel#tagline {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#petName {{ font-family: "{pixel_family}"; font-size: 10px; color: {TEXT_MUTED}; }}
QLabel#cardTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#eyebrow {{
    font-family: "{pixel_family}"; font-size: 8px; color: {LAVENDER_DEEPER};
    letter-spacing: 1px;
}}
QLabel#stateTitle {{ font-size: 24px; font-weight: 700; }}
QLabel#message {{ font-size: 14px; color: {TEXT}; }}
QLabel#muted, QLabel#hint {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#statValue {{ font-size: 20px; font-weight: 700; }}
QLabel#statLabel {{ color: {TEXT_MUTED}; font-size: 11px; }}

QLabel#chip {{
    border-radius: 11px; padding: 3px 10px; font-size: 12px; font-weight: 600;
    background: {NEUTRAL_CHIP}; color: {TEXT_MUTED};
}}
QLabel#chip[tone="good"] {{ background: {MINT}; color: {MINT_TEXT}; }}
QLabel#chip[tone="warn"] {{ background: {PEACH}; color: {PEACH_TEXT}; }}
QLabel#chip[tone="bad"] {{ background: {CORAL}; color: {CORAL_TEXT}; }}
QLabel#chip[tone="info"] {{ background: {LAVENDER}; color: {LAVENDER_DEEPER}; }}

QPushButton {{
    background: {LAVENDER}; color: {TEXT}; border: 1px solid transparent;
    border-radius: 10px; padding: 9px 16px; font-size: 13px; font-weight: 600;
}}
QPushButton:hover {{ background: #D4C8FF; }}
QPushButton:pressed {{ background: #C7B8FF; }}
QPushButton:focus {{ border: 2px solid {LAVENDER_DEEP}; }}
QPushButton:disabled {{ background: #EFECF5; color: #A79FB8; }}
QPushButton#primary {{ background: {LAVENDER_DEEP}; color: white; }}
QPushButton#primary:hover {{ background: {LAVENDER_DEEPER}; }}
QPushButton#primary:focus {{ border: 2px solid {TEXT}; }}
QPushButton#primary:disabled {{ background: #CFC8E6; color: #F4F1FB; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {BORDER}; }}
QPushButton#ghost:hover {{ background: {NEUTRAL_CHIP}; }}
QPushButton#link {{
    background: transparent; border: none; color: {LAVENDER_DEEPER}; padding: 2px 4px;
    text-decoration: underline;
}}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background: white; border: 1px solid {BORDER}; border-radius: 8px; padding: 5px 8px;
    min-height: 20px;
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 2px solid {LAVENDER_DEEP}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow {{ image: url("{icons}/chevron.png"); width: 14px; height: 14px; }}
QComboBox QAbstractItemView {{
    background: white; selection-background-color: {LAVENDER}; selection-color: {TEXT};
}}
QCheckBox {{ spacing: 8px; font-size: 13px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px; border: 1px solid #B9AEDB;
    background: white;
}}
QCheckBox::indicator:checked {{
    background: {LAVENDER_DEEP}; border-color: {LAVENDER_DEEP}; image: url("{icons}/check.png");
}}
QCheckBox:focus {{ color: {LAVENDER_DEEPER}; }}

QProgressBar {{
    background: {NEUTRAL_CHIP}; border: none; border-radius: 5px; height: 10px;
    text-align: center; font-size: 1px; color: transparent;
}}
QProgressBar::chunk {{ background: {LAVENDER_DEEP}; border-radius: 5px; }}

QFrame#banner {{ border-radius: 12px; border: 1px solid {BORDER}; background: {LAVENDER}; }}
QFrame#banner[tone="warn"] {{ background: {PEACH}; }}
QFrame#banner[tone="bad"] {{ background: {CORAL}; }}
QFrame#banner[tone="good"] {{ background: {MINT}; }}

QLabel#preview {{
    background: #EFEAFB; border-radius: 12px; color: {TEXT_MUTED}; font-size: 13px;
    padding: 12px;
}}
QGroupBox {{
    border: 1px solid {BORDER}; border-radius: 12px; margin-top: 14px; padding: 12px;
    background: {SURFACE}; font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; }}
"""
