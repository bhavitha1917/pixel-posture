# Experimental PyInstaller spec for Pixel Posture (one-folder build, windowed).
# Run from the repository root after downloading the models:
#   pyinstaller local-app/packaging/pixel_posture.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

ROOT = Path(SPECPATH).resolve().parents[1]  # noqa: F821 - SPECPATH is provided by PyInstaller
APP = ROOT / "local-app"
RESOURCES = APP / "app" / "resources"

for model in ("pose_landmarker_lite.task", "face_landmarker.task"):
    if not (RESOURCES / "models" / model).is_file():
        raise SystemExit(f"Missing {model}: run python local-app/scripts/download_models.py first")

datas = [
    (str(RESOURCES / "models" / "pose_landmarker_lite.task"), "app/resources/models"),
    (str(RESOURCES / "models" / "face_landmarker.task"), "app/resources/models"),
    (str(RESOURCES / "fonts"), "app/resources/fonts"),
]
datas += collect_data_files("mediapipe", excludes=["**/*.task"])
# Licence texts for everything redistributed in the bundle (see THIRD_PARTY_NOTICES.md).
datas.append((str(ROOT / "THIRD_PARTY_NOTICES.md"), "."))
datas.append((str(ROOT / "LICENSE"), "."))
for package in (
    "mediapipe", "opencv-contrib-python", "numpy", "matplotlib",
    "PySide6-Essentials", "shiboken6", "absl-py", "flatbuffers",
):
    datas += copy_metadata(package)
binaries = collect_dynamic_libs("mediapipe")

a = Analysis(  # noqa: F821
    [str(APP / "main.py")],
    pathex=[str(APP)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["PySide6.QtNetwork"],
    # mediapipe.tasks.python.vision imports matplotlib at import time, so it must stay.
    excludes=["tkinter", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PixelPosture",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PixelPosture", upx=False)  # noqa: F821
