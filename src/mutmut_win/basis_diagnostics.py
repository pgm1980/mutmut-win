"""Opt-in, buffered observations of the canonical execution-basis hash stream.

This module never supplies an authority decision. Observed hashes forward the
original bytes to hashlib; diagnostic tokens use a private per-session HMAC key
so a report does not expose low-entropy environment values. Tokens can only be
compared within one session. Recording failures are reported after the run and
must not replace a result or an exception from the operation being observed.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import inspect
import json
import os
import secrets
import sys
import threading
import time
from collections import defaultdict
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_SESSION: ContextVar[_Collector | None] = ContextVar("basis_diagnostic_session", default=None)
_CAPTURE: ContextVar[_Capture | None] = ContextVar("basis_diagnostic_capture", default=None)
_FRAME: ContextVar[int | None] = ContextVar("basis_diagnostic_frame", default=None)
_RESULT_FIELDS = (
    "digest",
    "complete",
    "core_digest",
    "core_complete",
    "fingerprint",
    "reuse_safe",
    "core_reuse_safe",
)


def _stamp() -> dict[str, Any]:
    return {"utc": datetime.now(UTC).isoformat(), "monotonic_ns": time.monotonic_ns()}


def _safe(value: Any) -> Any:
    """Accept explicit diagnostic fields, without arbitrary repr/str calls."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items() if isinstance(key, str)}
    return {"type": type(value).__name__}


def _result(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    fields = {name: _safe(getattr(value, name)) for name in _RESULT_FIELDS if hasattr(value, name)}
    return fields or {"type": type(value).__name__}


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _validate_output(path: Path, roots: list[Path]) -> Path:
    if not path.is_absolute():
        raise ValueError("basis diagnostics requires an absolute output path")
    if not path.parent.is_dir():
        raise ValueError("basis diagnostics output parent must already exist")
    resolved = path.parent.resolve(strict=True) / path.name
    if path.exists() or path.is_symlink() or resolved.exists() or resolved.is_symlink():
        raise ValueError("basis diagnostics output must be a new file")
    for root in roots:
        if _within(resolved, root.resolve(strict=False)):
            raise ValueError("basis diagnostics output is inside an execution input root")
    return resolved


class _Capture:
    def __init__(self, collector: _Collector, sequence: int) -> None:
        self.collector = collector
        self.frames: list[dict[str, Any]] = []
        self.streams: list[dict[str, Any]] = []
        self.tokens: dict[tuple[int, int], Any] = {}
        self.hash_entries: dict[tuple[int, int], dict[str, Any]] = {}
        self.occurrences: dict[tuple[int | None, str, str], int] = defaultdict(int)
        self.report: dict[str, Any] = {
            "sequence": sequence,
            "pid": os.getpid(),
            "thread_id": threading.get_ident(),
            "start": _stamp(),
            "status": "partial",
            "frames": self.frames,
            "streams": self.streams,
        }

    def begin_frame(self, kind: str, identity: dict[str, Any], parent: int | None) -> int:
        identity = _safe(identity)
        key = (parent, kind, json.dumps(identity, sort_keys=True))
        occurrence = self.occurrences[key]
        self.occurrences[key] += 1
        frame_id = len(self.frames)
        segment = {"kind": kind, "identity": identity, "occurrence": occurrence}
        parent_path = [] if parent is None else self.frames[parent]["path"]
        self.frames.append(
            {
                "id": frame_id,
                "parent_id": parent,
                "kind": kind,
                "identity": identity,
                "occurrence": occurrence,
                "path": [*parent_path, segment],
                "status": "partial",
                "events": [],
                "hashes": [],
            }
        )
        return frame_id

    def begin_stream(self, stream: str) -> int:
        stream_id = len(self.streams)
        self.streams.append(
            {
                "id": stream_id,
                "name": stream,
                "updates": 0,
                "bytes": 0,
                "hmac": None,
                "attribution": [],
            }
        )
        self.tokens[(-1, stream_id)] = hmac.new(self.collector.key, digestmod="sha256")
        return stream_id

    def record_update(self, stream_id: int, frame_id: int, data: bytes) -> None:
        stream = self.streams[stream_id]
        stream["updates"] += 1
        stream["bytes"] += len(data)
        self.tokens[(-1, stream_id)].update(data)
        attribution = stream["attribution"]
        if not attribution or attribution[-1]["frame_id"] != frame_id:
            attribution.append({"frame_id": frame_id, "updates": 0, "bytes": 0})
        attribution[-1]["updates"] += 1
        attribution[-1]["bytes"] += len(data)
        key = (frame_id, stream_id)
        if key not in self.tokens:
            self.tokens[key] = hmac.new(self.collector.key, digestmod="sha256")
            entry = {
                "stream_id": stream_id,
                "stream": stream["name"],
                "updates": 0,
                "bytes": 0,
                "hmac": None,
            }
            self.frames[frame_id]["hashes"].append(entry)
            self.hash_entries[key] = entry
        token = self.tokens[key]
        token.update(data)
        entry = self.hash_entries[key]
        entry["updates"] += 1
        entry["bytes"] += len(data)

    def finalize(self) -> None:
        for (frame_id, stream_id), token in self.tokens.items():
            if frame_id == -1:
                self.streams[stream_id]["hmac"] = token.hexdigest()
            else:
                self.hash_entries[(frame_id, stream_id)]["hmac"] = token.hexdigest()


class _Collector:
    def __init__(self, output: Path) -> None:
        self.roots = [
            Path.cwd(),
            Path(sys.prefix),
            Path(sys.base_prefix),
            Path(sys.executable).parent,
        ]
        self.output = _validate_output(output, self.roots)
        self.key = secrets.token_bytes(32)
        self.session_id = secrets.token_hex(16)
        self.start = _stamp()
        self.captures: list[_Capture] = []
        self.capture_lock = threading.Lock()
        self.errors: list[dict[str, Any]] = []
        self.publication_blocked = False

    def fault(self, operation: str, error: BaseException) -> None:
        self.errors.append({"operation": operation, "exception_type": type(error).__name__})

    def begin_capture(self) -> _Capture:
        with self.capture_lock:
            capture = _Capture(self, len(self.captures) + 1)
            self.captures.append(capture)
            return capture

    def publish(self) -> None:
        if self.publication_blocked:
            raise ValueError("basis diagnostics output overlaps an observed execution input")
        _validate_output(self.output, self.roots)
        captures = [item.report for item in self.captures]
        report = {
            "schema": 1,
            "session_id": self.session_id,
            "pid": os.getpid(),
            "start": self.start,
            "end": _stamp(),
            "diagnostics_complete": bool(captures)
            and not self.errors
            and all(item["status"] == "complete" for item in captures),
            "token_scope": "private per-session HMAC-SHA256 key; key is not exported",
            "errors": self.errors,
            # Parent/frame ids retain the complete hierarchy without repeating
            # every ancestor identity once for every descendant in the report.
            "snapshots": [
                {
                    **capture,
                    "frames": [
                        {key: value for key, value in frame.items() if key != "path"}
                        for frame in capture["frames"]
                    ],
                }
                for capture in captures
            ],
            "transitions": [_transition(left, right) for left, right in pairwise(captures)],
        }
        encoded = json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
        # Exclusive creation protects existing evidence. No writes occur during a snapshot.
        with self.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)


def _frame_signature(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": frame["status"],
        "result": frame.get("result"),
        "events": frame["events"],
        "hashes": [
            {key: value for key, value in item.items() if key != "stream_id"}
            for item in frame["hashes"]
        ],
    }


def _transition(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    def index(capture: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {json.dumps(frame["path"], sort_keys=True): frame for frame in capture["frames"]}

    old, new = index(left), index(right)
    changes: list[dict[str, Any]] = []
    for key in sorted(old.keys() | new.keys()):
        before, after = old.get(key), new.get(key)
        before_value = _frame_signature(before) if before is not None else None
        after_value = _frame_signature(after) if after is not None else None
        if before_value != after_value:
            changes.append(
                {
                    "path": json.loads(key),
                    "before_frame_id": before["id"] if before else None,
                    "after_frame_id": after["id"] if after else None,
                    "before": before_value,
                    "after": after_value,
                }
            )

    def streams(capture: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "name": stream["name"],
                "updates": stream["updates"],
                "bytes": stream["bytes"],
                "hmac": stream["hmac"],
                "attribution": [
                    {
                        "path": capture["frames"][item["frame_id"]]["path"],
                        "updates": item["updates"],
                        "bytes": item["bytes"],
                    }
                    for item in stream["attribution"]
                ],
            }
            for stream in capture["streams"]
        ]

    return {
        "from_sequence": left["sequence"],
        "to_sequence": right["sequence"],
        "result_changed": left.get("result") != right.get("result"),
        "status_changed": left["status"] != right["status"],
        "frame_changes": changes,
        "stream_observations_changed": streams(left) != streams(right),
    }


def _fault(operation: str, error: BaseException) -> None:
    collector = _SESSION.get()
    if collector is not None:
        with contextlib.suppress(Exception):
            collector.fault(operation, error)


def is_observing() -> bool:
    """Whether this context is currently capturing a canonical basis snapshot."""
    return _CAPTURE.get() is not None


@contextlib.contextmanager
def diagnostics_session(output_path: Path) -> Iterator[_Collector]:
    """Observe snapshots and publish once after execution, never inside the run.

    Invalid output configuration raises before execution. Recording/publication
    errors after entry are explicit on stderr and do not affect execution.
    """
    if _SESSION.get() is not None:
        raise ValueError("basis diagnostics sessions cannot be nested")
    collector = _Collector(output_path)
    token = _SESSION.set(collector)
    try:
        yield collector
    finally:
        try:
            collector.publish()
            if collector.errors:
                print(
                    "Basis diagnostics incomplete: observation errors recorded in report.",
                    file=sys.stderr,
                )
        except Exception as error:
            with contextlib.suppress(Exception):
                print(
                    f"Basis diagnostics could not be published ({type(error).__name__}).",
                    file=sys.stderr,
                )
        finally:
            _SESSION.reset(token)


def register_input_root(path: Path) -> None:
    """Register an exact measured root, without broadening to its parent."""
    collector = _SESSION.get()
    if collector is None:
        return
    try:
        resolved = path.resolve(strict=False)
        if resolved not in collector.roots:
            collector.roots.append(resolved)
        if _within(collector.output, resolved):
            collector.publication_blocked = True
            collector.fault("output_overlaps_input", ValueError())
    except Exception as error:
        collector.publication_blocked = True
        _fault("register_input_root", error)


def record_event(kind: str, **safe_fields: Any) -> None:
    """Record explicitly safe fields; callers must never pass raw environment values."""
    capture, frame_id = _CAPTURE.get(), _FRAME.get()
    if capture is None or frame_id is None:
        return
    try:
        capture.frames[frame_id]["events"].append({"kind": kind, **_safe(safe_fields)})
    except Exception as error:
        _fault("record_event", error)


def record_token(kind: str, value: bytes, **safe_identity: Any) -> None:
    """Record a keyed token from an already read value, never the value itself."""
    capture = _CAPTURE.get()
    if capture is None:
        return
    try:
        token = hmac.new(capture.collector.key, value, digestmod="sha256").hexdigest()
        record_event(kind, **safe_identity, token=token)
    except Exception as error:
        _fault("record_token", error)


def record_error(operation: str, error: BaseException, **safe_fields: Any) -> None:
    """Record an observed error type and numeric OS codes, never its message."""
    try:
        fields = {"operation": operation, "exception_type": type(error).__name__, **safe_fields}
        for name in ("errno", "winerror"):
            value = getattr(error, name, None)
            if isinstance(value, int):
                fields[name] = value
        record_event("error", **fields)
    except Exception as diagnostic_error:
        _fault("record_error", diagnostic_error)


@contextlib.contextmanager
def component_scope(kind: str, **safe_identity: Any) -> Iterator[None]:
    """Attribute nested hash updates to an ordered component occurrence."""
    capture = _CAPTURE.get()
    if capture is None:
        yield
        return
    token = None
    frame_id = None
    try:
        frame_id = capture.begin_frame(kind, safe_identity, _FRAME.get())
        token = _FRAME.set(frame_id)
    except Exception as error:
        _fault("begin_component", error)
    try:
        yield
    except BaseException as error:
        record_error("component", error)
        raise
    else:
        try:
            if frame_id is not None:
                capture.frames[frame_id]["status"] = "complete"
        except Exception as error:
            _fault("end_component", error)
    finally:
        if token is not None:
            _FRAME.reset(token)


def component[**P, R](
    kind: str, identity: tuple[str, ...] = ()
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Observe a helper; only explicitly selected bound arguments identify it."""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(function)

        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            if not is_observing():
                return function(*args, **kwargs)
            fields: dict[str, Any] = {}
            try:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                fields = {
                    name: bound.arguments[name] for name in identity if name in bound.arguments
                }
            except Exception as error:
                _fault("component_identity", error)
            with component_scope(kind, **fields):
                result = function(*args, **kwargs)
                try:
                    capture, frame_id = _CAPTURE.get(), _FRAME.get()
                    if capture is not None and frame_id is not None:
                        capture.frames[frame_id]["result"] = _result(result)
                except Exception as error:
                    _fault("component_result", error)
                return result

        return wrapped

    return decorate


def snapshot[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Capture one complete canonical call, including its returned completeness."""

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        collector = _SESSION.get()
        if collector is None:
            return function(*args, **kwargs)
        capture_token = frame_token = None
        capture = None
        try:
            capture = collector.begin_capture()
            capture_token = _CAPTURE.set(capture)
            frame_token = _FRAME.set(capture.begin_frame("snapshot", {}, None))
        except Exception as error:
            _fault("begin_snapshot", error)
            if capture_token is not None:
                _CAPTURE.reset(capture_token)
                capture_token = None
        try:
            result = function(*args, **kwargs)
            try:
                if capture is not None:
                    capture.report["result"] = _result(result)
                    capture.report["status"] = "complete"
                    capture.frames[0]["status"] = "complete"
            except Exception as error:
                _fault("snapshot_result", error)
            return result
        except BaseException as error:
            record_error("snapshot", error)
            raise
        finally:
            try:
                if capture is not None:
                    capture.finalize()
                    capture.report["end"] = _stamp()
            except Exception as error:
                _fault("end_snapshot", error)
            finally:
                if frame_token is not None:
                    _FRAME.reset(frame_token)
                if capture_token is not None:
                    _CAPTURE.reset(capture_token)

    return wrapped


class _ObservedHash:
    def __init__(self, real: Any, capture: _Capture, stream: str) -> None:
        self._real = real
        self._capture = capture
        self._stream_id = capture.begin_stream(stream)

    @property
    def digest_size(self) -> int:
        return int(self._real.digest_size)

    @property
    def block_size(self) -> int:
        return int(self._real.block_size)

    @property
    def name(self) -> str:
        return str(self._real.name)

    def update(self, data: bytes) -> None:
        self._real.update(data)
        try:
            frame_id = _FRAME.get() if _CAPTURE.get() is self._capture else 0
            self._capture.record_update(
                self._stream_id, frame_id if frame_id is not None else 0, data
            )
        except Exception as error:
            _fault("hash_update", error)

    def hexdigest(self) -> str:
        return str(self._real.hexdigest())

    def digest(self) -> bytes:
        return bytes(self._real.digest())


def observed_sha256(data: bytes = b"", *, stream: str) -> Any:
    """Create a canonical SHA-256, forwarding its exact bytes when observed."""
    capture = _CAPTURE.get()
    if capture is None:
        return hashlib.sha256(data)
    real = hashlib.sha256()
    try:
        observed = _ObservedHash(real, capture, stream)
    except Exception as error:
        _fault("begin_hash_stream", error)
        real.update(data)
        return real
    if data:
        observed.update(data)
    return observed
