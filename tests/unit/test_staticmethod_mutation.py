"""W5 backport: methods decorated SOLELY with @staticmethod are mutated.

mutmut 3.5.0 skips ALL decorated methods; mutmut-win now mutates @staticmethod
methods, dispatching them through the trampoline like a free function (no
instance/class argument). @classmethod, @property and any extra decorator stay
skipped. The trampoline dispatch is exec-verified end to end.
"""

from __future__ import annotations

import os

import libcst as cst

from mutmut_win.mutation import _is_static_only, mutate_file_contents


def _exec(source: str) -> tuple[dict[str, object], list[str]]:
    code, names = mutate_file_contents("m.py", source)
    namespace: dict[str, object] = {"__name__": "m"}
    exec(code, namespace)  # noqa: S102 - exercising the generated trampoline code
    return namespace, list(names)


def _method(src: str) -> cst.FunctionDef:
    cls = cst.parse_module(src).body[0]
    assert isinstance(cls, cst.ClassDef)
    method = cls.body.body[0]
    assert isinstance(method, cst.FunctionDef)
    return method


class TestIsStaticOnly:
    def test_solely_staticmethod_is_true(self) -> None:
        assert _is_static_only(_method("class C:\n    @staticmethod\n    def f():\n        pass\n"))

    def test_classmethod_is_false(self) -> None:
        assert not _is_static_only(
            _method("class C:\n    @classmethod\n    def f(cls):\n        pass\n")
        )

    def test_undecorated_is_false(self) -> None:
        assert not _is_static_only(_method("class C:\n    def f(self):\n        pass\n"))

    def test_staticmethod_plus_other_is_false(self) -> None:
        src = "class C:\n    @staticmethod\n    @other\n    def f():\n        pass\n"
        assert not _is_static_only(_method(src))


class TestStaticMethodMutation:
    _SRC = "class C:\n    @staticmethod\n    def add(a, b):\n        return a + b\n"

    def test_staticmethod_now_produces_mutants(self) -> None:
        _ns, names = _exec(self._SRC)
        assert any("add" in n for n in names)  # 3.5.0 skipped it; W5 mutates it

    def test_orig_path_returns_the_real_value(self) -> None:
        namespace, _names = _exec(self._SRC)
        os.environ.pop("MUTANT_UNDER_TEST", None)
        cls = namespace["C"]
        assert cls.add(2, 3) == 5  # type: ignore[attr-defined]

    def test_each_mutant_dispatches_through_the_trampoline(self) -> None:
        namespace, names = _exec(self._SRC)
        cls = namespace["C"]
        add_mutants = [n for n in names if "add" in n]
        assert add_mutants
        try:
            observed = set()
            for mutant in add_mutants:
                os.environ["MUTANT_UNDER_TEST"] = "m." + mutant
                observed.add(cls.add(2, 3))  # type: ignore[attr-defined]
            assert observed != {5}  # at least one mutant alters the result
        finally:
            os.environ.pop("MUTANT_UNDER_TEST", None)
        os.environ.pop("MUTANT_UNDER_TEST", None)
        assert cls.add(2, 3) == 5  # type: ignore[attr-defined]  # orig restored

    def test_staticmethod_with_multiple_args_forwards_all(self) -> None:
        # a static method forwards EVERY parameter (no self drop) — guards the
        # forwarded-params split that W5 introduced
        ns, _names = _exec(
            "class C:\n    @staticmethod\n    def calc(a, b, c):\n        return a + b + c\n"
        )
        os.environ.pop("MUTANT_UNDER_TEST", None)
        assert ns["C"].calc(1, 2, 3) == 6  # type: ignore[attr-defined]

    def test_instance_method_with_args_unaffected(self) -> None:
        # the instance path (self + extra params) whose condition W5 split must
        # still drop self and forward the rest correctly
        ns, _names = _exec("class C:\n    def m(self, a, b):\n        return a + b + 1\n")
        os.environ.pop("MUTANT_UNDER_TEST", None)
        assert ns["C"]().m(2, 3) == 6  # type: ignore[attr-defined]


class TestDecoratedStaysSkipped:
    def test_classmethod_not_mutated(self) -> None:
        _ns, names = _exec(
            "class C:\n    @classmethod\n    def make(cls, x):\n        return x + 1\n"
        )
        assert not any("make" in n for n in names)

    def test_property_not_mutated(self) -> None:
        _ns, names = _exec("class C:\n    @property\n    def val(self):\n        return 1 + 1\n")
        assert not any("val" in n for n in names)

    def test_staticmethod_with_extra_decorator_skipped(self) -> None:
        src = (
            "def deco(f):\n    return f\n\n\n"
            "class C:\n    @deco\n    @staticmethod\n    def f(x):\n        return x + 1\n"
        )
        _ns, names = _exec(src)
        assert not any("Cǁf" in n for n in names)  # the method f stays skipped
