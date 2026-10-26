"""Pixel Posture desktop entry point.

python local-app/main.py                 launch the app
python local-app/main.py --self-check    verify models + camera without the GUI
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from app import APP_ID, APP_NAME, __version__
from app.logging_setup import configure_logging
from app.settings.store import SettingsStore

log = logging.getLogger("pixel_posture")

SELF_CHECK_FRAMES = 30


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    return Path(base) / APP_ID if base else Path.home() / ".pixel_posture"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pixel-posture", description=APP_NAME)
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument("--log-dir", type=Path, help="directory for log files")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="load models, open the camera, analyse a few frames, release it, and exit",
    )
    parser.add_argument("--camera", type=int, help="camera index for --self-check")
    return parser.parse_args(argv)


def report(*parts: object) -> None:
    line = " ".join(str(p) for p in parts)
    print(line)
    log.info("self-check: %s", line.strip())


def run_self_check(camera_index: int) -> int:
    """Headless verification of the real vision pipeline. Reports counts only, no images.

    Results are printed *and* logged: the packaged windowed exe has no console, so the log
    file (and the exit code) is how its result is read there.
    """
    from app.vision.analyzer import FrameAnalyzer  # noqa: PLC0415 - heavy import
    from app.vision.camera import CameraError, CameraSource  # noqa: PLC0415
    from app.vision.model_assets import missing_or_invalid  # noqa: PLC0415

    missing = missing_or_invalid()
    if missing:
        report("FAIL  models missing/invalid:", ", ".join(m.filename for m in missing))
        report("      run: python local-app/scripts/download_models.py")
        return 1
    report("OK    model files present and SHA-256 verified")

    started = time.perf_counter()
    analyzer = FrameAnalyzer()
    report(f"OK    MediaPipe pose + face models loaded in {time.perf_counter() - started:.1f} s")

    source = CameraSource(camera_index)
    try:
        width, height = source.open()
    except CameraError as exc:
        analyzer.close()
        report(f"FAIL  {exc}")
        return 2
    report(f"OK    camera {camera_index} opened at {width}x{height}")

    body = head = frames = 0
    issues: dict[str, int] = {}
    started = time.perf_counter()
    try:
        while frames < SELF_CHECK_FRAMES and time.perf_counter() - started < 15:
            frame = source.read()
            if frame is None:
                continue
            observation = analyzer.analyze(frame, time.monotonic()).observation
            frames += 1
            body += observation.body is not None
            head += observation.head is not None
            for issue in (observation.body_issue, observation.head_issue):
                if issue:
                    issues[issue] = issues.get(issue, 0) + 1
    finally:
        source.release()
        analyzer.close()
    elapsed = time.perf_counter() - started
    report(f"OK    analysed {frames} frames at {frames / max(elapsed, 1e-6):.1f} fps")
    report(f"      valid body: {body}/{frames}, valid head pose: {head}/{frames}")
    if issues:
        report("      reasons:", "; ".join(f"{k} ({v})" for k, v in sorted(issues.items())))
    report("OK    camera released, models closed")
    return 0 if frames else 3


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    data_dir = app_data_dir()
    log_file = configure_logging(args.log_dir or data_dir / "logs", args.debug)
    store = SettingsStore(data_dir / "settings.json")
    settings = store.load()
    log.info("%s %s starting (log: %s)", APP_NAME, __version__, log_file)

    if args.self_check:
        return run_self_check(settings.camera_index if args.camera is None else args.camera)

    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    from app.application import PixelPostureApp  # noqa: PLC0415
    from app.services.single_instance import SingleInstance, instance_key  # noqa: PLC0415
    from app.ui.theme import load_fonts, stylesheet, write_icons  # noqa: PLC0415

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName(APP_NAME)
    qt_app.setOrganizationName(APP_ID)
    qt_app.setApplicationVersion(__version__)
    qt_app.setQuitOnLastWindowClosed(False)  # closing the window keeps the tray app alive

    guard = SingleInstance(instance_key(APP_ID))
    if guard.notify_existing():
        log.info("Another instance is running; asked it to show its window")
        return 0
    if not guard.listen():
        log.warning("Single-instance server could not start; continuing")

    ui_family, pixel_family = load_fonts()
    icon_dir = write_icons(data_dir / "cache" / "icons")
    qt_app.setStyleSheet(stylesheet(ui_family, pixel_family, icon_dir))

    app = PixelPostureApp(qt_app, store, settings)
    guard.activation_requested.connect(app.show_window)
    app.show_window()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
