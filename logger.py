from __future__ import annotations

import logging
import io
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_configured: bool = False
_LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_file: Optional[Path] = None,
    level: Optional[str] = None,
    max_bytes: Optional[int] = None,
    backup_count: Optional[int] = None,
) -> logging.Logger:
    global _configured
    if _configured:
        return logging.getLogger("newsscrape")

    from settings import Settings
    cfg = Settings()

    _file = log_file or cfg.log_file
    _level = getattr(logging, (level or cfg.log_level).upper(), logging.INFO)
    _max = max_bytes if max_bytes is not None else cfg.log_max_bytes
    _backups = backup_count if backup_count is not None else cfg.log_backup_count

    _file.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("newsscrape")
    root.setLevel(_level)
    root.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        filename=str(_file),
        maxBytes=_max,
        backupCount=_backups,
        encoding="utf-8",
    )
    file_handler.setLevel(_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    utf8_stream = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    console_handler = logging.StreamHandler(utf8_stream)
    console_handler.setLevel(_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _configured = True
    root.debug("Logging subsystem initialised -> %s [%s]", _file, _level)
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"newsscrape.{name}")
