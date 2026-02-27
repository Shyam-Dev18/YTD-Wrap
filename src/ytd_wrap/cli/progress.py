"""Rich-based progress display driven by yt-dlp progress hooks.

This module bridges yt-dlp's ``progress_hooks`` callback mechanism
with a Rich :class:`~rich.progress.Progress` bar.  It is used by
the CLI layer — the infra layer only forwards the raw hook dicts.

Design
------
* The :class:`RichProgressHook` manages a Rich Progress context.
* :meth:`__call__` is the callback passed to yt-dlp via the provider.
* Shutdown-safe: if the progress bar is already stopped, calls are
  silently ignored.
* No ``print()`` — Rich handles all rendering.
"""

from __future__ import annotations

from typing import Any

from ytd_wrap.cli.console import get_rich_console
from ytd_wrap.exceptions import EnvironmentError


class RichProgressHook:
    """Callable progress-hook adapter for Rich.

    Usage::

        hook = RichProgressHook()
        hook.start()
        # pass hook as progress_callback to DownloadService
        download_service.download(url, fmt_id, progress_callback=hook)
        hook.stop()

    Or as a context manager::

        with RichProgressHook() as hook:
            download_service.download(url, fmt_id, progress_callback=hook)
    """

    def __init__(self) -> None:
        try:
            from rich.progress import (
                BarColumn,
                DownloadColumn,
                Progress,
                SpinnerColumn,
                TextColumn,
                TimeRemainingColumn,
                TransferSpeedColumn,
            )
        except ModuleNotFoundError as exc:
            raise EnvironmentError(
                "rich is not installed. Install with: pip install rich",
            ) from exc

        self._progress: Any = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=get_rich_console(),
            transient=False,
        )
        self._task_id: int | None = None
        self._started: bool = False

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> RichProgressHook:
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Rich progress display."""
        if not self._started:
            self._progress.start()
            self._started = True

    def stop(self) -> None:
        """Stop the Rich progress display (idempotent)."""
        if self._started:
            self._progress.stop()
            self._started = False

    # ------------------------------------------------------------------
    # Hook callback
    # ------------------------------------------------------------------

    def __call__(self, d: dict[str, Any]) -> None:
        """yt-dlp progress-hook callback.

        Parameters
        ----------
        d:
            A dict with at least ``"status"`` key.  Possible statuses:
            ``"downloading"``, ``"finished"``, ``"error"``.
        """
        if not self._started:
            return

        status: str = d.get("status", "")

        if status == "downloading":
            self._handle_downloading(d)
        elif status == "finished":
            self._handle_finished()

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _handle_downloading(self, d: dict[str, Any]) -> None:
        """Update progress bar with download metrics."""
        total: int | None = _safe_int(d.get("total_bytes") or d.get("total_bytes_estimate"))
        downloaded: int = _safe_int(d.get("downloaded_bytes")) or 0

        if self._task_id is None:
            filename: str = d.get("filename", "Downloading")
            # Use just the base filename for display.
            display_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if len(display_name) > 50:
                display_name = display_name[:47] + "..."
            self._task_id = self._progress.add_task(
                display_name,
                total=total,
            )

        task_id = self._task_id
        if total is not None:
            self._progress.update(task_id, total=total, completed=downloaded)
        else:
            self._progress.update(task_id, completed=downloaded)

    def _handle_finished(self) -> None:
        """Mark the current task as complete."""
        if self._task_id is not None:
            task = self._progress.tasks[self._task_id]
            if task.total is not None:
                self._progress.update(self._task_id, completed=task.total)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _safe_int(value: object) -> int | None:
    """Convert *value* to ``int`` or return ``None``."""
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float, str, bytes, bytearray)):
            return int(value)
        return None
    except (TypeError, ValueError):
        return None
