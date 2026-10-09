"""Fresh clean-call evidence with parent-issued Windows spawn tickets.

A fixed mapped control page survives worker termination. Each new name is
published before its original call; PENDING/INVALID cannot authorize a result.
Only this page uses mapped I/O. The append-only event file uses ordinary I/O
throughout. Recording helpers are excluded from their own instrumentation.
"""

from __future__ import annotations

import atexit
import mmap
import os
import secrets
import time
from contextvars import ContextVar
from multiprocessing import process, spawn
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Callable

_MAX_BYTES = 16 * 1024 * 1024
_MAX_PARTICIPANTS = 1024
_MAX_NAMES = 100_000
_CONTROL_BYTES = 4096
_UNREADY, _READY, _PENDING, _INVALID, _CLOSED = range(5)
_LOCK = RLock()
_installed = False
_exit_code: int | None = None


class _Ticket(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[3] = 3
    phase: Literal["clean"] = "clean"
    generation_policy: Literal["clean-called-v3"] = "clean-called-v3"
    participant_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    parent_participant_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    issuer_pid: int = Field(gt=0)
    token: str = Field(pattern=r"^[0-9a-f]{64}$")


class _Entry(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    kind: Literal["name", "child"]
    value: str = Field(min_length=1, max_length=4096)


class _Recorder(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    directory: Path
    ticket: _Ticket
    control: mmap.mmap
    names: set[str] = Field(default_factory=set)
    children: set[str] = Field(default_factory=set)
    closed: bool = False
    invalid: bool = False


_recorder: _Recorder | None = None
_start_ticket: ContextVar[_Ticket | None] = ContextVar("mutmut_clean_start_ticket", default=None)


def _path(directory: Path, ticket: _Ticket, suffix: str) -> Path:
    return directory / f"{ticket.participant_id}.{suffix}"


def _directory() -> Path:
    directory = Path(os.environ["MUTMUT_CLEAN_NAMES_PATH"])
    if not directory.is_absolute() or not directory.is_dir():
        raise ValueError("invalid runtime-name proof directory")
    if os.environ.get("MUTANT_UNDER_TEST") != "":
        raise ValueError("runtime-name proof requested outside clean phase")
    return directory


def _create_ticket(directory: Path, parent: _Ticket | None) -> _Ticket:
    ticket = _Ticket(
        participant_id=secrets.token_hex(16),
        parent_participant_id=parent.participant_id if parent else None,
        issuer_pid=os.getpid(),
        token=os.environ["MUTMUT_CLEAN_NAMES_TOKEN"],
    )
    raw = ticket.model_dump_json().encode("utf-8")
    if len(raw) > _CONTROL_BYTES - 64:
        raise ValueError("runtime-name ticket exceeds control page")
    # Files are exclusively created before OS spawn; any partial allocation is
    # an unexpected artifact or a pending parent transaction, never empty proof.
    with _path(directory, ticket, "control").open("x+b") as stream:
        stream.truncate(_CONTROL_BYTES)
        with mmap.mmap(stream.fileno(), _CONTROL_BYTES, access=mmap.ACCESS_WRITE) as control:
            control[4:8] = len(raw).to_bytes(4, "little")
            control[64 : 64 + len(raw)] = raw
    with _path(directory, ticket, "events").open("xb"):
        pass
    return ticket


def _read_ticket(control: mmap.mmap) -> _Ticket:
    if len(control) != _CONTROL_BYTES:
        raise ValueError("invalid runtime-name control size")
    size = int.from_bytes(control[4:8], "little")
    if not 0 < size <= _CONTROL_BYTES - 64:
        raise ValueError("invalid runtime-name ticket size")
    return _Ticket.model_validate_json(control[64 : 64 + size])


def _attach(ticket: _Ticket) -> _Recorder:
    directory = _directory()
    if ticket.token != os.environ["MUTMUT_CLEAN_NAMES_TOKEN"]:
        raise ValueError("runtime-name ticket token mismatch")
    with _path(directory, ticket, "control").open("r+b") as stream:
        control = mmap.mmap(stream.fileno(), _CONTROL_BYTES, access=mmap.ACCESS_WRITE)
    try:
        if _read_ticket(control) != ticket or control[0] != _UNREADY:
            raise ValueError("runtime-name ticket already claimed or mismatched")
        recorder = _Recorder(directory=directory, ticket=ticket, control=control)
        control[8:16] = os.getpid().to_bytes(8, "little")
        control[0] = _READY
        # Permanent bootstrap bit, independent of later publication states.
        control[1] = 1
        return recorder
    except BaseException:
        control.close()
        raise


def _ensure_recorder() -> _Recorder:
    if _recorder is None:
        # A plain Popen child cannot borrow the parent identity. Its first
        # staged call explicitly invalidates the phase; harmless helpers never
        # enter this path. MP children attach before their main import.
        directory = _directory()
        (directory / f"unsupported-{os.getpid()}.invalid").touch(exist_ok=True)
        raise RuntimeError("unregistered clean runtime-name participant")
    return _recorder


def _invalidate(recorder: _Recorder) -> None:
    recorder.invalid = True
    try:
        recorder.control[0] = _INVALID
    except ValueError, OSError:
        # Independent file evidence also covers a prematurely closed view.
        _path(recorder.directory, recorder.ticket, "invalid").touch(exist_ok=True)


def _begin(recorder: _Recorder) -> None:
    if recorder.closed or recorder.invalid:
        raise RuntimeError("clean runtime-name proof is closed or invalid")
    recorder.control[0] = _PENDING


def _write_part(path: Path, model: BaseModel) -> None:
    raw = model.model_dump_json().encode("utf-8") + b"\n"
    with path.open("ab") as stream:
        stream.write(raw)


def _append(recorder: _Recorder, entry: _Entry) -> None:
    _write_part(_path(recorder.directory, recorder.ticket, "events"), entry)
    used = int.from_bytes(recorder.control[16:24], "little")
    used += len(entry.model_dump_json().encode("utf-8")) + 1
    if used > _MAX_BYTES:
        raise ValueError("runtime-name proof exceeds 16 MiB")
    recorder.control[16:24] = used.to_bytes(8, "little")


def record_runtime_name(name: str) -> None:
    """Publish an actual original-call identity before the call executes.

    Args:
        name: Original function module and mangled name used by dispatch.
    """
    with _LOCK:
        recorder = _ensure_recorder()
        try:
            if recorder.closed or recorder.invalid:
                raise RuntimeError("clean runtime-name proof is closed or invalid")
            if name in recorder.names:
                return
            _begin(recorder)
            if len(recorder.names) >= _MAX_NAMES:
                raise ValueError("runtime-name proof name limit exceeded")
            _append(recorder, _Entry(kind="name", value=name))
            recorder.names.add(name)
            recorder.control[0] = _READY
        except BaseException:
            _invalidate(recorder)
            raise


def _finish_at_exit() -> None:
    with _LOCK:
        recorder = _recorder
        if recorder is None or recorder.closed:
            return
        try:
            if recorder.invalid or (
                recorder.ticket.parent_participant_id is None and _exit_code != 0
            ):
                _invalidate(recorder)
            else:
                recorder.control[0] = _CLOSED
        finally:
            recorder.closed = True
            recorder.control.close()


def finish_pytest(exit_code: int) -> None:
    """Bind the root pytest outcome before interpreter shutdown."""
    global _exit_code
    with _LOCK:
        _exit_code = exit_code


def start_pytest() -> None:
    """Initialize root evidence before initial project conftest imports."""
    global _recorder
    with _LOCK:
        if _recorder is not None:
            raise RuntimeError("duplicate clean pytest root")
        directory = _directory()
        ticket = _create_ticket(directory, None)
        (directory / "parent.json").write_text(ticket.model_dump_json(), encoding="utf-8")
        _recorder = _attach(ticket)
    install_spawn_observer()


def _resume_spawn(raw_ticket: str) -> None:
    global _recorder
    ticket = _Ticket.model_validate_json(raw_ticket)
    if ticket.parent_participant_id is None or _recorder is not None:
        raise ValueError("invalid child runtime-name ticket")
    _recorder = _attach(ticket)
    install_spawn_observer()


class _SpawnObserver(BaseModel):
    ticket: _Ticket

    def __reduce__(self) -> tuple[Callable[[str], None], tuple[str]]:
        return _resume_spawn, (self.ticket.model_dump_json(),)


def _wait_bootstrap(ticket: _Ticket) -> None:
    with (
        _path(_directory(), ticket, "control").open("r+b") as stream,
        mmap.mmap(stream.fileno(), _CONTROL_BYTES, access=mmap.ACCESS_READ) as control,
    ):
        deadline = time.monotonic() + 30
        while control[1] != 1:
            if control[0] == _INVALID or time.monotonic() >= deadline:
                raise RuntimeError("clean runtime-name child bootstrap incomplete")
            time.sleep(0.005)
        if _read_ticket(control) != ticket or not int.from_bytes(control[8:16], "little"):
            raise ValueError("clean runtime-name child identity mismatch")


def install_spawn_observer() -> None:
    """Bind MP tickets before OS creation and confirm bootstrap before return.

    The CPython 3.14.7 preparation marker is reconstructed before child main
    imports. Chaining preserves an existing coverage observer. The fixed
    control map never resizes while the parent waits for its bootstrap bit.
    """
    global _installed
    if _installed:
        return
    _installed = True
    original_prepare = cast("Callable[[str], dict[str, object]]", spawn.get_preparation_data)
    original_start = process.BaseProcess.start

    def prepare(name: str) -> dict[str, object]:
        data = original_prepare(name)
        with _LOCK:
            recorder = _ensure_recorder()
            try:
                _begin(recorder)
                if len(recorder.children) >= _MAX_PARTICIPANTS:
                    raise ValueError("runtime-name child limit exceeded")
                ticket = _create_ticket(recorder.directory, recorder.ticket)
                _append(recorder, _Entry(kind="child", value=ticket.participant_id))
                recorder.children.add(ticket.participant_id)
                recorder.control[0] = _READY
                _start_ticket.set(ticket)
            except BaseException:
                _invalidate(recorder)
                raise
        # CPython-owned preparation transport, not an application data model.
        data["mutmut_win_clean_names_observer"] = _SpawnObserver(ticket=ticket)
        return data

    def start(child: process.BaseProcess) -> None:
        with _start_ticket.set(None):
            original_start(child)
            ticket = _start_ticket.get()
            if ticket is None:
                raise RuntimeError("clean child started without a runtime-name ticket")
            _wait_bootstrap(ticket)

    spawn.get_preparation_data = prepare
    # Install the CPython method hook dynamically; preserve its ordinary API.
    setattr(process.BaseProcess, "start", start)  # noqa: B010
    atexit.register(_finish_at_exit)


def _read_part(directory: Path, ticket: _Ticket) -> tuple[int, list[_Entry]]:
    with (
        _path(directory, ticket, "control").open("rb") as stream,
        mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as control,
    ):
        identity = _read_ticket(control)
        state = control[0]
        process_id = int.from_bytes(control[8:16], "little")
        used = int.from_bytes(control[16:24], "little")
        if identity != ticket or control[1] != 1 or process_id <= 0:
            raise ValueError("runtime-name participant identity mismatch")
        if state not in {_READY, _CLOSED}:
            raise ValueError("runtime-name participant is incomplete")
        if ticket.parent_participant_id is None and state != _CLOSED:
            raise ValueError("runtime-name root completion missing")
        if used > _MAX_BYTES:
            raise ValueError("runtime-name part exceeds limit")
    with _path(directory, ticket, "events").open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    if len(raw) != used or (raw and not raw.endswith(b"\n")):
        raise ValueError("runtime-name partial event publication")
    return process_id, [_Entry.model_validate_json(line) for line in raw.split(b"\n") if line]


def collect_runtime_names(directory: Path, token: str) -> frozenset[str]:
    """Validate the complete rooted ticket graph after process-tree cleanup.

    Args:
        directory: Fresh external directory owned by this clean phase.
        token: Nonce supplied exclusively to the phase process environment.

    Returns:
        Actual clean-call names, including a valid empty observation.

    Raises:
        OSError: Evidence cannot be read.
        ValueError: Evidence is missing, stale, malformed, or incomplete.
    """
    files: set[Path] = set()
    total_bytes = 0
    for path in directory.iterdir():
        files.add(path)
        total_bytes += path.stat().st_size
        if len(files) > 2 * _MAX_PARTICIPANTS + 1 or total_bytes > _MAX_BYTES:
            raise ValueError("runtime-name proof resource limit exceeded")
    parent_path = directory / "parent.json"
    parent = _Ticket.model_validate_json(parent_path.read_bytes())
    if parent.token != token or parent.parent_participant_id is not None:
        raise ValueError("runtime-name parent ticket mismatch")
    expected = {parent_path}
    pending = [parent]
    participants: set[str] = set()
    names: set[str] = set()
    while pending:
        ticket = pending.pop()
        if ticket.participant_id in participants:
            raise ValueError("runtime-name duplicate participant")
        participants.add(ticket.participant_id)
        pid, entries = _read_part(directory, ticket)
        expected.update((_path(directory, ticket, "control"), _path(directory, ticket, "events")))
        for entry in entries:
            if entry.kind == "name":
                names.add(entry.value)
                if len(names) > _MAX_NAMES:
                    raise ValueError("runtime-name name limit exceeded")
            else:
                # Model validation precedes using the supplied identity in a path.
                child = _Ticket(
                    participant_id=entry.value,
                    parent_participant_id=ticket.participant_id,
                    issuer_pid=pid,
                    token=token,
                )
                pending.append(child)
    if files != expected:
        raise ValueError("runtime-name unexpected or invalid participant evidence")
    return frozenset(names)
