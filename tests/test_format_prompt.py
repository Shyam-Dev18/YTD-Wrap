"""Tests for the interactive format selection UI (Phase 3).

All tests mock the :class:`MetadataService` and ``questionary`` to
avoid internet access and terminal interaction.  No yt-dlp call is
made.  No Rich rendering assertions are needed — we test the logical
mapping between user selection and returned ``format_id``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ytd_wrap.cli import exit_codes
from ytd_wrap.cli.format_prompt import (
    _build_choice_label,
    _format_filesize,
    _format_fps,
    _format_resolution,
    prompt_format_selection,
)
from ytd_wrap.core.models import (
    FormatCollection,
    VideoFormat,
    VideoMetadata,
)
from ytd_wrap.exceptions import FormatSelectionError


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------

def _meta(**overrides: Any) -> VideoMetadata:
    defaults: dict[str, Any] = {
        "id": "abc123",
        "title": "Test Video",
        "duration": 120,
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
    }
    defaults.update(overrides)
    return VideoMetadata(**defaults)


def _fmt(**overrides: Any) -> VideoFormat:
    defaults: dict[str, Any] = {
        "format_id": "137",
        "ext": "mp4",
        "height": 1080,
        "fps": 30,
        "filesize": 50_000_000,
        "vcodec": "avc1.640028",
        "acodec": "none",
    }
    defaults.update(overrides)
    return VideoFormat(**defaults)


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

class TestFormatFilesize:
    def test_none_returns_unknown(self) -> None:
        assert _format_filesize(None) == "Unknown"

    def test_bytes_to_mb(self) -> None:
        assert _format_filesize(1_048_576) == "1.0 MB"

    def test_large_filesize(self) -> None:
        assert _format_filesize(524_288_000) == "500.0 MB"

    def test_small_filesize(self) -> None:
        result = _format_filesize(100_000)
        assert "MB" in result


class TestFormatResolution:
    def test_none_returns_unknown(self) -> None:
        assert _format_resolution(None) == "Unknown"

    def test_1080p(self) -> None:
        assert _format_resolution(1080) == "1080p"

    def test_720p(self) -> None:
        assert _format_resolution(720) == "720p"

    def test_4k(self) -> None:
        assert _format_resolution(2160) == "2160p"


class TestFormatFps:
    def test_none_returns_dash(self) -> None:
        assert _format_fps(None) == "—"

    def test_30fps(self) -> None:
        assert _format_fps(30) == "30"

    def test_60fps(self) -> None:
        assert _format_fps(60) == "60"


class TestBuildChoiceLabel:
    def test_contains_all_fields(self) -> None:
        fmt = _fmt(height=1080, fps=30, ext="mp4", filesize=50_000_000)
        label = _build_choice_label(0, fmt)
        assert "1080p" in label
        assert "30fps" in label
        assert "mp4" in label
        assert "MB" in label

    def test_unknown_filesize(self) -> None:
        fmt = _fmt(filesize=None)
        label = _build_choice_label(0, fmt)
        assert "Unknown" in label

    def test_index_one_based_display(self) -> None:
        label = _build_choice_label(0, _fmt())
        assert label.strip().startswith("1.")

    def test_second_item(self) -> None:
        label = _build_choice_label(1, _fmt())
        assert "2." in label


# ---------------------------------------------------------------------------
# prompt_format_selection — selection mapping
# ---------------------------------------------------------------------------

class TestPromptFormatSelection:
    """Test the logical mapping from user selection to format_id.

    ``questionary.select().ask()`` is mocked to return a known value
    without requiring a real terminal.
    """

    @patch("ytd_wrap.cli.format_prompt._import_questionary")
    def test_returns_selected_format_id(self, mock_q: MagicMock) -> None:
        questionary_mod = MagicMock()
        questionary_mod.Choice = _real_choice_class()
        questionary_mod.select.return_value.ask.return_value = "248"
        mock_q.return_value = questionary_mod

        formats = [
            _fmt(format_id="137", height=1080),
            _fmt(format_id="248", height=1080, ext="webm"),
        ]
        with patch(
            "ytd_wrap.cli.format_prompt._import_rich_table",
            return_value=_real_table_class(),
        ):
            result = prompt_format_selection(_meta(), formats)
        assert result == "248"

    @patch("ytd_wrap.cli.format_prompt._import_questionary")
    def test_single_format(self, mock_q: MagicMock) -> None:
        questionary_mod = MagicMock()
        questionary_mod.Choice = _real_choice_class()
        questionary_mod.select.return_value.ask.return_value = "137"
        mock_q.return_value = questionary_mod

        with patch(
            "ytd_wrap.cli.format_prompt._import_rich_table",
            return_value=_real_table_class(),
        ):
            result = prompt_format_selection(_meta(), [_fmt(format_id="137")])
        assert result == "137"

    @patch("ytd_wrap.cli.format_prompt._import_questionary")
    def test_none_selection_raises_format_selection_error(
        self, mock_q: MagicMock,
    ) -> None:
        questionary_mod = MagicMock()
        questionary_mod.Choice = _real_choice_class()
        questionary_mod.select.return_value.ask.return_value = None
        mock_q.return_value = questionary_mod

        with patch(
            "ytd_wrap.cli.format_prompt._import_rich_table",
            return_value=_real_table_class(),
        ):
            with pytest.raises(FormatSelectionError, match="No format selected"):
                prompt_format_selection(_meta(), [_fmt()])

    @patch("ytd_wrap.cli.format_prompt._import_questionary")
    def test_choices_built_correctly(self, mock_q: MagicMock) -> None:
        """Verify questionary.select is called with one choice per format."""
        questionary_mod = MagicMock()
        questionary_mod.Choice = _real_choice_class()
        questionary_mod.select.return_value.ask.return_value = "137"
        mock_q.return_value = questionary_mod

        formats = [
            _fmt(format_id="137", height=1080),
            _fmt(format_id="248", height=720),
            _fmt(format_id="399", height=480),
        ]
        with patch(
            "ytd_wrap.cli.format_prompt._import_rich_table",
            return_value=_real_table_class(),
        ):
            prompt_format_selection(_meta(), formats)

        call_kwargs = questionary_mod.select.call_args
        choices = call_kwargs[1].get("choices") or call_kwargs[0][1]
        assert len(choices) == 3

    @patch("ytd_wrap.cli.format_prompt._import_questionary")
    def test_metadata_with_no_duration(self, mock_q: MagicMock) -> None:
        """No crash when duration is None."""
        questionary_mod = MagicMock()
        questionary_mod.Choice = _real_choice_class()
        questionary_mod.select.return_value.ask.return_value = "137"
        mock_q.return_value = questionary_mod

        with patch(
            "ytd_wrap.cli.format_prompt._import_rich_table",
            return_value=_real_table_class(),
        ):
            result = prompt_format_selection(_meta(duration=None), [_fmt()])
        assert result == "137"


# ---------------------------------------------------------------------------
# _handle_download integration (mocked end-to-end)
# ---------------------------------------------------------------------------

class TestHandleDownloadIntegration:
    """Test the full CLI wiring from URL → format selection.

    All service, provider, and download layers are mocked so no
    network or terminal interaction occurs.
    """

    @patch("ytd_wrap.cli.progress.RichProgressHook")
    @patch("ytd_wrap.core.download_service.DownloadService")
    @patch("ytd_wrap.infra.ytdlp_download_provider.YtDlpDownloadProvider")
    @patch("ytd_wrap.cli.format_prompt.prompt_format_selection", return_value="137")
    @patch("ytd_wrap.core.metadata_service.MetadataService")
    @patch("ytd_wrap.infra.ytdlp_provider.YtDlpMetadataProvider")
    def test_happy_path(
        self,
        mock_meta_provider_cls: MagicMock,
        mock_meta_service_cls: MagicMock,
        mock_prompt: MagicMock,
        mock_dl_provider_cls: MagicMock,
        mock_dl_service_cls: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        from ytd_wrap.cli.app import main

        svc = mock_meta_service_cls.return_value
        svc.extract_metadata.return_value = _meta()
        svc.get_adaptive_video_formats.return_value = FormatCollection(
            formats=(_fmt(format_id="137"),),
        )

        hook_instance = MagicMock()
        mock_progress_cls.return_value.__enter__ = MagicMock(return_value=hook_instance)
        mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)

        code = main(["https://www.youtube.com/watch?v=abc123"])
        assert code == exit_codes.SUCCESS
        svc.extract_metadata.assert_called_once()
        svc.get_adaptive_video_formats.assert_called_once()
        mock_prompt.assert_called_once()

    @patch("ytd_wrap.core.metadata_service.MetadataService")
    @patch("ytd_wrap.infra.ytdlp_provider.YtDlpMetadataProvider")
    def test_format_selection_error_propagates(
        self,
        mock_provider_cls: MagicMock,
        mock_service_cls: MagicMock,
    ) -> None:
        from ytd_wrap.cli.app import main

        svc = mock_service_cls.return_value
        svc.extract_metadata.return_value = _meta()
        svc.get_adaptive_video_formats.side_effect = FormatSelectionError(
            "No adaptive video formats found."
        )

        with pytest.raises(FormatSelectionError):
            main(["https://www.youtube.com/watch?v=abc123"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _real_choice_class() -> type:
    """Return a minimal Choice-like class for mocking questionary.Choice."""

    class FakeChoice:
        def __init__(self, title: str, value: str) -> None:
            self.title = title
            self.value = value

    return FakeChoice


def _real_table_class() -> type:
    """Return a minimal Table-like class for tests without rich."""

    class FakeTable:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

        def add_column(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

        def add_row(self, *args: object, **kwargs: object) -> None:
            _ = args, kwargs

    return FakeTable
