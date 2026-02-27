"""Tests for MetadataService (core/metadata_service.py).

The :class:`MetadataProvider` dependency is **mocked** — no internet
access, no yt-dlp invocation.  These tests verify:

* URL validation
* Raw-dict → domain-model parsing
* Exception mapping (provider errors → our hierarchy)
* ``FormatSelectionError`` when no adaptive formats survive
* Unexpected provider errors wrapped as ``MetadataExtractionError``
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ytd_wrap.core.metadata_service import MetadataService
from ytd_wrap.core.models import FormatCollection, VideoFormat, VideoMetadata
from ytd_wrap.exceptions import (
    FormatSelectionError,
    InvalidURLError,
    MetadataExtractionError,
    VideoUnavailableError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_provider(info: dict[str, Any] | Exception) -> MagicMock:
    """Return a mock MetadataProvider.

    If *info* is a dict, ``fetch_info`` returns it.
    If *info* is an exception, ``fetch_info`` raises it.
    """
    provider = MagicMock()
    if isinstance(info, Exception):
        provider.fetch_info.side_effect = info
    else:
        provider.fetch_info.return_value = info
    return provider


def _sample_info(
    *,
    formats: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Minimal valid info dict."""
    return {
        "id": "abc123",
        "title": "Sample Video",
        "duration": 180,
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
        "formats": formats or [],
    }


def _raw_format(
    *,
    format_id: str = "137",
    ext: str = "mp4",
    height: int | None = 1080,
    fps: int | float | None = 30,
    filesize: int | None = 50_000_000,
    filesize_approx: int | None = None,
    vcodec: str = "avc1.640028",
    acodec: str = "none",
) -> dict[str, Any]:
    """Factory for a raw format dict matching yt-dlp output shape."""
    d: dict[str, Any] = {
        "format_id": format_id,
        "ext": ext,
        "height": height,
        "fps": fps,
        "filesize": filesize,
        "vcodec": vcodec,
        "acodec": acodec,
    }
    if filesize_approx is not None:
        d["filesize_approx"] = filesize_approx
    return d


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

class TestURLValidation:
    def test_empty_url_raises(self) -> None:
        svc = MetadataService(_fake_provider(_sample_info()))
        with pytest.raises(InvalidURLError, match="empty"):
            svc.extract_metadata("")

    def test_whitespace_only_raises(self) -> None:
        svc = MetadataService(_fake_provider(_sample_info()))
        with pytest.raises(InvalidURLError, match="empty"):
            svc.extract_metadata("   ")

    def test_non_http_raises(self) -> None:
        svc = MetadataService(_fake_provider(_sample_info()))
        with pytest.raises(InvalidURLError, match="Invalid URL"):
            svc.extract_metadata("ftp://example.com/video")

    def test_http_accepted(self) -> None:
        svc = MetadataService(_fake_provider(_sample_info()))
        result = svc.extract_metadata("http://www.youtube.com/watch?v=x")
        assert isinstance(result, VideoMetadata)

    def test_https_accepted(self) -> None:
        svc = MetadataService(_fake_provider(_sample_info()))
        result = svc.extract_metadata("https://www.youtube.com/watch?v=x")
        assert isinstance(result, VideoMetadata)


# ---------------------------------------------------------------------------
# extract_metadata — parsing
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_parses_all_fields(self) -> None:
        info = _sample_info()
        svc = MetadataService(_fake_provider(info))
        meta = svc.extract_metadata("https://youtube.com/watch?v=abc123")
        assert meta.id == "abc123"
        assert meta.title == "Sample Video"
        assert meta.duration == 180
        assert meta.webpage_url == "https://www.youtube.com/watch?v=abc123"

    def test_missing_duration_yields_none(self) -> None:
        info = _sample_info()
        del info["duration"]
        svc = MetadataService(_fake_provider(info))
        meta = svc.extract_metadata("https://youtube.com/watch?v=x")
        assert meta.duration is None

    def test_missing_title_yields_unknown(self) -> None:
        info = _sample_info()
        del info["title"]
        svc = MetadataService(_fake_provider(info))
        meta = svc.extract_metadata("https://youtube.com/watch?v=x")
        assert meta.title == "Unknown"

    def test_missing_id_yields_empty(self) -> None:
        info = _sample_info()
        del info["id"]
        svc = MetadataService(_fake_provider(info))
        meta = svc.extract_metadata("https://youtube.com/watch?v=x")
        assert meta.id == ""


# ---------------------------------------------------------------------------
# extract_metadata — exception mapping
# ---------------------------------------------------------------------------

class TestExtractMetadataExceptions:
    def test_provider_ytdwrap_error_propagates(self) -> None:
        svc = MetadataService(
            _fake_provider(VideoUnavailableError("gone"))
        )
        with pytest.raises(VideoUnavailableError, match="gone"):
            svc.extract_metadata("https://youtube.com/watch?v=x")

    def test_provider_unexpected_error_wrapped(self) -> None:
        svc = MetadataService(_fake_provider(RuntimeError("boom")))
        with pytest.raises(MetadataExtractionError, match="Unexpected"):
            svc.extract_metadata("https://youtube.com/watch?v=x")


# ---------------------------------------------------------------------------
# get_adaptive_video_formats — happy path
# ---------------------------------------------------------------------------

class TestGetAdaptiveVideoFormats:
    def test_returns_format_collection(self) -> None:
        info = _sample_info(formats=[
            _raw_format(format_id="137", height=1080, vcodec="avc1", acodec="none"),
        ])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert isinstance(col, FormatCollection)
        assert len(col) == 1

    def test_filters_audio_only(self) -> None:
        info = _sample_info(formats=[
            _raw_format(format_id="140", vcodec="none", acodec="mp4a"),
        ])
        svc = MetadataService(_fake_provider(info))
        with pytest.raises(FormatSelectionError):
            svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")

    def test_filters_muxed(self) -> None:
        info = _sample_info(formats=[
            _raw_format(vcodec="avc1", acodec="mp4a"),
        ])
        svc = MetadataService(_fake_provider(info))
        with pytest.raises(FormatSelectionError):
            svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")

    def test_deduplication(self) -> None:
        info = _sample_info(formats=[
            _raw_format(format_id="1", height=1080, fps=30, ext="mp4",
                        vcodec="avc1", acodec="none"),
            _raw_format(format_id="2", height=1080, fps=30, ext="mp4",
                        vcodec="avc1", acodec="none"),
        ])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert len(col) == 1

    def test_sorted_by_resolution_desc(self) -> None:
        info = _sample_info(formats=[
            _raw_format(format_id="low", height=480, fps=30,
                        vcodec="avc1", acodec="none"),
            _raw_format(format_id="high", height=1080, fps=30,
                        vcodec="avc1", acodec="none"),
            _raw_format(format_id="mid", height=720, fps=30,
                        vcodec="avc1", acodec="none"),
        ])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        heights = [f.height for f in col.formats]
        assert heights == [1080, 720, 480]

    def test_mp4_preferred_over_webm(self) -> None:
        info = _sample_info(formats=[
            _raw_format(format_id="webm", height=1080, fps=30, ext="webm",
                        vcodec="vp9", acodec="none"),
            _raw_format(format_id="mp4", height=1080, fps=30, ext="mp4",
                        vcodec="avc1", acodec="none"),
        ])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert col.formats[0].ext == "mp4"
        assert col.formats[1].ext == "webm"


# ---------------------------------------------------------------------------
# get_adaptive_video_formats — edge cases
# ---------------------------------------------------------------------------

class TestGetAdaptiveFormatsEdgeCases:
    def test_no_formats_key_raises(self) -> None:
        info = {"id": "x", "title": "t", "webpage_url": "u"}
        svc = MetadataService(_fake_provider(info))
        with pytest.raises(FormatSelectionError):
            svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")

    def test_empty_formats_list_raises(self) -> None:
        info = _sample_info(formats=[])
        svc = MetadataService(_fake_provider(info))
        with pytest.raises(FormatSelectionError):
            svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")

    def test_formats_not_a_list_raises(self) -> None:
        info = _sample_info()
        info["formats"] = "not-a-list"
        svc = MetadataService(_fake_provider(info))
        with pytest.raises(FormatSelectionError):
            svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")

    def test_url_validation_applied(self) -> None:
        svc = MetadataService(_fake_provider(_sample_info()))
        with pytest.raises(InvalidURLError):
            svc.get_adaptive_video_formats("")

    def test_no_adaptive_formats_hint_includes_ytdlp_upgrade(self) -> None:
        info = _sample_info(formats=[])
        svc = MetadataService(_fake_provider(info))

        with pytest.raises(FormatSelectionError) as exc_info:
            svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")

        hint = exc_info.value.hint
        assert hint is not None
        assert "The video may only provide muxed formats." in hint
        assert "Also try updating yt-dlp:" in hint
        assert "pip install --upgrade yt-dlp" in hint


# ---------------------------------------------------------------------------
# Parsing edge cases
# ---------------------------------------------------------------------------

class TestParsing:
    def test_filesize_approx_fallback(self) -> None:
        info = _sample_info(formats=[
            _raw_format(
                filesize=None,
                filesize_approx=12345678,
                vcodec="avc1",
                acodec="none",
            ),
        ])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert col.formats[0].filesize == 12345678

    def test_no_filesize_yields_none(self) -> None:
        raw = _raw_format(filesize=None, vcodec="avc1", acodec="none")
        info = _sample_info(formats=[raw])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert col.formats[0].filesize is None

    def test_float_fps_rounded(self) -> None:
        info = _sample_info(formats=[
            _raw_format(fps=29.97, vcodec="avc1", acodec="none"),
        ])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert col.formats[0].fps == 30

    def test_none_fps_preserved(self) -> None:
        info = _sample_info(formats=[
            _raw_format(fps=None, vcodec="avc1", acodec="none"),
        ])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert col.formats[0].fps is None

    def test_none_vcodec_normalised(self) -> None:
        """A raw None vcodec must become the string ``"none"``."""
        raw = _raw_format(vcodec="avc1", acodec="none")
        raw["vcodec"] = None
        info = _sample_info(formats=[raw])
        svc = MetadataService(_fake_provider(info))
        # This format has vcodec="none" after normalisation → filtered out
        with pytest.raises(FormatSelectionError):
            svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")

    def test_non_int_height_yields_none(self) -> None:
        raw = _raw_format(vcodec="avc1", acodec="none")
        raw["height"] = "not-an-int"
        info = _sample_info(formats=[raw])
        svc = MetadataService(_fake_provider(info))
        col = svc.get_adaptive_video_formats("https://youtube.com/watch?v=x")
        assert col.formats[0].height is None
