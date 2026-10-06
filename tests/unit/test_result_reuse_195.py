"""Issue #195 (TM-09): cross-run verdict reuse needs a stable test basis.

A restart of ``mutmut-win run`` with the same tests-dir, the same HEAD and a
warm, unchanged virtual environment must not lose every prior verdict.  The
context fingerprint backing ``tests_fingerprint`` currently changes for
reasons that cannot alter any child verdict (issue #195):

* RC-1: the complete inherited ``os.environ`` is hashed inside the
  distribution basis, so a benign launch difference between two runs (shell
  wrapper, session variable) invalidates every cached verdict.
* RC-2: distribution hashing covers derived ``__pycache__`` artifacts whose
  bytes and presence drift while the venv warms up.
* RC-3: per-file timestamps are hashed, so even a content-identical ``touch``
  invalidates the whole basis.

The contract under test (roadmap W0 fix note): the reuse basis is bound to
the verdict-relevant inputs — tests-dir content, project source, config,
interpreter identity, installed source distributions and the curated set of
environment variables that reach pytest children.  Counter-probes pin the
conservative side: semantic deltas (PYTHONPATH, PYTEST_ADDOPTS, source
edits) must keep invalidating.

The distribution enumeration is faked to one small in-test distribution so
the real ``_installed_distribution_basis`` (including the environment and
runtime-identity hashing under test) runs quickly and hermetically.
"""

from __future__ import annotations

import os
from email.message import Message
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mutmut_win.config import MutmutConfig
from mutmut_win.stats import (
    _build_stats_context_evidence,
    _installed_distribution_basis,
    build_stats_context_fingerprint,
)

# Deliberately outside every curated namespace (python*/pytest*/mutmut_*/
# mutant_*): the kind of session- or wrapper-specific variable that differs
# between two launches of the same unchanged project (issue #195).
BENIGN_VARIABLE = "OPENCODE_SHELL_GENERATION"


class _FakeDistribution:
    """Minimal importlib.metadata.Distribution stand-in over tmp files."""

    def __init__(self, name: str, version: str, location: Path, files: list[str]) -> None:
        self._name = name
        self._version = version
        self._location = location
        self._files = files
        metadata = Message()
        metadata["Name"] = name
        self.metadata = metadata

    @property
    def version(self) -> str:
        return self._version

    @property
    def files(self) -> list[str]:
        return self._files

    def locate_file(self, entry: Any) -> Path:
        return self._location / str(entry)

    def read_text(self, _entry: str) -> str | None:
        """Non-editable distribution: no direct_url.json (None, like the
        real API when the file is absent)."""

        return None


def _make_project(root: Path) -> Path:
    tests = root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    (root / "srcmod.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return root


def _fake_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install one small fake distribution as the entire venv inventory."""

    site = tmp_path / "site-packages"
    pkg = site / "example_pkg"
    (pkg / "__pycache__").mkdir(parents=True, exist_ok=True)
    (pkg / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (pkg / "__pycache__" / "core.cpython-314.pyc").write_bytes(b"derived-artifact-v1")
    distribution = _FakeDistribution(
        "example-pkg",
        "1.0.0",
        site,
        ["example_pkg/core.py", "example_pkg/__pycache__/core.cpython-314.pyc"],
    )
    monkeypatch.setattr(
        "mutmut_win.stats.importlib.metadata.distributions",
        lambda: [distribution],
    )
    # Isolate the unit under test: the effective-import-path classification
    # covers the REAL interpreter environment (editable installs, pytest
    # plugin roots) and is neither fakeable nor the component under test
    # here.  It stays covered by its own suite; stubbing keeps this file's
    # basis fully hashable so reuse-safety reflects the file hashing only.
    monkeypatch.setattr(
        "mutmut_win.stats._hash_effective_import_paths",
        lambda *_args, **_kwargs: True,
    )
    return site


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return _make_project(tmp_path / "project")


@pytest.fixture
def hermetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MutmutConfig:
    _fake_venv(tmp_path, monkeypatch)
    return MutmutConfig(paths_to_mutate=["srcmod.py"], tests_dir=["tests"])


class TestFingerprintStability:
    """RC-1 and RC-3: irrelevant differences must not change the basis."""

    def test_benign_env_delta_keeps_fingerprint(
        self,
        hermetic: MutmutConfig,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(BENIGN_VARIABLE, "run-1")
        first = build_stats_context_fingerprint(hermetic, project_root=project)
        monkeypatch.setenv(BENIGN_VARIABLE, "run-2")
        second = build_stats_context_fingerprint(hermetic, project_root=project)
        assert first == second, (
            "a benign inherited environment difference must not invalidate "
            "the verdict-reuse basis (issue #195 RC-1)"
        )

    def test_mtime_touch_keeps_fingerprint(
        self,
        hermetic: MutmutConfig,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv(BENIGN_VARIABLE, raising=False)
        first = build_stats_context_fingerprint(hermetic, project_root=project)
        # Content-identical timestamp bump: only mtime/ctime move.
        os.utime(project / "srcmod.py")
        second = build_stats_context_fingerprint(hermetic, project_root=project)
        assert first == second, (
            "a content-identical timestamp change must not invalidate the "
            "verdict-reuse basis (issue #195 RC-3)"
        )


class TestFingerprintInvalidation:
    """Counter-probes: semantic deltas must keep invalidating (conservative)."""

    def test_pythonpath_delta_invalidates(
        self,
        hermetic: MutmutConfig,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PYTHONPATH", r"C:\basis-a")
        first = build_stats_context_fingerprint(hermetic, project_root=project)
        monkeypatch.setenv("PYTHONPATH", r"C:\basis-b")
        second = build_stats_context_fingerprint(hermetic, project_root=project)
        assert first != second

    def test_pytest_addopts_delta_invalidates(
        self,
        hermetic: MutmutConfig,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PYTEST_ADDOPTS", "-x")
        first = build_stats_context_fingerprint(hermetic, project_root=project)
        monkeypatch.setenv("PYTEST_ADDOPTS", "-k smoke")
        second = build_stats_context_fingerprint(hermetic, project_root=project)
        assert first != second

    def test_source_edit_invalidates(
        self,
        hermetic: MutmutConfig,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv(BENIGN_VARIABLE, raising=False)
        first = build_stats_context_fingerprint(hermetic, project_root=project)
        (project / "srcmod.py").write_text(
            "def add(a, b):\n    return a + b + 0\n", encoding="utf-8"
        )
        second = build_stats_context_fingerprint(hermetic, project_root=project)
        assert first != second


class TestDistributionBasisStability:
    """RC-2: derived __pycache__ drift must not change the dependency basis."""

    def _digest(self, project_root: Path) -> tuple[str, bool]:
        basis = _installed_distribution_basis(project_root, set())
        return basis.digest, basis.reuse_safe

    def test_pyc_drift_keeps_digest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        site = _fake_venv(tmp_path, monkeypatch)
        project_root = tmp_path / "project"
        project_root.mkdir()
        first_digest, first_safe = self._digest(project_root)
        (site / "example_pkg" / "__pycache__" / "core.cpython-314.pyc").write_bytes(
            b"derived-artifact-v2-rewritten-by-import"
        )
        second_digest, second_safe = self._digest(project_root)
        assert first_safe
        assert second_safe
        assert first_digest == second_digest, (
            "derived __pycache__ drift must not change the dependency basis (issue #195 RC-2)"
        )

    def test_source_change_in_distribution_invalidates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        site = _fake_venv(tmp_path, monkeypatch)
        project_root = tmp_path / "project"
        project_root.mkdir()
        first_digest, first_safe = self._digest(project_root)
        assert first_safe, "fake inventory must stay fully hashable"
        (site / "example_pkg" / "core.py").write_text("VALUE = 2\n", encoding="utf-8")
        second_digest, _ = self._digest(project_root)
        assert first_digest != second_digest


class TestEvidenceObjectStability:
    """The evidence object must stay reuse-safe under benign deltas."""

    def test_benign_env_delta_keeps_reuse_safety(
        self,
        hermetic: MutmutConfig,
        project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(BENIGN_VARIABLE, "run-1")
        first = _build_stats_context_evidence(hermetic, project_root=project)
        monkeypatch.setenv(BENIGN_VARIABLE, "run-2")
        second = _build_stats_context_evidence(hermetic, project_root=project)
        assert first.complete
        assert second.complete
        assert first.fingerprint == second.fingerprint
        assert not first.fingerprint.startswith("no-reuse:")
