"""Tests for domain models (core/models.py).

All models are frozen dataclasses — these tests verify immutability,
equality semantics, and collection behaviour.
"""

from __future__ import annotations

import pytest

from ytd_wrap.core.models import FormatCollection, VideoFormat, VideoMetadata


# ---------------------------------------------------------------------------
# Fixtures — reusable model instances
# ---------------------------------------------------------------------------

def _make_format(**overrides: object) -> VideoFormat:
    """Factory with sensible defaults for concise tests."""
    defaults: dict[str, object] = {
        "format_id": "137",
        "ext": "mp4",
        "height": 1080,
        "fps": 30,
        "filesize": 50_000_000,
        "vcodec": "avc1.640028",
        "acodec": "none",
    }
    defaults.update(overrides)
    return VideoFormat(**defaults)  # type: ignore[arg-type]


def _make_metadata(**overrides: object) -> VideoMetadata:
    defaults: dict[str, object] = {
        "id": "abc123",
        "title": "Test Video",
        "duration": 120,
        "webpage_url": "https://www.youtube.com/watch?v=abc123",
    }
    defaults.update(overrides)
    return VideoMetadata(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# VideoMetadata
# ---------------------------------------------------------------------------

class TestVideoMetadata:
    def test_fields_accessible(self) -> None:
        m = _make_metadata()
        assert m.id == "abc123"
        assert m.title == "Test Video"
        assert m.duration == 120
        assert m.webpage_url == "https://www.youtube.com/watch?v=abc123"

    def test_duration_can_be_none(self) -> None:
        m = _make_metadata(duration=None)
        assert m.duration is None

    def test_frozen(self) -> None:
        m = _make_metadata()
        with pytest.raises(AttributeError):
            m.title = "Changed"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = _make_metadata()
        b = _make_metadata()
        assert a == b

    def test_inequality(self) -> None:
        a = _make_metadata(id="x")
        b = _make_metadata(id="y")
        assert a != b


# ---------------------------------------------------------------------------
# VideoFormat
# ---------------------------------------------------------------------------

class TestVideoFormat:
    def test_fields_accessible(self) -> None:
        f = _make_format()
        assert f.format_id == "137"
        assert f.ext == "mp4"
        assert f.height == 1080
        assert f.fps == 30
        assert f.filesize == 50_000_000
        assert f.vcodec == "avc1.640028"
        assert f.acodec == "none"

    def test_nullable_fields(self) -> None:
        f = _make_format(height=None, fps=None, filesize=None)
        assert f.height is None
        assert f.fps is None
        assert f.filesize is None

    def test_frozen(self) -> None:
        f = _make_format()
        with pytest.raises(AttributeError):
            f.ext = "webm"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FormatCollection
# ---------------------------------------------------------------------------

class TestFormatCollection:
    def test_len(self) -> None:
        col = FormatCollection(formats=(_make_format(), _make_format(format_id="248")))
        assert len(col) == 2

    def test_empty_is_falsy(self) -> None:
        col = FormatCollection(formats=())
        assert not col
        assert len(col) == 0

    def test_non_empty_is_truthy(self) -> None:
        col = FormatCollection(formats=(_make_format(),))
        assert col

    def test_formats_is_tuple(self) -> None:
        col = FormatCollection(formats=(_make_format(),))
        assert isinstance(col.formats, tuple)

    def test_frozen(self) -> None:
        col = FormatCollection(formats=())
        with pytest.raises(AttributeError):
            col.formats = ()  # type: ignore[misc]
