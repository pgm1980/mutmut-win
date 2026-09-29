"""Tests for trampoline-wrapper codegen correctness (Issue #76).

Audit findings — all clean-run breakers on legal Python:
- A1-MT-001: the wrapper hardcoded ``self``; methods whose first parameter
  has another name (``__init_subclass__(cls)``, metaclass ``cls``/``mcs``,
  ``this``) raised NameError in the CLEAN run.
- A1-MT-002: the wrapper locals ``args``/``kwargs`` collided with same-named
  user parameters — silent value corruption or TypeError.
- A1-MT-003: ``args = args[1:]`` dropped the StarredElement for
  ``def m(*args)`` methods, forwarding NO arguments.
- A1-MT-006: async generators were wrapped in ``async for … yield`` which
  swallowed ``asend()`` values and bypassed ``athrow()`` handling.
"""

from __future__ import annotations

import asyncio
import keyword
import os
import unicodedata
from typing import Any

from hypothesis import assume, given
from hypothesis import strategies as st

from mutmut_win.mutation import _compiled_parameter_name, mutate_file_contents


def _exec_clean(source: str) -> tuple[dict[str, Any], list[str]]:
    code, names = mutate_file_contents("m.py", source)
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
    return namespace, list(names)


class TestFirstParamName:
    def test_init_subclass_survives_clean_run(self) -> None:
        # A1-MT-001 repro: implicit classmethod with first param ``cls``.
        # ``object.__getattribute__`` cannot dispatch through a class's MRO,
        # so implicit classmethods are excluded from mutation entirely
        # (same treatment as ``__new__``).
        source = "class A:\n    def __init_subclass__(cls, **kwargs):\n        cls.marker = 1 + 1\n"
        ns, names = _exec_clean(source)
        # Literal snippet in a codegen regression test; the next line is a
        # semgrep suppression directive, not commented-out code (ERA001 FP).
        # nosemgrep: python.lang.security.audit.exec-detected.exec-detected  # noqa: ERA001
        exec("class B(A):\n    pass", ns)  # noqa: S102  # used to raise NameError
        assert ns["B"].marker == 2
        assert not any("__init_subclass__" in n for n in names)

    def test_unconventional_self_name(self) -> None:
        source = "class C:\n    def m(this):\n        return this.v + 1\n"
        ns, _names = _exec_clean(source)
        obj = ns["C"]()
        obj.v = 1
        assert obj.m() == 2


class TestLocalCollisions:
    def test_kwonly_param_named_args(self) -> None:
        # A1-MT-002: used to return (2, [1]) — the wrapper's list leaked in.
        source = "def f(x, *, args):\n    return (x + 1, args)\n"
        ns, _names = _exec_clean(source)
        assert ns["f"](1, args=2) == (2, 2)

    def test_star_kwarg_named_args(self) -> None:
        # A1-MT-002: used to raise TypeError ('list' object is not a mapping).
        source = "def f(x, **args):\n    return (x + 1, args)\n"
        ns, _names = _exec_clean(source)
        assert ns["f"](1, k=2) == (2, {"k": 2})


class TestCompiledKeywordKeys:
    """M-040: kwargs-dict keys must be the COMPILED parameter names.

    The wrapper, the private ``_orig`` copy and every mutant of a method
    live in the class body, so CPython NFKC-normalizes every identifier
    (U+00B5 -> U+03BC) and privately mangles ``__x`` to ``_C__x``.  The
    forwarding dict key used to be the raw CST name, so even the clean
    call died with ``TypeError: unexpected keyword argument '__x'``.
    """

    def test_private_kwonly_param_in_method_forwards_mangled_key(self) -> None:
        source = "class C:\n    def m(self, *, __x=1):\n        return __x + 1\n"
        ns, _names = _exec_clean(source)
        assert ns["C"]().m() == 2
        # the compiled parameter name is '_C__x', so it is also the only
        # legal keyword to override the default with
        assert ns["C"]().m(_C__x=5) == 6

    def test_private_kwonly_param_with_leading_underscore_class(self) -> None:
        # leading underscores of the class name are stripped for mangling
        source = "class _P:\n    def m(self, *, __y=3):\n        return __y + 0\n"
        ns, _names = _exec_clean(source)
        assert ns["_P"]().m() == 3

    def test_nfkc_class_and_private_kwonly_param(self) -> None:
        # class U+FF23 compiles to 'C', __U+00B5 mangles to '_C__' + U+03BC
        source = "class \uff23:\n    def m(self, *, __\u00b5=1):\n        return __\u00b5 + 1\n"
        ns, _names = _exec_clean(source)
        assert ns["C"]().m() == 2
        compiled_key = "_C__\u03bc"
        assert ns["C"]().m(**{compiled_key: 5}) == 6

    def test_nfkc_kwonly_param_in_top_level_function(self) -> None:
        source = "def f(*, \u00b5=1):\n    return \u00b5 + 1\n"
        ns, _names = _exec_clean(source)
        assert ns["f"]() == 2

    def test_kelvin_sign_kwonly_param_in_top_level_function(self) -> None:
        # U+212A (KELVIN SIGN) is the second NFKC variant that compiles to 'K'
        source = "def f(*, \u212a=1):\n    return \u212a + 1\n"
        ns, _names = _exec_clean(source)
        assert ns["f"]() == 2

    def test_nfkc_kwonly_param_colliding_with_wrapper_args_local(self) -> None:
        # Separate tested step of M-040: '_\uff4dutmut_args' (fullwidth m)
        # compiles to '_mutmut_args'.  Without NFKC-aware used_names the
        # wrapper local shadows the parameter and forwards the empty args
        # list as the keyword value.
        source = "def f(*, _\uff4dutmut_args=7):\n    return _\uff4dutmut_args + 1\n"
        ns, _names = _exec_clean(source)
        assert ns["f"]() == 8
        assert ns["f"](_mutmut_args=9) == 10

    def test_dunder_suffix_kwonly_param_is_not_mangled(self) -> None:
        # guard: names ending in '__' are dunders and must stay untouched
        source = "class C:\n    def m(self, *, __x__=1):\n        return __x__ + 1\n"
        ns, _names = _exec_clean(source)
        assert ns["C"]().m() == 2
        assert ns["C"]().m(__x__=5) == 6

    def test_underscore_only_class_does_not_mangle(self) -> None:
        # guard: a class name consisting only of underscores never mangles
        source = "class _:\n    def m(self, *, __x=1):\n        return __x + 1\n"
        ns, _names = _exec_clean(source)
        assert ns["_"]().m() == 2
        assert ns["_"]().m(__x=5) == 6


def _kwdefaults_oracle_key(name: str, class_name: str | None) -> str:
    """Read the compiled kwonly key from CPython 3.14.7 itself (Q-52 oracle)."""
    if class_name is None:
        source = f"def m(self, *, {name}=0):\n    pass\n"
    else:
        source = f"class {class_name}:\n    def m(self, *, {name}=0):\n        pass\n"
    namespace: dict[str, Any] = {}
    # Literal snippets in a codegen oracle; exec'ing compiler output IS the
    # test purpose (same suppression rationale as _exec_clean).
    exec(compile(source, "<oracle>", "exec"), namespace)  # noqa: S102  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
    if class_name is None:
        method = namespace["m"]
    else:
        method = namespace[unicodedata.normalize("NFKC", class_name)].m
    kwdefaults = method.__kwdefaults__
    assert kwdefaults is not None
    return next(iter(kwdefaults))


# Identifier-shaped names incl. NFKC variants (µ, KELVIN SIGN, fullwidth
# letters) and optional dunder prefix/suffix so every mangling branch is hit.
_IDENTIFIER_STRATEGY = st.from_regex(
    r"_{0,2}[a-z\u00b5\u212a\uff41-\uff5a][a-z0-9]{0,5}(__)?",
    fullmatch=True,
)


_CLASS_NAME_STRATEGY = st.sampled_from([None, "C", "_C", "__C", "\uff23", "_", "__"])


class TestCompiledParameterNameOracle:
    @given(name=_IDENTIFIER_STRATEGY, class_name=_CLASS_NAME_STRATEGY)
    def test_compiled_parameter_name_matches_cpython_oracle(
        self, name: str, class_name: str | None
    ) -> None:
        normalized = unicodedata.normalize("NFKC", name)
        # Keywords and 'self' would make the oracle source invalid
        # (SyntaxError / duplicate argument), not the code under test.
        assume(not keyword.iskeyword(normalized))
        assume(normalized not in {"self", "m"})
        assert _compiled_parameter_name(name, class_name) == _kwdefaults_oracle_key(
            name, class_name
        )


class TestStarArgsMethods:
    def test_method_with_only_star_args_is_mutated_and_dispatches(self) -> None:
        # A1-MT-003/MW221-024: the complete ``*args`` tuple, including the
        # bound instance, is forwarded to both the original and each mutant.
        source = "class C:\n    def m(*args):\n        return (1 + 1, args[1:])\n"
        ns, names = _exec_clean(source)
        assert ns["C"]().m(5) == (2, (5,))
        method_mutants = [name for name in names if "ǁCǁm" in name]
        assert method_mutants
        try:
            os.environ["MUTANT_UNDER_TEST"] = "m." + method_mutants[0]
            assert ns["C"]().m(5) != (2, (5,))
        finally:
            os.environ.pop("MUTANT_UNDER_TEST", None)

    def test_method_with_self_and_star_args_still_mutated(self) -> None:
        source = "class C:\n    def m(self, *rest):\n        return (1 + 1, rest)\n"
        ns, names = _exec_clean(source)
        assert ns["C"]().m(5, 6) == (2, (5, 6))
        assert any("ǁCǁm" in n for n in names)


class TestAsyncGeneratorProtocol:
    def test_asend_values_reach_the_generator(self) -> None:
        # A1-MT-006: the ``async for`` wrapper swallowed asend() values.
        source = "async def agen():\n    x = yield 1 + 1\n    yield x\n"
        ns, _names = _exec_clean(source)

        async def drive() -> tuple[Any, Any]:
            ag = ns["agen"]()
            first = await ag.asend(None)
            second = await ag.asend(41)
            return first, second

        assert asyncio.run(drive()) == (2, 41)

    def test_athrow_reaches_generator_try_except(self) -> None:
        source = (
            "async def agen():\n"
            "    try:\n"
            "        yield 1 + 1\n"
            "    except ValueError:\n"
            "        yield 99\n"
        )
        ns, _names = _exec_clean(source)

        async def drive() -> tuple[Any, Any]:
            ag = ns["agen"]()
            first = await ag.asend(None)
            second = await ag.athrow(ValueError)
            return first, second

        assert asyncio.run(drive()) == (2, 99)

    def test_plain_async_function_still_awaitable(self) -> None:
        source = "async def f(x):\n    return x + 1\n"
        ns, _names = _exec_clean(source)
        assert asyncio.run(ns["f"](1)) == 2
