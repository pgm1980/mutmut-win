"""M-062: transient basis-observation failures must not read as drift.

A sharing-locked input file, a half-written tree, or any other transiently
unobservable input previously collapsed into the drift verdicts ("inputs
changed"), aborting otherwise valid runs with a wrong diagnosis.  These
tests pin the three-part contract:

* ``stats._hash_context_file`` retries only transient Windows sharing
  violations (winerror 32) on open and keeps the hash stream identical.
* ``_validate_staging_unchanged`` and ``_stable_run_basis_evidence``
  distinguish "could not be completely observed" (bounded re-observation,
  honest message) from real drift (unchanged message, terminal).
* The CLI export path separates asymmetric incompleteness from drift while
  keeping the existing symmetric-incomplete message.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import mutmut_win.cli as cli_module
import mutmut_win.orchestrator as orchestrator_module
import mutmut_win.stats as stats_module
from mutmut_win.cli import _stable_live_basis
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import MutmutWinError, OrchestratorError
from mutmut_win.models import MutationRunResult
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.stats import RunBasisEvidence, _hash_context_file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evidence(
    digest: str,
    *,
    complete: bool = True,
    core_digest: str | None = "core",
    core_complete: bool = True,
) -> RunBasisEvidence:
    return RunBasisEvidence(
        digest=digest,
        complete=complete,
        core_digest=core_digest,
        core_complete=core_complete,
    )


def _fail_first_opens(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
    failures: int,
    winerror: int,
) -> dict[str, int]:
    """Make ``Path.open`` fail for ``target`` the first ``failures`` times."""

    real_open = Path.open
    state = {"attempts": 0}

    def flaky_open(self: Path, mode: str, *args: object, **kwargs: object) -> object:
        if self == target and mode == "rb":
            state["attempts"] += 1
            if state["attempts"] <= failures:
                raise OSError(None, "locked", str(self), winerror)
        return real_open(self, mode, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", flaky_open)
    return state


def _orchestrator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MutationOrchestrator:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    config = MutmutConfig(paths_to_mutate=["src/mod.py"])
    return MutationOrchestrator(config)


# ---------------------------------------------------------------------------
# stats._hash_context_file: bounded open retry for winerror 32
# ---------------------------------------------------------------------------


class TestContextOpenRetry:
    def test_transient_sharing_violation_is_retried_and_hash_matches(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "input.py"
        target.write_bytes(b"payload-bytes")

        reference = hashlib.sha256()
        assert _hash_context_file(reference, target, label="x", seen=set())

        monkeypatch.setattr(stats_module, "_CONTEXT_OPEN_RETRY_DELAYS", (0.0, 0.0, 0.0))
        _fail_first_opens(monkeypatch, target, failures=2, winerror=32)

        disturbed = hashlib.sha256()
        ok = _hash_context_file(disturbed, target, label="x", seen=set())

        assert ok is True
        assert disturbed.hexdigest() == reference.hexdigest()

    def test_persistent_sharing_violation_stays_unreadable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "input.py"
        target.write_bytes(b"payload-bytes")
        monkeypatch.setattr(stats_module, "_CONTEXT_OPEN_RETRY_DELAYS", (0.0, 0.0, 0.0))
        _fail_first_opens(monkeypatch, target, failures=99, winerror=32)

        hasher = hashlib.sha256()
        ok = _hash_context_file(hasher, target, label="x", seen=set())

        assert ok is False

    def test_access_denied_is_not_retried(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "input.py"
        target.write_bytes(b"payload-bytes")
        monkeypatch.setattr(stats_module, "_CONTEXT_OPEN_RETRY_DELAYS", (0.0, 0.0, 0.0))
        state = _fail_first_opens(monkeypatch, target, failures=99, winerror=5)

        hasher = hashlib.sha256()
        ok = _hash_context_file(hasher, target, label="x", seen=set())

        assert ok is False
        assert state["attempts"] == 1


# ---------------------------------------------------------------------------
# orchestrator._validate_staging_unchanged
# ---------------------------------------------------------------------------


class TestValidateStagingUnchanged:
    def test_incomplete_staging_reports_unobservable_not_changed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            orchestrator_module,
            "build_staging_context_evidence",
            lambda: _evidence("d" * 64, complete=False, core_complete=False),
        )
        with pytest.raises(OrchestratorError, match="could not be completely observed"):
            orchestrator_module._validate_staging_unchanged(_evidence("d" * 64), {})

    def test_transient_staging_incompleteness_remeasures_then_accepts(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(orchestrator_module, "_STAGING_REOBSERVE_DELAYS", (0.0,))
        expected = _evidence("d" * 64)
        sequence = [
            _evidence("d" * 64, complete=False),
            expected,
        ]
        calls = iter(sequence)
        monkeypatch.setattr(
            orchestrator_module,
            "build_staging_context_evidence",
            lambda: next(calls),
        )
        orchestrator_module._validate_staging_unchanged(expected, {})


# ---------------------------------------------------------------------------
# orchestrator._stable_run_basis_evidence
# ---------------------------------------------------------------------------


class TestStableRunBasisEvidence:
    def _script(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sequence: list[RunBasisEvidence],
    ) -> None:
        monkeypatch.setattr(
            orchestrator_module,
            "_BASIS_REOBSERVE_DELAYS",
            (0.0,) * (len(sequence) - 2) if len(sequence) > 2 else (),
        )
        calls = iter(sequence)
        monkeypatch.setattr(
            orchestrator_module,
            "build_run_basis_evidence",
            lambda *_args, **_kwargs: next(calls),
        )

    def test_transient_incomplete_pair_converges(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        orchestrator = _orchestrator(tmp_path, monkeypatch)
        complete = _evidence("a" * 64)
        incomplete = _evidence("a" * 64, complete=False, core_complete=False)
        self._script(monkeypatch, [complete, incomplete, complete, complete])

        assert orchestrator._stable_run_basis_evidence() == complete

    def test_persistently_unstable_incomplete_raises_unobservable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        orchestrator = _orchestrator(tmp_path, monkeypatch)
        self._script(
            monkeypatch,
            [
                _evidence("a" * 64),
                _evidence("b" * 64, complete=False, core_complete=False),
                _evidence("c" * 64, complete=False, core_complete=False),
                _evidence("d" * 64, complete=False, core_complete=False),
            ],
        )
        with pytest.raises(OrchestratorError, match="could not be completely observed"):
            orchestrator._stable_run_basis_evidence()

    def test_complete_drift_keeps_drift_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        orchestrator = _orchestrator(tmp_path, monkeypatch)
        self._script(monkeypatch, [_evidence("a" * 64), _evidence("b" * 64, core_digest="other")])
        with pytest.raises(OrchestratorError, match="was being fingerprinted"):
            orchestrator._stable_run_basis_evidence()

    def test_ambient_change_keeps_diagnostic_degradation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        orchestrator = _orchestrator(tmp_path, monkeypatch)
        self._script(
            monkeypatch,
            [
                _evidence("a" * 64, core_digest="same"),
                _evidence("b" * 64, core_digest="same"),
            ],
        )
        degraded = orchestrator._stable_run_basis_evidence()
        assert degraded.complete is False
        assert degraded.core_complete is True


# ---------------------------------------------------------------------------
# End-of-run comparison message
# ---------------------------------------------------------------------------


class TestEndComparisonMessage:
    def test_unobservable_end_basis_fails_with_honest_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        orchestrator = _orchestrator(tmp_path, monkeypatch)
        start = _evidence("a" * 64)
        end = _evidence("a" * 64, complete=True, core_digest="core", core_complete=False)
        sequence = [start, end]
        calls = iter(sequence)
        monkeypatch.setattr(
            orchestrator,
            "_stable_run_basis_evidence",
            lambda: next(calls),
        )
        monkeypatch.setattr(orchestrator, "_recover_abandoned_run", lambda: None)

        def fake_pipeline() -> MutationRunResult:
            orchestrator._start_current_run([])
            return MutationRunResult(total_mutants=1, killed=1)

        monkeypatch.setattr(orchestrator, "_run_pipeline", fake_pipeline)

        with pytest.raises(OrchestratorError, match="could not be completely observed"):
            orchestrator._run_with_identity()


# ---------------------------------------------------------------------------
# cli._stable_live_basis
# ---------------------------------------------------------------------------


class TestStableLiveBasis:
    def test_asymmetric_incomplete_live_basis_reports_unobservable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["src/mod.py"])
        calls = iter(
            [
                _evidence("a" * 64),
                _evidence("a" * 64, complete=False, core_complete=False),
            ]
        )
        monkeypatch.setattr(
            cli_module,
            "build_run_basis_evidence",
            lambda *_args, **_kwargs: next(calls),
        )
        with pytest.raises(MutmutWinError, match="could not be completely observed"):
            _stable_live_basis(config, tmp_path / "unused.db")

    def test_symmetric_incomplete_live_basis_keeps_generic_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["src/mod.py"])
        incomplete = _evidence("a" * 64, complete=False, core_complete=False)
        calls = iter([incomplete, incomplete])
        monkeypatch.setattr(
            cli_module,
            "build_run_basis_evidence",
            lambda *_args, **_kwargs: next(calls),
        )
        with pytest.raises(MutmutWinError, match="cannot be fingerprinted"):
            _stable_live_basis(config, tmp_path / "unused.db")
