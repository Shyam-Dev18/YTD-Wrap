"""questionary-based interactive format selector.

questionary is lazily imported inside each function to avoid import-time
crashes when the package is unavailable (e.g. during unit tests that mock it).
"""

from __future__ import annotations

from typing import Any

from ytd_wrap.utils.exceptions import FormatSelectionError, UserCancelledError


def _fmt_choice_label(fmt: dict[str, Any]) -> str:
    """Build the human-readable label for a questionary choice row.

    Args:
        fmt: Merged format dict produced by
             :func:`~ytd_wrap.core.extractor.extract_formats`.

    Returns:
        A fixed-width string like
        ``"FHD / 1080p    \u2502 MP4  \u2502 \u2605 h264 + aac    \u2502  12.4 MB"``.
    """
    resolution   = (fmt.get("resolution") or "?")
    container    = (fmt.get("container") or "mkv").upper()
    codec_pair   = fmt.get("codec_pair") or "?"
    filesize_str = fmt.get("filesize_str") or "~unknown"
    vcs = fmt.get("vcodec_short", "")
    acs = fmt.get("acodec_short", "")

    codec_label = f"\u2605 {codec_pair}" if (vcs == "h264" and acs == "aac") else codec_pair

    return f"{resolution:<14} \u2502 {container:<4} \u2502 {codec_label:<16} \u2502 {filesize_str:>10}"


def select_format(formats: list[dict[str, Any]]) -> dict[str, Any]:
    """Present an interactive arrow-key list for the user to pick a format.

    Lazily imports :mod:`questionary`.

    Args:
        formats: Ranked list of format dicts.  Must not be empty.

    Returns:
        The format dict corresponding to the user's selection.

    Raises:
        FormatSelectionError: If *formats* is empty.
        UserCancelledError: If the user presses Ctrl+C or submits an empty answer.
    """
    import questionary  # lazy import

    if not formats:
        raise FormatSelectionError("No formats are available for this URL.")

    choices = [
        questionary.Choice(title=_fmt_choice_label(fmt), value=fmt)
        for fmt in formats
    ]

    try:
        chosen = questionary.select(
            "Select a format (↑↓ to navigate, Enter to confirm):",
            choices=choices,
        ).ask()
    except KeyboardInterrupt:
        raise UserCancelledError() from None

    if chosen is None:
        # questionary returns None when the user cancels via Ctrl+C in some versions
        raise UserCancelledError()

    return chosen


def confirm_download(title: str) -> bool:
    """Ask the user to confirm they want to proceed with the download.

    Lazily imports :mod:`questionary`.

    Args:
        title: The video title to display in the prompt.

    Returns:
        ``True`` if the user confirmed, ``False`` otherwise.
    """
    import questionary  # lazy import

    try:
        answer = questionary.confirm(
            f"Download \"{title}\"?",
            default=True,
        ).ask()
    except KeyboardInterrupt:
        return False

    return bool(answer)

