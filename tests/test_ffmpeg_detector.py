"""Tests for ffmpeg detection (infra/ffmpeg_detector.py).

All tests mock :func:`shutil.which` — no system dependency.

Coverage:
* ``detect_ffmpeg`` when ffmpeg is found.
* ``detect_ffmpeg`` when ffmpeg is missing.
* ``require_ffmpeg`` happy path.
* ``require_ffmpeg`` raises ``FfmpegNotFoundError``.
* Platform-specific install commands (Windows / Linux).
* ``future_auto_install`` stub raises ``NotImplementedError``.
* ``FfmpegStatus`` frozen dataclass.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ytd_wrap.exceptions import FfmpegNotFoundError
from ytd_wrap.infra.ffmpeg_detector import (
    FfmpegStatus,
    _platform_install_commands,
    detect_ffmpeg,
    future_auto_install,
    require_ffmpeg,
)


# ---------------------------------------------------------------------------
# detect_ffmpeg
# ---------------------------------------------------------------------------

class TestDetectFfmpeg:
    @patch("ytd_wrap.infra.ffmpeg_detector.shutil.which")
    def test_found(self, mock_which: object) -> None:
        mock_which.return_value = "/usr/bin/ffmpeg"  # type: ignore[union-attr]
        status = detect_ffmpeg()

        assert status.found is True
        assert status.path is not None
        assert "ffmpeg" in str(status.path).lower() or "ffmpeg" in status.version_hint
        assert status.install_commands == ()

    @patch("ytd_wrap.infra.ffmpeg_detector.shutil.which")
    def test_not_found(self, mock_which: object) -> None:
        mock_which.return_value = None  # type: ignore[union-attr]
        status = detect_ffmpeg()

        assert status.found is False
        assert status.path is None
        assert status.version_hint == "not found"
        assert len(status.install_commands) > 0

    @patch("ytd_wrap.infra.ffmpeg_detector.shutil.which")
    def test_found_returns_resolved_path(self, mock_which: object) -> None:
        mock_which.return_value = "/usr/local/bin/ffmpeg"  # type: ignore[union-attr]
        status = detect_ffmpeg()
        assert isinstance(status.path, Path)


# ---------------------------------------------------------------------------
# require_ffmpeg
# ---------------------------------------------------------------------------

class TestRequireFfmpeg:
    @patch("ytd_wrap.infra.ffmpeg_detector.shutil.which")
    def test_found_returns_path(self, mock_which: object) -> None:
        mock_which.return_value = "/usr/bin/ffmpeg"  # type: ignore[union-attr]
        path = require_ffmpeg()
        assert isinstance(path, Path)

    @patch("ytd_wrap.infra.ffmpeg_detector.shutil.which")
    def test_missing_raises(self, mock_which: object) -> None:
        mock_which.return_value = None  # type: ignore[union-attr]
        with pytest.raises(FfmpegNotFoundError, match="not installed"):
            require_ffmpeg()

    @patch("ytd_wrap.infra.ffmpeg_detector.shutil.which")
    def test_missing_hint_contains_install_command(self, mock_which: object) -> None:
        mock_which.return_value = None  # type: ignore[union-attr]
        with pytest.raises(FfmpegNotFoundError) as exc_info:
            require_ffmpeg()
        assert exc_info.value.hint is not None
        assert "Install ffmpeg" in exc_info.value.hint


# ---------------------------------------------------------------------------
# Platform install commands
# ---------------------------------------------------------------------------

class TestPlatformInstallCommands:
    @patch("ytd_wrap.infra.ffmpeg_detector.platform.system", return_value="Windows")
    def test_windows_commands(self, _mock_sys: object) -> None:
        cmds = _platform_install_commands()
        assert "winget install Gyan.FFmpeg" in cmds
        assert "choco install ffmpeg" in cmds

    @patch("ytd_wrap.infra.ffmpeg_detector.platform.system", return_value="Linux")
    def test_linux_commands(self, _mock_sys: object) -> None:
        cmds = _platform_install_commands()
        assert any("apt" in c for c in cmds)
        assert any("dnf" in c for c in cmds)

    @patch("ytd_wrap.infra.ffmpeg_detector.platform.system", return_value="Darwin")
    def test_darwin_commands(self, _mock_sys: object) -> None:
        cmds = _platform_install_commands()
        assert cmds == ("brew install ffmpeg",)


# ---------------------------------------------------------------------------
# FfmpegStatus dataclass
# ---------------------------------------------------------------------------

class TestFfmpegStatus:
    def test_frozen(self) -> None:
        status = FfmpegStatus(
            found=True,
            path=Path("/usr/bin/ffmpeg"),
            version_hint="found",
            install_commands=(),
        )
        with pytest.raises(AttributeError):
            status.found = False  # type: ignore[misc]

    def test_fields(self) -> None:
        status = FfmpegStatus(
            found=False,
            path=None,
            version_hint="not found",
            install_commands=("cmd1", "cmd2"),
        )
        assert status.found is False
        assert status.path is None
        assert status.install_commands == ("cmd1", "cmd2")


# ---------------------------------------------------------------------------
# future_auto_install stub
# ---------------------------------------------------------------------------

class TestFutureAutoInstall:
    def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            future_auto_install()
