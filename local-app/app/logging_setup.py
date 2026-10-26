"""Logging: rotating file in the app-data folder plus stderr. Never logs image data."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUPS = 3


def configure_logging(log_dir: Path | None, debug: bool = False) -> Path | None:
    level = logging.DEBUG if debug else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    log_file = None
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "pixel_posture.log"
            handlers.append(
                RotatingFileHandler(
                    log_file, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
                )
            )
        except OSError:
            log_file = None
    logging.basicConfig(level=level, format=LOG_FORMAT, handlers=handlers, force=True)
    return log_file
