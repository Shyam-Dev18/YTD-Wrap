"""Tests for the ``ytd-wrap doctor`` command (cli/doctor.py).

All external dependencies (ffmpeg, yt-dlp) are mocked — no system
dependency, no internet.

Coverage:
* Doctor runs and returns SUCCESS when everything is present.
* Doctor returns GENERAL_ERROR when Python version check fails.
* Individual check functions return correct tuples.
* CLI routing dispatches to ``run_doctor``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ytd_wrap.cli import exit_codes
from ytd_wrap.infra.ffmpeg_detector import FfmpegStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_ffmpeg_found() -> FfmpegStatus:
    return FfmpegStatus(
        found=True,
        path=Path("/usr/bin/ffmpeg"),
        version_hint="found at /usr/bin/ffmpeg",
        install_commands=(),
    )


def _mock_ffmpeg_missing() -> FfmpegStatus:
    return FfmpegStatus(
        found=False,
        path=None,
        version_hint="not found",
        install_commands=("winget install Gyan.FFmpeg",),
    )


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------

class TestPythonVersionCheck:
    def test_returns_tuple(self) -> None:
        from ytd_wrap.cli.doctor import _python_version_check

        label, value, status = _python_version_check()
        assert label == "Python"
        assert isinstance(value, str)
        assert "OK" in status or "FAIL" in status


class TestYtdlpVersionCheck:
    def test_installed(self) -> None:
        from ytd_wrap.cli.doctor import _ytdlp_version_check

        label, value, status = _ytdlp_version_check()
        assert label == "yt-dlp"
        # yt-dlp is installed in our test env
        assert "OK" in status

    @patch.dict("sys.modules", {"yt_dlp": None, "yt_dlp.version": None})
    def test_not_installed(self) -> None:
        from ytd_wrap.cli.doctor import _ytdlp_version_check

        label, value, status = _ytdlp_version_check()
        assert label == "yt-dlp"
        assert value == "NOT INSTALLED"
        assert "FAIL" in status


class TestFfmpegCheck:
    @patch("ytd_wrap.cli.doctor.detect_ffmpeg")
    def test_found(self, mock_detect: MagicMock) -> None:
        from ytd_wrap.cli.doctor import _ffmpeg_check

        mock_detect.return_value = _mock_ffmpeg_found()
        label, value, status = _ffmpeg_check()
        assert label == "ffmpeg"
        assert "OK" in status

    @patch("ytd_wrap.cli.doctor.detect_ffmpeg")
    def test_missing(self, mock_detect: MagicMock) -> None:
        from ytd_wrap.cli.doctor import _ffmpeg_check

        mock_detect.return_value = _mock_ffmpeg_missing()
        label, value, status = _ffmpeg_check()
        assert label == "ffmpeg"
        assert "WARN" in status


class TestOsCheck:
    def test_returns_tuple(self) -> None:
        from ytd_wrap.cli.doctor import _os_check

        label, value, status = _os_check()
        assert label == "OS"
        assert isinstance(value, str)
        assert "OK" in status

    @patch("ytd_wrap.cli.doctor.platform.machine", return_value="arm64")
    @patch("ytd_wrap.cli.doctor.platform.release", return_value="23.4.0")
    @patch("ytd_wrap.cli.doctor.platform.system", return_value="Darwin")
    def test_darwin_is_displayed_as_macos(
        self,
        _mock_system: MagicMock,
        _mock_release: MagicMock,
        _mock_machine: MagicMock,
    ) -> None:
        from ytd_wrap.cli.doctor import _os_check

        _label, value, _status = _os_check()
        assert "macOS" in value
        assert "Darwin" not in value


class TestYtdwrapVersionCheck:
    def test_returns_current_version(self) -> None:
        from ytd_wrap.cli.doctor import _ytdwrap_version_check
        from ytd_wrap.version import __version__

        label, value, status = _ytdwrap_version_check()
        assert label == "ytd-wrap"
        assert value == __version__
        assert "OK" in status


# ---------------------------------------------------------------------------
# run_doctor integration
# ---------------------------------------------------------------------------

class TestRunDoctor:
    @patch("ytd_wrap.cli.doctor.detect_ffmpeg")
    def test_all_pass_returns_success(self, mock_detect: MagicMock) -> None:
        from ytd_wrap.cli.doctor import run_doctor

        mock_detect.return_value = _mock_ffmpeg_found()
        code = run_doctor()
        assert code == exit_codes.SUCCESS

    @patch("ytd_wrap.cli.doctor.detect_ffmpeg")
    def test_ffmpeg_missing_still_succeeds(self, mock_detect: MagicMock) -> None:
        """ffmpeg missing is a WARN, not a FAIL — doctor should still succeed."""
        from ytd_wrap.cli.doctor import run_doctor

        mock_detect.return_value = _mock_ffmpeg_missing()
        code = run_doctor()
        # ffmpeg is WARN not FAIL, so should be SUCCESS
        assert code == exit_codes.SUCCESS

    @patch("ytd_wrap.cli.doctor.platform.machine", return_value="arm64")
    @patch("ytd_wrap.cli.doctor.platform.release", return_value="23.4.0")
    @patch("ytd_wrap.cli.doctor.platform.system", return_value="Darwin")
    @patch("ytd_wrap.cli.doctor.detect_ffmpeg")
    @patch.dict("sys.modules", {"rich": None, "rich.table": None})
    def test_darwin_plain_output_shows_macos_and_brew_guidance(
        self,
        mock_detect: MagicMock,
        _mock_system: MagicMock,
        _mock_release: MagicMock,
        _mock_machine: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from ytd_wrap.cli.doctor import run_doctor

        mock_detect.return_value = FfmpegStatus(
            found=False,
            path=None,
            version_hint="not found",
            install_commands=("brew install ffmpeg",),
        )

        _ = run_doctor()
        captured = capsys.readouterr()
        assert "macOS" in captured.err
        assert "brew install ffmpeg" in captured.err

    @patch("ytd_wrap.cli.doctor.detect_ffmpeg")
    @patch.dict("sys.modules", {"rich": None, "rich.table": None})
    def test_plain_output_includes_watermark(
        self,
        mock_detect: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from ytd_wrap.cli.doctor import run_doctor

        mock_detect.return_value = _mock_ffmpeg_found()
        _ = run_doctor()

        captured = capsys.readouterr()
        assert "@shyam" in captured.err


# ---------------------------------------------------------------------------
# CLI routing
# ---------------------------------------------------------------------------

class TestDoctorRouting:
    @patch("ytd_wrap.cli.doctor.run_doctor", return_value=exit_codes.SUCCESS)
    def test_doctor_dispatches(self, mock_run: MagicMock) -> None:
        from ytd_wrap.cli.app import main

        code = main(["doctor"])
        assert code == exit_codes.SUCCESS
        mock_run.assert_called_once()

    @patch("ytd_wrap.cli.doctor.run_doctor", return_value=exit_codes.GENERAL_ERROR)
    def test_doctor_failure_propagates(self, mock_run: MagicMock) -> None:
        from ytd_wrap.cli.app import main

        code = main(["doctor"])
        assert code == exit_codes.GENERAL_ERROR
