"""PyPI version checks for ytd-wrap and yt-dlp — once-per-day, non-blocking."""

from __future__ import annotations

import json
import time
from typing import Any

from ytd_wrap import __version__ as _SELF_VERSION
from ytd_wrap.constants import (
    CACHE_FILE,
    REQUESTS_TIMEOUT,
    VERSION_CHECK_INTERVAL_SECONDS,
    YTDLP_PYPI_URL,
    YTDWRAP_PYPI_URL,
)
from ytd_wrap.utils.logger import get_logger
from ytd_wrap.utils.paths import ensure_app_dirs

_log = get_logger(__name__)

# The two packages we monitor.
_PACKAGES_TO_CHECK = [
    ("ytd-wrap", YTDWRAP_PYPI_URL, _SELF_VERSION),
    ("yt-dlp",   YTDLP_PYPI_URL,   None),          # current version resolved at runtime
]


def _read_cache() -> dict[str, Any]:
    """Read the cache JSON file safely.

    Returns:
        Parsed cache dict, or an empty dict if the file is missing or corrupt.
    """
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.debug("Could not read cache file %s: %s", CACHE_FILE, exc)
    return {}


def _write_cache(data: dict[str, Any]) -> None:
    """Write *data* to the cache JSON file.

    Creates parent directories if necessary.  Silently ignores write errors.

    Args:
        data: Dict to serialise and persist.
    """
    try:
        ensure_app_dirs()
        CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        _log.debug("Could not write cache file %s: %s", CACHE_FILE, exc)


def _fetch_pypi_version(package_name: str) -> str | None:
    """Query the PyPI JSON API for the latest released version of *package_name*.

    Args:
        package_name: The PyPI package name (e.g. ``"yt-dlp"``).

    Returns:
        Version string such as ``"2024.3.10"``, or ``None`` on any error.
    """
    url = YTDLP_PYPI_URL if package_name == "yt-dlp" else YTDWRAP_PYPI_URL
    try:
        import requests  # lazy import

        resp = requests.get(url, timeout=REQUESTS_TIMEOUT)
        resp.raise_for_status()
        return resp.json()["info"]["version"]
    except Exception as exc:  # noqa: BLE001
        _log.debug("PyPI version check failed for %r: %s", package_name, exc)
        return None


def _is_check_due(cache: dict[str, Any]) -> bool:
    """Return ``True`` if enough time has elapsed since the last check.

    Args:
        cache: The currently loaded cache dict.

    Returns:
        ``True`` if the check should run, ``False`` if it ran recently.
    """
    last_checked = cache.get("last_checked")
    if last_checked is None:
        return True
    return (time.time() - float(last_checked)) >= VERSION_CHECK_INTERVAL_SECONDS


def _write_cache_timestamp() -> None:
    """Persist the current UTC epoch timestamp into the cache file."""
    cache = _read_cache()
    cache["last_checked"] = time.time()
    _write_cache(cache)


def _get_ytdlp_installed_version() -> str | None:
    """Return the installed yt-dlp version string, or None if not importable.

    Returns:
        Version string or ``None``.
    """
    try:
        import importlib.metadata
        return importlib.metadata.version("yt-dlp")
    except Exception:  # noqa: BLE001
        return None


def check_for_updates() -> list[dict[str, str]]:
    """Check PyPI for newer versions of ytd-wrap and yt-dlp.

    Only runs if the last check was more than
    :data:`~ytd_wrap.constants.VERSION_CHECK_INTERVAL_SECONDS` ago.
    Updates the cache timestamp after a successful check.
    Never raises — all errors are logged at DEBUG level.

    Returns:
        List of dicts for each outdated package::

            [{"package": "yt-dlp", "current": "2024.1.0", "latest": "2024.3.10"}]

        Empty list if everything is up-to-date or the check was skipped.
    """
    try:
        cache = _read_cache()
        if not _is_check_due(cache):
            _log.debug("Version check skipped — checked recently.")
            return []

        outdated: list[dict[str, str]] = []

        for package_name, _url, builtin_current in _PACKAGES_TO_CHECK:
            if package_name == "yt-dlp":
                current = _get_ytdlp_installed_version()
            else:
                current = builtin_current  # type: ignore[assignment]

            if current is None:
                continue  # can't compare if not installed

            latest = _fetch_pypi_version(package_name)
            if latest is None:
                continue  # network/API error — skip silently

            if _version_is_newer(latest, current):
                outdated.append(
                    {"package": package_name, "current": current, "latest": latest}
                )

        _write_cache_timestamp()
        return outdated

    except Exception as exc:  # noqa: BLE001
        _log.debug("Unexpected error during update check: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _version_is_newer(candidate: str, current: str) -> bool:
    """Return True if *candidate* is strictly newer than *current*.

    Compares using :func:`packaging.version.Version` when available, with a
    simple lexicographic fallback.

    Args:
        candidate: The version to test (e.g. latest from PyPI).
        current: The installed version.

    Returns:
        ``True`` if candidate > current.
    """
    try:
        from packaging.version import Version  # available via pip deps
        return Version(candidate) > Version(current)
    except Exception:  # noqa: BLE001
        # Plain string comparison as last resort (works for date-based versions)
        return candidate > current
