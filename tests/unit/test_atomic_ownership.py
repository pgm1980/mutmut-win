"""Real Windows name changes must not transfer cleanup ownership (S3-008)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import BaseModel

import mutmut_win.atomic_file as atomic_module


class _SwapState(BaseModel):
    """Track the one owned descriptor and actual filesystem displacement."""

    attempted: bool = False
    fd: int | None = None
    sibling: Path | None = None
    close_count: int = 0
    swapped: bool = False


@pytest.mark.parametrize("corridor", ["sibling", "sibling-close-error", "exclusive"])
def test_rejected_sibling_keeps_foreign_bytes_after_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corridor: str
) -> None:
    """A real hardlink rejection cannot unlink a new owner of the old name."""
    target = tmp_path / "target.bin"
    target.write_bytes(b"OLD")
    saved = tmp_path / "saved-owned.bin"
    hardlink = tmp_path / "owned-hardlink.bin"
    state = _SwapState()
    real_open = os.open
    real_close = os.close

    def open_then_link(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        candidate = Path(path)
        chosen = (
            candidate.name.startswith("trial-")
            if corridor == "exclusive"
            else (".mutmut-atomic-" in candidate.name)
        )
        if not state.attempted and candidate.parent == tmp_path and chosen:
            state.attempted = True
            state.fd = fd
            state.sibling = candidate
            os.link(candidate, hardlink)
            assert candidate.lstat().st_nlink == 2
        return fd

    def close_then_swap(fd: int) -> None:
        real_close(fd)
        if fd == state.fd:
            state.close_count += 1
            state.fd = None
            assert state.sibling is not None
            state.sibling.rename(saved)
            state.sibling.write_bytes(b"FOREIGN-FIXTURE")
            state.swapped = True
            if corridor == "sibling-close-error":
                raise OSError("controlled close error after descriptor release")

    with monkeypatch.context() as patcher:
        patcher.setattr(atomic_module.os, "open", open_then_link)
        patcher.setattr(atomic_module.os, "close", close_then_swap)
        if corridor == "sibling-close-error":
            with pytest.raises(OSError, match="controlled close error"):
                atomic_module.atomic_write_bytes(target, b"NEW")
        elif corridor == "exclusive":
            published, _identity = atomic_module.create_exclusive_random_bytes(
                tmp_path, b"CONFIG", prefix="trial-", suffix=".ini"
            )
            assert published.read_bytes() == b"CONFIG"
        else:
            atomic_module.atomic_write_bytes(target, b"NEW")

    assert state.swapped
    assert state.close_count == 1
    assert state.sibling is not None
    assert state.sibling.exists(), "cleanup deleted foreign bytes at the reused sibling name"
    assert state.sibling.read_bytes() == b"FOREIGN-FIXTURE"
    assert saved.read_bytes() == hardlink.read_bytes() == b""
    assert target.read_bytes() == (b"NEW" if corridor == "sibling" else b"OLD")


@pytest.mark.parametrize("identity", [(-1, 1), (1, 0), (1, -1)])
def test_cleanup_capture_refuses_invalid_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity: tuple[int, int]
) -> None:
    """An invalid descriptor observation cannot grant cleanup authority."""
    target = tmp_path / "owned.bin"
    target.write_bytes(b"KEEP")
    with target.open("rb") as handle, monkeypatch.context() as patcher:
        patcher.setattr(atomic_module, "_identity", lambda _stat: identity)
        assert atomic_module._capture_cleanup_identity(handle.fileno()) is None
    assert target.read_bytes() == b"KEEP"


def test_cleanup_capture_refuses_unavailable_descriptor() -> None:
    """An invalid descriptor preserves the original failure without path cleanup."""
    assert atomic_module._capture_cleanup_identity(-1) is None


def test_cleanup_capture_refuses_non_regular_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory-shaped observation cannot authorize deleting a sibling."""
    directory_stat = tmp_path.stat()
    with monkeypatch.context() as patcher:
        patcher.setattr(atomic_module.os, "fstat", lambda _fd: directory_stat)
        assert atomic_module._capture_cleanup_identity(-1) is None
