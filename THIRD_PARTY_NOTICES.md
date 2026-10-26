# Third-party notices

Pixel Posture's own code and the Pip pixel art are MIT-licensed (see `LICENSE`). The
project uses or redistributes the third-party components below. License identifiers were
read from each package's installed metadata (Python `importlib.metadata`, npm
`package.json`). This list is informational and is not legal advice. Check the original
license texts before redistributing.

## Desktop app (installed from PyPI; redistributed inside the PyInstaller build)

| Component | Version | License |
|---|---|---|
| PySide6-Essentials / shiboken6 (Qt for Python) | 6.12.0 | LGPL-3.0-only (or GPL-2.0/3.0) |
| MediaPipe | 1.1.1 | Apache-2.0 |
| MediaPipe model bundles `pose_landmarker_lite.task`, `face_landmarker.task` | float16 / v1 | Apache-2.0 (Google; see `local-app/app/resources/models/README.md`) |
| OpenCV (`opencv-contrib-python`) | 5.0.0.93 | Apache-2.0 (plus bundled third-party notices) |
| NumPy | 2.4.6 | BSD-3-Clause and others |
| matplotlib (imported by MediaPipe) | 3.11.2 | Matplotlib license (PSF-based) |
| absl-py, flatbuffers (MediaPipe dependencies) | – | Apache-2.0 |
| Press Start 2P font | – | SIL OFL 1.1 (`local-app/app/resources/fonts/OFL.txt`) |

The PyInstaller build copies these packages' `*.dist-info` metadata, including their
license files, into the bundle, along with this file and the font license. Qt is linked
dynamically (separate DLLs in the one-folder build), which is the usual way to meet the
LGPL's relinking requirement. Verify this against your own distribution plans.

## Website (bundled into the static build)

| Component | License |
|---|---|
| React, React DOM, React Router | MIT |
| Lucide icons (`lucide-react`) | ISC |
| Inter font (`@fontsource/inter`) | SIL OFL 1.1, text served at `/licenses/inter-OFL.txt` |
| Press Start 2P font (`@fontsource/press-start-2p`) | SIL OFL 1.1, text served at `/licenses/press-start-2p-OFL.txt` |

Development-only tools (pytest, Ruff, mypy, PyInstaller, Vite, Vitest, oxlint, TypeScript)
are not redistributed.
