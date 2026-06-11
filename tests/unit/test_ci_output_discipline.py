"""Tests for CI output discipline (Issue #103, audit A4-UI-006, A4-QX-003).

With ``--output json`` the stdout stream carried step headers, warnings and
the summary BEFORE the JSON — ``json.loads(stdout)`` failed (the #97 score
field was unreachable for real CI consumers). And emoji output on a
cp1252/redirected console raised UnicodeEncodeError and ABORTED the whole
run; the dev environment masked it via PYTHONUTF8=1.
"""

from __future__ import annotations

import io
import json
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.models import MutationRunResult
from mutmut_win.orchestrator import _ensure_tolerant_stdout, _print_live_progress

if TYPE_CHECKING:
    import pytest


class TestPureJsonStdout:
    def test_json_loads_stdout_works(self) -> None:
        orchestrator = MagicMock()

        def noisy_run() -> MutationRunResult:
            print("Running clean test suite…")
            print("Collecting test timing statistics…")
            return MutationRunResult(total_mutants=2, killed=2)

        orchestrator.run.side_effect = noisy_run
        with (
            patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
            patch("mutmut_win.cli.load_config", return_value=MagicMock(model_copy=MagicMock())),
        ):
            result = CliRunner().invoke(cli, ["run", "--output", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)  # the WHOLE stdout is the JSON
        assert payload["score"] == 100.0
        # The prose still exists — on stderr, where CI logs pick it up.
        assert "clean test suite" in result.stderr


class TestEmojiEncodingSafety:
    def test_progress_line_survives_cp1252_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A4-QX-003: the live progress line prints emoji; on a cp1252 console
        # (the Windows default for redirected output without PYTHONUTF8) the
        # whole run died with UnicodeEncodeError.
        raw = io.BytesIO()
        narrow_stdout = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
        monkeypatch.setattr(sys, "stdout", narrow_stdout)

        _ensure_tolerant_stdout()
        _print_live_progress(1, 2, MutationRunResult(total_mutants=2, killed=1))

        sys.stdout.flush()
        assert b"1/2" in raw.getvalue()  # the line arrived, emoji degraded

    def test_utf8_stdout_is_left_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        raw = io.BytesIO()
        utf8_stdout = io.TextIOWrapper(raw, encoding="utf-8", errors="strict")
        monkeypatch.setattr(sys, "stdout", utf8_stdout)

        _ensure_tolerant_stdout()
        print("\U0001f389")

        sys.stdout.flush()
        assert "\U0001f389".encode() in raw.getvalue()  # emoji intact
