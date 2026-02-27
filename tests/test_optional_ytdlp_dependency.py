"""Regression tests for optional yt-dlp dependency boundaries.

These tests ensure CLI paths that do not require yt-dlp still work when
yt-dlp is absent, while runtime download/extraction paths fail cleanly
with a typed environment error.
"""

from __future__ import annotations

import sys

import pytest

from ytd_wrap.cli import exit_codes
from ytd_wrap.cli.app import main
from ytd_wrap.exceptions import EnvironmentError
from ytd_wrap.infra.ytdlp_download_provider import YtDlpDownloadProvider
from ytd_wrap.infra.ytdlp_provider import YtDlpMetadataProvider


def _remove_ytdlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "yt_dlp", None)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", None)
    monkeypatch.setitem(sys.modules, "yt_dlp.version", None)


def test_help_works_without_ytdlp(monkeypatch: pytest.MonkeyPatch) -> None:
    _remove_ytdlp(monkeypatch)
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_version_works_without_ytdlp(monkeypatch: pytest.MonkeyPatch) -> None:
    _remove_ytdlp(monkeypatch)
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


def test_doctor_works_without_ytdlp(monkeypatch: pytest.MonkeyPatch) -> None:
    _remove_ytdlp(monkeypatch)
    code = main(["doctor"])
    assert code == exit_codes.GENERAL_ERROR


def test_metadata_extraction_raises_environment_error_without_ytdlp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _remove_ytdlp(monkeypatch)
    provider = YtDlpMetadataProvider()

    with pytest.raises(EnvironmentError, match="yt-dlp is not installed"):
        provider.fetch_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_download_raises_environment_error_without_ytdlp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _remove_ytdlp(monkeypatch)
    provider = YtDlpDownloadProvider()

    with pytest.raises(EnvironmentError, match="yt-dlp is not installed"):
        provider.download(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "137+bestaudio[ext=m4a]/best[ext=mp4]",
        )
