"""Unit tests for mutmut_win.test_mapping."""

from __future__ import annotations

import pytest

from mutmut_win.test_mapping import (
    is_mutated_method_name,
    mangled_name_from_mutant_name,
    orig_function_and_class_names_from_key,
    tests_for_mutant_names,
)
from mutmut_win.trampoline import CLASS_NAME_SEPARATOR

# ---------------------------------------------------------------------------
# mangled_name_from_mutant_name
# ---------------------------------------------------------------------------


class TestMangledNameFromMutantName:
    def test_top_level_function(self) -> None:
        name = "src.module.x_my_func__mutmut_1"
        assert mangled_name_from_mutant_name(name) == "src.module.x_my_func"

    def test_class_method(self) -> None:
        sep = CLASS_NAME_SEPARATOR
        name = f"src.module.x{sep}MyClass{sep}my_method__mutmut_3"
        assert mangled_name_from_mutant_name(name) == f"src.module.x{sep}MyClass{sep}my_method"

    def test_missing_mutmut_marker_raises(self) -> None:
        with pytest.raises(ValueError, match="missing '__mutmut_'"):
            mangled_name_from_mutant_name("src.module.x_my_func")

    def test_strips_only_at_mutmut_boundary(self) -> None:
        # The partition is on the first occurrence of __mutmut_.
        name = "pkg.mod.x_func__mutmut_10"
        result = mangled_name_from_mutant_name(name)
        assert result == "pkg.mod.x_func"
        assert "__mutmut_" not in result

    def test_multiple_mutmut_in_name(self) -> None:
        # partition takes the first occurrence; the rest is discarded.
        name = "pkg.mod.x_func__mutmut_1__mutmut_extra"
        result = mangled_name_from_mutant_name(name)
        assert result == "pkg.mod.x_func"


# ---------------------------------------------------------------------------
# orig_function_and_class_names_from_key
# ---------------------------------------------------------------------------


class TestOrigFunctionAndClassNamesFromKey:
    def test_top_level_function(self) -> None:
        name = "src.module.x_my_func__mutmut_1"
        func, cls = orig_function_and_class_names_from_key(name)
        assert func == "my_func"
        assert cls is None

    def test_class_method(self) -> None:
        sep = CLASS_NAME_SEPARATOR
        name = f"src.module.x{sep}MyClass{sep}my_method__mutmut_2"
        func, cls = orig_function_and_class_names_from_key(name)
        assert func == "my_method"
        assert cls == "MyClass"

    def test_nested_package_top_level(self) -> None:
        name = "a.b.c.x_helper__mutmut_5"
        func, cls = orig_function_and_class_names_from_key(name)
        assert func == "helper"
        assert cls is None

    def test_nested_package_method(self) -> None:
        sep = CLASS_NAME_SEPARATOR
        name = f"a.b.c.x{sep}Svc{sep}process__mutmut_0"
        func, cls = orig_function_and_class_names_from_key(name)
        assert func == "process"
        assert cls == "Svc"

    def test_bad_prefix_raises(self) -> None:
        # User input errors are explicit and remain enforced under ``python -O``.
        name = "src.module.bad_func__mutmut_1"
        with pytest.raises(ValueError, match="Malformed mutant function prefix"):
            orig_function_and_class_names_from_key(name)

    def test_malformed_class_method_raises_value_error(self) -> None:
        name = f"src.module.x{CLASS_NAME_SEPARATOR}OnlyClass__mutmut_1"
        with pytest.raises(ValueError, match="Malformed class-method mutant name"):
            orig_function_and_class_names_from_key(name)


# ---------------------------------------------------------------------------
# is_mutated_method_name
# ---------------------------------------------------------------------------


class TestIsMutatedMethodName:
    def test_top_level_trampoline_name(self) -> None:
        assert is_mutated_method_name("x_my_func__mutmut_1") is True

    def test_class_method_trampoline_name(self) -> None:
        sep = CLASS_NAME_SEPARATOR
        assert is_mutated_method_name(f"x{sep}MyClass{sep}my_method__mutmut_2") is True

    def test_orig_trampoline_name(self) -> None:
        # The __orig__ variant should also match (it contains __mutmut).
        assert is_mutated_method_name("x_my_func__mutmut_orig") is True

    def test_plain_function_name(self) -> None:
        assert is_mutated_method_name("my_func") is False

    def test_starts_with_x_but_no_mutmut(self) -> None:
        assert is_mutated_method_name("x_regular_function") is False

    def test_has_mutmut_but_bad_prefix(self) -> None:
        assert is_mutated_method_name("regular__mutmut_1") is False

    def test_empty_string(self) -> None:
        assert is_mutated_method_name("") is False


# ---------------------------------------------------------------------------
# tests_for_mutant_names
# ---------------------------------------------------------------------------


class TestTestsForMutantNames:
    def test_exact_match_returns_tests(self) -> None:
        mapping = {"src.module.x_func": {"tests/test_foo.py::test_a"}}
        result = tests_for_mutant_names(["src.module.x_func__mutmut_1"], mapping)
        assert result == {"tests/test_foo.py::test_a"}

    def test_unknown_name_returns_empty_set(self) -> None:
        mapping: dict[str, set[str]] = {}
        result = tests_for_mutant_names(["src.module.x_unknown__mutmut_1"], mapping)
        assert result == set()

    def test_wildcard_matches_multiple(self) -> None:
        mapping = {
            "src.module.x_func_a": {"tests/test_foo.py::test_a"},
            "src.module.x_func_b": {"tests/test_foo.py::test_b"},
            "other.x_other": {"tests/test_other.py::test_x"},
        }
        result = tests_for_mutant_names(["src.module.*"], mapping)
        assert "tests/test_foo.py::test_a" in result
        assert "tests/test_foo.py::test_b" in result
        assert "tests/test_other.py::test_x" not in result

    def test_multiple_mutant_names_union(self) -> None:
        mapping = {
            "pkg.x_a": {"tests/t.py::test_a"},
            "pkg.x_b": {"tests/t.py::test_b"},
        }
        result = tests_for_mutant_names(["pkg.x_a__mutmut_1", "pkg.x_b__mutmut_1"], mapping)
        assert result == {"tests/t.py::test_a", "tests/t.py::test_b"}

    def test_empty_mutant_names_returns_empty_set(self) -> None:
        mapping = {"pkg.x_a": {"tests/t.py::test_a"}}
        result = tests_for_mutant_names([], mapping)
        assert result == set()

    def test_wildcard_no_match_returns_empty(self) -> None:
        mapping = {"pkg.x_a": {"tests/t.py::test_a"}}
        result = tests_for_mutant_names(["nonexistent.*"], mapping)
        assert result == set()

    def test_star_pattern_with_mutant_suffix_matches_function_mapping(self) -> None:
        mapping = {
            "pkg.x_func_a": {"tests/t.py::test_a"},
            "pkg.x_func_b": {"tests/t.py::test_b"},
        }
        result = tests_for_mutant_names(["pkg.x_func_*__mutmut_*"], mapping)

        assert result == {"tests/t.py::test_a", "tests/t.py::test_b"}

    def test_question_mark_pattern_is_supported(self) -> None:
        mapping = {
            "pkg.x_func_a": {"tests/t.py::test_a"},
            "pkg.x_func_ab": {"tests/t.py::test_ab"},
        }
        result = tests_for_mutant_names(["pkg.x_func_?__mutmut_1"], mapping)

        assert result == {"tests/t.py::test_a"}

    def test_character_class_pattern_is_supported(self) -> None:
        mapping = {
            "pkg.x_func_a": {"tests/t.py::test_a"},
            "pkg.x_func_b": {"tests/t.py::test_b"},
            "pkg.x_func_c": {"tests/t.py::test_c"},
        }
        result = tests_for_mutant_names(["pkg.x_func_[ab]__mutmut_[12]"], mapping)

        assert result == {"tests/t.py::test_a", "tests/t.py::test_b"}

    def test_exact_mangled_function_name_without_suffix_is_accepted(self) -> None:
        mapping = {"pkg.x_func": {"tests/t.py::test_func"}}

        assert tests_for_mutant_names(["pkg.x_func"], mapping) == {"tests/t.py::test_func"}

    def test_malformed_user_input_is_an_empty_match_not_an_assertion(self) -> None:
        mapping = {"pkg.x_func": {"tests/t.py::test_func"}}

        assert tests_for_mutant_names(["not-a-mutant"], mapping) == set()

    def test_returns_set_not_list(self) -> None:
        mapping = {"pkg.x_a": {"tests/t.py::test_a", "tests/t.py::test_b"}}
        result = tests_for_mutant_names(["pkg.x_a__mutmut_1"], mapping)
        assert isinstance(result, set)

    def test_multiple_tests_per_mangled_name(self) -> None:
        tests_set = {"tests/t.py::test_1", "tests/t.py::test_2", "tests/t.py::test_3"}
        mapping = {"pkg.x_func": tests_set}
        result = tests_for_mutant_names(["pkg.x_func__mutmut_1"], mapping)
        assert result == tests_set
