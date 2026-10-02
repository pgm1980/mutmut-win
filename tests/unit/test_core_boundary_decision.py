"""Core-fingerprint import boundaries as decided (M-061 = B, AP-11 rest).

Decision B confirms the status quo of the terminal core digest: every
effective project import root is bound WITHOUT a gitignore boundary.  The
executed child removes only ``src``/``source`` roots from ``sys.path``
(``SOURCE_ROOT_NAMES``), so import roots such as a flat-layout project root
or an editable install stay importable in place — their ignored-but-readable
bytes must remain terminally classified as project (core) drift.  A gitignore
boundary is permitted only for provably isolated or staged roots and only in
the combined ambient digest (MBR-2026-09-14-01 pruning).

These tests pin the decision.  Re-introducing variant A — a symmetric
``ignore_boundary`` in ``_hash_project_import_core`` or the editable core
walk of ``_installed_distribution_basis`` — must turn them red, as must
removing the ambient boundary from isolated source trees (reverse symmetry).
The sibling cases are pinned elsewhere: ignored runtime trees (a project-
internal ``.venv`` and interpreter prefixes strictly inside the project) in
``test_import_root_gitignore_policy.py`` and
``test_import_root_boundary_prefix.py``; ignored *trees* inside flat and
editable import roots in ``test_stats.py``
(``TestIgnoredImportRootCoreBinding``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import mutmut_win.stats as stats_module
from mutmut_win.config import MutmutConfig
from mutmut_win.constants import SOURCE_ROOT_NAMES
from mutmut_win.stats import build_run_basis_evidence

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _flat_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    ignored: bool,
) -> tuple[Path, MutmutConfig, Path]:
    """Create a flat-layout project whose root is the effective import root.

    ``local_settings.py`` is a top-level module: the child keeps the project
    root on ``sys.path`` (only ``SOURCE_ROOT_NAMES`` entries are removed), so
    the module is importable in place during the run whether or not git
    ignores it.
    """
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "src" / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project / ".gitignore").write_text(
        "local_settings.py\n" if ignored else "unrelated-pattern\n", encoding="utf-8"
    )
    module = project / "local_settings.py"
    module.write_text("FLAT = 1\n", encoding="utf-8")
    monkeypatch.chdir(project)
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    config = MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests"])
    return project, config, module


class TestFlatLayoutImportRootCoreBinding:
    """M-061 = B: a flat-layout import root stays bound without a boundary."""

    def test_ignored_flat_layout_module_stays_bound_in_core_digest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The decision-B pin: ignored but still importable means core-bound.

        A git-ignored top-level module of a flat-layout project root that
        remains on the child's ``sys.path`` must keep hashing into the
        terminal core digest.  Variant A (a symmetric ``ignore_boundary`` in
        ``_hash_project_import_core``) would prune it and turn this red.
        """
        project, config, module = _flat_project(tmp_path, monkeypatch, ignored=True)

        before = build_run_basis_evidence(config, project_root=project)
        module.write_text("FLAT = 2\n", encoding="utf-8")
        after = build_run_basis_evidence(config, project_root=project)

        assert before.core_complete is True
        assert after.core_complete is True
        # The combined ambient digest keeps pruning the ignored module ...
        assert after.digest == before.digest
        # ... while the terminal core deliberately still binds its bytes.
        assert after.core_digest != before.core_digest

    def test_unignored_flat_layout_module_drifts_both_digests(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guard: only the ignore rule makes the difference, nothing else.

        The same layout with the module NOT ignored must drift both digests,
        so the first test pins the gitignore asymmetry — not an unrelated
        stabiliser — and fail-closed source-drift classification is intact.
        """
        project, config, module = _flat_project(tmp_path, monkeypatch, ignored=False)

        before = build_run_basis_evidence(config, project_root=project)
        module.write_text("FLAT = 2\n", encoding="utf-8")
        after = build_run_basis_evidence(config, project_root=project)

        assert before.core_complete is True
        assert after.core_complete is True
        assert after.digest != before.digest
        assert after.core_digest != before.core_digest


class TestIsolatedSourceLayoutAmbientBoundary:
    """Isolated ``src`` roots keep the ambient boundary; the core binds anyway."""

    def test_isolated_src_root_keeps_ambient_boundary_and_core_binding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Boundary only for provably isolated roots, and only in the ambient.

        An editable src-layout install puts ``src`` on the fingerprint-time
        ``sys.path``; the child removes exactly that root (``SOURCE_ROOT_NAMES``)
        and executes the staged copy instead, so the root is isolated for the
        run.  Its ignored artifacts keep gitignore pruning in the combined
        ambient digest, while the core walk still binds them whole — removing
        bytes that merely the parent imports would weaken the terminal
        classification without buying anything.
        """
        project = tmp_path / "project"
        src = project / "src"
        (src / "pkg").mkdir(parents=True)
        (project / "tests").mkdir()
        (src / "pkg" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (project / ".gitignore").write_text("*.log\n", encoding="utf-8")
        artifact = src / "debug.log"
        artifact.write_text("ignored payload v1\n", encoding="utf-8")
        monkeypatch.chdir(project)
        monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
        assert "src" in SOURCE_ROOT_NAMES  # the isolation premise of decision B
        monkeypatch.setattr(stats_module.sys, "path", [str(project), str(src)])
        config = MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests"])

        before = build_run_basis_evidence(config, project_root=project)
        artifact.write_text("ignored payload v2\n", encoding="utf-8")
        after = build_run_basis_evidence(config, project_root=project)

        assert before.core_complete is True
        assert after.core_complete is True
        # Isolated/staged roots keep the gitignore boundary in the ambient
        # digest (a stability property, not a completeness proof) ...
        assert after.digest == before.digest
        # ... while the core still binds the ignored artifact without one.
        assert after.core_digest != before.core_digest
