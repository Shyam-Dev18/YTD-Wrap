"""Pure format filtering, deduplication, and sorting logic.

Every function in this module is a **pure** transformation — no I/O,
no side effects, fully deterministic, and trivially unit-testable.

Pipeline order (enforced by :func:`select_adaptive_formats`):

1. **Filter** — keep only video-only adaptive streams.
2. **Deduplicate** — collapse identical ``(height, fps, ext)`` tuples.
3. **Sort** — resolution desc → fps desc → mp4 preferred.
"""

from __future__ import annotations

from collections.abc import Sequence

from ytd_wrap.core.models import VideoFormat


# ---------------------------------------------------------------------------
# 1. Filter
# ---------------------------------------------------------------------------

def filter_adaptive_video_only(
    formats: Sequence[VideoFormat],
) -> list[VideoFormat]:
    """Return only video-only adaptive formats.

    A format qualifies when it carries a video codec (``vcodec != "none"``)
    **and** has no audio track (``acodec == "none"``).
    """
    return [
        fmt
        for fmt in formats
        if fmt.vcodec != "none" and fmt.acodec == "none"
    ]


# ---------------------------------------------------------------------------
# 2. Deduplicate
# ---------------------------------------------------------------------------

def deduplicate_formats(
    formats: Sequence[VideoFormat],
) -> list[VideoFormat]:
    """Remove duplicates keyed by ``(height, fps, ext)``.

    When multiple formats share the same key, the **first** occurrence
    wins.  Callers should sort or pre-filter to control which entry is
    retained.
    """
    seen: set[tuple[int | None, int | None, str]] = set()
    result: list[VideoFormat] = []
    for fmt in formats:
        key = (fmt.height, fmt.fps, fmt.ext)
        if key not in seen:
            seen.add(key)
            result.append(fmt)
    return result


# ---------------------------------------------------------------------------
# 3. Sort
# ---------------------------------------------------------------------------

def _sort_key(fmt: VideoFormat) -> tuple[int, int, int]:
    """Compute a sort key that orders formats for user presentation.

    Ordering rules (all ascending on the returned tuple):
    * Higher resolution first  → negate height
    * Higher fps first          → negate fps
    * mp4 before other exts     → 0 for mp4, 1 otherwise
    """
    height: int = fmt.height if fmt.height is not None else 0
    fps: int = fmt.fps if fmt.fps is not None else 0
    ext_priority: int = 0 if fmt.ext == "mp4" else 1
    return (-height, -fps, ext_priority)


def sort_formats(formats: Sequence[VideoFormat]) -> list[VideoFormat]:
    """Sort formats by resolution desc, fps desc, mp4 preferred."""
    return sorted(formats, key=_sort_key)


# ---------------------------------------------------------------------------
# Composite pipeline
# ---------------------------------------------------------------------------

def select_adaptive_formats(
    formats: Sequence[VideoFormat],
) -> list[VideoFormat]:
    """Run the full filter → deduplicate → sort pipeline.

    Returns an empty list when no qualifying formats remain.
    """
    filtered = filter_adaptive_video_only(formats)
    deduped = deduplicate_formats(filtered)
    return sort_formats(deduped)
