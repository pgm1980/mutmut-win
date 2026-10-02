"""Loader for generated pytest plugin sources (remediation AP-00 / Q-03).

mutmut-win embeds the phase-guard plugin (``_PYTEST_PHASE_GUARD_SOURCE`` in
``mutmut_win.process.worker``) and the stats plugin (inside
``PytestRunner._write_stats_plugin``) as string literals. mutmut-win cannot
semantically mutate string literals (documented gap, handover Q-07), so their
logic must be exercised by loading the exact production source into a fresh
namespace and driving the hooks with synthetic reports.

Loading mirrors a real plugin load: the production writer materializes the
file (``prepare_pytest_phase_guard`` / ``PytestRunner._write_stats_plugin``)
and :func:`runpy.run_path` executes it. The phase-guard source validates the
frozen pytest location boundary from ``os.environ`` *at import time*, so
:func:`phase_guard_plugin` installs the production boundary environment via
``pytest.MonkeyPatch.context()`` for the duration of the block (restored
afterwards, which also satisfies the phase-guard monkeypatch hygiene
convention). A fresh namespace per load makes the one-shot flags
(``_proof_published``) observable for every example, including Hypothesis
examples without function-scoped fixtures.

Consumers are the regression tests for M-008, M-143, M-126 and M-130.
"""

from __future__ import annotations

import contextlib
import runpy
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

__all__ = [
    "load_phase_guard_plugin",
    "load_plugin_source",
    "load_stats_plugin",
    "make_log_report",
    "phase_guard_plugin",
]

_STATS_PLUGIN_FILENAME = "_mutmut_stats_plugin.py"
_MUTMUT_ENV_PREFIX = "MUTMUT_"


def load_plugin_source(source: str, *, scratch_dir: Path, filename: str) -> dict[str, Any]:
    """Materialize ``source`` and load it via ``runpy`` into a fresh namespace.

    Only suitable for sources that do not require production environment
    variables at import time (e.g. the stats plugin); use
    :func:`phase_guard_plugin` for the phase guard.

    Args:
        source: Exact plugin source text (the production string literal).
        scratch_dir: Writable directory for the temporary file. Use a
            ``tmp_path``/``TemporaryDirectory`` location, never the checkout.
        filename: File name to use inside ``scratch_dir``.

    Returns:
        The module namespace dict produced by ``runpy.run_path``.
    """

    target = scratch_dir / filename
    target.write_text(source, encoding="utf-8")
    return dict(runpy.run_path(str(target), run_name=filename.removesuffix(".py")))


def load_phase_guard_plugin(scratch_dir: Path) -> dict[str, Any]:
    """Load the phase-guard plugin source with a minimal valid environment.

    Convenience wrapper for tests that only inspect the namespace; the full
    hook behaviour needs :func:`phase_guard_plugin` because the plugin
    validates ``MUTMUT_*`` environment variables at import time.

    Args:
        scratch_dir: Writable directory used as the fake staging root.

    Returns:
        Namespace containing the generated ``pytest_runtest_logreport`` hook
        and its module-level one-shot flags.
    """

    from mutmut_win.process.worker import _PYTEST_PHASE_GUARD_SOURCE

    with _phase_guard_env(scratch_dir):
        return load_plugin_source(
            _PYTEST_PHASE_GUARD_SOURCE,
            scratch_dir=scratch_dir,
            filename="_mutmut_phase_guard_util_load.py",
        )


@contextlib.contextmanager
def phase_guard_plugin(scratch_dir: Path) -> Iterator[tuple[dict[str, Any], Path, str]]:
    """Load the phase guard with production environment and proof target.

    Materializes the real plugin via ``prepare_pytest_phase_guard`` (into
    ``scratch_dir``), installs every ``MUTMUT_*`` variable of the produced
    child environment into ``os.environ`` for the duration of the block,
    loads the plugin file via ``runpy.run_path`` and yields

    ``(namespace, marker_path, token)``.

    The environment is restored on exit; the marker file stays inside
    ``scratch_dir`` (caller-owned temporary directory).
    """

    with _phase_guard_env(scratch_dir) as (marker_path, token):
        from mutmut_win.process.worker import PYTEST_PHASE_GUARD_PLUGIN

        plugin_file = scratch_dir / f"{PYTEST_PHASE_GUARD_PLUGIN}.py"
        namespace = dict(runpy.run_path(str(plugin_file)))
        yield namespace, marker_path, token


def load_stats_plugin(staging_dir: Path) -> dict[str, Any]:
    """Materialize the production stats plugin and load it freshly.

    The stats plugin source is a local literal inside
    ``PytestRunner._write_stats_plugin``; the only faithful way to obtain it
    is to run the production writer into an empty directory and load the
    emitted ``_mutmut_stats_plugin.py``.

    Args:
        staging_dir: Empty writable directory used as the fake staging root.

    Returns:
        Namespace of the generated stats plugin.
    """

    from mutmut_win.runner import PytestRunner

    PytestRunner._write_stats_plugin(staging_dir)
    return dict(runpy.run_path(str(staging_dir / _STATS_PLUGIN_FILENAME)))


def make_log_report(
    *,
    when: str = "call",
    skipped: bool = False,
    wasxfail: str | None = None,
    **extra: Any,
) -> SimpleNamespace:
    """Build a synthetic ``pytest_runtest_logreport`` report object.

    Args:
        when: Report phase (``"setup"``/``"call"``/``"teardown"``).
        skipped: Whether the report outcome is ``skipped``.
        wasxfail: Value for the ``wasxfail`` attribute; ``None`` omits the
            attribute entirely (like reports without any xfail involvement).
        **extra: Additional attributes copied onto the report.

    Returns:
        A ``SimpleNamespace`` standing in for the pytest report.
    """

    attributes: dict[str, Any] = {"when": when, "skipped": skipped}
    if wasxfail is not None:
        attributes["wasxfail"] = wasxfail
    attributes.update(extra)
    return SimpleNamespace(**attributes)


@contextlib.contextmanager
def _phase_guard_env(scratch_dir: Path) -> Iterator[tuple[Path, str]]:
    """Install the production phase-guard environment into ``os.environ``.

    Builds the child environment exactly like the runner does (boundary
    variables plus one unique proof target), exports the ``MUTMUT_*`` part
    into ``os.environ`` for the duration of the block and yields
    ``(marker_path, token)``.
    """

    from mutmut_win.process.worker import (
        apply_pytest_boundary_environment,
        prepare_pytest_phase_guard,
    )
    from mutmut_win.pytest_boundary import prepare_pytest_boundary

    runtime_dir = scratch_dir / "runtime"
    runtime_dir.mkdir(exist_ok=True)
    env: dict[str, str] = {}
    boundary = prepare_pytest_boundary(
        project_root=scratch_dir,
        staging_root=scratch_dir,
        tests_dir=[],
    )
    apply_pytest_boundary_environment(boundary, env)
    marker_path, token = prepare_pytest_phase_guard(
        env,
        mutants_dir=scratch_dir,
        runtime_dir=runtime_dir,
    )
    mutmut_keys = {key: value for key, value in env.items() if key.startswith(_MUTMUT_ENV_PREFIX)}
    with pytest.MonkeyPatch.context() as patch:
        for key, value in mutmut_keys.items():
            patch.setenv(key, value)
        yield marker_path, token
