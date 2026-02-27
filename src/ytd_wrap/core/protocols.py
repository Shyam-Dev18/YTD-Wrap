"""Protocols (interfaces) consumed by the core layer.

These define the contracts that infrastructure adapters must satisfy.
Core code depends ONLY on these protocols — never on concrete
implementations — preserving the dependency inversion principle.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class MetadataProvider(Protocol):
    """Contract for metadata extraction backends.

    Any object that implements :meth:`fetch_info` with the correct
    signature satisfies this protocol structurally (no explicit
    inheritance required).
    """

    def fetch_info(self, url: str) -> dict[str, Any]:
        """Fetch raw metadata for *url* and return a provider-specific dict.

        The returned dict must contain at least:

        * ``"id"`` — video identifier (``str``)
        * ``"title"`` — video title (``str``)
        * ``"webpage_url"`` — canonical page URL (``str``)
        * ``"formats"`` — list of format dicts (``list[dict]``)

        Implementations must map all backend-specific exceptions to
        :class:`~ytd_wrap.exceptions.YtdWrapError` subclasses.

        Raises
        ------
        MetadataExtractionError
            When the backend fails to extract metadata.
        VideoUnavailableError
            When the target video is confirmed unavailable.
        """
        ...  # pragma: no cover


class DownloadProvider(Protocol):
    """Contract for video download backends.

    Implementations wrap the actual download mechanics (e.g. yt-dlp)
    and must map all backend-specific exceptions to
    :class:`~ytd_wrap.exceptions.YtdWrapError` subclasses.
    """

    def download(
        self,
        url: str,
        format_spec: str,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Download *url* using *format_spec*.

        Parameters
        ----------
        url:
            The video page URL.
        format_spec:
            A yt-dlp compatible format string
            (e.g. ``"137+bestaudio/best"``).
        progress_callback:
            Optional callable invoked with progress-hook dicts
            during the download.  May be ``None``.

        Raises
        ------
        DownloadFailedError
            When the download fails for any reason.
        """
        ...  # pragma: no cover
