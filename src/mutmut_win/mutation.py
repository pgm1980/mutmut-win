"""This module contains code for managing mutant creation for whole files."""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import libcst as cst
import libcst.matchers as m
from libcst.metadata import MetadataWrapper, PositionProvider

from mutmut_win.node_mutation import OPERATORS_TYPE, mutation_operators
from mutmut_win.trampoline import create_trampoline_lookup, mangle_function_name, trampoline_impl

NEVER_MUTATE_FUNCTION_NAMES = {"__getattribute__", "__setattr__", "__new__"}
NEVER_MUTATE_FUNCTION_CALLS = {"len", "isinstance"}


@dataclass
class Mutation:
    original_node: cst.CSTNode
    mutated_node: cst.CSTNode
    contained_by_top_level_function: cst.FunctionDef | None


def mutate_file_contents(
    filename: str,  # noqa: ARG001 - kept for API compatibility with original mutmut
    code: str,
    covered_lines: set[int] | None = None,
) -> tuple[str, Sequence[str]]:
    """Create mutations for `code` and merge them to a single mutated file with trampolines.

    :return: A tuple of (mutated code, list of mutant function names)"""
    module, mutations = create_mutations(code, covered_lines)

    return combine_mutations_to_source(module, mutations)


def create_mutations(
    code: str,
    covered_lines: set[int] | None = None,
) -> tuple[cst.Module, list[Mutation]]:
    """Parse the code and create mutations."""
    ignored_lines = pragma_no_mutate_lines(code)

    module = cst.parse_module(code)

    metadata_wrapper = MetadataWrapper(module)
    visitor = MutationVisitor(mutation_operators, ignored_lines, covered_lines)
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
    ) -> None:
        self.mutations: list[Mutation] = []
        self._operators = operators
        self._ignored_lines = ignore_lines
        self._covered_lines = covered_lines
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

        # continue to mutate children
        return True

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
            nodes, mutant_names = function_trampoline_arrangement(
                func, func_mutants, class_name=None
            )
            result.extend(nodes)
            mutation_names.extend(mutant_names)
        elif isinstance(statement, cst.ClassDef):
            cls = statement
            if not isinstance(cls.body, cst.IndentedBlock):
                # we don't mutate single-line classes, e.g. `class A: a = 1; b = 2`
                result.append(cls)
            else:
                mutated_body = []
                for method in cls.body.body:
                    method_mutants = mutations_within_function.get(method)
                    if not isinstance(method, cst.FunctionDef) or not method_mutants:
                        mutated_body.append(method)
                        continue
                    nodes, mutant_names = function_trampoline_arrangement(
                        method, method_mutants, class_name=cls.name.value
                    )
                    mutated_body.extend(nodes)
                    mutation_names.extend(mutant_names)

                result.append(cls.with_changes(body=cls.body.with_changes(body=mutated_body)))
        else:
            result.append(statement)

    mutated_module = module.with_changes(body=result)
    return mutated_module.code, mutation_names


def function_trampoline_arrangement(
    function: cst.FunctionDef,
    mutants: Iterable[Mutation],
    class_name: str | None,
) -> tuple[Sequence[MODULE_STATEMENT], Sequence[str]]:
    """Create mutated functions and a trampoline that switches between versions.

    :return: A tuple of (nodes, mutant names)"""
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

    mutants_dict = list(
        cst.parse_module(
            create_trampoline_lookup(orig_name=name, mutants=mutant_names, class_name=class_name)
        ).body
    )
    mutants_dict[0] = mutants_dict[0].with_changes(leading_lines=[cst.EmptyLine()])

    nodes.extend(mutants_dict)

    return nodes, mutant_names


def create_trampoline_wrapper(
    function: cst.FunctionDef, mangled_name: str, class_name: str | None
) -> cst.FunctionDef:
    """Create a trampoline wrapper function that dispatches to original or mutant."""
    args: list[cst.Element | cst.StarredElement] = [
        cst.Element(p.name) for p in function.params.posonly_params
    ]
    args.extend(cst.Element(p.name) for p in function.params.params)
    if isinstance(function.params.star_arg, cst.Param):
        args.append(cst.StarredElement(function.params.star_arg.name))

    if class_name is not None:
        # remove self arg (handled by the trampoline function)
        args = args[1:]

    args_assignemnt = cst.Assign([cst.AssignTarget(cst.Name(value="args"))], cst.List(args))

    kwargs: list[cst.DictElement | cst.StarredDictElement] = [
        cst.DictElement(cst.SimpleString(f"'{p.name.value}'"), p.name)
        for p in function.params.kwonly_params
    ]
    if isinstance(function.params.star_kwarg, cst.Param):
        kwargs.append(cst.StarredDictElement(function.params.star_kwarg.name))

    kwargs_assignment = cst.Assign([cst.AssignTarget(cst.Name(value="kwargs"))], cst.Dict(kwargs))

    def _get_local_name(func_name: str) -> cst.BaseExpression:
        # for top level, simply return the name
        if class_name is None:
            return cst.Name(func_name)
        # for class methods, use object.__getattribute__(self, name)
        return cst.Call(
            func=cst.Attribute(cst.Name("object"), cst.Name("__getattribute__")),
            args=[cst.Arg(cst.Name("self")), cst.Arg(cst.SimpleString(f"'{func_name}'"))],
        )

    result: cst.BaseExpression = cst.Call(
        func=cst.Name("_mutmut_trampoline"),
        args=[
            cst.Arg(_get_local_name(f"{mangled_name}_orig")),
            cst.Arg(_get_local_name(f"{mangled_name}_mutants")),
            cst.Arg(cst.Name("args")),
            cst.Arg(cst.Name("kwargs")),
            cst.Arg(cst.Name("None" if class_name is None else "self")),
        ],
    )
    # for non-async functions, simply return the value or generator
    result_statement: cst.BaseStatement = cst.SimpleStatementLine([cst.Return(result)])

    if function.asynchronous:
        is_generator = _is_generator(function)
        if is_generator:
            result_statement = cst.For(
                target=cst.Name("i"),
                iter=result,
                body=cst.IndentedBlock(
                    [cst.SimpleStatementLine([cst.Expr(cst.Yield(cst.Name("i")))])]
                ),
                asynchronous=cst.Asynchronous(),
            )
        else:
            result_statement = cst.SimpleStatementLine([cst.Return(cst.Await(result))])

    type_ignore_whitespace = cst.TrailingWhitespace(comment=cst.Comment("# type: ignore"))

    return function.with_changes(
        body=cst.IndentedBlock(
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
    )


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


def pragma_no_mutate_lines(source: str) -> set[int]:
    """Return line numbers that have a `# pragma: no mutate` comment."""
    return {
        i + 1
        for i, line in enumerate(source.split("\n"))
        if "# pragma:" in line and "no mutate" in line.partition("# pragma:")[-1]
    }


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
