"""Tests for ytd_wrap.utils.paths — download directory resolution, filename sanitization."""

from __future__ import annotations

from pathlib import Path

import pytest

from ytd_wrap.utils.paths import (
    ensure_app_dirs,
    ensure_unique_path,
    get_download_dir,
    sanitize_filename,
)


# ---------------------------------------------------------------------------
# get_download_dir
# ---------------------------------------------------------------------------

class TestGetDownloadDir:
    """Tests for get_download_dir()."""

    def test_returns_downloads_when_writable(self, mocker, tmp_path) -> None:
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        mocker.patch("ytd_wrap.utils.paths.DEFAULT_DOWNLOAD_DIR", downloads)
        result = get_download_dir()
        assert result == downloads

    def test_falls_back_to_cwd_when_not_writable(self, mocker, tmp_path) -> None:
        # Point DEFAULT_DOWNLOAD_DIR at a path we mark as non-writable via os.access mock
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        mocker.patch("ytd_wrap.utils.paths.DEFAULT_DOWNLOAD_DIR", downloads)
        mocker.patch("os.access", return_value=False)
        result = get_download_dir()
        assert result == Path.cwd()

    def test_falls_back_when_downloads_does_not_exist(self, mocker, tmp_path) -> None:
        missing = tmp_path / "NoSuchDir"
        mocker.patch("ytd_wrap.utils.paths.DEFAULT_DOWNLOAD_DIR", missing)
        result = get_download_dir()
        # Missing dir is not writable; should return cwd
        assert result == Path.cwd()

    def test_never_raises(self, mocker, tmp_path) -> None:
        mocker.patch("os.access", side_effect=OSError("broken"))
        try:
            get_download_dir()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"get_download_dir() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    """Tests for sanitize_filename()."""

    def test_removes_illegal_windows_chars(self) -> None:
        result = sanitize_filename('video:<>"/\\|?*.mp4')
        for ch in '<>:"/\\|?*':
            assert ch not in result

    def test_strips_leading_trailing_dots_and_spaces(self) -> None:
        result = sanitize_filename("  .  video name  .  ")
        assert not result.startswith(" ")
        assert not result.startswith(".")
        assert not result.endswith(" ")
        assert not result.endswith(".")

    def test_removes_control_characters(self) -> None:
        result = sanitize_filename("video\x00\x1ftest")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_truncates_to_max_length(self) -> None:
        long_name = "a" * 300 + ".mp4"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_preserves_extension_after_truncation(self) -> None:
        long_name = "a" * 300 + ".mp4"
        result = sanitize_filename(long_name)
        assert result.endswith(".mp4")

    def test_windows_reserved_name_prefixed(self) -> None:
        result = sanitize_filename("CON.mp4")
        assert not result.upper().startswith("CON.")

    def test_collapses_multiple_spaces(self) -> None:
        result = sanitize_filename("video   name")
        assert "  " not in result

    def test_empty_string_returns_fallback(self) -> None:
        result = sanitize_filename("")
        assert result == "video"

    def test_plain_name_unchanged(self) -> None:
        result = sanitize_filename("My Video 2024.mp4")
        assert result == "My Video 2024.mp4"


# ---------------------------------------------------------------------------
# ensure_unique_path
# ---------------------------------------------------------------------------

class TestEnsureUniquePath:
    """Tests for ensure_unique_path()."""

    def test_returns_same_path_when_file_absent(self, tmp_path) -> None:
        target = tmp_path / "video.mp4"
        assert ensure_unique_path(target) == target

    def test_appends_counter_when_file_exists(self, tmp_path) -> None:
        target = tmp_path / "video.mp4"
        target.touch()
        result = ensure_unique_path(target)
        assert result == tmp_path / "video (1).mp4"

    def test_increments_counter_until_free(self, tmp_path) -> None:
        target = tmp_path / "video.mp4"
        target.touch()
        (tmp_path / "video (1).mp4").touch()
        result = ensure_unique_path(target)
        assert result == tmp_path / "video (2).mp4"

    def test_preserves_extension(self, tmp_path) -> None:
        target = tmp_path / "clip.mkv"
        target.touch()
        result = ensure_unique_path(target)
        assert result.suffix == ".mkv"

    def test_unique_result_does_not_exist(self, tmp_path) -> None:
        target = tmp_path / "video.mp4"
        target.touch()
        result = ensure_unique_path(target)
        assert not result.exists()


# ---------------------------------------------------------------------------
# ensure_app_dirs
# ---------------------------------------------------------------------------

class TestEnsureAppDirs:
    """Tests for ensure_app_dirs()."""

    def test_creates_app_dir(self, mocker, tmp_path) -> None:
        app_dir = tmp_path / ".ytd-wrap"
        log_dir = app_dir / "logs"
        mocker.patch("ytd_wrap.utils.paths.APP_DIR", app_dir)
        mocker.patch("ytd_wrap.utils.paths.LOG_DIR", log_dir)
        ensure_app_dirs()
        assert app_dir.is_dir()

    def test_creates_log_dir(self, mocker, tmp_path) -> None:
        app_dir = tmp_path / ".ytd-wrap"
        log_dir = app_dir / "logs"
        mocker.patch("ytd_wrap.utils.paths.APP_DIR", app_dir)
        mocker.patch("ytd_wrap.utils.paths.LOG_DIR", log_dir)
        ensure_app_dirs()
        assert log_dir.is_dir()

    def test_idempotent_when_dirs_exist(self, mocker, tmp_path) -> None:
        app_dir = tmp_path / ".ytd-wrap"
        log_dir = app_dir / "logs"
        app_dir.mkdir(parents=True)
        log_dir.mkdir(parents=True)
        mocker.patch("ytd_wrap.utils.paths.APP_DIR", app_dir)
        mocker.patch("ytd_wrap.utils.paths.LOG_DIR", log_dir)
        try:
            ensure_app_dirs()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"ensure_app_dirs() raised on existing dirs: {exc}")
