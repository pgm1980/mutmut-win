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
from hypothesis import given, settings
from hypothesis import strategies as st

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
from mutmut_win.stats import build_staging_context_evidence

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
    output_dir = tmp_path / "stats-output"
    output_dir.mkdir()
    stats_path = output_dir / "mutmut-stats.json"
    monkeypatch.setenv("MUTMUT_STATS_OUTPUT_PATH", str(stats_path))
    sentinel = tmp_path / "outside-stats-sentinel.json"
    sentinel.write_bytes(b"EXTERNAL-STATS-SENTINEL")
    predictable_tmp = output_dir / "mutmut-stats.json.tmp"
    os.link(sentinel, predictable_tmp)
    monkeypatch.chdir(staging)

    finish(object(), 0)

    assert sentinel.read_bytes() == b"EXTERNAL-STATS-SENTINEL"
    assert predictable_tmp.samefile(sentinel)
    assert stats_path.is_file()
    assert not (staging / "mutmut-stats.json").exists()
    assert list(output_dir.glob(".mutmut-stats.json.mutmut-atomic-*.tmp")) == []


def test_generated_plugin_detects_private_sibling_substitution_before_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    PytestRunner._write_stats_plugin(staging)
    finish = _load_session_finish(staging / "_mutmut_stats_plugin.py")
    output_dir = tmp_path / "stats-output"
    output_dir.mkdir()
    stats_path = output_dir / "mutmut-stats.json"
    monkeypatch.setenv("MUTMUT_STATS_OUTPUT_PATH", str(stats_path))
    stats_path.write_bytes(b"PREVIOUS-GOOD-STATS")
    sentinel = tmp_path / "outside-substitution-sentinel.json"
    sentinel.write_bytes(b"EXTERNAL-SUBSTITUTION-SENTINEL")
    real_close = os.close
    substituted: list[Path] = []

    def close_then_substitute(fd: int) -> None:
        real_close(fd)
        if substituted:
            return
        candidates = list(output_dir.glob(".mutmut-stats.json.mutmut-atomic-*.tmp"))
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


def test_generated_phase_proof_publishes_once_per_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The execution proof is published exactly once per phase.

    The first qualifying call report carries the full strict publication
    contract; every later report must be a no-op. Per-report republication
    fed filter drivers thousands of fresh temporary files per phase and
    starved the whole run under load (MBR-2026-09-14-01 follow-up).
    """
    staging = tmp_path / "mutants"
    staging.mkdir()
    env: dict[str, str] = {}
    marker_path, token = prepare_pytest_phase_guard(env, staging)
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
    monkeypatch.setenv(_PYTEST_PHASE_SENTINEL_PATH_ENV, env[_PYTEST_PHASE_SENTINEL_PATH_ENV])
    monkeypatch.setenv(_PYTEST_PHASE_SENTINEL_PROOF_ENV, env[_PYTEST_PHASE_SENTINEL_PROOF_ENV])

    # run_path returns a COPY of the module globals, so patching the returned
    # namespace cannot intercept the hook; patch the source module BEFORE the
    # plugin is published so its import binds the counting wrapper.
    publications: list[Path] = []
    real_atomic = atomic_file_module.atomic_write_bytes

    def counting_atomic_write(path: Path, payload: bytes, **_kwargs: object) -> None:
        if Path(path) == marker_path:
            publications.append(Path(path))
        real_atomic(path, payload)

    monkeypatch.setattr(atomic_file_module, "atomic_write_bytes", counting_atomic_write)
    namespace = runpy.run_path(str(staging / "_mutmut_phase_guard.py"))
    hook = cast("Callable[[object], None]", namespace["pytest_runtest_logreport"])
    call_report = SimpleNamespace(when="call", skipped=False)

    hook(SimpleNamespace(when="setup", skipped=False))
    hook(SimpleNamespace(when="call", skipped=True))
    assert publications == []

    hook(call_report)
    assert publications == [marker_path]
    assert marker_path.read_text(encoding="utf-8") == token

    hook(call_report)
    hook(call_report)
    assert publications == [marker_path]


def test_generated_phase_proof_detects_parent_swap_before_outside_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """The parent-swap tripwire fires, but never escapes into pytest (M-008).

    Before M-008 the UnsafeAtomicWriteError escaped the hook and became a
    pytest INTERNALERROR (exit 3), which the score counted as killed. Now
    the hook records the failure once, emits the prefixed diagnostic line,
    and publishes no proof.
    """
    # Skip the ~15.85 s parent-capture retry ladder; the tripwire verdict
    # itself is unaffected by the delays.
    monkeypatch.setattr(atomic_file_module, "_PARENT_CAPTURE_RETRY_DELAYS", ())
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

    capfd.readouterr()
    assert hook(SimpleNamespace(when="call", skipped=False)) is None
    captured = capfd.readouterr().err
    assert "mutmut-win: execution proof publication failed" in captured
    assert "UnsafeAtomicWriteError" in captured
    assert "parent must be a real directory" in captured

    # One-shot: a second qualifying report neither retries nor re-emits.
    capfd.readouterr()
    hook(SimpleNamespace(when="call", skipped=False))
    assert "mutmut-win: execution proof publication failed" not in capfd.readouterr().err

    assert not marker_path.exists()
    assert list(outside.iterdir()) == []


def test_real_benchmark_save_stays_outside_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real pytest-benchmark save must not change executable staging."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    staging = tmp_path / "mutants"
    staging.mkdir()
    test_path = staging / "test_benchmark_output.py"
    test_path.write_text(
        "def test_benchmark_output(benchmark):\n    assert benchmark(lambda: 42) == 42\n",
        encoding="utf-8",
    )
    runner = PytestRunner(
        MutmutConfig(
            tests_dir=[test_path.name],
            pytest_add_cli_args=["--benchmark-save=mutmut-sidecar-regression"],
            clean_run_timeout=60,
        )
    )
    runner.write_pth_blocker(staging)
    before = build_staging_context_evidence(tmp_path)

    assert before.complete
    assert runner.run_clean_test() == 0
    after = build_staging_context_evidence(tmp_path)

    assert after == before
    assert not any(path.name.casefold() == ".benchmarks" for path in tmp_path.rglob("*"))
    assert not (staging / "Users").exists()
    assert not (tmp_path / "Users").exists()


# ---------------------------------------------------------------------------
# Proof publication failures inside the generated plugin (M-008, issue #143)
# ---------------------------------------------------------------------------

_FAILURE_EXAMPLES = [
    "UnsafeAtomicWriteError",
    "AtomicReplaceError",
    "AtomicPublicationRaceError",
    "PermissionError",
    "FileNotFoundError",
    "FileExistsError",
    "OSError",
    "RuntimeError",
    "ValueError",
]


class _BrokenStrError(RuntimeError):
    def __str__(self) -> str:  # pragma: no cover - exercises the fallback
        raise RuntimeError("str() is broken")


def _load_hook(
    staging: Path,
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    *,
    atomic_override: object = None,
) -> tuple[dict, object, Path]:
    """Publish + load the real plugin and export its sentinel env.

    ``atomic_override`` replaces ``atomic_write_bytes`` BEFORE the plugin is
    loaded: the plugin binds the name at import time, so later patches on the
    source module would no longer reach it.
    """
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
    monkeypatch.setenv(_PYTEST_PHASE_SENTINEL_PATH_ENV, env[_PYTEST_PHASE_SENTINEL_PATH_ENV])
    monkeypatch.setenv(_PYTEST_PHASE_SENTINEL_PROOF_ENV, env[_PYTEST_PHASE_SENTINEL_PROOF_ENV])
    if atomic_override is not None:
        monkeypatch.setattr(atomic_file_module, "atomic_write_bytes", atomic_override)
    namespace = runpy.run_path(str(staging / "_mutmut_phase_guard.py"))
    hook = namespace["pytest_runtest_logreport"]
    return namespace, hook, marker_path


def test_generated_phase_proof_publication_failure_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """T1: a publication failure stays inside the hook and is diagnosed once."""
    from mutmut_win.atomic_file import AtomicPublicationRaceError

    staging = tmp_path / "mutants"
    staging.mkdir()
    env: dict[str, str] = {}

    attempts: list[Path] = []

    def failing_atomic_write(path: Path, _payload: bytes, **_kwargs: object) -> None:
        attempts.append(Path(path))
        raise AtomicPublicationRaceError("race")

    _namespace, hook, marker_path = _load_hook(
        staging, monkeypatch, env, atomic_override=failing_atomic_write
    )

    capfd.readouterr()
    assert hook(SimpleNamespace(when="call", skipped=False)) is None
    assert not marker_path.exists()
    assert len(attempts) == 1

    err = capfd.readouterr().err
    assert err.count("mutmut-win: execution proof publication failed") == 1
    assert "AtomicPublicationRaceError: race" in err

    # One-shot: two more qualifying reports retry nothing and stay silent.
    capfd.readouterr()
    hook(SimpleNamespace(when="call", skipped=False))
    hook(SimpleNamespace(when="call", skipped=False))
    assert len(attempts) == 1
    assert "mutmut-win: execution proof publication failed" not in capfd.readouterr().err


@given(exception_type=st.sampled_from(_FAILURE_EXAMPLES))
@settings(max_examples=25, deadline=None)
def test_generated_phase_proof_never_raises_across_exception_types(
    exception_type: str,
) -> None:
    """T2: for every failure class the hook tries once, publishes nothing."""
    import tempfile

    exception_class = {
        "UnsafeAtomicWriteError": UnsafeAtomicWriteError,
        "AtomicReplaceError": atomic_file_module.AtomicReplaceError,
        "AtomicPublicationRaceError": atomic_file_module.AtomicPublicationRaceError,
        "PermissionError": PermissionError,
        "FileNotFoundError": FileNotFoundError,
        "FileExistsError": FileExistsError,
        "OSError": OSError,
        "RuntimeError": RuntimeError,
        "ValueError": ValueError,
    }[exception_type]

    def raising_write(_path: Path, _payload: bytes, **_kwargs: object) -> None:
        raise exception_class("boom")

    emitted: list[bytes] = []

    def recording_write(_fd: int, payload: bytes) -> int:
        emitted.append(payload)
        return len(payload)

    with tempfile.TemporaryDirectory() as name:
        staging = Path(name) / "mutants"
        staging.mkdir()
        with pytest.MonkeyPatch.context() as patch:
            env: dict[str, str] = {}
            _namespace, hook, marker_path = _load_hook(
                staging, patch, env, atomic_override=raising_write
            )
            report = SimpleNamespace(when="call", skipped=False)
            with patch.context() as scoped:
                scoped.setattr(os, "write", recording_write)
                assert hook(report) is None
                assert hook(report) is None
            assert not marker_path.exists()
            # run_path returns a copy of the module globals, so one-shot
            # state is proven behaviourally: exactly one attempt (recorded
            # in the closure) and exactly one diagnostic emission.
            assert len(emitted) == 1
            assert b"mutmut-win: execution proof publication failed" in emitted[0]
            assert exception_type.encode() in emitted[0]


def test_generated_phase_proof_keyboard_interrupt_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T3: BaseException subclasses are not swallowed by the guard."""
    staging = tmp_path / "mutants"
    staging.mkdir()
    env: dict[str, str] = {}

    def interrupting_write(_path: Path, _payload: bytes, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    _namespace, hook, marker_path = _load_hook(
        staging, monkeypatch, env, atomic_override=interrupting_write
    )

    with pytest.raises(KeyboardInterrupt):
        hook(SimpleNamespace(when="call", skipped=False))
    assert not marker_path.exists()


def test_publication_diagnostic_is_robust_and_reemitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T4: broken str, failing fd 2, and unconfigure re-emission are all safe."""
    staging = tmp_path / "mutants"
    staging.mkdir()
    env: dict[str, str] = {}
    real_atomic = atomic_file_module.atomic_write_bytes

    def broken_write(_path: Path, _payload: bytes, **_kwargs: object) -> None:
        raise _BrokenStrError

    namespace, hook, marker_path = _load_hook(
        staging, monkeypatch, env, atomic_override=broken_write
    )

    emitted: list[bytes] = []

    def recording_write(_fd: int, payload: bytes) -> int:
        emitted.append(payload)
        return len(payload)

    with monkeypatch.context() as scoped:
        scoped.setattr(os, "write", recording_write)
        hook(SimpleNamespace(when="call", skipped=False))
        assert len(emitted) == 1
        assert b"mutmut-win: execution proof publication failed: _BrokenStrError" in emitted[0]
        # pytest_unconfigure repeats the recorded line exactly once more.
        namespace["pytest_unconfigure"](SimpleNamespace())
        assert len(emitted) == 2
        assert emitted[1] == emitted[0]
    assert not marker_path.exists()

    # After a successful publication, unconfigure writes nothing.
    monkeypatch.setattr(atomic_file_module, "atomic_write_bytes", real_atomic)
    fresh_env: dict[str, str] = {}
    fresh_namespace, fresh_hook, fresh_marker = _load_hook(staging, monkeypatch, fresh_env)
    fresh_hook(SimpleNamespace(when="call", skipped=False))
    assert fresh_marker.exists()
    emitted.clear()
    with monkeypatch.context() as scoped:
        scoped.setattr(os, "write", recording_write)
        fresh_namespace["pytest_unconfigure"](SimpleNamespace())
        assert emitted == []

    # A failing os.write never lets the hook or unconfigure raise.
    def exploding_write(_fd: int, _payload: bytes) -> int:
        raise OSError("fd 2 is gone")

    def failing_again(_path: Path, _payload: bytes, **_kwargs: object) -> None:
        raise RuntimeError("still failing")

    broken_env: dict[str, str] = {}
    broken_namespace, broken_hook, _broken_marker = _load_hook(
        staging, monkeypatch, broken_env, atomic_override=failing_again
    )
    with monkeypatch.context() as scoped:
        scoped.setattr(os, "write", exploding_write)
        assert broken_hook(SimpleNamespace(when="call", skipped=False)) is None
        broken_namespace["pytest_unconfigure"](SimpleNamespace())


def test_plugin_source_pins_prefix_and_compiles() -> None:
    """T9: the failure prefix, compile safety, and unconfigure are pinned."""
    from mutmut_win.process.worker import (
        _PROOF_PUBLICATION_FAILURE_PREFIX,
        _PYTEST_PHASE_GUARD_SOURCE,
    )

    compile(_PYTEST_PHASE_GUARD_SOURCE, "_mutmut_phase_guard.py", "exec")
    assert _PROOF_PUBLICATION_FAILURE_PREFIX in _PYTEST_PHASE_GUARD_SOURCE
    assert "pytest_unconfigure" in _PYTEST_PHASE_GUARD_SOURCE
    # Escape trap (U3): a non-raw triple-quoted literal would turn any
    # backslash sequence into real control characters in the plugin.
    assert "\\" not in _PYTEST_PHASE_GUARD_SOURCE


# ---------------------------------------------------------------------------
# Expected xfail call reports count as executed (M-143, issue #143)
# ---------------------------------------------------------------------------


def test_generated_phase_proof_accepts_xfailed_call_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skipped call report with a real wasxfail reason publishes the proof."""
    staging = tmp_path / "mutants"
    staging.mkdir()
    env: dict[str, str] = {}
    _namespace, hook, marker_path = _load_hook(staging, monkeypatch, env)

    hook(SimpleNamespace(when="call", skipped=True, wasxfail="expected failure"))
    hook(SimpleNamespace(when="call", skipped=True, wasxfail=""))
    assert marker_path.is_file()


def test_generated_phase_proof_rejects_notrun_and_plain_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dynamic xfail(run=False) markers and runtime skips publish nothing."""
    staging = tmp_path / "mutants"
    staging.mkdir()
    env: dict[str, str] = {}
    _namespace, hook, marker_path = _load_hook(staging, monkeypatch, env)

    hook(SimpleNamespace(when="call", skipped=True, wasxfail="[NOTRUN] reason"))
    hook(SimpleNamespace(when="call", skipped=True, wasxfail="[NOTRUN] "))
    hook(SimpleNamespace(when="call", skipped=True))
    hook(SimpleNamespace(when="setup", skipped=True, wasxfail="expected failure"))
    assert not marker_path.exists()
