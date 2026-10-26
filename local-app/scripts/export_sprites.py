"""Export Pip's sprites as SVG for the showcase website (single source of truth for the art).

Usage (from the repository root):  python local-app/scripts/export_sprites.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.posture.models import PetState
from app.ui.sprites import FRAME_COUNT, sprite, to_svg

TARGET = Path(__file__).resolve().parents[2] / "showcase" / "src" / "assets" / "pet"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    for state in PetState:
        for frame in range(FRAME_COUNT):
            path = TARGET / f"{state.value}-{frame}.svg"
            path.write_text(to_svg(sprite(state, frame)) + "\n", encoding="utf-8")
            print(f"wrote {path.relative_to(TARGET.parents[3])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
