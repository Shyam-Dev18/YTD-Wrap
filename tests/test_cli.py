"""Integration tests for ytd_wrap.cli -- uses click.testing.CliRunner.

Design: All external side-effects (network, yt-dlp, filesystem, rich output)
are mocked.  Rich Console is module-level and does NOT write to CliRunner's
captured stdout, so we patch every print_* / get_spinner function imported into
ytd_wrap.cli and assert on mock call-args.  Exit codes are the primary signal.
"""

from __future__ import annotations

from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ytd_wrap import __version__
from ytd_wrap.cli import main
from ytd_wrap.utils.exceptions import (
    DiskFullError,
    DownloadError,
    ExtractionError,
    NetworkError,
    UserCancelledError,
)


# ---------------------------------------------------------------------------
# Fixtures & shared helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _make_progress_cm() -> MagicMock:
    """Mock Progress context manager: add_task returns 0, tasks[0] exists."""
    progress = MagicMock()
    progress.__enter__ = MagicMock(return_value=progress)
    progress.__exit__ = MagicMock(return_value=False)
    progress.tasks = {0: MagicMock(completed=0, total=100)}
    progress.add_task = MagicMock(return_value=0)
    return progress


def _spinner_cm() -> MagicMock:
    """Mock Status context manager (for get_spinner)."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


_FAKE_METADATA = {
    "title": "Test Video",
    "uploader": "TestUser",
    "duration": 120,
    "webpage_url": "https://youtube.com/watch?v=test",
    "thumbnail": None,
}

_FAKE_FORMAT = {
    "format_id": "22",
    "resolution": "1080p",
    "vcodec": "avc1.42001f",
    "acodec": "mp4a.40.2",
    "filesize": 50_000_000,
    "ext": "mp4",
}

_FAKE_FORMATS = [_FAKE_FORMAT]


# ---------------------------------------------------------------------------
# Patch helper
# ---------------------------------------------------------------------------

@contextmanager
def _apply_patches(patches: dict):
    """Apply a dict of {dotted_target: value_or_mock} patches simultaneously.

    If the value is already a callable Mock it is used as ``new=``.
    Otherwise it is wrapped in ``MagicMock(return_value=value)``.
    """
    with ExitStack() as stack:
        for target, value in patches.items():
            if isinstance(value, MagicMock) or (
                callable(value) and not isinstance(value, (type, bool, int, float, str, Path, list, dict))
            ):
                stack.enter_context(patch(target, new=value))
            else:
                stack.enter_context(patch(target, MagicMock(return_value=value)))
        yield


def _ui_patches() -> dict:
    """Return patches for all UI functions that use rich (safe no-ops)."""
    return {
        "ytd_wrap.cli.print_banner":          MagicMock(),
        "ytd_wrap.cli.print_version":         MagicMock(),
        "ytd_wrap.cli.print_doctor_table":    MagicMock(),
        "ytd_wrap.cli.print_formats_table":   MagicMock(),
        "ytd_wrap.cli.print_update_notice":   MagicMock(),
        "ytd_wrap.cli.print_download_start":  MagicMock(),
        "ytd_wrap.cli.print_success":         MagicMock(),
        "ytd_wrap.cli.print_error":           MagicMock(),
        "ytd_wrap.cli.print_ffmpeg_missing":  MagicMock(),
        "ytd_wrap.cli.get_spinner":           MagicMock(return_value=_spinner_cm()),
    }


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_flag_exits_zero(self, runner: CliRunner) -> None:
        mock_pv = MagicMock()
        with patch("ytd_wrap.cli.print_version", mock_pv):
            result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_version_flag_calls_print_version(self, runner: CliRunner) -> None:
        mock_pv = MagicMock()
        with patch("ytd_wrap.cli.print_version", mock_pv):
            runner.invoke(main, ["--version"])
        mock_pv.assert_called_once_with(__version__)

    def test_short_version_flag(self, runner: CliRunner) -> None:
        mock_pv = MagicMock()
        with patch("ytd_wrap.cli.print_version", mock_pv):
            result = runner.invoke(main, ["-V"])
        assert result.exit_code == 0
        mock_pv.assert_called_once_with(__version__)


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------

class TestHelp:
    def test_help_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_help_mentions_url(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert "URL" in result.output or "url" in result.output.lower()

    def test_help_lists_doctor(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert "doctor" in result.output

    def test_no_args_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "Usage" in result.output or "usage" in result.output.lower()


# ---------------------------------------------------------------------------
# Invalid URL
# ---------------------------------------------------------------------------

class TestInvalidUrl:
    def test_invalid_url_exit_code_1(self, runner: CliRunner) -> None:
        mock_pe = MagicMock()
        with (
            patch("ytd_wrap.cli.is_valid_url", return_value=False),
            patch("ytd_wrap.cli.print_error", mock_pe),
        ):
            result = runner.invoke(main, ["not-a-url"])
        assert result.exit_code == 1

    def test_invalid_url_calls_print_error(self, runner: CliRunner) -> None:
        mock_pe = MagicMock()
        with (
            patch("ytd_wrap.cli.is_valid_url", return_value=False),
            patch("ytd_wrap.cli.print_error", mock_pe),
        ):
            runner.invoke(main, ["not-a-url"])
        mock_pe.assert_called_once()
        # first positional arg should mention 'Invalid'
        assert "Invalid" in mock_pe.call_args.args[0] or "invalid" in mock_pe.call_args.args[0].lower()


# ---------------------------------------------------------------------------
# ffmpeg missing
# ---------------------------------------------------------------------------

class TestFfmpegMissing:
    def test_ffmpeg_missing_exits_1(self, runner: CliRunner) -> None:
        mock_pfm = MagicMock()
        with (
            patch("ytd_wrap.cli.is_valid_url", return_value=True),
            patch("ytd_wrap.cli.check_ffmpeg", return_value=False),
            patch("ytd_wrap.cli.get_ffmpeg_install_command", return_value="brew install ffmpeg"),
            patch("ytd_wrap.cli.print_ffmpeg_missing", mock_pfm),
        ):
            result = runner.invoke(main, ["https://youtube.com/watch?v=abc"])
        assert result.exit_code == 1

    def test_ffmpeg_missing_calls_print_ffmpeg_missing(self, runner: CliRunner) -> None:
        mock_pfm = MagicMock()
        with (
            patch("ytd_wrap.cli.is_valid_url", return_value=True),
            patch("ytd_wrap.cli.check_ffmpeg", return_value=False),
            patch("ytd_wrap.cli.get_ffmpeg_install_command", return_value="brew install ffmpeg"),
            patch("ytd_wrap.cli.print_ffmpeg_missing", mock_pfm),
        ):
            runner.invoke(main, ["https://youtube.com/watch?v=abc"])
        mock_pfm.assert_called_once()


# ---------------------------------------------------------------------------
# doctor subcommand
# ---------------------------------------------------------------------------

class TestDoctorCommand:
    _CHECKS_OK = {
        "ffmpeg": True, "ytdlp": True,
        "python_ok": True, "python_version": "3.11.0",
    }

    def test_doctor_exits_zero(self, runner: CliRunner) -> None:
        with (
            patch("ytd_wrap.cli.run_all_checks", return_value=self._CHECKS_OK),
            patch("ytd_wrap.cli.print_doctor_table"),
        ):
            result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_calls_run_all_checks(self, runner: CliRunner) -> None:
        mock_rac = MagicMock(return_value=self._CHECKS_OK)
        with (
            patch("ytd_wrap.cli.run_all_checks", mock_rac),
            patch("ytd_wrap.cli.print_doctor_table"),
        ):
            runner.invoke(main, ["doctor"])
        mock_rac.assert_called_once()

    def test_doctor_calls_print_doctor_table(self, runner: CliRunner) -> None:
        mock_pdt = MagicMock()
        with (
            patch("ytd_wrap.cli.run_all_checks", return_value=self._CHECKS_OK),
            patch("ytd_wrap.cli.print_doctor_table", mock_pdt),
        ):
            runner.invoke(main, ["doctor"])
        mock_pdt.assert_called_once_with(self._CHECKS_OK)

    def test_doctor_shows_ffmpeg_hint_when_missing(self, runner: CliRunner) -> None:
        checks = {**self._CHECKS_OK, "ffmpeg": False}
        mock_pfm = MagicMock()
        with (
            patch("ytd_wrap.cli.run_all_checks", return_value=checks),
            patch("ytd_wrap.cli.print_doctor_table"),
            patch("ytd_wrap.cli.get_ffmpeg_install_command", return_value="brew install ffmpeg"),
            patch("ytd_wrap.cli.print_ffmpeg_missing", mock_pfm),
        ):
            runner.invoke(main, ["doctor"])
        mock_pfm.assert_called_once()

    def test_doctor_no_ffmpeg_hint_when_present(self, runner: CliRunner) -> None:
        mock_pfm = MagicMock()
        with (
            patch("ytd_wrap.cli.run_all_checks", return_value=self._CHECKS_OK),
            patch("ytd_wrap.cli.print_doctor_table"),
            patch("ytd_wrap.cli.print_ffmpeg_missing", mock_pfm),
        ):
            runner.invoke(main, ["doctor"])
        mock_pfm.assert_not_called()


# ---------------------------------------------------------------------------
# Full social download flow
# ---------------------------------------------------------------------------

class TestSocialDownloadFlow:
    def _patches(self, tmp_path: Path, *, download_val=None) -> dict:
        final_file = tmp_path / "Test_Video.mp4"
        final_file.touch()
        return {
            **_ui_patches(),
            "ytd_wrap.cli.is_valid_url":              True,
            "ytd_wrap.cli.check_ffmpeg":               True,
            "ytd_wrap.cli.check_for_updates":          [],
            "ytd_wrap.cli.detect_url_type":            "social",
            "ytd_wrap.cli.extract_metadata":           _FAKE_METADATA,
            "ytd_wrap.cli.extract_formats":            _FAKE_FORMATS,
            "ytd_wrap.cli.select_format":              _FAKE_FORMAT,
            "ytd_wrap.cli.determine_output_container": "mp4",
            "ytd_wrap.cli.get_download_dir":           tmp_path,
            "ytd_wrap.cli.download":                   download_val or final_file,
            "ytd_wrap.cli._make_progress":             _make_progress_cm(),
        }

    def test_social_flow_exits_zero(self, runner: CliRunner, tmp_path: Path) -> None:
        with _apply_patches(self._patches(tmp_path)):
            result = runner.invoke(main, ["https://youtube.com/watch?v=test"])
        assert result.exit_code == 0

    def test_social_flow_calls_extract_metadata(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._patches(tmp_path)
        mock_meta = MagicMock(return_value=_FAKE_METADATA)
        patches["ytd_wrap.cli.extract_metadata"] = mock_meta
        with _apply_patches(patches):
            runner.invoke(main, ["https://youtube.com/watch?v=test"])
        mock_meta.assert_called_once_with("https://youtube.com/watch?v=test")

    def test_social_flow_calls_select_format(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._patches(tmp_path)
        mock_sel = MagicMock(return_value=_FAKE_FORMAT)
        patches["ytd_wrap.cli.select_format"] = mock_sel
        with _apply_patches(patches):
            runner.invoke(main, ["https://youtube.com/watch?v=test"])
        mock_sel.assert_called_once()

    def test_social_flow_calls_download_with_format_id(self, runner: CliRunner, tmp_path: Path) -> None:
        final_file = tmp_path / "Test_Video.mp4"
        final_file.touch()
        mock_dl = MagicMock(return_value=final_file)
        patches = self._patches(tmp_path, download_val=final_file)
        patches["ytd_wrap.cli.download"] = mock_dl
        with _apply_patches(patches):
            runner.invoke(main, ["https://youtube.com/watch?v=test"])
        mock_dl.assert_called_once()
        args = mock_dl.call_args.args
        assert args[0] == "https://youtube.com/watch?v=test"
        assert args[1] == "22"  # format_id from _FAKE_FORMAT

    def test_social_flow_calls_print_success(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._patches(tmp_path)
        mock_ps = MagicMock()
        patches["ytd_wrap.cli.print_success"] = mock_ps
        with _apply_patches(patches):
            runner.invoke(main, ["https://youtube.com/watch?v=test"])
        mock_ps.assert_called_once()

    def test_social_flow_shows_banner(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._patches(tmp_path)
        mock_pb = MagicMock()
        patches["ytd_wrap.cli.print_banner"] = mock_pb
        with _apply_patches(patches):
            runner.invoke(main, ["https://youtube.com/watch?v=test"])
        mock_pb.assert_called_once()


# ---------------------------------------------------------------------------
# Direct / unknown flow
# ---------------------------------------------------------------------------

class TestDirectDownloadFlow:
    def _patches(self, tmp_path: Path) -> dict:
        final_file = tmp_path / "video.mp4"
        final_file.touch()
        return {
            **_ui_patches(),
            "ytd_wrap.cli.is_valid_url":              True,
            "ytd_wrap.cli.check_ffmpeg":               True,
            "ytd_wrap.cli.check_for_updates":          [],
            "ytd_wrap.cli.detect_url_type":            "direct",
            "ytd_wrap.cli.extract_metadata":           _FAKE_METADATA,
            "ytd_wrap.cli.extract_formats":            _FAKE_FORMATS,
            "ytd_wrap.cli.select_best_format":         _FAKE_FORMAT,
            "ytd_wrap.cli.determine_output_container": "mp4",
            "ytd_wrap.cli.get_download_dir":           tmp_path,
            "ytd_wrap.cli.download":                   final_file,
            "ytd_wrap.cli._make_progress":             _make_progress_cm(),
        }

    def test_direct_flow_exits_zero(self, runner: CliRunner, tmp_path: Path) -> None:
        with _apply_patches(self._patches(tmp_path)):
            result = runner.invoke(main, ["https://cdn.example.com/stream.m3u8"])
        assert result.exit_code == 0

    def test_direct_flow_does_not_prompt_for_format(self, runner: CliRunner, tmp_path: Path) -> None:
        """select_format (interactive) must NOT be called for direct URLs."""
        mock_sel = MagicMock()
        patches = self._patches(tmp_path)
        patches["ytd_wrap.cli.select_format"] = mock_sel
        with _apply_patches(patches):
            runner.invoke(main, ["https://cdn.example.com/stream.m3u8"])
        mock_sel.assert_not_called()

    def test_direct_flow_falls_back_on_extraction_error(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        final_file = tmp_path / "video.mp4"
        final_file.touch()
        patches = self._patches(tmp_path)
        patches["ytd_wrap.cli.extract_metadata"] = MagicMock(
            side_effect=ExtractionError("url", "fail")
        )
        patches["ytd_wrap.cli.download"] = final_file
        with _apply_patches(patches):
            result = runner.invoke(main, ["https://cdn.example.com/stream.m3u8"])
        # Should still succeed with fallback {"format_id": "best", ...}
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def _happy_preflight(self, tmp_path: Path) -> dict:
        return {
            **_ui_patches(),
            "ytd_wrap.cli.is_valid_url":              True,
            "ytd_wrap.cli.check_ffmpeg":               True,
            "ytd_wrap.cli.check_for_updates":          [],
            "ytd_wrap.cli.detect_url_type":            "social",
            "ytd_wrap.cli.extract_metadata":           _FAKE_METADATA,
            "ytd_wrap.cli.extract_formats":            _FAKE_FORMATS,
            "ytd_wrap.cli.select_format":              _FAKE_FORMAT,
            "ytd_wrap.cli.determine_output_container": "mp4",
            "ytd_wrap.cli.get_download_dir":           tmp_path,
            "ytd_wrap.cli._make_progress":             _make_progress_cm(),
        }

    def test_network_error_exits_1(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._happy_preflight(tmp_path)
        patches["ytd_wrap.cli.download"] = MagicMock(side_effect=NetworkError("timeout"))
        with _apply_patches(patches):
            result = runner.invoke(main, ["https://youtube.com/watch?v=test"])
        assert result.exit_code == 1

    def test_disk_full_exits_1(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._happy_preflight(tmp_path)
        patches["ytd_wrap.cli.download"] = MagicMock(side_effect=DiskFullError(str(tmp_path)))
        with _apply_patches(patches):
            result = runner.invoke(main, ["https://youtube.com/watch?v=test"])
        assert result.exit_code == 1

    def test_download_error_exits_1(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._happy_preflight(tmp_path)
        patches["ytd_wrap.cli.download"] = MagicMock(
            side_effect=DownloadError("https://youtube.com/watch?v=test", "403")
        )
        with _apply_patches(patches):
            result = runner.invoke(main, ["https://youtube.com/watch?v=test"])
        assert result.exit_code == 1

    def test_user_cancelled_exits_0(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._happy_preflight(tmp_path)
        patches["ytd_wrap.cli.download"] = MagicMock(side_effect=UserCancelledError())
        with _apply_patches(patches):
            result = runner.invoke(main, ["https://youtube.com/watch?v=test"])
        assert result.exit_code == 0

    def test_user_cancelled_calls_print_error(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._happy_preflight(tmp_path)
        patches["ytd_wrap.cli.download"] = MagicMock(side_effect=UserCancelledError())
        mock_pe = MagicMock()
        patches["ytd_wrap.cli.print_error"] = mock_pe
        with _apply_patches(patches):
            runner.invoke(main, ["https://youtube.com/watch?v=test"])
        mock_pe.assert_called_once()
        assert "cancel" in mock_pe.call_args.args[0].lower()

    def test_network_error_calls_print_error(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._happy_preflight(tmp_path)
        patches["ytd_wrap.cli.download"] = MagicMock(side_effect=NetworkError("timed out"))
        mock_pe = MagicMock()
        patches["ytd_wrap.cli.print_error"] = mock_pe
        with _apply_patches(patches):
            runner.invoke(main, ["https://youtube.com/watch?v=test"])
        mock_pe.assert_called_once()

    def test_unexpected_exception_exits_1(self, runner: CliRunner, tmp_path: Path) -> None:
        patches = self._happy_preflight(tmp_path)
        patches["ytd_wrap.cli.download"] = MagicMock(side_effect=RuntimeError("boom"))
        with _apply_patches(patches):
            result = runner.invoke(main, ["https://youtube.com/watch?v=test"])
        assert result.exit_code == 1

    def test_update_notice_called_when_updates_available(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        patches = self._happy_preflight(tmp_path)
        updates = [{"package": "yt-dlp", "current": "2024.1.1", "latest": "2024.12.1"}]
        patches["ytd_wrap.cli.check_for_updates"] = updates
        mock_dl = MagicMock()
        patches["ytd_wrap.cli.download"] = mock_dl
        mock_pun = MagicMock()
        patches["ytd_wrap.cli.print_update_notice"] = mock_pun
        with _apply_patches(patches):
            result = runner.invoke(main, ["https://youtube.com/watch?v=test"])
        assert result.exit_code == 0
        mock_pun.assert_called_once_with(updates)
        mock_dl.assert_not_called()
