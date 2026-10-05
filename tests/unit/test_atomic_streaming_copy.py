"""M-070: streaming staging copy with bounded peak memory.

The staging copy path used to read every file fully into memory
(``payload = source_file.read()``), so the peak requirement grew with the
largest single file.  The streaming rewrite copies in 1 MiB chunks and the
follow-up freshness hash streams through ``hashlib.file_digest`` — both
paths now need O(1) memory.
"""

from __future__ import annotations

import os
import stat
import tempfile
import tracemalloc
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import mutmut_win.atomic_file as atomic_module
from mutmut_win.atomic_file import atomic_copy_file
from mutmut_win.file_setup import _content_hash

_COPY_CHUNK_BYTES = 1 << 20


class TestStreamingCopy:
    def test_atomic_copy_peak_memory_is_bounded(self, tmp_path: Path) -> None:
        source = tmp_path / "large.bin"
        source.write_bytes(os.urandom(32 * _COPY_CHUNK_BYTES))
        target = tmp_path / "dst" / "large.bin"
        target.parent.mkdir()

        tracemalloc.start()
        try:
            atomic_copy_file(source, target)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert peak < 4 * _COPY_CHUNK_BYTES, f"streaming copy peaked at {peak} bytes"
        assert target.read_bytes() == source.read_bytes()

    def test_source_change_mid_stream_raises_and_leaves_no_siblings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "src.bin"
        source.write_bytes(b"A" * (3 * _COPY_CHUNK_BYTES))
        target = tmp_path / "dst" / "src.bin"
        target.parent.mkdir()

        real_write_all = atomic_module._write_all
        calls = {"count": 0}

        def hooked_write_all(fd: int, chunk: bytes) -> None:
            real_write_all(fd, chunk)
            calls["count"] += 1
            if calls["count"] == 1:
                # Change the source mtime after the first chunk landed.
                os.utime(source, ns=(0, 0))

        monkeypatch.setattr(atomic_module, "_write_all", hooked_write_all)

        with pytest.raises(OSError, match="changed while it was being read"):
            atomic_copy_file(source, target)

        monkeypatch.undo()
        assert list(target.parent.glob(".*.mutmut-atomic-*.tmp")) == []
        assert not target.exists()

    def test_copy_preserves_mode_and_mtime(self, tmp_path: Path) -> None:
        source = tmp_path / "paced.bin"
        source.write_bytes(b"payload-bytes")
        os.utime(source, ns=(1_700_000_000_123_456_700, 1_700_000_000_765_432_100))
        source.chmod(0o444)
        target = tmp_path / "dst" / "paced.bin"
        target.parent.mkdir()

        try:
            atomic_copy_file(source, target)
            assert target.read_bytes() == b"payload-bytes"
            assert target.stat().st_mtime_ns == source.stat().st_mtime_ns
            assert stat.S_IMODE(target.stat().st_mode) & stat.S_IWRITE == 0
        finally:
            source.chmod(stat.S_IWRITE)

    @settings(max_examples=25, deadline=None)
    @given(size=st.integers(min_value=0, max_value=3 * _COPY_CHUNK_BYTES + 7))
    def test_copy_is_byte_identical_across_chunk_boundaries(self, size: int) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            base = Path(raw_dir)
            source = base / "src.bin"
            source.write_bytes(os.urandom(size))
            target = base / "dst" / "src.bin"
            target.parent.mkdir()
            atomic_copy_file(source, target)
            assert target.read_bytes() == source.read_bytes()


class TestStreamingContentHash:
    def test_content_hash_peak_memory_is_bounded(self, tmp_path: Path) -> None:
        large = tmp_path / "large.bin"
        large.write_bytes(os.urandom(32 * _COPY_CHUNK_BYTES))

        tracemalloc.start()
        try:
            digest = _content_hash(large)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert peak < 4 * _COPY_CHUNK_BYTES, f"content hash peaked at {peak} bytes"
        assert len(digest) == 64
