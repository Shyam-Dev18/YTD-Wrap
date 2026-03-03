"""All application-wide constants, magic values, and configuration rules for ytd-wrap."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Application identity & directory layout
# ---------------------------------------------------------------------------

APP_NAME: str = "ytd-wrap"
APP_DIR: Path = Path.home() / ".ytd-wrap"
LOG_DIR: Path = APP_DIR / "logs"
CACHE_FILE: Path = APP_DIR / "cache.json"

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_DOWNLOAD_DIR: Path = Path.home() / "Downloads"

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOG_FILENAME: str = "ytd-wrap.log"
MAX_LOG_BYTES: int = 2 * 1024 * 1024  # 2 MB per rotating file
LOG_BACKUP_COUNT: int = 5             # keep 5 rotated files

# ---------------------------------------------------------------------------
# Version check
# ---------------------------------------------------------------------------

VERSION_CHECK_INTERVAL_SECONDS: int = 43_200  # 12 hours

YTDLP_PYPI_URL: str = "https://pypi.org/pypi/yt-dlp/json"
YTDWRAP_PYPI_URL: str = "https://pypi.org/pypi/ytd-wrap/json"

# ---------------------------------------------------------------------------
# Codec & container rules
# ---------------------------------------------------------------------------

# Ordered list of (video_codec_prefix, audio_codec_prefix) preference tuples.
# First match wins during format selection.
#
# yt-dlp reports H.264 as "avc1.xxx" (prefix → "avc1") and AAC as "mp4a.40.x"
# (prefix → "mp4a"), so both "h264"/"avc1" and "aac"/"mp4a"/"m4a" variants
# must be listed to ensure the priority score fires correctly.
FORMAT_PRIORITY: list[tuple[str, str]] = [
    # H.264 + AAC/M4A — best device compatibility (mp4-safe)
    ("h264", "aac"),
    ("h264", "mp4a"),
    ("h264", "m4a"),
    ("avc1", "aac"),
    ("avc1", "mp4a"),  # most common yt-dlp H.264 output
    ("avc1", "m4a"),
    # H.264 with any audio
    ("h264", ""),
    ("avc1", ""),
    # VP9 + Opus
    ("vp9",  "opus"),
    ("vp09", "opus"),  # yt-dlp uses "vp09" internally
    # AV1 + Opus
    ("av1",  "opus"),
    ("av01", "opus"),  # yt-dlp uses "av01" internally
    # Absolute fallback
    ("", ""),
]

# Preferred video/audio codec identifiers (substrings matched against yt-dlp codec strings)
PREFERRED_VIDEO_CODECS: list[str] = ["h264", "avc1", "vp9", "vp09", "av01", "av1"]
PREFERRED_AUDIO_CODECS: list[str] = ["aac", "mp4a", "m4a", "opus", "vorbis", "mp3"]

# Maps (video_codec_prefix, audio_codec_prefix) → output container extension.
# Rule: mp4 ONLY for h264/avc1 + aac/mp4a/m4a; mkv for everything else.
CONTAINER_RULES: dict[tuple[str, str], str] = {
    ("h264", "aac"):  "mp4",
    ("h264", "mp4a"): "mp4",
    ("h264", "m4a"):  "mp4",
    ("avc1", "aac"):  "mp4",
    ("avc1", "mp4a"): "mp4",
    ("avc1", "m4a"):  "mp4",
}
DEFAULT_CONTAINER: str = "mkv"   # fallback when no CONTAINER_RULES match

# ---------------------------------------------------------------------------
# Supported output containers
# ---------------------------------------------------------------------------

SUPPORTED_CONTAINERS: list[str] = ["mp4", "mkv"]

# ---------------------------------------------------------------------------
# ffmpeg install instructions keyed by platform.system() return value
# ---------------------------------------------------------------------------

FFMPEG_INSTALL_COMMANDS: dict[str, str] = {
    "Darwin":  "brew install ffmpeg",
    "Windows": "winget install --id Gyan.FFmpeg  (or download from https://ffmpeg.org/download.html)",
    "Ubuntu":  "sudo apt install ffmpeg",
    "Debian":  "sudo apt install ffmpeg",
    "Linux":   "sudo dnf install ffmpeg  (or refer to https://ffmpeg.org/download.html)",
}

FFMPEG_DOWNLOAD_URL: str = "https://ffmpeg.org/download.html"

# ---------------------------------------------------------------------------
# Human-readable HTTP error messages
# ---------------------------------------------------------------------------

HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "Bad request — the server could not understand the URL.",
    401: "Authentication required — this content requires a login.",
    403: "Access denied (HTTP 403) — the platform is blocking this request.",
    404: "Not found (HTTP 404) — the video no longer exists or the URL is wrong.",
    410: "Gone (HTTP 410) — this video has been permanently removed.",
    429: "Rate limited (HTTP 429) — too many requests. Please wait a moment and retry.",
    500: "Server error (HTTP 500) — the platform is having issues. Try again later.",
    503: "Service unavailable (HTTP 503) — the platform is temporarily down.",
}

# ---------------------------------------------------------------------------
# yt-dlp download options (defaults — overridden in downloader.py as needed)
# ---------------------------------------------------------------------------

YTDLP_SOCKET_TIMEOUT: int = 30       # seconds
YTDLP_RETRIES: int = 10
YTDLP_FRAGMENT_RETRIES: int = 10
YTDLP_CONTINUEDL: bool = True        # always auto-resume

# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

# Domain suffixes/substrings that identify social media platforms.
# Matched via substring against the URL's netloc (lowercased).
SOCIAL_MEDIA_DOMAINS: frozenset[str] = frozenset({
    # Video platforms
    "youtube.com", "youtu.be",
    "vimeo.com",
    "dailymotion.com",
    "twitch.tv",
    "bilibili.com",
    "rumble.com",
    "odysee.com",
    "lbry.tv",
    "nicovideo.jp",
    "tiktok.com",
    "vm.tiktok.com",
    "streamable.com",
    "ted.com",
    "mixcloud.com",
    "soundcloud.com",
    # Social networks
    "twitter.com", "x.com", "t.co",
    "instagram.com",
    "facebook.com", "fb.com", "fb.watch",
    "reddit.com", "v.redd.it",
    "linkedin.com",
    "pinterest.com",
    # Misc
    "tumblr.com",
    "coub.com",
    "gfycat.com",
    "streamja.com",
    "streamff.com",
    "clippituser.tv",
    "clips.twitch.tv",
})

# File extensions that indicate a direct streamable/downloadable URL.
DIRECT_STREAM_EXTENSIONS: frozenset[str] = frozenset({
    ".m3u8", ".m3u", ".ts", ".mp4", ".mkv", ".webm",
    ".avi", ".mov", ".flv", ".wmv", ".mpg", ".mpeg",
})

# URL path/query substrings that hint at a CDN or direct stream regardless of extension.
DIRECT_STREAM_PATTERNS: tuple[str, ...] = (
    ".m3u8",
    "/manifest",
    "/playlist",
    "/hls/",
    "/dash/",
    "/video/mp4",
    "application/x-mpegurl",
    "googlevideo.com",
    "akamaized.net",
    "cloudfront.net",
    "fastly.net",
)

# ---------------------------------------------------------------------------
# yt-dlp error string fragments → exception type mapping
# ---------------------------------------------------------------------------

# Substrings found in yt-dlp error messages mapped to a short reason code.
# Keys are compared case-insensitively (lowered before lookup).
YTDLP_ERROR_MAP: dict[str, str] = {
    # Network failures
    "unable to download webpage": "network",
    "connection reset":           "network",
    "urlopen error":              "network",
    "ssl":                        "network",
    "name or service not known":  "network",
    "timed out":                  "timeout",
    # HTTP errors
    "http error 403":             "http_403",
    "http error 404":             "http_404",
    "http error 429":             "http_429",
    "http error 500":             "http_500",
    "http error 503":             "http_503",
    # Filesystem
    "no space left":              "disk_full",
    "enospc":                     "disk_full",
    "permission denied":          "permission",
    # Authentication / age-restriction
    "sign in":                    "auth",
    "login required":             "auth",
    "age-restricted":             "age_restricted",
    "age restricted":             "age_restricted",
    "confirm your age":           "age_restricted",
    "member":                     "members_only",
    # Geo-restriction
    "geo":                        "geo_block",
    "not available in your country": "geo_block",
    "country":                    "geo_block",
    # ffmpeg
    "ffmpeg is not installed":    "ffmpeg_missing",
    "ffmpeg not found":           "ffmpeg_missing",
    "needs ffmpeg":               "ffmpeg_missing",
    "postprocessing: error":      "ffmpeg_error",
    # Format unavailable
    "requested format is not available": "format_unavailable",
    "format is not available":    "format_unavailable",
    # Content unavailable
    "video unavailable":          "unavailable",
    "this video has been removed": "unavailable",
    "private video":              "unavailable",
    "has been removed":           "unavailable",
    "is not available":           "unavailable",
}

# ---------------------------------------------------------------------------
# Miscellaneous
# ---------------------------------------------------------------------------

REQUESTS_TIMEOUT: int = 10           # seconds for PyPI version-check HTTP calls
