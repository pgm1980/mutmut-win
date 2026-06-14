"""This module contains the mutations for individual nodes, e.g. replacing a != b with a == b."""

import math
import re
from collections.abc import Callable, Iterable, Sequence
from typing import Any, cast

import libcst as cst
import libcst.matchers as m

from mutmut_win.constants import Profile

OPERATORS_TYPE = Sequence[
    tuple[
        type[cst.CSTNode],
        Callable[[Any], Iterable[cst.CSTNode]],
    ]
]

#: The registry row type: a (node_type, operator, profile) triple. The profile
#: tag is the LOWEST profile that includes the operator; the visitor never sees
#: it — ``operators_for_profile`` strips it back to ``OPERATORS_TYPE``.
TAGGED_OPERATORS_TYPE = Sequence[
    tuple[
        type[cst.CSTNode],
        Callable[[Any], Iterable[cst.CSTNode]],
        Profile,
    ]
]

# pattern to match (nearly) all chars in a string that are not part of an escape sequence
NON_ESCAPE_SEQUENCE = re.compile(r"((?<!\\)[^\\]+)")


def operator_number(
    node: cst.BaseNumber,
) -> Iterable[cst.BaseNumber]:
    """Mutate numeric literals by incrementing their value."""
    if isinstance(node, (cst.Integer, cst.Float)):
        new_value = node.evaluated_value + 1
        # 1e400 is a legal literal evaluating to inf, but repr(inf) is not a
        # valid float token — with_changes would raise CSTValidationError and
        # kill mutant generation for the whole file (issue #78 / A1-NM-007).
        if isinstance(new_value, float) and not math.isfinite(new_value):
            return
        yield node.with_changes(value=repr(new_value))
    elif isinstance(node, cst.Imaginary):
        new_imag = node.evaluated_value + 1j
        if not (math.isfinite(new_imag.real) and math.isfinite(new_imag.imag)):
            return
        yield node.with_changes(value=repr(new_imag))
    else:
        print("Unexpected number type", node)


def operator_string(
    node: cst.BaseString,
) -> Iterable[cst.BaseString]:
    """Mutate string literals: prepend/append XX, lowercase, uppercase.

    f-strings mutate their literal TEXT parts only (one mutant per part,
    XX-wrapped) — format specs and expressions live in
    ``FormattedStringExpression`` nodes and are provably untouched
    (issue #121 / external QA MUT-001: upstream 3.5.0 mutates only
    ``SimpleString``, leaving f-strings outside the mutation surface).
    """
    if isinstance(node, cst.FormattedString):
        for index, part in enumerate(node.parts):
            if isinstance(part, cst.FormattedStringText):
                new_parts = list(node.parts)
                new_parts[index] = part.with_changes(value=f"XX{part.value}XX")
                yield node.with_changes(parts=new_parts)
        return
    if isinstance(node, cst.SimpleString):
        value = node.value
        old_value = value
        prefix = value[: min([x for x in [value.find('"'), value.find("'")] if x != -1])]
        value = value[len(prefix) :]

        if value.startswith(('"""', "'''")):
            # We assume here that triple-quoted stuff are docs or other things
            # that mutation is meaningless for
            return

        supported_str_mutations: list[Callable[[str], str]] = [
            lambda x: "XX" + x + "XX",
            # do not modify escape sequences, as this could break python syntax
            lambda x: NON_ESCAPE_SEQUENCE.sub(lambda match: match.group(1).lower(), x),
            lambda x: NON_ESCAPE_SEQUENCE.sub(lambda match: match.group(1).upper(), x),
        ]

        for mut_func in supported_str_mutations:
            new_value = f"{prefix}{value[0]}{mut_func(value[1:-1])}{value[-1]}"
            if new_value == value:
                continue
            if new_value == old_value:
                continue
            yield node.with_changes(value=new_value)


def operator_lambda(
    node: cst.Lambda,
) -> Iterable[cst.Lambda]:
    """Mutate lambda body to None or 0."""
    if m.matches(node, m.Lambda(body=m.Name("None"))):
        yield node.with_changes(body=cst.Integer("0"))
    else:
        yield node.with_changes(body=cst.Name("None"))


def operator_dict_arguments(
    node: cst.Call,
) -> Iterable[cst.Call]:
    """Mutate dict(a=b, c=d) to dict(aXX=b, c=d) and dict(a=b, cXX=d)."""
    if not m.matches(node.func, m.Name(value="dict")):
        return

    existing_keywords = {arg.keyword.value for arg in node.args if arg.keyword}
    for i, arg in enumerate(node.args):
        if not arg.keyword:
            return
        keyword = arg.keyword
        if keyword.value + "XX" in existing_keywords:
            # dict(a=1, aXX=2): mutating ``a`` would duplicate the existing
            # ``aXX`` keyword — a SyntaxError mutant (issue #78 / A1-NM-009).
            continue
        mutated_keyword = keyword.with_changes(value=keyword.value + "XX")
        mutated_args = [
            *node.args[:i],
            node.args[i].with_changes(keyword=mutated_keyword),
            *node.args[i + 1 :],
        ]
        yield node.with_changes(args=mutated_args)


def operator_arg_removal(
    node: cst.Call,
) -> Iterable[cst.Call]:
    """Try to drop each arg in a function call, e.g. foo(a, b) -> foo(b), foo(a)."""
    for i, arg in enumerate(node.args):
        # replace with None
        if arg.star == "" and not m.matches(arg.value, m.Name("None")):
            mutated_arg = arg.with_changes(value=cst.Name("None"))
            yield node.with_changes(args=[*node.args[:i], mutated_arg, *node.args[i + 1 :]])

    if len(node.args) > 1:
        for i in range(len(node.args)):
            yield node.with_changes(args=[*node.args[:i], *node.args[i + 1 :]])


supported_symmetric_str_methods_swap = [
    ("lower", "upper"),
    ("upper", "lower"),
    ("lstrip", "rstrip"),
    ("rstrip", "lstrip"),
    ("find", "rfind"),
    ("rfind", "find"),
    ("ljust", "rjust"),
    ("rjust", "ljust"),
    ("index", "rindex"),
    ("rindex", "index"),
    ("removeprefix", "removesuffix"),
    ("removesuffix", "removeprefix"),
    ("partition", "rpartition"),
    ("rpartition", "partition"),
]

supported_unsymmetrical_str_methods_swap = [
    ("split", "rsplit"),
    ("rsplit", "split"),
]


def operator_symmetric_string_methods_swap(
    node: cst.Call,
) -> Iterable[cst.Call]:
    """Try to swap string method to opposite e.g. a.lower() -> a.upper()."""
    for old_call, new_call in supported_symmetric_str_methods_swap:
        if m.matches(node.func, m.Attribute(value=m.DoNotCare(), attr=m.Name(value=old_call))):
            func_name = cst.ensure_type(node.func, cst.Attribute).attr
            yield node.with_deep_changes(func_name, value=new_call)


def operator_unsymmetrical_string_methods_swap(
    node: cst.Call,
) -> Iterable[cst.Call]:
    """Try to handle specific mutations of string, useful only in specific args combination."""
    for old_call, new_call in supported_unsymmetrical_str_methods_swap:
        if m.matches(node.func, m.Attribute(attr=m.Name(value=old_call))) and old_call in {
            "split",
            "rsplit",
        }:
            # The logic of this "if" operator described here:
            # https://github.com/boxed/mutmut/pull/394#issuecomment-2977890188
            # sep or maxsplit or nothing
            key_args: set[str] = {a.keyword.value for a in node.args if a.keyword}
            if len(node.args) == 2 or "maxsplit" in key_args:
                func_name = cst.ensure_type(node.func, cst.Attribute).attr
                yield node.with_deep_changes(func_name, value=new_call)


#: Expression types that can safely replace their enclosing node bare: they
#: bind at least as tightly as a call and cannot carry hanging continuation
#: lines unless already parenthesized (then the lpar check applies anyway).
_ATOMIC_UNWRAP_TYPES: tuple[type[cst.BaseExpression], ...] = (
    cst.Name,
    cst.Integer,
    cst.Float,
    cst.Imaginary,
    cst.SimpleString,
    cst.ConcatenatedString,
    cst.FormattedString,
    cst.Call,
    cst.Attribute,
    cst.Subscript,
    cst.List,
    cst.Dict,
    cst.Set,
    cst.ListComp,
    cst.SetComp,
    cst.DictComp,
    cst.Tuple,
)


def _safe_unwrap(expression: cst.BaseExpression) -> cst.BaseExpression:
    """Make *expression* safe to stand alone where its enclosing node was.

    Operators of the "yield a sub-expression" family (collection/math
    neutralise, or-default, unary removal, conditional expression) replace a
    node by one of its children.  The child loses its parent's parentheses,
    which broke in three ways (issue #73, audit A1-NM-001…006, downstream
    BUG-1):

    - a sole-argument generator expression borrowed the call's parens —
      yielding it bare is a SyntaxError;
    - multi-line operands relied on the parent's parens to legalise their
      newlines — stranded continuation lines are a SyntaxError;
    - lower-precedence expressions rebind in the surrounding context
      (``list(a or b)[0]`` → ``a or b[0]``) — valid code, wrong mutant.

    All three are cured the same way: give the child its own parentheses.
    Atomic single-line expressions stay bare to keep mutant diffs minimal.
    """
    if getattr(expression, "lpar", None):
        return expression
    rendered_multiline = "\n" in cst.Module(body=[]).code_for_node(expression)
    if (
        isinstance(expression, cst.GeneratorExp)
        or not isinstance(expression, _ATOMIC_UNWRAP_TYPES)
        or rendered_multiline
    ):
        return expression.with_changes(lpar=[cst.LeftParen()], rpar=[cst.RightParen()])
    return expression


def operator_remove_unary_ops(
    node: cst.UnaryOperation,
) -> Iterable[cst.BaseExpression]:
    """Remove unary Not and BitInvert operators."""
    if isinstance(node.operator, (cst.Not, cst.BitInvert)):
        yield _safe_unwrap(node.expression)


_keyword_mapping: dict[type[cst.CSTNode], type[cst.CSTNode]] = {
    cst.Is: cst.IsNot,
    cst.IsNot: cst.Is,
    cst.In: cst.NotIn,
    cst.NotIn: cst.In,
    cst.Break: cst.Return,
    cst.Continue: cst.Break,
}


def operator_keywords(
    node: cst.CSTNode,
) -> Iterable[cst.CSTNode]:
    """Mutate keyword operators like is/is not, in/not in."""
    yield from _simple_mutation_mapping(node, _keyword_mapping)


def operator_name(node: cst.Name) -> Iterable[cst.CSTNode]:
    """Mutate well-known names like True/False."""
    name_mappings = {
        "True": "False",
        "False": "True",
        "deepcopy": "copy",
        # TODO: probably need to add a lot of things here... some builtins maybe, what more?
    }
    if node.value in name_mappings:
        yield node.with_changes(value=name_mappings[node.value])


_operator_mapping: dict[type[cst.CSTNode], type[cst.CSTNode]] = {
    cst.Plus: cst.Minus,
    cst.Add: cst.Subtract,
    cst.Minus: cst.Plus,
    cst.Subtract: cst.Add,
    cst.Multiply: cst.Divide,
    cst.Divide: cst.Multiply,
    cst.FloorDivide: cst.Divide,
    cst.Modulo: cst.Divide,
    cst.LeftShift: cst.RightShift,
    cst.RightShift: cst.LeftShift,
    cst.BitAnd: cst.BitOr,
    cst.BitOr: cst.BitAnd,
    cst.BitXor: cst.BitAnd,
    cst.Power: cst.Multiply,
    cst.AddAssign: cst.SubtractAssign,
    cst.SubtractAssign: cst.AddAssign,
    cst.MultiplyAssign: cst.DivideAssign,
    cst.DivideAssign: cst.MultiplyAssign,
    cst.FloorDivideAssign: cst.DivideAssign,
    cst.ModuloAssign: cst.DivideAssign,
    cst.LeftShiftAssign: cst.RightShiftAssign,
    cst.RightShiftAssign: cst.LeftShiftAssign,
    cst.BitAndAssign: cst.BitOrAssign,
    cst.BitOrAssign: cst.BitAndAssign,
    cst.BitXorAssign: cst.BitAndAssign,
    cst.PowerAssign: cst.MultiplyAssign,
    cst.LessThan: cst.LessThanEqual,
    cst.LessThanEqual: cst.LessThan,
    cst.GreaterThan: cst.GreaterThanEqual,
    cst.GreaterThanEqual: cst.GreaterThan,
    cst.Equal: cst.NotEqual,
    cst.NotEqual: cst.Equal,
    cst.And: cst.Or,
    cst.Or: cst.And,
}


def operator_swap_op(
    node: cst.CSTNode,
) -> Iterable[cst.CSTNode]:
    """Swap binary/unary/boolean/comparison operators with related alternatives."""
    if m.matches(
        node,
        m.BinaryOperation()
        | m.UnaryOperation()
        | m.BooleanOperation()
        | m.ComparisonTarget()
        | m.AugAssign(),
    ):
        typed_node = cast(
            "cst.BinaryOperation | cst.UnaryOperation | cst.BooleanOperation"
            " | cst.ComparisonTarget | cst.AugAssign",
            node,
        )
        operator = typed_node.operator
        for new_operator in _simple_mutation_mapping(operator, _operator_mapping):
            yield node.with_changes(operator=new_operator)


def operator_augmented_assignment(
    node: cst.AugAssign,
) -> Iterable[cst.Assign]:
    """Mutate all augmented assignments (+=, *=, |=, etc.) to normal = assignments."""
    yield cst.Assign([cst.AssignTarget(node.target)], node.value, node.semicolon)


def operator_assignment(
    node: cst.Assign | cst.AnnAssign,
) -> Iterable[cst.CSTNode]:
    """Mutate `a = b` to `a = None` and `a = None` to `a = ""`."""
    if not node.value:
        # do not mutate `a: sometype` to an assignment `a: sometype = ""`
        return
    if m.matches(node.value, m.Name("None")):
        mutated_value = cst.SimpleString('""')
    else:
        mutated_value = cst.Name("None")

    yield node.with_changes(value=mutated_value)


def operator_match(node: cst.Match) -> Iterable[cst.CSTNode]:
    """Drop the case statements in a match."""
    if len(node.cases) > 1:
        for i in range(len(node.cases)):
            yield node.with_changes(cases=[*node.cases[:i], *node.cases[i + 1 :]])


# ---------------------------------------------------------------------------
# Regex mutations (unique to mutmut-win — no other Python tool has this)
# ---------------------------------------------------------------------------

#: ``re`` module functions whose first argument is a regex pattern.
_RE_PATTERN_FUNCTIONS: set[str] = {
    "compile",
    "match",
    "search",
    "findall",
    "finditer",
    "sub",
    "split",
    "fullmatch",
    "subn",
}


def operator_regex(node: cst.Call) -> Iterable[cst.Call]:
    """Mutate regex patterns in ``re.*()`` calls.

    Recognises calls like ``re.compile(r"\\d+")``, ``re.match(r"^foo", text)``,
    etc. and mutates the pattern string (first argument).
    """
    from mutmut_win.regex_mutation import mutate_regex_pattern

    # Check: is this re.<func>(...)?
    if not isinstance(node.func, cst.Attribute):
        return
    if not isinstance(node.func.value, cst.Name) or node.func.value.value != "re":
        return
    if node.func.attr.value not in _RE_PATTERN_FUNCTIONS:
        return

    # The first positional argument should be a string literal (the pattern).
    if not node.args:
        return
    first_arg = node.args[0]
    if not isinstance(first_arg.value, cst.SimpleString):
        return

    # Extract the raw pattern string (strip quotes and r-prefix).
    raw = first_arg.value.value
    # Determine prefix (r, b, etc.) and quote style
    quote_char = raw[-1]  # ' or "
    prefix_end = raw.index(quote_char)
    prefix = raw[:prefix_end]
    # Skip f-strings and byte strings
    if "f" in prefix.lower() or "b" in prefix.lower():
        return
    inner = raw[prefix_end + 1 : -1]  # pattern without quotes

    mutations = mutate_regex_pattern(inner)
    for mutated_pattern in mutations:
        new_value = f"{prefix}{quote_char}{mutated_pattern}{quote_char}"
        new_string = first_arg.value.with_changes(value=new_value)
        new_arg = first_arg.with_changes(value=new_string)
        yield node.with_changes(args=[new_arg, *node.args[1:]])


# ---------------------------------------------------------------------------
# Math method mutations (inspired by Stryker.NET)
# ---------------------------------------------------------------------------

#: Pairwise swaps for math functions.
_MATH_SWAPS: dict[str, str] = {
    "ceil": "floor",
    "floor": "ceil",
    "min": "max",
    "max": "min",
}

#: Functions whose result is replaced by their first argument (neutralisation).
_MATH_NEUTRALIZE_TO_ARG: set[str] = {"abs", "round"}

#: Functions whose result is replaced by a constant.
_MATH_NEUTRALIZE_TO_ZERO: set[str] = {"sum"}


def _get_call_simple_name(node: cst.Call) -> str | None:
    """Extract the function name from a simple call like ``abs(x)`` or ``math.ceil(x)``."""
    if isinstance(node.func, cst.Name):
        return node.func.value
    if isinstance(node.func, cst.Attribute) and isinstance(node.func.value, cst.Name):
        return node.func.attr.value
    return None


def operator_math_methods(node: cst.Call) -> Iterable[cst.CSTNode]:
    """Mutate math functions: swap pairs and neutralise.

    - ``math.ceil(x)`` ↔ ``math.floor(x)``, ``min(a,b)`` ↔ ``max(a,b)``
    - ``abs(x)`` → ``x``, ``round(x)`` → ``x``
    - ``sum(iterable)`` → ``0``
    """
    func_name = _get_call_simple_name(node)
    if func_name is None:
        return

    # Pairwise swap (ceil↔floor, min↔max)
    if func_name in _MATH_SWAPS:
        new_name = _MATH_SWAPS[func_name]
        if isinstance(node.func, cst.Name):
            yield node.with_changes(func=cst.Name(new_name))
        elif isinstance(node.func, cst.Attribute):
            yield node.with_deep_changes(node.func.attr, value=new_name)

    # Neutralise to first argument (abs(x)→x, round(x)→x)
    if func_name in _MATH_NEUTRALIZE_TO_ARG and node.args:
        yield _safe_unwrap(node.args[0].value)

    # Neutralise to zero (sum(x)→0)
    if func_name in _MATH_NEUTRALIZE_TO_ZERO:
        yield cst.Integer("0")


# ---------------------------------------------------------------------------
# Return Value Replacement (inspired by cargo-mutants)
# ---------------------------------------------------------------------------


def operator_return_value(node: cst.Return) -> Iterable[cst.Return]:
    """Replace non-literal return values with ``None``.

    Skips bare ``return``, ``return None``, and literal values (numbers,
    strings, booleans) which are already mutated by other operators —
    EXCEPT f-strings: their expression parts are not covered by
    ``operator_string``, and skipping them made f-string-only functions
    vanish from the mutation surface entirely (issue #121 / external QA
    MUT-001: no trampoline, no mutants, invisible in every report).
    """
    if node.value is None:
        return  # bare return
    # Skip literals already covered by other operators
    if isinstance(node.value, (cst.BaseNumber, cst.BaseString)) and not isinstance(
        node.value, cst.FormattedString
    ):
        return
    if isinstance(node.value, cst.Name) and node.value.value in ("None", "True", "False"):
        return
    yield node.with_changes(value=cst.Name("None"))


# ---------------------------------------------------------------------------
# Conditional Expression mutation (inspired by Stryker.NET)
# ---------------------------------------------------------------------------


def operator_conditional_expression(node: cst.IfExp) -> Iterable[cst.BaseExpression]:
    """Simplify ``x if condition else y`` to just ``x`` or just ``y``.

    Tests whether both branches of a ternary expression are actually needed.
    """
    yield _safe_unwrap(node.body)  # always true-branch
    yield _safe_unwrap(node.orelse)  # always false-branch


# ---------------------------------------------------------------------------
# Statement Removal — void calls + raise → pass (inspired by Stryker.NET)
# ---------------------------------------------------------------------------

#: Function names whose calls should NOT be removed (too noisy as surviving mutants).
_EXCLUDED_VOID_CALLS: set[str] = {
    "print",
    "pprint",
    # logging methods
    "debug",
    "info",
    "warning",
    "error",
    "critical",
    "exception",
    "log",
    # typing runtime no-ops
    "assert_type",
    "reveal_type",
    # warnings
    "warn",
}


def operator_void_call_removal(
    node: cst.SimpleStatementLine,
) -> Iterable[cst.SimpleStatementLine]:
    """Remove void function calls by replacing the statement with ``pass``.

    Only targets single-expression statements where the expression is a
    ``Call`` whose return value is ignored (void / side-effect calls).
    Excludes logging, print, typing, and warnings calls.
    """
    if len(node.body) != 1 or not isinstance(node.body[0], cst.Expr):
        return
    expr = node.body[0]
    if not isinstance(expr.value, cst.Call):
        return

    # Get the leaf function name for the exclusion check.
    func_name = _get_call_simple_name(expr.value)
    if func_name and func_name in _EXCLUDED_VOID_CALLS:
        return

    yield node.with_changes(body=[cst.Pass()])


def operator_raise_removal(
    node: cst.SimpleStatementLine,
) -> Iterable[cst.SimpleStatementLine]:
    """Remove ``raise`` statements by replacing with ``pass``.

    Tests whether error/exception paths are actually covered by tests.
    """
    if len(node.body) != 1 or not isinstance(node.body[0], cst.Raise):
        return
    yield node.with_changes(body=[cst.Pass()])


# ---------------------------------------------------------------------------
# Collection method mutations (inspired by Stryker.NET LINQ mutator)
# ---------------------------------------------------------------------------

#: Builtin calls that can be neutralised to their first argument.
_COLLECTION_NEUTRALIZE: set[str] = {"sorted", "reversed", "list", "tuple", "frozenset", "set"}


def operator_collection_neutralize(node: cst.Call) -> Iterable[cst.CSTNode]:
    """Neutralise collection operations: ``sorted(x)`` → ``x``, etc.

    Tests whether sorting, reversing, or type conversion is actually needed.
    """
    func_name = _get_call_simple_name(node)
    if func_name not in _COLLECTION_NEUTRALIZE:
        return
    if not node.args:
        return
    yield _safe_unwrap(node.args[0].value)


def operator_comprehension_filter_removal(
    node: cst.ListComp,
) -> Iterable[cst.ListComp]:
    """Remove ``if`` filter clauses from list comprehensions.

    ``[x for x in items if pred(x)]`` → ``[x for x in items]``
    Tests whether the filter condition is actually needed.
    """
    for_in = node.for_in
    if not isinstance(for_in, cst.CompFor) or not for_in.ifs:
        return
    yield node.with_changes(for_in=for_in.with_changes(ifs=[]))


# ---------------------------------------------------------------------------
# or-Default mutation (inspired by Stryker.NET null-coalescing)
# ---------------------------------------------------------------------------


def operator_or_default(node: cst.BooleanOperation) -> Iterable[cst.BaseExpression]:
    """Simplify ``x or default`` to just ``x`` or just ``default``.

    Only applies to ``or`` operations (not ``and``).
    Tests whether the fallback value is actually needed.
    """
    if not isinstance(node.operator, cst.Or):
        return
    # Bug #68 / issue #73: multi-line operands used to be skipped entirely;
    # _safe_unwrap parenthesizes them instead, so the mutants exist AND parse.
    yield _safe_unwrap(node.left)  # remove fallback
    yield _safe_unwrap(node.right)  # always use fallback


# Operators that should be called on specific node types, each tagged with the
# LOWEST profile that includes it; operators_for_profile filters on this tag.
# The first 15 entries are mutmut's base operators at profile BASIC; the last 9
# are mutmut-win's extras at profile ADVANCED, marked by the origin comments
# higher up in this file. operator_assignment is registered twice, for Assign
# and AnnAssign, so the 15 base entries span 14 distinct functions. Aggressive
# ALL-tier operators arrive in a later phase of the operator roadmap.
mutation_operators: TAGGED_OPERATORS_TYPE = [
    # --- mutmut base operators (profile: basic) ---
    (cst.BaseNumber, operator_number, Profile.BASIC),
    (cst.BaseString, operator_string, Profile.BASIC),
    (cst.Name, operator_name, Profile.BASIC),
    (cst.Assign, operator_assignment, Profile.BASIC),
    (cst.AnnAssign, operator_assignment, Profile.BASIC),
    (cst.AugAssign, operator_augmented_assignment, Profile.BASIC),
    (cst.UnaryOperation, operator_remove_unary_ops, Profile.BASIC),
    (cst.Call, operator_dict_arguments, Profile.BASIC),
    (cst.Call, operator_arg_removal, Profile.BASIC),
    (cst.Call, operator_symmetric_string_methods_swap, Profile.BASIC),
    (cst.Call, operator_unsymmetrical_string_methods_swap, Profile.BASIC),
    (cst.Lambda, operator_lambda, Profile.BASIC),
    (cst.CSTNode, operator_keywords, Profile.BASIC),
    (cst.CSTNode, operator_swap_op, Profile.BASIC),
    (cst.Match, operator_match, Profile.BASIC),
    # --- mutmut-win extras (profile: advanced) ---
    (cst.Call, operator_regex, Profile.ADVANCED),
    (cst.Call, operator_math_methods, Profile.ADVANCED),
    (cst.Return, operator_return_value, Profile.ADVANCED),
    (cst.IfExp, operator_conditional_expression, Profile.ADVANCED),
    (cst.SimpleStatementLine, operator_void_call_removal, Profile.ADVANCED),
    (cst.SimpleStatementLine, operator_raise_removal, Profile.ADVANCED),
    (cst.Call, operator_collection_neutralize, Profile.ADVANCED),
    (cst.ListComp, operator_comprehension_filter_removal, Profile.ADVANCED),
    (cst.BooleanOperation, operator_or_default, Profile.ADVANCED),
]


def operators_for_profile(
    active: Profile,
) -> list[tuple[type[cst.CSTNode], Callable[[Any], Iterable[cst.CSTNode]]]]:
    """Return the ``(node_type, operator)`` pairs active under ``active``.

    An operator tagged with profile ``P`` is included iff ``P <= active``, so
    ``advanced`` includes every ``basic`` operator and ``all`` includes
    everything. The Profile tag is stripped from the result — callers (the
    ``MutationVisitor``) consume plain ``(node_type, operator)`` pairs.
    """
    return [
        (node_type, operator)
        for (node_type, operator, profile) in mutation_operators
        if profile <= active
    ]


def _simple_mutation_mapping(
    node: cst.CSTNode, mapping: dict[type[cst.CSTNode], type[cst.CSTNode]]
) -> Iterable[cst.CSTNode]:
    """Yield mutations from the node class mapping."""
    mutated_node_type = mapping.get(type(node))
    if mutated_node_type:
        yield mutated_node_type()


# TODO: detect regexes and mutate them in nasty ways? Maybe mutate all strings as regexes
