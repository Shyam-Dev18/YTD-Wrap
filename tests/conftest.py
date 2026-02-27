"""Shared pytest fixtures and configuration for the ytd-wrap test suite.

Guidelines
----------
* No internet access in any test.
* yt-dlp must be mocked at the infra boundary.
* Core tests must be pure — no side effects.
* Tests must not depend on OS state.
"""

from __future__ import annotations
