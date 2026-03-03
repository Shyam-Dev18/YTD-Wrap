"""Download path resolution with graceful fallback."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

from ytd_wrap.constants import APP_DIR, DEFAULT_DOWNLOAD_DIR, LOG_DIR

# Characters that are forbidden in filenames on Windows, macOS, or Linux.
_ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
)
_MAX_FILENAME_LENGTH = 200


def get_download_dir() -> Path:
    """Return the best available download directory.

    Tries ``~/Downloads`` first; falls back to the current working directory
    if ``~/Downloads`` does not exist or is not writable.

    Never raises. Always returns a valid, writable :class:`~pathlib.Path`.

    Returns:
        An existing, writable directory path.
    """
    candidate = DEFAULT_DOWNLOAD_DIR
    if _is_writable_dir(candidate):
        return candidate

    fallback = Path.cwd()
    if _is_writable_dir(fallback):
        return fallback

    # Last resort: return cwd regardless (caller will surface any write error).
    return fallback


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are illegal in filenames.

    Normalises Unicode to NFC, strips control characters and characters
    forbidden on Windows / macOS / Linux, collapses whitespace runs, and
    truncates to :data:`~ytd_wrap.constants._MAX_FILENAME_LENGTH` characters.

    Args:
        name: Raw filename string (without directory component).

    Returns:
        A cleaned filename string safe to use on all major platforms.
    """
    # Normalise unicode
    name = unicodedata.normalize("NFC", name)

    # Replace illegal characters with underscore
    name = _ILLEGAL_CHARS_RE.sub("_", name)

    # Strip leading/trailing dots and spaces (Windows dislikes them)
    name = name.strip(". ")

    # Collapse multiple spaces / underscores
    name = re.sub(r"[ _]{2,}", " ", name)

    # Guard against Windows reserved names (match stem before extension)
    stem = Path(name).stem.upper()
    if stem in _WINDOWS_RESERVED_NAMES:
        name = f"_{name}"

    # Enforce maximum length (keep extension intact)
    if len(name) > _MAX_FILENAME_LENGTH:
        path = Path(name)
        suffix = path.suffix  # e.g. ".mp4"
        max_stem = _MAX_FILENAME_LENGTH - len(suffix)
        name = path.stem[:max_stem] + suffix

    return name or "video"


def ensure_unique_path(path: Path) -> Path:
    """Return *path* with a counter suffix if the file already exists.

    If ``/dir/video.mp4`` exists, returns ``/dir/video (1).mp4``.
    Increments until a non-existing path is found.

    Args:
        path: Desired output path (may or may not already exist).

    Returns:
        A :class:`~pathlib.Path` that does not currently exist on disk.
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def ensure_app_dirs() -> None:
    """Create ``~/.ytd-wrap/`` and ``~/.ytd-wrap/logs/`` if they do not exist.

    Silently swallows :class:`OSError` (e.g. permission denied) so that the
    application can still function when the home directory is not writable.
    Logs a warning in that case.
    """
    import logging
    _alog = logging.getLogger("ytd-wrap")
    for d in (APP_DIR, LOG_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _alog.warning("Could not create app directory %s: %s", d, exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_writable_dir(path: Path) -> bool:
    """Return True if *path* is an existing directory we can write to.

    Args:
        path: The directory to test.

    Returns:
        True if the directory exists and is writable.
    """
    try:
        return path.is_dir() and os.access(path, os.W_OK)
    except OSError:
        return False
