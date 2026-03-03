"""Tests for ytd_wrap.checks.updates — PyPI version check with cache."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ytd_wrap.checks.updates import (
    _fetch_pypi_version,
    _is_check_due,
    _read_cache,
    _version_is_newer,
    _write_cache,
    _write_cache_timestamp,
    check_for_updates,
)
from ytd_wrap.constants import VERSION_CHECK_INTERVAL_SECONDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pypi_response(version: str) -> MagicMock:
    """Build a mock requests.Response returning the given version."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"info": {"version": version}}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# _read_cache / _write_cache
# ---------------------------------------------------------------------------

class TestCacheIO:
    """Tests for _read_cache() and _write_cache()."""

    def test_read_returns_empty_dict_when_file_missing(self, tmp_path, mocker) -> None:
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", tmp_path / "nonexistent.json")
        result = _read_cache()
        assert result == {}

    def test_read_returns_dict_when_file_valid(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps({"last_checked": 12345.0}), encoding="utf-8")
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        result = _read_cache()
        assert result == {"last_checked": 12345.0}

    def test_read_returns_empty_dict_on_corrupt_json(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("NOT JSON!!", encoding="utf-8")
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        result = _read_cache()
        assert result == {}

    def test_write_creates_file(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        _write_cache({"last_checked": 99.9})
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["last_checked"] == 99.9

    def test_write_overwrites_existing(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps({"last_checked": 1.0}), encoding="utf-8")
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        _write_cache({"last_checked": 2.0})
        data = json.loads(cache_file.read_text())
        assert data["last_checked"] == 2.0

    def test_write_does_not_raise_on_os_error(self, tmp_path, mocker) -> None:
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        mocker.patch("pathlib.Path.write_text", side_effect=OSError("disk full"))
        try:
            _write_cache({"x": 1})
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"_write_cache() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# _is_check_due
# ---------------------------------------------------------------------------

class TestIsCheckDue:
    """Tests for _is_check_due()."""

    def test_returns_true_when_cache_empty(self) -> None:
        assert _is_check_due({}) is True

    def test_returns_true_when_last_checked_missing(self) -> None:
        assert _is_check_due({"other_key": "value"}) is True

    def test_returns_false_when_checked_recently(self) -> None:
        recent = time.time() - 60  # 60 seconds ago
        assert _is_check_due({"last_checked": recent}) is False

    def test_returns_true_when_checked_over_a_day_ago(self) -> None:
        old = time.time() - (VERSION_CHECK_INTERVAL_SECONDS + 1)
        assert _is_check_due({"last_checked": old}) is True

    def test_returns_true_exactly_at_interval_boundary(self) -> None:
        at_boundary = time.time() - VERSION_CHECK_INTERVAL_SECONDS
        # Should be due (>=) — the check uses >=
        assert _is_check_due({"last_checked": at_boundary}) is True


# ---------------------------------------------------------------------------
# _fetch_pypi_version
# ---------------------------------------------------------------------------

class TestFetchPypiVersion:
    """Tests for _fetch_pypi_version()."""

    def test_returns_version_string_on_success(self, mocker) -> None:
        mocker.patch("requests.get", return_value=_make_pypi_response("2024.3.10"))
        result = _fetch_pypi_version("yt-dlp")
        assert result == "2024.3.10"

    def test_returns_none_on_http_error(self, mocker) -> None:
        import requests
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("403")
        mocker.patch("requests.get", return_value=mock_resp)
        assert _fetch_pypi_version("yt-dlp") is None

    def test_returns_none_on_connection_timeout(self, mocker) -> None:
        import requests
        mocker.patch("requests.get", side_effect=requests.Timeout("timed out"))
        assert _fetch_pypi_version("yt-dlp") is None

    def test_returns_none_on_network_error(self, mocker) -> None:
        import requests
        mocker.patch("requests.get", side_effect=requests.ConnectionError("unreachable"))
        assert _fetch_pypi_version("yt-dlp") is None

    def test_returns_none_on_malformed_json(self, mocker) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {}  # missing "info" key
        mocker.patch("requests.get", return_value=mock_resp)
        assert _fetch_pypi_version("yt-dlp") is None


# ---------------------------------------------------------------------------
# check_for_updates
# ---------------------------------------------------------------------------

class TestCheckForUpdates:
    """Tests for check_for_updates()."""

    def test_skips_when_checked_recently(self, tmp_path, mocker) -> None:
        recent = time.time() - 60
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps({"last_checked": recent}), encoding="utf-8")
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mock_get = mocker.patch("requests.get")
        result = check_for_updates()
        mock_get.assert_not_called()
        assert result == []

    def test_returns_empty_list_when_all_up_to_date(self, tmp_path, mocker) -> None:
        from ytd_wrap import __version__ as current_self_version

        cache_file = tmp_path / "cache.json"
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        ytdlp_installed = "2024.3.10"
        mocker.patch(
            "ytd_wrap.checks.updates._get_ytdlp_installed_version",
            return_value=ytdlp_installed,
        )

        # Return the exact installed version for each package → nothing is outdated
        def same_version(package_name: str) -> str:
            return ytdlp_installed if package_name == "yt-dlp" else current_self_version

        mocker.patch("ytd_wrap.checks.updates._fetch_pypi_version", side_effect=same_version)
        result = check_for_updates()
        assert result == []

    def test_returns_outdated_package_when_newer_exists(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        mocker.patch(
            "ytd_wrap.checks.updates._get_ytdlp_installed_version",
            return_value="2024.1.0",
        )

        def fake_fetch(package_name: str) -> str:
            return "2024.3.10"  # newer for both

        mocker.patch("ytd_wrap.checks.updates._fetch_pypi_version", side_effect=fake_fetch)
        result = check_for_updates()
        packages = [r["package"] for r in result]
        assert "yt-dlp" in packages

    def test_updates_cache_timestamp_after_check(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        mocker.patch("ytd_wrap.checks.updates._get_ytdlp_installed_version", return_value="1.0")
        mocker.patch("ytd_wrap.checks.updates._fetch_pypi_version", return_value="1.0")
        before = time.time()
        check_for_updates()
        data = json.loads(cache_file.read_text())
        assert data["last_checked"] >= before

    def test_never_raises_on_network_exception(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        mocker.patch("requests.get", side_effect=RuntimeError("catastrophic failure"))
        try:
            check_for_updates()
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"check_for_updates() raised unexpectedly: {exc}")

    def test_handles_yt_dlp_not_installed(self, tmp_path, mocker) -> None:
        cache_file = tmp_path / "cache.json"
        mocker.patch("ytd_wrap.checks.updates.CACHE_FILE", cache_file)
        mocker.patch("ytd_wrap.checks.updates.ensure_app_dirs")
        mocker.patch("ytd_wrap.checks.updates._get_ytdlp_installed_version", return_value=None)
        mocker.patch("ytd_wrap.checks.updates._fetch_pypi_version", return_value="2024.3.10")
        # Should not raise and yt-dlp should not appear in outdated (no current version)
        result = check_for_updates()
        packages = [r["package"] for r in result]
        assert "yt-dlp" not in packages


# ---------------------------------------------------------------------------
# _version_is_newer
# ---------------------------------------------------------------------------

class TestVersionIsNewer:
    """Tests for _version_is_newer()."""

    def test_newer_semver(self) -> None:
        assert _version_is_newer("1.2.0", "1.1.0") is True

    def test_same_version(self) -> None:
        assert _version_is_newer("1.0.0", "1.0.0") is False

    def test_older_version(self) -> None:
        assert _version_is_newer("1.0.0", "2.0.0") is False

    def test_date_based_version(self) -> None:
        assert _version_is_newer("2024.3.10", "2024.1.1") is True
