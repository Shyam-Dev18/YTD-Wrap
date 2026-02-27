"""Infrastructure: ffmpeg detection and platform guidance.

This module is responsible for locating ffmpeg on the system PATH
and providing platform-specific installation guidance when it is
missing.

Rules
-----
* Detection via :func:`shutil.which` only — no subprocess.
* No permanent PATH modification.
* No automatic installation.
* No ``print()`` — callers handle user-facing output.
"""

from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass
from pathlib import Path

from ytd_wrap.exceptions import FfmpegNotFoundError


# ---------------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FfmpegStatus:
    """Result of an ffmpeg detection probe.

    Attributes
    ----------
    found : bool
        Whether ffmpeg was located on PATH.
    path : Path | None
        Absolute path to the ffmpeg binary, or ``None``.
    version_hint : str
        Human-readable status string (e.g. ``"found at …"`` or ``"not found"``).
    install_commands : tuple[str, ...]
        Suggested shell commands for installing ffmpeg on the current
        platform.  Empty when ffmpeg is already present.
    """

    found: bool
    path: Path | None
    version_hint: str
    install_commands: tuple[str, ...]


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def detect_ffmpeg() -> FfmpegStatus:
    """Probe the system for an ffmpeg binary.

    Returns a :class:`FfmpegStatus` regardless of whether ffmpeg is
    present — the caller decides whether to abort or merely warn.
    """
    result = shutil.which("ffmpeg")

    if result is not None:
        resolved = Path(result).resolve()
        return FfmpegStatus(
            found=True,
            path=resolved,
            version_hint=f"found at {resolved}",
            install_commands=(),
        )

    return FfmpegStatus(
        found=False,
        path=None,
        version_hint="not found",
        install_commands=_platform_install_commands(),
    )


def require_ffmpeg() -> Path:
    """Locate ffmpeg or raise :class:`FfmpegNotFoundError`.

    This is a convenience wrapper used by code paths that **require**
    ffmpeg to proceed (e.g. adaptive-format merging).
    """
    status = detect_ffmpeg()
    if not status.found or status.path is None:
        hint_lines: list[str] = []
        if status.install_commands:
            hint_lines.append("Install ffmpeg using one of:")
            hint_lines.extend(f"  {cmd}" for cmd in status.install_commands)
        raise FfmpegNotFoundError(
            "ffmpeg is not installed or not on PATH.",
            hint="\n".join(hint_lines) if hint_lines else None,
        )
    return status.path


# ---------------------------------------------------------------------------
# Platform-specific install guidance
# ---------------------------------------------------------------------------

def _platform_install_commands() -> tuple[str, ...]:
    """Return install commands appropriate for the current OS."""
    system = platform.system().lower()
    if system == "windows":
        return (
            "winget install Gyan.FFmpeg",
            "choco install ffmpeg",
        )
    if system == "linux":
        return (
            "sudo apt install ffmpeg",
            "sudo dnf install ffmpeg",
            "sudo pacman -S ffmpeg",
        )
    if system == "darwin":
        return ("brew install ffmpeg",)
    # Fallback — generic guidance.
    return ("Please install ffmpeg from https://ffmpeg.org/download.html",)


# ---------------------------------------------------------------------------
# Future auto-install stub
# ---------------------------------------------------------------------------

def future_auto_install() -> None:
    """Placeholder for a future automatic ffmpeg installer.

    This function intentionally raises :class:`NotImplementedError`.
    It exists as an explicit stub so that the feature can be tracked
    and wired when appropriate — **no silent installs** are permitted
    without user consent and without this stub being replaced with
    a full implementation.
    """
    raise NotImplementedError(
        "Automatic ffmpeg installation is not yet implemented. "
        "Please install ffmpeg manually."
    )
