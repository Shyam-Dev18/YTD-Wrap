"""Tests for ytd_wrap.core.extractor — metadata, format extraction, helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ytd_wrap.core.extractor import (
    _codec_prefix,
    _dedup_formats,
    _format_priority_score,
    _is_video_format,
    _normalise_format,
    _shorten_codec,
    _resolution_label,
    _has_audio,
    _build_merged_entry,
    determine_output_container,
    extract_formats,
    extract_metadata,
    select_best_format,
)
from ytd_wrap.utils.exceptions import ExtractionError


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_ydl_cm(info: dict) -> MagicMock:
    """Return a mock context-manager instance configured to return *info*."""
    instance = MagicMock()
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    instance.extract_info = MagicMock(return_value=info)
    return instance


def _raw_fmt(
    *,
    format_id: str = "22",
    vcodec: str = "avc1.42001f",
    acodec: str = "mp4a.40.2",
    height: int = 1080,
    width: int = 1920,
    filesize: int = 100_000_000,
    ext: str = "mp4",
) -> dict:
    return {
        "format_id": format_id,
        "vcodec": vcodec,
        "acodec": acodec,
        "height": height,
        "width": width,
        "filesize": filesize,
        "ext": ext,
        "fps": 30,
    }


# ──────────────────────────────────────────────────────────────────────────────
# _codec_prefix
# ──────────────────────────────────────────────────────────────────────────────

class TestCodecPrefix:
    def test_avc1_matches_avc1_prefix(self) -> None:
        # yt-dlp reports H.264 as "avc1.xxx"; "avc1" comes before "h264" in the
        # substring scan because "h264" is not a substring of "avc1.42001f".
        from ytd_wrap.constants import PREFERRED_VIDEO_CODECS
        result = _codec_prefix("avc1.42001f", PREFERRED_VIDEO_CODECS)
        assert result == "avc1"

    def test_vp09_matches_vp09_prefix(self) -> None:
        # yt-dlp reports VP9 as "vp09.xxx"; "vp9" is NOT a substring of "vp09",
        # so the match falls through to "vp09".
        from ytd_wrap.constants import PREFERRED_VIDEO_CODECS
        result = _codec_prefix("vp09.00.51.08", PREFERRED_VIDEO_CODECS)
        assert result == "vp09"

    def test_mp4a_matches_aac(self) -> None:
        from ytd_wrap.constants import PREFERRED_AUDIO_CODECS
        result = _codec_prefix("mp4a.40.2", PREFERRED_AUDIO_CODECS)
        assert result in ("aac", "m4a", "mp4a")

    def test_unknown_codec_returns_empty(self) -> None:
        result = _codec_prefix("unknown_codec", ["h264", "vp9"])
        assert result == ""

    def test_none_returns_empty(self) -> None:
        result = _codec_prefix(None, ["h264"])
        assert result == ""


# ──────────────────────────────────────────────────────────────────────────────
# _is_video_format
# ──────────────────────────────────────────────────────────────────────────────

class TestIsVideoFormat:
    def test_video_format_returns_true(self) -> None:
        assert _is_video_format({"vcodec": "avc1.42001f"}) is True

    def test_none_vcodec_returns_false(self) -> None:
        assert _is_video_format({"vcodec": "none"}) is False

    def test_empty_vcodec_returns_false(self) -> None:
        assert _is_video_format({"vcodec": ""}) is False

    def test_missing_vcodec_returns_false(self) -> None:
        assert _is_video_format({}) is False

    def test_direct_m3u8_unknown_codecs_treated_as_video(self) -> None:
        fmt = {"vcodec": None, "acodec": None, "protocol": "m3u8_native", "ext": "mp4"}
        assert _is_video_format(fmt) is True

    def test_audio_m3u8_unknown_codecs_not_treated_as_video(self) -> None:
        fmt = {"vcodec": None, "acodec": None, "protocol": "m3u8_native", "ext": "m4a"}
        assert _is_video_format(fmt) is False


# ──────────────────────────────────────────────────────────────────────────────
# _normalise_format
# ──────────────────────────────────────────────────────────────────────────────

class TestNormaliseFormat:
    def test_extracts_expected_keys(self) -> None:
        raw = _raw_fmt()
        result = _normalise_format(raw)
        assert "format_id" in result
        assert "resolution" in result
        assert "vcodec" in result
        assert "acodec" in result
        assert "filesize" in result

    def test_resolution_uses_height(self) -> None:
        raw = _raw_fmt(height=720)
        result = _normalise_format(raw)
        assert result["resolution"] == "720p"

    def test_missing_height_uses_format_note(self) -> None:
        raw = {"format_id": "3", "vcodec": "h264", "format_note": "360p"}
        result = _normalise_format(raw)
        assert "360p" in result["resolution"]


# ──────────────────────────────────────────────────────────────────────────────
# _dedup_formats
# ──────────────────────────────────────────────────────────────────────────────

class TestDedupFormats:
    def _merged(self, format_id: str, height: int, vcodec_short: str, filesize: int | None = None) -> dict:
        """Minimal merged-format dict for dedup testing."""
        return {
            "format_id": format_id,
            "height": height,
            "vcodec_short": vcodec_short,
            "acodec_short": "aac",
            "filesize": filesize,
        }

    def test_removes_duplicates(self) -> None:
        fmt = self._merged("1", 1080, "h264", filesize=None)
        result = _dedup_formats([fmt, dict(fmt)])
        assert len(result) == 1

    def test_different_resolutions_kept(self) -> None:
        a = self._merged("1", 1080, "h264")
        b = self._merged("2",  720, "h264")
        result = _dedup_formats([a, b])
        assert len(result) == 2

    def test_keeps_higher_filesize_on_dedup(self) -> None:
        small = self._merged("1", 1080, "h264", filesize=10_000)
        large = self._merged("2", 1080, "h264", filesize=50_000)
        result = _dedup_formats([small, large])
        assert len(result) == 1
        assert result[0]["format_id"] == "2"

    def test_prefers_audio_entry_even_if_smaller(self) -> None:
        no_audio = self._merged("1", 720, "h264", filesize=80_000)
        no_audio["acodec_short"] = "—"
        no_audio["audio_format_id"] = None

        with_audio = self._merged("2", 720, "h264", filesize=20_000)
        with_audio["acodec_short"] = "aac"
        with_audio["audio_format_id"] = "140"

        result = _dedup_formats([no_audio, with_audio])
        assert len(result) == 1
        assert result[0]["format_id"] == "2"

    def test_when_audio_status_equal_keeps_larger_filesize(self) -> None:
        a = self._merged("1", 1080, "h264", filesize=10_000)
        a["acodec_short"] = "—"
        a["audio_format_id"] = None

        b = self._merged("2", 1080, "h264", filesize=50_000)
        b["acodec_short"] = "—"
        b["audio_format_id"] = None

        result = _dedup_formats([a, b])
        assert len(result) == 1
        assert result[0]["format_id"] == "2"


# ──────────────────────────────────────────────────────────────────────────────
# extract_metadata
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractMetadata:
    def test_returns_expected_fields(self) -> None:
        fake_info = {
            "title": "My Video",
            "uploader": "Creator",
            "duration": 120,
            "webpage_url": "https://youtube.com/watch?v=abc",
            "thumbnail": "https://img.example.com/thumb.jpg",
        }
        mock_ydl = _make_ydl_cm(fake_info)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = extract_metadata("https://youtube.com/watch?v=abc")

        assert result["title"] == "My Video"
        assert result["uploader"] == "Creator"
        assert result["duration"] == 120
        assert "webpage_url" in result
        assert "thumbnail" in result

    def test_raises_extraction_error_on_failure(self) -> None:
        mock_ydl = _make_ydl_cm(None)
        mock_ydl.extract_info.side_effect = Exception("network error")
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(ExtractionError):
                extract_metadata("https://youtube.com/watch?v=abc")

    def test_raises_when_info_none(self) -> None:
        mock_ydl = _make_ydl_cm(None)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(ExtractionError, match="no metadata"):
                extract_metadata("https://youtube.com/watch?v=abc")


# ──────────────────────────────────────────────────────────────────────────────
# extract_formats
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractFormats:
    def _make_info(self, formats: list[dict]) -> dict:
        return {"formats": formats, "title": "Test", "webpage_url": "https://example.com"}

    def test_returns_sorted_formats(self) -> None:
        h264_fmt = _raw_fmt(format_id="22", vcodec="avc1.42001f", acodec="mp4a.40.2", height=1080)
        vp9_fmt  = _raw_fmt(format_id="248", vcodec="vp09.00", acodec="opus", height=1080)
        info = self._make_info([vp9_fmt, h264_fmt])
        mock_ydl = _make_ydl_cm(info)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = extract_formats("https://youtube.com/watch?v=abc")
        assert len(result) >= 2
        # h264+aac should rank before vp9+opus
        ids = [f["format_id"] for f in result]
        assert ids.index("22") < ids.index("248")

    def test_excludes_audio_only_formats(self) -> None:
        audio_only = _raw_fmt(format_id="140", vcodec="none", acodec="mp4a.40.2")
        video_fmt  = _raw_fmt(format_id="22", vcodec="avc1", acodec="mp4a.40.2")
        info = self._make_info([audio_only, video_fmt])
        mock_ydl = _make_ydl_cm(info)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = extract_formats("https://youtube.com/watch?v=abc")
        fmt_ids = [f["format_id"] for f in result]
        assert "140" not in fmt_ids
        assert "22" in fmt_ids

    def test_raises_when_no_video_formats(self) -> None:
        audio_only = _raw_fmt(format_id="140", vcodec="none", acodec="mp4a.40.2")
        info = self._make_info([audio_only])
        mock_ydl = _make_ydl_cm(info)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(ExtractionError, match="No video formats"):
                extract_formats("https://youtube.com/watch?v=abc")

    def test_raises_on_ydl_exception(self) -> None:
        mock_ydl = _make_ydl_cm(None)
        mock_ydl.extract_info.side_effect = Exception("yt-dlp error")
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(ExtractionError):
                extract_formats("https://youtube.com/watch?v=abc")

    def test_accepts_direct_m3u8_with_unknown_codecs(self) -> None:
        direct = {
            "format_id": "0",
            "vcodec": None,
            "acodec": None,
            "protocol": "m3u8_native",
            "ext": "mp4",
            "height": None,
            "width": None,
        }
        info = self._make_info([direct])
        mock_ydl = _make_ydl_cm(info)
        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            result = extract_formats("https://example.com/manifest.m3u8")
        assert len(result) == 1
        assert result[0]["format_id"] == "0"


# ──────────────────────────────────────────────────────────────────────────────
# select_best_format
# ──────────────────────────────────────────────────────────────────────────────

class TestSelectBestFormat:
    def test_returns_first_format(self) -> None:
        fmts = [{"format_id": "22"}, {"format_id": "18"}]
        assert select_best_format(fmts)["format_id"] == "22"

    def test_raises_on_empty_list(self) -> None:
        with pytest.raises(ExtractionError):
            select_best_format([])


# ──────────────────────────────────────────────────────────────────────────────
# determine_output_container
# ──────────────────────────────────────────────────────────────────────────────

class TestDetermineOutputContainer:
    def test_h264_aac_returns_mp4(self) -> None:
        fmt = {"vcodec": "avc1.42001f", "acodec": "mp4a.40.2"}
        assert determine_output_container(fmt) == "mp4"

    def test_vp9_opus_returns_mkv(self) -> None:
        fmt = {"vcodec": "vp09.00.51.08", "acodec": "opus"}
        assert determine_output_container(fmt) == "mkv"

    def test_h264_opus_returns_mkv(self) -> None:
        fmt = {"vcodec": "avc1.42001f", "acodec": "opus"}
        assert determine_output_container(fmt) == "mkv"

    def test_unknown_codecs_return_default(self) -> None:
        fmt = {"vcodec": "somecodec", "acodec": "someaudio"}
        result = determine_output_container(fmt)
        assert result in ("mp4", "mkv")    # default — just ensure it's valid

    def test_empty_format_returns_default(self) -> None:
        result = determine_output_container({})
        assert result in ("mp4", "mkv")
