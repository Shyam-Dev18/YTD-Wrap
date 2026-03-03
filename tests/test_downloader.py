"""Tests for ytd_wrap.core.downloader — download orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from ytd_wrap.core.downloader import build_ydl_opts, create_progress_hook, download
from ytd_wrap.utils.exceptions import (
    DownloadError,
    NetworkError,
    DiskFullError,
    UserCancelledError,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_ydl_cm(*, download_side_effect=None) -> MagicMock:
    """Build a mock yt_dlp.YoutubeDL context manager."""
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    if download_side_effect is not None:
        instance.download = MagicMock(side_effect=download_side_effect)
    else:
        instance.download = MagicMock(return_value=0)
    return instance


# ──────────────────────────────────────────────────────────────────────────────
# build_ydl_opts
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildYdlOpts:
    def _opts(self, format_id: str = "22", container: str = "mp4") -> dict:
        output_path = Path("/tmp/video.mp4")
        hook = MagicMock()
        return build_ydl_opts(format_id, output_path, container, hook)

    def test_contains_continuedl(self) -> None:
        opts = self._opts()
        assert opts["continuedl"] is True

    def test_retries_set(self) -> None:
        from ytd_wrap.constants import YTDLP_RETRIES
        opts = self._opts()
        assert opts["retries"] == YTDLP_RETRIES

    def test_fragment_retries_set(self) -> None:
        from ytd_wrap.constants import YTDLP_FRAGMENT_RETRIES
        opts = self._opts()
        assert opts["fragment_retries"] == YTDLP_FRAGMENT_RETRIES

    def test_socket_timeout_set(self) -> None:
        from ytd_wrap.constants import YTDLP_SOCKET_TIMEOUT
        opts = self._opts()
        assert opts["socket_timeout"] == YTDLP_SOCKET_TIMEOUT

    def test_quiet_mode(self) -> None:
        opts = self._opts()
        assert opts["quiet"] is True

    def test_progress_hook_included(self) -> None:
        hook = MagicMock()
        output_path = Path("/tmp/video.mp4")
        opts = build_ydl_opts("22", output_path, "mp4", hook)
        assert hook in opts["progress_hooks"]

    def test_format_id_in_selector(self) -> None:
        opts = self._opts(format_id="248")
        assert "248" in opts["format"]

    def test_merge_output_format_set(self) -> None:
        opts = self._opts(container="mkv")
        assert opts.get("merge_output_format") == "mkv"

    def test_outtmpl_uses_output_path(self) -> None:
        output_path = Path("/tmp/myvideo.mp4")
        opts = build_ydl_opts("22", output_path, "mp4", MagicMock())
        assert "/tmp/myvideo" in opts["outtmpl"] or "myvideo" in opts["outtmpl"]

    def test_uses_native_hls_when_requested(self) -> None:
        output_path = Path("/tmp/video.mp4")
        opts = build_ydl_opts("22", output_path, "mp4", MagicMock(), use_native_hls=True)
        assert opts["hls_prefer_native"] is True
        assert "downloader" not in opts

    def test_forces_ffmpeg_hls_when_not_native(self) -> None:
        output_path = Path("/tmp/video.mp4")
        opts = build_ydl_opts("22", output_path, "mp4", MagicMock(), use_native_hls=False)
        assert opts["hls_prefer_native"] is False
        assert opts["downloader"] == {"m3u8": "ffmpeg"}

    def test_keeps_source_container_when_convert_disabled(self) -> None:
        output_path = Path("/tmp/video.mp4")
        opts = build_ydl_opts(
            "22",
            output_path,
            "mp4",
            MagicMock(),
            use_native_hls=True,
            convert_container=False,
        )
        assert "merge_output_format" not in opts
        assert "postprocessors" not in opts


# ──────────────────────────────────────────────────────────────────────────────
# download — success
# ──────────────────────────────────────────────────────────────────────────────

class TestDownloadSuccess:
    def test_returns_path_object(self, tmp_path: Path) -> None:
        # Create the expected output file so _find_output_file can find it
        title = "My Video"
        from ytd_wrap.utils.paths import sanitize_filename
        clean = sanitize_filename(title)
        expected = tmp_path / f"{clean}.mp4"
        expected.touch()

        mock_ydl = _make_ydl_cm()
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = download("https://youtube.com/watch?v=abc", "22", title, tmp_path, "mp4", MagicMock())

        assert isinstance(result, Path)

    def test_calls_ydl_download(self, tmp_path: Path) -> None:
        mock_ydl = _make_ydl_cm()
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            download("https://youtube.com/watch?v=abc", "22", "My Video", tmp_path, "mp4", MagicMock())
        mock_ydl.download.assert_called_once_with(["https://youtube.com/watch?v=abc"])

    def test_direct_stream_uses_native_hls_opts(self, tmp_path: Path) -> None:
        mock_ydl = _make_ydl_cm()
        with (
            patch("yt_dlp.YoutubeDL", return_value=mock_ydl),
            patch("ytd_wrap.core.resolver.is_direct_stream", return_value=True),
            patch("ytd_wrap.core.downloader.build_ydl_opts", wraps=build_ydl_opts) as mock_build,
        ):
            download("https://cdn.example.com/stream.m3u8", "best", "My Video", tmp_path, "mp4", MagicMock())
        assert mock_build.call_args.kwargs["use_native_hls"] is True
        assert mock_build.call_args.kwargs["convert_container"] is False


# ──────────────────────────────────────────────────────────────────────────────
# download — error mapping
# ──────────────────────────────────────────────────────────────────────────────

class TestDownloadErrors:
    def _run(self, error_msg: str, tmp_path: Path) -> None:
        import yt_dlp.utils
        exc = yt_dlp.utils.DownloadError(error_msg)
        mock_ydl = _make_ydl_cm(download_side_effect=exc)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            download("https://youtube.com/watch?v=abc", "22", "title", tmp_path, "mp4", MagicMock())

    def test_timeout_raises_network_error(self, tmp_path: Path) -> None:
        with pytest.raises((NetworkError, DownloadError)):
            self._run("Connection timed out", tmp_path)

    def test_http_403_raises_download_error(self, tmp_path: Path) -> None:
        with pytest.raises(DownloadError):
            self._run("HTTP Error 403: Forbidden", tmp_path)

    def test_no_space_raises_disk_full_error(self, tmp_path: Path) -> None:
        with pytest.raises(DiskFullError):
            self._run("No space left on device", tmp_path)

    def test_generic_error_raises_download_error(self, tmp_path: Path) -> None:
        with pytest.raises(DownloadError):
            self._run("Something completely unexpected happened", tmp_path)


# ──────────────────────────────────────────────────────────────────────────────
# download — KeyboardInterrupt cleanup
# ──────────────────────────────────────────────────────────────────────────────

class TestDownloadKeyboardInterrupt:
    def test_raises_user_cancelled(self, tmp_path: Path) -> None:
        mock_ydl = _make_ydl_cm(download_side_effect=KeyboardInterrupt)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(UserCancelledError):
                download("https://youtube.com/watch?v=abc", "22", "title", tmp_path, "mp4", MagicMock())

    def test_removes_partial_file_on_cancel(self, tmp_path: Path) -> None:
        from ytd_wrap.utils.paths import sanitize_filename
        clean = sanitize_filename("title")
        partial = tmp_path / f"{clean}.part"
        partial.write_bytes(b"partial")

        mock_ydl = _make_ydl_cm(download_side_effect=KeyboardInterrupt)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(UserCancelledError):
                download("https://youtube.com/watch?v=abc", "22", "title", tmp_path, "mp4", MagicMock())

        assert not partial.exists()


# ──────────────────────────────────────────────────────────────────────────────
# create_progress_hook
# ──────────────────────────────────────────────────────────────────────────────

class TestCreateProgressHook:
    def _make_progress(self, completed: float = 0.0, total: float = 100.0):
        """Return a minimal rich.progress.Progress-like mock."""
        progress = MagicMock()
        task = MagicMock()
        task.completed = completed
        task.total = total
        progress.tasks = {0: task}
        return progress

    def test_downloading_updates_progress(self) -> None:
        progress = self._make_progress()
        hook = create_progress_hook(progress, 0)
        hook({
            "status": "downloading",
            "downloaded_bytes": 512_000,
            "total_bytes": 1_000_000,
            "speed": 1_048_576,
            "eta": 0,
        })
        progress.update.assert_called_once()
        call_kwargs = progress.update.call_args.kwargs
        assert call_kwargs.get("completed") == 512_000

    def test_finished_marks_complete(self) -> None:
        progress = self._make_progress(total=1_000_000.0)
        hook = create_progress_hook(progress, 0)
        hook({"status": "finished", "total_bytes": 1_000_000})
        progress.update.assert_called_once()

    def test_error_status_handled(self) -> None:
        progress = self._make_progress()
        hook = create_progress_hook(progress, 0)
        hook({"status": "error"})
        progress.update.assert_called_once()

    def test_downloading_without_speed_or_eta(self) -> None:
        progress = self._make_progress()
        hook = create_progress_hook(progress, 0)
        # Should not raise
        hook({
            "status": "downloading",
            "downloaded_bytes": 100,
            "total_bytes": 1000,
        })
        progress.update.assert_called_once()

    def test_downloading_updates_description_with_speed(self) -> None:
        progress = self._make_progress()
        hook = create_progress_hook(progress, 0)
        hook({
            "status": "downloading",
            "downloaded_bytes": 100_000,
            "total_bytes": 1_000_000,
            "speed": 2_097_152,   # 2 MB/s
            "eta": 5,
        })
        call_kwargs = progress.update.call_args.kwargs
        desc = call_kwargs.get("description", "")
        assert "MB/s" in desc
