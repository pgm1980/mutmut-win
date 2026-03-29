"""Tests for mutmut_win.constants."""

from mutmut_win.constants import (
    EXIT_CODE_SKIPPED,
    EXIT_CODE_TIMEOUT,
    EXIT_CODE_TYPE_CHECK,
    emoji_by_status,
    status_by_exit_code,
)


class TestStatusByExitCode:
    def test_exit_0_is_survived(self) -> None:
        assert status_by_exit_code[0] == "survived"

    def test_exit_1_is_killed(self) -> None:
        assert status_by_exit_code[1] == "killed"

    def test_exit_5_is_no_tests(self) -> None:
        assert status_by_exit_code[5] == "no tests"

    def test_exit_2_is_interrupted(self) -> None:
        assert status_by_exit_code[2] == "check was interrupted by user"

    def test_exit_37_is_type_check(self) -> None:
        assert status_by_exit_code[37] == "caught by type check"

    def test_unknown_exit_code_is_suspicious(self) -> None:
        assert status_by_exit_code[999] == "suspicious"
        assert status_by_exit_code[-999] == "suspicious"

    def test_none_is_not_checked(self) -> None:
        assert status_by_exit_code[None] == "not checked"

    def test_internal_exit_code_constants(self) -> None:
        assert EXIT_CODE_TIMEOUT == 36
        assert EXIT_CODE_SKIPPED == 34
        assert EXIT_CODE_TYPE_CHECK == 37


class TestEmojiByStatus:
    def test_all_statuses_have_emoji(self) -> None:
        expected_statuses = {
            "survived",
            "no tests",
            "timeout",
            "suspicious",
            "skipped",
            "caught by type check",
            "check was interrupted by user",
            "not checked",
            "killed",
            "segfault",
        }
        assert set(emoji_by_status.keys()) == expected_statuses

    def test_killed_has_empty_emoji(self) -> None:
        assert emoji_by_status["killed"] == ""
