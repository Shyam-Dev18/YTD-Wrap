"""Rich tables, panels, spinners, and status output for ytd-wrap.

All user-visible output goes through the module-level ``console`` object.
Tests can swap it out via ``ytd_wrap.ui.display.console = Console(file=buf)``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

from ytd_wrap import __version__
from ytd_wrap.constants import APP_NAME

# Module-level console — replace in tests for captured output.
console: Console = Console(highlight=False)

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_size(filesize: int | None) -> str:
    """Return a human-readable size string.

    Args:
        filesize: Size in bytes, or ``None`` if unknown.

    Returns:
        String like ``"142.3 MB"`` or ``"~unknown"``.
    """
    if filesize is None or filesize <= 0:
        return "~unknown"
    mb = filesize / (1024 * 1024)
    return f"{mb:.1f} MB"


def _is_preferred(fmt: dict[str, Any]) -> bool:
    """Return True if this format is h264 + aac/m4a (highlight-worthy).

    Args:
        fmt: Format dict with ``vcodec`` and ``acodec`` keys.

    Returns:
        True when the format uses h264 video and aac/m4a audio.
    """
    vcodec = (fmt.get("vcodec") or "").lower()
    acodec = (fmt.get("acodec") or "").lower()
    return ("h264" in vcodec or "avc1" in vcodec) and (
        "aac" in acodec or "m4a" in acodec or "mp4a" in acodec
    )


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def print_banner() -> None:
    """Print the app name and version in a styled panel on startup."""
    text = Text(justify="center")
    text.append(APP_NAME, style="bold cyan")
    text.append(f"  v{__version__}", style="dim")
    console.print(
        Panel(text, border_style="cyan", padding=(0, 4)),
        justify="center",
    )


def print_version(version: str) -> None:
    """Print a single-line version string.

    Args:
        version: Version string to display (e.g. ``"1.0.0"``).
    """
    console.print(f"[bold]{APP_NAME}[/bold] version [cyan]{version}[/cyan]")


def print_doctor_table(checks: dict[str, Any]) -> None:
    """Render a rich Table summarising the ``doctor`` checks.

    Expected keys in *checks*: ``python_ok``, ``python_version``,
    ``ytdlp``, ``ffmpeg``.

    Args:
        checks: Dict returned by :func:`~ytd_wrap.checks.dependencies.run_all_checks`.
    """
    table = Table(
        title=f"[bold]{APP_NAME} — Environment Check[/bold]",
        show_header=True,
        header_style="bold magenta",
        border_style="bright_black",
        expand=False,
    )
    table.add_column("Component", style="bold", min_width=12)
    table.add_column("Status", min_width=8, justify="center")
    table.add_column("Detail")

    def _ok(flag: bool) -> Text:
        return Text("✓  OK", style="green bold") if flag else Text("✗  Missing", style="red bold")

    # Python
    py_ver = checks.get("python_version", "?")
    py_ok: bool = checks.get("python_ok", False)
    table.add_row("Python", _ok(py_ok), f"v{py_ver}" + ("" if py_ok else "  [yellow](requires ≥ 3.11)[/yellow]"))

    # yt-dlp
    ytdlp_ok: bool = checks.get("ytdlp", False)
    table.add_row("yt-dlp", _ok(ytdlp_ok), "importable" if ytdlp_ok else "[yellow]run: pip install yt-dlp[/yellow]")

    # ffmpeg
    ffmpeg_ok: bool = checks.get("ffmpeg", False)
    table.add_row("ffmpeg", _ok(ffmpeg_ok), "found on PATH" if ffmpeg_ok else "[yellow]see hint below[/yellow]")

    # ytd-wrap itself
    table.add_row("ytd-wrap", Text("✓  OK", style="green bold"), f"v{__version__}")

    console.print(table)


def print_formats_table(formats: list[dict[str, Any]]) -> None:
    """Render available video formats as a rich Table.

    Columns: # | Resolution | Container | Codecs | Size

    Args:
        formats: List of merged format dicts produced by
                 :func:`~ytd_wrap.core.extractor.extract_formats`.
    """
    table = Table(
        title="[bold]Available Formats[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="bright_black",
        expand=False,
    )
    table.add_column("#",          min_width=3,  justify="right")
    table.add_column("Resolution", min_width=13)
    table.add_column("Container",  min_width=9)
    table.add_column("Codecs",     min_width=16)
    table.add_column("Size",       min_width=10, justify="right")

    for fmt in formats:
        idx        = str(fmt.get("display_index") or fmt.get("format_id") or "?")
        resolution = fmt.get("resolution") or "?"
        container  = (fmt.get("container") or "mkv").upper()
        codec_pair = fmt.get("codec_pair") or "?"
        size_str   = fmt.get("filesize_str") or _fmt_size(fmt.get("filesize"))
        height     = fmt.get("height") or 0
        vcs        = fmt.get("vcodec_short", "")
        acs        = fmt.get("acodec_short", "")

        # Resolution column style: 4K/8K bold cyan, FHD/2K bold white, HD white, lower dim
        if height >= 2160:
            res_cell = Text(resolution, style="bold cyan")
        elif height >= 1080:
            res_cell = Text(resolution, style="bold white")
        elif height >= 720:
            res_cell = Text(resolution, style="white")
        else:
            res_cell = Text(resolution, style="dim")

        # Container: MP4 green, MKV blue
        cont_cell = Text(container, style="green" if container == "MP4" else "blue")

        # Codecs: star-prefix + green for h264+aac
        if vcs == "h264" and acs == "aac":
            codec_cell = Text(f"\u2605 {codec_pair}", style="green")
        else:
            codec_cell = Text(codec_pair)

        table.add_row(idx, res_cell, cont_cell, codec_cell, size_str)

    console.print(table)


def print_update_notice(updates: list[dict[str, str]]) -> None:
    """Display a yellow panel listing outdated packages and upgrade commands.

    Args:
        updates: List of dicts with keys ``package``, ``current``, ``latest``.
    """
    if not updates:
        return

    lines: list[str] = ["[bold yellow]Updates available![/bold yellow]\n"]
    pip_packages: list[str] = []

    for item in updates:
        pkg = item["package"]
        cur = item["current"]
        lat = item["latest"]
        lines.append(f"  • [bold]{pkg}[/bold]  {cur} → [green]{lat}[/green]")
        pip_packages.append(pkg)

    upgrade_cmd = "pip install --upgrade " + " ".join(pip_packages)
    lines.append(f"\n[dim]Run:[/dim]  [bold cyan]{upgrade_cmd}[/bold cyan]")

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold yellow]⬆  Update Available[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def print_download_start(title: str, url: str) -> None:
    """Show a panel with the video title and source URL before downloading.

    Args:
        title: Video title extracted from metadata.
        url: The source URL being downloaded.
    """
    body = Text()
    body.append("Title:  ", style="bold")
    body.append(title + "\n", style="bright_white")
    body.append("Source: ", style="bold")
    body.append(url, style="dim")

    console.print(
        Panel(body, title="[bold cyan]Downloading[/bold cyan]", border_style="cyan", padding=(1, 2))
    )


def print_success(filename: str, path: Path) -> None:
    """Print a green panel confirming a completed download.

    Args:
        filename: The output filename (basename).
        path: Full absolute path to the saved file.
    """
    body = Text()
    body.append("File:   ", style="bold")
    body.append(filename + "\n", style="bright_white")
    body.append("Saved:  ", style="bold")
    body.append(str(path), style="bright_cyan")

    console.print(
        Panel(
            body,
            title="[bold green]✓  Download Complete[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


def print_error(message: str, hint: str | None = None) -> None:
    """Print a red panel with an error message and optional hint.

    Args:
        message: Short human-readable error description.
        hint: Optional suggestion for resolving the error.
    """
    body = Text()
    body.append(message, style="bold red")
    if hint:
        body.append("\n\n")
        body.append("Hint: ", style="bold yellow")
        body.append(hint, style="yellow")

    console.print(
        Panel(body, title="[bold red]✗  Error[/bold red]", border_style="red", padding=(1, 2))
    )


def print_ffmpeg_missing(install_cmd: str) -> None:
    """Print a yellow panel informing the user that ffmpeg is missing.

    Args:
        install_cmd: The OS-appropriate install command to display.
    """
    body = Text()
    body.append("ffmpeg", style="bold")
    body.append(" was not found on your system PATH.\n\n")
    body.append("Install it with:\n", style="dim")
    body.append(f"  {install_cmd}", style="bold cyan")
    body.append("\n\nAfter installing, close and reopen your terminal.", style="dim")

    console.print(
        Panel(
            body,
            title="[bold yellow]⚠  ffmpeg Not Found[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def get_spinner(message: str) -> Status:
    """Return a rich :class:`~rich.status.Status` context manager.

    Usage::

        with get_spinner("Fetching metadata…") as status:
            data = fetch_metadata(url)

    Args:
        message: Message to display next to the spinner.

    Returns:
        A :class:`rich.status.Status` instance (not yet started).
    """
    return console.status(message, spinner="dots")

