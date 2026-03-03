"""Tests for ytd_wrap.core.resolver — URL classification."""

import pytest

from ytd_wrap.core.resolver import (
    detect_url_type,
    is_direct_stream,
    is_social_media,
    is_valid_url,
)


# ──────────────────────────────────────────────────────────────────────────────
# is_valid_url
# ──────────────────────────────────────────────────────────────────────────────

class TestIsValidUrl:
    def test_https_url_is_valid(self) -> None:
        assert is_valid_url("https://www.youtube.com/watch?v=abc") is True

    def test_http_url_is_valid(self) -> None:
        assert is_valid_url("http://example.com/video.mp4") is True

    def test_ftp_scheme_is_invalid(self) -> None:
        assert is_valid_url("ftp://files.example.com/video.mp4") is False

    def test_no_scheme_is_invalid(self) -> None:
        assert is_valid_url("www.youtube.com/watch?v=abc") is False

    def test_empty_string_is_invalid(self) -> None:
        assert is_valid_url("") is False

    def test_no_netloc_is_invalid(self) -> None:
        assert is_valid_url("https://") is False

    def test_plain_text_is_invalid(self) -> None:
        assert is_valid_url("not a url at all") is False


# ──────────────────────────────────────────────────────────────────────────────
# is_direct_stream
# ──────────────────────────────────────────────────────────────────────────────

class TestIsDirectStream:
    def test_m3u8_extension(self) -> None:
        assert is_direct_stream("https://cdn.example.com/stream.m3u8") is True

    def test_mp4_extension(self) -> None:
        assert is_direct_stream("https://cdn.example.com/video.mp4") is True

    def test_mkv_extension(self) -> None:
        assert is_direct_stream("https://cdn.example.com/video.mkv") is True

    def test_webm_extension(self) -> None:
        assert is_direct_stream("https://cdn.example.com/clip.webm") is True

    def test_hls_path_segment(self) -> None:
        assert is_direct_stream("https://cdn.example.com/hls/1080/playlist") is True

    def test_manifest_path(self) -> None:
        assert is_direct_stream("https://cdn.example.com/manifest/video") is True

    def test_akamaized_cdn(self) -> None:
        assert is_direct_stream("https://abc.akamaized.net/video/segment.ts") is True

    def test_googlevideo(self) -> None:
        assert is_direct_stream("https://r1---sn.googlevideo.com/videoplayback") is True

    def test_social_url_is_not_direct(self) -> None:
        assert is_direct_stream("https://www.youtube.com/watch?v=abc") is False

    def test_html_page_is_not_direct(self) -> None:
        assert is_direct_stream("https://example.com/page") is False


# ──────────────────────────────────────────────────────────────────────────────
# is_social_media
# ──────────────────────────────────────────────────────────────────────────────

class TestIsSocialMedia:
    def test_youtube_com(self) -> None:
        assert is_social_media("https://www.youtube.com/watch?v=abc") is True

    def test_youtu_be_short(self) -> None:
        assert is_social_media("https://youtu.be/abc") is True

    def test_twitter_com(self) -> None:
        assert is_social_media("https://twitter.com/user/status/123") is True

    def test_x_com(self) -> None:
        assert is_social_media("https://x.com/user/status/123") is True

    def test_instagram_com(self) -> None:
        assert is_social_media("https://www.instagram.com/p/abc") is True

    def test_tiktok_com(self) -> None:
        assert is_social_media("https://www.tiktok.com/@user/video/123") is True

    def test_twitch_tv(self) -> None:
        assert is_social_media("https://www.twitch.tv/videos/123") is True

    def test_vimeo_com(self) -> None:
        assert is_social_media("https://vimeo.com/123456") is True

    def test_mobile_subdomain(self) -> None:
        # m.youtube.com should still match youtube.com
        assert is_social_media("https://m.youtube.com/watch?v=abc") is True

    def test_unknown_domain_is_not_social(self) -> None:
        assert is_social_media("https://randomsite.com/video") is False

    def test_cdn_url_is_not_social(self) -> None:
        assert is_social_media("https://cdn.example.com/video.mp4") is False


# ──────────────────────────────────────────────────────────────────────────────
# detect_url_type
# ──────────────────────────────────────────────────────────────────────────────

class TestDetectUrlType:
    def test_youtube_returns_social(self) -> None:
        assert detect_url_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "social"

    def test_twitter_returns_social(self) -> None:
        assert detect_url_type("https://twitter.com/user/status/123") == "social"

    def test_m3u8_returns_direct(self) -> None:
        assert detect_url_type("https://cdn.example.com/stream.m3u8") == "direct"

    def test_mp4_cdn_returns_direct(self) -> None:
        assert detect_url_type("https://media.akamaized.net/video.mp4") == "direct"

    def test_unknown_domain_returns_unknown(self) -> None:
        assert detect_url_type("https://example.com/page") == "unknown"

    def test_invalid_url_returns_unknown(self) -> None:
        assert detect_url_type("not-a-url") == "unknown"

    def test_social_takes_precedence_over_direct_pattern(self) -> None:
        # If a social-media domain URL also matches a direct pattern it's still "social"
        url = "https://www.youtube.com/hls/live"
        assert detect_url_type(url) == "social"

    def test_non_m3u8_returns_false(self) -> None:
        pass
