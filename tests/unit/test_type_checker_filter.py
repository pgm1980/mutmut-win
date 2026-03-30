"""Unit tests for mutmut_win.type_checker_filter."""

from __future__ import annotations

from pathlib import Path

import libcst as cst
import pytest

from mutmut_win.type_checker_filter import (
    FailedTypeCheckMutant,
    MutatedMethodLocation,
    MutatedMethodsCollector,
    group_by_path,
    is_mutated_method_name,
)
from mutmut_win.type_checking import TypeCheckingError

# ---------------------------------------------------------------------------
# is_mutated_method_name
# ---------------------------------------------------------------------------


class TestIsMutatedMethodName:
    def test_x_prefix_with_mutmut_marker(self) -> None:
        assert is_mutated_method_name("x_foo__mutmut_1") is True

    def test_class_separator_prefix_with_mutmut_marker(self) -> None:
        assert is_mutated_method_name("xǁMyClassǁfoo__mutmut_1") is True

    def test_plain_name_is_not_mutated(self) -> None:
        assert is_mutated_method_name("foo") is False

    def test_x_prefix_without_mutmut_marker(self) -> None:
        assert is_mutated_method_name("x_foo") is False

    def test_mutmut_marker_without_x_prefix(self) -> None:
        assert is_mutated_method_name("foo__mutmut_1") is False

    @pytest.mark.parametrize(
        "name",
        [
            "x_add__mutmut_1",
            "x_complex_name__mutmut_42",
            "xǁMyClassǁmethod__mutmut_7",
        ],
    )
    def test_valid_trampoline_names(self, name: str) -> None:
        assert is_mutated_method_name(name) is True


# ---------------------------------------------------------------------------
# MutatedMethodLocation dataclass
# ---------------------------------------------------------------------------


class TestMutatedMethodLocation:
    def test_construction(self) -> None:
        loc = MutatedMethodLocation(
            file=Path("src/mymod.py"),
            function_name="x_foo__mutmut_1",
            line_number_start=10,
            line_number_end=15,
        )
        assert loc.file == Path("src/mymod.py")
        assert loc.function_name == "x_foo__mutmut_1"
        assert loc.line_number_start == 10
        assert loc.line_number_end == 15


# ---------------------------------------------------------------------------
# FailedTypeCheckMutant dataclass
# ---------------------------------------------------------------------------


class TestFailedTypeCheckMutant:
    def test_construction(self) -> None:
        loc = MutatedMethodLocation(
            file=Path("src/mymod.py"),
            function_name="x_foo__mutmut_1",
            line_number_start=5,
            line_number_end=8,
        )
        error = TypeCheckingError(
            file_path=Path("src/mymod.py"),
            line_number=6,
            error_description="Type error",
        )
        mutant = FailedTypeCheckMutant(
            method_location=loc,
            name="mymod.x_foo__mutmut_1",
            error=error,
        )
        assert mutant.name == "mymod.x_foo__mutmut_1"
        assert mutant.error.line_number == 6
        assert mutant.method_location.line_number_start == 5


# ---------------------------------------------------------------------------
# group_by_path
# ---------------------------------------------------------------------------


class TestGroupByPath:
    def test_empty_list(self) -> None:
        result = group_by_path([])
        assert result == {}

    def test_single_error(self) -> None:
        error = TypeCheckingError(
            file_path=Path("src/foo.py"),
            line_number=1,
            error_description="err",
        )
        result = group_by_path([error])
        assert Path("src/foo.py") in result
        assert result[Path("src/foo.py")] == [error]

    def test_groups_by_path(self) -> None:
        err1 = TypeCheckingError(
            file_path=Path("src/foo.py"), line_number=1, error_description="a"
        )
        err2 = TypeCheckingError(
            file_path=Path("src/foo.py"), line_number=2, error_description="b"
        )
        err3 = TypeCheckingError(
            file_path=Path("src/bar.py"), line_number=5, error_description="c"
        )
        result = group_by_path([err1, err2, err3])
        assert len(result) == 2
        assert len(result[Path("src/foo.py")]) == 2
        assert len(result[Path("src/bar.py")]) == 1


# ---------------------------------------------------------------------------
# MutatedMethodsCollector CST visitor
# ---------------------------------------------------------------------------

_SIMPLE_MUTATED_SOURCE = """\
def x_foo__mutmut_1(x):
    return x + 1

def normal_function():
    return 42

def x_bar__mutmut_2(y):
    return y * 2
"""

_NO_MUTATED_SOURCE = """\
def foo():
    return 1

def bar():
    return 2
"""


class TestMutatedMethodsCollector:
    def _collect(self, source: str, file: Path = Path("test.py")) -> MutatedMethodsCollector:
        tree = cst.parse_module(source)
        wrapper = cst.MetadataWrapper(tree)
        visitor = MutatedMethodsCollector(file)
        wrapper.visit(visitor)
        return visitor

    def test_finds_mutated_methods(self) -> None:
        collector = self._collect(_SIMPLE_MUTATED_SOURCE)
        names = [m.function_name for m in collector.found_mutants]
        assert "x_foo__mutmut_1" in names
        assert "x_bar__mutmut_2" in names

    def test_does_not_collect_normal_functions(self) -> None:
        collector = self._collect(_SIMPLE_MUTATED_SOURCE)
        names = [m.function_name for m in collector.found_mutants]
        assert "normal_function" not in names

    def test_no_mutants_in_clean_source(self) -> None:
        collector = self._collect(_NO_MUTATED_SOURCE)
        assert collector.found_mutants == []

    def test_stores_file_path(self) -> None:
        path = Path("src/mymodule.py")
        collector = self._collect(_SIMPLE_MUTATED_SOURCE, file=path)
        assert all(m.file == path for m in collector.found_mutants)

    def test_line_numbers_are_positive(self) -> None:
        collector = self._collect(_SIMPLE_MUTATED_SOURCE)
        for mutant in collector.found_mutants:
            assert mutant.line_number_start >= 1
            assert mutant.line_number_end >= mutant.line_number_start

    def test_line_numbers_are_ordered(self) -> None:
        collector = self._collect(_SIMPLE_MUTATED_SOURCE)
        assert len(collector.found_mutants) == 2
        # x_foo comes before x_bar in the source
        assert collector.found_mutants[0].function_name == "x_foo__mutmut_1"
        assert collector.found_mutants[1].function_name == "x_bar__mutmut_2"
        assert (
            collector.found_mutants[0].line_number_start
            < collector.found_mutants[1].line_number_start
        )

    def test_count_matches_mutated_methods(self) -> None:
        collector = self._collect(_SIMPLE_MUTATED_SOURCE)
        assert len(collector.found_mutants) == 2
