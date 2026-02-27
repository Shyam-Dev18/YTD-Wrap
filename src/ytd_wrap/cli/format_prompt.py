"""Interactive format selection UI for the CLI layer.

This module is responsible for:

* Rendering a Rich table showing available video formats.
* Prompting the user to select a format via questionary arrow keys.
* Returning the selected ``format_id`` as a string.

All display-related logic lives here — no business logic, no
downloading, no metadata parsing.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ytd_wrap.cli.console import console
from ytd_wrap.core.models import VideoFormat, VideoMetadata
from ytd_wrap.exceptions import EnvironmentError


def _import_questionary() -> Any:
    """Import questionary lazily for interactive selection."""
    try:
        import questionary
    except ModuleNotFoundError as exc:
        raise EnvironmentError(
            "questionary is not installed. Install with: pip install questionary",
        ) from exc
    return questionary


def _import_rich_table() -> type[Any]:
    """Import rich table lazily for format rendering."""
    try:
        from rich.table import Table
    except ModuleNotFoundError as exc:
        raise EnvironmentError(
            "rich is not installed. Install with: pip install rich",
        ) from exc
    return Table


# ---------------------------------------------------------------------------
# Presentation helpers (pure transforms — no I/O themselves)
# ---------------------------------------------------------------------------

def _format_filesize(filesize: int | None) -> str:
    """Convert bytes to a human-readable MB string, or ``"Unknown"``."""
    if filesize is None:
        return "Unknown"
    mb = filesize / (1024 * 1024)
    return f"{mb:.1f} MB"


def _format_resolution(height: int | None) -> str:
    """Render height as ``"1080p"`` or ``"Unknown"``."""
    if height is None:
        return "Unknown"
    return f"{height}p"


def _format_fps(fps: int | None) -> str:
    """Render FPS or ``"—"`` when unavailable."""
    if fps is None:
        return "—"
    return str(fps)


def _build_choice_label(index: int, fmt: VideoFormat) -> str:
    """Build the single-line label shown in the questionary selector.

    Format: ``"  1.  1080p   30fps   mp4   150.3 MB"``
    """
    res = _format_resolution(fmt.height)
    fps = _format_fps(fmt.fps)
    size = _format_filesize(fmt.filesize)
    return f"  {index + 1}.  {res:<10} {fps:>4}fps   {fmt.ext:<6} {size}"


# ---------------------------------------------------------------------------
# Rich table display
# ---------------------------------------------------------------------------

def _display_format_table(
    metadata: VideoMetadata,
    formats: Sequence[VideoFormat],
) -> None:
    """Print a Rich table summarising the available formats."""
    table_class = _import_rich_table()

    console.print()
    console.print(f"[bold cyan]Title:[/bold cyan]  {metadata.title}")
    if metadata.duration is not None:
        minutes, seconds = divmod(metadata.duration, 60)
        console.print(f"[bold cyan]Duration:[/bold cyan] {minutes}m {seconds}s")
    console.print()

    table = table_class(
        title="Available Formats",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Resolution", justify="left", min_width=10)
    table.add_column("FPS", justify="right", min_width=5)
    table.add_column("Container", justify="left", min_width=8)
    table.add_column("Size", justify="right", min_width=10)

    for i, fmt in enumerate(formats, start=1):
        table.add_row(
            str(i),
            _format_resolution(fmt.height),
            _format_fps(fmt.fps),
            fmt.ext,
            _format_filesize(fmt.filesize),
        )

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Public prompt function
# ---------------------------------------------------------------------------

def prompt_format_selection(
    metadata: VideoMetadata,
    formats: Sequence[VideoFormat],
) -> str:
    """Display formats and prompt the user for an interactive selection.

    Parameters
    ----------
    metadata:
        Video metadata used to display title and duration.
    formats:
        Pre-filtered, sorted sequence of adaptive video formats.

    Returns
    -------
    str
        The ``format_id`` of the user's chosen format.

    Raises
    ------
    KeyboardInterrupt
        If the user presses Ctrl+C during selection.
    FormatSelectionError
        If the user cancels the prompt (Esc / None return).
    """
    from ytd_wrap.exceptions import FormatSelectionError

    questionary = _import_questionary()

    _display_format_table(metadata, formats)

    # Build questionary choices — each label maps back to a format_id.
    choices = [
        questionary.Choice(
            title=_build_choice_label(i, fmt),
            value=fmt.format_id,
        )
        for i, fmt in enumerate(formats)
    ]

    selected: str | None = questionary.select(
        "Select format to download:",
        choices=choices,
        use_arrow_keys=True,
        use_shortcuts=False,
    ).ask()  # Returns None on Ctrl+C / Esc

    if selected is None:
        raise FormatSelectionError(
            "No format selected.",
            hint="Use arrow keys to pick a format, then press Enter.",
        )

    return selected
