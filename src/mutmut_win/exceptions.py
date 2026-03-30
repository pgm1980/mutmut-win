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
