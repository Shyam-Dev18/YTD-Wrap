"""yt-dlp download orchestration for social media and direct/m3u8 URLs.

yt-dlp is lazily imported inside every function to avoid module-load crashes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ytd_wrap.constants import (
    YTDLP_CONTINUEDL,
    YTDLP_FRAGMENT_RETRIES,
    YTDLP_RETRIES,
    YTDLP_SOCKET_TIMEOUT,
    YTDLP_ERROR_MAP,
)
from ytd_wrap.utils.exceptions import (
    DiskFullError,
    DownloadError,
    NetworkError,
    PermissionError,
    UserCancelledError,
)
from ytd_wrap.utils.logger import get_logger
from ytd_wrap.utils.paths import sanitize_filename

if TYPE_CHECKING:
    import rich.progress

_log = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

_AGE_RESTRICTED_HINT = (
    "This content is age-restricted. Sign in to YouTube/the platform in your"
    " browser and try again, or pass --cookies-from-browser to yt-dlp."
)
_GEO_BLOCK_HINT = (
    "This content is not available in your country. "
    "Try using a VPN to access it."
)
_FFMPEG_MISSING_HINT = (
    "ffmpeg was removed or is not on PATH. Re-install ffmpeg and ensure it is"
    " accessible from your terminal."
)
_MEMBERS_ONLY_HINT = "This content is for channel members only. Sign in with a member account."
_UNAVAILABLE_HINT = "The video may have been deleted, made private, or is not accessible."


def _map_error(msg: str, url: str) -> DownloadError | NetworkError | DiskFullError | PermissionError:  # type: ignore[return]
    """Inspect a yt-dlp error message and return the appropriate exception.

    Args:
        msg: The raw error message string from yt-dlp.
        url: The URL that was being downloaded.

    Returns:
        An appropriate :class:`~ytd_wrap.utils.exceptions.YtdWrapError` subclass instance.
    """
    from ytd_wrap.constants import HTTP_ERROR_MESSAGES

    lower = msg.lower()

    for fragment, code in YTDLP_ERROR_MAP.items():
        if fragment in lower:
            if code == "disk_full":
                return DiskFullError(url)
            if code == "permission":
                return PermissionError(url)  # type: ignore[return-value]
            if code in ("network", "timeout"):
                return NetworkError(msg)
            if code == "age_restricted":
                return DownloadError(url, _AGE_RESTRICTED_HINT)
            if code == "geo_block":
                return DownloadError(url, _GEO_BLOCK_HINT)
            if code == "ffmpeg_missing":
                return DownloadError(url, _FFMPEG_MISSING_HINT)
            if code == "ffmpeg_error":
                return DownloadError(url, "ffmpeg post-processing failed. " + msg)
            if code == "members_only":
                return DownloadError(url, _MEMBERS_ONLY_HINT)
            if code == "unavailable":
                return DownloadError(url, _UNAVAILABLE_HINT + " Error: " + msg)
            if code == "format_unavailable":
                return DownloadError(url, "The selected format is no longer available. Try a different resolution.")
            # HTTP errors
            if code.startswith("http_"):
                status = int(code.split("_")[1])
                human = HTTP_ERROR_MESSAGES.get(status, msg)
                return DownloadError(url, human)
            return DownloadError(url, msg)

    return DownloadError(url, msg)


def _find_output_file(output_dir: Path, title_safe: str, container: str) -> Path | None:
    """Try to locate the downloaded file in *output_dir*.

    yt-dlp may append suffixes, so we search by stem prefix.

    Args:
        output_dir: Directory where the file was saved.
        title_safe: Sanitized title used as the filename stem.
        container: Expected file extension (``"mp4"`` / ``"mkv"``).

    Returns:
        The :class:`~pathlib.Path` of the first matching file, or ``None``.
    """
    target = output_dir / f"{title_safe}.{container}"
    if target.exists():
        return target

    # Broaden search: match any file starting with the stem
    stem_lower = title_safe.lower()
    for candidate in output_dir.iterdir():
        if candidate.stem.lower().startswith(stem_lower[:30]) and candidate.suffix.lstrip(".") in ("mp4", "mkv", "webm"):
            return candidate

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def build_ydl_opts(
    format_id: str,
    output_path: Path,
    container: str,
    progress_hook: Callable[[dict[str, Any]], None],
    audio_format_id: str | None = None,
    use_native_hls: bool = False,
    convert_container: bool = True,
) -> dict[str, Any]:
    """Construct a full yt-dlp options dict for a download job.

    Args:
        format_id: yt-dlp video format ID.
        output_path: Full output file path including extension.
        container: Target container extension ``"mp4"`` or ``"mkv"``.
        progress_hook: Callable to receive yt-dlp progress dicts.
        audio_format_id: Separate audio format ID to merge with video, or None
            when the selected format already contains audio.
        use_native_hls: When False (default), force ffmpeg for HLS/m3u8 streams.
        convert_container: When True, force output remux/convert to *container*.
            When False, keep the source container chosen by yt-dlp.

    Returns:
        Dict suitable for passing to ``yt_dlp.YoutubeDL(**opts)``.
    """
    # Build format selector
    if audio_format_id:
        fmt_selector = f"{format_id}+{audio_format_id}/best"
    else:
        fmt_selector = f"{format_id}/best"

    opts: dict[str, Any] = {
        "format":                        fmt_selector,
        "outtmpl":                       str(output_path.with_suffix(".%(ext)s")),
        "continuedl":                    YTDLP_CONTINUEDL,
        "retries":                       YTDLP_RETRIES,
        "fragment_retries":              YTDLP_FRAGMENT_RETRIES,
        "socket_timeout":                YTDLP_SOCKET_TIMEOUT,
        "quiet":                         True,
        "no_warnings":                   True,
        "progress_hooks":                [progress_hook],
        "noprogress":                    True,
        "prefer_ffmpeg":                 True,
        "overwrites":                    False,
        # HLS/fragmented-stream reliability
        "hls_prefer_native":             use_native_hls,
        "concurrent_fragment_downloads": 4,
        "buffersize":                    1024 * 1024,
        "http_chunk_size":               10 * 1024 * 1024,
    }

    if convert_container:
        opts["merge_output_format"] = container
        opts["postprocessors"] = [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": container,
            },
        ]

    # Force ffmpeg HLS downloader for m3u8 streams
    if not use_native_hls:
        opts["downloader"] = {"m3u8": "ffmpeg"}

    return opts


def download(
    url: str,
    format_id: str,
    title: str,
    output_dir: Path,
    container: str,
    on_progress: Callable[[dict[str, Any]], None],
    audio_format_id: str | None = None,
) -> Path:
    """Download a video using yt-dlp and return the saved file path.

    Lazily imports :mod:`yt_dlp`.

    Args:
        url: The media URL to download.
        format_id: The yt-dlp video format ID to use.
        title: Video title used to name the output file.
        output_dir: Directory to save the downloaded file.
        container: Output container extension (``"mp4"`` or ``"mkv"``).
        on_progress: Callable receiving yt-dlp progress dicts.
        audio_format_id: Separate audio format ID to merge, or None when the
            video format already contains audio.

    Returns:
        Absolute :class:`~pathlib.Path` to the downloaded file.

    Raises:
        DownloadError: Generic download failure.
        NetworkError: Network timeout or unreachable host.
        DiskFullError: No space left on destination filesystem.
        PermissionError: Cannot write to destination.
        UserCancelledError: User pressed Ctrl+C.
    """
    import yt_dlp  # lazy import

    # Strip surrounding whitespace and quotes that users sometimes paste
    url = url.strip().strip('"\'')

    # Detect m3u8 / HLS streams — use ffmpeg downloader for reliability
    from ytd_wrap.core.resolver import is_direct_stream
    _is_hls = is_direct_stream(url)

    title_safe = sanitize_filename(title)
    output_path = output_dir / f"{title_safe}.{container}"

    opts = build_ydl_opts(
        format_id, output_path, container, on_progress,
        audio_format_id=audio_format_id,
        use_native_hls=_is_hls,
        convert_container=(not _is_hls),
    )

    _log.debug(
        "Starting download: url=%r format=%r audio=%r title=%r output=%s",
        url, format_id, audio_format_id, title, output_path,
    )

    partial_path: Path | None = None

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    except KeyboardInterrupt:
        _log.info("Download interrupted by user.")
        # Clean up partial files
        for ext in (container, "part", "ytdl"):
            candidate = output_dir / f"{title_safe}.{ext}"
            if candidate.exists():
                try:
                    candidate.unlink()
                    _log.debug("Removed partial file: %s", candidate)
                except OSError:
                    pass
        raise UserCancelledError() from None

    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        _log.debug("yt-dlp DownloadError: %s", msg, exc_info=True)
        raise _map_error(msg, url) from exc

    except OSError as exc:
        msg = str(exc)
        _log.debug("OSError during download: %s", msg, exc_info=True)
        if exc.errno == 28 or "no space left" in msg.lower():  # ENOSPC
            raise DiskFullError(str(output_dir)) from exc
        if exc.errno == 13 or "permission denied" in msg.lower():  # EACCES
            raise PermissionError(str(output_dir)) from exc
        raise DownloadError(url, msg) from exc

    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        _log.debug("Unexpected error during download: %s", msg, exc_info=True)
        raise _map_error(msg, url) from exc

    # Locate the actual output file (yt-dlp may adjust extension)
    found = _find_output_file(output_dir, title_safe, container)
    if found and found.exists():
        return found

    # Absolute fallback: return the expected path even if not verified
    return output_path


def create_progress_hook(
    progress: "rich.progress.Progress",
    task_id: "rich.progress.TaskID",
    filename: str = "",
) -> Callable[[dict[str, Any]], None]:
    """Return a yt-dlp ``progress_hook`` that drives a rich Progress bar.

    The returned callable is passed directly to yt-dlp via ``progress_hooks``.

    Args:
        progress: The :class:`rich.progress.Progress` instance managing the bar.
        task_id: The task ID within *progress* to update.
        filename: Short output filename to display in the description prefix.

    Returns:
        A callable ``(d: dict) -> None`` compatible with yt-dlp's progress hook API.
    """
    # Truncate filename for display so very long names don't swamp the bar
    _fname = (filename[:40] + "…") if len(filename) > 40 else filename
    _prefix = f"[bold]{_fname}[/bold]  " if _fname else ""

    def hook(d: dict[str, Any]) -> None:
        status = d.get("status")

        if status == "downloading":
            total   = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            current = d.get("downloaded_bytes") or 0
            speed   = d.get("speed")
            eta     = d.get("eta")

            # Build a description with optional speed + ETA
            parts: list[str] = []
            if speed:
                mb_s = speed / (1024 * 1024)
                parts.append(f"{mb_s:.1f} MB/s")
            if eta is not None:
                parts.append(f"ETA {int(eta)}s")
            suffix = "  ".join(parts) if parts else "Downloading"
            description = f"{_prefix}{suffix}"

            if total:
                progress.update(task_id, completed=current, total=total, description=description)
            else:
                prev = progress.tasks[task_id].completed or 0
                progress.update(task_id, advance=max(0, current - prev), description=description)

        elif status == "finished":
            total = d.get("total_bytes") or (progress.tasks[task_id].total if progress.tasks else 0) or 0
            if total:
                progress.update(task_id, completed=total, description=f"{_prefix}[green]✓ Done[/green]")
            else:
                progress.update(task_id, description=f"{_prefix}[green]✓ Done[/green]")

        elif status == "error":
            progress.update(task_id, description=f"{_prefix}[red]✗ Failed[/red]")

    return hook

