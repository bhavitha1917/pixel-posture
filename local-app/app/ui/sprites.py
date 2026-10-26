"""Pip, the pixel pet: original pixel art defined as character grids.

This module is Qt-free so the same definitions render in the desktop app (``pet_widget``)
and export to SVG for the website (``scripts/export_sprites.py``).
"""

from __future__ import annotations

from app.posture.models import PetState

CANVAS_WIDTH = 26
CANVAS_HEIGHT = 22
BODY_ORIGIN = (3, 3)  # where the 20x18 body grid sits on the canvas

PALETTE: dict[str, str] = {
    "o": "#3B2D52",  # outline
    "b": "#CFC2FF",  # body (lavender)
    "h": "#F1ECFF",  # highlight
    "s": "#AE9CF0",  # shade
    "e": "#2E2240",  # eyes
    "w": "#FFFFFF",  # eye shine
    "c": "#F6AFC0",  # cheeks
    "m": "#2E2240",  # mouth
    "d": "#8FD0F2",  # sweat drop
    "y": "#FFD36B",  # sparkle
    "r": "#F28C7E",  # stress squiggle (coral)
    "z": "#9C8FBF",  # sleepy Zs
}

BODY = (
    "...oo..........oo...",
    "..obbo........obbo..",
    "..obbbo......obbbo..",
    ".obbbbboooooobbbbbo.",
    ".obhhbbbbbbbbbbbbbo.",
    "obhhbbbbbbbbbbbbbbbo",
    "obhbbbbbbbbbbbbbbbbo",
    "obbbbbbbbbbbbbbbbbbo",
    "obbbbbbbbbbbbbbbbbbo",
    "obbbbbbbbbbbbbbbbbbo",
    "obbbbbbbbbbbbbbbbbbo",
    "obbbbbbbbbbbbbbbbbbo",
    "obbbbbbbbbbbbbbbbbso",
    ".obbbbbbbbbbbbbbbso.",
    ".obsbbbbbbbbbbbbsso.",
    "..obssbbbbbbbbsssso.",
    "...osssssssssssso...",
    ".....oooooooooo.....",
)

Pixels = list[tuple[int, int, str]]  # (x, y, palette key) in body coordinates


def _mirror(pixels: Pixels) -> Pixels:
    """Mirror left-side facial features onto the right side of the 20-wide body."""
    return pixels + [(19 - x, y, c) for x, y, c in pixels]


_ROUND_EYES = _mirror([(5, 8, "w"), (6, 8, "e"), (5, 9, "e"), (6, 9, "e")])
_BLINK_EYES = _mirror([(5, 9, "e"), (6, 9, "e")])
_CHEEKS = _mirror([(3, 10, "c"), (4, 10, "c")])

# Facial features per state and animation frame (body coordinates).
_FACES: dict[PetState, tuple[Pixels, Pixels]] = {
    PetState.CALIBRATING: (
        _ROUND_EYES + _CHEEKS + [(9, 11, "m"), (10, 11, "m")],
        _BLINK_EYES + _CHEEKS + [(9, 11, "m"), (10, 11, "m")],
    ),
    PetState.THRIVING: (
        _mirror([(4, 9, "e"), (5, 8, "e"), (6, 9, "e")])
        + _CHEEKS
        + [(8, 11, "m"), (11, 11, "m"), (9, 12, "m"), (10, 12, "m")],
    )
    * 2,
    PetState.WARNING: (
        _ROUND_EYES
        + _mirror([(5, 6, "o"), (6, 5, "o")])
        + [(8, 12, "m"), (9, 11, "m"), (10, 12, "m"), (11, 11, "m")],
    )
    * 2,
    PetState.CRITICAL: (
        _mirror([(4, 8, "o"), (5, 8, "o"), (6, 8, "o"), (7, 8, "o"), (5, 9, "e"), (6, 9, "e")])
        + _mirror([(4, 10, "s"), (5, 10, "s"), (6, 10, "s")])
        + [(9, 11, "m"), (10, 11, "m"), (8, 12, "m"), (11, 12, "m")],
    )
    * 2,
    PetState.UNAVAILABLE: (
        _mirror([(4, 9, "e"), (5, 9, "e"), (6, 9, "e")]) + [(9, 12, "m"), (10, 12, "m")],
    )
    * 2,
}

# Accessories in canvas coordinates, per frame.
_SPARKLE = [(1, 4, "y"), (0, 5, "y"), (2, 5, "y"), (1, 6, "y")]
_SPARKLE_2 = [(24, 2, "y"), (23, 3, "y"), (25, 3, "y"), (24, 4, "y")]
_DROP = [(23, 4, "d"), (22, 5, "d"), (23, 5, "d"), (23, 6, "d")]
_DROP_LOW = [(x, y + 1, c) for x, y, c in _DROP]
_DROP_LEFT = [(2, 4, "d"), (1, 5, "d"), (2, 5, "d"), (2, 6, "d")]
_SQUIGGLE = [(10, 0, "r"), (11, 1, "r"), (12, 0, "r"), (13, 1, "r"), (14, 0, "r"), (15, 1, "r")]
_SQUIGGLE_2 = [(x, 1 - y, c) for x, y, c in _SQUIGGLE]


def _z(x: int, y: int) -> Pixels:
    return [(x, y, "z"), (x + 1, y, "z"), (x + 2, y, "z"), (x + 1, y + 1, "z"),
            (x, y + 2, "z"), (x + 1, y + 2, "z"), (x + 2, y + 2, "z")]  # fmt: skip


_ACCESSORIES: dict[PetState, tuple[Pixels, Pixels]] = {
    PetState.CALIBRATING: ([], []),
    PetState.THRIVING: (_SPARKLE, _SPARKLE_2),
    PetState.WARNING: (_DROP, _DROP_LOW),
    PetState.CRITICAL: (_DROP + _DROP_LEFT + _SQUIGGLE, _DROP_LOW + _DROP_LEFT + _SQUIGGLE_2),
    PetState.UNAVAILABLE: (_z(21, 1), _z(22, 0)),
}

# Vertical body offset per frame: Pip bounces when happy and slumps when critical.
_BODY_OFFSET: dict[PetState, tuple[int, int]] = {
    PetState.CALIBRATING: (0, 0),
    PetState.THRIVING: (0, -1),
    PetState.WARNING: (0, 0),
    PetState.CRITICAL: (1, 1),
    PetState.UNAVAILABLE: (1, 1),
}

FRAME_COUNT = 2


def sprite(state: PetState, frame: int = 0) -> list[str]:
    """The full canvas for ``state`` as rows of palette keys ('.' = transparent)."""
    frame %= FRAME_COUNT
    grid = [["."] * CANVAS_WIDTH for _ in range(CANVAS_HEIGHT)]
    ox, oy = BODY_ORIGIN
    oy += _BODY_OFFSET[state][frame]

    def put(x: int, y: int, key: str) -> None:
        if 0 <= x < CANVAS_WIDTH and 0 <= y < CANVAS_HEIGHT:
            grid[y][x] = key

    for y, row in enumerate(BODY):
        for x, key in enumerate(row):
            if key != ".":
                put(ox + x, oy + y, key)
    for x, y, key in _FACES[state][frame]:
        put(ox + x, oy + y, key)
    for x, y, key in _ACCESSORIES[state][frame]:
        put(x, y, key)
    return ["".join(row) for row in grid]


def to_svg(rows: list[str], pixel: int = 1) -> str:
    """Crisp SVG with one rect per horizontal run of equal colour."""
    width, height = len(rows[0]) * pixel, len(rows) * pixel
    rects = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            key = row[x]
            run = 1
            while x + run < len(row) and row[x + run] == key:
                run += 1
            if key != ".":
                rects.append(
                    f'<rect x="{x * pixel}" y="{y * pixel}" width="{run * pixel}" '
                    f'height="{pixel}" fill="{PALETTE[key]}"/>'
                )
            x += run
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" shape-rendering="crispEdges">'
        + "".join(rects)
        + "</svg>"
    )
