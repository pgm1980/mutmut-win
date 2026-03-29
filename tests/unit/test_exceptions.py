"""Tests for mutmut_win.exceptions."""

from mutmut_win.exceptions import (
    CleanTestFailedError,
    ConfigError,
    ForcedFailError,
    InvalidConfigValueError,
    MutationError,
    MutationParseError,
    MutmutWinError,
    OrchestratorError,
    WorkerCrashError,
    WorkerError,
    WorkerInitError,
)


class TestExceptionHierarchy:
    def test_base_exception(self) -> None:
        assert issubclass(MutmutWinError, Exception)

    def test_config_errors(self) -> None:
        assert issubclass(ConfigError, MutmutWinError)
        assert issubclass(InvalidConfigValueError, ConfigError)

    def test_worker_errors(self) -> None:
        assert issubclass(WorkerError, MutmutWinError)
        assert issubclass(WorkerCrashError, WorkerError)
        assert issubclass(WorkerInitError, WorkerError)

    def test_orchestrator_errors(self) -> None:
        assert issubclass(OrchestratorError, MutmutWinError)
        assert issubclass(CleanTestFailedError, OrchestratorError)
        assert issubclass(ForcedFailError, OrchestratorError)

    def test_mutation_errors(self) -> None:
        assert issubclass(MutationError, MutmutWinError)
        assert issubclass(MutationParseError, MutationError)

    def test_exceptions_carry_message(self) -> None:
        err = ConfigError("bad config")
        assert str(err) == "bad config"
