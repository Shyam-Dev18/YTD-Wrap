"""CLI application entry point and command routing for ytd-wrap.

This module is the **sole error boundary** for the entire application.
It catches :class:`~ytd_wrap.exceptions.YtdWrapError`, ``KeyboardInterrupt``,
and any unexpected ``Exception``, rendering user-friendly messages via Rich
and returning well-defined exit codes.

Architecture notes
------------------
* No business logic lives here — all work is delegated to the core/service
  and infrastructure layers.
* ``print()`` is forbidden outside the CLI layer; Rich console is used
  exclusively.
* This module is the only place that translates between the domain world
  and the OS process exit code.
"""

from __future__ import annotations

import argparse
import sys

from ytd_wrap.cli import exit_codes
from ytd_wrap.cli.console import console
from ytd_wrap.exceptions import YtdWrapError
from ytd_wrap.version import __version__


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser.

    Sub-commands are not used for the MVP; the CLI supports:
    * ``ytd-wrap <url>``   — download a single video (interactive)
    * ``ytd-wrap doctor``  — environment diagnostics
    * ``ytd-wrap --version``
    """
    parser = argparse.ArgumentParser(
        prog="ytd-wrap",
        description="YouTube single-video interactive downloader.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="YouTube URL to download, or 'doctor' to run diagnostics.",
    )
    return parser


# ---------------------------------------------------------------------------
# Command dispatch (skeleton — no business logic)
# ---------------------------------------------------------------------------

def _handle_download(url: str) -> int:
    """Dispatch a single-video interactive download.

    Flow:
    1. Instantiate infra providers + core services.
    2. Extract metadata for display.
    3. Fetch adaptive video formats.
    4. Prompt user to select a format interactively.
    5. Download the selected format with Rich progress.
    """
    from ytd_wrap.cli.format_prompt import prompt_format_selection
    from ytd_wrap.cli.progress import RichProgressHook
    from ytd_wrap.core.download_service import DownloadService
    from ytd_wrap.core.metadata_service import MetadataService
    from ytd_wrap.exceptions import FormatSelectionError, append_ytdlp_upgrade_suggestion
    from ytd_wrap.infra.ytdlp_download_provider import YtDlpDownloadProvider
    from ytd_wrap.infra.ytdlp_provider import YtDlpMetadataProvider

    metadata_provider = YtDlpMetadataProvider()
    metadata_service = MetadataService(metadata_provider)

    console.print(f"\n[bold]Fetching metadata…[/bold]  {url}\n")
    metadata = metadata_service.extract_metadata(url)
    format_collection = metadata_service.get_adaptive_video_formats(url)

    selected_format_id = prompt_format_selection(
        metadata,
        format_collection.formats,
    )
    selected_format = next(
        (fmt for fmt in format_collection.formats if fmt.format_id == selected_format_id),
        None,
    )
    if selected_format is None:
        raise FormatSelectionError(
            "Selected format is no longer available.",
            hint=append_ytdlp_upgrade_suggestion("Retry and choose a listed format."),
        )

    console.print(
        f"\n[bold green]Starting download…[/bold green]  "
        f"format={selected_format_id}\n"
    )

    download_provider = YtDlpDownloadProvider()
    download_service = DownloadService(download_provider)

    with RichProgressHook() as hook:
        download_service.download(
            url,
            selected_format_id,
            selected_format.ext,
            progress_callback=hook,
        )

    console.print("\n[bold green]Download complete.[/bold green]")
    return exit_codes.SUCCESS


def _handle_doctor() -> int:
    """Dispatch the ``doctor`` diagnostics command."""
    from ytd_wrap.cli.doctor import run_doctor

    return run_doctor()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Run the ytd-wrap CLI.

    Parameters
    ----------
    argv:
        Explicit argument list.  When ``None`` (default), ``sys.argv[1:]``
        is used.  Accepting *argv* enables deterministic testing without
        monkeypatching.

    Returns
    -------
    int
        OS process exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.target is None:
        parser.print_help()
        return exit_codes.SUCCESS

    target: str = args.target

    if target.lower() == "doctor":
        return _handle_doctor()

    return _handle_download(target)


# ---------------------------------------------------------------------------
# Script-level error boundary
# ---------------------------------------------------------------------------

def cli() -> None:
    """Top-level error boundary invoked by the console-script entry point.

    This function wraps :func:`main` and guarantees the process never
    exits with a raw stack trace during normal usage.
    """
    try:
        code = main()
        sys.exit(code)
    except YtdWrapError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        if exc.hint:
            console.print(f"[yellow]Hint:[/yellow] {exc.hint}")
        sys.exit(exit_codes.GENERAL_ERROR)
    except KeyboardInterrupt:
        console.print("\n[yellow]Aborted by user.[/yellow]")
        sys.exit(exit_codes.KEYBOARD_INTERRUPT)
    except Exception as exc:  # noqa: BLE001
        console.print(
            "[bold red]Unexpected error.[/bold red] "
            "Please report this issue.\n"
            f"  {type(exc).__name__}: {exc}"
        )
        sys.exit(exit_codes.UNEXPECTED_ERROR)
