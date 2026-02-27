"""Custom exception hierarchy for ytd-wrap.

All exceptions that cross layer boundaries must inherit from
:class:`YtdWrapError`.  Raw third-party exceptions (e.g. from yt-dlp)
must NEVER propagate beyond the infrastructure layer — they must be
caught and re-raised as a typed subclass defined here.

Hierarchy
---------
YtdWrapError
├── InvalidURLError
├── MetadataExtractionError
├── VideoUnavailableError
├── FormatSelectionError
├── DownloadFailedError
├── FfmpegNotFoundError
└── EnvironmentCheckError
"""

from __future__ import annotations


class YtdWrapError(Exception):
    """Base exception for all ytd-wrap errors.

    Every user-visible error condition must map to a subclass of this
    exception so that the CLI error boundary can render a clean message
    without leaking internal stack traces.
    """

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint: str | None = hint
        """Optional actionable guidance shown below the error message."""


# --- URL validation --------------------------------------------------------

class InvalidURLError(YtdWrapError):
    """Raised when the provided URL fails validation."""


# --- Metadata / extraction -------------------------------------------------

class MetadataExtractionError(YtdWrapError):
    """Raised when yt-dlp fails to extract video metadata."""


class VideoUnavailableError(YtdWrapError):
    """Raised when the target video is unavailable (private, removed, etc.)."""


# --- Format handling -------------------------------------------------------

class FormatSelectionError(YtdWrapError):
    """Raised when no suitable format can be determined."""


# --- Download --------------------------------------------------------------

class DownloadFailedError(YtdWrapError):
    """Raised when the download process terminates with an error."""


# --- Environment / tooling -------------------------------------------------

class EnvironmentError(YtdWrapError):
    """Raised when a required runtime dependency is not available."""


class FfmpegNotFoundError(YtdWrapError):
    """Raised when ffmpeg cannot be located on the system PATH."""


class EnvironmentCheckError(EnvironmentError):
    """Raised when a required environment precondition is not met."""


def append_ytdlp_upgrade_suggestion(hint: str) -> str:
    """Append yt-dlp upgrade guidance to an existing hint text.

    The suggestion is appended only once and preserves the original
    hint content verbatim.
    """
    marker = "Also try updating yt-dlp:"
    if marker in hint:
        return hint
    return "\n".join(
        (
            hint,
            marker,
            "    pip install --upgrade yt-dlp",
        )
    )
