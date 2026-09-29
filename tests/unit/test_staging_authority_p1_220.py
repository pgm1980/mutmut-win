"""Regressions for generated-output authority and atomic staging copies."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

import mutmut_win.atomic_file as atomic_file_module
import mutmut_win.file_setup as file_setup_module
from mutmut_win.exceptions import UnsafeStagingError
from mutmut_win.file_setup import _copy_with_retry, create_mutants_for_file
from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _source_and_output(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "src" / "mod.py"
    output = tmp_path / "mutants" / "src" / "mod.py"
    source.parent.mkdir(parents=True)
    source.write_text("def add(x: int) -> int:\n    return x + 1\n", encoding="utf-8")
    return source, output


def _replace_mutant_bodies_with_forced_kills(generated: str, names: list[str]) -> str:
    tampered = generated
    for local_name in names:
        pattern = rf"(def {re.escape(local_name)}\([^\n]*\):\n)(    [^\n]*\n)"
        tampered, replacements = re.subn(
            pattern,
            r'\1    raise AssertionError("tampered mutant kill")\n',
            tampered,
            count=1,
        )
        assert replacements == 1
    return tampered


def test_generated_file_tamper_forces_regeneration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source, output = _source_and_output(tmp_path)
    names, _, first_fast_path = create_mutants_for_file(source, output)
    assert names
    assert first_fast_path is False

    tampered = _replace_mutant_bodies_with_forced_kills(output.read_text(encoding="utf-8"), names)
    output.write_text(tampered, encoding="utf-8")

    regenerated_names, _, second_fast_path = create_mutants_for_file(source, output)

    assert regenerated_names == names
    assert second_fast_path is False
    assert "tampered mutant kill" not in output.read_text(encoding="utf-8")
    metadata = SourceFileMutationData(path="src/mod.py")
    metadata.load()
    assert metadata.generated_hash == hashlib.sha256(output.read_bytes()).hexdigest()


def test_legacy_meta_without_generated_hash_regenerates_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source, output = _source_and_output(tmp_path)
    names, _, _ = create_mutants_for_file(source, output)
    meta_path = output.with_name(output.name + ".meta")
    legacy = json.loads(meta_path.read_text(encoding="utf-8"))
    legacy.pop("generated_hash")
    meta_path.write_text(json.dumps(legacy), encoding="utf-8")

    regenerated_names, _, fast_path = create_mutants_for_file(source, output)

    assert regenerated_names == names
    assert fast_path is False
    healed = json.loads(meta_path.read_text(encoding="utf-8"))
    assert healed["generated_hash"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_output_publish_without_meta_commit_cannot_authorize_fast_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source, output = _source_and_output(tmp_path)
    names, _, _ = create_mutants_for_file(source, output)
    meta_path = output.with_name(output.name + ".meta")
    committed_meta = meta_path.read_bytes()

    def publish_different_valid_output(
        *,
        out: object,
        source: str,
        filename: Path | str,
        covered_lines: set[int] | None = None,
        active_profile: object,
        do_not_mutate_patterns: object,
    ) -> list[str]:
        del source, filename, covered_lines, active_profile, do_not_mutate_patterns
        out.write("alternate_generation = True\n")  # type: ignore[attr-defined]
        return names

    with (
        patch(
            "mutmut_win.file_setup.write_all_mutants_to_file",
            side_effect=publish_different_valid_output,
        ),
        patch.object(
            SourceFileMutationData,
            "save_generation_metadata",
            side_effect=OSError("meta commit failed"),
        ),
        pytest.raises(OSError, match="meta commit failed"),
    ):
        create_mutants_for_file(source, output, allow_fast_path=False)

    assert output.read_text(encoding="utf-8") == "alternate_generation = True\n"
    assert meta_path.read_bytes() == committed_meta

    regenerated_names, _, fast_path = create_mutants_for_file(source, output)
    assert regenerated_names == names
    assert fast_path is False
    assert "alternate_generation" not in output.read_text(encoding="utf-8")


def test_atomic_staging_copy_detects_close_substitute_without_external_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.py"
    destination = tmp_path / "staged.py"
    sentinel = tmp_path / "outside-sentinel.bin"
    source.write_bytes(b"SOURCE-CONTENT")
    sentinel.write_bytes(b"EXTERNAL-SENTINEL")
    real_close: Callable[[int], None] = os.close
    hijacked = False

    def close_then_substitute(fd: int) -> None:
        nonlocal hijacked
        real_close(fd)
        if hijacked:
            return
        candidates = list(tmp_path.glob(".staged.py.mutmut-atomic-*.tmp"))
        if not candidates:
            return
        candidate = candidates[0]
        candidate.unlink()
        os.link(sentinel, candidate)
        hijacked = True

    # file_setup and atomic_file reference the same stdlib os module. This
    # hook deterministically recreates the old close/reopen substitution at
    # the exact point a directory watcher would observe the closed sibling.
    monkeypatch.setattr(file_setup_module.os, "close", close_then_substitute)
    monkeypatch.setattr(file_setup_module.time, "sleep", lambda _seconds: None)
    _copy_with_retry(source, destination, max_attempts=2)

    assert hijacked is True
    assert sentinel.read_bytes() == b"EXTERNAL-SENTINEL"
    assert destination.read_bytes() == b"SOURCE-CONTENT"
    assert not destination.samefile(sentinel)


def test_atomic_staging_copy_preserves_freshness_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    destination = tmp_path / "staged.py"
    source.write_bytes(b"payload")
    os.utime(source, ns=(1_600_000_000_123_456_700, 1_600_000_000_123_456_700))
    source_stat = source.stat()

    _copy_with_retry(source, destination)

    destination_stat = destination.stat()
    assert destination_stat.st_mtime_ns == source_stat.st_mtime_ns
    if os.name != "nt":
        assert stat.S_IMODE(destination_stat.st_mode) == stat.S_IMODE(source_stat.st_mode)


def test_timestamp_copy_fallback_without_nofollow_utime_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.py"
    destination = tmp_path / "staged.py"
    sentinel = tmp_path / "outside-sentinel.bin"
    source.write_bytes(b"payload")
    sentinel.write_bytes(b"EXTERNAL-SENTINEL")
    os.link(sentinel, destination)
    os.utime(source, ns=(1_600_000_000_123_456_700, 1_600_000_000_123_456_700))
    source_mtime_ns = source.stat().st_mtime_ns
    monkeypatch.setattr(atomic_file_module.os, "supports_follow_symlinks", set())

    _copy_with_retry(source, destination)

    assert destination.read_bytes() == b"payload"
    assert destination.stat().st_mtime_ns == source_mtime_ns
    assert not destination.samefile(sentinel)
    assert sentinel.read_bytes() == b"EXTERNAL-SENTINEL"


def test_copy_with_retry_makes_exactly_max_attempts_with_full_backoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M-088: permanently locked files see exactly ``max_attempts`` copies.

    The historic loop swallowed the last iteration's ``OSError`` and then ran
    an unconditional extra ``copy_once()`` — six outer attempts for the
    default of five, the last one without a preceding backoff pause.
    """
    source = tmp_path / "source.py"
    destination = tmp_path / "staged.py"
    source.write_text("payload\n", encoding="utf-8")
    calls: list[str] = []
    sleeps: list[float] = []

    def locked_copy(_src: object, _dst: object) -> None:
        calls.append("copy")
        raise PermissionError("locked")

    monkeypatch.setattr(file_setup_module, "atomic_copy_file", locked_copy)
    monkeypatch.setattr(file_setup_module.time, "sleep", sleeps.append)

    with pytest.raises(PermissionError, match="locked"):
        _copy_with_retry(source, destination, max_attempts=5)

    assert calls == ["copy"] * 5
    assert sleeps == pytest.approx([0.1, 0.2, 0.4, 0.8])


def test_copy_with_retry_recovers_after_transient_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.py"
    destination = tmp_path / "staged.py"
    source.write_text("payload\n", encoding="utf-8")
    calls: list[str] = []
    sleeps: list[float] = []

    def flaky_copy(_src: object, _dst: object) -> None:
        calls.append("copy")
        if len(calls) <= 2:
            raise PermissionError("locked")

    monkeypatch.setattr(file_setup_module, "atomic_copy_file", flaky_copy)
    monkeypatch.setattr(file_setup_module.time, "sleep", sleeps.append)

    _copy_with_retry(source, destination, max_attempts=5)

    assert calls == ["copy"] * 3
    assert sleeps == pytest.approx([0.1, 0.2])


def test_copy_with_retry_rejects_non_positive_max_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conscious hardening (M-088): without the historic bonus attempt, a
    budget of zero could never publish anything — fail fast instead."""
    calls: list[str] = []

    monkeypatch.setattr(file_setup_module, "atomic_copy_file", lambda _s, _d: calls.append("copy"))

    with pytest.raises(ValueError, match="max_attempts"):
        _copy_with_retry(tmp_path / "source.py", tmp_path / "staged.py", max_attempts=0)

    assert calls == []


def test_copy_with_retry_propagates_non_oserror_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.py"
    destination = tmp_path / "staged.py"
    source.write_text("payload\n", encoding="utf-8")
    calls: list[str] = []
    sleeps: list[float] = []

    def refusing_copy(_src: object, _dst: object) -> None:
        calls.append("copy")
        raise UnsafeStagingError("hardlink substitute detected")

    monkeypatch.setattr(file_setup_module, "atomic_copy_file", refusing_copy)
    monkeypatch.setattr(file_setup_module.time, "sleep", sleeps.append)

    with pytest.raises(UnsafeStagingError, match="hardlink"):
        _copy_with_retry(source, destination, max_attempts=3)

    assert calls == ["copy"]
    assert sleeps == []


@given(
    max_attempts=st.integers(min_value=1, max_value=8),
    failures=st.integers(min_value=0, max_value=8),
)
def test_copy_with_retry_exact_attempt_budget(max_attempts: int, failures: int) -> None:
    """Q-42 property: the attempt budget and backoff ladder are exact.

    ``atomic_copy_file`` is stubbed, so fixed non-existent paths suffice and
    no function-scoped fixture is needed under ``@given``.
    """
    from pathlib import Path

    calls: list[str] = []
    sleeps: list[float] = []

    def flaky_copy(_src: object, _dst: object) -> None:
        calls.append("copy")
        if len(calls) <= failures:
            raise OSError("locked")

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(file_setup_module, "atomic_copy_file", flaky_copy)
        patcher.setattr(file_setup_module.time, "sleep", sleeps.append)
        if failures < max_attempts:
            _copy_with_retry(
                Path("copy-retry-nowhere-src.py"),
                Path("copy-retry-nowhere-dst.py"),
                max_attempts=max_attempts,
            )
        else:
            with pytest.raises(OSError, match="locked"):
                _copy_with_retry(
                    Path("copy-retry-nowhere-src.py"),
                    Path("copy-retry-nowhere-dst.py"),
                    max_attempts=max_attempts,
                )

    if failures < max_attempts:
        assert len(calls) == failures + 1
    else:
        assert len(calls) == max_attempts
        assert len(sleeps) == max_attempts - 1
    assert sleeps == [0.1 * 2**index for index in range(len(sleeps))]
