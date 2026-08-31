"""Security regressions for runner-generated workspace sidecars."""

from __future__ import annotations

import json
import os
import runpy
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

import mutmut_win.atomic_file as atomic_file_module
from mutmut_win.atomic_file import UnsafeAtomicWriteError
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import PytestBoundaryError
from mutmut_win.process.worker import (
    _PYTEST_PHASE_SENTINEL_PATH_ENV,
    _PYTEST_PHASE_SENTINEL_PROOF_ENV,
    _write_pytest_argfile,
    prepare_pytest_phase_guard,
)
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from collections.abc import Callable


def _make_link(link: Path, referent: Path, kind: str) -> None:
    if kind == "hardlink":
        os.link(referent, link)
        return
    try:
        link.symlink_to(referent)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable in this environment: {exc}")


@pytest.mark.parametrize("kind", ["hardlink", "symlink"])
@pytest.mark.parametrize(
    ("sidecar_name", "expected_fragment"),
    [("_mutmut_stats_plugin.py", "pytest_sessionfinish"), ("sitecustomize.py", "sys.path[:]")],
)
def test_runner_sidecars_replace_links_without_writing_their_referents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    sidecar_name: str,
    expected_fragment: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    staging = tmp_path / "mutants"
    staging.mkdir()
    sentinel = tmp_path / "outside-sentinel.py"
    sentinel.write_bytes(b"EXTERNAL-SENTINEL")
    sidecar = staging / sidecar_name
    _make_link(sidecar, sentinel, kind)

    if sidecar_name == "_mutmut_stats_plugin.py":
        PytestRunner._write_stats_plugin(staging)
    else:
        PytestRunner(MutmutConfig()).write_pth_blocker(staging)

    assert sentinel.read_bytes() == b"EXTERNAL-SENTINEL"
    assert expected_fragment in sidecar.read_text(encoding="utf-8")
    assert not sidecar.is_symlink()
    assert not sidecar.samefile(sentinel)


def _load_session_finish(plugin_path: Path) -> Callable[[object, int], None]:
    namespace = runpy.run_path(str(plugin_path))
    return cast("Callable[[object, int], None]", namespace["pytest_sessionfinish"])


def test_generated_plugin_never_opens_the_predictable_stats_tmp_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    PytestRunner._write_stats_plugin(staging)
    finish = _load_session_finish(staging / "_mutmut_stats_plugin.py")
    sentinel = tmp_path / "outside-stats-sentinel.json"
    sentinel.write_bytes(b"EXTERNAL-STATS-SENTINEL")
    predictable_tmp = staging / "mutmut-stats.json.tmp"
    os.link(sentinel, predictable_tmp)
    monkeypatch.chdir(staging)

    finish(object(), 0)

    assert sentinel.read_bytes() == b"EXTERNAL-STATS-SENTINEL"
    assert predictable_tmp.samefile(sentinel)
    assert (staging / "mutmut-stats.json").is_file()
    assert list(staging.glob(".mutmut-stats.json.mutmut-atomic-*.tmp")) == []


def test_generated_plugin_detects_private_sibling_substitution_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    PytestRunner._write_stats_plugin(staging)
    finish = _load_session_finish(staging / "_mutmut_stats_plugin.py")
    stats_path = staging / "mutmut-stats.json"
    stats_path.write_bytes(b"PREVIOUS-GOOD-STATS")
    sentinel = tmp_path / "outside-substitution-sentinel.json"
    sentinel.write_bytes(b"EXTERNAL-SUBSTITUTION-SENTINEL")
    real_close = os.close
    substituted: list[Path] = []

    def close_then_substitute(fd: int) -> None:
        real_close(fd)
        if substituted:
            return
        candidates = list(staging.glob(".mutmut-stats.json.mutmut-atomic-*.tmp"))
        if not candidates:
            return
        candidate = candidates[0]
        candidate.unlink()
        os.link(sentinel, candidate)
        substituted.append(candidate)

    monkeypatch.chdir(staging)
    monkeypatch.setattr(atomic_file_module.os, "close", close_then_substitute)

    with pytest.raises(UnsafeAtomicWriteError, match="changed before publication"):
        finish(object(), 0)

    assert substituted
    assert sentinel.read_bytes() == b"EXTERNAL-SUBSTITUTION-SENTINEL"
    assert stats_path.read_bytes() == b"PREVIOUS-GOOD-STATS"
    assert substituted[0].samefile(sentinel)


def test_phase_guard_refuses_redirected_parent_before_outside_write(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    staging = tmp_path / "mutants"
    try:
        staging.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(PytestBoundaryError, match="Could not publish the pytest execution guard"):
        prepare_pytest_phase_guard({}, staging)

    assert list(outside.iterdir()) == []


def test_parallel_phase_guard_publishers_accept_only_the_identical_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five simultaneous publisher calls accept the byte-identical winner."""
    staging = tmp_path / "mutants"
    staging.mkdir()
    publisher_count = 5
    first_checks = threading.Barrier(publisher_count)
    completed_replaces = threading.Barrier(publisher_count)
    replace_lock = threading.Lock()
    verification_lock = threading.Lock()
    recovery_verifications = 0
    thread_state = threading.local()
    real_matches = atomic_file_module._regular_file_matches_bytes
    real_replace = Path.replace

    def synchronize_initial_miss(path: Path, payload: bytes) -> bool:
        nonlocal recovery_verifications
        if not getattr(thread_state, "initial_check_done", False):
            thread_state.initial_check_done = True
            first_checks.wait(timeout=5)
            return False
        with verification_lock:
            recovery_verifications += 1
        return real_matches(path, payload)

    def replace_then_release_publishers(source: Path, destination: Path) -> Path:
        # Serialize only the OS rename itself. Every writer then waits until
        # all five replacements are complete, forcing four post-publication
        # identity mismatches in the strict writer.
        with replace_lock:
            result = real_replace(source, destination)
        completed_replaces.wait(timeout=5)
        return result

    monkeypatch.setattr(
        atomic_file_module,
        "_regular_file_matches_bytes",
        synchronize_initial_miss,
    )
    monkeypatch.setattr(Path, "replace", replace_then_release_publishers)

    def publish_guard(_worker: int) -> tuple[Path, str]:
        return prepare_pytest_phase_guard({}, staging)

    with ThreadPoolExecutor(max_workers=publisher_count) as pool:
        results = list(pool.map(publish_guard, range(publisher_count)))

    plugin = staging / "_mutmut_phase_guard.py"
    assert plugin.is_file()
    assert "pytest_load_initial_conftests" in plugin.read_text(encoding="utf-8")
    assert len({marker for marker, _token in results}) == publisher_count
    assert len({token for _marker, token in results}) == publisher_count
    assert recovery_verifications == publisher_count - 1
    assert list(staging.glob("._mutmut_phase_guard.py.mutmut-atomic-*.tmp")) == []


def test_pytest_argfile_refuses_redirected_parent_before_outside_write(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    staging = tmp_path / "mutants"
    try:
        staging.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(UnsafeAtomicWriteError, match="parent must be a real directory"):
        _write_pytest_argfile(["tests/test_example.py::test_it"], staging)

    assert list(outside.iterdir()) == []


def test_generated_phase_proof_detects_parent_swap_before_outside_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    moved_staging = tmp_path / "original-mutants"
    env: dict[str, str] = {}
    marker_path, _token = prepare_pytest_phase_guard(env, staging)
    staging_stat = staging.stat()
    monkeypatch.setenv(
        "MUTMUT_PYTEST_ALLOWED_DIRS",
        json.dumps(
            [
                {
                    "path": str(staging.resolve()),
                    "st_dev": staging_stat.st_dev,
                    "st_ino": staging_stat.st_ino,
                }
            ]
        ),
    )
    monkeypatch.setenv("MUTMUT_PYTEST_ALLOWED_FILES", "[]")
    namespace = runpy.run_path(str(staging / "_mutmut_phase_guard.py"))
    hook = cast("Callable[[object], None]", namespace["pytest_runtest_logreport"])

    try:
        staging.rename(moved_staging)
        staging.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    monkeypatch.setenv(_PYTEST_PHASE_SENTINEL_PATH_ENV, env[_PYTEST_PHASE_SENTINEL_PATH_ENV])
    monkeypatch.setenv(_PYTEST_PHASE_SENTINEL_PROOF_ENV, env[_PYTEST_PHASE_SENTINEL_PROOF_ENV])

    with pytest.raises(UnsafeAtomicWriteError, match="parent must be a real directory"):
        hook(SimpleNamespace(when="call"))

    assert marker_path.parent == staging.absolute()
    assert list(outside.iterdir()) == []
