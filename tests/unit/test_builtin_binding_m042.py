"""Regression tests for M-042 / BC-085 — len/isinstance builtin binding resolution.

Two original-card correction steps are pinned here with node-identity
evidence (a mutant counts only if ``id(mutation.original_node)`` IS the call
node or a member of the probed argument-subtree id set — never via totals or
``return None`` mutants, which the Return-statement operator produces
regardless):

Step 1 — binding resolution instead of spelling:
    a locally shadowed ``len``/``isinstance`` (parameter, module-level def) is
    an ordinary user function and mutates normally, while the QUALIFIED
    ``builtins.len(...)`` attribute call (and genuine import aliases) is
    protected exactly like the plain builtin.

Step 2 — narrowed argument subtree skip:
    for a REAL builtin call the call node and the function expression stay
    protected, but the argument logic is visited; the isinstance type
    expression is protected only under an unambiguous positional binding
    (second positional arg, no keyword, no star); any star argument keeps the
    conservative whole-argument skip.
"""

from __future__ import annotations

import libcst as cst

from mutmut_win.mutation import create_mutations

#: callee spellings the probe accepts (each case source has exactly one call)
_PROTECTED_CALLEES = frozenset({"len", "isinstance", "L", "B", "cast"})


class _IdCollector(cst.CSTVisitor):
    """Collect ``id()`` of every node in a subtree (including the root)."""

    def __init__(self, target: set[int]) -> None:
        super().__init__()
        self._target = target

    def on_visit(self, node: cst.CSTNode) -> bool:
        self._target.add(id(node))
        return True


class _ProtectedCallProbe(cst.CSTVisitor):
    """Find the first call of a protected-spelling callee and its subtree ids.

    Attributes:
        call: The probed ``cst.Call`` node, or ``None`` if no such call exists.
        func_ids: ids of every node in the callee expression subtree.
        arg_ids: one id set per argument, in call order.
    """

    def __init__(self) -> None:
        super().__init__()
        self.call: cst.Call | None = None
        self.func_ids: set[int] = set()
        self.arg_ids: list[set[int]] = []

    def on_visit(self, node: cst.CSTNode) -> bool:
        if self.call is None and isinstance(node, cst.Call):
            callee = None
            if isinstance(node.func, cst.Name):
                callee = node.func.value
            elif isinstance(node.func, cst.Attribute):
                callee = node.func.attr.value
            if callee in _PROTECTED_CALLEES:
                self.call = node
                node.func.visit(_IdCollector(self.func_ids))
                for arg in node.args:
                    ids: set[int] = set()
                    arg.visit(_IdCollector(ids))
                    self.arg_ids.append(ids)
                return False
        return True


def _mutations_for(source: str) -> tuple[cst.Module, list[cst.CSTNode]]:
    """Generate mutations for *source* and return the module plus originals.

    Args:
        source: Python source with exactly one len/isinstance-spelled call.

    Returns:
        The parsed module (the tree the mutations reference) and the list of
        ``Mutation.original_node`` nodes, so tests can assert node identity.
    """
    module, mutations = create_mutations(source)
    return module, [mutation.original_node for mutation in mutations]


def _probe(module: cst.Module) -> _ProtectedCallProbe:
    """Probe *module* for the protected call; asserts it was found."""
    probe = _ProtectedCallProbe()
    module.visit(probe)
    assert probe.call is not None, "probe lost the len/isinstance call — test source broken"
    return probe


# ---------------------------------------------------------------------------
# Step 1 — binding resolution (shadowed names mutate, qualified calls protect)
# ---------------------------------------------------------------------------


def test_shadowed_module_len_argument_is_mutated() -> None:
    """A module-level ``def len`` shadows the builtin: mutate normally."""
    module, originals = _mutations_for(
        "def len(x):\n    return 0\n\n\ndef f(a):\n    return len(a + 1)\n"
    )
    probe = _probe(module)
    binary = probe.call.args[0].value
    assert isinstance(binary, cst.BinaryOperation)
    assert any(original is binary for original in originals), (
        "No mutant has the shadowed len argument ``a + 1`` (BinaryOperation, "
        "node identity) as original node — a user function named len is still "
        "silenced by the old spelling check."
    )


def test_param_named_len_is_mutated_normally() -> None:
    """A parameter named ``len`` binds locally (LOCAL, not BUILTIN)."""
    module, originals = _mutations_for("def f(len, a):\n    return len(a + 1)\n")
    probe = _probe(module)
    binary = probe.call.args[0].value
    assert isinstance(binary, cst.BinaryOperation)
    assert any(original is binary for original in originals)


def test_shadowed_module_isinstance_is_mutated_normally() -> None:
    """A module-level ``def isinstance`` shadows the builtin for callers."""
    module, originals = _mutations_for(
        "def isinstance(obj, cls):\n    return True\n\n\n"
        "def f(a):\n    return isinstance(a + 1, int)\n"
    )
    probe = _probe(module)
    binary = probe.call.args[0].value
    assert isinstance(binary, cst.BinaryOperation)
    assert any(original is binary for original in originals)


def test_qualified_builtins_len_call_is_protected() -> None:
    """``builtins.len(...)`` (Attribute callee) is a real builtin call.

    Before M-042 the ``cst.Name``-only check let ``operator_arg_removal``
    mutate the call node itself (e.g. ``builtins.len(None)``).
    """
    module, originals = _mutations_for(
        "import builtins\n\n\ndef f(a):\n    return builtins.len(a)\n"
    )
    probe = _probe(module)
    assert not any(original is probe.call for original in originals), (
        "The qualified builtin call node itself must never be mutated."
    )
    assert not any(id(original) in probe.func_ids for original in originals), (
        "The ``builtins.len`` function expression must never be mutated."
    )


def test_aliased_import_len_call_is_protected_and_argument_mutated() -> None:
    """``from builtins import len as L`` resolves to builtins.len (IMPORT)."""
    module, originals = _mutations_for(
        "from builtins import len as L\n\n\ndef f(a):\n    return L(a + 1)\n"
    )
    probe = _probe(module)
    assert not any(original is probe.call for original in originals)
    binary = probe.call.args[0].value
    assert isinstance(binary, cst.BinaryOperation)
    assert any(original is binary for original in originals), (
        "The genuine builtin alias must protect the call, but its argument "
        "logic (``a + 1``) is ordinary mutable code."
    )


def test_aliased_builtins_module_isinstance_is_protected() -> None:
    """``import builtins as B; B.isinstance(...)`` resolves to the builtin."""
    module, originals = _mutations_for(
        "import builtins as B\n\n\ndef f(a):\n    return B.isinstance(a + 1, int)\n"
    )
    probe = _probe(module)
    assert not any(original is probe.call for original in originals)
    assert not any(id(original) in probe.func_ids for original in originals)
    # the FIRST argument stays mutable; the type argument is protected below
    first_arg_ids = probe.arg_ids[0]
    assert any(id(original) in first_arg_ids for original in originals)


# ---------------------------------------------------------------------------
# Step 2 — narrowed argument subtree skip for REAL builtin calls
# ---------------------------------------------------------------------------


def test_real_len_argument_logic_is_mutated() -> None:
    """Real ``len``: call protected, argument ``a + 1`` visited."""
    module, originals = _mutations_for("def f(a):\n    return len(a + 1)\n")
    probe = _probe(module)
    assert not any(original is probe.call for original in originals), (
        "The real builtin call node itself must stay unmutated."
    )
    binary = probe.call.args[0].value
    assert isinstance(binary, cst.BinaryOperation)
    assert any(original is binary for original in originals), (
        "No mutant inside the len argument (node identity) — the whole "
        "argument subtree is still discarded."
    )


def test_real_len_comprehension_filter_is_mutated() -> None:
    """Argument logic nested deep in a len argument is visited (node ids)."""
    source = "def f(items):\n    return len([i for i in items if i > 1])\n"
    module, originals = _mutations_for(source)
    probe = _probe(module)
    arg_ids = probe.arg_ids[0]
    assert any(id(original) in arg_ids for original in originals), (
        "No mutant node inside the len argument subtree (id-proven) — "
        "the comprehension filter ``i > 1`` was never visited."
    )


def test_real_isinstance_first_arg_mutated_type_arg_protected() -> None:
    """``isinstance(a + 1, int | None)``: value mutated, type union not."""
    module, originals = _mutations_for("def f(a):\n    return isinstance(a + 1, int | None)\n")
    probe = _probe(module)
    assert not any(original is probe.call for original in originals)
    first_arg, type_arg = probe.arg_ids
    assert any(id(original) in first_arg for original in originals), (
        "The isinstance value argument is ordinary mutable logic."
    )
    assert not any(id(original) in type_arg for original in originals), (
        "The isinstance type expression (``int | None``) is type-level code; "
        "mutating the union creates unkillable equivalents."
    )


def test_real_isinstance_type_arg_guard_green_before_fix() -> None:
    """Guard (green before the fix too): the plain call never got mutants."""
    module, originals = _mutations_for("def f(a):\n    return isinstance(a, int)\n")
    probe = _probe(module)
    assert not any(original is probe.call for original in originals)
    assert not any(id(original) in probe.arg_ids[1] for original in originals)


def test_isinstance_keyword_second_arg_binding_not_protected() -> None:
    """Keyword binding is not an unambiguous positional type argument.

    ``isinstance(a, typ=int | None)`` is a runtime TypeError anyway; per the
    M-042 decision the type-argument protection applies ONLY to an
    unambiguous positional second argument (no keyword, no star).
    """
    module, originals = _mutations_for("def f(a):\n    return isinstance(a, typ=int | None)\n")
    probe = _probe(module)
    assert not any(original is probe.call for original in originals)
    type_arg_ids = probe.arg_ids[1]
    assert any(id(original) in type_arg_ids for original in originals)


def test_star_arguments_keep_conservative_whole_argument_skip() -> None:
    """``isinstance(*pair)`` / ``len(*parts)``: keep the full argument skip."""
    for source in (
        "def f(pair):\n    return isinstance(*pair)\n",
        "def f(parts):\n    return len(*parts)\n",
    ):
        module, originals = _mutations_for(source)
        probe = _probe(module)
        assert not any(original is probe.call for original in originals)
        for index, ids in enumerate(probe.arg_ids):
            assert not any(id(original) in ids for original in originals), (
                f"Star-argument position {index} must keep the conservative "
                "whole-argument skip (positional binding unclear)."
            )


# ---------------------------------------------------------------------------
# Preserved contracts: function-name locks and typing.cast handling
# ---------------------------------------------------------------------------


def test_never_mutate_function_names_lock_preserved() -> None:
    """``__init_subclass__`` etc. stay unmutated wholesale (existing lock)."""
    source = "class C:\n    def __init_subclass__(cls, a):\n        return a + 1\n"
    _module, originals = _mutations_for(source)
    assert not originals, "NEVER_MUTATE_FUNCTION_NAMES subtree lock regressed"


def test_typing_cast_first_argument_lock_preserved() -> None:
    """``typing.cast`` first-argument skip (Bug #4) is untouched by M-042."""
    source = "from typing import cast\n\n\ndef f(obj):\n    return cast('Any', obj + 1)\n"
    module, originals = _mutations_for(source)
    probe = _probe(module)
    assert not any(id(original) in probe.arg_ids[0] for original in originals), (
        "typing.cast first-argument lock regressed"
    )
    second_arg = probe.call.args[1].value
    assert isinstance(second_arg, cst.BinaryOperation)
    assert any(original is second_arg for original in originals)
