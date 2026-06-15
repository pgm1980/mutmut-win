"""WRK-002: a worker dying at interpreter bootstrap aborts cleanly, never hangs.

External QA (v2.19.0) found that a crashing ``sitecustomize`` / ``.pth`` /
site-packages (``os._exit`` before the multiprocessing child connects) wedged
the STAGING pool: ``multiprocessing.Pool.imap_unordered`` has no broken-worker
detection, so it blocked the whole run forever (>80s, no abort). The staging
pool is now a ``concurrent.futures.ProcessPoolExecutor`` whose management thread
raises ``BrokenProcessPool``; ``_generate_mutants`` turns that into a clean
``OrchestratorError`` (rendered to exit 1 by the run command).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import OrchestratorError
from mutmut_win.orchestrator import MutationOrchestrator

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# The exact diagnosed-abort message is the WRK-002 deliverable (it tells the user
# their interpreter environment is wedged). Pinned verbatim so a mutation to any
# segment — or to the ``raise`` itself — fails this test.
_EXPECTED_MSG = (
    "worker pool collapsed during mutant generation — workers are "
    "dying at interpreter startup (a crashing sitecustomize/.pth/"
    "site-packages wedges every spawn). Aborting the run."
)


def _raise_on_iteration() -> Iterator[object]:
    """Lazy like ``ProcessPoolExecutor.map``: raise only while the result is consumed.

    A real ``ProcessPoolExecutor.map`` returns immediately and surfaces
    ``BrokenProcessPool`` as the caller iterates the result. The production code
    therefore wraps the call in ``list(...)`` INSIDE the ``try`` so the failure
    lands in the ``except``'s reach; an eager mock would let that ``list(...)``
    look optional. Raising on iteration pins it as load-bearing.
    """
    from concurrent.futures.process import BrokenProcessPool

    raise BrokenProcessPool("simulated worker death during interpreter bootstrap")
    yield  # unreachable: present only so this function compiles to a generator


class _BrokenPool:
    """Stand-in for ProcessPoolExecutor whose workers die during bootstrap."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> _BrokenPool:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def map(self, *_args: object, **_kwargs: object) -> Iterator[object]:
        return _raise_on_iteration()


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

    # The parallel staging branch (max_children > 1) must use ProcessPoolExecutor;
    # a BrokenProcessPool from it becomes a clean OrchestratorError, not a hang.
    monkeypatch.setattr("concurrent.futures.ProcessPoolExecutor", _BrokenPool)

    cfg = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"], max_children=2)
    orch = MutationOrchestrator(cfg)

    with pytest.raises(OrchestratorError) as exc_info:
        orch._generate_mutants()
    assert str(exc_info.value) == _EXPECTED_MSG
