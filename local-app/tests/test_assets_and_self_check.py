"""Model-asset verification and the --self-check failure paths (no camera needed)."""

from __future__ import annotations

import pytest

import main
from app.vision import model_assets
from app.vision.model_assets import ALL_MODELS, FACE_MODEL, load_model_bytes, missing_or_invalid


def test_missing_models_are_reported(tmp_path):
    assert {m.filename for m in missing_or_invalid(tmp_path)} == {m.filename for m in ALL_MODELS}


def test_corrupt_model_fails_integrity_check(tmp_path):
    (tmp_path / FACE_MODEL.filename).write_bytes(b"not a model")
    assert FACE_MODEL in missing_or_invalid(tmp_path)
    with pytest.raises(ValueError, match="integrity"):
        load_model_bytes(FACE_MODEL, tmp_path)


def test_self_check_fails_cleanly_without_models(monkeypatch, capsys):
    monkeypatch.setattr(model_assets, "missing_or_invalid", lambda directory=None: list(ALL_MODELS))
    assert main.run_self_check(0) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "download_models.py" in out


def test_resources_dir_points_at_bundled_files():
    resources = model_assets.resources_dir()
    assert (resources / "fonts" / "PressStart2P-Regular.ttf").is_file()
    assert (resources / "fonts" / "OFL.txt").is_file()
