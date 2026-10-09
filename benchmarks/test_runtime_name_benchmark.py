"""Fixed-load trampoline measurements with and without active clean recording."""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from mutmut_win import runtime_names
from mutmut_win.trampoline import trampoline_impl

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.parametrize(
    "mode", ["clean_active", "clean_inactive", "clean_without_recorder_branch", "mutant"]
)
def test_runtime_name_call_batch(
    benchmark: BenchmarkFixture,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    tmp_path: Path,
) -> None:
    """Measure repeated calls after one publication, excluding setup from timing."""
    module = ModuleType("benchmark_target")
    template = trampoline_impl
    if mode == "clean_without_recorder_branch":
        recorder_branch = (
            "    if mutant_under_test == '' and os.environ.get('MUTMUT_CLEAN_NAMES_PATH'):\n"
            "        from mutmut_win.runtime_names import record_runtime_name\n"
            "        record_runtime_name(orig.__module__ + '.' + orig.__name__)\n"
        )
        assert template.count(recorder_branch) == 1
        template = template.replace(recorder_branch, "")
    # Only the checked-in engine trampoline and fixed fixture code are executed.
    exec(  # noqa: S102
        compile(template + "\ndef original(): return 2\n", "<benchmark>", "exec"),
        module.__dict__,
    )
    monkeypatch.setenv("MUTANT_UNDER_TEST", "")
    monkeypatch.setenv("MUTMUT_CLEAN_NAMES_TOKEN", "a" * 64)
    monkeypatch.setenv("MUTMUT_CLEAN_NAMES_PATH", str(tmp_path))
    monkeypatch.setattr(runtime_names, "_recorder", None)
    monkeypatch.setattr(runtime_names, "_installed", True)
    monkeypatch.setattr(runtime_names, "_exit_code", None)
    runtime_names.start_pytest()
    recorder = runtime_names._ensure_recorder()
    if mode == "clean_inactive":
        monkeypatch.delenv("MUTMUT_CLEAN_NAMES_PATH")
    elif mode == "mutant":
        monkeypatch.setenv("MUTANT_UNDER_TEST", "unrelated.x_value__mutmut_1")

    def batch() -> int:
        return sum(module._mutmut_trampoline(module.original, {}, (), {}) for _ in range(1000))

    try:
        assert benchmark.pedantic(batch, rounds=100, iterations=1, warmup_rounds=5) == 2000
        assert recorder.names == (
            {"benchmark_target.original"} if mode == "clean_active" else set()
        )
    finally:
        recorder.control.close()
