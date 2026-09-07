"""Constants for mutmut-win: exit code mappings and status definitions."""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path


class Profile(IntEnum):
    """Mutation-operator profile, ordered by inclusiveness.

    Higher profiles are supersets of lower ones: ``advanced`` adds mutmut-win's
    extra operators on top of mutmut's ``basic`` base set, and ``all`` adds the
    aggressive operators on top of that. The integer order drives the registry
    filter — an operator tagged with profile ``P`` is active iff ``P <= active``
    (see ``node_mutation.operators_for_profile``).

    ``advanced`` is the out-of-box default and equals mutmut-win's historical
    behaviour; ``basic`` is strict mutmut parity (the 15 base operators only).
    """

    BASIC = 0
    ADVANCED = 1
    ALL = 2

    @classmethod
    def from_name(cls, name: str) -> Profile:
        """Parse a case-insensitive profile name such as ``"advanced"``.

        :raises ValueError: if ``name`` is not one of basic/advanced/all.
        """
        try:
            return cls[name.strip().upper()]
        except KeyError:
            valid = ", ".join(p.to_name() for p in cls)
            raise ValueError(
                f"unknown mutation profile {name!r}; valid profiles: {valid}"
            ) from None

    def to_name(self) -> str:
        """Return the lower-case CLI/config name, e.g. ``"advanced"``."""
        return self.name.lower()


#: Environment variable read by the trampoline to select the mutant under
#: test. Single source of truth (issue #110 / A4-QX-019) — runner.py and
#: process/worker.py re-export it; the literal inside the trampoline
#: TEMPLATE stays standalone by design (the generated artifact must not
#: import mutmut_win for the env read) and is pinned against this value.
MUTANT_ENV_VAR: str = "MUTANT_UNDER_TEST"

#: Ownership marker for mutation metadata sidecars.  Runtime verdicts and
#: durations inside these files are mutable outputs, while source/generation
#: hashes and the mutant-name universe are stable execution inputs.  The
#: marker lets the context digester project only tool-owned sidecars without
#: confusing an arbitrary user fixture named ``*.meta`` for internal state.
SOURCE_METADATA_SCHEMA: str = "mutmut-win-source-metadata-v1"

#: Internal controls removed from the external type-checker environment as a
#: hygiene boundary. The run basis still hashes every inherited environment
#: value: Python startup hooks can observe a value before a later launcher has
#: a chance to remove or overwrite it.
INTERNAL_CHILD_ENVIRONMENT_VARS: frozenset[str] = frozenset(
    {
        MUTANT_ENV_VAR,
        "MUTMUT_PYTEST_PHASE_SENTINEL_PATH",
        "MUTMUT_PYTEST_PHASE_SENTINEL_PROOF",
        "MUTMUT_PYTEST_ALLOWED_DIRS",
        "MUTMUT_PYTEST_ALLOWED_FILES",
        "PY_IGNORE_IMPORTMISMATCH",
    }
)

#: Minimum pytest version in the TARGET venv (issue #125 / 360°-A2). The
#: worker hands per-mutant tests to pytest via the ``@argfile`` syntax — the
#: only transfer path by design (no dual code paths, no 32k-limit
#: thresholds) — and that syntax exists since pytest 8.2 ("Added in
#: version 8.2"). Single source of truth: the orchestrator guard enforces
#: it at run start, the pyproject dependency floor encodes it for the
#: resolver, and a pin test keeps both in sync (the #110 pattern).
MINIMUM_PYTEST_VERSION: tuple[int, int] = (8, 2)

#: Exclusive upper pytest version bound. The immutable configuration
#: discovery boundary deliberately mirrors only pytest 8.2+ and pytest 9;
#: unknown future majors must be reviewed before mutation execution.
MAXIMUM_PYTEST_VERSION_EXCLUSIVE: tuple[int, int] = (10, 0)

#: Source roots whose name is stripped from module paths AND mirrored into
#: the staging / put on the worker PYTHONPATH (issue #126 / 360°-A3).
#: Single source of truth: ``get_mutant_name`` strips exactly these
#: prefixes, and ``copy_src_dir``, ``setup_source_paths``,
#: ``runner._mutants_env`` and the worker build their root lists from this
#: tuple — the old per-site literals let ``source/`` be importable but
#: never name-stripped, so every mutant of a source/-layout was 'no tests'.
#: ``"."`` is deliberately NOT part of this tuple: modules under the
#: project root carry no prefix to strip.
SOURCE_ROOT_NAMES: tuple[str, ...] = ("src", "source")


def configured_staging_relative_path(
    raw_path: str | Path,
    *,
    project_root: Path,
) -> Path | None:
    """Map one configured mirror/import path to its relative staging target.

    Absolute project-internal inputs are canonicalized before relativization,
    so Windows long names, 8.3 aliases, and case variants cannot make the
    planner, copy phase, runner, and worker disagree.  Absolute external and
    drive-relative inputs are not staged.  Explicit ``..`` siblings retain the
    long-standing Bug-#69 contract of being mirrored under their basename.
    """

    path = Path(raw_path)
    # On Windows, both ``C:relative`` and ``\root-relative`` are anchored
    # without being absolute. Joining either to ``mutants`` discards the
    # staging root, so every consumer must reject them before composition.
    if path.anchor and not path.is_absolute():
        return None
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(project_root.resolve())
        # Parenthesized for the pinned Semgrep parser, which does not yet
        # understand Python 3.14's PEP 758 bare multi-exception syntax.
        except (OSError, RuntimeError, ValueError):  # fmt: skip
            return None
    if ".." in path.parts:
        path = Path(path.name)
    if not path.name or path in {Path(), Path("..")}:
        return None
    return path


#: Workspace directory names that are neither copied into mutation staging nor
#: execution-basis inputs.  Keeping one immutable set prevents generated tool
#: state (for example import-linter or IDE caches) from invalidating a run even
#: though the same bytes are deliberately absent from every worker tree.
WORKSPACE_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
        ".hypothesis",
        ".tox",
        ".nox",
        "mutants",
        ".mutmut-cache",
        "dist",
        "build",
        "htmlcov",
        "html",
        "node_modules",
        ".import_linter_cache",
        ".benchmarks",
        ".serena",
        ".claude",
        ".codex",
        ".sprint",
        "bug_reporting",
        "_docs",
        ".idea",
        ".vscode",
    }
)

#: The subset that is tooling/generated state regardless of nesting depth.
#: Human project directories with generic names such as ``build`` or ``html``
#: are excluded only at the workspace root; nested packages with those names
#: remain executable source and therefore must be staged and fingerprinted.
WORKSPACE_RECURSIVE_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
        ".hypothesis",
        ".tox",
        ".nox",
        "mutants",
        ".mutmut-cache",
        "node_modules",
        ".import_linter_cache",
        ".benchmarks",
        "htmlcov",
        ".serena",
        ".claude",
        ".codex",
        ".sprint",
        ".idea",
        ".vscode",
    }
)

# Exit code to status mapping — based on mutmut 3.5.0, with two deliberate
# deviations (issue #91, audit A2-EW-020 / A4-QX-025):
#
# * Exit 2 maps to "killed", not "check was interrupted by user". pytest
#   exit 2 covers collection errors — and an import-breaking mutant that
#   aborts collection IS an observable behaviour change, i.e. a kill
#   (precedent: exit 3, pytest internal error, has always counted as one).
#   In mutmut-win workers a genuine user Ctrl-C ends the run via the
#   orchestrator's interrupt path, not via worker exit codes; the worker
#   captures the log tail for anomalous exits, so a collection kill stays
#   auditable ("Interrupted: N errors during collection" in last_output).
#   The legacy status string remains renderable for pre-v2.9 DB rows.
# * The duplicate -24 key is resolved to "timeout" (SIGXCPU, upstream
#   behaviour); the shadowed "killed" mapping was dead code.
#
# Negative codes (-24, -11, -9) are POSIX signal semantics — unreachable on
# the supported Windows runtime and retained only for legacy result rendering;
# they carry no POSIX runtime or CI-support commitment. Windows crashes surface
# as the unsigned DWORD form of NTSTATUS codes instead.

#: Status string for IL-classified kills — single source for the literal
#: that used to be duplicated in ``loop_monitor`` (issue #132 / 360°-B8).
STATUS_KILLED_BY_INFINITE_LOOP: str = "killed_by_infinite_loop"

# Plain dict (issue #132 / 360°-C6): the defaultdict factory inserted a key
# on EVERY unknown lookup — a stray read could grow the table. Readers use
# ``.get(code, "suspicious")``; the unknown→suspicious contract is pinned
# by tests.
status_by_exit_code: dict[int | None, str] = {
    0: "survived",
    1: "killed",
    2: "killed",  # pytest "Interrupted" — collection error under a mutant
    3: "killed",  # internal error in pytest means a kill
    5: "no tests",
    33: "no tests",
    34: "skipped",
    35: "suspicious",
    36: "timeout",
    37: "caught by type check",
    38: STATUS_KILLED_BY_INFINITE_LOOP,  # Issue #71 — triple-check IL classifier
    -24: "timeout",  # SIGXCPU (POSIX only)
    24: "timeout",  # SIGXCPU
    152: "timeout",  # SIGXCPU
    255: "timeout",
    -11: "segfault",  # SIGSEGV (POSIX only)
    -9: "segfault",  # SIGKILL, e.g. the OOM killer (POSIX only)
    0xC0000005: "segfault",  # Windows STATUS_ACCESS_VIOLATION
    0xC00000FD: "segfault",  # Windows STATUS_STACK_OVERFLOW (recursion mutants)
    0xC0000409: "segfault",  # Windows STATUS_STACK_BUFFER_OVERRUN
    None: "not checked",
}

emoji_by_status: dict[str, str] = {
    "survived": "\U0001f641",
    "no tests": "\U0001fae5",
    "timeout": "\u23f0",
    "suspicious": "\U0001f914",
    "skipped": "\U0001f507",
    "caught by type check": "\U0001f9d9",
    "check was interrupted by user": "\U0001f6d1",
    "not checked": "?",
    "killed": "\U0001f389",
    "killed_by_infinite_loop": "\U0001f300",  # cyclone — IL classification (Issue #71)
    "segfault": "\U0001f4a5",
}

# Plain dict (issue #132 / 360°-C6) — readers fall back to the suspicious
# emoji via ``.get(code, emoji_by_status["suspicious"])``.
exit_code_to_emoji: dict[int | None, str] = {
    code: emoji_by_status.get(status, "") for code, status in status_by_exit_code.items()
}

# Internal exit codes used by mutmut-win for non-pytest results.
EXIT_CODE_TIMEOUT: int = 36
EXIT_CODE_SKIPPED: int = 34
EXIT_CODE_TYPE_CHECK: int = 37
EXIT_CODE_INFINITE_LOOP: int = 38  # Issue #71 — triple-check IL classifier verdict
EXIT_CODE_NO_TESTS: int = 33  # Issue #106 — mapped-but-uncovered mutant, never dispatched
