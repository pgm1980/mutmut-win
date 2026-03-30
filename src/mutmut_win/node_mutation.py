"""This module contains the mutations for individual nodes, e.g. replacing a != b with a == b."""

import re
from collections.abc import Callable, Iterable, Sequence
from typing import Any, cast

import libcst as cst
import libcst.matchers as m

OPERATORS_TYPE = Sequence[
    tuple[
        type[cst.CSTNode],
        Callable[[Any], Iterable[cst.CSTNode]],
    ]
]

# pattern to match (nearly) all chars in a string that are not part of an escape sequence
NON_ESCAPE_SEQUENCE = re.compile(r"((?<!\\)[^\\]+)")


def operator_number(
    node: cst.BaseNumber,
) -> Iterable[cst.BaseNumber]:
    """Mutate numeric literals by incrementing their value."""
    if isinstance(node, (cst.Integer, cst.Float)):
        yield node.with_changes(value=repr(node.evaluated_value + 1))
    elif isinstance(node, cst.Imaginary):
        yield node.with_changes(value=repr(node.evaluated_value + 1j))
    else:
        print("Unexpected number type", node)


def operator_string(
    node: cst.BaseString,
) -> Iterable[cst.BaseString]:
    """Mutate string literals: prepend/append XX, lowercase, uppercase."""
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

    for i, arg in enumerate(node.args):
        if not arg.keyword:
            return
        keyword = arg.keyword
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


def operator_remove_unary_ops(
    node: cst.UnaryOperation,
) -> Iterable[cst.BaseExpression]:
    """Remove unary Not and BitInvert operators."""
    if isinstance(node.operator, (cst.Not, cst.BitInvert)):
        yield node.expression


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


# Operators that should be called on specific node types
mutation_operators: OPERATORS_TYPE = [
    (cst.BaseNumber, operator_number),
    (cst.BaseString, operator_string),
    (cst.Name, operator_name),
    (cst.Assign, operator_assignment),
    (cst.AnnAssign, operator_assignment),
    (cst.AugAssign, operator_augmented_assignment),
    (cst.UnaryOperation, operator_remove_unary_ops),
    (cst.Call, operator_dict_arguments),
    (cst.Call, operator_arg_removal),
    (cst.Call, operator_symmetric_string_methods_swap),
    (cst.Call, operator_unsymmetrical_string_methods_swap),
    (cst.Lambda, operator_lambda),
    (cst.CSTNode, operator_keywords),
    (cst.CSTNode, operator_swap_op),
    (cst.Match, operator_match),
    (cst.Call, operator_regex),
]


def _simple_mutation_mapping(
    node: cst.CSTNode, mapping: dict[type[cst.CSTNode], type[cst.CSTNode]]
) -> Iterable[cst.CSTNode]:
    """Yield mutations from the node class mapping."""
    mutated_node_type = mapping.get(type(node))
    if mutated_node_type:
        yield mutated_node_type()


# TODO: detect regexes and mutate them in nasty ways? Maybe mutate all strings as regexes
