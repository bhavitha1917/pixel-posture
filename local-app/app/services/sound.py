"""Pip's reminder chime: a bundled WAV played locally, with a volume setting.

Playback uses ``winsound.PlaySound`` (standard library, asynchronous). A new chime replaces
any chime still playing instead of overlapping it, nothing is ever looped, and chimes closer
together than ``min_interval_s`` are skipped. If the asset is missing or unreadable, the
player falls back to the Windows system sound so reminders are never silently lost.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import wave
from array import array
from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.vision.model_assets import resources_dir

log = logging.getLogger(__name__)

CHIME_FILENAME = "pip_chime.wav"
MAX_CHIME_SECONDS = 3.0
MIN_CHIME_INTERVAL_S = 1.5


def chime_path() -> Path:
    return resources_dir() / "sounds" / CHIME_FILENAME


def read_chime(path: Path) -> tuple[wave._wave_params, bytes] | None:
    """The chime's PCM data if it is a short 16-bit PCM WAV, otherwise None."""
    try:
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            frames = source.readframes(params.nframes)
    except (OSError, EOFError, wave.Error) as exc:
        log.warning("Chime unavailable (%s): %s", path.name, exc)
        return None
    if (
        params.sampwidth != 2
        or params.nchannels not in (1, 2)
        or not 8000 <= params.framerate <= 96000
        or params.nframes == 0
        or params.nframes / params.framerate > MAX_CHIME_SECONDS
    ):
        log.warning("Chime %s has an unsupported format: %s", path.name, params)
        return None
    return params, frames


def _winsound_play(path: Path) -> None:
    import winsound  # noqa: PLC0415 - Windows-only stdlib module

    # ASYNC: never blocks the UI; a later call replaces this one. NODEFAULT: if the file
    # cannot be played, stay quiet rather than playing the generic Windows sound.
    winsound.PlaySound(
        str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
    )


def system_beep() -> None:
    if sys.platform == "win32":
        import winsound  # noqa: PLC0415

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    else:
        QApplication.beep()


class ChimePlayer:
    """Implements the dispatcher's ``SoundPlayer`` protocol."""

    def __init__(
        self,
        cache_dir: Path,
        volume: int = 70,
        *,
        path: Path | None = None,
        play_file: Callable[[Path], None] | None = None,
        fallback: Callable[[], None] = system_beep,
        clock: Callable[[], float] = time.monotonic,
        min_interval_s: float = MIN_CHIME_INTERVAL_S,
    ) -> None:
        self.volume = volume
        self._cache_dir = cache_dir
        self._path = path or chime_path()
        if play_file is None:
            play_file = _winsound_play if sys.platform == "win32" else lambda _: QApplication.beep()
        self._play_file = play_file
        self._fallback = fallback
        self._clock = clock
        self._min_interval_s = min_interval_s
        self._last_played: float | None = None
        self._chime = read_chime(self._path)
        self._files: dict[int, Path] = {}

    @property
    def asset_available(self) -> bool:
        return self._chime is not None

    def play(self) -> None:
        self._play(force=False)

    def preview(self, volume: int | None = None) -> None:
        """Play now at ``volume`` (the Settings slider), ignoring the repeat guard."""
        if volume is not None:
            self.volume = volume
        self._play(force=True)

    def _play(self, force: bool) -> None:
        now = self._clock()
        if (
            not force
            and self._last_played is not None
            and now - self._last_played < self._min_interval_s
        ):
            log.debug("Chime skipped: the previous one is still recent")
            return
        if self.volume <= 0:
            return
        self._last_played = now
        file = self._file_for_volume(self.volume)
        if file is None:
            self._fallback()
        else:
            self._play_file(file)

    def _file_for_volume(self, volume: int) -> Path | None:
        """The chime scaled to ``volume`` percent, cached on disk (PlaySound needs a file)."""
        if self._chime is None:
            return None
        volume = min(volume, 100)
        if volume == 100:
            return self._path
        cached = self._files.get(volume)
        if cached is not None and cached.is_file():
            return cached
        params, frames = self._chime
        samples = array("h")
        samples.frombytes(frames)
        if sys.byteorder == "big":
            samples.byteswap()
        gain = (volume / 100) ** 2  # perceptually smoother than a linear slider
        scaled = array("h", (round(s * gain) for s in samples))
        if sys.byteorder == "big":
            scaled.byteswap()
        target = self._cache_dir / f"pip_chime_{volume}.wav"
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            with wave.open(str(tmp), "wb") as out:
                out.setparams(params)
                out.writeframes(scaled.tobytes())
            os.replace(tmp, target)
        except OSError as exc:
            log.warning("Could not prepare the chime at %d%% volume: %s", volume, exc)
            return self._path
        self._files[volume] = target
        return target
