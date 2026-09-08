"""Second adversarial hardening round for mutation/runtime boundaries."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from mutmut_win.mutation import mutate_file_contents


def _exec_generated(
    source: str, *, mutant_under_test: str | None = None
) -> tuple[str, list[str], dict[str, Any]]:
    generated, names = mutate_file_contents("m.py", source)
    namespace: dict[str, Any] = {"__name__": "m"}
    old_mutant = os.environ.pop("MUTANT_UNDER_TEST", None)
    if mutant_under_test is not None:
        os.environ["MUTANT_UNDER_TEST"] = mutant_under_test
    try:
        # The generated string derives solely from the literal test fixture.
        exec(  # noqa: S102  # nosec B102  # nosemgrep
            compile(generated, "m", "exec", dont_inherit=True), namespace
        )
    finally:
        os.environ.pop("MUTANT_UNDER_TEST", None)
        if old_mutant is not None:
            os.environ["MUTANT_UNDER_TEST"] = old_mutant
    return generated, list(names), namespace


class TestModuleGlobalTrampolineIsolation:
    def test_source_rebinding_uses_a_collision_free_helper(self) -> None:
        source = """\
_mutmut_trampoline = "before"


def add(_mutmut_trampoline_1):
    return _mutmut_trampoline_1 + 1


_mutmut_trampoline = "after"
"""
        generated, names, namespace = _exec_generated(source)

        assert names
        assert "def _mutmut_trampoline_2(" in generated
        assert namespace["_mutmut_trampoline"] == "after"
        assert namespace["add"](2) == 3
        assert "MutantDict" not in generated
        assert "from typing import Annotated" not in generated

    def test_collision_free_helper_still_dispatches_an_active_mutant(self) -> None:
        source = """\
_mutmut_trampoline = 42


def add(value):
    return value + 1
"""
        _generated, names = mutate_file_contents("m.py", source)
        target = next(name for name in names if "x_add__mutmut" in name)

        _generated, _names, namespace = _exec_generated(source)

        assert namespace["_mutmut_trampoline"] == 42
        with patch.dict(os.environ, {"MUTANT_UNDER_TEST": f"m.{target}"}):
            assert namespace["add"](2) != 3

    def test_typing_scaffold_no_longer_overwrites_user_globals(self) -> None:
        source = """\
Annotated = object()
Callable = object()
ClassVar = object()
MutantDict = object()
before = (Annotated, Callable, ClassVar, MutantDict)


def values():
    return (Annotated, Callable, ClassVar, MutantDict, 1 + 1)
"""
        generated, names, namespace = _exec_generated(source)

        assert names
        assert namespace["values"]()[:4] == namespace["before"]
        assert namespace["values"]()[4] == 2
        assert "from typing import Annotated" not in generated

    def test_saved_staticmethod_survives_public_class_name_rebinding(self) -> None:
        source = """\
class C:
    @staticmethod
    def add(value):
        return value + 1


SavedC = C
C = "rebound"
"""
        _generated, names, namespace = _exec_generated(source)
        target = next(name for name in names if "add__mutmut" in name)

        assert namespace["C"] == "rebound"
        assert namespace["SavedC"].add(2) == 3
        with patch.dict(os.environ, {"MUTANT_UNDER_TEST": f"m.{target}"}):
            assert namespace["SavedC"].add(2) != 3

    def test_instance_original_uses_captured_descriptor_not_runtime_attribute(self) -> None:
        source = """\
class C:
    def add(self, value):
        return value + 1


SavedC = C
C = "rebound"
"""
        _generated, names, namespace = _exec_generated(source)
        target = next(name for name in names if "add__mutmut" in name)
        saved_class = namespace["SavedC"]

        assert saved_class().add(2) == 3
        # Legal Python unbound invocation with an object that is not a C
        # instance must retain the original function's binding behaviour.
        assert saved_class.add(object(), 2) == 3
        with patch.dict(os.environ, {"MUTANT_UNDER_TEST": f"m.{target}"}):
            assert saved_class().add(2) != 3

    def test_unbound_method_accepts_none_in_clean_and_mutant_paths(self) -> None:
        """MW221-023: ``None`` is a legal first argument, not a sentinel."""
        source = """\
class C:
    def add(self, value):
        return value + 1
"""
        _generated, names, namespace = _exec_generated(source)
        target = next(name for name in names if "add__mutmut" in name)
        saved_class = namespace["C"]

        assert saved_class.add(None, 2) == 3
        with patch.dict(os.environ, {"MUTANT_UNDER_TEST": f"m.{target}"}):
            assert saved_class.add(None, 2) != 3

    def test_static_private_namespace_collision_skips_only_that_function(self) -> None:
        source = """\
def f():
    return 1 + 1


x_f__mutmut_orig = "user-owned"
"""
        with pytest.warns(SyntaxWarning, match="internal trampoline namespace"):
            _generated, names, namespace = _exec_generated(source)

        assert not any("x_f__mutmut" in name for name in names)
        assert namespace["f"]() == 2
        assert namespace["x_f__mutmut_orig"] == "user-owned"


class TestWrapperDocstringSemantics:
    def test_leading_fstring_concatenation_side_effect_runs_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = """\
calls = []


def side_effect():
    calls.append("hit")
    return "prefix"


def value():
    f"{side_effect()}" "tail"
    return 1 + 1
"""
        _generated, names, namespace = _exec_generated(source)
        monkeypatch.delenv("MUTANT_UNDER_TEST", raising=False)

        assert names
        assert namespace["value"]() == 2
        assert namespace["calls"] == ["hit"]

    def test_indented_semicolon_docstring_is_preserved_without_double_execution(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = """\
calls = []


def value():
    "real docs"; calls.append("hit")
    return 1 + 1
"""
        _generated, names, namespace = _exec_generated(source)
        monkeypatch.delenv("MUTANT_UNDER_TEST", raising=False)

        assert names
        assert namespace["value"].__doc__ == "real docs"
        assert namespace["value"]() == 2
        assert namespace["calls"] == ["hit"]
