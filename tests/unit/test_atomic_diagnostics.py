"""Sibling-exhaustion diagnostics must never leave the failing process.

The former ``_dump_sibling_diagnostics`` appended one JSON line to a fixed
path under the shared ``%TEMP%`` — opened with ``Path.open("a")`` without
``lstat``, ``O_EXCL`` or identity checks, so a prepared hard/symlink
redirected the append onto its referent (M-067).  The diagnosis now
travels inside the raised ``UnsafeAtomicWriteError`` message instead: no
predictable path, no link following, no unbounded growth in shared temp
directories, no dependency on the very atomic writer that just failed.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

from mutmut_win.atomic_file import UnsafeAtomicWriteError, atomic_write_bytes


def _doctored_nlink(result: os.stat_result, nlink: int) -> os.stat_result:
    """Rebuild *result* with an overridden ``st_nlink`` (path-view doctoring).

    ``os.stat_result`` cannot be mutated; the extras dictionary is the only
    supported way to carry the Windows-only attributes through a rebuild
    (same technique as ``test_atomic_transient_retry.py``).
    """
    values = list(result)
    values[3] = nlink
    extras = {
        "st_atime_ns": result.st_atime_ns,
        "st_mtime_ns": result.st_mtime_ns,
        "st_ctime_ns": result.st_ctime_ns,
    }
    for optional in ("st_birthtime_ns", "st_file_attributes", "st_reparse_tag"):
        value = getattr(result, optional, None)
        if value is not None:
            extras[optional] = value
    return os.stat_result(tuple(values), extras)


def _reject_sibling_path_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the path-view ``lstat`` report an extra link for every sibling."""
    real_lstat = Path.lstat

    def atomic_twins(self: Path) -> os.stat_result:
        result = real_lstat(self)
        if ".mutmut-atomic-" in self.name:
            return _doctored_nlink(result, nlink=2)
        return result

    monkeypatch.setattr(Path, "lstat", atomic_twins)


def test_sibling_exhaustion_never_writes_through_a_prepared_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_temp = tmp_path / "shared-temp"
    shared_temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(shared_temp))
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"ORIGINAL")
    # A hardlink under the former diagnostics sink name redirects any append
    # onto the victim — no special privileges required on NTFS.
    os.link(victim, shared_temp / "mutmut-sibling-diag.jsonl")
    _reject_sibling_path_view(monkeypatch)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(UnsafeAtomicWriteError) as exc_info:
        atomic_write_bytes(tmp_path / "marker", b"x")
    monkeypatch.undo()

    assert victim.read_bytes() == b"ORIGINAL"
    assert "st_nlink" in str(exc_info.value)


def test_sibling_exhaustion_reports_fields_without_any_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated_temp = tmp_path / "isolated-temp"
    isolated_temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(isolated_temp))
    _reject_sibling_path_view(monkeypatch)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(UnsafeAtomicWriteError) as exc_info:
        atomic_write_bytes(tmp_path / "marker", b"x")
    monkeypatch.undo()

    message = str(exc_info.value)
    assert message.startswith("exclusive atomic-write sibling is not a private regular file")
    assert f"pid={os.getpid()}" in message
    assert "st_nlink" in message
    assert "identity_mismatch" in message
    # No filesystem access outside the failing operation's own directory:
    # the redirected temp directory stays untouched.
    assert list(isolated_temp.iterdir()) == []
