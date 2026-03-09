"""Tests for ytd_wrap.ui.display — rich output rendering.

Strategy: swap the module-level ``console`` for a captured Console before each
test, restore it afterwards with a fixture.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

import ytd_wrap.ui.display as display_mod


@pytest.fixture(autouse=True)
def captured_console():
    """Replace the module console with a StringIO-backed one for every test.

    Yields:
        The StringIO buffer so tests can call ``.getvalue()`` on it.
    """
    buf = StringIO()
    test_console = Console(file=buf, highlight=False, width=120, force_terminal=False)
    original = display_mod.console
    display_mod.console = test_console
    yield buf
    display_mod.console = original


# ──────────────────────────────────────────────────────────────────────────────
# print_banner
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintBanner:
    def test_contains_app_name(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_banner
        print_banner()
        output = captured_console.getvalue()
        assert "ytd-wrap" in output

    def test_contains_version(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_banner
        from ytd_wrap import __version__
        print_banner()
        assert __version__ in captured_console.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# print_version
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintVersion:
    def test_contains_version_string(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_version
        print_version("1.2.3")
        assert "1.2.3" in captured_console.getvalue()

    def test_contains_app_name(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_version
        print_version("1.2.3")
        assert "ytd-wrap" in captured_console.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# print_doctor_table
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintDoctorTable:
    _checks_ok = {
        "python_ok": True,
        "python_version": "3.11",
        "ytdlp": True,
        "ffmpeg": True,
    }
    _checks_fail = {
        "python_ok": False,
        "python_version": "3.9",
        "ytdlp": False,
        "ffmpeg": False,
    }

    def test_renders_ok_symbol_for_passing(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_doctor_table
        print_doctor_table(self._checks_ok)
        output = captured_console.getvalue()
        assert "✓" in output

    def test_renders_fail_symbol_for_missing(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_doctor_table
        print_doctor_table(self._checks_fail)
        output = captured_console.getvalue()
        assert "✗" in output

    def test_contains_python_row(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_doctor_table
        print_doctor_table(self._checks_ok)
        assert "Python" in captured_console.getvalue()

    def test_contains_ytdlp_row(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_doctor_table
        print_doctor_table(self._checks_ok)
        assert "yt-dlp" in captured_console.getvalue()

    def test_contains_ffmpeg_row(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_doctor_table
        print_doctor_table(self._checks_ok)
        assert "ffmpeg" in captured_console.getvalue()

    def test_contains_version_string(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_doctor_table
        from ytd_wrap import __version__
        print_doctor_table(self._checks_ok)
        assert __version__ in captured_console.getvalue()

    def test_shows_python_version(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_doctor_table
        print_doctor_table(self._checks_ok)
        assert "3.11" in captured_console.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# print_formats_table
# ──────────────────────────────────────────────────────────────────────────────

_FMT_H264_AAC = {
    "display_index":   1,
    "format_id":       "22",
    "audio_format_id": None,
    "resolution":      "FHD / 1080p",
    "height":          1080,
    "vcodec_short":    "h264",
    "acodec_short":    "aac",
    "container":       "mp4",
    "filesize":        148_000_000,
    "filesize_str":    "141.1 MB",
    "codec_pair":      "h264 + aac",
}
_FMT_VP9 = {
    "display_index":   2,
    "format_id":       "248",
    "audio_format_id": "251",
    "resolution":      "2K / 1440p",
    "height":          1440,
    "vcodec_short":    "vp9",
    "acodec_short":    "opus",
    "container":       "mkv",
    "filesize":        None,
    "filesize_str":    "~unknown",
    "codec_pair":      "vp9 + opus",
}


class TestPrintFormatsTable:
    def test_contains_resolution(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([_FMT_H264_AAC])
        assert "1080p" in captured_console.getvalue()

    def test_contains_vcodec(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([_FMT_H264_AAC])
        assert "h264" in captured_console.getvalue()

    def test_contains_acodec(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([_FMT_H264_AAC])
        assert "aac" in captured_console.getvalue()

    def test_contains_format_id(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([_FMT_H264_AAC])
        # display_index=1 shows as "1" in the # column
        assert "1" in captured_console.getvalue()

    def test_shows_size_in_mb(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([_FMT_H264_AAC])
        assert "MB" in captured_console.getvalue()

    def test_shows_unknown_for_missing_size(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([_FMT_VP9])
        assert "unknown" in captured_console.getvalue()

    def test_multiple_formats_all_appear(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([_FMT_H264_AAC, _FMT_VP9])
        output = captured_console.getvalue()
        assert "1080p" in output
        assert "1440p" in output

    def test_empty_formats_renders_without_error(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_formats_table
        print_formats_table([])  # should not raise


# ──────────────────────────────────────────────────────────────────────────────
# print_update_notice
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintUpdateNotice:
    _updates = [{"package": "yt-dlp", "current": "2024.1.0", "latest": "2024.3.10"}]

    def test_contains_package_name(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_update_notice
        print_update_notice(self._updates)
        assert "yt-dlp" in captured_console.getvalue()

    def test_contains_latest_version(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_update_notice
        print_update_notice(self._updates)
        assert "2024.3.10" in captured_console.getvalue()

    def test_contains_pip_command(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_update_notice
        print_update_notice(self._updates)
        assert "pip install --upgrade" in captured_console.getvalue()

    def test_empty_list_prints_nothing(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_update_notice
        print_update_notice([])
        assert captured_console.getvalue() == ""


# ──────────────────────────────────────────────────────────────────────────────
# print_download_start
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintDownloadStart:
    def test_contains_title(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_download_start
        print_download_start("My Video Title", "https://example.com/v")
        assert "My Video Title" in captured_console.getvalue()

    def test_contains_url(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_download_start
        print_download_start("My Video Title", "https://example.com/v")
        assert "https://example.com/v" in captured_console.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# print_success
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintSuccess:
    def test_contains_filename(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_success
        print_success("my_video.mp4", Path("/home/user/Downloads/my_video.mp4"))
        assert "my_video.mp4" in captured_console.getvalue()

    def test_contains_path(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_success
        print_success("my_video.mp4", Path("/home/user/Downloads/my_video.mp4"))
        assert "Downloads" in captured_console.getvalue()

    def test_contains_success_indicator(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_success
        print_success("clip.mkv", Path("/tmp/clip.mkv"))
        assert "✓" in captured_console.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# print_error
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintError:
    def test_contains_message(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_error
        print_error("Something went wrong")
        assert "Something went wrong" in captured_console.getvalue()

    def test_contains_hint_when_provided(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_error
        print_error("Network timeout", hint="Check your internet connection.")
        output = captured_console.getvalue()
        assert "Network timeout" in output
        assert "Check your internet connection." in output

    def test_no_hint_renders_without_error(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_error
        print_error("Oops")  # should not raise


# ──────────────────────────────────────────────────────────────────────────────
# print_ffmpeg_missing
# ──────────────────────────────────────────────────────────────────────────────

class TestPrintFfmpegMissing:
    def test_contains_ffmpeg_name(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_ffmpeg_missing
        print_ffmpeg_missing("brew install ffmpeg")
        assert "ffmpeg" in captured_console.getvalue()

    def test_contains_install_command(self, captured_console) -> None:
        from ytd_wrap.ui.display import print_ffmpeg_missing
        print_ffmpeg_missing("brew install ffmpeg")
        assert "brew install ffmpeg" in captured_console.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# get_spinner
# ──────────────────────────────────────────────────────────────────────────────

class TestGetSpinner:
    def test_returns_status_object(self, captured_console) -> None:
        from ytd_wrap.ui.display import get_spinner
        from rich.status import Status
        spinner = get_spinner("Loading…")
        assert isinstance(spinner, Status)

    def test_is_context_manager(self, captured_console) -> None:
        from ytd_wrap.ui.display import get_spinner
        # Should be usable as a context manager without raising
        with get_spinner("Working…"):
            pass
