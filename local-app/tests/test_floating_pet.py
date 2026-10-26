"""Floating Pip: window behaviour, placement, state updates and app lifecycle (offscreen Qt).

Real always-on-top behaviour, click-through and focus over other apps depend on the Windows
window manager and are manual checks (docs/testing.md).
"""

from __future__ import annotations

import pytest
from conftest import make_baseline, obs, short_config, timeline
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from app.application import PixelPostureApp
from app.posture.engine import PostureEngine
from app.posture.models import PetState
from app.services.monitor import MonitorController, MonitorStatus
from app.settings.store import AppSettings, SettingsStore
from app.ui.floating_pet import (
    PIXEL_SCALE,
    SCREEN_MARGIN,
    WINDOW_SIZE,
    FloatingPet,
    clamp_into,
    place_on_screens,
)
from app.ui.tray import TrayController

PRIMARY = QRect(0, 0, 1920, 1040)  # available area above a 40 px taskbar
LEFT = QRect(-1280, 0, 1280, 984)  # a second monitor to the left (negative coordinates)
SIZE = WINDOW_SIZE


@pytest.fixture
def pet(qtbot):
    widget = FloatingPet()
    qtbot.addWidget(widget)
    return widget


def visible_actions(pet: FloatingPet) -> set[str]:
    return {a.text() for a in pet.menu.actions() if a.isVisible() and a.text()}


# ---------------------------------------------------------------- window properties
def test_is_a_small_frameless_topmost_tool_window(pet):
    flags = pet.windowFlags()
    for flag in (
        Qt.WindowType.Tool,
        Qt.WindowType.FramelessWindowHint,
        Qt.WindowType.WindowStaysOnTopHint,
        Qt.WindowType.WindowDoesNotAcceptFocus,
    ):
        assert flags & flag
    assert pet.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert pet.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert pet.focusPolicy() is Qt.FocusPolicy.NoFocus
    assert 100 <= pet.width() <= 140 and pet.height() <= 140
    assert pet.parent() is None  # independent of the dashboard


def test_only_pips_pixels_take_mouse_input(pet):
    mask = pet.mask()
    assert not mask.contains(QPoint(1, 1))  # transparent corner: clicks pass through
    assert not mask.contains(QPoint(pet.width() - 2, pet.height() - 2))
    # A body pixel: canvas (13, 12) is lavender body in every state.
    assert mask.contains(QPoint(13 * PIXEL_SCALE + 2, 12 * PIXEL_SCALE + 2))


def test_showing_does_not_take_focus(qtbot, pet):
    pet.show_at(None)
    qtbot.waitExposed(pet)
    assert not pet.isActiveWindow()
    assert QApplication.focusWidget() is not pet


# ---------------------------------------------------------------- state updates
def test_state_changes_update_look_but_repeats_do_not(pet, monkeypatch):
    updates: list[int] = []
    monkeypatch.setattr(pet, "update", lambda: updates.append(1))
    for _ in range(50):
        pet.set_state(PetState.CALIBRATING)  # already showing this
    assert updates == []
    for state in (PetState.THRIVING, PetState.WARNING, PetState.CRITICAL, PetState.UNAVAILABLE):
        pet.set_state(state)
        assert pet.state is state
        assert f"Pip is {state.value}" in pet.toolTip()
    assert len(updates) == 4


@pytest.mark.parametrize(
    ("status", "state"),
    [
        (MonitorStatus.IDLE, PetState.CALIBRATING),
        (MonitorStatus.PAUSED, PetState.UNAVAILABLE),
        (MonitorStatus.ERROR, PetState.UNAVAILABLE),
    ],
)
def test_not_monitoring_states(pet, status, state):
    pet.set_state(PetState.THRIVING)
    pet.set_monitor_status(status)
    assert pet.state is state


def test_running_status_leaves_state_to_results(pet):
    pet.set_state(PetState.WARNING)
    pet.set_monitor_status(MonitorStatus.RUNNING)
    assert pet.state is PetState.WARNING


@pytest.mark.parametrize(
    ("status", "shown", "hidden"),
    [
        (MonitorStatus.IDLE, "Start Monitoring", {"Pause Monitoring", "Resume Monitoring"}),
        (MonitorStatus.RUNNING, "Pause Monitoring", {"Start Monitoring", "Resume Monitoring"}),
        (MonitorStatus.PAUSED, "Resume Monitoring", {"Start Monitoring", "Pause Monitoring"}),
    ],
)
def test_context_menu_matches_status(pet, status, shown, hidden):
    pet.set_monitor_status(status)
    actions = visible_actions(pet)
    assert shown in actions and not hidden & actions
    assert {"Open Dashboard", "Hide Pip", "Quit Pixel Posture"} <= actions


def test_context_menu_actions_emit_signals(qtbot, pet):
    for action, signal in (
        (pet.open_action, pet.open_dashboard_requested),
        (pet.start_action, pet.start_requested),
        (pet.pause_action, pet.pause_requested),
        (pet.resume_action, pet.resume_requested),
        (pet.hide_action, pet.hide_requested),
        (pet.quit_action, pet.quit_requested),
    ):
        with qtbot.waitSignal(signal, timeout=500):
            action.trigger()


# ---------------------------------------------------------------- placement
def test_default_position_is_bottom_right_above_the_taskbar():
    pos = place_on_screens(None, SIZE, [PRIMARY], PRIMARY)
    assert pos == QPoint(1920 - SIZE.width() - SCREEN_MARGIN, 1040 - SIZE.height() - SCREEN_MARGIN)


def test_saved_position_on_a_second_monitor_is_kept():
    pos = QPoint(-600, 300)
    assert place_on_screens(pos, SIZE, [PRIMARY, LEFT], PRIMARY) == pos


def test_position_on_an_unplugged_monitor_returns_to_primary():
    pos = place_on_screens(QPoint(-600, 300), SIZE, [PRIMARY], PRIMARY)
    assert PRIMARY.contains(QRect(pos, SIZE))


def test_half_off_screen_edge_is_pulled_back_on():
    pos = place_on_screens(QPoint(1900, 1000), SIZE, [PRIMARY], PRIMARY)
    assert PRIMARY.contains(QRect(pos, SIZE))
    assert pos == QPoint(1920 - SIZE.width(), 1040 - SIZE.height())


def test_straddling_two_monitors_snaps_to_the_one_holding_its_centre():
    pos = place_on_screens(QPoint(-30, 200), SIZE, [PRIMARY, LEFT], PRIMARY)
    assert PRIMARY.contains(QRect(pos, SIZE)) and pos.y() == 200


def test_clamp_into_leaves_inside_positions_alone():
    assert clamp_into(QPoint(10, 10), QSize(100, 100), PRIMARY) == QPoint(10, 10)


def _mouse(pet, kind, global_pos, button, buttons):
    local = QPointF(global_pos - pet.pos())
    event = QMouseEvent(
        kind, local, QPointF(global_pos), button, buttons, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(pet, event)


def test_dragging_moves_pip_and_reports_the_spot(qtbot, pet):
    pet.show_at((200, 200))
    qtbot.waitExposed(pet)
    start = pet.pos() + QPoint(60, 60)
    left, none = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    _mouse(pet, QMouseEvent.Type.MouseButtonPress, start, left, left)
    _mouse(pet, QMouseEvent.Type.MouseMove, start + QPoint(40, 25), none, left)
    with qtbot.waitSignal(pet.moved, timeout=500) as moved:
        _mouse(pet, QMouseEvent.Type.MouseButtonRelease, start + QPoint(40, 25), left, none)
    assert pet.pos() == QPoint(240, 225)
    assert moved.args == [240, 225]


def test_click_without_drag_does_not_report_a_move(qtbot, pet):
    pet.show_at((200, 200))
    spot = pet.pos() + QPoint(60, 60)
    left, none = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    with qtbot.assertNotEmitted(pet.moved):
        _mouse(pet, QMouseEvent.Type.MouseButtonPress, spot, left, left)
        _mouse(pet, QMouseEvent.Type.MouseButtonRelease, spot, left, none)


# ---------------------------------------------------------------- app integration
@pytest.fixture
def app(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(TrayController, "available", property(lambda self: True))
    store = SettingsStore(tmp_path / "settings.json")
    application = PixelPostureApp(qapp, store, AppSettings())
    qtbot.addWidget(application.window)
    monkeypatch.setattr(qapp, "quit", lambda: None)
    yield application, store
    application.quit()


def test_pip_floats_by_default_and_is_independent_of_the_dashboard(app):
    application, _ = app
    assert application.pet_window.isVisible()
    assert application.tray.floating_pet_action.isChecked()
    application.show_window()
    application.window.close()  # close to tray
    assert not application.window.isVisible()
    assert application.pet_window.isVisible()
    application.window.showMinimized()
    assert application.pet_window.isVisible()


def test_closing_the_dashboard_keeps_monitoring(qtbot, qapp, tmp_path, monkeypatch):
    calls: list[str] = []
    for name in ("stop", "pause", "shutdown"):
        monkeypatch.setattr(MonitorController, name, lambda self, n=name: calls.append(n))
    monkeypatch.setattr(TrayController, "available", property(lambda self: True))
    application = PixelPostureApp(qapp, SettingsStore(tmp_path / "s.json"), AppSettings())
    qtbot.addWidget(application.window)
    monkeypatch.setattr(qapp, "quit", lambda: None)
    application.show_window()
    application.window.close()
    assert calls == []
    application.quit()
    assert calls == ["shutdown"]


def test_hide_pip_from_its_menu_then_show_it_from_the_tray(app):
    application, store = app
    application.pet_window.hide_action.trigger()
    assert not application.pet_window.isVisible()
    assert not store.load().floating_pet_enabled
    assert not application.tray.floating_pet_action.isChecked()
    assert not application.window.floating_pet_check.isChecked()
    application.tray.floating_pet_action.trigger()
    assert application.pet_window.isVisible()
    assert store.load().floating_pet_enabled


def test_quick_settings_checkbox_toggles_pip(app):
    application, store = app
    application.window.floating_pet_check.click()
    assert not application.pet_window.isVisible() and not store.load().floating_pet_enabled
    application.window.floating_pet_check.click()
    assert application.pet_window.isVisible()


def test_disabled_setting_starts_without_pip(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(qapp, "quit", lambda: None)
    settings = AppSettings(floating_pet_enabled=False)
    application = PixelPostureApp(qapp, SettingsStore(tmp_path / "s.json"), settings)
    qtbot.addWidget(application.window)
    assert not application.pet_window.isVisible()
    application.quit()


def test_dragged_position_is_saved(app):
    application, store = app
    application.pet_window.moved.emit(321, 222)
    assert store.load().floating_pet_position == (321, 222)


def test_menu_actions_drive_the_app(qtbot, qapp, tmp_path, monkeypatch):
    calls: list[str] = []
    for name in ("start", "pause", "resume"):
        monkeypatch.setattr(MonitorController, name, lambda self, n=name: calls.append(n))
    application = PixelPostureApp(qapp, SettingsStore(tmp_path / "s.json"), AppSettings())
    qtbot.addWidget(application.window)
    monkeypatch.setattr(qapp, "quit", lambda: None)
    pet = application.pet_window
    pet.start_action.trigger()
    pet.pause_action.trigger()
    pet.resume_action.trigger()
    assert calls == ["start", "pause", "resume"]
    application.window.hide()
    pet.open_action.trigger()
    assert application.window.isVisible()
    application.quit()


def test_results_and_status_drive_floating_pip(app, monkeypatch):
    application, _ = app
    engine = PostureEngine(short_config(), make_baseline())
    result = None
    for t in timeline(0, 15, 10):
        result = engine.update(obs(t, 2.0, 0.0))
    monkeypatch.setattr(MonitorController, "status", property(lambda self: MonitorStatus.RUNNING))
    application.controller.result_ready.emit(result)
    assert application.pet_window.state is PetState.WARNING
    application.controller.status_changed.emit(MonitorStatus.PAUSED)
    assert application.pet_window.state is PetState.UNAVAILABLE


def test_quit_closes_pip_tray_and_dashboard(app):
    application, _ = app
    application.quit()
    assert not application.pet_window.isVisible()
    assert not application.window.isVisible()
    assert not application.tray.icon.isVisible()
    assert not application.controller.has_worker
