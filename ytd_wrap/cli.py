"""CLI entry points for ytd-wrap.

Pure orchestration -- no business logic lives here.
All logic belongs in ytd_wrap.core / ytd_wrap.checks / ytd_wrap.ui.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ytd_wrap import __version__
from ytd_wrap.checks.dependencies import (
    check_ffmpeg,
    get_ffmpeg_install_command,
    run_all_checks,
)
from ytd_wrap.checks.updates import check_for_updates
from ytd_wrap.core.downloader import create_progress_hook, download
from ytd_wrap.core.extractor import (
    determine_output_container,
    extract_formats,
    extract_metadata,
    select_best_format,
)
from ytd_wrap.core.resolver import detect_url_type, is_valid_url
from ytd_wrap.ui.display import (
    get_spinner,
    print_banner,
    print_download_start,
    print_doctor_table,
    print_error,
    print_ffmpeg_missing,
    print_formats_table,
    print_success,
    print_update_notice,
    print_version,
)
from ytd_wrap.ui.selector import select_format
from ytd_wrap.utils.exceptions import (
    DiskFullError,
    DownloadError,
    ExtractionError,
    NetworkError,
    UserCancelledError,
)
from ytd_wrap.utils.logger import get_logger
from ytd_wrap.utils.paths import get_download_dir

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom group: routes unknown first token as a URL instead of erroring
# ---------------------------------------------------------------------------

class _SmartGroup(click.Group):
    """click.Group that treats an unrecognised first positional token as a URL
    for the default download flow rather than raising "No such command"."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Find the first non-option token
        non_opt_idx = next(
            (i for i, a in enumerate(args) if not a.startswith("-")), None
        )
        if non_opt_idx is not None:
            token = args[non_opt_idx]
            if token not in self.commands:
                # This token is not a subcommand - treat it as the URL
                ctx.ensure_object(dict)
                ctx.obj["_url"] = token
                args = args[:non_opt_idx] + args[non_opt_idx + 1:]
        return super().parse_args(ctx, args)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Version callback
# ---------------------------------------------------------------------------

def _version_callback(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return
    print_version(__version__)
    ctx.exit()


# ---------------------------------------------------------------------------
# Progress bar factory
# ---------------------------------------------------------------------------

def _make_progress() -> Progress:
    """Return a rich Progress bar configured for file downloads."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        transient=True,
    )


# ---------------------------------------------------------------------------
# Shared pre-flight helpers
# ---------------------------------------------------------------------------

def _preflight(url: str) -> None:
    """Validate URL and ensure ffmpeg is present.  Exits on failure."""
    if not is_valid_url(url):
        print_error(
            f"Invalid URL: {url!r}",
            hint="Make sure the URL starts with http:// or https://",
        )
        sys.exit(1)

    if not check_ffmpeg():
        print_ffmpeg_missing(get_ffmpeg_install_command())
        sys.exit(1)


def _announce_updates() -> bool:
    """Non-blocking update check.

    Returns:
        ``True`` if updates are available and the caller should stop further
        processing for this invocation, else ``False``.
    """
    try:
        updates = check_for_updates()
        if updates:
            print_update_notice(updates)
            return True
        return False
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Download flows
# ---------------------------------------------------------------------------

def _run_social_download(url: str) -> None:
    """Full interactive flow for social-media URLs."""
    with get_spinner("Fetching video info..."):
        metadata = extract_metadata(url)
        try:
            formats = extract_formats(url)
        except ExtractionError:
            # No video formats found — fall back to automatic best selection
            formats = []

    if not formats:
        _log.debug("No video formats found for %r — using 'best' fallback", url)
        chosen = {"format_id": "best", "vcodec": "unknown", "acodec": "unknown"}
    else:
        print_download_start(metadata["title"], url)
        print_formats_table(formats)
        chosen = select_format(formats)

    if formats:  # only show start panel once (already shown above)
        pass
    else:
        print_download_start(metadata.get("title", "video"), url)

    container = chosen.get("container") or determine_output_container(chosen)
    output_dir = get_download_dir()
    title = metadata.get("title", "video")
    from ytd_wrap.utils.paths import sanitize_filename
    fname = sanitize_filename(title) + "." + container

    with _make_progress() as progress:
        task = progress.add_task(f"Downloading {fname[:40]}", total=100)
        hook = create_progress_hook(progress, task, filename=fname)
        final_path = download(
            url,
            chosen["format_id"],
            title,
            output_dir,
            container,
            hook,
            audio_format_id=chosen.get("audio_format_id"),
        )

    print_success(final_path.name, final_path.parent)


def _run_direct_download(url: str) -> None:
    """Automatic (no format prompt) flow for direct / unknown URLs."""
    with get_spinner("Probing stream..."):
        metadata = {"title": "video"}
        try:
            metadata = extract_metadata(url)
        except ExtractionError:
            pass
        try:
            formats = extract_formats(url)
            chosen = select_best_format(formats)
        except ExtractionError as exc:
            _log.debug("Direct format extraction failed for %r; using best fallback: %s", url, exc)
            chosen = {"format_id": "best", "vcodec": "unknown", "acodec": "unknown"}

    container = chosen.get("container") or determine_output_container(chosen)
    output_dir = get_download_dir()
    title = metadata.get("title", "stream")
    from ytd_wrap.utils.paths import sanitize_filename
    fname = sanitize_filename(title) + "." + container

    print_download_start(title, url)

    with _make_progress() as progress:
        task = progress.add_task(f"Downloading {fname[:40]}", total=100)
        hook = create_progress_hook(progress, task, filename=fname)
        final_path = download(
            url,
            chosen["format_id"],
            metadata.get("title", "video"),
            output_dir,
            container,
            hook,
            audio_format_id=chosen.get("audio_format_id"),
        )

    print_success(final_path.name, final_path.parent)


# ---------------------------------------------------------------------------
# Top-level exception handler
# ---------------------------------------------------------------------------

def _handle_download_errors(exc: BaseException, url: str = "") -> None:  # noqa: ARG001
    """Map every possible download exception to a user-facing error message."""
    if isinstance(exc, UserCancelledError):
        print_error("Download cancelled.")
        sys.exit(0)
    if isinstance(exc, NetworkError):
        print_error(
            "Network error",
            hint=str(exc) or "Check your internet connection and retry.",
        )
        sys.exit(1)
    if isinstance(exc, DiskFullError):
        print_error(
            "Disk full",
            hint=f"Free up space on the destination drive: {exc}",
        )
        sys.exit(1)
    if isinstance(exc, PermissionError):  # type: ignore[misc]
        print_error(
            "Permission denied",
            hint=f"Check write permissions for the download directory: {exc}",
        )
        sys.exit(1)
    if isinstance(exc, DownloadError):
        print_error("Download failed", hint=str(exc))
        sys.exit(1)
    # Unexpected
    _log.exception("Unexpected error during download")
    print_error("Unexpected error. Check logs for details.", hint=str(exc) or None)
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@click.group(cls=_SmartGroup, invoke_without_command=True)
@click.option(
    "--version", "-V",
    is_flag=True, is_eager=True, expose_value=False,
    callback=_version_callback,
    help="Show version and exit.",
)
@click.pass_context
def main(ctx: click.Context) -> None:
    """ytd-wrap -- download videos from social media or direct stream URLs.

    Pass a URL as the only argument to start downloading:

    \b
        ytd-wrap "https://www.youtube.com/watch?v=..."
        ytd-wrap "https://example.com/stream.m3u8"

    Run `ytd-wrap doctor` to check your environment.

    \b
    Examples:
      ytd-wrap "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
      ytd-wrap "https://twitter.com/user/status/123"
      ytd-wrap "https://cdn.example.com/live.m3u8"
    """
    if ctx.invoked_subcommand is not None:
        # A subcommand (e.g. doctor) was requested
        return

    url: str | None = (ctx.obj or {}).get("_url")

    if not url:
        click.echo(ctx.get_help())
        ctx.exit()
        return

    # Strip surrounding whitespace and quotes users sometimes paste
    url = url.strip().strip('"\'')

    _preflight(url)
    if _announce_updates():
        # If newer versions are available, ask user to upgrade first instead
        # of continuing extraction/download in this run.
        ctx.exit(0)
        return
    print_banner()

    url_type = detect_url_type(url)
    _log.debug("Detected URL type: %s for %r", url_type, url)

    try:
        if url_type == "social":
            _run_social_download(url)
        else:
            _run_direct_download(url)

    except KeyboardInterrupt:
        print_error("Download cancelled.")
        sys.exit(0)
    except (UserCancelledError, NetworkError, DiskFullError, DownloadError, ExtractionError) as exc:
        _handle_download_errors(exc, url)
    except Exception as exc:  # noqa: BLE001
        _handle_download_errors(exc, url)


@main.command()
def doctor() -> None:
    """Check Python version, yt-dlp, and ffmpeg — shows OS-specific install hints."""
    results = run_all_checks()
    print_doctor_table(results)

    if not results.get("ffmpeg"):
        print_ffmpeg_missing(get_ffmpeg_install_command())

    click.echo("@shyam")
