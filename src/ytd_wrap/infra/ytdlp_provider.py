"""yt-dlp backed implementation of :class:`~ytd_wrap.core.protocols.MetadataProvider`.

This module is the **only** place in the codebase that imports ``yt_dlp``.
All yt-dlp exceptions are caught here and re-raised as typed
:class:`~ytd_wrap.exceptions.YtdWrapError` subclasses — nothing raw
escapes the infrastructure boundary.
"""

from __future__ import annotations

from typing import Any

from ytd_wrap.exceptions import EnvironmentError, MetadataExtractionError, VideoUnavailableError


class YtDlpMetadataProvider:
    """Concrete :class:`MetadataProvider` backed by the yt-dlp Python API.

    Usage::

        provider = YtDlpMetadataProvider()
        info = provider.fetch_info("https://www.youtube.com/watch?v=...")

    This class satisfies the :class:`~ytd_wrap.core.protocols.MetadataProvider`
    protocol structurally — no explicit inheritance required.
    """

    # Substrings in yt-dlp error messages that indicate the video itself
    # is unavailable (as opposed to a transient or extraction error).
    _UNAVAILABLE_SIGNALS: tuple[str, ...] = (
        "unavailable",
        "private video",
        "removed",
        "not available",
        "account terminated",
        "video has been removed",
        "this video is no longer available",
        "sign in to confirm your age",
    )

    @staticmethod
    def _build_opts() -> dict[str, Any]:
        """Return yt-dlp options suitable for metadata-only extraction."""
        return {
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            # Do not write any files to disk.
            "skip_download": True,
        }

    # ------------------------------------------------------------------
    # Protocol method
    # ------------------------------------------------------------------

    def fetch_info(self, url: str) -> dict[str, Any]:
        """Extract metadata for *url* without downloading.

        Returns
        -------
        dict[str, Any]
            The raw info dict produced by ``yt_dlp.YoutubeDL.extract_info``.

        Raises
        ------
        VideoUnavailableError
            When yt-dlp reports the video as unavailable / private / removed.
        MetadataExtractionError
            For all other extraction failures.
        """
        opts = self._build_opts()

        try:
            import yt_dlp
            import yt_dlp.utils
        except ModuleNotFoundError as exc:
            raise EnvironmentError(
                "yt-dlp is not installed. Install with: pip install yt-dlp",
            ) from exc

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info: Any = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            self._raise_mapped(exc)
        except Exception as exc:
            raise MetadataExtractionError(
                f"Unexpected yt-dlp error: {exc}",
            ) from exc

        if info is None:
            raise MetadataExtractionError(
                "yt-dlp returned no metadata for the given URL.",
                hint="The URL may not point to a valid video.",
            )

        if not isinstance(info, dict):
            raise MetadataExtractionError(
                "yt-dlp returned an unexpected data structure.",
            )

        return dict(info)  # shallow copy — isolate from yt-dlp internals

    # ------------------------------------------------------------------
    # Exception mapping
    # ------------------------------------------------------------------

    @classmethod
    def _raise_mapped(cls, exc: Exception) -> None:
        """Translate a yt-dlp ``DownloadError`` into a domain exception.

        Always raises — the ``Never`` return type is implicit via
        ``raise`` at every exit path.
        """
        msg_lower = str(exc).lower()
        if any(signal in msg_lower for signal in cls._UNAVAILABLE_SIGNALS):
            raise VideoUnavailableError(
                str(exc),
                hint="The video may be private, removed, or geo-restricted.",
            ) from exc
        raise MetadataExtractionError(str(exc)) from exc
