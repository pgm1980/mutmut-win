"""Custom exception hierarchy for mutmut-win."""


class MutmutWinError(Exception):
    """Base exception for all mutmut-win errors."""


class ConfigError(MutmutWinError):
    """Error in configuration loading or validation."""


class StagingNamespaceCollisionError(ConfigError):
    """A live project input collides with a mutmut-win-owned staging path.

    The source/configuration is valid Python, but its planned mirror target
    would be overwritten by mutation metadata, pytest guards, or other
    run-control artifacts.  The collision is therefore rejected before any
    cache or staging mutation instead of silently testing different bytes.
    """


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


class PytestBoundaryError(OrchestratorError):
    """The frozen pytest config/root/test-location boundary is invalid or drifted."""


class CleanTestFailedError(OrchestratorError):
    """The clean test run (no mutations) failed."""


class ForcedFailError(OrchestratorError):
    """The forced-fail validation test failed."""


class UnsupportedPytestVersionError(OrchestratorError):
    """The target venv's pytest is outside the validated execution range.

    Producer: the orchestrator's run-start guard (issue #125 / 360°-A2).
    Workers require pytest >= 8.2 for ``@argfile`` and the frozen config
    boundary mirrors only pytest majors 8 and 9. The guard fails before
    staging/mutation so an incompatible dependency cannot produce false data.
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
    """The staged or source bytes do not match their recorded hashes.

    Producers: ``mutant_diff._read_source_bytes_matching_staging`` (source
    SHA-256 mismatch or missing hash), ``file_setup.read_verified_generated_bytes``
    (staged bytes mismatch the generated hash), ``mutant_diff._public_mutant_function``
    (staged original body differs from the source body), and the
    compare-and-swap publication in ``mutant_diff.apply_mutant`` (source
    changed while apply was running — nothing is overwritten, M-005).
    All producers bind byte content, never file timestamps (issue #123 /
    external QA CLI-003 - the refusal used to escape as a raw
    ``RuntimeError`` traceback past the #114 domain-error rendering).
    """


class UnsafeStagingError(MutmutWinError):
    """The staging destination resolves outside its canonical workspace tree.

    Producer: staging mirror and generation writes reject a ``mutants`` root,
    parent directory, or file path redirected through a symlink/junction.  A
    stale or hostile staging tree must never turn a refresh into an external
    write.
    """


class UnsafeWorkspaceStateError(MutmutWinError):
    """A fixed workspace state root is redirected outside the workspace.

    The CLI validates ``mutants/`` and ``.mutmut-cache/`` before deriving a
    lock path or touching persistent state.  A symlink, Junction, or otherwise
    redirected root must never turn a local run/apply/export operation into an
    external filesystem or SQLite write.
    """


class CorruptCacheError(MutmutWinError):
    """The ``.mutmut-cache/`` SQLite database is corrupt or unreadable.

    Reserved for genuinely corrupt or invalid persisted cache content only:
    garbage / truncated DB bytes (SQLITE_CORRUPT, SQLITE_NOTADB) and rows that
    fail schema or domain validation. Recover with ``run --force``, which
    deletes the cache before rebuilding it.

    Producer: ``db.create_db`` (and therefore every reader via
    ``db.load_results``) wraps ``sqlite3.DatabaseError`` — a garbage / truncated
    DB file used to escape as a raw traceback from ``run`` / ``results`` /
    ``export-cicd-stats`` (external QA CACHE-001). Mirrors the domain-error
    contract of the other state errors (e.g. :class:`StaleStagingError`): a clean
    message + a defined exit code, never a traceback.
    """


class CacheEnvironmentError(MutmutWinError):
    """The cache database could not be read or written because of its environment.

    Producer: ``db._raise_database_error`` for SQLite base codes that describe
    the surrounding system rather than the persisted bytes — SQLITE_READONLY
    (read-only file or directory), SQLITE_IOERR (I/O error), SQLITE_FULL
    (disk full), SQLITE_CANTOPEN (path unopenable), plus SQLITE_PERM and
    SQLITE_NOLFS on the same grounds (M-037 / issue #164).

    Distinct from :class:`CorruptCacheError`: the cache is NOT known to be
    corrupt here, so the message deliberately gives recovery guidance
    (read-only state, disk space, antivirus/backup interference) and never
    recommends deleting ``.mutmut-cache/`` or re-running with ``--force`` —
    that would destroy possibly intact, reusable verdicts. Extended
    SQLITE_IOERR codes can also surface real damage (e.g.
    SQLITE_IOERR_CORRUPTFS); classifying them as environment errors is the
    fail-safe direction: the run still aborts with exit 1, it just never
    advises deleting a possibly intact cache.
    """


class AmbiguousMutantNameError(MutmutWinError):
    """A mutant name pattern matched more than one mutant.

    Producer: ``mutant_diff.resolve_mutant`` — ``show``/``apply`` accept
    glob patterns but require a UNIQUE match; the error lists the
    candidates (issue #115 / A4-UI-012). ``run`` deliberately accepts
    multi-matches (filtering many mutants is its job).
    """


class ProcessContainmentError(MutmutWinError):
    """A subprocess could not be placed inside a reliable process boundary."""


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


class MutationSurfaceDegradedWarning(SyntaxWarning):
    """A file could not be mutated; the mutation surface is incomplete.

    Producer: ``file_setup.create_mutants_for_file`` when LibCST cannot parse
    the source (``unsupported_source_syntax``), rejects the syntax tree
    (``cst_validation_error``), or the generated mutant module does not
    compile (``generated_code_invalid``).  The file is staged unmutated
    (issue #78 safety net) and excluded from the mutation surface, so
    ``--min-score`` and CI/CD export are revoked for the run (M-003).

    Function-granular skips (U+01C1 mangling, trampoline collisions) keep
    raising plain ``SyntaxWarning`` — they narrow individual functions, not
    the file-level surface.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(reason, message)
        self.reason = reason
        self.detail = message

    def __str__(self) -> str:
        return self.detail
