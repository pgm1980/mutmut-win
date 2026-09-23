"""Self-tests for the generated-plugin loader (AP-00 / Q-03)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.unit.guard_plugin_util import (
    load_phase_guard_plugin,
    load_plugin_source,
    load_stats_plugin,
    make_log_report,
    phase_guard_plugin,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_load_plugin_source_returns_fresh_namespaces(tmp_path: Path) -> None:
    source = "VALUE = 41\nVALUE += 1\n"
    first = load_plugin_source(source, scratch_dir=tmp_path, filename="freshness.py")
    second = load_plugin_source(source, scratch_dir=tmp_path, filename="freshness.py")
    assert first["VALUE"] == 42
    assert second["VALUE"] == 42
    assert first is not second


def test_load_phase_guard_plugin_exposes_hook_and_flags(tmp_path: Path) -> None:
    namespace = load_phase_guard_plugin(tmp_path)
    assert callable(namespace["pytest_runtest_logreport"])
    assert namespace["_proof_published"] is False


def test_load_stats_plugin_writes_production_plugin(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    namespace = load_stats_plugin(staging)
    assert (staging / "_mutmut_stats_plugin.py").is_file()
    assert callable(namespace["pytest_sessionfinish"])
    assert callable(namespace["pytest_runtest_makereport"])


def test_make_log_report_attribute_variants() -> None:
    without_xfail = make_log_report(when="call", skipped=True)
    assert not hasattr(without_xfail, "wasxfail")
    assert without_xfail.when == "call"
    assert without_xfail.skipped is True

    with_xfail = make_log_report(wasxfail="expected failure")
    assert with_xfail.wasxfail == "expected failure"

    notrun = make_log_report(skipped=True, wasxfail="[NOTRUN] reason")
    assert notrun.wasxfail.startswith("[NOTRUN]")


def test_phase_guard_hook_publishes_proof_once(tmp_path: Path) -> None:
    """End-to-end sanity: loaded hook publishes the proof token exactly once."""
    import os

    with phase_guard_plugin(tmp_path) as (namespace, marker_path, token):
        hook = namespace["pytest_runtest_logreport"]
        report = make_log_report(when="call", skipped=False)
        hook(report)
        assert marker_path.is_file()
        assert marker_path.read_text(encoding="utf-8") == token
        hook(report)  # one-shot: must not fail or re-publish differently
        assert marker_path.read_text(encoding="utf-8") == token
    assert "MUTMUT_PYTEST_PHASE_SENTINEL_PATH" not in os.environ
