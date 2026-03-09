"""Rotating file logger configuration for ytd-wrap."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from ytd_wrap.constants import LOG_BACKUP_COUNT, LOG_DIR, LOG_FILENAME, MAX_LOG_BYTES

# Guard so the handler setup only runs once per logger name.
_configured: set[str] = set()


def get_logger(name: str = "ytd-wrap") -> logging.Logger:
    """Return a configured logger that writes to the rotating log file.

    On first call the logger is configured with:

    * A :class:`~logging.handlers.RotatingFileHandler` writing ``DEBUG+`` to
      ``~/.ytd-wrap/logs/ytd-wrap.log`` (5 files × 2 MB).
    * A :class:`~rich.logging.RichHandler` writing ``WARNING+`` to the terminal.

    Subsequent calls with the same *name* return the existing logger unchanged.
    Safe to call before ``~/.ytd-wrap`` exists — the directory is created on
    first use.

    Args:
        name: Logger name (default ``"ytd-wrap"``).

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if name in _configured:
        return logger

    logger.setLevel(logging.DEBUG)

    # ------------------------------------------------------------------ #
    # File handler — rotating, DEBUG level                                #
    # ------------------------------------------------------------------ #
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / LOG_FILENAME
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)
    except OSError as exc:
        # If we cannot create the log directory (unlikely), fall back silently.
        _add_fallback_stderr_handler(logger, logging.DEBUG)
        logger.warning("Could not create log file: %s — logging to stderr only.", exc)

    # ------------------------------------------------------------------ #
    # Rich terminal handler — WARNING+ only                               #
    # ------------------------------------------------------------------ #
    try:
        from rich.logging import RichHandler  # lazy import

        rich_handler = RichHandler(
            level=logging.WARNING,
            show_path=False,
            rich_tracebacks=True,
            markup=True,
        )
        rich_handler.setLevel(logging.WARNING)
        logger.addHandler(rich_handler)
    except ImportError:
        _add_fallback_stderr_handler(logger, logging.WARNING)

    _configured.add(name)
    return logger


def _add_fallback_stderr_handler(logger: logging.Logger, level: int) -> None:
    """Add a plain stderr handler if rich is unavailable.

    Args:
        logger: The logger to add the handler to.
        level: The minimum log level for this handler.
    """
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(level)
    stderr_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stderr_handler)
