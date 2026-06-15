"""Custom exception hierarchy for mutmut-win."""


class MutmutWinError(Exception):
    """Base exception for all mutmut-win errors."""


class ConfigError(MutmutWinError):
    """Error in configuration loading or validation."""


class InvalidConfigValueError(ConfigError):
    """A specific configuration value failed validation.

    Producer: config loading wraps pydantic validation failures
    (issue #114 / A4-QX-006 — the class used to exist without one).
    """


class WorkerError(MutmutWinError):
    """Error in worker process management or communication.

    Producer: the executor's event loop, for unknown event shapes on the
    queue (issue #114 / A4-QX-006). Worker CRASHES deliberately do NOT
    raise — they are recovered into synthesized task events (Bug #12 /
    issue #80), which is why the former ``WorkerCrashError`` /
    ``WorkerInitError`` classes were removed as unproducible.
    """


class OrchestratorError(MutmutWinError):
    """Error in the mutation testing orchestration."""


class CleanTestFailedError(OrchestratorError):
    """The clean test run (no mutations) failed."""


class ForcedFailError(OrchestratorError):
    """The forced-fail validation test failed."""


class UnsupportedPytestVersionError(OrchestratorError):
    """The pytest in the target venv is too old for the ``@argfile`` hand-off.

    Producer: the orchestrator's run-start guard (issue #125 / 360°-A2).
    Workers pass per-mutant tests via pytest's ``@argfile`` syntax, which
    exists since pytest 8.2 — under an older pytest every covered mutant
    floods into ``suspicious`` (usage error) despite a green clean run.
    The ``pytest>=8.2`` dependency floor is the primary defence; this
    guard catches bypassed resolvers (``pip --no-deps``, hand-patched
    environments) BEFORE any staging or test execution.
    """


class MutationError(MutmutWinError):
    """Error during mutation generation or mutant handling."""


class MutationParseError(MutationError):
    """A source or staged file could not be parsed for mutant handling.

    Producer: the mutant-diff readers behind ``show``/``apply``/``browse``
    (issue #114 / A4-QX-006). The GENERATION side deliberately degrades to
    a warning and copies the file unmutated instead of raising (the
    issue-#78 safety net).
    """


class StaleStagingError(MutmutWinError):
    """The staging is older than the source it was generated from.

    Producer: ``mutant_diff.apply_mutant`` refuses to patch a source file
    that changed after its mutants were generated (issue #123 / external QA
    CLI-003 — the refusal used to escape as a raw ``RuntimeError``
    traceback past the #114 domain-error rendering).
    """


class CorruptCacheError(MutmutWinError):
    """The ``.mutmut-cache/`` SQLite database is corrupt or unreadable.

    Producer: ``db.create_db`` (and therefore every reader via
    ``db.load_results``) wraps ``sqlite3.DatabaseError`` — a garbage / truncated
    DB file used to escape as a raw traceback from ``run`` / ``results`` /
    ``export-cicd-stats`` (external QA CACHE-001). Mirrors the domain-error
    contract of the other state errors (e.g. :class:`StaleStagingError`): a clean
    message + a defined exit code, never a traceback. ``run --force`` recovers by
    deleting ``.mutmut-cache/`` first.
    """


class AmbiguousMutantNameError(MutmutWinError):
    """A mutant name pattern matched more than one mutant.

    Producer: ``mutant_diff.resolve_mutant`` — ``show``/``apply`` accept
    glob patterns but require a UNIQUE match; the error lists the
    candidates (issue #115 / A4-UI-012). ``run`` deliberately accepts
    multi-matches (filtering many mutants is its job).
    """


class TypeCheckCommandError(MutmutWinError):
    """The external type checker failed to run or produced an unusable report.

    Distinct from a checker FINDING (the ``TypeCheckingError`` dataclass in
    ``type_checking``): this is the command itself timing out, exiting with
    a non-finding status, or emitting a report that cannot be parsed
    (issue #114 / A4-QX-023 — these were bare ``Exception`` raises).
    """


class CoverageCollectionError(MutmutWinError):
    """The coverage bridge for ``mutate_only_covered_lines`` failed loudly.

    Carries the issue-#95 design promise: a run whose coverage is invisible
    (subprocess/xdist execution) must abort with an explanation instead of
    silently filtering every mutant (was a bare ``Exception``; issue #114).
    """


class MutmutProgrammaticFailException(MutmutWinError):  # noqa: N818 — name hardcoded in trampoline_impl
    """Raised by the trampoline when MUTANT_UNDER_TEST == 'fail'."""


class BadTestExecutionCommandsException(MutmutWinError):  # noqa: N818 — name matches mutmut 3.5.0 public API
    """Raised when pytest exits with code 4 (usage error / bad CLI args).

    Args:
        pytest_args: The pytest argument list that caused the failure.
    """

    def __init__(self, pytest_args: list[str], detail: str | None = None) -> None:
        msg = (
            f"Failed to run pytest with args: {pytest_args}. "
            "If your config sets debug=true, the original pytest error should be above."
        )
        if detail:
            msg += f"\n{detail}"
        super().__init__(msg)


class InvalidGeneratedSyntaxException(MutmutWinError):  # noqa: N818 — name matches mutmut 3.5.0 public API
    """Raised when a generated mutant file contains invalid Python syntax.

    Deliberately producer-less in mutmut-win (issue #114 / A4-QX-006):
    the issue-#78 safety net validates generated code BEFORE writing and
    degrades to a warning plus the unmutated source instead of raising.
    Kept for mutmut 3.5.0 public-API parity.

    Args:
        file: Path to the file that contains invalid syntax.
    """

    def __init__(self, file: object) -> None:
        msg = (
            f"Mutmut generated invalid python syntax for {file}. "
            "If the original file has valid python syntax, please file an issue "
            "with a minimal reproducible example file."
        )
        super().__init__(msg)
