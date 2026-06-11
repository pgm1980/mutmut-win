"""End-to-end test for the type-check filter with a REAL mypy run (#93).

A3-CM-002 verified that the filter's matching had ZERO test coverage and
never produced a real hit: checker paths and task names disagreed on their
form, so real type-breaking mutants were missed while phantom matches could
inflate the score.  This test drives the actual chain — mypy --output=json
inside mutants/, path normalization, CST-based line matching, task
intersection — against a hand-built but representation-faithful mutants
tree, and asserts the EXACT caught set.
"""

from __future__ import annotations

import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

from mutmut_win.models import MutationTask
from mutmut_win.orchestrator import _filter_with_type_checker

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]

pytest.importorskip("mypy", reason="mypy not installed in the test environment")

#: A trampolined module the way file_setup writes it into mutants/:
#: mutant 1 introduces a type error (str + int), mutant 2 is type-clean.
_MUTATED_MODULE = textwrap.dedent(
    '''
    def x_join__mutmut_orig(value: str) -> str:
        return value + "!"


    def x_join__mutmut_1(value: str) -> str:
        return value + 1


    def x_join__mutmut_2(value: str) -> str:
        return value + "?"
    '''
).lstrip()


def _build_mutants_tree(tmp_path: Path) -> None:
    pkg = tmp_path / "mutants" / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text(_MUTATED_MODULE, encoding="utf-8")


_MYPY_CMD = [sys.executable, "-m", "mypy", "--output=json", "src"]


class TestTypeCheckFilterEndToEnd:
    def test_real_mypy_catches_exactly_the_type_breaking_mutant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        tasks = [
            MutationTask(mutant_name="pkg.mod.x_join__mutmut_1"),
            MutationTask(mutant_name="pkg.mod.x_join__mutmut_2"),
        ]

        remaining, caught = _filter_with_type_checker(tasks, {}, _MYPY_CMD)

        assert caught == {"pkg.mod.x_join__mutmut_1"}, (
            f"Expected exactly the type-breaking mutant to be caught, got {caught!r}. "
            f"An empty set means the path/name matching is broken again (A3-CM-002)."
        )
        assert [t.mutant_name for t in remaining] == ["pkg.mod.x_join__mutmut_2"]

    def test_subset_runs_never_count_foreign_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-OS-009: the caught set used to contain EVERY mutant the checker
        # flagged — even ones not part of this (filtered) run, inflating
        # subset scores.
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        subset = [MutationTask(mutant_name="pkg.mod.x_join__mutmut_2")]

        remaining, caught = _filter_with_type_checker(subset, {}, _MYPY_CMD)

        assert caught == set()  # mutmut_1 is flagged by mypy but NOT in this run
        assert [t.mutant_name for t in remaining] == ["pkg.mod.x_join__mutmut_2"]
