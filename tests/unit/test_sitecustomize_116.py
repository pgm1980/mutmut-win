"""Issue #116 (audit A2-RN-010 + A2-RN-011): sitecustomize hygiene.

RN-010 — ``_mutants_env`` (an env GETTER) wrote ``sitecustomize.py`` as
a side effect, with no injectable target — unit tests touching the
getter left real artifacts in the repo (observed live in the Sprint-32
dogfooding pilot). The write is now an explicit, injectable setup step
(``write_pth_blocker``) the orchestrator runs once per run.

RN-011 — the generated blocker compared ``sys.path`` entries by exact
string: case variants or symlinked forms of the real ``src/`` shadowed
the staged tree anyway. The comparison is now
``normcase(realpath(...))`` on both sides.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()
    (tmp_path / "src").mkdir()


def _completed(returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    return proc


# ---------------------------------------------------------------------------
# RN-010 — the env getter writes nothing
# ---------------------------------------------------------------------------


class TestEnvGetterIsPure:
    def test_mutants_env_writes_no_files(self, tmp_path: Path) -> None:
        runner = PytestRunner(MutmutConfig())
        runner._mutants_env()
        assert not (tmp_path / "mutants" / "sitecustomize.py").exists()

    def test_phase_runs_do_not_write_the_blocker(self, tmp_path: Path) -> None:
        """Phases consume the env — the blocker write is the orchestrator's
        explicit setup step, not a phase side effect."""
        runner = PytestRunner(MutmutConfig())
        with patch("subprocess.run", return_value=_completed(0)):
            runner.run_clean_test()
        assert not (tmp_path / "mutants" / "sitecustomize.py").exists()


class TestExplicitBlockerStep:
    def test_write_pth_blocker_writes_the_file(self, tmp_path: Path) -> None:
        runner = PytestRunner(MutmutConfig())
        runner.write_pth_blocker()
        assert (tmp_path / "mutants" / "sitecustomize.py").exists()

    def test_target_directory_is_injectable(self, tmp_path: Path) -> None:
        staging = tmp_path / "elsewhere"
        staging.mkdir()
        runner = PytestRunner(MutmutConfig())
        runner.write_pth_blocker(staging)
        assert (staging / "sitecustomize.py").exists()
        assert not (tmp_path / "mutants" / "sitecustomize.py").exists()

    def test_no_real_source_dirs_means_no_blocker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bare = tmp_path / "bare"
        (bare / "mutants").mkdir(parents=True)
        monkeypatch.chdir(bare)
        runner = PytestRunner(MutmutConfig())
        runner.write_pth_blocker()
        assert not (bare / "mutants" / "sitecustomize.py").exists()

    def test_orchestrator_runs_the_setup_step_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src" / "target.py").parent.mkdir(exist_ok=True)
        (tmp_path / "src" / "target.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8"
        )
        runner = MagicMock()
        runner.run_clean_test.return_value = 0
        runner.run_stats.return_value = None
        runner.collect_tests.return_value = []
        runner.run_forced_fail.return_value = 1
        runner.last_forced_fail_attributed = True
        executor = MagicMock()
        executor.get_events.return_value = iter([])
        cfg = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        orch.run()
        runner.write_pth_blocker.assert_called_once()


# ---------------------------------------------------------------------------
# RN-011 — normcase/realpath comparison
# ---------------------------------------------------------------------------


class TestBlockerNormalisation:
    def _generated_blocker(self, tmp_path: Path) -> str:
        runner = PytestRunner(MutmutConfig())
        runner.write_pth_blocker()
        return (tmp_path / "mutants" / "sitecustomize.py").read_text(encoding="utf-8")

    def test_case_variant_of_real_src_is_removed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blocker = self._generated_blocker(tmp_path)
        real_src = tmp_path / "src"
        case_variant = str(real_src).upper() if sys.platform == "win32" else str(real_src)
        keep = str(tmp_path / "mutants" / "src")
        monkeypatch.setattr(sys, "path", [case_variant, keep])
        exec(blocker, {"__name__": "sitecustomize"})  # noqa: S102  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected — executing our own generated blocker IS the test purpose
        assert keep in sys.path
        assert case_variant not in sys.path

    def test_unrelated_entries_survive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blocker = self._generated_blocker(tmp_path)
        unrelated = str(tmp_path / "lib" / "site-packages")
        monkeypatch.setattr(sys, "path", [unrelated])
        exec(blocker, {"__name__": "sitecustomize"})  # noqa: S102  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected — executing our own generated blocker IS the test purpose
        assert sys.path == [unrelated]
