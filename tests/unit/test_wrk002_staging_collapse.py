"""WRK-002: a worker dying at interpreter bootstrap aborts cleanly, never hangs.

External QA (v2.19.0) found that a crashing ``sitecustomize`` / ``.pth`` /
site-packages wedged the staging pool. Generation now runs below a contained
supervisor and translates every diagnosed supervisor failure into a clean
``OrchestratorError``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import OrchestratorError
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process import (
    GenerationNoProgressTimeoutError,
    GenerationSupervisorCrashedError,
)

if TYPE_CHECKING:
    from pathlib import Path

# The exact diagnosed-abort message is the WRK-002 deliverable (it tells the user
# their interpreter environment is wedged). Pinned verbatim so a mutation to any
# segment — or to the ``raise`` itself — fails this test.
_EXPECTED_MSG = "mutant generation supervisor failed: simulated worker death"


def test_staging_pool_collapse_aborts_with_clean_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("def f(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(
        "from src.mod import f\n\n\ndef test_f() -> None:\n    assert f(1, 2) == 3\n",
        encoding="utf-8",
    )

    def crash(*_args: object, **_kwargs: object) -> list[object]:
        raise GenerationSupervisorCrashedError("simulated worker death")

    monkeypatch.setattr("mutmut_win.process.run_generation_supervised", crash)

    cfg = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"], max_children=2)
    orch = MutationOrchestrator(cfg)

    with pytest.raises(OrchestratorError) as exc_info:
        orch._generate_mutants()
    assert str(exc_info.value) == _EXPECTED_MSG


def test_staging_pool_no_progress_is_bounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    def timeout(*_args: object, **_kwargs: object) -> list[object]:
        raise GenerationNoProgressTimeoutError("made no progress for 0.01s")

    monkeypatch.setattr("mutmut_win.process.run_generation_supervised", timeout)

    cfg = MutmutConfig(
        paths_to_mutate=["src/"],
        tests_dir=["tests/"],
        max_children=2,
        generation_timeout=0.01,
    )

    with pytest.raises(OrchestratorError, match=r"made no progress for 0\.01s"):
        MutationOrchestrator(cfg)._generate_mutants()
