"""Domain models for ytd-wrap.

All models are **frozen** dataclasses — immutable value objects with no
behaviour beyond data access.  They carry zero I/O, zero dependencies on
external packages, and must remain pure across the entire lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Video metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Top-level metadata for a single YouTube video."""

    id: str
    """YouTube video ID (e.g. ``dQw4w9WgXcQ``)."""

    title: str
    """Human-readable video title."""

    duration: int | None
    """Duration in seconds, or ``None`` if unavailable."""

    webpage_url: str
    """Canonical URL of the video page."""


# ---------------------------------------------------------------------------
# Individual format descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class VideoFormat:
    """A single media format reported by the extraction backend.

    This represents one adaptive stream — typically video-only or
    audio-only — as opposed to a muxed container.
    """

    format_id: str
    """Backend-specific identifier for this format."""

    ext: str
    """Container extension (e.g. ``mp4``, ``webm``)."""

    height: int | None
    """Vertical resolution in pixels, or ``None`` if unknown."""

    fps: int | None
    """Frames per second, or ``None`` if unknown."""

    filesize: int | None
    """File size in bytes, or ``None`` if unknown."""

    vcodec: str
    """Video codec name.  ``"none"`` when the stream has no video."""

    acodec: str
    """Audio codec name.  ``"none"`` when the stream has no audio."""


# ---------------------------------------------------------------------------
# Typed collection wrapper
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FormatCollection:
    """Immutable, ordered collection of :class:`VideoFormat` entries.

    The tuple guarantees immutability.  Convenience dunder methods make
    the collection usable in boolean and length contexts.
    """

    formats: tuple[VideoFormat, ...]

    def __len__(self) -> int:
        return len(self.formats)

    def __bool__(self) -> bool:
        return len(self.formats) > 0
