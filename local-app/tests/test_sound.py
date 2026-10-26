"""Pip's chime: the bundled asset, volume, repeat guard and graceful fallback.

``play_file`` and ``fallback`` record calls instead of producing audio, so these tests are
silent and deterministic. Whether the chime is *audible* is a manual check (docs/testing.md).
"""

from __future__ import annotations

import sys
import wave
from array import array
from pathlib import Path

import pytest

from app.services.alerts import Alert
from app.services.notifications import AlertDispatcher
from app.services.sound import (
    CHIME_FILENAME,
    MIN_CHIME_INTERVAL_S,
    ChimePlayer,
    chime_path,
    read_chime,
)

ROOT = Path(__file__).resolve().parents[2]
ALERT = Alert("t", "m", None, None)


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def player(tmp_path: Path, path: Path | None = None, volume: int = 100):
    played: list[Path] = []
    beeps: list[int] = []
    clock = Clock()
    chime = ChimePlayer(
        tmp_path / "cache",
        volume,
        path=path,
        play_file=played.append,
        fallback=lambda: beeps.append(1),
        clock=clock,
    )
    return chime, played, beeps, clock


def peak(path: Path) -> int:
    with wave.open(str(path), "rb") as source:
        samples = array("h")
        samples.frombytes(source.readframes(source.getnframes()))
    if sys.byteorder == "big":
        samples.byteswap()
    return max(abs(s) for s in samples)


def test_bundled_chime_is_found_and_short():
    path = chime_path()
    assert path.name == CHIME_FILENAME and path.is_file()
    chime = read_chime(path)
    assert chime is not None
    params, _frames = chime
    duration = params.nframes / params.framerate
    assert 0.5 <= duration <= 1.5
    assert params.nchannels == 1 and params.sampwidth == 2
    assert 0 < peak(path) < 32767 * 0.7  # gentle, never clipping
    assert path.stat().st_size < 100_000


def test_committed_chime_matches_its_generator():
    sys.path.insert(0, str(ROOT / "local-app" / "scripts"))
    try:
        import generate_chime
    finally:
        sys.path.pop(0)
    data = generate_chime.render()
    if sys.byteorder == "big":
        data.byteswap()
    _, frames = read_chime(chime_path())  # type: ignore[misc]
    assert frames == data.tobytes()


def test_packaging_bundles_the_sounds_folder():
    spec = (ROOT / "local-app" / "packaging" / "pixel_posture.spec").read_text(encoding="utf-8")
    assert '"sounds"' in spec and "app/resources/sounds" in spec


def test_play_uses_the_custom_chime(tmp_path):
    chime, played, beeps, _ = player(tmp_path)
    chime.play()
    assert played == [chime_path()] and beeps == []
    assert chime.asset_available


def test_repeated_alerts_do_not_stack(tmp_path):
    chime, played, _, clock = player(tmp_path)
    chime.play()
    clock.now += MIN_CHIME_INTERVAL_S / 2
    chime.play()
    assert len(played) == 1
    clock.now += MIN_CHIME_INTERVAL_S
    chime.play()
    assert len(played) == 2


def test_preview_ignores_the_repeat_guard_and_sets_volume(tmp_path):
    chime, played, _, _ = player(tmp_path)
    chime.play()
    chime.preview(40)
    assert len(played) == 2 and chime.volume == 40


def test_volume_scales_a_cached_copy(tmp_path):
    chime, played, _, clock = player(tmp_path, volume=50)
    chime.play()
    scaled = played[0]
    assert scaled.parent == tmp_path / "cache" and scaled.name == "pip_chime_50.wav"
    assert peak(scaled) == pytest.approx(peak(chime_path()) * 0.25, abs=2)
    clock.now += 10
    chime.play()
    assert played[1] == scaled  # reused, not rewritten


def test_zero_volume_is_silent(tmp_path):
    chime, played, beeps, _ = player(tmp_path, volume=0)
    chime.play()
    assert played == [] and beeps == []


@pytest.mark.parametrize("content", [None, b"", b"RIFF not really a wav file"])
def test_missing_or_corrupt_asset_falls_back_to_system_sound(tmp_path, content):
    path = tmp_path / "pip_chime.wav"
    if content is not None:
        path.write_bytes(content)
    chime, played, beeps, _ = player(tmp_path, path=path, volume=60)
    assert not chime.asset_available
    chime.play()
    assert played == [] and beeps == [1]


def test_unsupported_format_falls_back(tmp_path):
    path = tmp_path / "eight_bit.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(1)
        out.setframerate(22050)
        out.writeframes(bytes(2205))
    chime, _, beeps, _ = player(tmp_path, path=path)
    chime.play()
    assert beeps == [1]


def test_disabled_sound_never_plays(tmp_path):
    chime, played, beeps, _ = player(tmp_path)

    class Backend:
        def notify(self, title, message, critical):
            pass

    report = AlertDispatcher(Backend(), chime).deliver(
        ALERT, notifications_enabled=True, sound_enabled=False
    )
    assert not report.sound_played and played == [] and beeps == []


def test_playback_errors_do_not_break_delivery(tmp_path):
    def broken(_path: Path) -> None:
        raise RuntimeError("no audio device")

    chime = ChimePlayer(tmp_path, 100, play_file=broken)

    class Backend:
        def notify(self, title, message, critical):
            pass

    report = AlertDispatcher(Backend(), chime).deliver(
        ALERT, notifications_enabled=True, sound_enabled=True
    )
    assert report.notified and not report.sound_played
    assert report.error is not None and "no audio device" in report.error
