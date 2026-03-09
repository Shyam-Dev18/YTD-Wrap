"""Runtime dependency checks: ffmpeg, yt-dlp presence, Python version."""

from __future__ import annotations

import platform
import sys
from typing import Any

from ytd_wrap.constants import FFMPEG_INSTALL_COMMANDS


def check_ffmpeg() -> bool:
    """Detect whether ffmpeg is available on the system PATH.

    Uses a lazy import of :mod:`shutil` so the module is only loaded on demand.
    Logs a warning (but never raises) when ffmpeg is absent.

    Returns:
        ``True`` if ``ffmpeg`` is found and executable, ``False`` otherwise.
    """
    try:
        import shutil  # lazy
        found = shutil.which("ffmpeg") is not None
        if not found:
            from ytd_wrap.utils.logger import get_logger
            get_logger().warning(
                "ffmpeg not found on PATH. Install it with: %s",
                get_ffmpeg_install_command(),
            )
        return found
    except Exception:  # noqa: BLE001
        return False


def check_ytdlp() -> bool:
    """Detect whether yt-dlp is importable in the current environment.

    Uses a lazy import attempt so the module is only loaded on demand.

    Returns:
        ``True`` if ``yt_dlp`` can be imported, ``False`` otherwise.
    """
    import importlib  # lazy
    try:
        importlib.import_module("yt_dlp")
        return True
    except ImportError:
        from ytd_wrap.utils.logger import get_logger
        get_logger().warning("yt-dlp is not installed or not importable.")
        return False


def check_python_version() -> tuple[int, int]:
    """Return the major and minor version of the running Python interpreter.

    Returns:
        A ``(major, minor)`` tuple — e.g. ``(3, 11)``.
    """
    return sys.version_info.major, sys.version_info.minor


def get_ffmpeg_install_command() -> str:
    """Return the OS-appropriate ffmpeg installation command string.

    Detects the host OS via :func:`platform.system`.  On Linux, attempts to
    identify Debian/Ubuntu via :func:`platform.freedesktop_os_release` for a
    more specific command; falls back to the generic Linux entry otherwise.

    Returns:
        A human-readable install command for the detected host OS.
    """
    system = platform.system()  # "Darwin", "Windows", "Linux", …

    if system == "Linux":
        try:
            info = platform.freedesktop_os_release()  # Python 3.10+
            distro_id = info.get("ID", "").lower()
            distro_id_like = info.get("ID_LIKE", "").lower()
            if "ubuntu" in distro_id or "ubuntu" in distro_id_like:
                return FFMPEG_INSTALL_COMMANDS.get("Ubuntu", FFMPEG_INSTALL_COMMANDS["Linux"])
            if "debian" in distro_id or "debian" in distro_id_like:
                return FFMPEG_INSTALL_COMMANDS.get("Debian", FFMPEG_INSTALL_COMMANDS["Linux"])
        except (OSError, AttributeError):
            pass
        return FFMPEG_INSTALL_COMMANDS["Linux"]

    return FFMPEG_INSTALL_COMMANDS.get(system, FFMPEG_INSTALL_COMMANDS["Linux"])


def run_all_checks() -> dict[str, Any]:
    """Execute all dependency checks and return a structured results dict.

    Returns a flat dict suitable for display and testing::

        {
            "ffmpeg": True,
            "ytdlp": True,
            "python_ok": True,
            "python_version": "3.11",
        }

    Returns:
        Mapping of check name → result value (``bool`` or ``str``).
    """
    major, minor = check_python_version()
    python_ok = (major, minor) >= (3, 11)

    return {
        "ffmpeg": check_ffmpeg(),
        "ytdlp": check_ytdlp(),
        "python_ok": python_ok,
        "python_version": f"{major}.{minor}",
    }
