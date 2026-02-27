"""Core download service — orchestrates the download pipeline.

This service delegates the actual download to a
:class:`~ytd_wrap.core.protocols.DownloadProvider` injected at
construction time.  It is responsible for:

* Building the yt-dlp–compatible format string.
* Delegating to the provider.
* Ensuring only :class:`~ytd_wrap.exceptions.YtdWrapError` subclasses
  escape.

Guarantees
----------
* Pure orchestration — no I/O, no ``print()``, no filesystem access.
* No yt-dlp import.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ytd_wrap.core.protocols import DownloadProvider
from ytd_wrap.exceptions import DownloadFailedError, YtdWrapError


class DownloadService:
    """Stateless service that drives the download pipeline.

    Parameters
    ----------
    provider:
        Any object satisfying the :class:`DownloadProvider` protocol.
    """

    def __init__(self, provider: DownloadProvider) -> None:
        self._provider: DownloadProvider = provider

    # ------------------------------------------------------------------
    # Format string construction (pure)
    # ------------------------------------------------------------------

    @staticmethod
    def build_format_spec(video_format_id: str, video_ext: str) -> str:
        """Build the yt-dlp format string for selected video stream metadata.

        Rules
        -----
        * ``mp4`` video prefers ``m4a`` audio, with mp4 fallback.
        * ``webm`` video prefers ``webm`` audio, with webm/best fallback.
        * Unknown containers fall back to generic ``bestaudio/best``.
        """
        normalized_ext = video_ext.lower()
        if normalized_ext == "mp4":
            return f"{video_format_id}+bestaudio[ext=m4a]/best[ext=mp4]"
        if normalized_ext == "webm":
            return f"{video_format_id}+bestaudio[ext=webm]/best[ext=webm]/best"
        return f"{video_format_id}+bestaudio/best"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(
        self,
        url: str,
        video_format_id: str,
        video_ext: str,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Download a single video.

        Parameters
        ----------
        url:
            The video page URL.
        video_format_id:
            The ``format_id`` of the selected video-only format.
        video_ext:
            The container extension of the selected video-only format.
        progress_callback:
            Optional callable forwarded to the provider for progress
            reporting.

        Raises
        ------
        DownloadFailedError
            When the download fails for any reason.
        """
        format_spec = self.build_format_spec(video_format_id, video_ext)
        try:
            self._provider.download(
                url,
                format_spec,
                progress_callback=progress_callback,
            )
        except YtdWrapError:
            # Already one of ours — propagate unchanged.
            raise
        except Exception as exc:
            raise DownloadFailedError(
                f"Unexpected download error: {exc}",
            ) from exc
