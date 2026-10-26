"""Generate Pip's reminder chime: an original, soft two-note bell (G5 then C6).

Pure standard library and fully deterministic, so the committed WAV can always be rebuilt:

    python local-app/scripts/generate_chime.py
"""

from __future__ import annotations

import math
import sys
import wave
from array import array
from pathlib import Path

SAMPLE_RATE = 22_050
DURATION_S = 0.9
PEAK = 0.55  # about -5 dBFS: gentle, and leaves room for the volume setting to go down
# (start s, frequency Hz, decay time constant s) - a rising perfect fourth.
NOTES = ((0.0, 783.99, 0.16), (0.17, 1046.50, 0.26))
# Bell-like partials: (frequency multiple, relative amplitude, extra decay factor).
PARTIALS = ((1.0, 1.0, 1.0), (2.0, 0.28, 1.8), (3.0, 0.08, 2.6))
ATTACK_S = 0.008
FADE_OUT_S = 0.04

OUTPUT = Path(__file__).resolve().parents[1] / "app" / "resources" / "sounds" / "pip_chime.wav"


def render() -> array[int]:
    count = int(SAMPLE_RATE * DURATION_S)
    samples = [0.0] * count
    for start, freq, tau in NOTES:
        first = int(start * SAMPLE_RATE)
        for i in range(first, count):
            t = (i - first) / SAMPLE_RATE
            envelope = min(1.0, t / ATTACK_S)
            value = 0.0
            for multiple, amplitude, decay in PARTIALS:
                value += (
                    amplitude
                    * math.exp(-t * decay / tau)
                    * math.sin(2 * math.pi * freq * multiple * t)
                )
            samples[i] += envelope * value
    fade = int(FADE_OUT_S * SAMPLE_RATE)
    for k in range(fade):
        samples[count - 1 - k] *= k / fade
    scale = PEAK / max(abs(s) for s in samples)
    return array("h", (round(s * scale * 32767) for s in samples))


def write(path: Path = OUTPUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        data = render()
        if sys.byteorder == "big":
            data.byteswap()
        out.writeframes(data.tobytes())
    return path


if __name__ == "__main__":
    print(f"Wrote {write()}")
