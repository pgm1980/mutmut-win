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

import pytest

from mutmut_win.mutation import mutate_file_contents


def _exec_clean(source: str) -> dict[str, Any]:
    code, _names = mutate_file_contents("m.py", source)
    namespace: dict[str, Any] = {"__name__": "m"}
    old = os.environ.get("MUTANT_UNDER_TEST")
    os.environ["MUTANT_UNDER_TEST"] = ""
    try:
        exec(compile(code, "m", "exec"), namespace)  # noqa: S102  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected — executing our own codegen output IS the test purpose
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
            exec(compile(code, "m", "exec"), namespace)  # noqa: S102  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected — executing our own codegen output IS the test purpose
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


class TestClassCreationTimeCalls:
    """M-039: a method called while its own class is being built.

    The method wrapper resolves ``<mangled>_orig_ref`` / ``<mangled>_mutants``
    as module-level names, which used to be bound only AFTER the class
    statement.  A call during class creation — enum member creation invoking
    ``__init__`` or ``_generate_next_value_``, a class attribute computed
    from an own method, a decorator defined in the class body — therefore
    died with NameError at import time.
    """

    def test_enum_init_called_during_member_creation(self) -> None:
        source = (
            "import enum\n"
            "class Color(enum.Enum):\n"
            "    RED = 1\n"
            "    BLUE = 2\n"
            "    def __init__(self, value):\n"
            "        self.double = value * 2\n"
        )
        ns = _exec_clean(source)  # used to raise NameError at exec
        assert ns["Color"].BLUE.double == 4
        assert [member.name for member in ns["Color"]] == ["RED", "BLUE"]

    def test_enum_generate_next_value_called_for_auto_members(self) -> None:
        source = (
            "import enum\n"
            "class Letter(enum.Enum):\n"
            "    def _generate_next_value_(name, start, count, last):\n"
            "        return count + 1\n"
            "    a = enum.auto()\n"
            "    b = enum.auto()\n"
        )
        ns = _exec_clean(source)  # used to raise NameError at exec
        assert ns["Letter"].a.value == 1
        assert ns["Letter"].b.value == 2

    def test_class_attribute_from_own_method_call(self) -> None:
        source = "class K:\n    def helper(x):\n        return x + 1\n    VALUE = helper(1)\n"
        ns = _exec_clean(source)  # used to raise NameError at exec
        assert ns["K"].VALUE == 2

    def test_class_body_defined_decorator(self) -> None:
        source = (
            "class D:\n"
            "    def deco(fn):\n"
            "        marker = 1 + 1\n"
            "        return fn\n"
            "    @deco\n"
            "    def m(self):\n"
            "        return 3 + 4\n"
        )
        ns = _exec_clean(source)  # used to raise NameError when @deco applied
        assert ns["D"]().m() == 7

    def test_mutant_activation_during_class_creation(self) -> None:
        # The creation-time bindings must also carry the in-body mutants
        # dict and the ``__name__`` assignment: without them a mutant
        # activated during class creation silently runs as the original.
        source = "class K:\n    def helper(x):\n        return x + 1\n    VALUE = helper(1)\n"
        code, names = mutate_file_contents("m.py", source)
        target = next(n for n in names if "helper" in n)
        namespace: dict[str, Any] = {"__name__": "m"}
        old = os.environ.get("MUTANT_UNDER_TEST")
        os.environ["MUTANT_UNDER_TEST"] = f"m.{target}"
        try:
            exec(compile(code, "m", "exec"), namespace)  # noqa: S102  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected — executing our own codegen output IS the test purpose
            value = namespace["K"].VALUE
        finally:
            if old is None:
                del os.environ["MUTANT_UNDER_TEST"]
            else:
                os.environ["MUTANT_UNDER_TEST"] = old
        assert value != 2  # the activated mutant changes the arithmetic

    def test_creation_bindings_carry_type_ignore_comments(self) -> None:
        # The four creation-time binding lines are generated code inside the
        # user's class body; like every other codegen line they carry a
        # '# type: ignore' trailing comment so the mutants tree keeps the
        # type-check baseline quiet.
        source = "class K:\n    def m(self):\n        return 1 + 1\n"
        code, _names = mutate_file_contents("m.py", source)
        binding_lines = [
            line
            for line in code.splitlines()
            if line.startswith(
                (
                    "    global xǁKǁm__mutmut",
                    "    xǁKǁm__mutmut_orig_ref = ",
                    "    xǁKǁm__mutmut_mutants = ",
                    "    xǁKǁm__mutmut_orig.__name__",
                )
            )
        ]
        # class-body: global decl, orig_ref, mutants dict, __name__ — the
        # unindented post-class capture/lookup lines must NOT match
        assert len(binding_lines) == 4
        for line in binding_lines:
            assert line.endswith("# type: ignore"), line

    def test_top_level_functions_get_no_creation_bindings(self) -> None:
        # Creation-time bindings are a method-only concept (the wrapper
        # shares the class body); a top-level function's nodes must not
        # grow 'global' statements or early orig_ref/mutants assignments.
        source = "def f(x):\n    return x + 1\n"
        code, _names = mutate_file_contents("m.py", source)
        assert "global x_f__mutmut" not in code
        assert "x_f__mutmut_orig_ref = x_f__mutmut_orig" not in code

    @pytest.mark.parametrize(
        ("source", "class_name"),
        [
            ("class K:\n    def m(self):\n        return 1 + 1\n", "K"),
            (
                "import enum\nclass E(enum.Enum):\n    A = 1\n"
                "    def m(self):\n        return 1 + 1\n",
                "E",
            ),
            (
                "import enum\nclass I(enum.IntEnum):\n    A = 1\n"
                "    def m(self):\n        return 1 + 1\n",
                "I",
            ),
            (
                "from typing import NamedTuple\nclass P(NamedTuple):\n    a: int\n"
                "    def m(self):\n        return self.a + 1\n",
                "P",
            ),
        ],
        ids=["plain", "enum", "int-enum", "namedtuple"],
    )
    def test_class_namespace_stays_clean(self, source: str, class_name: str) -> None:
        # The 'global' creation-time binding must bypass the class
        # namespace: no enum member, no NamedTuple field, no stray attribute.
        ns = _exec_clean(source)
        polluted = [
            name for name in vars(ns[class_name]) if name.endswith(("_orig_ref", "_mutants"))
        ]
        assert polluted == []
