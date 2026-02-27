"""Regression tests for optional CLI UI dependencies (rich/questionary).

These tests verify bootstrap commands are resilient when optional UI
packages are missing, and download flows fail cleanly only when UI paths
are actually exercised.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from ytd_wrap.cli import exit_codes
from ytd_wrap.cli.app import main
from ytd_wrap.core.models import FormatCollection, VideoFormat, VideoMetadata
from ytd_wrap.exceptions import EnvironmentError


def _hide_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "rich", None)
    monkeypatch.setitem(sys.modules, "rich.console", None)
    monkeypatch.setitem(sys.modules, "rich.table", None)
    monkeypatch.setitem(sys.modules, "rich.progress", None)


def _hide_questionary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "questionary", None)


def _meta() -> VideoMetadata:
    return VideoMetadata(
        id="abc123",
        title="Test Video",
        duration=120,
        webpage_url="https://www.youtube.com/watch?v=abc123",
    )


def _fmt() -> VideoFormat:
    return VideoFormat(
        format_id="137",
        ext="mp4",
        height=1080,
        fps=30,
        filesize=50_000_000,
        vcodec="avc1.640028",
        acodec="none",
    )


def test_help_works_without_rich_or_questionary(monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_rich(monkeypatch)
    _hide_questionary(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_version_works_without_rich_or_questionary(monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_rich(monkeypatch)
    _hide_questionary(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0


def test_doctor_works_without_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    _hide_rich(monkeypatch)

    code = main(["doctor"])
    assert code in (exit_codes.SUCCESS, exit_codes.GENERAL_ERROR)


def test_download_errors_cleanly_when_rich_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _hide_rich(monkeypatch)

    with patch("ytd_wrap.core.metadata_service.MetadataService") as mock_meta_svc_cls:
        with patch("ytd_wrap.infra.ytdlp_provider.YtDlpMetadataProvider"):
            mock_meta_svc_cls.return_value.extract_metadata.return_value = _meta()
            mock_meta_svc_cls.return_value.get_adaptive_video_formats.return_value = (
                FormatCollection(formats=(_fmt(),))
            )

            with pytest.raises(EnvironmentError, match="rich is not installed"):
                main(["https://www.youtube.com/watch?v=abc123"])


def test_download_errors_cleanly_when_questionary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _hide_questionary(monkeypatch)

    with patch("ytd_wrap.core.metadata_service.MetadataService") as mock_meta_svc_cls:
        with patch("ytd_wrap.infra.ytdlp_provider.YtDlpMetadataProvider"):
            mock_meta_svc_cls.return_value.extract_metadata.return_value = _meta()
            mock_meta_svc_cls.return_value.get_adaptive_video_formats.return_value = (
                FormatCollection(formats=(_fmt(),))
            )

            with pytest.raises(EnvironmentError, match="questionary is not installed"):
                main(["https://www.youtube.com/watch?v=abc123"])
