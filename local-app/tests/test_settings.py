import json

from conftest import make_baseline

from app.posture.config import Sensitivity
from app.settings.store import AppSettings, SettingsStore


def test_defaults_when_file_missing(tmp_path):
    assert SettingsStore(tmp_path / "settings.json").load() == AppSettings()


def test_round_trip_including_baseline(tmp_path):
    store = SettingsStore(tmp_path / "nested" / "settings.json")
    settings = AppSettings(
        camera_index=1,
        sensitivity=Sensitivity.STRICT,
        warning_seconds=15,
        critical_seconds=45,
        sound_enabled=False,
        reduce_motion=True,
        baseline=make_baseline(camera_index=1),
    )
    store.save(settings)
    assert store.load() == settings


def test_out_of_range_values_are_clamped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "camera_index": 99,
                "warning_seconds": 1,
                "critical_seconds": 2,
                "recovery_seconds": 1000,
                "cooldown_seconds": -5,
            }
        )
    )
    s = SettingsStore(path).load()
    assert s.camera_index == 9
    assert s.warning_seconds == 3
    assert s.critical_seconds == 8  # at least warning + 5
    assert s.recovery_seconds == 30
    assert s.cooldown_seconds == 10


def test_wrong_types_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "camera_index": "front",
                "sensitivity": "extreme",
                "sound_enabled": "yes",
                "warning_seconds": True,
                "baseline": {"neck_ratio": "x"},
            }
        )
    )
    s = SettingsStore(path).load()
    defaults = AppSettings()
    assert s.camera_index == defaults.camera_index
    assert s.sensitivity is Sensitivity.BALANCED
    assert s.sound_enabled is True
    assert s.warning_seconds == defaults.warning_seconds
    assert s.baseline is None


def test_invalid_baseline_numbers_are_rejected(tmp_path):
    path = tmp_path / "settings.json"
    bad = make_baseline().to_dict() | {"shoulder_width": -1.0}
    path.write_text(json.dumps({"baseline": bad}))
    assert SettingsStore(path).load().baseline is None


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    assert SettingsStore(path).load() == AppSettings()
    assert (tmp_path / "settings.json.bak").read_text() == "{not json"
    assert not path.exists()


def test_settings_build_posture_config():
    cfg = AppSettings(warning_seconds=12, critical_seconds=40, recovery_seconds=4).posture_config()
    assert (cfg.timing.warning_s, cfg.timing.critical_s, cfg.timing.recovery_s) == (12, 40, 4)


def test_baseline_camera_match():
    b = make_baseline()
    assert b.matches_camera(0, 640, 480)
    assert not b.matches_camera(1, 640, 480)
    assert not b.matches_camera(0, 1280, 720)
