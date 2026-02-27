"""``ytd-wrap doctor`` — environment diagnostics command.

Gathers system information and renders a Rich table summarising
whether the runtime environment satisfies ytd-wrap's requirements.

This module lives in the CLI layer — it may import from ``infra``
and ``core``, and it renders via Rich.  No business logic resides
here; it purely collects and displays diagnostic data.
"""

from __future__ import annotations

import platform
import sys

from ytd_wrap.cli import exit_codes
from ytd_wrap.cli.console import console
from ytd_wrap.infra.ffmpeg_detector import detect_ffmpeg
from ytd_wrap.version import __version__


# ---------------------------------------------------------------------------
# Diagnostic collectors
# ---------------------------------------------------------------------------

def _python_version_check() -> tuple[str, str, str]:
    """Return (label, value, status) for the Python version row."""
    version = platform.python_version()
    major, minor = sys.version_info[:2]
    ok = major >= 3 and minor >= 10
    status = "[green]OK[/green]" if ok else "[red]FAIL (>=3.10 required)[/red]"
    return "Python", version, status


def _ytdlp_version_check() -> tuple[str, str, str]:
    """Return (label, value, status) for the yt-dlp version row."""
    try:
        from yt_dlp.version import __version__ as ydl_ver

        return "yt-dlp", ydl_ver, "[green]OK[/green]"
    except ImportError:
        pass

    # Fallback: yt-dlp installed but version submodule unavailable.
    try:
        import yt_dlp  # noqa: F401

        return "yt-dlp", "unknown", "[green]OK[/green]"
    except ImportError:
        return "yt-dlp", "NOT INSTALLED", "[red]FAIL[/red]"


def _ffmpeg_check() -> tuple[str, str, str]:
    """Return (label, value, status) for the ffmpeg row."""
    status_obj = detect_ffmpeg()
    if status_obj.found:
        path_str = str(status_obj.path) if status_obj.path else "found"
        return "ffmpeg", path_str, "[green]OK[/green]"
    return "ffmpeg", "not found", "[yellow]WARN[/yellow]"


def _os_check() -> tuple[str, str, str]:
    """Return (label, value, status) for the OS row."""
    system_raw = platform.system()
    system_display = {
        "Windows": "Windows",
        "Linux": "Linux",
        "Darwin": "macOS",
    }.get(system_raw, system_raw)
    release = platform.release()
    machine = platform.machine()
    value = f"{system_display} {release} ({machine})"
    return "OS", value, "[green]OK[/green]"


def _ytdwrap_version_check() -> tuple[str, str, str]:
    """Return (label, value, status) for the ytd-wrap version row."""
    return "ytd-wrap", __version__, "[green]OK[/green]"


def _status_plain(status: str) -> str:
    """Convert rich-markup status to plain text."""
    if "FAIL" in status:
        return "FAIL"
    if "WARN" in status:
        return "WARN"
    if "OK" in status:
        return "OK"
    return status


def _print_plain_doctor_table(checks: list[tuple[str, str, str]]) -> None:
    """Render doctor output without Rich."""
    print("\nytd-wrap doctor", file=sys.stderr)
    print("=" * 56, file=sys.stderr)
    print(f"{'Component':<12} {'Value':<32} {'Status':<8}", file=sys.stderr)
    print("-" * 56, file=sys.stderr)
    for label, value, status in checks:
        plain_status = _status_plain(status)
        print(f"{label:<12} {value:<32} {plain_status:<8}", file=sys.stderr)
    print("@shyam", file=sys.stderr)
    print(file=sys.stderr)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_doctor() -> int:
    """Execute all diagnostic checks and render a Rich summary table.

    Returns
    -------
    int
        :data:`exit_codes.SUCCESS` when all critical checks pass,
        :data:`exit_codes.GENERAL_ERROR` if a critical check fails.
    """
    checks = [
        _ytdwrap_version_check(),
        _python_version_check(),
        _ytdlp_version_check(),
        _ffmpeg_check(),
        _os_check(),
    ]

    has_failure = False
    for _, _, status in checks:
        if "FAIL" in status:
            has_failure = True

    rich_available = True
    try:
        from rich.table import Table
    except ModuleNotFoundError:
        rich_available = False

    if rich_available:
        table = Table(
            title="ytd-wrap doctor",
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Component", style="bold", min_width=12)
        table.add_column("Value", min_width=20)
        table.add_column("Status", justify="center", min_width=8)

        for label, value, status in checks:
            table.add_row(label, value, status)

        console.print()
        console.print(table)
        console.print()
    else:
        _print_plain_doctor_table(checks)

    # Show ffmpeg install guidance when missing.
    ffmpeg_status = detect_ffmpeg()
    if not ffmpeg_status.found and ffmpeg_status.install_commands:
        if rich_available:
            console.print("[yellow]ffmpeg is not installed.[/yellow]")
            console.print("Install using one of the following commands:\n")
            for cmd in ffmpeg_status.install_commands:
                console.print(f"  [bold]{cmd}[/bold]")
            console.print()
        else:
            print("ffmpeg is not installed.", file=sys.stderr)
            print("Install using one of the following commands:\n", file=sys.stderr)
            for cmd in ffmpeg_status.install_commands:
                print(f"  {cmd}", file=sys.stderr)
            print(file=sys.stderr)

    if has_failure:
        if rich_available:
            console.print("[bold red]Some checks failed.[/bold red]")
            console.print("[dim]@shyam[/dim]")
        else:
            print("Some checks failed.", file=sys.stderr)
            print("@shyam", file=sys.stderr)
        return exit_codes.GENERAL_ERROR

    if rich_available:
        console.print("[bold green]All checks passed.[/bold green]")
        console.print("[dim]@shyam[/dim]")
    else:
        print("All checks passed.", file=sys.stderr)
        print("@shyam", file=sys.stderr)
    return exit_codes.SUCCESS
