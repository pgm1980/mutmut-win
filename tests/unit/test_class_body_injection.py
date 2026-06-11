"""Tests for the mutants-dict placement (Issue #77, audit A1-MT-004/005).

The lookup dict used to be emitted INTO the class body.  A dict is no
descriptor, so ``enum.Enum`` turned it into a phantom member
(``list(Color)`` returned ``['RED', 'xǁColorǁdescribe__mutmut_mutants']``),
and the ``ClassVar[Annotated[...]]`` annotation crashed ``NamedTuple``
creation at import time.  The dict now lives at module level (referencing
the methods via ``ClassName.<mutant>``); the ``_orig`` copy and the mutant
functions stay inside the class so methods keep their ``__class__`` cell
(zero-arg ``super()``).
"""

from __future__ import annotations

import os
from typing import Any

from mutmut_win.mutation import mutate_file_contents


def _exec_clean(source: str) -> dict[str, Any]:
    code, _names = mutate_file_contents("m.py", source)
    namespace: dict[str, Any] = {"__name__": "m"}
    old = os.environ.get("MUTANT_UNDER_TEST")
    os.environ["MUTANT_UNDER_TEST"] = ""
    try:
        exec(compile(code, "m", "exec"), namespace)  # noqa: S102
    finally:
        if old is None:
            del os.environ["MUTANT_UNDER_TEST"]
        else:
            os.environ["MUTANT_UNDER_TEST"] = old
    return namespace


class TestEnumStaysClean:
    def test_enum_members_unpolluted(self) -> None:
        source = (
            "import enum\n"
            "class Color(enum.Enum):\n"
            "    RED = 1\n"
            "    def describe(self):\n"
            "        return 1 + 1\n"
        )
        ns = _exec_clean(source)
        assert [m.name for m in ns["Color"]] == ["RED"]

    def test_enum_method_still_dispatches_clean(self) -> None:
        source = (
            "import enum\n"
            "class Color(enum.Enum):\n"
            "    RED = 1\n"
            "    def describe(self):\n"
            "        return 1 + 1\n"
        )
        ns = _exec_clean(source)
        assert ns["Color"].RED.describe() == 2


class TestNamedTupleImports:
    def test_namedtuple_with_method_executes(self) -> None:
        source = (
            "from typing import NamedTuple\n"
            "class P(NamedTuple):\n"
            "    a: int\n"
            "    b: int\n"
            "    def total(self):\n"
            "        return self.a + self.b\n"
        )
        ns = _exec_clean(source)  # used to raise TypeError at class creation
        assert ns["P"](1, 2).total() == 3


class TestDispatchRegression:
    def test_clean_run_uses_original(self) -> None:
        source = "class C:\n    def m(self):\n        return 1 + 1\n"
        ns = _exec_clean(source)
        assert ns["C"]().m() == 2

    def test_mutant_activation_via_module_level_dict(self) -> None:
        source = "class C:\n    def m(self):\n        return 1 + 1\n"
        code, names = mutate_file_contents("m.py", source)
        target = next(n for n in names if "ǁCǁ" in n)
        namespace: dict[str, Any] = {"__name__": "m"}
        old = os.environ.get("MUTANT_UNDER_TEST")
        os.environ["MUTANT_UNDER_TEST"] = f"m.{target}"
        try:
            exec(compile(code, "m", "exec"), namespace)  # noqa: S102
            result = namespace["C"]().m()
        finally:
            if old is None:
                del os.environ["MUTANT_UNDER_TEST"]
            else:
                os.environ["MUTANT_UNDER_TEST"] = old
        assert result != 2  # the activated mutant changes the arithmetic

    def test_zero_arg_super_still_works(self) -> None:
        source = (
            "class Base:\n"
            "    def m(self):\n"
            "        return 10 + 10\n"
            "class Child(Base):\n"
            "    def m(self):\n"
            "        return super().m() + 1\n"
        )
        ns = _exec_clean(source)
        assert ns["Child"]().m() == 21
