"""UI wiring tests on the offscreen Qt platform (no camera is opened)."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from conftest import make_baseline, obs, timeline

from app.application import PixelPostureApp
from app.posture.config import Sensitivity
from app.posture.engine import PostureEngine
from app.posture.models import PetState, SignalLevel
from app.services.alerts import Alert
from app.services.monitor import MonitorController, MonitorStatus
from app.services.single_instance import SingleInstance
from app.settings.store import AppSettings, SettingsStore
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.sprites import CANVAS_HEIGHT, CANVAS_WIDTH, FRAME_COUNT, PALETTE, sprite, to_svg
from app.ui.tray import TrayController


@pytest.fixture
def window(qtbot):
    w = MainWindow(AppSettings())
    qtbot.addWidget(w)
    return w


def visible_actions(tray: TrayController) -> set[str]:
    return {a.text() for a in tray.menu.actions() if a.isVisible() and a.text()}


@pytest.mark.parametrize(
    ("status", "expected", "hidden"),
    [
        (MonitorStatus.IDLE, "Start Monitoring", {"Pause Monitoring", "Resume Monitoring"}),
        (MonitorStatus.RUNNING, "Pause Monitoring", {"Start Monitoring", "Resume Monitoring"}),
        (MonitorStatus.PAUSED, "Resume Monitoring", {"Start Monitoring", "Pause Monitoring"}),
        (MonitorStatus.ERROR, "Start Monitoring", {"Pause Monitoring", "Resume Monitoring"}),
    ],
)
def test_tray_menu_matches_status(qtbot, status, expected, hidden):
    tray = TrayController()
    tray.update_status(status)
    actions = visible_actions(tray)
    assert expected in actions
    assert not hidden & actions
    assert {"Open Pixel Posture", "Settings…", "Quit Pixel Posture"} <= actions


def test_tray_actions_emit_signals(qtbot):
    tray = TrayController()
    for action, signal in (
        (tray.open_action, tray.open_requested),
        (tray.start_action, tray.start_requested),
        (tray.pause_action, tray.pause_requested),
        (tray.resume_action, tray.resume_requested),
        (tray.settings_action, tray.settings_requested),
        (tray.quit_action, tray.quit_requested),
    ):
        with qtbot.waitSignal(signal, timeout=500):
            action.trigger()


def test_tray_tooltip_reflects_state(qtbot):
    tray = TrayController()
    tray.update_status(MonitorStatus.RUNNING)
    tray.update_pet_state(PetState.WARNING)
    assert "Monitoring" in tray.icon.toolTip() and "warning" in tray.icon.toolTip()


def test_window_buttons_follow_status(window):
    window.set_status(MonitorStatus.IDLE)
    assert not window.start_button.isHidden() and window.pause_button.isHidden()
    assert not window.stop_button.isEnabled()
    window.set_status(MonitorStatus.RUNNING)
    assert window.start_button.isHidden() and not window.pause_button.isHidden()
    assert window.stop_button.isEnabled() and not window.detect_button.isEnabled()
    window.set_status(MonitorStatus.PAUSED)
    assert not window.resume_button.isHidden() and window.pause_button.isHidden()
    window.set_status(MonitorStatus.ERROR)
    assert window.start_button.text() == "Try Again"


def test_missing_models_disable_start(window):
    window.set_models_ok(False)
    assert not window.start_button.isEnabled() and not window.calibrate_button.isEnabled()


def test_window_buttons_emit_intents(qtbot, window):
    window.set_status(MonitorStatus.IDLE)
    with qtbot.waitSignal(window.start_clicked, timeout=500):
        window.start_button.click()
    with qtbot.waitSignal(window.calibrate_clicked, timeout=500):
        window.calibrate_button.click()
    window.set_status(MonitorStatus.RUNNING)
    with qtbot.waitSignal(window.pause_clicked, timeout=500):
        window.pause_button.click()
    with qtbot.waitSignal(window.stop_clicked, timeout=500):
        window.stop_button.click()
    with qtbot.waitSignal(window.sound_toggled, timeout=500) as blocker:
        window.sound_check.click()
    assert blocker.args == [False]


def test_result_updates_pet_and_panels(window):
    engine = PostureEngine(baseline=make_baseline())
    result = None
    for t in timeline(0, 15, 10):
        result = engine.update(obs(t, 0.0, 2.0))
    assert result is not None
    window.set_status(MonitorStatus.RUNNING)
    window.show_result(result)
    assert window.pet.state is PetState.WARNING
    assert window.head_panel.chip.text() == "Warning"
    assert window.back_panel.chip.text() == "Within range"
    assert "Ongoing for" in window.head_panel.duration.text()


def test_alert_banner(window):
    alert = Alert("Time for a posture check!", "msg", SignalLevel.WARNING, None)
    window.show_alert(alert)
    assert not window.reminder.isHidden()
    assert window.reminder.property("tone") == "warn"


def test_close_event_is_delegated(qtbot, window):
    window.show()
    with qtbot.waitSignal(window.close_requested, timeout=500):
        window.close()
    assert window.isVisible()  # the app decides; the window does not close itself


def test_settings_dialog_validates_and_forgets_baseline(qtbot):
    dialog = SettingsDialog(AppSettings(baseline=make_baseline()))
    qtbot.addWidget(dialog)
    dialog.warning.setValue(20)
    dialog.critical.setValue(10)  # below warning + 5: clamped by the spin box minimum
    dialog.sensitivity.setCurrentIndex(2)
    dialog.sound.setChecked(False)
    dialog.forget.click()
    result = dialog.result_settings()
    assert result.warning_seconds == 20 and result.critical_seconds == 25
    assert result.sensitivity is Sensitivity.STRICT and not result.sound_enabled
    assert result.baseline is None


@pytest.fixture
def app(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(TrayController, "available", property(lambda self: True))
    store = SettingsStore(tmp_path / "settings.json")
    application = PixelPostureApp(qapp, store, AppSettings())
    qtbot.addWidget(application.window)
    monkeypatch.setattr(qapp, "quit", lambda: None)  # keep the shared test QApplication alive
    yield application, store
    application.quit()  # stops the stats timer and the controller


def test_close_to_tray_hides_window_and_remembers_hint(app):
    application, store = app
    application.show_window()
    application.window.close()
    assert not application.window.isVisible()
    assert store.load().tray_hint_shown


def test_tray_actions_drive_the_controller(qtbot, qapp, tmp_path, monkeypatch):
    calls: list[str] = []
    for name in ("start", "pause", "resume"):
        monkeypatch.setattr(MonitorController, name, lambda self, n=name: calls.append(n))
    application = PixelPostureApp(qapp, SettingsStore(tmp_path / "s.json"), AppSettings())
    qtbot.addWidget(application.window)
    monkeypatch.setattr(qapp, "quit", lambda: None)
    application.tray.start_action.trigger()
    application.tray.pause_action.trigger()
    application.tray.resume_action.trigger()
    assert calls == ["start", "pause", "resume"]
    application.quit()


def test_quick_settings_are_persisted(app):
    application, store = app
    application.window.sensitivity_combo.setCurrentIndex(0)
    application.window.sensitivity_combo.activated.emit(0)
    assert store.load().sensitivity is Sensitivity.RELAXED


def test_quit_releases_everything(app):
    application, store = app
    application.quit()
    assert not application.controller.has_worker
    assert application.window.allow_close and not application.window.isVisible()
    assert store.path.exists()


def test_sprites_are_well_formed():
    for state in PetState:
        for frame in range(FRAME_COUNT):
            rows = sprite(state, frame)
            assert len(rows) == CANVAS_HEIGHT
            assert all(len(r) == CANVAS_WIDTH for r in rows)
            assert set("".join(rows)) <= set(PALETTE) | {"."}
    svg = to_svg(sprite(PetState.THRIVING))
    assert svg.startswith("<svg") and 'shape-rendering="crispEdges"' in svg


def test_states_look_different():
    images = {"".join(sprite(state)) for state in PetState}
    assert len(images) == len(PetState)


SECOND_INSTANCE = """
import sys
from PySide6.QtCore import QCoreApplication
from app.services.single_instance import SingleInstance
app = QCoreApplication([])
sys.exit(0 if SingleInstance(sys.argv[1]).notify_existing() else 1)
"""


def test_second_process_hands_over_to_first(qtbot):
    key = f"PixelPostureTest-{uuid.uuid4().hex}"
    first = SingleInstance(key)
    assert first.listen()
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    process = subprocess.Popen([sys.executable, "-c", SECOND_INSTANCE, key], env=env)
    with qtbot.waitSignal(first.activation_requested, timeout=10000):
        pass
    assert process.wait(timeout=10) == 0  # the second process exits instead of starting


def test_no_existing_instance(qtbot):
    assert not SingleInstance(f"PixelPostureTest-{uuid.uuid4().hex}").notify_existing()


def make_app(qapp, tmp_path, monkeypatch, settings=None):
    monkeypatch.setattr(TrayController, "available", property(lambda self: True))
    monkeypatch.setattr(qapp, "quit", lambda: None)
    store = SettingsStore(tmp_path / "settings.json")
    return PixelPostureApp(qapp, store, settings or AppSettings()), store


def test_missing_models_disable_monitoring_and_explain(qtbot, qapp, tmp_path, monkeypatch):
    from app import application as application_module
    from app.vision.model_assets import FACE_MODEL

    monkeypatch.setattr(application_module, "missing_or_invalid", lambda: [FACE_MODEL])
    application, _ = make_app(qapp, tmp_path, monkeypatch)
    qtbot.addWidget(application.window)
    window = application.window
    assert not window.start_button.isEnabled() and not window.calibrate_button.isEnabled()
    assert "face_landmarker.task" in window.banner.text.text()
    assert "download_models.py" in window.banner.text.text()
    application.quit()


def test_detect_cameras_lists_working_cameras(qtbot, qapp, tmp_path, monkeypatch):
    from app import application as application_module

    monkeypatch.setattr(application_module, "probe_cameras", lambda n: [0, 2])
    application, _ = make_app(qapp, tmp_path, monkeypatch)
    qtbot.addWidget(application.window)
    application.window.detect_button.click()
    combo = application.window.camera_combo
    qtbot.waitUntil(lambda: combo.findText("Camera 2 ✓") >= 0, timeout=3000)
    assert combo.currentData() == 0
    assert application.window.detect_button.isEnabled()
    application.quit()


def test_detect_switches_to_a_working_camera(qtbot, qapp, tmp_path, monkeypatch):
    from app import application as application_module

    monkeypatch.setattr(application_module, "probe_cameras", lambda n: [1])
    application, store = make_app(qapp, tmp_path, monkeypatch, AppSettings(camera_index=3))
    qtbot.addWidget(application.window)
    application.window.detect_button.click()
    qtbot.waitUntil(lambda: application.settings.camera_index == 1, timeout=3000)
    assert store.load().camera_index == 1
    application.quit()


def test_calibration_baseline_is_persisted_without_losing_other_settings(
    qtbot, qapp, tmp_path, monkeypatch
):
    application, store = make_app(qapp, tmp_path, monkeypatch, AppSettings(sound_enabled=False))
    qtbot.addWidget(application.window)
    baseline = make_baseline()
    application.controller.settings_changed.emit(AppSettings(baseline=baseline))
    saved = store.load()
    assert saved.baseline == baseline
    assert saved.sound_enabled is False
    application.quit()


def test_camera_error_is_shown_to_the_user(qtbot, qapp, tmp_path, monkeypatch):
    application, _ = make_app(qapp, tmp_path, monkeypatch)
    qtbot.addWidget(application.window)
    application.controller.last_error = "Camera 0 could not be opened."
    application._on_status(MonitorStatus.ERROR)
    assert application.window.banner.text.text() == "Camera 0 could not be opened."
    assert application.window.start_button.text() == "Try Again"
    application.quit()
