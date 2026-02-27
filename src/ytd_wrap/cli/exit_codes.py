"""Exit-code constants used by the CLI layer.

Centralised here so that every exit path uses a well-known, tested
value rather than magic integers scattered across the codebase.
"""

from __future__ import annotations

SUCCESS: int = 0
"""Clean exit — command completed without error."""

GENERAL_ERROR: int = 1
"""A known YtdWrapError was caught. User-facing message was displayed."""

KEYBOARD_INTERRUPT: int = 130
"""User pressed Ctrl+C.  Follows POSIX convention (128 + SIGINT=2)."""

UNEXPECTED_ERROR: int = 2
"""An unhandled exception escaped all known error boundaries."""
