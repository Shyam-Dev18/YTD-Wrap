"""Tests for the pure format filtering pipeline (core/format_filter.py).

Every test is a pure function call — no I/O, no mocking, no side
effects.  These tests exercise:

* Adaptive-video-only filtering
* Deduplication by (height, fps, ext)
* Sort order (height desc, fps desc, mp4 preferred)
* End-to-end pipeline via ``select_adaptive_formats``
* Edge cases (empty input, all-filtered, None dimensions)
"""

from __future__ import annotations

from ytd_wrap.core.format_filter import (
    deduplicate_formats,
    filter_adaptive_video_only,
    select_adaptive_formats,
    sort_formats,
)
from ytd_wrap.core.models import VideoFormat


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def _fmt(
    *,
    format_id: str = "100",
    ext: str = "mp4",
    height: int | None = 1080,
    fps: int | None = 30,
    filesize: int | None = 50_000_000,
    vcodec: str = "avc1.640028",
    acodec: str = "none",
) -> VideoFormat:
    return VideoFormat(
        format_id=format_id,
        ext=ext,
        height=height,
        fps=fps,
        filesize=filesize,
        vcodec=vcodec,
        acodec=acodec,
    )


# ---------------------------------------------------------------------------
# filter_adaptive_video_only
# ---------------------------------------------------------------------------

class TestFilterAdaptiveVideoOnly:
    def test_keeps_video_only_formats(self) -> None:
        formats = [
            _fmt(vcodec="avc1", acodec="none"),
            _fmt(vcodec="vp9", acodec="none"),
        ]
        result = filter_adaptive_video_only(formats)
        assert len(result) == 2

    def test_removes_audio_only(self) -> None:
        audio = _fmt(vcodec="none", acodec="opus")
        result = filter_adaptive_video_only([audio])
        assert result == []

    def test_removes_muxed(self) -> None:
        muxed = _fmt(vcodec="avc1", acodec="mp4a")
        result = filter_adaptive_video_only([muxed])
        assert result == []

    def test_removes_no_codec(self) -> None:
        no_codec = _fmt(vcodec="none", acodec="none")
        result = filter_adaptive_video_only([no_codec])
        assert result == []

    def test_empty_input(self) -> None:
        assert filter_adaptive_video_only([]) == []

    def test_mixed_keeps_only_adaptive_video(self) -> None:
        formats = [
            _fmt(format_id="1", vcodec="avc1", acodec="none"),   # keep
            _fmt(format_id="2", vcodec="none", acodec="opus"),   # audio
            _fmt(format_id="3", vcodec="avc1", acodec="mp4a"),   # muxed
            _fmt(format_id="4", vcodec="vp9", acodec="none"),    # keep
        ]
        result = filter_adaptive_video_only(formats)
        assert [f.format_id for f in result] == ["1", "4"]


# ---------------------------------------------------------------------------
# deduplicate_formats
# ---------------------------------------------------------------------------

class TestDeduplicateFormats:
    def test_no_duplicates_unchanged(self) -> None:
        formats = [
            _fmt(height=1080, fps=30, ext="mp4"),
            _fmt(height=720, fps=30, ext="mp4"),
        ]
        result = deduplicate_formats(formats)
        assert len(result) == 2

    def test_removes_exact_dupes(self) -> None:
        formats = [
            _fmt(format_id="1", height=1080, fps=30, ext="mp4"),
            _fmt(format_id="2", height=1080, fps=30, ext="mp4"),
        ]
        result = deduplicate_formats(formats)
        assert len(result) == 1
        assert result[0].format_id == "1"  # first wins

    def test_different_ext_not_deduped(self) -> None:
        formats = [
            _fmt(height=1080, fps=30, ext="mp4"),
            _fmt(height=1080, fps=30, ext="webm"),
        ]
        result = deduplicate_formats(formats)
        assert len(result) == 2

    def test_different_fps_not_deduped(self) -> None:
        formats = [
            _fmt(height=1080, fps=30, ext="mp4"),
            _fmt(height=1080, fps=60, ext="mp4"),
        ]
        result = deduplicate_formats(formats)
        assert len(result) == 2

    def test_empty_input(self) -> None:
        assert deduplicate_formats([]) == []

    def test_none_dimensions_treated_as_key(self) -> None:
        formats = [
            _fmt(format_id="1", height=None, fps=None, ext="mp4"),
            _fmt(format_id="2", height=None, fps=None, ext="mp4"),
        ]
        result = deduplicate_formats(formats)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# sort_formats
# ---------------------------------------------------------------------------

class TestSortFormats:
    def test_height_descending(self) -> None:
        formats = [
            _fmt(height=480, fps=30),
            _fmt(height=1080, fps=30),
            _fmt(height=720, fps=30),
        ]
        result = sort_formats(formats)
        assert [f.height for f in result] == [1080, 720, 480]

    def test_fps_descending_within_same_height(self) -> None:
        formats = [
            _fmt(height=1080, fps=30),
            _fmt(height=1080, fps=60),
        ]
        result = sort_formats(formats)
        assert [f.fps for f in result] == [60, 30]

    def test_mp4_preferred_within_same_resolution(self) -> None:
        formats = [
            _fmt(height=1080, fps=30, ext="webm"),
            _fmt(height=1080, fps=30, ext="mp4"),
        ]
        result = sort_formats(formats)
        assert [f.ext for f in result] == ["mp4", "webm"]

    def test_none_height_sorted_last(self) -> None:
        formats = [
            _fmt(height=None, fps=30),
            _fmt(height=720, fps=30),
        ]
        result = sort_formats(formats)
        assert [f.height for f in result] == [720, None]

    def test_none_fps_treated_as_zero(self) -> None:
        formats = [
            _fmt(height=1080, fps=None),
            _fmt(height=1080, fps=30),
        ]
        result = sort_formats(formats)
        assert [f.fps for f in result] == [30, None]

    def test_empty_input(self) -> None:
        assert sort_formats([]) == []

    def test_full_sort_order(self) -> None:
        """Combined test: height > fps > ext preference."""
        formats = [
            _fmt(format_id="a", height=720, fps=30, ext="webm"),
            _fmt(format_id="b", height=1080, fps=30, ext="webm"),
            _fmt(format_id="c", height=1080, fps=60, ext="mp4"),
            _fmt(format_id="d", height=1080, fps=30, ext="mp4"),
            _fmt(format_id="e", height=720, fps=60, ext="mp4"),
        ]
        result = sort_formats(formats)
        assert [f.format_id for f in result] == ["c", "d", "b", "e", "a"]


# ---------------------------------------------------------------------------
# select_adaptive_formats (full pipeline)
# ---------------------------------------------------------------------------

class TestSelectAdaptiveFormats:
    def test_end_to_end(self) -> None:
        formats = [
            _fmt(format_id="audio", vcodec="none", acodec="opus"),
            _fmt(format_id="muxed", vcodec="avc1", acodec="mp4a"),
            _fmt(format_id="low", height=480, fps=30, ext="mp4",
                 vcodec="avc1", acodec="none"),
            _fmt(format_id="high", height=1080, fps=30, ext="mp4",
                 vcodec="avc1", acodec="none"),
            _fmt(format_id="dup", height=1080, fps=30, ext="mp4",
                 vcodec="avc1", acodec="none"),
        ]
        result = select_adaptive_formats(formats)
        # audio and muxed filtered, dup removed, sorted high → low
        assert len(result) == 2
        assert result[0].height == 1080
        assert result[1].height == 480

    def test_empty_when_no_adaptive(self) -> None:
        formats = [
            _fmt(vcodec="avc1", acodec="mp4a"),  # muxed
        ]
        assert select_adaptive_formats(formats) == []

    def test_empty_input(self) -> None:
        assert select_adaptive_formats([]) == []
