"""This module contains code for managing mutant creation for whole files."""

import ast
import io
import re
import tokenize
import unicodedata
import warnings
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import libcst as cst
import libcst.matchers as m
from libcst.metadata import (
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    QualifiedNameProvider,
    QualifiedNameSource,
)

from mutmut_win.constants import Profile
from mutmut_win.node_mutation import (
    OPERATORS_TYPE,
    _is_bare_decimal_integer,
    operators_for_profile,
)
from mutmut_win.trampoline import create_trampoline_lookup, mangle_function_name, trampoline_impl

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

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


def parse_module_preserving_newlines(source: str) -> cst.Module:
    """Parse source without losing a final bare CR during later code generation.

    LibCST recognises CR line endings but marks a module ending in bare CR as
    having no trailing newline. Correct that flag before replacing any nodes;
    the original newline spelling is already present in the CST.

    Args:
        source: Decoded Python source with its original physical newlines.

    Returns:
        Parsed module with an accurate trailing-newline flag.
    """
    module = cst.parse_module(source)
    if source.endswith("\r") and not module.has_trailing_newline:
        module = module.with_changes(has_trailing_newline=True)
    return module


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

    module = parse_module_preserving_newlines(code)

    metadata_wrapper = MetadataWrapper(module)
    visitor = MutationVisitor(
        operators_for_profile(active_profile),
        ignored_lines,
        covered_lines,
        do_not_mutate_patterns,
    )
    module = metadata_wrapper.visit(visitor)

    return module, visitor.mutations


class OuterFunctionProvider(cst.BatchableMetadataProvider[cst.CSTNode]):
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

    def __init__(self, provider: OuterFunctionProvider, top_level_node: cst.CSTNode) -> None:
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

    The created mutations will be accessible at `self.mutations`.

    Two candidate-local guards run before a mutation is recorded: a
    context-sensitive parenthesisation that fixes bare unary replacements at
    a ``**`` base and bare decimal integers at an attribute base (M-046,
    M-047), and a pattern-local syntax gate that discards candidates which
    cannot legally appear inside a ``case`` pattern, e.g. ``case +1``
    (M-048). Both keep the file-wide compile net in create_mutants_for_file
    as the last line of defence.
    """

    METADATA_DEPENDENCIES = (
        PositionProvider,
        OuterFunctionProvider,
        ParentNodeProvider,
        QualifiedNameProvider,
    )

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
        # Enclosing ClassDef nodes (maintained by on_visit/on_leave) so the
        # do_not_mutate_patterns can match a QUALIFIED ``Class.method`` name.
        # Invariant: the list holds exactly the ClassDef nodes whose subtree
        # is currently being visited.  Node IDENTITY is load-bearing: libcst
        # calls on_leave for every node — including ClassDefs skipped by
        # on_visit — so on_leave pops only when the leaving node is the top
        # entry (see M-038).
        self._class_nodes: list[cst.ClassDef] = []
        # ids() of CST nodes whose entire subtree must NOT be mutated.
        # Populated lazily when we hit a special-cased call like ``typing.cast(...)``
        # whose first argument is a pure type annotation (see Bug #4).
        self._skip_subtree_ids: set[int] = set()
        # id() -> enclosing case-pattern root for every node inside a match
        # pattern (M-048 pattern-local syntax gate). Filled in on_visit when
        # a MatchCase is entered; node identity stays valid for the whole
        # visitor run.
        self._pattern_root_by_id: dict[int, cst.MatchPattern] = {}

    def on_visit(self, node: cst.CSTNode) -> bool:
        if id(node) in self._skip_subtree_ids:
            return False
        if self._skip_node_and_children(node):
            return False

        if isinstance(node, cst.Expr) and self._is_docstring_expression(node):
            # Quote style does not determine whether a string is a docstring.
            # Mutating a leading single-quoted string statement changes only a
            # private implementation's ignored ``__doc__`` and creates a
            # structurally unkillable equivalent mutant (MW221-027).
            return False

        # Declaration identifiers are not runtime name reads.  Applying the
        # generic Name operator to ``def deepcopy(...)`` used to create a
        # mutant that was immediately overwritten by the private trampoline
        # name and was therefore byte-for-byte identical to the original.
        # Parameter declaration names have the same problem (and can also
        # produce an inconsistent signature/body pair), so prune those Name
        # nodes before libcst visits them.  References with the same spelling
        # inside the function body remain mutable.
        if isinstance(node, (cst.FunctionDef, cst.ClassDef, cst.Param)):
            self._skip_subtree_ids.add(id(node.name))

        # If this is a typing.cast(...) call, mark its first argument's entire
        # subtree as no-mutate. The first argument is a pure type annotation
        # (``cast`` is the identity function at runtime) and mutations there
        # are observable-equivalent — see Bug #4.
        if isinstance(node, cst.Call) and self._is_typing_cast_call(node) and node.args:
            node.args[0].value.visit(_SubtreeIdCollector(self._skip_subtree_ids))

        # Pattern-local syntax gate (M-048): record for every node inside a
        # case PATTERN which pattern it belongs to, so _create_mutations can
        # probe candidates against the pattern sub-grammar. Guards are plain
        # expressions and deliberately not part of the mapping.
        if isinstance(node, cst.MatchCase):
            node.pattern.visit(_PatternRootCollector(node.pattern, self._pattern_root_by_id))

        if self._should_mutate_node(node):
            self._create_mutations(node)

        # Track the enclosing class so do_not_mutate_patterns can match a
        # qualified ``Class.method`` name. Pushed only after the skip checks
        # above — a skipped class returns early, never pushed. on_leave only
        # pops when the leaving node IS the top entry, so skipped nested
        # classes cannot desynchronise the stack (M-038).
        if isinstance(node, cst.ClassDef):
            self._class_nodes.append(node)
        # continue to mutate children
        return True

    def _is_docstring_expression(self, node: cst.Expr) -> bool:
        if not isinstance(node.value, (cst.SimpleString, cst.ConcatenatedString)):
            return False
        # Python only assigns ``__doc__`` for a constant ``str`` expression.
        # Bytes literals evaluate to ``bytes`` and a concatenation containing
        # an f-string has no constant value, so both remain mutation targets.
        if not isinstance(node.value.evaluated_value, str):
            return False
        statement = self.get_metadata(ParentNodeProvider, node, None)
        if isinstance(statement, cst.SimpleStatementLine):
            if not statement.body or statement.body[0] is not node:
                return False
            body = self.get_metadata(ParentNodeProvider, statement, None)
            if isinstance(body, cst.Module):
                return bool(body.body and body.body[0] is statement)
            if isinstance(body, cst.IndentedBlock):
                owner = self.get_metadata(ParentNodeProvider, body, None)
                return (
                    isinstance(owner, (cst.FunctionDef, cst.ClassDef))
                    and bool(body.body)
                    and body.body[0] is statement
                )
            return False
        if isinstance(statement, cst.SimpleStatementSuite):
            owner = self.get_metadata(ParentNodeProvider, statement, None)
            return (
                isinstance(owner, (cst.FunctionDef, cst.ClassDef))
                and bool(statement.body)
                and statement.body[0] is node
            )
        return False

    def on_leave(self, original_node: cst.CSTNode) -> None:
        """Pop the enclosing-class stack when leaving a ``ClassDef``.

        libcst calls ``on_leave`` for EVERY node — including nodes whose
        ``on_visit`` returned ``False`` (a skipped nested ``ClassDef`` never
        pushes).  The stack stays balanced through node identity: pop only
        when the node being left IS the current top entry.
        """
        if (
            isinstance(original_node, cst.ClassDef)
            and self._class_nodes
            and self._class_nodes[-1] is original_node
        ):
            self._class_nodes.pop()

    def _create_mutations(self, node: cst.CSTNode) -> None:
        is_cast = isinstance(node, cst.Call) and self._is_typing_cast_call(node)
        original_first_arg: cst.Arg | None = None
        if is_cast:
            # mypy: the is_cast guard already proves node is a cst.Call
            assert isinstance(node, cst.Call)  # noqa: S101 - narrow-only assert
            original_first_arg = node.args[0] if node.args else None
        pattern_root = self._pattern_root_by_id.get(id(node))
        for t, operator in self._operators:
            if isinstance(node, t):
                for mutated_node in operator(node):
                    # Context-sensitive parenthesisation (Q-55): a bare unary
                    # replacement at a ** base (M-046) and a bare decimal
                    # integer at an attribute base (M-047) must be
                    # parenthesised BEFORE the candidate is recorded, so the
                    # gate below probes the repaired node.
                    mutated_node = _parenthesize_for_context(
                        self.get_metadata(ParentNodeProvider, node, None), node, mutated_node
                    )
                    # Pattern-local syntax gate (M-048): match patterns are a
                    # strict sub-grammar; discard candidates that cannot
                    # appear in a case pattern instead of losing the whole
                    # file in the file-wide safety net.
                    if pattern_root is not None and not _pattern_candidate_parses(
                        pattern_root, node, mutated_node
                    ):
                        continue
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
                        contained_by_top_level_function=cast(
                            "cst.FunctionDef | None",
                            self.get_metadata(OuterFunctionProvider, node, None),
                        ),
                    )
                    self.mutations.append(mutation)

    def _is_typing_cast_call(self, node: cst.Call) -> bool:
        """True only when scope metadata resolves the callable to ``typing.cast``.

        A spelling-only ``cast(...)`` check suppresses real mutations for a
        perfectly ordinary user function with that name.  QualifiedNameProvider
        distinguishes imported/aliased ``typing.cast`` from local definitions
        and from a locally shadowed ``typing`` object.
        """
        qualified_names = self.get_metadata(QualifiedNameProvider, node.func, set())
        return any(
            qualified_name.name in {"typing.cast", "typing_extensions.cast"}
            and qualified_name.source is QualifiedNameSource.IMPORT
            for qualified_name in qualified_names
        )

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

        # Python has no ``async yield from``.  A hand-written async-generator
        # proxy cannot transparently preserve the complete asend/athrow/aclose
        # protocol, while turning the public wrapper into a plain ``def``
        # breaks inspect.isasyncgenfunction and framework dispatch.  Leave
        # async generators intact until the trampoline can preserve both
        # contracts.  Synchronous generators are delegated with ``yield from``
        # in create_trampoline_wrapper and remain safe to mutate.
        if (
            isinstance(node, cst.FunctionDef)
            and node.asynchronous is not None
            and _is_generator(node)
        ):
            return True

        # PEP-695 type parameters are function-local runtime objects and may be
        # referenced by the body (``def f[T](): return T``).  Recreating them on
        # private copies changes object identity; removing them makes such a
        # body fail with NameError.  Until private implementations can close
        # over the public definition's type-parameter scope, leave generic
        # functions untouched rather than corrupting the clean run.
        if isinstance(node, cst.FunctionDef) and node.type_parameters is not None:
            return True

        # do_not_mutate_patterns (mutmut-3.6.0 backport): skip a function/class
        # whose SIMPLE or QUALIFIED name (``Class.method``, via the class stack)
        # matches any configured regex, pruning its whole subtree. Qualified
        # matching lets a pattern target one class's method (external QA: the
        # matcher used to be name-only).
        if self._name_skip_patterns and isinstance(node, (cst.FunctionDef, cst.ClassDef)):
            simple = node.name.value
            qualified = ".".join([*(klass.name.value for klass in self._class_nodes), simple])
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
        # 4) decorated CLASSES are locked for their own technical reason, not
        #    merely inherited from the function rules (external QA BC-132,
        #    refuted at the code): combine_mutations_to_source rewrites the
        #    class body so that each mutated method's public trampoline
        #    wrapper, its private ``…__mutmut_orig`` copy AND all mutant
        #    copies live INSIDE the class body.  A class decorator that
        #    touches members during class creation — calling, registering or
        #    introspecting them, as @dataclass-style registries do — still
        #    sees those private copies as unexpected class members (their
        #    lookup module names are pre-bound at class-creation time since
        #    M-039, so calls no longer NameError, but member-visible private
        #    copies remain).  Keep decorated classes unmutated wholesale.
        # EXCEPTION (W5 / mutmut-3.6.0 backport): a method decorated SOLELY with
        # @staticmethod IS mutated — create_trampoline_wrapper dispatches it like
        # a free function (no instance/class arg). Other decorators stay skipped.
        if isinstance(node, cst.FunctionDef) and _is_static_only(node):
            return False
        return bool(isinstance(node, (cst.FunctionDef, cst.ClassDef)) and len(node.decorators))


class _SubtreeIdCollector(cst.CSTVisitor):
    """Collect ``id()`` of every node in a CST subtree (including the root)."""

    def __init__(self, target: set[int]) -> None:
        super().__init__()
        self._target = target

    def on_visit(self, node: cst.CSTNode) -> bool:
        self._target.add(id(node))
        return True


def _parenthesize_for_context(
    parent: cst.CSTNode | None,
    node: cst.CSTNode,
    mutated_node: cst.CSTNode,
) -> cst.CSTNode:
    """Parenthesise a replacement only where the parent context demands it.

    Two contexts rebind or invalidate a bare replacement (Q-55, issue #168):

    - the base of ``**``: a bare ``UnaryOperation`` rebinds — ``-1 ** x``
      parses as ``-(1 ** x)``, not the promised ``(-1) ** x`` (M-046);
    - the base of an attribute access: a bare decimal integer swallows the
      dot into a float token — ``0.bit_length()`` is a SyntaxError (M-047).

    Everything else stays untouched: mutant texts remain diff-minimal, and
    mapping keys under profile ALL keep their valid bare form.

    Args:
        parent: The replaced node's parent from ``ParentNodeProvider``.
        node: The original node being replaced.
        mutated_node: The operator's candidate replacement.

    Returns:
        The candidate, parenthesised where the context demands it.
    """
    if (
        isinstance(parent, cst.BinaryOperation)
        and isinstance(parent.operator, cst.Power)
        and parent.left is node
    ):
        if isinstance(mutated_node, cst.UnaryOperation) and not mutated_node.lpar:
            return mutated_node.with_changes(
                lpar=[cst.LeftParen()],
                rpar=[cst.RightParen()],
            )
        return mutated_node
    if (
        isinstance(parent, cst.Attribute)
        and parent.value is node
        and _is_bare_decimal_integer(mutated_node)
    ):
        return mutated_node.with_changes(
            lpar=[cst.LeftParen()],
            rpar=[cst.RightParen()],
        )
    return mutated_node


class _PatternRootCollector(cst.CSTVisitor):
    """Map every node id inside a match pattern to that pattern's root node.

    Feeds the pattern-local syntax gate (M-048): for any node inside a
    ``case`` pattern, the gate needs the enclosing pattern to render the
    candidate in place and probe it. ``MatchCase.guard`` is deliberately NOT
    part of the subtree — guards are plain expressions that every operator
    may mutate freely.
    """

    def __init__(self, root: cst.MatchPattern, mapping: dict[int, cst.MatchPattern]) -> None:
        super().__init__()
        self._root = root
        self._mapping = mapping

    def on_visit(self, node: cst.CSTNode) -> bool:
        self._mapping[id(node)] = self._root
        return True


def _pattern_candidate_parses(
    pattern_root: cst.MatchPattern,
    node: cst.CSTNode,
    mutated_node: cst.CSTNode,
) -> bool:
    """Probe a candidate replacement inside a match pattern for valid syntax.

    Match patterns are a strict expression sub-grammar: ``case +1`` and
    ``case --1`` are SyntaxErrors even though ``+1``/``--1`` are fine as
    expressions, and a single invalid mutant made the file-wide safety net
    drop every mutant of the file with a loud SyntaxWarning (M-048 /
    issue #168). The candidate is rendered into its enclosing pattern and
    parsed inside a synthetic ``match`` statement.

    Only ``SyntaxError`` rejects a candidate; any other error propagates
    (fail-closed). SyntaxWarnings are suppressed locally because
    ``create_mutants_for_file`` records warnings with ``record=True`` /
    ``simplefilter('always')`` and forwards them to the user — string
    patterns with invalid escapes would otherwise leak one warning per
    candidate into the orchestrator channel.

    Args:
        pattern_root: The enclosing ``case`` pattern of ``node``.
        node: The original node being replaced.
        mutated_node: The operator's candidate replacement.

    Returns:
        True when the probed pattern parses, False on ``SyntaxError``.
    """
    candidate = pattern_root.deep_replace(node, mutated_node)
    rendered = cst.Module(body=[]).code_for_node(candidate)
    probe = f"match _:\n    case {rendered}:\n        pass\n"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            ast.parse(probe)
        except SyntaxError:
            return False
    return True


MODULE_STATEMENT = cst.SimpleStatementLine | cst.BaseCompoundStatement

# The generated artifact needs only the runtime helper function.  Injecting the
# template's typing imports and ``MutantDict`` alias overwrote perfectly legal
# user globals named Annotated/Callable/ClassVar/MutantDict.  Lookup annotations
# are removed below, so keep only the function and give it a module-unique name.
trampoline_function_cst = cst.ensure_type(
    cst.parse_module(trampoline_impl).body[-1], cst.FunctionDef
).with_changes(leading_lines=[cst.EmptyLine(), cst.EmptyLine()])


class _NameValueCollector(cst.CSTVisitor):
    """Collect every statically spelled identifier in one source module."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: cst.Name) -> None:  # noqa: N802
        self.names.add(node.value)


def _source_name_values(module: cst.Module) -> set[str]:
    collector = _NameValueCollector()
    module.visit(collector)
    return collector.names


def _fresh_module_name(base: str, source_names: set[str]) -> str:
    """Return an internal module identifier absent from all source Name nodes."""
    candidate = base
    suffix = 1
    while candidate in source_names:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


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
    source_names = _source_name_values(module)
    trampoline_name = _fresh_module_name("_mutmut_trampoline", source_names)

    # copy start of the module (in particular __future__ imports)
    result: list[MODULE_STATEMENT] = get_statements_until_func_or_class(module.body)
    mutation_names: list[str] = []
    # Python permits repeated definitions in one scope.  Their public binding
    # semantics are positional (later definitions replace earlier ones), but
    # private trampoline symbols and persistent mutant IDs must remain unique.
    # Count every syntactic same-name definition, including an earlier one that
    # is decorated/uncovered/unmutatable, so the ordinal also locates the exact
    # source node for show/apply/diff.  Method counts span repeated top-level
    # class definitions with the same class name in module order.
    definition_counts: defaultdict[tuple[str | None, str], int] = defaultdict(int)

    # statements we still need to potentially mutate and add to the result
    remaining_statements = module.body[len(result) :]

    # A per-module collision-free trampoline helper.  Later source assignments
    # to the conventional ``_mutmut_trampoline`` name cannot rebind this symbol.
    result.append(trampoline_function_cst.with_changes(name=cst.Name(trampoline_name)))

    mutations_within_function = group_by_top_level_node(mutations)

    # We now iterate through all top-level nodes.
    # If they are a function or class method, we mutate and add trampolines.
    # Else we keep the original node without modifications.
    for statement in remaining_statements:
        if isinstance(statement, cst.FunctionDef):
            func = statement
            top_definition_key = (None, func.name.value)
            definition_counts[top_definition_key] += 1
            definition_ordinal = definition_counts[top_definition_key]
            func_mutants = mutations_within_function.get(func)
            if not func_mutants:
                result.append(func)
                continue
            try:
                nodes, lookup_nodes, mutant_names = function_trampoline_arrangement(
                    func,
                    func_mutants,
                    class_name=None,
                    trampoline_name=trampoline_name,
                    source_names=source_names,
                    definition_ordinal=definition_ordinal,
                )
            except ValueError as exc:
                # Issue #121 / external QA MUT-002: an unmanglable identifier
                # (U+01C1 collides with the internal mangling separator) used
                # to drop the WHOLE file as "Unsupported syntax" — the skip is
                # function-granular now and names the engine limitation.
                _warn_unmanglable_function(func.name.value, exc)
                result.append(func)
                continue
            if not mutant_names:
                # Every candidate was either a declaration-name/no-op mutation
                # or rendered identically to an earlier candidate.  Do not
                # replace a perfectly ordinary function by an empty trampoline.
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
                    definition_ordinal = 1
                    if isinstance(method, cst.FunctionDef):
                        method_definition_key = (cls.name.value, method.name.value)
                        definition_counts[method_definition_key] += 1
                        definition_ordinal = definition_counts[method_definition_key]
                    method_mutants = mutations_within_function.get(method)
                    if not isinstance(method, cst.FunctionDef) or not method_mutants:
                        mutated_body.append(method)
                        continue
                    try:
                        nodes, lookup_nodes, mutant_names = function_trampoline_arrangement(
                            method,
                            method_mutants,
                            class_name=cls.name.value,
                            trampoline_name=trampoline_name,
                            source_names=source_names,
                            definition_ordinal=definition_ordinal,
                        )
                    except ValueError as exc:
                        # Same function-granular skip for methods/classes
                        # whose names collide with the mangling separator
                        # (issue #121 / MUT-002).
                        _warn_unmanglable_function(f"{cls.name.value}.{method.name.value}", exc)
                        mutated_body.append(method)
                        continue
                    if not mutant_names:
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
    *,
    trampoline_name: str = "_mutmut_trampoline",
    source_names: set[str] | None = None,
    definition_ordinal: int = 1,
) -> tuple[Sequence[MODULE_STATEMENT], Sequence[MODULE_STATEMENT], Sequence[str]]:
    """Create mutated functions and a trampoline that switches between versions.

    The lookup statements (mutants dict + ``__name__`` assignment) are
    returned separately: they must be emitted at MODULE level — for methods
    AFTER the class definition — because a dict in a class body becomes an
    ``enum.Enum`` member and its annotation broke ``NamedTuple`` (issue #77).
    For methods the original-scope nodes additionally end with class-body
    creation-time bindings (:func:`_class_creation_bindings`, M-039): a
    ``global`` statement plus module-global assignments that make the
    wrapper's names resolvable while the class itself is still being built.

    :return: A tuple of (nodes for the original scope, module-level lookup
        nodes, mutant names)"""
    if function.asynchronous is not None and _is_generator(function):
        # See MutationVisitor._skip_node_and_children.  Keep this public helper
        # fail-closed as well, so a direct caller cannot accidentally publish a
        # coroutine wrapper for an async-generator function.
        return (), (), ()
    if function.type_parameters is not None:
        # Same defensive invariant for PEP-695 generics: their public TypeVars
        # cannot be transparently shared with module-level private copies.
        return (), (), ()

    nodes: list[MODULE_STATEMENT] = []
    mutant_names: list[str] = []

    name = function.name.value
    mangled_name = (
        mangle_function_name(
            name=name,
            class_name=class_name,
            definition_ordinal=definition_ordinal,
        )
        + "__mutmut"
    )
    collisions = (
        sorted(
            source_name
            for source_name in source_names
            if source_name.startswith(f"{mangled_name}_")
        )
        if source_names is not None
        else []
    )
    if collisions:
        # A statically present source identifier would overwrite (or be
        # overwritten by) this function's private orig/mutant/dict namespace.
        # Skipping one function is safer than corrupting the clean module.
        qualified_name = f"{class_name}.{name}" if class_name else name
        warnings.warn(
            f"cannot mutate function '{qualified_name}': source identifier "
            f"{collisions[0]!r} collides with its internal trampoline namespace — "
            "function left unmutated",
            SyntaxWarning,
            stacklevel=3,
        )
        return (), (), ()

    # trampoline with same signature, that forwards the calls to the activated mutant/original
    # (put first, s.t. it stays next to @overload definitions of this function. mypy needs this)
    nodes.append(
        create_trampoline_wrapper(
            function, mangled_name, class_name, trampoline_name=trampoline_name
        )
    )

    # Private implementations receive already-bound arguments from the public
    # wrapper.  Defaults, annotations, decorators and PEP-695 type parameters
    # must therefore exist only on that public definition: evaluating them on
    # every private copy repeats arbitrary import-time side effects.  In
    # particular, @staticmethod must decorate only the public method.
    original_implementation = _implementation_function(function, mangled_name + "_orig")
    nodes.append(original_implementation)

    # Deduplicate on the fully rendered private implementation, not merely on
    # the local replacement node.  Different operators can generate the same
    # function (True->False vs force-false, +1 vs CRCR), and declaration-name
    # replacements can disappear when the implementation receives its private
    # name.  Both are equivalent mutants and must not affect the score.
    seen_renderings = {_rendered_function_key(original_implementation)}

    # mutated versions of the function
    for mutant in mutants:
        mutated_function = cst.ensure_type(
            deep_replace(function, mutant.original_node, mutant.mutated_node),
            cst.FunctionDef,
        )
        candidate = _implementation_function(mutated_function, "_mutmut_candidate")
        rendered = _rendered_function_key(candidate)
        if rendered in seen_renderings:
            continue
        seen_renderings.add(rendered)

        mutant_name = f"{mangled_name}_{len(mutant_names) + 1}"
        mutant_names.append(mutant_name)
        nodes.append(candidate.with_changes(name=cst.Name(mutant_name)))

    if class_name is not None:
        # M-039: bind the wrapper's module-level names at class-creation
        # time, directly after THIS method's own nodes (not collected at the
        # class end) so an interleaved class attribute, decorator or enum
        # member creation between two methods already sees them.
        nodes.extend(_class_creation_bindings(mangled_name, mutant_names))

    lookup_nodes = _unannotated_trampoline_lookup(
        orig_name=name,
        mutants=mutant_names,
        class_name=class_name,
        capture_class_original=class_name is not None,
        definition_ordinal=definition_ordinal,
    )
    lookup_nodes[0] = lookup_nodes[0].with_changes(leading_lines=[cst.EmptyLine()])

    return nodes, lookup_nodes, mutant_names


def _class_creation_bindings(
    mangled_name: str, mutant_names: Sequence[str]
) -> list[cst.SimpleStatementLine]:
    """Bind a method's trampoline module globals at class-creation time.

    The public wrapper (still inside the class body) resolves
    ``<mangled>_orig_ref`` and ``<mangled>_mutants`` as GLOBAL names, but the
    module-level capture and lookup only run AFTER the class statement
    (issue #77).  Any call of the method while the class is being built —
    ``enum`` member creation invoking ``__init__`` or
    ``_generate_next_value_``, a class attribute computed from an own method,
    a decorator defined in the class body — therefore raised NameError before
    the trampoline could run (M-039).  A ``global`` statement inside the
    class body binds both names at module scope WITHOUT touching the class
    namespace: no ``enum.Enum`` member, no ``NamedTuple`` field — issue #77
    stays preserved.  The ``__name__`` assignment mirrors
    ``create_trampoline_lookup`` so ``MUTANT_UNDER_TEST`` activation and the
    stats prefix already work during class creation; the unchanged post-class
    capture and lookup rebind both names after the class statement exactly as
    before.

    No other class-body statement may read either name before this
    declaration (SyntaxError "used prior to global declaration"); the
    source-name collision check in :func:`function_trampoline_arrangement`
    guarantees that.

    :param mangled_name: Private name prefix including the ``__mutmut`` suffix.
    :param mutant_names: Mangled names of this method's mutants.
    :return: Statements to emit directly after the method's own nodes.
    """
    type_ignore = cst.TrailingWhitespace(comment=cst.Comment("# type: ignore"))
    public_name = mangled_name.removesuffix("__mutmut")
    mutants_dict = cst.Dict(
        [
            # Keys are the mangled mutant-name strings; values are the
            # class-body-local mutant functions defined just above.
            cst.DictElement(cst.SimpleString(repr(mutant_name)), cst.Name(mutant_name))
            for mutant_name in mutant_names
        ]
    )
    return [
        cst.SimpleStatementLine(
            body=[
                cst.Global(
                    [
                        cst.NameItem(cst.Name(f"{mangled_name}_orig_ref")),
                        cst.NameItem(cst.Name(f"{mangled_name}_mutants")),
                    ]
                )
            ],
            trailing_whitespace=type_ignore,
        ),
        cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(cst.Name(f"{mangled_name}_orig_ref"))],
                    value=cst.Name(f"{mangled_name}_orig"),
                )
            ],
            trailing_whitespace=type_ignore,
        ),
        cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(cst.Name(f"{mangled_name}_mutants"))],
                    value=mutants_dict,
                )
            ],
            trailing_whitespace=type_ignore,
        ),
        cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[
                        cst.AssignTarget(
                            cst.Attribute(
                                value=cst.Name(f"{mangled_name}_orig"), attr=cst.Name("__name__")
                            )
                        )
                    ],
                    value=cst.SimpleString(repr(public_name)),
                )
            ],
            trailing_whitespace=type_ignore,
        ),
    ]


def _unannotated_trampoline_lookup(
    *,
    orig_name: str,
    mutants: list[str],
    class_name: str | None,
    capture_class_original: bool,
    definition_ordinal: int,
) -> list[MODULE_STATEMENT]:
    """Build lookup statements without injecting a user-visible typing alias."""
    lookup_nodes: list[MODULE_STATEMENT] = list(
        cst.parse_module(
            create_trampoline_lookup(
                orig_name=orig_name,
                mutants=mutants,
                class_name=class_name,
                definition_ordinal=definition_ordinal,
            )
        ).body
    )
    first_line = cst.ensure_type(lookup_nodes[0], cst.SimpleStatementLine)
    annotated_assignment = cst.ensure_type(first_line.body[0], cst.AnnAssign)
    value = annotated_assignment.value
    if value is None:  # defensive: the template always emits a dict value
        msg = "trampoline lookup template produced an annotation without a value"
        raise ValueError(msg)
    assignment = cst.Assign(
        targets=[cst.AssignTarget(annotated_assignment.target)],
        value=value,
        semicolon=annotated_assignment.semicolon,
    )
    lookup_nodes[0] = first_line.with_changes(body=[assignment])
    if capture_class_original:
        if class_name is None:  # pragma: no cover - guarded by the caller
            msg = "a class original capture requires a class name"
            raise ValueError(msg)
        mangled_name = (
            mangle_function_name(
                name=orig_name,
                class_name=class_name,
                definition_ordinal=definition_ordinal,
            )
            + "__mutmut"
        )
        capture = cst.SimpleStatementLine(
            [
                cst.Assign(
                    targets=[cst.AssignTarget(cst.Name(f"{mangled_name}_orig_ref"))],
                    value=cst.Attribute(
                        value=cst.Name(class_name),
                        attr=cst.Name(f"{mangled_name}_orig"),
                    ),
                )
            ]
        )
        lookup_nodes.insert(0, capture)
    return lookup_nodes


def _implementation_param(param: cst.Param) -> cst.Param:
    """Return a private-implementation parameter without definition-time metadata."""
    return param.with_changes(
        annotation=None,
        default=None,
        equal=cst.MaybeSentinel.DEFAULT,
    )


def _implementation_parameters(params: cst.Parameters) -> cst.Parameters:
    """Strip annotations/defaults while preserving the public call shape."""
    star_arg = params.star_arg
    if isinstance(star_arg, cst.Param):
        star_arg = _implementation_param(star_arg)
    star_kwarg = params.star_kwarg
    if star_kwarg is not None:
        star_kwarg = _implementation_param(star_kwarg)
    return params.with_changes(
        posonly_params=[_implementation_param(param) for param in params.posonly_params],
        params=[_implementation_param(param) for param in params.params],
        star_arg=star_arg,
        kwonly_params=[_implementation_param(param) for param in params.kwonly_params],
        star_kwarg=star_kwarg,
    )


def _implementation_function(function: cst.FunctionDef, name: str) -> cst.FunctionDef:
    """Build one side-effect-free private implementation of ``function``."""
    return function.with_changes(
        name=cst.Name(name),
        params=_implementation_parameters(function.params),
        decorators=(),
        returns=None,
        type_parameters=None,
        leading_lines=(),
        lines_after_decorators=(),
    )


def _rendered_function_key(function: cst.FunctionDef) -> str:
    """Canonical rendered key for original/no-op and cross-operator deduplication."""
    normalized = function.with_changes(name=cst.Name("_mutmut_candidate"), leading_lines=())
    return cst.Module(body=[]).code_for_node(normalized)


def _fresh_wrapper_name(base: str, used_names: set[str]) -> str:
    """Choose a deterministic wrapper-local name outside the public signature."""
    candidate = base
    suffix = 1
    while candidate in used_names:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def _docstring_statement(function: cst.FunctionDef) -> cst.BaseStatement | None:
    """Return a standalone copy of the public function's docstring statement."""

    def is_docstring(expression: cst.BaseSmallStatement) -> bool:
        return (
            isinstance(expression, cst.Expr)
            and isinstance(expression.value, (cst.SimpleString, cst.ConcatenatedString))
            and isinstance(expression.value.evaluated_value, str)
        )

    if isinstance(function.body, cst.IndentedBlock):
        if not function.body.body:
            return None
        first = function.body.body[0]
        if isinstance(first, cst.SimpleStatementLine) and first.body:
            first_small_statement = first.body[0]
            if is_docstring(first_small_statement):
                if len(first.body) == 1:
                    return first
                # A physical line may contain real statements after the
                # leading docstring. Copy only the string into the wrapper;
                # the selected private implementation executes the rest.
                assert isinstance(first_small_statement, cst.Expr)  # noqa: S101
                return cst.SimpleStatementLine([cst.Expr(first_small_statement.value)])
        return None

    if isinstance(function.body, cst.SimpleStatementSuite) and function.body.body:
        first_small_statement = function.body.body[0]
        if is_docstring(first_small_statement):
            # A one-line suite may contain more statements after a semicolon.
            # Keep only the leading string expression in the wrapper.
            assert isinstance(first_small_statement, cst.Expr)  # noqa: S101 - narrowed above
            return cst.SimpleStatementLine([cst.Expr(first_small_statement.value)])
    return None


def _compiled_parameter_name(name: str, class_name: str | None) -> str:
    """Return the identifier CPython actually binds for a parameter name.

    The tokenizer normalizes every identifier with NFKC (``U+00B5`` becomes
    ``U+03BC``, the KELVIN SIGN becomes ``K``), and inside a class body
    private name mangling additionally rewrites an identifier that starts
    with two underscores but does not end with them to
    ``_<class><name>`` — the leading underscores of the class name are
    stripped, and a class name consisting only of underscores does not
    mangle at all (``_Py_Mangle`` semantics of CPython 3.14).  NFKC runs
    FIRST on the parameter and the class name, then the mangling rule is
    applied to the normalized forms.

    :param name: Raw parameter name as written in the source.
    :param class_name: Raw enclosing class name, or ``None`` for a
        top-level function (no mangling).
    :return: The compiled identifier, for use in generated string keys.
    """
    compiled = unicodedata.normalize("NFKC", name)
    if class_name is not None and compiled.startswith("__") and not compiled.endswith("__"):
        stripped_class = unicodedata.normalize("NFKC", class_name).lstrip("_")
        if stripped_class:
            compiled = f"_{stripped_class}{compiled}"
    return compiled


def create_trampoline_wrapper(
    function: cst.FunctionDef,
    mangled_name: str,
    class_name: str | None,
    *,
    trampoline_name: str = "_mutmut_trampoline",
) -> cst.FunctionDef:
    """Create a trampoline wrapper function that dispatches to original or mutant.

    Codegen safety (issue #76): the instance/class argument is referenced by
    its REAL first-parameter name (``cls`` for ``__init_subclass__``,
    ``this``, … — the old hardcoded ``self`` raised NameError in the clean
    run, A1-MT-001); wrapper locals are chosen outside the complete public
    parameter set (A1-MT-002); ``*args`` is forwarded intact (A1-MT-003);
    synchronous generators delegate through ``yield from`` and retain their
    generator-function identity.  Async generators are conservatively excluded
    before this helper is called because Python has no transparent async
    ``yield from`` equivalent.  Methods whose complete positional signature is
    ``*args`` are supported as well: descriptor binding places the instance in
    that tuple and the wrapper forwards it without guessing a ``self`` name.

    Keyword-only parameters are forwarded through a dict whose STRING keys
    must be the identifiers CPython binds (M-040): NFKC-normalized and, for
    methods, privately mangled (``__x`` in ``class C`` compiles to ``_C__x``
    because the wrapper shares the class body).  Keyword names at CALL sites
    are never mangled, so a caller overrides such a default with ``_C__x=…``.
    """
    named_params = [*function.params.posonly_params, *function.params.params]
    used_names = {
        _compiled_parameter_name(param.name.value, class_name)
        for param in [
            *function.params.posonly_params,
            *function.params.params,
            *function.params.kwonly_params,
        ]
    }
    if isinstance(function.params.star_arg, cst.Param):
        used_names.add(_compiled_parameter_name(function.params.star_arg.name.value, class_name))
    if function.params.star_kwarg is not None:
        used_names.add(_compiled_parameter_name(function.params.star_kwarg.name.value, class_name))
    args_local_name = _fresh_wrapper_name("_mutmut_args", used_names)
    kwargs_local_name = _fresh_wrapper_name("_mutmut_kwargs", used_names)

    # Private implementations and lookup entries are raw functions.  Forward
    # every positional parameter, including an instance method's first one,
    # through the same argument list.  A legal unbound call such as
    # ``C.m(None, value)`` must not confuse ``None`` with a no-instance
    # sentinel (MW221-023).
    args: list[cst.Element | cst.StarredElement] = [cst.Element(p.name) for p in named_params]
    if isinstance(function.params.star_arg, cst.Param):
        args.append(cst.StarredElement(function.params.star_arg.name))

    args_assignment = cst.Assign(
        [cst.AssignTarget(cst.Name(value=args_local_name))], cst.List(args)
    )

    kwargs: list[cst.DictElement | cst.StarredDictElement] = [
        # M-040: the key is the COMPILED parameter name (NFKC + private
        # class mangling); the value expression is a CST name that the
        # compiler renames identically, so both sides stay in sync.
        cst.DictElement(
            cst.SimpleString(repr(_compiled_parameter_name(p.name.value, class_name))),
            p.name,
        )
        for p in function.params.kwonly_params
    ]
    if isinstance(function.params.star_kwarg, cst.Param):
        kwargs.append(cst.StarredDictElement(function.params.star_kwarg.name))

    kwargs_assignment = cst.Assign(
        [cst.AssignTarget(cst.Name(value=kwargs_local_name))], cst.Dict(kwargs)
    )

    def _get_local_name(func_name: str) -> cst.BaseExpression:
        # for top level, simply return the name
        if class_name is None:
            return cst.Name(func_name)
        # Methods (including @staticmethod) use the raw module-level reference
        # captured immediately after class creation.  Rebinding the public
        # class name later therefore cannot break saved class aliases, and the
        # complete argument list above retains ordinary descriptor semantics.
        # During class creation itself the same module globals already exist
        # via the class-body creation-time bindings (M-039), so calls from
        # ``__init__`` during enum member creation, class attributes computed
        # from own methods, and class-body decorators resolve as well.
        return cst.Name(f"{mangled_name}_orig_ref")

    result: cst.BaseExpression = cst.Call(
        func=cst.Name(trampoline_name),
        args=[
            cst.Arg(_get_local_name(f"{mangled_name}_orig")),
            # The mutants dict lives at module level (issue #77), so it is
            # resolved as a global name even from inside a method body.
            cst.Arg(cst.Name(f"{mangled_name}_mutants")),
            cst.Arg(cst.Name(args_local_name)),
            cst.Arg(cst.Name(kwargs_local_name)),
        ],
    )
    # Plain synchronous functions simply return the selected implementation's
    # value.  A synchronous generator must contain a yield in the public wrapper
    # as well, otherwise inspect.isgeneratorfunction and framework dispatch are
    # silently changed.  ``yield from`` also preserves send/throw/close and the
    # generator return value.
    result_statement: cst.BaseStatement = cst.SimpleStatementLine([cst.Return(result)])

    if _is_generator(function):
        delegated_yield = cst.Yield(
            value=cst.From(item=result),
            lpar=[cst.LeftParen()],
            rpar=[cst.RightParen()],
        )
        result_statement = cst.SimpleStatementLine([cst.Return(delegated_yield)])
    elif function.asynchronous:
        result_statement = cst.SimpleStatementLine([cst.Return(cst.Await(result))])

    type_ignore_whitespace = cst.TrailingWhitespace(comment=cst.Comment("# type: ignore"))

    wrapper_body: list[cst.BaseStatement] = []
    docstring = _docstring_statement(function)
    if docstring is not None:
        wrapper_body.append(docstring)
    wrapper_body.extend(
        [
            cst.SimpleStatementLine([args_assignment], trailing_whitespace=type_ignore_whitespace),
            cst.SimpleStatementLine(
                [kwargs_assignment], trailing_whitespace=type_ignore_whitespace
            ),
            result_statement,
        ]
    )
    return function.with_changes(body=cst.IndentedBlock(wrapper_body))


def get_statements_until_func_or_class(
    statements: Sequence[MODULE_STATEMENT],
) -> list[MODULE_STATEMENT]:
    """Get all statements until we encounter the first function or class definition."""
    result: list[MODULE_STATEMENT] = []

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
    marker = re.search(
        r"#\s*pragma:\s*no\s+mutate(?=$|\s)(?:\s+(?P<suffix>\S+))?",
        line,
        flags=re.IGNORECASE,
    )
    if marker is None:
        return None
    suffix = marker.group("suffix")
    if suffix is None:
        return ""
    word = suffix.lower()
    return word if word in {"start", "end", "block"} else ""


def _pragma_block_range(lines: list[str], pragma_index: int) -> range:
    """1-based line range covered by a ``block`` pragma at ``lines[pragma_index]``.

    The pragma line plus the suite below it: every following line indented
    deeper than the pragma line, through the last such non-blank line.

    Legacy physical-indent extent; still used for ``block`` pragmas on
    comment-only lines and inside bracketed continuation lines, where the
    token-based extent (:func:`_pragma_block_range_from_tokens`) must not
    apply (it would swallow the enclosing header's suite).
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


def _pragma_block_range_from_tokens(
    tokens: Sequence[tokenize.TokenInfo], pragma_index: int
) -> range | None:
    """Token-stream block extent for a ``block`` pragma, or ``None`` for the legacy path.

    Applies only when the pragma comment sits on a CODE line that closes its
    logical line (the very next token is a ``NEWLINE`` on the same physical
    line). The extent then is that logical line plus — when the next
    significant token opens a suite — the whole suite, bounded by INDENT/DEDENT
    depth counting through the last ``NEWLINE`` before the matching ``DEDENT``.
    Comments and string CONTENT are invisible to the tokenizer's indent
    bookkeeping, so unlike the physical-indent scan they cannot end the block
    early (M-043).

    Returns:
        The covered 1-based line range, or ``None`` when the caller must keep
        the legacy physical-indent extent: comment-only pragma lines (the next
        significant token would be the ENCLOSING header's INDENT, swallowing
        the whole surrounding body) and pragmas inside bracketed continuation
        lines (no same-line ``NEWLINE``; widening to the full suite would
        exceed the documented pragma contract).
    """
    pragma_line = tokens[pragma_index].start[0]
    following = tokens[pragma_index + 1] if pragma_index + 1 < len(tokens) else None
    if following is None or following.type != tokenize.NEWLINE or following.start[0] != pragma_line:
        return None
    end_line = following.end[0]

    cursor = pragma_index + 2
    while cursor < len(tokens) and tokens[cursor].type in (tokenize.NL, tokenize.COMMENT):
        cursor += 1
    if cursor >= len(tokens) or tokens[cursor].type != tokenize.INDENT:
        # no suite below: the block is just the (logical) pragma line
        return range(pragma_line, end_line + 1)

    depth = 1
    cursor += 1
    while cursor < len(tokens) and depth:
        token = tokens[cursor]
        if token.type == tokenize.INDENT:
            depth += 1
        elif token.type == tokenize.DEDENT:
            depth -= 1
        elif token.type == tokenize.NEWLINE:
            # remember the last statement line inside the suite; comments or
            # blank lines after it do not extend the block
            end_line = token.end[0]
        cursor += 1
    return range(pragma_line, end_line + 1)


def pragma_no_mutate_lines(source: str) -> set[int]:
    """Return line numbers (1-based) excluded by ``# pragma: no mutate`` comments.

    Recognises four forms (mutmut-3.6.0 surface backport):

    - ``# pragma: no mutate`` — the comment's own line (the original behaviour).
    - ``# pragma: no mutate block`` — that line plus the suite below it. On a
      code line the extent follows the token stream (INDENT/DEDENT depth), so
      comment lines and multi-line string contents do not end the block early;
      comment-only and continuation-line pragmas keep the physical-indent
      extent.
    - ``# pragma: no mutate start`` … ``# pragma: no mutate end`` — the inclusive
      range between the two markers; a dangling ``start`` skips to end-of-file.
    """
    # Tokenize follows Python's universal-newline view; the CST input remains
    # untouched so comments, string literals and continuations retain bytes.
    scanner_source = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = scanner_source.split("\n")
    ignored: set[int] = set()
    open_start: int | None = None
    # Tokenization is essential here: scanning raw source text mistakes pragma
    # lookalikes in ordinary, raw, f- and triple-quoted strings for comments and
    # can suppress every mutation through EOF.  Only Python COMMENT tokens are
    # directives.  A ``block`` pragma's extent is likewise derived from the
    # token stream (INDENT/DEDENT depth, see _pragma_block_range_from_tokens)
    # so comment-only lines and multi-line string CONTENT cannot end the block
    # early; comment-only and continuation-line pragmas keep the physical
    # indent extent via _pragma_block_range.
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(scanner_source).readline))
    except (
        tokenize.TokenError,
        SyntaxError,
    ):
        # pragma_no_mutate_lines runs before libcst parsing.  An incomplete
        # token stream (unclosed bracket/string, etc.) must not replace the
        # parser's established graceful-error path with an earlier TokenError.
        # Ignore all provisional directives and let the real parser adjudicate
        # the invalid source.
        return set()
    for position, token in enumerate(tokens):
        if token.type != tokenize.COMMENT:
            continue
        suffix = _pragma_no_mutate_suffix(token.string)
        if suffix is None:
            continue
        lineno = token.start[0]
        index = lineno - 1
        if suffix == "start":
            if open_start is None:
                open_start = lineno
        elif suffix == "end":
            start = open_start if open_start is not None else lineno
            ignored.update(range(start, lineno + 1))
            open_start = None
        elif suffix == "block":
            token_range = _pragma_block_range_from_tokens(tokens, position)
            if token_range is not None:
                ignored.update(token_range)
            else:
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

    # Replacement operators may intentionally change the concrete CST type.
    def on_leave(  # type: ignore[override]
        self, original_node: cst.CSTNode, updated_node: cst.CSTNode
    ) -> cst.CSTNode:
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

    We do so by checking if any child is a Yield statement, but not looking
    into inner function definitions or lambda BODIES (both are their own
    scope: a ``yield`` there makes only the nested callable a generator).
    Lambda parameter DEFAULTS, however, are evaluated in the enclosing
    scope — ``lambda x=(yield): x`` DOES make the surrounding (async)
    function a generator — so they are visited explicitly before the body
    is skipped (M-044)."""

    def __init__(self, original_function: cst.FunctionDef) -> None:
        self.is_generator = False
        self.original_function: cst.FunctionDef = original_function

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool | None:  # noqa: N802
        # do not recurse into inner function definitions
        if self.original_function != node:
            return False
        return None

    def visit_Lambda(self, node: cst.Lambda) -> bool | None:  # noqa: N802
        # do not recurse into the lambda BODY (own scope), but evaluate its
        # parameter defaults in this scope like the compiler does.  A var-*
        # parameter cannot carry a default in valid Python source, so only
        # the three ordinary parameter groups are visited.
        params = node.params
        for param in (*params.posonly_params, *params.params, *params.kwonly_params):
            if param.default is not None:
                param.default.visit(self)
        return False

    # ARG002: libcst CSTVisitor requires the node parameter in visitor methods
    def visit_Yield(self, node: cst.Yield) -> bool | None:  # noqa: N802, ARG002
        self.is_generator = True
        return False
