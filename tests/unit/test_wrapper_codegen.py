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
import os
from typing import Any

from mutmut_win.mutation import mutate_file_contents


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


class TestStarArgsMethods:
    def test_method_with_only_star_args_left_unmutated(self) -> None:
        # A1-MT-003: ``def m(*args)`` has no named first parameter the wrapper
        # could bind — such methods are left unmutated instead of broken.
        source = "class C:\n    def m(*args):\n        return (1 + 1, args[1:])\n"
        ns, names = _exec_clean(source)
        assert ns["C"]().m(5) == (2, (5,))
        assert not any("ǁCǁm" in n for n in names)

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
