"""CLI console helpers with optional Rich support.

This module intentionally avoids module-level imports of optional UI
dependencies so bootstrap paths (``--help``, ``--version``) remain
functional even when Rich is not installed.
"""

from __future__ import annotations

import sys
from typing import Any

from ytd_wrap.exceptions import EnvironmentError


def _load_rich_console_class() -> type[Any]:
	"""Return ``rich.console.Console`` class or raise ``EnvironmentError``."""
	try:
		from rich.console import Console
	except ModuleNotFoundError as exc:
		raise EnvironmentError(
			"rich is not installed. Install with: pip install rich",
		) from exc
	return Console


def get_rich_console() -> Any:
	"""Create a Rich console instance targeting stderr."""
	console_class = _load_rich_console_class()
	return console_class(stderr=True)


class _ConsoleProxy:
	"""Minimal ``print``-compatible proxy with Rich fallback."""

	def print(self, *objects: object) -> None:
		"""Render with Rich when available, else plain stderr print."""
		try:
			rich_console = get_rich_console()
		except EnvironmentError:
			print(*objects, file=sys.stderr)
			return
		rich_console.print(*objects)


console = _ConsoleProxy()
