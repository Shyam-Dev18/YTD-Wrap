"""Tests for ytd_wrap.checks.dependencies — ffmpeg and yt-dlp detection."""

from __future__ import annotations

import platform
import sys
from unittest.mock import patch

import pytest

from ytd_wrap.checks.dependencies import (
    check_ffmpeg,
    check_python_version,
    check_ytdlp,
    get_ffmpeg_install_command,
    run_all_checks,
)
from ytd_wrap.constants import FFMPEG_INSTALL_COMMANDS


# ---------------------------------------------------------------------------
# check_ffmpeg
# ---------------------------------------------------------------------------

class TestCheckFfmpeg:
    """Tests for check_ffmpeg()."""

    def test_returns_true_when_ffmpeg_found(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
        assert check_ffmpeg() is True

    def test_returns_false_when_ffmpeg_missing(self, mocker) -> None:
        mocker.patch("shutil.which", return_value=None)
        result = check_ffmpeg()
        assert result is False

    def test_does_not_raise_when_missing(self, mocker) -> None:
        mocker.patch("shutil.which", return_value=None)
        try:
            check_ffmpeg()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"check_ffmpeg() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# check_ytdlp
# ---------------------------------------------------------------------------

class TestCheckYtdlp:
    """Tests for check_ytdlp()."""

    def test_returns_true_when_yt_dlp_importable(self, mocker) -> None:
        mocker.patch("importlib.import_module", return_value=object())
        assert check_ytdlp() is True

    def test_returns_false_when_yt_dlp_not_importable(self, mocker) -> None:
        mocker.patch("importlib.import_module", side_effect=ImportError("no yt_dlp"))
        assert check_ytdlp() is False

    def test_does_not_raise_when_missing(self, mocker) -> None:
        mocker.patch("importlib.import_module", side_effect=ImportError)
        try:
            check_ytdlp()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"check_ytdlp() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# check_python_version
# ---------------------------------------------------------------------------

class TestCheckPythonVersion:
    """Tests for check_python_version()."""

    def test_returns_tuple_of_two_ints(self) -> None:
        result = check_python_version()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, int) for v in result)

    def test_matches_sys_version_info(self) -> None:
        major, minor = check_python_version()
        assert major == sys.version_info.major
        assert minor == sys.version_info.minor


# ---------------------------------------------------------------------------
# get_ffmpeg_install_command
# ---------------------------------------------------------------------------

class TestGetFfmpegInstallCommand:
    """Tests for get_ffmpeg_install_command() — all OS branches."""

    def test_macos_returns_brew_command(self, mocker) -> None:
        mocker.patch("platform.system", return_value="Darwin")
        cmd = get_ffmpeg_install_command()
        assert cmd == FFMPEG_INSTALL_COMMANDS["Darwin"]
        assert "brew" in cmd

    def test_windows_returns_winget_command(self, mocker) -> None:
        mocker.patch("platform.system", return_value="Windows")
        cmd = get_ffmpeg_install_command()
        assert cmd == FFMPEG_INSTALL_COMMANDS["Windows"]
        assert "winget" in cmd.lower() or "ffmpeg" in cmd.lower()

    def test_linux_ubuntu_returns_apt_command(self, mocker) -> None:
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch(
            "platform.freedesktop_os_release",
            return_value={"ID": "ubuntu", "ID_LIKE": ""},
        )
        cmd = get_ffmpeg_install_command()
        assert cmd == FFMPEG_INSTALL_COMMANDS["Ubuntu"]
        assert "apt" in cmd

    def test_linux_debian_returns_apt_command(self, mocker) -> None:
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch(
            "platform.freedesktop_os_release",
            return_value={"ID": "debian", "ID_LIKE": ""},
        )
        cmd = get_ffmpeg_install_command()
        assert cmd == FFMPEG_INSTALL_COMMANDS["Debian"]
        assert "apt" in cmd

    def test_linux_fedora_returns_generic_linux_command(self, mocker) -> None:
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch(
            "platform.freedesktop_os_release",
            return_value={"ID": "fedora", "ID_LIKE": ""},
        )
        cmd = get_ffmpeg_install_command()
        assert cmd == FFMPEG_INSTALL_COMMANDS["Linux"]

    def test_linux_no_os_release_fallback(self, mocker) -> None:
        mocker.patch("platform.system", return_value="Linux")
        mocker.patch("platform.freedesktop_os_release", side_effect=OSError)
        cmd = get_ffmpeg_install_command()
        assert cmd == FFMPEG_INSTALL_COMMANDS["Linux"]

    def test_unknown_os_falls_back_to_linux(self, mocker) -> None:
        mocker.patch("platform.system", return_value="Haiku")
        cmd = get_ffmpeg_install_command()
        assert cmd == FFMPEG_INSTALL_COMMANDS["Linux"]


# ---------------------------------------------------------------------------
# run_all_checks
# ---------------------------------------------------------------------------

class TestRunAllChecks:
    """Tests for run_all_checks() — integration of all sub-checks."""

    def test_returns_all_required_keys(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
        mocker.patch("importlib.import_module", return_value=object())
        result = run_all_checks()
        assert set(result.keys()) == {"ffmpeg", "ytdlp", "python_ok", "python_version"}

    def test_ffmpeg_true_when_found(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
        mocker.patch("importlib.import_module", return_value=object())
        result = run_all_checks()
        assert result["ffmpeg"] is True

    def test_ffmpeg_false_when_missing(self, mocker) -> None:
        mocker.patch("shutil.which", return_value=None)
        mocker.patch("importlib.import_module", return_value=object())
        result = run_all_checks()
        assert result["ffmpeg"] is False

    def test_ytdlp_false_when_not_importable(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
        mocker.patch("importlib.import_module", side_effect=ImportError)
        result = run_all_checks()
        assert result["ytdlp"] is False

    def test_python_ok_true_for_current_interpreter(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
        mocker.patch("importlib.import_module", return_value=object())
        result = run_all_checks()
        # We're running tests on 3.11+, so this must be True
        assert result["python_ok"] is True

    def test_python_version_is_string(self, mocker) -> None:
        mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
        mocker.patch("importlib.import_module", return_value=object())
        result = run_all_checks()
        assert isinstance(result["python_version"], str)
        assert "." in result["python_version"]

    def test_never_raises(self, mocker) -> None:
        mocker.patch("shutil.which", side_effect=OSError("broken"))
        try:
            run_all_checks()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"run_all_checks() raised unexpectedly: {exc}")
