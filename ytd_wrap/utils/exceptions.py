"""All custom exception classes for ytd-wrap.

Hierarchy
---------
YtdWrapError (base)
├── DependencyMissingError(dependency_name)
├── UnsupportedURLError(url)
├── ExtractionError(url, reason)
├── DownloadError(url, reason)
│   ├── NetworkError(reason)
│   ├── DiskFullError(path)
│   └── PermissionError(path)
├── FormatSelectionError(reason)
└── UserCancelledError
"""


class YtdWrapError(Exception):
    """Base exception for all ytd-wrap errors."""


class DependencyMissingError(YtdWrapError):
    """Raised when a required system or Python dependency is not available.

    Attributes:
        dependency_name: The name of the missing dependency (e.g. ``"ffmpeg"``).
    """

    def __init__(self, dependency_name: str) -> None:
        self.dependency_name = dependency_name
        super().__init__(f"Required dependency not found: {dependency_name!r}")


class UnsupportedURLError(YtdWrapError):
    """Raised when the provided URL cannot be parsed or is not supported.

    Attributes:
        url: The URL that triggered the error.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        super().__init__(f"Unsupported or invalid URL: {url!r}")


class ExtractionError(YtdWrapError):
    """Raised when yt-dlp fails to extract metadata or formats.

    Attributes:
        url: The URL being processed.
        reason: Human-readable explanation of the failure.
    """

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Extraction failed for {url!r}: {reason}")


class DownloadError(YtdWrapError):
    """Raised when a download fails for any reason.

    Attributes:
        url: The URL being downloaded.
        reason: Human-readable explanation of the failure.
    """

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        self.reason = reason
        super().__init__(f"Download failed for {url!r}: {reason}")


class NetworkError(DownloadError):
    """Raised on network timeouts, DNS failures, or unreachable hosts.

    Attributes:
        reason: Human-readable description of the network problem.
    """

    def __init__(self, reason: str) -> None:
        self.url = ""
        self.reason = reason
        YtdWrapError.__init__(self, f"Network error: {reason}")


class DiskFullError(DownloadError):
    """Raised when the destination filesystem reports no space left.

    Attributes:
        path: The filesystem path that ran out of space.
    """

    def __init__(self, path: str) -> None:
        self.url = ""
        self.path = path
        self.reason = f"No space left on device at {path!r}"
        YtdWrapError.__init__(self, self.reason)


class PermissionError(DownloadError):
    """Raised when the process cannot write to the destination path.

    Attributes:
        path: The path where the write was denied.
    """

    def __init__(self, path: str) -> None:
        self.url = ""
        self.path = path
        self.reason = f"Permission denied: {path!r}"
        YtdWrapError.__init__(self, self.reason)


class FormatSelectionError(YtdWrapError):
    """Raised when no suitable format is available or selection is aborted.

    Attributes:
        reason: Human-readable explanation.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Format selection error: {reason}")


class UserCancelledError(YtdWrapError):
    """Raised when the user interrupts an interactive prompt (Ctrl+C)."""

    def __init__(self) -> None:
        super().__init__("Operation cancelled by user.")


class GeoBlockedError(ExtractionError):
    """Raised when content is unavailable in the user's region."""
