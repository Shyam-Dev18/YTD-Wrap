"""Allow ``python -m ytd_wrap`` invocation.

This module simply delegates to the CLI error-boundary entry point so
that ``python -m ytd_wrap`` behaves identically to the ``ytd-wrap``
console script.
"""

from __future__ import annotations

from ytd_wrap.cli.app import cli

if __name__ == "__main__":
    cli()
