"""Centralized logging setup: file + console."""

from __future__ import annotations

import logging
from pathlib import Path

_configured = False


def setup_logging(
    log_dir: str | Path = "logs",
    log_file: str = "trading_bot.log",
    *,
    console_level: int = logging.WARNING,
    file_level: int = logging.DEBUG,
) -> Path:
    """
    Configure root logger with a rotating-style single file handler.
    Returns the path to the log file.
    """
    global _configured
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    full_path = log_path / log_file

    if _configured:
        return full_path

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if setup_logging is called twice
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        fh = logging.FileHandler(full_path, encoding="utf-8")
        fh.setLevel(file_level)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        ch = logging.StreamHandler()
        ch.setLevel(console_level)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    _configured = True
    return full_path
