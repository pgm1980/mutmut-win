"""Constants for mutmut-win: exit code mappings and status definitions."""

#: Environment variable read by the trampoline to select the mutant under
#: test. Single source of truth (issue #110 / A4-QX-019) — runner.py and
#: process/worker.py re-export it; the literal inside the trampoline
#: TEMPLATE stays standalone by design (the generated artifact must not
#: import mutmut_win for the env read) and is pinned against this value.
MUTANT_ENV_VAR: str = "MUTANT_UNDER_TEST"

#: Minimum pytest version in the TARGET venv (issue #125 / 360°-A2). The
#: worker hands per-mutant tests to pytest via the ``@argfile`` syntax — the
#: only transfer path by design (no dual code paths, no 32k-limit
#: thresholds) — and that syntax exists since pytest 8.2 ("Added in
#: version 8.2"). Single source of truth: the orchestrator guard enforces
#: it at run start, the pyproject dependency floor encodes it for the
#: resolver, and a pin test keeps both in sync (the #110 pattern).
MINIMUM_PYTEST_VERSION: tuple[int, int] = (8, 2)

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
# Windows, kept for WSL/Linux CI. Windows crashes surface as the unsigned
# DWORD form of NTSTATUS codes instead.

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
