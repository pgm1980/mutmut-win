"""Both incremental Git subprocess boundaries preserve usage diagnostics."""

from __future__ import annotations

from io import StringIO

import pytest
from pydantic import BaseModel, ConfigDict

from mutmut_win.cli import _git_changed_names, _resolve_since_commit


class _ErrorReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str
    exit_code: int


@pytest.mark.parametrize("operation", ["resolve", "diff"])
@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError, OSError])
def test_spawn_oserror_uses_incremental_error_contract(
    monkeypatch: pytest.MonkeyPatch, operation: str, error: type[OSError]
) -> None:
    """A missing or unusable Git cannot escape either subprocess boundary."""

    def fail(*_args: object, **_kwargs: object) -> None:
        raise error("S3 injected Git spawn failure")

    monkeypatch.setattr("subprocess.run", fail)
    output = StringIO()
    invoke = _resolve_since_commit if operation == "resolve" else _git_changed_names
    reference = "HEAD" if operation == "resolve" else "a" * 40
    with pytest.raises(SystemExit) as raised:
        invoke(reference, json_stdout=output)
    assert raised.value.code == 2
    payload = _ErrorReport.model_validate_json(output.getvalue())
    assert payload.exit_code == 2
    assert "git" in payload.error.lower()
    assert "S3 injected Git spawn failure" in payload.error
