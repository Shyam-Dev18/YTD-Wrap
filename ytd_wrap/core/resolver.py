"""URL type detection — distinguishes social media URLs from direct/m3u8 streams."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from ytd_wrap.constants import (
    DIRECT_STREAM_EXTENSIONS,
    DIRECT_STREAM_PATTERNS,
    SOCIAL_MEDIA_DOMAINS,
)


def is_valid_url(url: str) -> bool:
    """Return True if *url* has an http/https scheme and a non-empty netloc.

    Uses :mod:`urllib.parse` only — no network calls.

    Args:
        url: Raw URL string provided by the user.

    Returns:
        True if the URL is structurally valid for downloading.
    """
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:  # noqa: BLE001
        return False


def is_direct_stream(url: str) -> bool:
    """Return True if the URL appears to be a direct video/stream file.

    Checks file extension and known CDN/stream URL patterns.
    Heuristic — does not make a network request.

    Args:
        url: URL to classify.

    Returns:
        True if the URL likely points directly to a media file or HLS stream.
    """
    try:
        parsed = urlparse(url.lower())
    except Exception:  # noqa: BLE001
        return False

    # Check file extension on the path component (strip query string)
    path = parsed.path
    for ext in DIRECT_STREAM_EXTENSIONS:
        if path.endswith(ext):
            return True

    # Check pattern substrings across the full URL
    full = url.lower()
    return any(pattern in full for pattern in DIRECT_STREAM_PATTERNS)


def is_social_media(url: str) -> bool:
    """Return True if the URL's domain matches a known social media platform.

    Performs suffix/substring matching against :data:`~ytd_wrap.constants.SOCIAL_MEDIA_DOMAINS`.

    Args:
        url: URL to classify.

    Returns:
        True if the domain is a recognised social media or video platform.
    """
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001
        return False

    # Strip leading "www." for clean matching
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Exact match first, then suffix match (handles subdomains like "m.youtube.com")
    if netloc in SOCIAL_MEDIA_DOMAINS:
        return True
    return any(netloc.endswith("." + domain) or netloc == domain for domain in SOCIAL_MEDIA_DOMAINS)


def detect_url_type(url: str) -> Literal["social", "direct", "unknown"]:
    """Classify a URL as ``"social"``, ``"direct"``, or ``"unknown"``.

    Classification order:
    1. ``"social"`` — domain is a known social media platform
    2. ``"direct"`` — URL has a direct-stream extension or CDN pattern
    3. ``"unknown"`` — neither; still attempted as a download

    Args:
        url: URL to classify.

    Returns:
        One of ``"social"``, ``"direct"``, or ``"unknown"``.
    """
    if is_social_media(url):
        return "social"
    if is_direct_stream(url):
        return "direct"
    return "unknown"

