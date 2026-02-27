"""Infrastructure layer — external system integration.

This layer wraps all interaction with yt-dlp, the operating system,
and ffmpeg.  Every raw third-party exception must be caught here and
re-raised as a :class:`~ytd_wrap.exceptions.YtdWrapError` subclass.

Rules
-----
* No imports from ``cli``.
* No user-facing output (no ``print()``, no Rich rendering).
* Must expose clean, typed interfaces consumed by the core layer.
"""

from ytd_wrap.infra.ffmpeg_detector import FfmpegStatus, detect_ffmpeg, require_ffmpeg
from ytd_wrap.infra.ytdlp_download_provider import YtDlpDownloadProvider
from ytd_wrap.infra.ytdlp_provider import YtDlpMetadataProvider

__all__: list[str] = [
    "FfmpegStatus",
    "YtDlpDownloadProvider",
    "YtDlpMetadataProvider",
    "detect_ffmpeg",
    "require_ffmpeg",
]
