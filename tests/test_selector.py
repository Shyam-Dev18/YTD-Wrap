"""Tests for ytd_wrap.ui.selector — questionary-based format selection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ytd_wrap.utils.exceptions import FormatSelectionError, UserCancelledError


# ---------------------------------------------------------------------------
# Sample format fixtures
# ---------------------------------------------------------------------------

_FORMAT_H264 = {
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
_FORMAT_VP9 = {
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


# ---------------------------------------------------------------------------
# select_format
# ---------------------------------------------------------------------------

class TestSelectFormat:
    """Tests for select_format()."""

    def test_returns_chosen_format(self, mocker) -> None:
        """select_format() returns the format dict chosen by the user."""
        mock_ask = MagicMock(return_value=_FORMAT_H264)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=lambda title, value: value)

        from ytd_wrap.ui.selector import select_format
        result = select_format([_FORMAT_H264, _FORMAT_VP9])
        assert result == _FORMAT_H264

    def test_raises_format_selection_error_on_empty_list(self) -> None:
        """select_format() with no formats must raise FormatSelectionError."""
        from ytd_wrap.ui.selector import select_format
        with pytest.raises(FormatSelectionError):
            select_format([])

    def test_keyboard_interrupt_raises_user_cancelled(self, mocker) -> None:
        """Ctrl+C during selection raises UserCancelledError, not KeyboardInterrupt."""
        mock_ask = MagicMock(side_effect=KeyboardInterrupt)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=lambda title, value: value)

        from ytd_wrap.ui.selector import select_format
        with pytest.raises(UserCancelledError):
            select_format([_FORMAT_H264])

    def test_none_answer_raises_user_cancelled(self, mocker) -> None:
        """questionary returning None (cancelled) raises UserCancelledError."""
        mock_ask = MagicMock(return_value=None)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=lambda title, value: value)

        from ytd_wrap.ui.selector import select_format
        with pytest.raises(UserCancelledError):
            select_format([_FORMAT_H264])

    def test_does_not_propagate_bare_keyboard_interrupt(self, mocker) -> None:
        """Raw KeyboardInterrupt must never escape select_format()."""
        mock_ask = MagicMock(side_effect=KeyboardInterrupt)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=lambda title, value: value)

        from ytd_wrap.ui.selector import select_format
        try:
            select_format([_FORMAT_H264])
        except UserCancelledError:
            pass  # expected
        except KeyboardInterrupt:
            pytest.fail("KeyboardInterrupt escaped from select_format()")

    def test_choice_label_contains_resolution(self, mocker) -> None:
        """The choice label generated for each format includes the resolution."""
        captured_choices: list = []

        def fake_choice(title: str, value) -> MagicMock:
            captured_choices.append(title)
            m = MagicMock()
            m.title = title
            m.value = value
            return m

        mock_ask = MagicMock(return_value=_FORMAT_H264)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=fake_choice)

        from ytd_wrap.ui.selector import select_format
        select_format([_FORMAT_H264])
        assert any("1080p" in label for label in captured_choices)

    def test_choice_label_contains_codec_info(self, mocker) -> None:
        """The choice label includes vcodec and acodec joined with ' + '."""
        captured_choices: list = []

        def fake_choice(title: str, value) -> MagicMock:
            captured_choices.append(title)
            m = MagicMock()
            m.title = title
            m.value = value
            return m

        mock_ask = MagicMock(return_value=_FORMAT_H264)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=fake_choice)

        from ytd_wrap.ui.selector import select_format
        select_format([_FORMAT_H264])
        assert any("h264" in label and "aac" in label for label in captured_choices)

    def test_choice_label_shows_size_in_mb(self, mocker) -> None:
        """The choice label shows file size in MB when filesize is known."""
        captured_choices: list = []

        def fake_choice(title: str, value) -> MagicMock:
            captured_choices.append(title)
            m = MagicMock()
            m.title = title
            m.value = value
            return m

        mock_ask = MagicMock(return_value=_FORMAT_H264)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=fake_choice)

        from ytd_wrap.ui.selector import select_format
        select_format([_FORMAT_H264])
        assert any("MB" in label for label in captured_choices)

    def test_choice_label_shows_unknown_for_missing_size(self, mocker) -> None:
        """The choice label shows '~unknown' when filesize is None."""
        captured_choices: list = []

        def fake_choice(title: str, value) -> MagicMock:
            captured_choices.append(title)
            m = MagicMock()
            m.title = title
            m.value = value
            return m

        mock_ask = MagicMock(return_value=_FORMAT_VP9)
        mock_select_result = MagicMock()
        mock_select_result.ask = mock_ask
        mocker.patch("questionary.select", return_value=mock_select_result)
        mocker.patch("questionary.Choice", side_effect=fake_choice)

        from ytd_wrap.ui.selector import select_format
        select_format([_FORMAT_VP9])
        assert any("unknown" in label for label in captured_choices)


# ---------------------------------------------------------------------------
# confirm_download
# ---------------------------------------------------------------------------

class TestConfirmDownload:
    """Tests for confirm_download()."""

    def test_returns_true_when_user_confirms(self, mocker) -> None:
        mock_ask = MagicMock(return_value=True)
        mock_confirm_result = MagicMock()
        mock_confirm_result.ask = mock_ask
        mocker.patch("questionary.confirm", return_value=mock_confirm_result)

        from ytd_wrap.ui.selector import confirm_download
        assert confirm_download("My Video") is True

    def test_returns_false_when_user_declines(self, mocker) -> None:
        mock_ask = MagicMock(return_value=False)
        mock_confirm_result = MagicMock()
        mock_confirm_result.ask = mock_ask
        mocker.patch("questionary.confirm", return_value=mock_confirm_result)

        from ytd_wrap.ui.selector import confirm_download
        assert confirm_download("My Video") is False

    def test_returns_false_on_keyboard_interrupt(self, mocker) -> None:
        mocker.patch("questionary.confirm", side_effect=KeyboardInterrupt)

        from ytd_wrap.ui.selector import confirm_download
        assert confirm_download("My Video") is False

    def test_prompt_includes_title(self, mocker) -> None:
        """The confirm prompt should mention the video title."""
        call_args: list = []

        def fake_confirm(prompt: str, **kwargs):
            call_args.append(prompt)
            m = MagicMock()
            m.ask = MagicMock(return_value=True)
            return m

        mocker.patch("questionary.confirm", side_effect=fake_confirm)

        from ytd_wrap.ui.selector import confirm_download
        confirm_download("Awesome Clip")
        assert any("Awesome Clip" in arg for arg in call_args)
