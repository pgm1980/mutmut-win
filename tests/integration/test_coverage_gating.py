"""End-to-end test for the reactivated coverage gating (Issue #95).

Drives the REAL chain — `coverage run -m pytest` as a subprocess inside a
mutants tree, parent-side data-file loading, normcase keying, and the
MutationVisitor's covered-lines filter — against a tiny project with one
covered and one never-called function.  Spike-verified design
(`_issues/spike_coverage_bridge.py`); this is the regression pin.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from mutmut_win.code_coverage import gather_coverage, get_covered_lines_for_file
from mutmut_win.config import MutmutConfig
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_MODULE_SOURCE = textwrap.dedent(
    """
    def covered(value):
        return value + 1


    def never_called(value):
        return value - 1
    """
).lstrip()

_TEST_SOURCE = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, "src")
    from pkg.mod import covered


    def test_covered():
        assert covered(1) == 2
    """
).lstrip()


def _build_mutants_tree(tmp_path: Path) -> None:
    files = {
        "mutants/src/pkg/__init__.py": "",
        "mutants/src/pkg/mod.py": _MODULE_SOURCE,
        "mutants/tests/test_mod.py": _TEST_SOURCE,
    }
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


class TestCoverageGatingEndToEnd:
    def test_real_subprocess_coverage_filters_uncovered_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        runner = PytestRunner(MutmutConfig(tests_dir=["tests"]))

        covered_map = gather_coverage(runner, ["src/pkg/mod.py"])
        file_covered = get_covered_lines_for_file("src/pkg/mod.py", covered_map)

        assert file_covered is not None
        assert 2 in file_covered  # body of covered()
        assert 6 not in file_covered  # body of never_called() was never run

        # The actual value of the feature: mutants are only generated on
        # covered lines.
        _mutated, gated_names = mutate_file_contents("src/pkg/mod.py", _MODULE_SOURCE, file_covered)
        _mutated_all, all_names = mutate_file_contents("src/pkg/mod.py", _MODULE_SOURCE, None)

        assert gated_names, "covered() mutants must survive the gate"
        assert len(gated_names) < len(all_names), (
            "never_called() mutants must be filtered out by the coverage gate"
        )
        assert all("never_called" not in name for name in gated_names)
