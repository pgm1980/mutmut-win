"""Tests for mutmut_win.exceptions."""

from mutmut_win.exceptions import (
    BadTestExecutionCommandsException,
    CleanTestFailedError,
    ConfigError,
    CoverageCollectionError,
    ForcedFailError,
    InvalidConfigValueError,
    InvalidGeneratedSyntaxException,
    MutationError,
    MutationParseError,
    MutmutWinError,
    OrchestratorError,
    TypeCheckCommandError,
    WorkerError,
)


class TestExceptionHierarchy:
    def test_base_exception(self) -> None:
        assert issubclass(MutmutWinError, Exception)

    def test_config_errors(self) -> None:
        assert issubclass(ConfigError, MutmutWinError)
        assert issubclass(InvalidConfigValueError, ConfigError)

    def test_worker_errors(self) -> None:
        # WorkerCrashError/WorkerInitError were removed as unproducible —
        # crash recovery is event-based by design (issue #114 / A4-QX-006).
        assert issubclass(WorkerError, MutmutWinError)

    def test_tooling_errors(self) -> None:
        assert issubclass(TypeCheckCommandError, MutmutWinError)
        assert issubclass(CoverageCollectionError, MutmutWinError)

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

    def test_bad_test_execution_commands_exception(self) -> None:
        assert issubclass(BadTestExecutionCommandsException, MutmutWinError)
        exc = BadTestExecutionCommandsException(["pytest", "--bad"])
        msg = str(exc)
        assert "pytest" in msg
        assert "--bad" in msg

    def test_bad_test_execution_commands_exception_detail(self) -> None:
        exc = BadTestExecutionCommandsException(["--bad"], detail="usage: pytest")
        assert "usage: pytest" in str(exc)

    def test_invalid_generated_syntax_exception(self) -> None:
        assert issubclass(InvalidGeneratedSyntaxException, MutmutWinError)
        from pathlib import Path

        exc = InvalidGeneratedSyntaxException(Path("mutants/src/foo.py"))
        msg = str(exc)
        assert "foo.py" in msg

    def test_invalid_generated_syntax_exception_with_string(self) -> None:
        exc = InvalidGeneratedSyntaxException("some/path.py")
        assert "some/path.py" in str(exc)


class TestMutationSurfaceDegradedWarning:
    """M-003 (issue #145): the constructor assigns fields positionally."""

    def test_init_assigns_reason_and_detail(self) -> None:
        from mutmut_win.exceptions import MutationSurfaceDegradedWarning

        warning = MutationSurfaceDegradedWarning("test_reason", "test_message")
        assert warning.reason == "test_reason"
        assert warning.detail == "test_message"
        assert str(warning) == "test_message"
        # super().__init__(reason, message) passes both positionally
        assert warning.args == ("test_reason", "test_message")

    def test_str_returns_detail_not_reason(self) -> None:
        from mutmut_win.exceptions import MutationSurfaceDegradedWarning

        warning = MutationSurfaceDegradedWarning("reason_code", "human readable text")
        assert str(warning) == "human readable text"
        assert str(warning) != "reason_code"
