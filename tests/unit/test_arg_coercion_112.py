"""Issue #112 (audit A2-RN-013): shell-style CLI-arg coercion.

``pytest_add_cli_args = '-m "not slow"'`` was tokenized with a naive
``str.split()`` — pytest received ``['-m', '"not', 'slow"']``. And the
sibling field ``pytest_add_cli_args_test_selection`` accepted no string
at all. Both fields now coerce strings shell-style: quotes group,
Windows backslashes stay literal (no escape character).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win.config import MutmutConfig


class TestQuoteAwareCoercion:
    def test_quoted_marker_expression_stays_one_token(self) -> None:
        cfg = MutmutConfig(pytest_add_cli_args='-m "not slow"')  # type: ignore[arg-type]
        assert cfg.pytest_add_cli_args == ["-m", "not slow"]

    def test_single_quotes_group_too(self) -> None:
        cfg = MutmutConfig(pytest_add_cli_args="-k 'a and b' -x")  # type: ignore[arg-type]
        assert cfg.pytest_add_cli_args == ["-k", "a and b", "-x"]

    def test_test_selection_accepts_a_string(self) -> None:
        """The sibling field rejected strings outright (inconsistent)."""
        cfg = MutmutConfig(
            pytest_add_cli_args_test_selection='-m "not slow"'  # type: ignore[arg-type]
        )
        assert cfg.pytest_add_cli_args_test_selection == ["-m", "not slow"]

    def test_windows_path_backslashes_survive(self) -> None:
        """posix-shlex would eat backslashes as escapes — ours must not."""
        cfg = MutmutConfig(pytest_add_cli_args=r"--rootdir=C:\proj\sub")  # type: ignore[arg-type]
        assert cfg.pytest_add_cli_args == [r"--rootdir=C:\proj\sub"]

    def test_type_check_command_still_coerces(self) -> None:
        cfg = MutmutConfig(type_check_command="mypy src/")  # type: ignore[arg-type]
        assert cfg.type_check_command == ["mypy", "src/"]

    def test_list_input_passes_through_unchanged(self) -> None:
        cfg = MutmutConfig(
            pytest_add_cli_args=["-m", "not slow"],
            pytest_add_cli_args_test_selection=["-k", "x or y"],
        )
        assert cfg.pytest_add_cli_args == ["-m", "not slow"]
        assert cfg.pytest_add_cli_args_test_selection == ["-k", "x or y"]

    def test_empty_string_means_no_args(self) -> None:
        cfg = MutmutConfig(pytest_add_cli_args="")  # type: ignore[arg-type]
        assert cfg.pytest_add_cli_args == []

    def test_unbalanced_quote_is_a_loud_config_error(self) -> None:
        with pytest.raises(ValidationError, match="unbalanced quotes"):
            MutmutConfig(pytest_add_cli_args='-m "not slow')  # type: ignore[arg-type]


class TestCoercionProperties:
    @given(
        st.lists(
            st.text(
                alphabet=st.characters(
                    codec="ascii",
                    categories=("L", "N"),
                    include_characters="-_=./\\:",
                ),
                min_size=1,
                max_size=12,
            ),
            min_size=1,
            max_size=6,
        )
    )
    def test_space_joined_simple_tokens_round_trip(self, tokens: list[str]) -> None:
        """For tokens without quotes/whitespace, joining and coercing is the
        identity — the property the naive split() only held by accident."""
        cfg = MutmutConfig(pytest_add_cli_args=" ".join(tokens))  # type: ignore[arg-type]
        assert cfg.pytest_add_cli_args == tokens
