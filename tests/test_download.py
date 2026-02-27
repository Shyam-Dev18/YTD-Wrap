"""Tests for the download pipeline (Phase 4).

All tests mock the :class:`DownloadProvider` — no actual downloads
occur and no internet access is required.

Coverage:
* Format-spec construction.
* Provider delegation.
* Exception wrapping (provider errors → DownloadFailedError).
* CLI integration wiring with mocked services.
* Progress hook callback handling.
"""

from __future__ import annotations

import importlib.util
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from ytd_wrap.cli import exit_codes
from ytd_wrap.core.download_service import DownloadService
from ytd_wrap.core.models import FormatCollection, VideoFormat, VideoMetadata
from ytd_wrap.exceptions import DownloadFailedError, FormatSelectionError


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
# DownloadService — format spec
# ---------------------------------------------------------------------------

class TestBuildFormatSpec:
    def test_mp4_branch_prefers_m4a(self) -> None:
        assert (
            DownloadService.build_format_spec("137", "mp4")
            == "137+bestaudio[ext=m4a]/best[ext=mp4]"
        )

    def test_webm_branch_prefers_webm_audio(self) -> None:
        assert (
            DownloadService.build_format_spec("248", "webm")
            == "248+bestaudio[ext=webm]/best[ext=webm]/best"
        )

    def test_fallback_branch_unknown_ext(self) -> None:
        result = DownloadService.build_format_spec("399", "mkv")
        assert "+bestaudio/best" in result
        assert result.startswith("399")

    def test_ext_is_case_insensitive(self) -> None:
        assert (
            DownloadService.build_format_spec("137", "MP4")
            == "137+bestaudio[ext=m4a]/best[ext=mp4]"
        )


# ---------------------------------------------------------------------------
# DownloadService — delegation
# ---------------------------------------------------------------------------

class TestDownloadServiceDelegation:
    def test_calls_provider_with_format_spec(self) -> None:
        provider = MagicMock()
        svc = DownloadService(provider)
        svc.download("https://youtube.com/watch?v=x", "137", "mp4")

        provider.download.assert_called_once_with(
            "https://youtube.com/watch?v=x",
            "137+bestaudio[ext=m4a]/best[ext=mp4]",
            progress_callback=None,
        )

    def test_forwards_progress_callback(self) -> None:
        provider = MagicMock()
        svc = DownloadService(provider)
        callback = MagicMock()
        svc.download(
            "https://youtube.com/watch?v=x", "137", "mp4", progress_callback=callback,
        )

        provider.download.assert_called_once_with(
            "https://youtube.com/watch?v=x",
            "137+bestaudio[ext=m4a]/best[ext=mp4]",
            progress_callback=callback,
        )


# ---------------------------------------------------------------------------
# DownloadService — exception mapping
# ---------------------------------------------------------------------------

class TestDownloadServiceExceptions:
    def test_download_failed_error_propagates(self) -> None:
        provider = MagicMock()
        provider.download.side_effect = DownloadFailedError("network error")
        svc = DownloadService(provider)

        with pytest.raises(DownloadFailedError, match="network error"):
            svc.download("https://youtube.com/watch?v=x", "137", "mp4")

    def test_unexpected_error_wrapped(self) -> None:
        provider = MagicMock()
        provider.download.side_effect = RuntimeError("kaboom")
        svc = DownloadService(provider)

        with pytest.raises(DownloadFailedError, match="Unexpected"):
            svc.download("https://youtube.com/watch?v=x", "137", "mp4")

    def test_unexpected_error_chained(self) -> None:
        provider = MagicMock()
        original = RuntimeError("root cause")
        provider.download.side_effect = original
        svc = DownloadService(provider)

        with pytest.raises(DownloadFailedError) as exc_info:
            svc.download("https://youtube.com/watch?v=x", "137", "mp4")
        assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# Progress hook callback
# ---------------------------------------------------------------------------

class TestProgressHookCallback:
    """Test the RichProgressHook as a plain callback (no terminal)."""

    @pytest.mark.skipif(
        importlib.util.find_spec("rich") is None,
        reason="rich not installed",
    )
    def test_downloading_status_accepted(self) -> None:
        """The hook should not crash on a downloading dict."""
        from ytd_wrap.cli.progress import RichProgressHook

        hook = RichProgressHook()
        hook.start()
        try:
            hook({
                "status": "downloading",
                "downloaded_bytes": 1024,
                "total_bytes": 10240,
                "filename": "test.mp4",
            })
        finally:
            hook.stop()

    @pytest.mark.skipif(
        importlib.util.find_spec("rich") is None,
        reason="rich not installed",
    )
    def test_finished_status_accepted(self) -> None:
        from ytd_wrap.cli.progress import RichProgressHook

        hook = RichProgressHook()
        hook.start()
        try:
            # Simulate a download then finish
            hook({
                "status": "downloading",
                "downloaded_bytes": 5000,
                "total_bytes": 10000,
                "filename": "test.mp4",
            })
            hook({
                "status": "finished",
            })
        finally:
            hook.stop()

    @pytest.mark.skipif(
        importlib.util.find_spec("rich") is None,
        reason="rich not installed",
    )
    def test_not_started_ignores_calls(self) -> None:
        """No crash when called before start()."""
        from ytd_wrap.cli.progress import RichProgressHook

        hook = RichProgressHook()
        hook({"status": "downloading", "downloaded_bytes": 100})

    @pytest.mark.skipif(
        importlib.util.find_spec("rich") is None,
        reason="rich not installed",
    )
    def test_stop_is_idempotent(self) -> None:
        from ytd_wrap.cli.progress import RichProgressHook

        hook = RichProgressHook()
        hook.start()
        hook.stop()
        hook.stop()  # second call should not raise

    @pytest.mark.skipif(
        importlib.util.find_spec("rich") is None,
        reason="rich not installed",
    )
    def test_context_manager(self) -> None:
        from ytd_wrap.cli.progress import RichProgressHook

        with RichProgressHook() as hook:
            hook({"status": "downloading", "downloaded_bytes": 100,
                  "total_bytes": 1000, "filename": "x.mp4"})
        # After exit, hook should be stopped
        assert not hook._started

    @pytest.mark.skipif(
        importlib.util.find_spec("rich") is None,
        reason="rich not installed",
    )
    def test_unknown_status_no_crash(self) -> None:
        from ytd_wrap.cli.progress import RichProgressHook

        with RichProgressHook() as hook:
            hook({"status": "unknown_event"})

    @pytest.mark.skipif(
        importlib.util.find_spec("rich") is None,
        reason="rich not installed",
    )
    def test_missing_total_bytes_uses_estimate(self) -> None:
        from ytd_wrap.cli.progress import RichProgressHook

        with RichProgressHook() as hook:
            hook({
                "status": "downloading",
                "downloaded_bytes": 500,
                "total_bytes": None,
                "total_bytes_estimate": 5000,
                "filename": "test.mp4",
            })


# ---------------------------------------------------------------------------
# Progress hook utility
# ---------------------------------------------------------------------------

class TestSafeInt:
    def test_none(self) -> None:
        from ytd_wrap.cli.progress import _safe_int
        assert _safe_int(None) is None

    def test_int(self) -> None:
        from ytd_wrap.cli.progress import _safe_int
        assert _safe_int(1024) == 1024

    def test_float(self) -> None:
        from ytd_wrap.cli.progress import _safe_int
        assert _safe_int(1024.5) == 1024

    def test_string_number(self) -> None:
        from ytd_wrap.cli.progress import _safe_int
        assert _safe_int("1024") == 1024

    def test_bad_string(self) -> None:
        from ytd_wrap.cli.progress import _safe_int
        assert _safe_int("not_a_number") is None


# ---------------------------------------------------------------------------
# CLI integration (mocked end-to-end)
# ---------------------------------------------------------------------------

class TestHandleDownloadWithDownload:
    """Verify the full CLI wiring from URL → download."""

    @patch("ytd_wrap.cli.progress.RichProgressHook")
    @patch("ytd_wrap.core.download_service.DownloadService")
    @patch("ytd_wrap.cli.format_prompt.prompt_format_selection", return_value="137")
    @patch("ytd_wrap.core.metadata_service.MetadataService")
    @patch("ytd_wrap.infra.ytdlp_provider.YtDlpMetadataProvider")
    @patch("ytd_wrap.infra.ytdlp_download_provider.YtDlpDownloadProvider")
    def test_happy_path(
        self,
        mock_dl_provider_cls: MagicMock,
        mock_meta_provider_cls: MagicMock,
        mock_meta_svc_cls: MagicMock,
        mock_prompt: MagicMock,
        mock_dl_svc_cls: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        from ytd_wrap.cli.app import main

        # Wire metadata service mock
        svc = mock_meta_svc_cls.return_value
        svc.extract_metadata.return_value = _meta()
        svc.get_adaptive_video_formats.return_value = FormatCollection(
            formats=(_fmt(format_id="137"),),
        )

        # Wire progress hook context manager
        hook_instance = MagicMock()
        mock_progress_cls.return_value.__enter__ = MagicMock(return_value=hook_instance)
        mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)

        code = main(["https://www.youtube.com/watch?v=abc123"])
        assert code == exit_codes.SUCCESS
        mock_dl_svc_cls.return_value.download.assert_called_once_with(
            "https://www.youtube.com/watch?v=abc123",
            "137",
            "mp4",
            progress_callback=hook_instance,
        )

    @patch("ytd_wrap.cli.progress.RichProgressHook")
    @patch("ytd_wrap.core.download_service.DownloadService")
    @patch("ytd_wrap.cli.format_prompt.prompt_format_selection", return_value="137")
    @patch("ytd_wrap.core.metadata_service.MetadataService")
    @patch("ytd_wrap.infra.ytdlp_provider.YtDlpMetadataProvider")
    @patch("ytd_wrap.infra.ytdlp_download_provider.YtDlpDownloadProvider")
    def test_download_failed_error_propagates(
        self,
        mock_dl_provider_cls: MagicMock,
        mock_meta_provider_cls: MagicMock,
        mock_meta_svc_cls: MagicMock,
        mock_prompt: MagicMock,
        mock_dl_svc_cls: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        from ytd_wrap.cli.app import main

        svc = mock_meta_svc_cls.return_value
        svc.extract_metadata.return_value = _meta()
        svc.get_adaptive_video_formats.return_value = FormatCollection(
            formats=(_fmt(format_id="137"),),
        )

        hook_instance = MagicMock()
        mock_progress_cls.return_value.__enter__ = MagicMock(return_value=hook_instance)
        mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_dl_svc_cls.return_value.download.side_effect = DownloadFailedError(
            "download broke"
        )

        with pytest.raises(DownloadFailedError):
            main(["https://www.youtube.com/watch?v=abc123"])

    @patch("ytd_wrap.cli.progress.RichProgressHook")
    @patch("ytd_wrap.core.download_service.DownloadService")
    @patch("ytd_wrap.cli.format_prompt.prompt_format_selection", return_value="999")
    @patch("ytd_wrap.core.metadata_service.MetadataService")
    @patch("ytd_wrap.infra.ytdlp_provider.YtDlpMetadataProvider")
    @patch("ytd_wrap.infra.ytdlp_download_provider.YtDlpDownloadProvider")
    def test_selected_format_unavailable_hint_includes_ytdlp_upgrade(
        self,
        mock_dl_provider_cls: MagicMock,
        mock_meta_provider_cls: MagicMock,
        mock_meta_svc_cls: MagicMock,
        mock_prompt: MagicMock,
        mock_dl_svc_cls: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        from ytd_wrap.cli.app import main

        svc = mock_meta_svc_cls.return_value
        svc.extract_metadata.return_value = _meta()
        svc.get_adaptive_video_formats.return_value = FormatCollection(
            formats=(_fmt(format_id="137"),),
        )

        hook_instance = MagicMock()
        mock_progress_cls.return_value.__enter__ = MagicMock(return_value=hook_instance)
        mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(FormatSelectionError) as exc_info:
            main(["https://www.youtube.com/watch?v=abc123"])

        hint = exc_info.value.hint
        assert hint is not None
        assert "Retry and choose a listed format." in hint
        assert "Also try updating yt-dlp:" in hint
        assert "pip install --upgrade yt-dlp" in hint
