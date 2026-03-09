"""Metadata and format extraction via yt-dlp.

yt-dlp is lazily imported inside every function to avoid module-load crashes.
"""

from __future__ import annotations

from typing import Any, Literal

from ytd_wrap.constants import (
    CONTAINER_RULES,
    DEFAULT_CONTAINER,
    FORMAT_PRIORITY,
    PREFERRED_AUDIO_CODECS,
    PREFERRED_VIDEO_CODECS,
)
from ytd_wrap.utils.exceptions import ExtractionError
from ytd_wrap.utils.logger import get_logger

_log = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _codec_prefix(codec: str | None, known: list[str]) -> str:
    """Return the first matching codec identifier from *known*, or empty string.

    Args:
        codec: Raw codec string from yt-dlp (e.g. ``"avc1.42001f"``).
        known: Ordered list of codec prefixes to match against.

    Returns:
        The first matching prefix, or ``""`` if none match.
    """
    if not codec:
        return ""
    codec_lower = codec.lower()
    for k in known:
        if k in codec_lower:
            return k
    return ""


def _format_priority_score(fmt: dict[str, Any]) -> tuple[int, int, int]:
    """Return a sort key (lower = better) for a format dict.

    Scoring:
    1. Position in FORMAT_PRIORITY (0 = best, len = worst)
    2. Negative height (higher resolution = lower score = sorts first)
    3. Negative filesize (bigger file = lower score = sorts first when equal res)

    Args:
        fmt: yt-dlp format dict (normalised by :func:`_normalise`).

    Returns:
        A 3-tuple used as a sort key.
    """
    vprefix = _codec_prefix(fmt.get("vcodec"), PREFERRED_VIDEO_CODECS)
    aprefix = _codec_prefix(fmt.get("acodec"), PREFERRED_AUDIO_CODECS)

    priority_idx = len(FORMAT_PRIORITY)  # default: worst
    for idx, (vp, ap) in enumerate(FORMAT_PRIORITY):
        v_match = (vp == "" or vp == vprefix)
        a_match = (ap == "" or ap == aprefix)
        if v_match and a_match:
            priority_idx = idx
            break

    height = fmt.get("height") or 0
    filesize = fmt.get("filesize") or 0
    return (priority_idx, -height, -filesize)


def _normalise_format(raw: dict[str, Any]) -> dict[str, Any]:
    """Produce a cleaned format dict from a raw yt-dlp format entry.

    Args:
        raw: Raw format dict from yt-dlp's ``info_dict["formats"]``.

    Returns:
        Normalised dict with guaranteed keys.
    """
    width  = raw.get("width")
    height = raw.get("height")

    if height:
        resolution = f"{height}p"
    elif width and height:
        resolution = f"{width}x{height}"
    else:
        resolution = raw.get("format_note") or raw.get("format_id") or "?"

    return {
        "format_id":  raw.get("format_id", ""),
        "resolution": resolution,
        "width":      width,
        "height":     height,
        "vcodec":     raw.get("vcodec") or "",
        "acodec":     raw.get("acodec") or "",
        "filesize":   raw.get("filesize") or raw.get("filesize_approx"),
        "fps":        raw.get("fps"),
        "ext":        raw.get("ext") or "",
    }


def _is_video_format(raw: dict[str, Any]) -> bool:
    """Return True if the raw format dict represents a video (not audio-only).

    Args:
        raw: Raw yt-dlp format dict.

    Returns:
        True when the format carries a video stream.
    """
    vcodec = (raw.get("vcodec") or "").lower()
    # yt-dlp sets vcodec to "none" for audio-only formats
    if vcodec and vcodec != "none":
        return True

    # Some direct HLS manifests expose generic entries with unknown codecs
    # (vcodec/acodec missing). Treat those as video candidates when protocol
    # and extension indicate a video stream container.
    protocol = (raw.get("protocol") or "").lower()
    ext = (raw.get("ext") or "").lower()
    if "m3u8" in protocol or "dash" in protocol:
        audio_only_exts = {"m4a", "mp3", "aac", "opus", "ogg", "flac", "wav", "weba", "mka"}
        if ext and ext not in audio_only_exts:
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# New merged-format helpers
# ──────────────────────────────────────────────────────────────────────────────

def _shorten_codec(codec: str | None) -> str:
    """Return a short display name for a raw yt-dlp codec string."""
    if not codec:
        return "\u2014"
    c = codec.lower()
    if c in ("none", "unknown", ""):
        return "\u2014"
    if c.startswith("avc1") or c.startswith("h264"):
        return "h264"
    if c.startswith("hev1") or c.startswith("hvc1") or "hevc" in c:
        return "hevc"
    if c.startswith("vp09") or c.startswith("vp9"):
        return "vp9"
    if c.startswith("av01") or c.startswith("av1"):
        return "av1"
    if c.startswith("mp4a") or c == "aac":
        return "aac"
    if c == "opus":
        return "opus"
    return c.split(".")[0]


def _resolution_label(height: int | None) -> str:
    """Return a friendly resolution label for a given frame height."""
    if not height:
        return "?"
    if height >= 4320:
        return "8K / 4320p"
    if height >= 2160:
        return "4K / 2160p"
    if height >= 1440:
        return "2K / 1440p"
    if height >= 1080:
        return "FHD / 1080p"
    if height >= 720:
        return "HD / 720p"
    if height >= 480:
        return "SD / 480p"
    return f"{height}p"


def _fmt_size_local(filesize: int | None) -> str:
    """Return a human-readable file-size string (no Rich import needed)."""
    if filesize is None or filesize <= 0:
        return "~unknown"
    mb = filesize / (1024 * 1024)
    return f"{mb:.1f} MB"


def _has_audio(raw: dict[str, Any]) -> bool:
    """Return True when the format carries an audio stream."""
    acodec = (raw.get("acodec") or "").lower()
    return bool(acodec) and acodec not in ("none", "unknown")


def _codec_rank(vcodec_short: str) -> int:
    """Sort rank for video codec — lower = preferred in same-height ties."""
    return {"h264": 0, "hevc": 1, "vp9": 2, "av1": 3}.get(vcodec_short, 99)


def _best_audio_for(
    video_raw: dict[str, Any],
    audio_raws: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the best matching audio-only format for a given video format."""
    if not audio_raws:
        return None
    vcs = _shorten_codec(video_raw.get("vcodec"))

    def _score(af: dict) -> tuple:
        ac = _shorten_codec(af.get("acodec"))
        abr = af.get("abr") or af.get("tbr") or 0
        if vcs == "h264":
            pref = 0 if ac == "aac" else (1 if ac == "opus" else 2)
        else:
            pref = 0 if ac == "opus" else (1 if ac == "aac" else 2)
        return (pref, -abr)

    return min(audio_raws, key=_score)


def _build_merged_entry(
    video_raw: dict[str, Any],
    audio_raw: dict[str, Any] | None,
) -> dict[str, Any]:
    """Produce a single merged dict combining video and best-audio info."""
    height = video_raw.get("height") or 0
    vcodec_raw = video_raw.get("vcodec") or ""

    v_has_audio = _has_audio(video_raw)
    if v_has_audio:
        acodec_raw = video_raw.get("acodec") or ""
        audio_format_id: str | None = None
        audio_size = 0
    elif audio_raw is not None:
        acodec_raw = audio_raw.get("acodec") or ""
        audio_format_id = audio_raw.get("format_id") or None
        audio_size = audio_raw.get("filesize") or audio_raw.get("filesize_approx") or 0
    else:
        acodec_raw = ""
        audio_format_id = None
        audio_size = 0

    vcodec_short = _shorten_codec(vcodec_raw)
    acodec_short = _shorten_codec(acodec_raw) if acodec_raw else "\u2014"

    container: str = "mp4" if (vcodec_short == "h264" and acodec_short == "aac") else "mkv"

    video_size = video_raw.get("filesize") or video_raw.get("filesize_approx") or 0
    total = (video_size + audio_size) or None
    if total == 0:
        total = None

    resolution = _resolution_label(height)
    codec_pair = f"{vcodec_short} + {acodec_short}"

    return {
        "display_index":   0,
        "format_id":       video_raw.get("format_id", ""),
        "audio_format_id": audio_format_id,
        "resolution":      resolution,
        "height":          height,
        "vcodec_short":    vcodec_short,
        "acodec_short":    acodec_short,
        "container":       container,
        "filesize":        total,
        "filesize_str":    _fmt_size_local(total),
        "codec_pair":      codec_pair,
    }


def _dedup_formats(formats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate merged format entries by (height, vcodec_short).

    When two entries share the same resolution and video-codec family,
    prefer the one that includes audio; if equal, keep the larger filesize.
    """
    def _has_audio_in_entry(fmt: dict[str, Any]) -> bool:
        # Prefer merged entries that already have embedded audio or a selected
        # companion audio stream ID for merge.
        if fmt.get("audio_format_id"):
            return True
        acs = (fmt.get("acodec_short") or "").strip()
        return acs not in ("", "—")

    seen: dict[tuple, dict[str, Any]] = {}
    for fmt in formats:
        key = (fmt.get("height", 0), fmt.get("vcodec_short", ""))
        if key not in seen:
            seen[key] = fmt
        else:
            existing = seen[key]
            fmt_has_audio = _has_audio_in_entry(fmt)
            existing_has_audio = _has_audio_in_entry(existing)

            if fmt_has_audio and not existing_has_audio:
                seen[key] = fmt
                continue
            if fmt_has_audio == existing_has_audio:
                if (fmt.get("filesize") or 0) > (existing.get("filesize") or 0):
                    seen[key] = fmt
    return list(seen.values())


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def extract_metadata(url: str) -> dict[str, Any]:
    """Fetch video metadata without downloading the file.

    Lazily imports :mod:`yt_dlp`.

    Args:
        url: Media URL to inspect.

    Returns:
        Dict with at least: ``title``, ``uploader``, ``duration``,
        ``webpage_url``, ``thumbnail``.

    Raises:
        ExtractionError: If yt-dlp fails for any reason.
    """
    try:
        import yt_dlp  # lazy import

        ydl_opts: dict[str, Any] = {
            "quiet":        True,
            "no_warnings":  True,
            "extract_flat": False,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ExtractionError(url, "yt-dlp returned no metadata.")

        return {
            "title":       info.get("title") or "Unknown Title",
            "uploader":    info.get("uploader") or info.get("channel") or "Unknown",
            "duration":    info.get("duration"),
            "webpage_url": info.get("webpage_url") or url,
            "thumbnail":   info.get("thumbnail"),
        }

    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        _log.debug("extract_metadata failed for %r: %s", url, exc, exc_info=True)
        raise ExtractionError(url, str(exc)) from exc


def extract_formats(url: str) -> list[dict[str, Any]]:
    """Return a sorted, deduplicated list of downloadable format options.

    Each entry is a "merged" dict that pairs the best video stream with its
    best matching audio track.  ALL resolutions are included (4K, 8K etc.).
    Entries are sorted by height descending; same-height entries are ordered
    by codec preference (h264 before vp9/av1).

    Lazily imports :mod:`yt_dlp`.

    Args:
        url: Media URL to inspect.

    Returns:
        List of merged format dicts, best first.

    Raises:
        ExtractionError: If yt-dlp fails or no video formats are found.
    """
    try:
        import yt_dlp  # lazy import

        ydl_opts: dict[str, Any] = {
            "quiet":         True,
            "no_warnings":   True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ExtractionError(url, "yt-dlp returned no info.")

        raw_formats: list[dict[str, Any]] = info.get("formats") or []

        # Split into video-bearing and audio-only buckets
        video_raws = [f for f in raw_formats if _is_video_format(f)]
        audio_raws = [f for f in raw_formats if not _is_video_format(f) and _has_audio(f)]

        if not video_raws:
            raise ExtractionError(url, "No video formats found. The URL may be audio-only or unsupported.")

        # Build merged entries (one per video format)
        merged: list[dict[str, Any]] = []
        for vf in video_raws:
            best_audio = None if _has_audio(vf) else _best_audio_for(vf, audio_raws)
            merged.append(_build_merged_entry(vf, best_audio))

        # Deduplicate by (height, vcodec_short) keeping highest-bitrate entry
        merged = _dedup_formats(merged)

        # Sort: height descending, then preferred codec first at same height
        merged.sort(key=lambda x: (-x["height"], _codec_rank(x["vcodec_short"])))

        # Assign 1-based display indices
        for i, entry in enumerate(merged, 1):
            entry["display_index"] = i

        return merged

    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        _log.debug("extract_formats failed for %r: %s", url, exc, exc_info=True)
        raise ExtractionError(url, str(exc)) from exc


def select_best_format(formats: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the highest-priority format from a sorted list.

    Used for direct/unknown URLs where interactive selection is skipped.

    Args:
        formats: Non-empty priority-sorted list from :func:`extract_formats`.

    Returns:
        The first (best) format dict.

    Raises:
        ExtractionError: If *formats* is empty.
    """
    if not formats:
        raise ExtractionError("", "Cannot select best format — format list is empty.")
    return formats[0]


def determine_output_container(format_dict: dict[str, Any]) -> Literal["mp4", "mkv"]:
    """Return the appropriate output container for the given format.

    Uses :data:`~ytd_wrap.constants.CONTAINER_RULES`: mp4 only for
    h264/avc1 + aac/m4a; mkv for everything else.

    Args:
        format_dict: Normalised format dict (must have ``vcodec`` and ``acodec``).

    Returns:
        ``"mp4"`` or ``"mkv"``.
    """
    vprefix = _codec_prefix(format_dict.get("vcodec"), PREFERRED_VIDEO_CODECS)
    aprefix = _codec_prefix(format_dict.get("acodec"), PREFERRED_AUDIO_CODECS)

    # Try exact (vprefix, aprefix) match first
    result = CONTAINER_RULES.get((vprefix, aprefix))
    if result:
        return result  # type: ignore[return-value]

    # Fallback: check if any rule's video prefix matches (partial audio flexibility)
    for (vp, ap), container in CONTAINER_RULES.items():
        if vp and vprefix == vp:
            # Compatible video codec — check audio compatibility
            if ap in ("aac", "m4a", "mp4a") and aprefix in ("aac", "m4a", "mp4a"):
                return container  # type: ignore[return-value]

    return DEFAULT_CONTAINER  # type: ignore[return-value]

