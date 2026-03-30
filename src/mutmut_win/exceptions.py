"""Custom exception hierarchy for mutmut-win."""


class MutmutWinError(Exception):
    """Base exception for all mutmut-win errors."""


class ConfigError(MutmutWinError):
    """Error in configuration loading or validation."""


class InvalidConfigValueError(ConfigError):
    """A specific configuration value is invalid."""


class WorkerError(MutmutWinError):
    """Error related to worker process management."""


class WorkerCrashError(WorkerError):
    """A worker process crashed unexpectedly."""


class WorkerInitError(WorkerError):
    """A worker process failed to initialize."""


class OrchestratorError(MutmutWinError):
    """Error in the mutation testing orchestration."""


class CleanTestFailedError(OrchestratorError):
    """The clean test run (no mutations) failed."""


class ForcedFailError(OrchestratorError):
    """The forced-fail validation test failed."""


class MutationError(MutmutWinError):
    """Error during mutation generation."""


class MutationParseError(MutationError):
    """Failed to parse a source file for mutation."""


class MutmutProgrammaticFailException(MutmutWinError):  # noqa: N818 — name hardcoded in trampoline_impl
    """Raised by the trampoline when MUTANT_UNDER_TEST == 'fail'."""


class BadTestExecutionCommandsException(MutmutWinError):  # noqa: N818 — name matches mutmut 3.5.0 public API
    """Raised when pytest exits with code 4 (usage error / bad CLI args).

    Args:
        pytest_args: The pytest argument list that caused the failure.
    """

    def __init__(self, pytest_args: list[str]) -> None:
        msg = (
            f"Failed to run pytest with args: {pytest_args}. "
            "If your config sets debug=true, the original pytest error should be above."
        )
        super().__init__(msg)


class InvalidGeneratedSyntaxException(MutmutWinError):  # noqa: N818 — name matches mutmut 3.5.0 public API
    """Raised when a generated mutant file contains invalid Python syntax.

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
