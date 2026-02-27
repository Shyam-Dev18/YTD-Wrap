"""yt-dlp backed implementation of :class:`~ytd_wrap.core.protocols.DownloadProvider`.

This module is the **only** place in the codebase that invokes the
yt-dlp download machinery.  All yt-dlp exceptions are caught here and
re-raised as :class:`~ytd_wrap.exceptions.DownloadFailedError`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ytd_wrap.exceptions import DownloadFailedError, EnvironmentError


class YtDlpDownloadProvider:
    """Concrete :class:`DownloadProvider` backed by the yt-dlp Python API.

    This class satisfies the :class:`~ytd_wrap.core.protocols.DownloadProvider`
    protocol structurally — no explicit inheritance required.
    """

    @staticmethod
    def _build_opts(
        format_spec: str,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Return yt-dlp options for downloading with *format_spec*.

        The output template ``%(title)s.%(ext)s`` writes into the
        current working directory — no path injection, no PATH
        modification.
        """
        hooks: list[Callable[[dict[str, Any]], None]] = []
        if progress_callback is not None:
            hooks.append(progress_callback)

        return {
            "format": format_spec,
            "outtmpl": "%(title)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "progress_hooks": hooks,
            # Merge to mp4 when ffmpeg is available; graceful fallback
            # when it is not.
            "merge_output_format": "mp4",
        }

    # ------------------------------------------------------------------
    # Protocol method
    # ------------------------------------------------------------------

    def download(
        self,
        url: str,
        format_spec: str,
        *,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Download *url* using *format_spec*.

        Raises
        ------
        DownloadFailedError
            For any yt-dlp error during the download.
        """
        opts = self._build_opts(format_spec, progress_callback=progress_callback)

        try:
            import yt_dlp
            import yt_dlp.utils
        except ModuleNotFoundError as exc:
            raise EnvironmentError(
                "yt-dlp is not installed. Install with: pip install yt-dlp",
            ) from exc

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadFailedError(
                str(exc),
                hint="Check the URL, your network, or try a different format.",
            ) from exc
        except Exception as exc:
            raise DownloadFailedError(
                f"Unexpected yt-dlp download error: {exc}",
            ) from exc
