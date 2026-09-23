"""Self-tests for the fault-injection harness (AP-00 / Q-01)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from tests.unit.atomic_fault_util import inject_call_fault, record_calls

if TYPE_CHECKING:
    from pathlib import Path


def _force_call(target: Path) -> None:
    source = target.with_name(f"{target.name}.src")
    source.write_text("payload", encoding="utf-8")
    source.replace(target)


def test_first_mode_fails_only_the_first_call(tmp_path: Path) -> None:
    target = tmp_path / "first.txt"
    with inject_call_fault(
        "os.replace", mode="first", exception=OSError("injected transient failure")
    ) as recorder:
        with pytest.raises(OSError, match="injected transient failure"):
            _force_call(target)
        # Second call goes through to the real implementation.
        _force_call(target)

    assert recorder.call_count == 2
    assert recorder.injected_failures == 1
    assert target.read_text(encoding="utf-8") == "payload"


def test_nth_mode_fails_exactly_the_nth_call(tmp_path: Path) -> None:
    target = tmp_path / "nth.txt"
    with inject_call_fault(
        "os.replace", mode="nth", n=2, exception=PermissionError("nth failure")
    ) as recorder:
        _force_call(target)  # recorded call 1 passes
        with pytest.raises(PermissionError, match="nth failure"):
            _force_call(target)  # recorded call 2 fails

    assert recorder.call_count == 2
    assert recorder.injected_failures == 1
    assert target.read_text(encoding="utf-8") == "payload"


def test_always_mode_fails_every_call(tmp_path: Path) -> None:
    with inject_call_fault(
        "os.replace", mode="always", exception=OSError(13, "always fails")
    ) as recorder:
        for _ in range(3):
            with pytest.raises(OSError, match="always fails"):
                _force_call(tmp_path / "always.txt")

    assert recorder.call_count == 3
    assert recorder.injected_failures == 3


def test_patch_is_scoped_after_the_context() -> None:
    with (
        inject_call_fault("os.lstat", mode="always", exception=OSError("blocked")),
        pytest.raises(OSError, match="blocked"),
    ):
        os.lstat(".")
    # Outside the context manager the real implementation must be back.
    assert os.lstat(".").st_size >= 0


def test_call_spy_records_without_changing_behaviour(tmp_path: Path) -> None:
    target = tmp_path / "spied.txt"
    with record_calls("mutmut_win.atomic_file.atomic_write_bytes") as recorder:
        from mutmut_win.atomic_file import atomic_write_bytes

        atomic_write_bytes(target, b"spy payload")

    assert recorder.call_count == 1
    assert recorder.injected_failures == 0
    assert target.read_bytes() == b"spy payload"


def test_invalid_mode_and_n_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown fault mode"):
        inject_call_fault("os.replace", mode="sometimes", exception=OSError())
    with pytest.raises(ValueError, match="n must be >= 1"):
        inject_call_fault("os.replace", mode="nth", n=0, exception=OSError())


def test_target_must_be_dotted() -> None:
    with pytest.raises(ValueError, match="dotted"):
        inject_call_fault("replace", mode="always", exception=OSError())
