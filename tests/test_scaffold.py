"""Phase 1 smoke tests — verify scaffold wiring.

These tests prove that:
* The CLI entry point is importable and callable.
* The exception hierarchy is correctly structured.
* Version is accessible.
* Exit codes are defined.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ytd_wrap import __version__
from ytd_wrap.cli import exit_codes
from ytd_wrap.cli.app import main
from ytd_wrap.exceptions import (
    DownloadFailedError,
    EnvironmentCheckError,
    FfmpegNotFoundError,
    FormatSelectionError,
    InvalidURLError,
    MetadataExtractionError,
    VideoUnavailableError,
    YtdWrapError,
)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_is_string(self) -> None:
        assert isinstance(__version__, str)

    def test_version_is_semver_like(self) -> None:
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptions:
    @pytest.mark.parametrize(
        "exc_class",
        [
            InvalidURLError,
            MetadataExtractionError,
            VideoUnavailableError,
            FormatSelectionError,
            DownloadFailedError,
            FfmpegNotFoundError,
            EnvironmentCheckError,
        ],
    )
    def test_all_exceptions_inherit_from_base(
        self, exc_class: type[YtdWrapError]
    ) -> None:
        assert issubclass(exc_class, YtdWrapError)

    def test_base_inherits_from_exception(self) -> None:
        assert issubclass(YtdWrapError, Exception)

    def test_hint_is_stored(self) -> None:
        err = YtdWrapError("boom", hint="try this")
        assert str(err) == "boom"
        assert err.hint == "try this"

    def test_hint_defaults_to_none(self) -> None:
        err = YtdWrapError("boom")
        assert err.hint is None


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

class TestExitCodes:
    def test_success_is_zero(self) -> None:
        assert exit_codes.SUCCESS == 0

    def test_general_error_is_one(self) -> None:
        assert exit_codes.GENERAL_ERROR == 1

    def test_keyboard_interrupt_is_130(self) -> None:
        assert exit_codes.KEYBOARD_INTERRUPT == 130

    def test_unexpected_error_is_two(self) -> None:
        assert exit_codes.UNEXPECTED_ERROR == 2


# ---------------------------------------------------------------------------
# CLI routing (skeleton)
# ---------------------------------------------------------------------------

class TestCLIRouting:
    def test_no_args_returns_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        """No arguments should print help and exit 0."""
        code = main([])
        assert code == exit_codes.SUCCESS

    def test_version_flag(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    @patch("ytd_wrap.cli.doctor.run_doctor", return_value=exit_codes.SUCCESS)
    def test_doctor_returns_success(self, _mock_doc: object) -> None:
        code = main(["doctor"])
        assert code == exit_codes.SUCCESS

    def test_url_returns_success(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """URL argument should route to _handle_download (mocked)."""
        from ytd_wrap.cli import app as app_module

        monkeypatch.setattr(
            app_module, "_handle_download", lambda url: exit_codes.SUCCESS,
        )
        code = main(["https://www.youtube.com/watch?v=dQw4w9WgXcQ"])
        assert code == exit_codes.SUCCESS
