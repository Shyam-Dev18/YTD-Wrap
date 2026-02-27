"""Core metadata service — orchestrates extraction and format selection.

This is the central service class consumed by the CLI layer.  It
depends on a :class:`~ytd_wrap.core.protocols.MetadataProvider` injected
at construction time (dependency inversion), keeping the core free of
any external-system imports.

Guarantees
----------
* Pure orchestration — no I/O, no ``print()``, no filesystem access.
* Only :class:`~ytd_wrap.exceptions.YtdWrapError` subclasses escape.
* All parsing logic is deterministic and stateless.
"""

from __future__ import annotations

from typing import Any

from ytd_wrap.core.format_filter import select_adaptive_formats
from ytd_wrap.core.models import FormatCollection, VideoFormat, VideoMetadata
from ytd_wrap.core.protocols import MetadataProvider
from ytd_wrap.exceptions import (
    FormatSelectionError,
    InvalidURLError,
    MetadataExtractionError,
    YtdWrapError,
    append_ytdlp_upgrade_suggestion,
)


class MetadataService:
    """Stateless service that extracts metadata and selects formats.

    Parameters
    ----------
    provider:
        Any object satisfying the :class:`MetadataProvider` protocol.
    """

    def __init__(self, provider: MetadataProvider) -> None:
        self._provider: MetadataProvider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_metadata(self, url: str) -> VideoMetadata:
        """Extract top-level metadata for a single video.

        Raises
        ------
        InvalidURLError
            If *url* is empty or malformed.
        MetadataExtractionError
            If the backend fails to return metadata.
        VideoUnavailableError
            If the video is confirmed unavailable.
        """
        self._validate_url(url)
        info = self._fetch(url)
        return self._parse_metadata(info)

    def get_adaptive_video_formats(self, url: str) -> FormatCollection:
        """Extract and filter adaptive video-only formats for *url*.

        Raises
        ------
        InvalidURLError
            If *url* is empty or malformed.
        MetadataExtractionError
            If the backend fails to return metadata.
        VideoUnavailableError
            If the video is confirmed unavailable.
        FormatSelectionError
            If no adaptive video formats survive filtering.
        """
        self._validate_url(url)
        info = self._fetch(url)
        raw_formats = self._extract_raw_formats(info)
        parsed = self._parse_formats(raw_formats)
        selected = select_adaptive_formats(parsed)

        if not selected:
            raise FormatSelectionError(
                "No adaptive video formats found for this video.",
                hint=append_ytdlp_upgrade_suggestion(
                    "The video may only provide muxed formats.",
                ),
            )

        return FormatCollection(formats=tuple(selected))

    # ------------------------------------------------------------------
    # URL validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_url(url: str) -> None:
        """Raise :class:`InvalidURLError` for empty or non-HTTP URLs."""
        stripped = url.strip()
        if not stripped:
            raise InvalidURLError("URL must not be empty.")
        if not stripped.startswith(("http://", "https://")):
            raise InvalidURLError(
                f"Invalid URL: {stripped}",
                hint="URL must start with http:// or https://",
            )

    # ------------------------------------------------------------------
    # Provider delegation (safe boundary)
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> dict[str, Any]:
        """Call the provider and ensure only our exceptions escape."""
        try:
            return self._provider.fetch_info(url)
        except YtdWrapError:
            # Already one of ours — let it propagate unchanged.
            raise
        except Exception as exc:
            raise MetadataExtractionError(
                f"Unexpected provider error: {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # Raw-dict → domain-model parsers (pure)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_metadata(info: dict[str, Any]) -> VideoMetadata:
        """Convert a raw info dict into a :class:`VideoMetadata`."""
        raw_duration = info.get("duration")
        duration: int | None = (
            int(raw_duration) if raw_duration is not None else None
        )
        return VideoMetadata(
            id=str(info.get("id", "")),
            title=str(info.get("title", "Unknown")),
            duration=duration,
            webpage_url=str(info.get("webpage_url", "")),
        )

    @staticmethod
    def _extract_raw_formats(info: dict[str, Any]) -> list[dict[str, Any]]:
        """Safely pull the ``formats`` list from a raw info dict."""
        raw: object = info.get("formats")
        if not isinstance(raw, list):
            return []
        # Each element is expected to be a dict; skip malformed entries.
        return [entry for entry in raw if isinstance(entry, dict)]

    @staticmethod
    def _parse_single_format(raw: dict[str, Any]) -> VideoFormat:
        """Convert one raw format dict to a :class:`VideoFormat`."""
        raw_fps = raw.get("fps")
        fps: int | None = round(raw_fps) if raw_fps is not None else None

        raw_size = raw.get("filesize")
        if raw_size is None:
            raw_size = raw.get("filesize_approx")
        filesize: int | None = int(raw_size) if raw_size is not None else None

        return VideoFormat(
            format_id=str(raw.get("format_id", "")),
            ext=str(raw.get("ext", "")),
            height=raw.get("height") if isinstance(raw.get("height"), int) else None,
            fps=fps,
            filesize=filesize,
            vcodec=str(raw.get("vcodec") or "none"),
            acodec=str(raw.get("acodec") or "none"),
        )

    @classmethod
    def _parse_formats(
        cls,
        raw_formats: list[dict[str, Any]],
    ) -> list[VideoFormat]:
        """Convert a list of raw format dicts to domain models."""
        return [cls._parse_single_format(entry) for entry in raw_formats]
