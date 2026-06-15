"""This module contains code for managing mutant creation for whole files."""

import re
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import libcst as cst
import libcst.matchers as m
from libcst.metadata import MetadataWrapper, PositionProvider

from mutmut_win.constants import Profile
from mutmut_win.node_mutation import OPERATORS_TYPE, operators_for_profile
from mutmut_win.trampoline import create_trampoline_lookup, mangle_function_name, trampoline_impl

NEVER_MUTATE_FUNCTION_NAMES = {
    "__getattribute__",
    "__setattr__",
    "__new__",
    # Implicit classmethods: their first parameter is the CLASS, and
    # ``object.__getattribute__(cls, …)`` does not search a class's MRO —
    # the trampoline cannot dispatch them (issue #76 / A1-MT-001).
    "__init_subclass__",
    "__class_getitem__",
}
NEVER_MUTATE_FUNCTION_CALLS = {"len", "isinstance"}


def _is_static_only(function: cst.FunctionDef) -> bool:
    """True if ``function`` is decorated SOLELY with ``@staticmethod``.

    Such a method has no instance/class parameter, so the trampoline can
    dispatch it like a free function (mutmut-3.6.0 backport, W5). A method that
    also wears any other decorator (``@classmethod``, ``@property``,
    ``@app.route`` …) stays skipped — those execute at definition time or break
    the trampoline's self-dispatch. ``@classmethod`` is deliberately NOT included
    here: the class-bound original's ``__name__`` is read-only, which the
    trampoline-lookup codegen cannot set, so classmethods remain unmutated.
    """
    decorators = function.decorators
    return bool(decorators) and all(
        isinstance(d.decorator, cst.Name) and d.decorator.value == "staticmethod"
        for d in decorators
    )


@dataclass
class Mutation:
    original_node: cst.CSTNode
    mutated_node: cst.CSTNode
    contained_by_top_level_function: cst.FunctionDef | None


def mutate_file_contents(
    filename: str,  # noqa: ARG001 - kept for API compatibility with original mutmut
    code: str,
    covered_lines: set[int] | None = None,
    active_profile: Profile = Profile.ADVANCED,
    do_not_mutate_patterns: Sequence[str] = (),
) -> tuple[str, Sequence[str]]:
    """Create mutations for `code` and merge them to a single mutated file with trampolines.

    ``active_profile`` selects the operator set (default ``advanced`` = the
    historical behaviour); it is threaded straight through to create_mutations.
    ``do_not_mutate_patterns`` are regexes that exclude a function/class by name.

    :return: A tuple of (mutated code, list of mutant function names)"""
    module, mutations = create_mutations(
        code, covered_lines, active_profile, do_not_mutate_patterns
    )

    return combine_mutations_to_source(module, mutations)


def create_mutations(
    code: str,
    covered_lines: set[int] | None = None,
    active_profile: Profile = Profile.ADVANCED,
    do_not_mutate_patterns: Sequence[str] = (),
) -> tuple[cst.Module, list[Mutation]]:
    """Parse the code and create mutations.

    ``active_profile`` selects which operators run; it defaults to ``advanced``
    (mutmut-win's historical operator set) so existing callers are unaffected.
    The full profile value is threaded in from the config by the generation
    path (file_setup / orchestrator) in a later wave.
    """
    ignored_lines = pragma_no_mutate_lines(code)

    module = cst.parse_module(code)

    metadata_wrapper = MetadataWrapper(module)
    visitor = MutationVisitor(
        operators_for_profile(active_profile),
        ignored_lines,
        covered_lines,
        do_not_mutate_patterns,
    )
    module = metadata_wrapper.visit(visitor)

    return module, visitor.mutations


class OuterFunctionProvider(cst.BatchableMetadataProvider):
    """Link all nodes to the top-level function or method that contains them.

    For instance given this module:

    ```
    def foo():
        def bar():
            x = 1
    ```

    Then `self.get_metadata(OuterFunctionProvider, <x>)` returns `<foo>`.
    """

    def __init__(self) -> None:
        super().__init__()

    # N802: visit_Module follows the libcst visitor naming convention (CSTVisitor API)
    def visit_Module(self, node: cst.Module) -> bool:  # noqa: N802
        for child in node.body:
            if isinstance(child, cst.FunctionDef):
                # mark all nodes inside the function to belong to this function
                child.visit(OuterFunctionVisitor(self, child))
            elif isinstance(child, cst.ClassDef) and isinstance(child.body, cst.IndentedBlock):
                for method in child.body.body:
                    # mark all nodes inside the class method to belong to this method
                    # NOTE (issue #132 / 360°-B11): only TOP-LEVEL classes are
                    # walked — methods of a class nested inside another class
                    # get no metadata, so their mutations are dropped in
                    # group_by_top_level_node (same for funcs-in-funcs, which
                    # the trampoline covers via their containing function).
                    # Documented in README "Mutation-surface limits".
                    method.visit(OuterFunctionVisitor(self, method))

        # no need to recurse, we already visited all function and class method children
        return False


class OuterFunctionVisitor(cst.CSTVisitor):
    """Mark all nodes as children of `top_level_node`."""

    def __init__(self, provider: "OuterFunctionProvider", top_level_node: cst.CSTNode) -> None:
        self.provider = provider
        self.top_level_node = top_level_node
        super().__init__()

    def on_visit(self, node: cst.CSTNode) -> bool:
        self.provider.set_metadata(node, self.top_level_node)
        return True


class MutationVisitor(cst.CSTVisitor):
    """Iterate through all nodes in the module and create mutations for them.

    Ignore nodes at lines `ignore_lines` and several other cases
    (e.g. nodes within type annotations).

    The created mutations will be accessible at `self.mutations`."""

    METADATA_DEPENDENCIES = (PositionProvider, OuterFunctionProvider)

    def __init__(
        self,
        operators: OPERATORS_TYPE,
        ignore_lines: set[int],
        covered_lines: set[int] | None = None,
        do_not_mutate_patterns: Sequence[str] = (),
    ) -> None:
        self.mutations: list[Mutation] = []
        self._operators = operators
        self._ignored_lines = ignore_lines
        self._covered_lines = covered_lines
        # Compiled name-skip regexes (mutmut-3.6.0 do_not_mutate_patterns backport):
        # a FunctionDef/ClassDef whose name matches any of these is skipped wholesale.
        self._name_skip_patterns = [re.compile(p) for p in do_not_mutate_patterns]
        # Enclosing-class names (maintained by on_visit/on_leave) so the
        # do_not_mutate_patterns can match a QUALIFIED ``Class.method`` name.
        self._class_stack: list[str] = []
        # ids() of CST nodes whose entire subtree must NOT be mutated.
        # Populated lazily when we hit a special-cased call like ``typing.cast(...)``
        # whose first argument is a pure type annotation (see Bug #4).
        self._skip_subtree_ids: set[int] = set()

    def on_visit(self, node: cst.CSTNode) -> bool:
        if id(node) in self._skip_subtree_ids:
            return False
        if self._skip_node_and_children(node):
            return False

        # If this is a typing.cast(...) call, mark its first argument's entire
        # subtree as no-mutate. The first argument is a pure type annotation
        # (``cast`` is the identity function at runtime) and mutations there
        # are observable-equivalent — see Bug #4.
        if isinstance(node, cst.Call) and _is_cast_call(node) and node.args:
            node.args[0].value.visit(_SubtreeIdCollector(self._skip_subtree_ids))

        if self._should_mutate_node(node):
            self._create_mutations(node)

        # Track the enclosing class so do_not_mutate_patterns can match a
        # qualified ``Class.method`` name (on_leave pops it). Pushed only after
        # the skip checks above — a skipped class returns early, never pushed.
        if isinstance(node, cst.ClassDef):
            self._class_stack.append(node.name.value)
        # continue to mutate children
        return True

    def on_leave(self, original_node: cst.CSTNode) -> None:
        """Pop the enclosing-class stack when leaving a ``ClassDef``.

        Balanced with the push in :meth:`on_visit`: libcst calls ``on_leave``
        exactly for the nodes whose ``on_visit`` returned True, so a skipped
        (never-pushed) class is never popped here.
        """
        if isinstance(original_node, cst.ClassDef) and self._class_stack:
            self._class_stack.pop()

    def _create_mutations(self, node: cst.CSTNode) -> None:
        is_cast = isinstance(node, cst.Call) and _is_cast_call(node)
        original_first_arg: cst.Arg | None = None
        if is_cast:
            # mypy: the is_cast guard already proves node is a cst.Call
            assert isinstance(node, cst.Call)  # noqa: S101 - narrow-only assert
            original_first_arg = node.args[0] if node.args else None
        for t, operator in self._operators:
            if isinstance(node, t):
                for mutated_node in operator(node):
                    # Bug #4: drop any mutation of a typing.cast(...) call that would
                    # change the first argument — it has no runtime effect and the
                    # resulting mutants are unkillable equivalents.
                    if (
                        is_cast
                        and original_first_arg is not None
                        and isinstance(mutated_node, cst.Call)
                        and (
                            not mutated_node.args or mutated_node.args[0] is not original_first_arg
                        )
                    ):
                        continue
                    mutation = Mutation(
                        original_node=node,
                        mutated_node=mutated_node,
                        # type: ignore[arg-type] - libcst metadata API returns Any
                        contained_by_top_level_function=self.get_metadata(  # type: ignore[arg-type]
                            OuterFunctionProvider, node, None
                        ),
                    )
                    self.mutations.append(mutation)

    def _should_mutate_node(self, node: cst.CSTNode) -> bool:
        # currently, the position metadata does not always exist
        # (see https://github.com/Instagram/LibCST/issues/1322)
        position = self.get_metadata(PositionProvider, node, None)
        if position:
            # do not mutate nodes with a pragma: no mutate comment
            if position.start.line in self._ignored_lines:
                return False

            # do not mutate nodes that are not covered
            if self._covered_lines is not None and position.start.line not in self._covered_lines:
                return False

        return True

    def _skip_node_and_children(self, node: cst.CSTNode) -> bool:
        is_never_mutate_call = (
            isinstance(node, cst.Call)
            and isinstance(node.func, cst.Name)
            and node.func.value in NEVER_MUTATE_FUNCTION_CALLS
        )
        is_never_mutate_func = (
            isinstance(node, cst.FunctionDef) and node.name.value in NEVER_MUTATE_FUNCTION_NAMES
        )
        if is_never_mutate_call or is_never_mutate_func:
            return True

        # do_not_mutate_patterns (mutmut-3.6.0 backport): skip a function/class
        # whose SIMPLE or QUALIFIED name (``Class.method``, via the class stack)
        # matches any configured regex, pruning its whole subtree. Qualified
        # matching lets a pattern target one class's method (external QA: the
        # matcher used to be name-only).
        if self._name_skip_patterns and isinstance(node, (cst.FunctionDef, cst.ClassDef)):
            simple = node.name.value
            qualified = ".".join([*self._class_stack, simple])
            if any(
                pattern.search(simple) or pattern.search(qualified)
                for pattern in self._name_skip_patterns
            ):
                return True

        # ignore everything inside of type annotations
        if isinstance(node, cst.Annotation):
            return True

        # Default parameter values are evaluated at function-definition time.
        # Two reasons to skip mutations inside them:
        # 1) Complex defaults (e.g. ``def foo(x=abs(-1)): ...``) that mutate to
        #    ``def foo(x=abs(None)): ...`` raise at definition time and break the
        #    whole import.
        # 2) Even simple defaults (``Name``, ``BaseNumber``, ``BaseString``) cannot
        #    be killed: mutmut's trampoline architecture captures the *mutated*
        #    default at import time of the mutant variant, but every caller still
        #    goes through the original symbol's default — so the mutation is
        #    structurally unobservable through behavioural tests (Bug #70).
        # The union of both reasons is "any ``cst.Param`` with a default" — skip
        # the whole subtree.
        if isinstance(node, cst.Param) and node.default is not None:
            return True

        # ignore decorated functions, because
        # 1) copying them for the trampoline setup can cause side effects
        #    (e.g. multiple @app.post("/foo") definitions)
        # 2) decorators are executed when the function is defined, so we don't want
        #    to mutate their arguments and cause exceptions
        # 3) @property decorators break the trampoline signature assignment
        #    (which expects it to be a function)
        # EXCEPTION (W5 / mutmut-3.6.0 backport): a method decorated SOLELY with
        # @staticmethod IS mutated — create_trampoline_wrapper dispatches it like
        # a free function (no instance/class arg). Other decorators stay skipped.
        if isinstance(node, cst.FunctionDef) and _is_static_only(node):
            return False
        return bool(isinstance(node, (cst.FunctionDef, cst.ClassDef)) and len(node.decorators))


def _is_cast_call(node: cst.Call) -> bool:
    """Return True if ``node`` is a call to ``typing.cast`` or unqualified ``cast``.

    The first argument of :func:`typing.cast` is a *type annotation* — at runtime
    ``cast`` is the identity function and returns the second argument unchanged.
    Mutating the first argument therefore can never change observable behaviour,
    which makes such mutants unkillable (see Bug #4 in critique-model-service's
    ``_misc/mutmut-win-bugs.md``).
    """
    func = node.func
    if isinstance(func, cst.Name) and func.value == "cast":
        return True
    return (
        isinstance(func, cst.Attribute)
        and isinstance(func.value, cst.Name)
        and func.value.value == "typing"
        and func.attr.value == "cast"
    )


class _SubtreeIdCollector(cst.CSTVisitor):
    """Collect ``id()`` of every node in a CST subtree (including the root)."""

    def __init__(self, target: set[int]) -> None:
        super().__init__()
        self._target = target

    def on_visit(self, node: cst.CSTNode) -> bool:
        self._target.add(id(node))
        return True


MODULE_STATEMENT = cst.SimpleStatementLine | cst.BaseCompoundStatement

# convert str trampoline implementations to CST nodes with some whitespace
trampoline_impl_cst = list(cst.parse_module(trampoline_impl).body)
trampoline_impl_cst[-1] = trampoline_impl_cst[-1].with_changes(
    leading_lines=[cst.EmptyLine(), cst.EmptyLine()]
)


def _warn_unmanglable_function(qualified_name: str, exc: ValueError) -> None:
    """Warn that one function stays unmutated due to the mangling limitation.

    The wording names the ENGINE limitation — the source is valid Python
    (U+01C1 is a legal identifier character); calling it "Unsupported
    syntax" sent users hunting for a syntax error that does not exist
    (issue #121 / external QA MUT-002).
    """
    warnings.warn(
        f"cannot mutate function '{qualified_name}': its name collides with "
        f"the internal mangling separator (U+01C1) — function left unmutated "
        f"({exc})",
        SyntaxWarning,
        stacklevel=3,
    )


def combine_mutations_to_source(
    module: cst.Module, mutations: Sequence[Mutation]
) -> tuple[str, Sequence[str]]:
    """Create mutated functions and trampolines for all mutations and compile them.

    :param module: The original parsed module
    :param mutations: Mutations that should be applied.
    :return: Mutated code and list of mutation names"""

    # copy start of the module (in particular __future__ imports)
    result: list[MODULE_STATEMENT] = get_statements_until_func_or_class(module.body)
    mutation_names: list[str] = []

    # statements we still need to potentially mutate and add to the result
    remaining_statements = module.body[len(result) :]

    # trampoline functions
    result.extend(trampoline_impl_cst)

    mutations_within_function = group_by_top_level_node(mutations)

    # We now iterate through all top-level nodes.
    # If they are a function or class method, we mutate and add trampolines.
    # Else we keep the original node without modifications.
    for statement in remaining_statements:
        if isinstance(statement, cst.FunctionDef):
            func = statement
            func_mutants = mutations_within_function.get(func)
            if not func_mutants:
                result.append(func)
                continue
            try:
                nodes, lookup_nodes, mutant_names = function_trampoline_arrangement(
                    func, func_mutants, class_name=None
                )
            except ValueError as exc:
                # Issue #121 / external QA MUT-002: an unmanglable identifier
                # (U+01C1 collides with the internal mangling separator) used
                # to drop the WHOLE file as "Unsupported syntax" — the skip is
                # function-granular now and names the engine limitation.
                _warn_unmanglable_function(func.name.value, exc)
                result.append(func)
                continue
            result.extend(nodes)
            result.extend(lookup_nodes)
            mutation_names.extend(mutant_names)
        elif isinstance(statement, cst.ClassDef):
            cls = statement
            if not isinstance(cls.body, cst.IndentedBlock):
                # we don't mutate single-line classes, e.g. `class A: a = 1; b = 2`
                result.append(cls)
            else:
                mutated_body = []
                # Lookup dicts go AFTER the class at module level (issue #77).
                class_lookup_nodes: list[MODULE_STATEMENT] = []
                for method in cls.body.body:
                    method_mutants = mutations_within_function.get(method)
                    if not isinstance(method, cst.FunctionDef) or not method_mutants:
                        mutated_body.append(method)
                        continue
                    if not (method.params.posonly_params or method.params.params):
                        # ``def m(*args)``-style methods have no named first
                        # parameter the wrapper could bind the instance to —
                        # leave them unmutated (issue #76 / A1-MT-001/003).
                        mutated_body.append(method)
                        continue
                    try:
                        nodes, lookup_nodes, mutant_names = function_trampoline_arrangement(
                            method, method_mutants, class_name=cls.name.value
                        )
                    except ValueError as exc:
                        # Same function-granular skip for methods/classes
                        # whose names collide with the mangling separator
                        # (issue #121 / MUT-002).
                        _warn_unmanglable_function(f"{cls.name.value}.{method.name.value}", exc)
                        mutated_body.append(method)
                        continue
                    mutated_body.extend(nodes)
                    class_lookup_nodes.extend(lookup_nodes)
                    mutation_names.extend(mutant_names)

                result.append(cls.with_changes(body=cls.body.with_changes(body=mutated_body)))
                result.extend(class_lookup_nodes)
        else:
            result.append(statement)

    mutated_module = module.with_changes(body=result)
    return mutated_module.code, mutation_names


def function_trampoline_arrangement(
    function: cst.FunctionDef,
    mutants: Iterable[Mutation],
    class_name: str | None,
) -> tuple[Sequence[MODULE_STATEMENT], Sequence[MODULE_STATEMENT], Sequence[str]]:
    """Create mutated functions and a trampoline that switches between versions.

    The lookup statements (mutants dict + ``__name__`` assignment) are
    returned separately: they must be emitted at MODULE level — for methods
    AFTER the class definition — because a dict in a class body becomes an
    ``enum.Enum`` member and its annotation broke ``NamedTuple`` (issue #77).

    :return: A tuple of (nodes for the original scope, module-level lookup
        nodes, mutant names)"""
    nodes: list[MODULE_STATEMENT] = []
    mutant_names: list[str] = []

    name = function.name.value
    mangled_name = mangle_function_name(name=name, class_name=class_name) + "__mutmut"

    # trampoline with same signature, that forwards the calls to the activated mutant/original
    # (put first, s.t. it stays next to @overload definitions of this function. mypy needs this)
    nodes.append(create_trampoline_wrapper(function, mangled_name, class_name))

    # copy of original function
    nodes.append(function.with_changes(name=cst.Name(mangled_name + "_orig")))

    # mutated versions of the function
    for i, mutant in enumerate(mutants):
        mutant_name = f"{mangled_name}_{i + 1}"
        mutant_names.append(mutant_name)
        mutated_method = function.with_changes(name=cst.Name(mutant_name))
        mutated_method = deep_replace(mutated_method, mutant.original_node, mutant.mutated_node)
        nodes.append(mutated_method)  # type: ignore[arg-type]

    lookup_nodes = list(
        cst.parse_module(
            create_trampoline_lookup(orig_name=name, mutants=mutant_names, class_name=class_name)
        ).body
    )
    lookup_nodes[0] = lookup_nodes[0].with_changes(leading_lines=[cst.EmptyLine()])

    return nodes, lookup_nodes, mutant_names


def create_trampoline_wrapper(
    function: cst.FunctionDef, mangled_name: str, class_name: str | None
) -> cst.FunctionDef:
    """Create a trampoline wrapper function that dispatches to original or mutant.

    Codegen safety (issue #76): the instance/class argument is referenced by
    its REAL first-parameter name (``cls`` for ``__init_subclass__``,
    ``this``, … — the old hardcoded ``self`` raised NameError in the clean
    run, A1-MT-001); wrapper locals are prefixed so user parameters named
    ``args``/``kwargs`` cannot collide (A1-MT-002); ``*args`` is forwarded
    intact (A1-MT-003); async generators get a plain ``def`` wrapper that
    returns the generator object untouched so ``asend``/``athrow`` keep
    working (A1-MT-006).  Callers guarantee that methods have a named first
    parameter (others are left unmutated).
    """
    named_params = [*function.params.posonly_params, *function.params.params]
    # A @staticmethod has no instance/class parameter, so it is dispatched like a
    # free function: every parameter is forwarded and no self_arg is passed (W5).
    is_static = class_name is not None and _is_static_only(function)
    instance_bound = class_name is not None and not is_static
    self_name = named_params[0].name.value if instance_bound else None

    forwarded_params = named_params[1:] if instance_bound else named_params
    args: list[cst.Element | cst.StarredElement] = [cst.Element(p.name) for p in forwarded_params]
    if isinstance(function.params.star_arg, cst.Param):
        args.append(cst.StarredElement(function.params.star_arg.name))

    args_assignemnt = cst.Assign([cst.AssignTarget(cst.Name(value="_mutmut_args"))], cst.List(args))

    kwargs: list[cst.DictElement | cst.StarredDictElement] = [
        cst.DictElement(cst.SimpleString(f"'{p.name.value}'"), p.name)
        for p in function.params.kwonly_params
    ]
    if isinstance(function.params.star_kwarg, cst.Param):
        kwargs.append(cst.StarredDictElement(function.params.star_kwarg.name))

    kwargs_assignment = cst.Assign(
        [cst.AssignTarget(cst.Name(value="_mutmut_kwargs"))], cst.Dict(kwargs)
    )

    def _get_local_name(func_name: str) -> cst.BaseExpression:
        # for top level, simply return the name
        if class_name is None:
            return cst.Name(func_name)
        # a @staticmethod has no instance to dispatch through — resolve the
        # original via the class object (a module global at call time).
        if is_static:
            return cst.Attribute(cst.Name(class_name), cst.Name(func_name))
        # for class methods, use object.__getattribute__(<first param>, name)
        return cst.Call(
            func=cst.Attribute(cst.Name("object"), cst.Name("__getattribute__")),
            args=[
                cst.Arg(cst.Name(cast("str", self_name))),
                cst.Arg(cst.SimpleString(f"'{func_name}'")),
            ],
        )

    result: cst.BaseExpression = cst.Call(
        func=cst.Name("_mutmut_trampoline"),
        args=[
            cst.Arg(_get_local_name(f"{mangled_name}_orig")),
            # The mutants dict lives at module level (issue #77), so it is
            # resolved as a global name even from inside a method body.
            cst.Arg(cst.Name(f"{mangled_name}_mutants")),
            cst.Arg(cst.Name("_mutmut_args")),
            cst.Arg(cst.Name("_mutmut_kwargs")),
            cst.Arg(cst.Name("None" if self_name is None else self_name)),
        ],
    )
    # For sync functions (and async generators, see below) simply return the
    # value or generator object.
    result_statement: cst.BaseStatement = cst.SimpleStatementLine([cst.Return(result)])

    async_generator = bool(function.asynchronous) and _is_generator(function)
    if function.asynchronous and not async_generator:
        result_statement = cst.SimpleStatementLine([cst.Return(cst.Await(result))])

    type_ignore_whitespace = cst.TrailingWhitespace(comment=cst.Comment("# type: ignore"))

    wrapper_changes: dict[str, object] = {
        "body": cst.IndentedBlock(
            [
                cst.SimpleStatementLine(
                    [args_assignemnt], trailing_whitespace=type_ignore_whitespace
                ),
                cst.SimpleStatementLine(
                    [kwargs_assignment], trailing_whitespace=type_ignore_whitespace
                ),
                result_statement,
            ],
        ),
    }
    if async_generator:
        # A sync wrapper returning the async-generator object preserves the
        # full protocol; re-yielding via ``async for`` swallowed ``asend()``
        # values and bypassed ``athrow()`` (issue #76 / A1-MT-006).
        wrapper_changes["asynchronous"] = None

    return function.with_changes(**wrapper_changes)


def get_statements_until_func_or_class(
    statements: Sequence[MODULE_STATEMENT],
) -> list[MODULE_STATEMENT]:
    """Get all statements until we encounter the first function or class definition."""
    result = []

    for stmt in statements:
        if m.matches(stmt, m.FunctionDef() | m.ClassDef()):
            return result
        result.append(stmt)

    return result


def group_by_top_level_node(
    mutations: Sequence[Mutation],
) -> Mapping[cst.CSTNode, Sequence[Mutation]]:
    """Group mutations by the top-level function or class that contains them."""
    grouped: dict[cst.CSTNode, list[Mutation]] = defaultdict(list)
    for mut in mutations:
        if mut.contained_by_top_level_function:
            grouped[mut.contained_by_top_level_function].append(mut)

    return grouped


def _indent_width(line: str) -> int:
    """Leading-whitespace width of a line (tabs count as one char)."""
    return len(line) - len(line.lstrip())


def _pragma_no_mutate_suffix(line: str) -> str | None:
    """Directive word after a ``# pragma: no mutate`` marker on ``line``.

    ``None`` if the line carries no such marker; otherwise ``""`` (plain),
    ``"start"``, ``"end"`` or ``"block"`` — the first word after ``no mutate``
    (an unknown word degrades to ``""`` / plain, preserving the original
    single-line behaviour).
    """
    if "# pragma:" not in line:
        return None
    after_pragma = line.partition("# pragma:")[-1]
    if "no mutate" not in after_pragma:
        return None
    tail = after_pragma.partition("no mutate")[-1].split()
    if not tail:
        return ""
    word = tail[0].lower()
    return word if word in {"start", "end", "block"} else ""


def _pragma_block_range(lines: list[str], pragma_index: int) -> range:
    """1-based line range covered by a ``block`` pragma at ``lines[pragma_index]``.

    The pragma line plus the suite below it: every following line indented
    deeper than the pragma line, through the last such non-blank line. A
    dedented continuation line of a multi-line string would end the block
    early, but triple-quoted strings are never mutated anyway (documented
    limitation of the text-based scan).
    """
    base = _indent_width(lines[pragma_index])
    last_body = pragma_index
    cursor = pragma_index + 1
    while cursor < len(lines):
        if lines[cursor].strip() == "":
            cursor += 1
            continue
        if _indent_width(lines[cursor]) <= base:
            break
        last_body = cursor
        cursor += 1
    return range(pragma_index + 1, last_body + 2)


def pragma_no_mutate_lines(source: str) -> set[int]:
    """Return line numbers (1-based) excluded by ``# pragma: no mutate`` comments.

    Recognises four forms (mutmut-3.6.0 surface backport):

    - ``# pragma: no mutate`` — the comment's own line (the original behaviour).
    - ``# pragma: no mutate block`` — that line plus the indented suite below it.
    - ``# pragma: no mutate start`` … ``# pragma: no mutate end`` — the inclusive
      range between the two markers; a dangling ``start`` skips to end-of-file.
    """
    lines = source.split("\n")
    ignored: set[int] = set()
    open_start: int | None = None
    for index, line in enumerate(lines):
        suffix = _pragma_no_mutate_suffix(line)
        if suffix is None:
            continue
        lineno = index + 1
        if suffix == "start":
            if open_start is None:
                open_start = lineno
        elif suffix == "end":
            start = open_start if open_start is not None else lineno
            ignored.update(range(start, lineno + 1))
            open_start = None
        elif suffix == "block":
            ignored.update(_pragma_block_range(lines, index))
        else:
            ignored.add(lineno)
    if open_start is not None:
        ignored.update(range(open_start, len(lines) + 1))
    return ignored


def deep_replace(tree: cst.CSTNode, old_node: cst.CSTNode, new_node: cst.CSTNode) -> cst.CSTNode:
    """Like the CSTNode.deep_replace method, but only replaces up to one occurrence."""
    return tree.visit(ChildReplacementTransformer(old_node, new_node))  # type: ignore[return-value]


class ChildReplacementTransformer(cst.CSTTransformer):
    """Replace the first occurrence of old_node with new_node in the tree."""

    def __init__(self, old_node: cst.CSTNode, new_node: cst.CSTNode) -> None:
        self.old_node = old_node
        self.new_node = new_node
        self.replaced_node = False

    def on_visit(self, node: cst.CSTNode) -> bool:
        # If the node is one we are about to replace, we shouldn't
        # recurse down it, that would be a waste of time.
        # Also, we stop recursion when we already replaced the node.
        return not (self.replaced_node or node is self.old_node)

    def on_leave(self, original_node: cst.CSTNode, updated_node: cst.CSTNode) -> cst.CSTNode:
        if original_node is self.old_node:
            self.replaced_node = True
            return self.new_node
        return updated_node


def _is_generator(function: cst.FunctionDef) -> bool:
    """Return True if the function has yield statement(s)."""
    visitor = IsGeneratorVisitor(function)
    function.visit(visitor)
    return visitor.is_generator


class IsGeneratorVisitor(cst.CSTVisitor):
    """Check if a function is a generator.

    We do so by checking if any child is a Yield statement, but not looking into
    inner function definitions."""

    def __init__(self, original_function: cst.FunctionDef) -> None:
        self.is_generator = False
        self.original_function: cst.FunctionDef = original_function

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool | None:  # noqa: N802
        # do not recurse into inner function definitions
        if self.original_function != node:
            return False
        return None

    # ARG002: libcst CSTVisitor requires the node parameter in visitor methods
    def visit_Yield(self, node: cst.Yield) -> bool | None:  # noqa: N802, ARG002
        self.is_generator = True
        return False
