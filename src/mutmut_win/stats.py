"""Stats persistence for mutmut-win.

Handles loading and saving the per-test timing and trampoline-hit data
collected during a stats run (``MUTANT_UNDER_TEST=stats``).  Also provides
``collect_or_load_stats`` which either loads a cached result or triggers
a fresh collection via the pytest runner.

Ported from mutmut 3.5.0 ``__main__.py`` with the following adaptations:
- All global state replaced by an explicit ``MutmutStats`` dataclass.
- ``Path`` objects used throughout; ``encoding='utf-8'`` on every file I/O.
- Collection runs pytest as a SUBPROCESS with an injected plugin; the
  plugin-written ``mutmut-stats.json`` is the single source of truth.
- ``collect_or_load_stats`` updates incrementally: new tests trigger a
  re-collection, removed tests trigger a cache cleanup (issue #99).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import stat
import sys
import sysconfig
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.atomic_file import atomic_write_bytes
from mutmut_win.basis_diagnostics import (
    component,
    component_scope,
    is_observing,
    observed_sha256,
    record_error,
    record_event,
    record_token,
    register_input_root,
    snapshot,
)
from mutmut_win.constants import (
    WORKSPACE_EXCLUDED_DIR_NAMES,
    WORKSPACE_RECURSIVE_EXCLUDED_DIR_NAMES,
)
from mutmut_win.file_setup import _configured_entry_boundary, _is_dotenv_name
from mutmut_win.gitignore_boundary import GitignoreBoundary

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import BinaryIO

    from mutmut_win.config import MutmutConfig
    from mutmut_win.runner import PytestRunner

#: Delays between bounded re-open attempts for transient Windows sharing
#: violations in ``_open_for_hash``.
_CONTEXT_OPEN_RETRY_DELAYS: tuple[float, ...] = (0.01, 0.05, 0.1, 0.25, 0.5)

#: ``ERROR_SHARING_VIOLATION``: another process holds the file without
#: ``FILE_SHARE_READ`` while we try to open it for hashing.  Range locks
#: (winerror 33) surface on read, not open, and stay covered by the
#: orchestrator's snapshot re-observation instead of this open-level retry.
_SHARING_VIOLATION_WINERROR: int = 32


def _open_for_hash(path: Path) -> BinaryIO:
    """Open ``path`` for hashing, retrying only transient sharing violations.

    A freshly published or concurrently scanned input file can be briefly
    held without ``FILE_SHARE_READ`` (antivirus, indexer); such opens are
    retried with bounded delays.  Every other ``PermissionError`` (for
    example ACL denial, winerror 5) and every exhausted retry re-raises so
    the caller keeps its fail-closed ``unreadable:`` verdict.
    """

    last: PermissionError | None = None
    for delay in (None, *_CONTEXT_OPEN_RETRY_DELAYS):
        if delay is not None:
            time.sleep(delay)
        try:
            return path.open("rb")
        except PermissionError as exc:
            if getattr(exc, "winerror", None) != _SHARING_VIOLATION_WINERROR:
                raise
            record_event("hash-open-retry", path=str(path))
            last = exc
    raise last  # type: ignore[misc]


def _atomic_write_json(path: Path, payload: object) -> None:
    """Durably publish JSON through the shared safe workspace writer.

    The destination parent must already exist. Creating it here would follow
    a pre-existing directory symlink/junction before the atomic writer had a
    chance to validate the publication boundary.
    """
    encoded = json.dumps(payload, indent=4).encode("utf-8")
    atomic_write_bytes(path, encoded)


#: Default filename for the CI/CD stats JSON export.
_CICD_STATS_FILENAME = "mutmut-cicd-stats.json"

#: Default filename for the stats JSON cache.
_STATS_FILENAME = "mutmut-stats.json"

#: Persistent timing/mapping state is run-control data, not executable test
#: input.  Keeping it beside the SQLite cache prevents a stats refresh from
#: changing the ``mutants/`` tree that the clean/forced/worker phases execute.
DEFAULT_STATS_DIR = Path(".mutmut-cache")


@dataclass
class MutmutStats:
    """Collected per-test timing and trampoline-hit data.

    Attributes:
        tests_by_mangled_function_name: Maps mangled function names to the set
            of test node IDs that exercise them (populated by the trampoline
            during a stats run).
        duration_by_test: Maps pytest node IDs to their measured duration
            in seconds.
        stats_time: Total CPU time (``process_time``) consumed by the stats
            collection run.
    """

    tests_by_mangled_function_name: dict[str, set[str]] = field(default_factory=dict)
    duration_by_test: dict[str, float] = field(default_factory=dict)
    stats_time: float = 0.0
    # Issue #130 / 360°-B1: SHA-256 per-test-file fingerprints (or
    # ``missing``) recorded with the cache. The wider context fingerprint also
    # covers helpers, conftest files, production source, locks and pytest config.
    test_file_fingerprints: dict[str, str] = field(default_factory=dict)
    # Digest of production/test/helper/config inputs behind this mapping.
    # Legacy caches lack it and are deliberately refreshed once.
    context_fingerprint: str | None = None
    # Absence from a mapping only proves "no tests" when the collector can
    # observe every execution domain. The current subprocess/xdist boundary
    # cannot make that proof, so production caches default to False.
    mapping_is_authoritative: bool = False


def load_stats(mutants_dir: Path = DEFAULT_STATS_DIR) -> MutmutStats | None:
    """Load stats from *mutants_dir*/mutmut-stats.json.

    Args:
        mutants_dir: Directory that contains the stats JSON file.
            Defaults to ``.mutmut-cache/``.

    Returns:
        A populated ``MutmutStats`` instance, or ``None`` if the file does
        not exist, cannot be read, or cannot be parsed.
    """
    stats_path = mutants_dir / _STATS_FILENAME
    try:
        with stats_path.open(encoding="utf-8") as f:
            raw_data: object = json.load(f)
    except (
        OSError,
        JSONDecodeError,
        UnicodeDecodeError,
    ):
        return None
    if not isinstance(raw_data, dict):
        return None
    data: dict[str, object] = raw_data

    raw_by_name = data.pop("tests_by_mangled_function_name", {})
    tests_by_mangled: dict[str, set[str]] = {}
    if not isinstance(raw_by_name, dict):
        return None
    for key, value in raw_by_name.items():
        if (
            not isinstance(key, str)
            or not isinstance(value, list)
            or not all(isinstance(item, str) for item in value)
        ):
            return None
        tests_by_mangled[key] = set(value)

    raw_durations = data.pop("duration_by_test", {})
    duration_by_test: dict[str, float] = {}
    if not isinstance(raw_durations, dict):
        return None
    for key, value in raw_durations.items():
        if (
            not isinstance(key, str)
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            return None
        # M-137: math.isfinite raises OverflowError for integers beyond
        # float range; a hand-edited stats cache with such a value must be
        # rejected, not crash the loader.
        try:
            if not math.isfinite(value) or value < 0:
                return None
        except OverflowError:
            return None
        duration_by_test[key] = float(value)

    raw_time = data.pop("stats_time", 0.0)
    if not isinstance(raw_time, (int, float)) or isinstance(raw_time, bool):
        return None
    try:
        if not math.isfinite(raw_time) or raw_time < 0:
            return None
    except OverflowError:
        return None
    stats_time = float(raw_time)

    raw_fps = data.pop("test_file_fingerprints", {})
    test_file_fingerprints: dict[str, str] = {}
    if isinstance(raw_fps, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw_fps.items()
    ):
        test_file_fingerprints = dict(raw_fps)

    raw_context = data.pop("context_fingerprint", None)
    context_fingerprint = raw_context if isinstance(raw_context, str) else None
    # Observed mappings are diagnostic only for the current collector.  An
    # on-disk authority bit is attacker/user controlled and cannot prove that
    # subprocess, thread, native-launcher, or ``python -S`` hits were observed.
    # Never let a stale or edited cache activate selective testing/no-tests.
    data.pop("mapping_is_authoritative", None)
    mapping_is_authoritative = False

    return MutmutStats(
        tests_by_mangled_function_name=tests_by_mangled,
        duration_by_test=duration_by_test,
        stats_time=stats_time,
        test_file_fingerprints=test_file_fingerprints,
        context_fingerprint=context_fingerprint,
        mapping_is_authoritative=mapping_is_authoritative,
    )


def _fingerprint_test_files(node_ids: object) -> dict[str, str]:
    """Hash every test file behind node IDs, or use the missing sentinel.

    Same derivation and content-hash basis (project root) as the per-mutant
    ``tests_fingerprint`` of issue #119 — deliberately one semantics for
    both reuse and mapping invalidation (issue #130 / 360°-B1).
    """
    fingerprints: dict[str, str] = {}
    for node_id in node_ids:  # type: ignore[attr-defined]
        file_part = str(node_id).split("::", 1)[0]
        if file_part in fingerprints:
            continue
        try:
            fingerprints[file_part] = hashlib.sha256(Path(file_part).read_bytes()).hexdigest()
        except OSError:
            fingerprints[file_part] = "missing"
    return fingerprints


_CONTEXT_SKIP_DIRS = WORKSPACE_RECURSIVE_EXCLUDED_DIR_NAMES
_CONTEXT_ROOT_SKIP_DIRS = WORKSPACE_EXCLUDED_DIR_NAMES
_IMPORT_CONTEXT_SKIP_DIRS = frozenset({"__pycache__"})
# A prefixed context remains useful for current-run diagnostics, but never
# becomes a capability for reusing an older verdict or authorizing CI export.
# Authoritative run evidence is persisted only when the complete execution
# basis was observable.
_NO_REUSE_CONTEXT_PREFIX = "no-reuse:"


@dataclass(frozen=True)
class _DependencyBasis:
    """Digest plus completeness proof for the active Python distributions."""

    digest: str
    reuse_safe: bool
    core_reuse_safe: bool = True


@dataclass(frozen=True)
class _StatsContextEvidence:
    """Combined context plus the independently observable project core."""

    fingerprint: str
    core_digest: str
    complete: bool
    core_complete: bool


@dataclass(frozen=True)
class RunBasisEvidence:
    """Digest plus proof that the complete execution basis was observable."""

    digest: str
    complete: bool
    # ``core_digest`` covers source, tests, config, explicit trees and every
    # effective import root contained by the project.  It lets the
    # orchestrator distinguish a real project-basis change (terminal) from an
    # ambient interpreter/environment change (diagnostic results may be kept,
    # but never reused or exported).  ``None`` is deliberately unclassifiable
    # and therefore retains the historical fail-closed behaviour for older
    # callers and test doubles.
    core_digest: str | None = None
    core_complete: bool = False


class _HashFanout:
    """Forward one canonical byte stream to independent digest domains."""

    def __init__(self, *targets: Any) -> None:
        self._targets = targets

    def update(self, payload: bytes) -> None:
        for target in self._targets:
            target.update(payload)


def context_allows_result_reuse(context_fingerprint: str | None) -> bool:
    """Return whether *context_fingerprint* proves a reusable test basis."""

    return context_fingerprint is not None and not context_fingerprint.startswith(
        _NO_REUSE_CONTEXT_PREFIX
    )


def _skip_context_file(name: str) -> bool:
    """Exclude only mutable coordination files from the execution basis.

    Dotenv files remain absent from executable staging so their secret values
    are never copied into ``mutants/``.  Their bytes can still influence test
    startup through upward dotenv discovery, however, so the one-way context
    digest must bind them just like any other runtime input.
    """

    folded = name.casefold()
    return folded in {".mutmut-win.run.lock", ".mutmut-win.run.lock.guard"} or (
        folded.startswith(".mutmut-win-") and folded.endswith((".run.lock", ".run.lock.guard"))
    )


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    """Compare identity and mutation-sensitive fields of two file stats."""

    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


@component("metadata", identity=("include_timestamps", "include_link_count"))
def _hash_runtime_metadata(
    hasher: Any,
    metadata: os.stat_result,
    *,
    include_timestamps: bool,
    include_link_count: bool,
) -> None:
    """Bind metadata that Python/tests can observe without hashing access time.

    File bytes alone do not describe the execution basis: tests commonly
    inspect writability, timestamps and Windows file attributes. Timestamps
    and link count are useful for an in-run executable-staging snapshot
    (including create-then-delete ABA), but generated sidecars are deliberately
    rewritten between their generation-only and rich result forms. Cross-run
    context fingerprints omit the derived tree's timestamps and every regular
    file's externally mutable hardlink count while still binding content,
    topology, permissions and Windows attributes.
    """

    is_directory = stat.S_ISDIR(metadata.st_mode)
    fields = ["st_mode"]
    # For a stable project/import fingerprint, directory topology is already
    # represented by the retained path entries.  Binding directory allocation
    # size or link count would indirectly reintroduce deliberately excluded
    # tool state (on Windows, creating `.mutmut-cache` can change the parent
    # size from 0 to 4096).  The strict in-run staging snapshot opts into the
    # full metadata set below and therefore still detects directory ABA.
    if include_link_count:
        fields.append("st_nlink")
    if not is_directory or include_timestamps:
        fields.append("st_size")
    if include_timestamps:
        fields.extend(("st_mtime_ns", "st_ctime_ns", "st_birthtime_ns"))
    fields.extend(("st_file_attributes", "st_reparse_tag"))
    for field_name in fields:
        if not hasattr(metadata, field_name):
            continue
        record_event("metadata-field", field=field_name, value=getattr(metadata, field_name))
        hasher.update(field_name.encode("ascii"))
        hasher.update(b"=")
        hasher.update(str(getattr(metadata, field_name)).encode("ascii", errors="replace"))
        hasher.update(b"\0")


def _same_path_binding(
    left: os.stat_result,
    right: os.stat_result,
    *,
    compare_link_count: bool,
) -> bool:
    """Compare two handles without treating unrelated aliases as path drift.

    Cross-run context snapshots deliberately ignore ``st_nlink``.  uv shares
    installed package files through hardlinks, so creating or deleting an
    unrelated environment changes the link count of this environment's files
    without changing their binding or executable bytes.  The strict in-run
    staging snapshot opts back into the comparison below.
    """

    fields = ["st_dev", "st_ino", "st_mode"]
    if compare_link_count:
        fields.append("st_nlink")
    fields.extend(("st_size", "st_mtime_ns"))
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _absolute_lexical_path(path: Path) -> Path:
    """Return an absolute path without dereferencing its final binding."""

    # ``Path.resolve`` dereferences the binding we deliberately re-open below.
    return Path(os.path.abspath(os.fspath(path)))  # noqa: PTH100


def _record_file_observation(role: str, metadata: os.stat_result) -> None:
    if is_observing():
        record_event(
            "file-observation",
            role=role,
            fields={
                field_name: getattr(metadata, field_name)
                for field_name in (
                    "st_dev",
                    "st_ino",
                    "st_mode",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                )
            },
        )


@component("file", identity=("path", "label", "hash_timestamps", "hash_link_count"))
def _hash_context_file(
    hasher: Any,
    path: Path,
    *,
    label: str,
    seen: set[Path],
    hash_timestamps: bool = False,
    hash_link_count: bool = False,
) -> bool:
    """Hash one regular file and verify its path/identity stayed stable.

    Timestamps stay out of the digest by default (issue #195 RC-3): a
    content-identical ``touch`` must not invalidate the reuse basis.  The
    during-hash identity checks below are independent of what is hashed.
    """

    register_input_root(path.parent)
    hasher.update(label.encode("utf-8", errors="surrogateescape"))
    hasher.update(b"\0")
    try:
        absolute = _absolute_lexical_path(path)
        hasher.update(str(absolute).encode("utf-8", errors="surrogateescape"))
        hasher.update(b"\0")
        if absolute in seen:
            hasher.update(b"already-hashed\0")
            return True
        with _open_for_hash(absolute) as stream:
            before = os.fstat(stream.fileno())
            _record_file_observation("before", before)
            if not stat.S_ISREG(before.st_mode):
                hasher.update(b"not-regular\0")
                return False
            _hash_runtime_metadata(
                hasher,
                before,
                include_timestamps=hash_timestamps,
                include_link_count=hash_link_count,
            )
            with component_scope("content"):
                while chunk := stream.read(1024 * 1024):
                    hasher.update(chunk)
            after_handle = os.fstat(stream.fileno())
            _record_file_observation("after-handle", after_handle)
            # Re-open the lexical path while the hashed handle is still live.
            # On POSIX this catches rename-and-replace; on Windows it avoids
            # comparing ``fstat().st_ctime`` with the path-stat value, whose
            # semantics differ on current CPython releases.
            with _open_for_hash(absolute) as rebound:
                rebound_handle = os.fstat(rebound.fileno())
                _record_file_observation("rebound", rebound_handle)
        if not _same_file_snapshot(before, after_handle) or not _same_path_binding(
            after_handle,
            rebound_handle,
            compare_link_count=hash_link_count,
        ):
            hasher.update(b"identity-changed\0")
            return False
        hasher.update(b"\0")
        seen.add(absolute)
        return True
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        record_error("hash-file", exc, path=str(path))
        hasher.update(b"unreadable:")
        hasher.update(type(exc).__qualname__.encode("ascii", errors="replace"))
        hasher.update(b"\0")
        return False


def _editable_source_path(direct_url: str) -> Path | None:
    """Return the local source directory named by a PEP 610 editable URL."""

    try:
        payload = json.loads(direct_url)
    except (
        JSONDecodeError,
        TypeError,
    ):
        return None
    if not isinstance(payload, dict):
        return None
    directory_info = payload.get("dir_info")
    if not isinstance(directory_info, dict) or directory_info.get("editable") is not True:
        return None
    raw_url = payload.get("url")
    if not isinstance(raw_url, str):
        return None
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme.casefold() != "file" or parsed.netloc not in {"", "localhost"}:
        return None
    # ``url2pathname`` percent-decodes on Windows already; a leading
    # ``unquote`` would re-decode literal ``%HH`` sequences in the source
    # location (M-060).
    raw_path = urllib.request.url2pathname(parsed.path)
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return Path(raw_path)


def _project_descended_boundary(
    project_boundary: GitignoreBoundary,
    project_root: Path,
    candidate: Path,
) -> GitignoreBoundary | None:
    """Return the normal-descend boundary for a tree inside the project.

    Unlike explicitly configured entries these trees are engine inference
    (effective import paths, editable installs), so the ignore decision of
    every component applies.  Trees outside the project root have no
    project-local gitignore domain and return ``None``.
    """
    try:
        relative = candidate.resolve(strict=False).relative_to(project_root)
    except (OSError, ValueError):  # fmt: skip
        return None
    if str(relative) in {".", ""}:
        return project_boundary
    return project_boundary.descend(*relative.parts)


def _import_root_boundary(
    project_boundary: GitignoreBoundary,
    project_root: Path,
    candidate: Path,
) -> GitignoreBoundary | None:
    """Return the gitignore boundary for one effective import root (M-006).

    Runtime environment trees (a project-internal ``.venv``, ``venv``,
    ``.tox``, ``.nox``, or any tree under the active ``sys.prefix`` /
    ``sys.exec_prefix`` / ``sys.base_prefix`` that is genuinely inside the
    project) are executed in place and never staged; they receive NO
    gitignore boundary so their bytes — including unclaimed modules and
    ``.pth`` files — are fully bound in the digest.  Project core trees
    (staged and copied to ``mutants/``) keep the pruning that protects
    against MBR-2026-09-14-01.

    The sys.prefix exception only applies when the prefix is genuinely
    inside the project root (strictly a descendant, not equal to or an
    ancestor of it); otherwise the project root itself would lose its
    boundary and ignored data trees would regress.

    Runtime roots are classified BEFORE ``covered_by`` deduplication so
    they appear in ``content_roots`` rather than being absorbed as
    content-covered by the project walk.
    """
    try:
        resolved = candidate.resolve(strict=False)
        relative = resolved.relative_to(project_root)
    except (OSError, ValueError):  # fmt: skip
        return None
    if str(relative) in {".", ""}:
        return project_boundary

    # Named tool-environment directories (.venv, venv, .tox, .nox, …) are
    # always runtime trees regardless of which interpreter is active.
    if any(part.casefold() in _CONTEXT_ROOT_SKIP_DIRS for part in relative.parts):
        return None

    # Any active interpreter prefix genuinely inside the project (e.g. a
    # venv named "env") is also a runtime tree.  Only a prefix that is
    # STRICTLY INSIDE the project may lift the boundary (AR-10 / PERF-002):
    # prefixes equal to, above, or outside the project describe an ordinary
    # project import tree (e.g. a project located below an interpreter
    # prefix), whose ignored artifacts must keep pruning instead of
    # becoming new fingerprint drift.
    for prefix_attr in ("prefix", "exec_prefix", "base_prefix"):
        prefix_value = getattr(sys, prefix_attr, None)
        if not prefix_value:
            continue
        try:
            prefix_path = Path(prefix_value).resolve(strict=False)
            if prefix_path == project_root:
                continue
            if not prefix_path.is_relative_to(project_root):
                continue
            if resolved.is_relative_to(prefix_path):
                return None
        except (OSError, ValueError):  # fmt: skip
            continue

    return project_boundary.descend(*relative.parts)


def _archive_import_root(absolute: Path) -> tuple[Path, str] | None:
    """Resolve a ZIP (or any regular file) ancestor for a subpath (M-007).

    Walks upward from *absolute* with ``os.stat`` (following symlinks, like
    ``zipimport``) until the first existing ancestor is found.  If it is a
    regular file, returns ``(archive_path, inner_prefix)`` where the prefix
    is the POSIX path below the archive root.  If the first existing
    ancestor is a directory, returns ``None`` (the entry is genuinely
    absent, like the default ``python314.zip``).

    Stat errors other than ``FileNotFoundError`` propagate so the caller
    can record them as import-root errors (reuse_safe=False).
    """
    import stat as stat_module

    parts = absolute.parts
    for depth in range(len(parts) - 1, 0, -1):
        ancestor = Path(*parts[:depth])
        try:
            stat_result = ancestor.stat()
        except FileNotFoundError:
            continue
        if stat_module.S_ISREG(stat_result.st_mode):
            inner_parts = parts[depth:]
            inner_prefix = "/".join(inner_parts)
            return ancestor, inner_prefix
        # First existing ancestor is a directory — genuinely absent.
        return None
    return None


@component("tree", identity=("root", "label_prefix"))
def _hash_context_tree(
    hasher: Any,
    root: Path,
    *,
    label_prefix: str,
    seen: set[Path],
    excluded: set[Path] | None = None,
    skip_dirs: frozenset[str] = _CONTEXT_SKIP_DIRS,
    root_skip_dirs: frozenset[str] = _CONTEXT_ROOT_SKIP_DIRS,
    skip_file: Callable[[Path], bool] | None = None,
    hash_file_timestamps: bool = False,
    hash_directory_timestamps: bool = False,
    hash_link_counts: bool = False,
    ignore_boundary: GitignoreBoundary | None = None,
) -> bool:
    """Hash every stable entry in one runtime-relevant tree.

    ``ignore_boundary`` prunes git-ignored subtrees before any stat or open
    (MBR-2026-09-14-01).  Dotenv files are the deliberate carve-out: they
    stay part of the basis even when git-ignored because tests can read them
    through upward dotenv discovery although they are never staged.
    """

    register_input_root(root)
    reuse_safe = True
    excluded = excluded or set()

    def record_walk_error(_error: OSError) -> None:
        nonlocal reuse_safe
        record_error("walk", _error, root=str(root), path=str(_error.filename))
        reuse_safe = False

    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        record_error("resolve-tree", exc, root=str(root))
        hasher.update(f"{label_prefix}:missing\0".encode("utf-8", errors="surrogateescape"))
        return False
    if not resolved_root.is_dir():
        hasher.update(f"{label_prefix}:not-directory\0".encode())
        return False

    try:
        root_metadata = resolved_root.lstat()
        if not stat.S_ISDIR(root_metadata.st_mode):
            hasher.update(f"{label_prefix}:root-not-directory\0".encode())
            return False
        hasher.update(f"{label_prefix}:.\0".encode("utf-8", errors="surrogateescape"))
        _hash_runtime_metadata(
            hasher,
            root_metadata,
            include_timestamps=hash_directory_timestamps,
            include_link_count=hash_link_counts,
        )
    except OSError as exc:
        record_error("stat-tree", exc, root=str(root))
        hasher.update(f"{label_prefix}:root-unreadable\0".encode())
        return False

    boundaries: dict[Path, GitignoreBoundary | None] = {resolved_root: ignore_boundary}
    for root_str, dirs, files in os.walk(resolved_root, onerror=record_walk_error):
        directory = Path(root_str)
        walk_boundary = boundaries.get(directory)
        retained_dirs: list[str] = []
        for dirname in sorted(dirs):
            folded = dirname.casefold()
            if folded in skip_dirs or (directory == resolved_root and folded in root_skip_dirs):
                continue
            child = directory / dirname
            if walk_boundary is not None and walk_boundary.excludes_directory(dirname):
                continue
            if walk_boundary is not None:
                boundaries[child] = walk_boundary.enter(dirname)
            try:
                is_link = child.is_symlink() or child.is_junction()
            except OSError as exc:
                record_error("directory-link-status", exc, path=str(child))
                is_link = True
            if is_link:
                hasher.update(
                    f"{label_prefix}:unfollowed-directory-link:{dirname}\0".encode(
                        "utf-8", errors="surrogateescape"
                    )
                )
                reuse_safe = False
                continue
            try:
                child_metadata = child.lstat()
                if not stat.S_ISDIR(child_metadata.st_mode):
                    hasher.update(
                        f"{label_prefix}:not-directory:{dirname}\0".encode(
                            "utf-8", errors="surrogateescape"
                        )
                    )
                    reuse_safe = False
                    continue
                relative_child = child.relative_to(resolved_root).as_posix()
                hasher.update(
                    f"{label_prefix}:{relative_child}/\0".encode("utf-8", errors="surrogateescape")
                )
                _hash_runtime_metadata(
                    hasher,
                    child_metadata,
                    include_timestamps=hash_directory_timestamps,
                    include_link_count=hash_link_counts,
                )
            except (OSError, ValueError) as exc:  # fmt: skip
                record_error("stat-directory", exc, path=str(child))
                hasher.update(
                    f"{label_prefix}:directory-unreadable:{dirname}\0".encode(
                        "utf-8", errors="surrogateescape"
                    )
                )
                reuse_safe = False
                continue
            retained_dirs.append(dirname)
        dirs[:] = retained_dirs
        for name in sorted(files):
            if directory == resolved_root and _skip_context_file(name):
                continue
            if (
                walk_boundary is not None
                and walk_boundary.excludes_file(name)
                and not _is_dotenv_name(name)
            ):
                continue
            path = directory / name
            absolute = _absolute_lexical_path(path)
            if absolute in excluded:
                continue
            try:
                relative_path = path.relative_to(resolved_root)
            except ValueError:
                relative_path = Path(path.name)
            if skip_file is not None and skip_file(relative_path):
                continue
            if not _hash_context_file(
                hasher,
                path,
                label=f"{label_prefix}:{relative_path.as_posix()}",
                seen=seen,
                hash_timestamps=hash_file_timestamps,
                hash_link_count=hash_link_counts,
            ):
                reuse_safe = False
    return reuse_safe


def build_staging_context_evidence(
    project_root: Path | None = None,
) -> RunBasisEvidence:
    """Hash all stable bytes that test phases can consume from ``mutants/``."""

    root = (project_root or Path.cwd()).resolve() / "mutants"
    hasher = hashlib.sha256()
    hasher.update(b"stable-generated-staging:v2\0")
    complete = _hash_context_tree(
        hasher,
        root,
        label_prefix="generated-staging",
        seen=set(),
        skip_dirs=frozenset(),
        root_skip_dirs=frozenset(),
        hash_file_timestamps=True,
        hash_directory_timestamps=True,
        hash_link_counts=True,
    )
    return RunBasisEvidence(hasher.hexdigest(), complete)


def _verdict_relevant_environment_entries() -> list[tuple[str, str]]:
    """Return every inherited input that project tests can observe.

    S3-001: arbitrary application variables reach pytest children. No name
    allowlist can establish that an unknown variable is verdict-irrelevant.
    Unchanged environments remain reusable; changed inputs require new verdicts.
    """

    return sorted(
        os.environ.items(),
        key=lambda item: (item[0].casefold(), item[0]),
    )


def _hash_verdict_relevant_environment(hasher: Any) -> None:
    """Bind the full inherited environment without publishing its values.

    S3-001 supersedes the curated #195 environment contract: even a shell
    identifier can be read by a project test. Length-prefixed hashing binds
    absent, empty and changed values distinctly, including unknown names.
    """

    hasher.update(b"verdict-environment:v2\0")
    for name, value in _verdict_relevant_environment_entries():
        encoded_name = name.encode("utf-8", errors="surrogateescape")
        encoded_value = value.encode("utf-8", errors="surrogateescape")
        with component_scope("environment-entry", name=name):
            hasher.update(len(encoded_name).to_bytes(8, "big"))
            hasher.update(encoded_name)
            hasher.update(len(encoded_value).to_bytes(8, "big"))
            hasher.update(encoded_value)
    hasher.update(b"\0")


@component("environment")
def _hash_inherited_environment(hasher: Any) -> None:
    """Bind the complete inherited environment without persisting its values.

    A variable can affect Python startup (for example through ``sitecustomize``)
    before mutmut-win gets a chance to overwrite or remove it at a later child
    boundary.  Consequently no inherited name is safe to exclude from the run
    basis, even when every direct pytest/type-checker launch sanitizes it.
    """

    hasher.update(b"inherited-environment:v2\0")
    entries = sorted(
        os.environ.items(),
        key=lambda item: (item[0].casefold(), item[0]),
    )
    for name, value in entries:
        encoded_name = name.encode("utf-8", errors="surrogateescape")
        encoded_value = value.encode("utf-8", errors="surrogateescape")
        with component_scope("environment-entry", name=name):
            hasher.update(len(encoded_name).to_bytes(8, "big"))
            hasher.update(encoded_name)
            hasher.update(len(encoded_value).to_bytes(8, "big"))
            hasher.update(encoded_value)


@component("runtime")
def _hash_runtime_identity(hasher: Any, seen: set[Path]) -> bool:
    """Bind the interpreter/ABI and executable used to launch test phases."""

    identity = {
        "schema": 2,
        "version": sys.version,
        "implementation": sys.implementation.name,
        "implementation_version": tuple(sys.implementation.version),
        "cache_tag": sys.implementation.cache_tag,
        "hexversion": sys.hexversion,
        "abiflags": getattr(sys, "abiflags", ""),
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "exec_prefix": sys.exec_prefix,
        "base_exec_prefix": sys.base_exec_prefix,
        "platform": sys.platform,
        "byteorder": sys.byteorder,
        "maxsize": sys.maxsize,
        # Command-line startup controls are not encoded in the executable
        # bytes.  They affect this process directly and multiprocessing forwards
        # them to spawned workers, so e.g. ``python`` and ``python -O`` cannot
        # share verdict evidence.
        "flags": repr(sys.flags),
        "xoptions": sorted(
            (str(name), type(value).__qualname__, repr(value))
            for name, value in sys._xoptions.items()
        ),
        # Warning option order is semantic: later filters can override earlier
        # ones. Preserve it rather than sorting.
        "warnoptions": list(sys.warnoptions),
        "pycache_prefix": sys.pycache_prefix,
        "filesystem_encoding": sys.getfilesystemencoding(),
        "filesystem_errors": sys.getfilesystemencodeerrors(),
        "default_encoding": sys.getdefaultencoding(),
        "stdlib": sysconfig.get_path("stdlib"),
        "platstdlib": sysconfig.get_path("platstdlib"),
    }
    if is_observing():
        for name, value in identity.items():
            record_token(
                "runtime-field",
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8", errors="surrogateescape"
                ),
                name=name,
            )
    hasher.update(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(
            "utf-8", errors="surrogateescape"
        )
    )
    hasher.update(b"\0")
    return _hash_context_file(
        hasher,
        Path(sys.executable),
        label="runtime:executable",
        seen=seen,
    )


def _is_generated_import_root(resolved: Path, generated_root: Path) -> bool:
    """Return whether *resolved* is safe generated staging below ``mutants/``.

    The staging tree is a deterministic derivative of the already-hashed
    project/configuration basis. Hashing it again would make the stats file
    recursively part of its own context digest if an explicitly isolated test
    child exposes ``mutants/`` on its import path. Resolved containment is the authority:
    a Windows 8.3/Junction/subst spelling of the workspace can legitimately
    differ lexically while naming the same tree. A redirected staging root is
    still rejected before containment is considered.
    """

    try:
        if generated_root.is_symlink() or generated_root.is_junction():
            return False
        resolved_generated_root = generated_root.resolve(strict=True)
        resolved.relative_to(resolved_generated_root)
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        return False
    return True


def _project_core_relative_path(path: Path, project_root: Path) -> Path | None:
    """Return a safe project-relative execution path, excluding tool state."""

    try:
        resolved = path.resolve(strict=False)
        relative = resolved.relative_to(project_root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):  # fmt: skip
        return None
    if any(part.casefold() in _CONTEXT_SKIP_DIRS for part in relative.parts):
        return None
    return relative


@component("project-import-core", identity=("project_root",))
def _hash_project_import_core(
    hasher: Any,
    project_root: Path,
    seen: set[Path],
    excluded: set[Path],
) -> bool:
    """Bind effective project-contained import bytes to the terminal core.

    The ordinary workspace walk intentionally omits generated/tool roots and
    generic top-level output names.  A generic root such as ``build/`` becomes
    executable input when the project root (or that child) is on ``sys.path``;
    such bytes are project drift, not ambient interpreter drift.  Runtime
    trees such as ``.venv`` and ``.mutmut-cache`` remain excluded recursively.

    Decided M-061/B: this walk deliberately passes NO gitignore boundary even
    though the combined ambient walks prune ignored subtrees.  The executed
    child removes only ``src``/``source`` roots from ``sys.path``
    (``SOURCE_ROOT_NAMES``), so import roots such as a flat-layout project
    root stay importable in place — dropping their ignored-but-readable bytes
    from the terminal core would reclassify real project drift as ambient.
    The asymmetry is fail-closed by design; a symmetric boundary (variant A)
    was rejected, and an isolated source root that only the parent imports is
    still bound whole, conservatively.  Pinned by
    ``tests/unit/test_core_boundary_decision.py``.
    """

    complete = True
    generated_root = _absolute_lexical_path(project_root / "mutants")
    hasher.update(b"effective-project-import-core:v1\0")
    for index, raw_entry in enumerate(sys.path):
        with component_scope("import-entry", index=index):
            try:
                entry = raw_entry if isinstance(raw_entry, str) else os.fspath(raw_entry)
                absolute = _absolute_lexical_path(Path(entry) if entry else project_root)
                register_input_root(absolute)
                record_event("import-path", index=index, entry=entry, path=str(absolute))
            except (OSError, TypeError, ValueError) as exc:
                record_error("project-import-entry", exc, index=index)
                hasher.update(f"entry-error:{index}:{type(exc).__qualname__}\0".encode())
                complete = False
                continue
            relative = _project_core_relative_path(absolute, project_root)
            if relative is None:
                continue
            encoded_entry = entry.encode("utf-8", errors="surrogateescape")
            encoded_absolute = str(absolute).encode("utf-8", errors="surrogateescape")
            hasher.update(index.to_bytes(8, "big"))
            hasher.update(len(encoded_entry).to_bytes(8, "big"))
            hasher.update(encoded_entry)
            hasher.update(len(encoded_absolute).to_bytes(8, "big"))
            hasher.update(encoded_absolute)
            hasher.update(b"\0")
            try:
                resolved = absolute.resolve(strict=True)
                if _is_generated_import_root(resolved, generated_root):
                    hasher.update(b"generated-staging-bound-separately\0")
                    continue
                if resolved.is_file():
                    if resolved in excluded:
                        hasher.update(b"excluded-file\0")
                        continue
                    if not _hash_context_file(
                        hasher,
                        resolved,
                        label=f"project-import:{index}:file",
                        seen=seen,
                    ):
                        complete = False
                    continue
                if not resolved.is_dir():
                    hasher.update(b"unsupported-entry\0")
                    complete = False
                    continue
                root_skip_dirs = frozenset({"mutants"}) if not relative.parts else frozenset()
                if not _hash_context_tree(
                    hasher,
                    resolved,
                    label_prefix=f"project-import:{index}:{relative.as_posix() or '.'}",
                    seen=seen,
                    excluded=excluded,
                    skip_dirs=_CONTEXT_SKIP_DIRS,
                    root_skip_dirs=root_skip_dirs,
                ):
                    complete = False
            except (OSError, RuntimeError, ValueError) as exc:
                record_error("project-import-root", exc, index=index, path=str(absolute))
                hasher.update(f"entry-error:{index}:{type(exc).__qualname__}\0".encode())
                complete = False
    return complete


@component("effective-import-paths", identity=("project_root",))
def _hash_effective_import_paths(
    hasher: Any,
    project_root: Path,
    seen: set[Path],
    covered_trees: tuple[tuple[Path, frozenset[str]], ...],
    excluded: set[Path],
) -> bool:
    """Bind ordered import roots, including unclaimed modules and ``.pth``."""

    reuse_safe = True
    content_roots: dict[Path, frozenset[str]] = {}
    runtime_content_roots: set[Path] = set()
    generated_content_roots: set[Path] = set()
    hasher.update(b"effective-sys-path:v3\0")
    generated_root = _absolute_lexical_path(project_root / "mutants")
    try:
        resolved_project_root = project_root.resolve(strict=True)
    except (OSError, RuntimeError):  # fmt: skip
        resolved_project_root = _absolute_lexical_path(project_root)
    # Gitignore pruning applies only to project-core trees that are staged
    # and copied to mutants/; runtime environments (.venv, sys.prefix inside
    # the project) are executed in place and therefore fully bound (M-006).
    project_boundary = GitignoreBoundary.load(project_root)

    def covered_by(root: Path, candidates: tuple[tuple[Path, frozenset[str]], ...]) -> bool:
        for candidate, skipped_names in candidates:
            try:
                relative = root.relative_to(candidate)
            except ValueError:
                continue
            # An exact root walked with root-level exclusions is only partially
            # covered.  If that same root is effective on sys.path, direct
            # namespace packages such as ``build.runtime_helper`` are
            # executable and must be picked up by a second, overlap-aware walk.
            if not relative.parts:
                return not skipped_names
            if all(part.casefold() not in skipped_names for part in relative.parts):
                return True
        return False

    def partial_coverage_policy(root: Path) -> frozenset[str] | None:
        for candidate, skipped_names in covered_trees:
            if root == candidate and skipped_names:
                return _CONTEXT_SKIP_DIRS
        return None

    for index, raw_entry in enumerate(sys.path):
        with component_scope("import-entry", index=index):
            entry = raw_entry if isinstance(raw_entry, str) else os.fspath(raw_entry)
            absolute = _absolute_lexical_path(Path(entry) if entry else project_root)
            register_input_root(absolute)
            record_event("import-path", index=index, entry=entry, path=str(absolute))
            encoded_entry = entry.encode("utf-8", errors="surrogateescape")
            encoded_absolute = str(absolute).encode("utf-8", errors="surrogateescape")
            hasher.update(index.to_bytes(8, "big"))
            hasher.update(len(encoded_entry).to_bytes(8, "big"))
            hasher.update(encoded_entry)
            hasher.update(len(encoded_absolute).to_bytes(8, "big"))
            hasher.update(encoded_absolute)
            hasher.update(b"\0")
            try:
                if absolute.is_file():
                    try:
                        resolved_file = absolute.resolve(strict=False)
                    except (OSError, RuntimeError):  # fmt: skip
                        resolved_file = absolute
                    if resolved_file in excluded:
                        hasher.update(b"excluded-import-file\0")
                        continue
                    if not _hash_context_file(
                        hasher,
                        absolute,
                        label=f"sys.path:{index}:file",
                        seen=seen,
                    ):
                        reuse_safe = False
                elif absolute.is_dir():
                    resolved = absolute.resolve(strict=True)
                    hasher.update(b"directory\0")
                    if _is_generated_import_root(resolved, generated_root):
                        # Staging is executable state, not an unquestioned
                        # derivative. Hash its stable bytes once below so stale
                        # mirrors and post-generation tampering invalidate reuse;
                        # mutable stats/verdict outputs are deliberately omitted.
                        resolved_generated = generated_root.resolve(strict=True)
                        generated_content_roots.add(resolved_generated)
                        hasher.update(b"generated-content-bound-separately\0")
                    elif (
                        _import_root_boundary(project_boundary, resolved_project_root, resolved)
                        is None
                    ):
                        # Runtime environment tree (M-006): always content-walk,
                        # never absorbed as content-covered by the project
                        # walk or deduplicated away in selected_roots — but
                        # ONLY when genuinely inside the project (where the
                        # gitignore boundary would prune it).  Roots outside
                        # the project keep normal overlap deduplication.
                        content_roots[resolved] = partial_coverage_policy(resolved) or (
                            _IMPORT_CONTEXT_SKIP_DIRS
                        )
                        try:
                            resolved.relative_to(resolved_project_root)
                        except ValueError:
                            pass
                        else:
                            runtime_content_roots.add(resolved)
                    elif covered_by(resolved, covered_trees):
                        hasher.update(b"content-covered\0")
                    else:
                        content_roots[resolved] = partial_coverage_policy(resolved) or (
                            _IMPORT_CONTEXT_SKIP_DIRS
                        )
                else:
                    try:
                        absolute.lstat()
                    except FileNotFoundError:
                        # M-007: a missing subpath may live inside a ZIP (or
                        # any regular file) on sys.path.  Resolve the archive
                        # ancestor and bind its bytes; only a genuinely absent
                        # entry stays a fully observed "missing" state.
                        archive = _archive_import_root(absolute)
                        if archive is not None:
                            archive_path, inner_prefix = archive
                            hasher.update(b"archive-import-root\0")
                            hasher.update(inner_prefix.encode("utf-8", errors="surrogateescape"))
                            hasher.update(b"\0")
                            try:
                                archive_resolved = archive_path.resolve(strict=False)
                            except (OSError, RuntimeError):  # fmt: skip
                                archive_resolved = archive_path
                            if archive_resolved in excluded:
                                hasher.update(b"excluded-archive\0")
                                continue
                            if not _hash_context_file(
                                hasher,
                                archive_path,
                                label=f"sys.path:{index}:archive",
                                seen=seen,
                            ):
                                reuse_safe = False
                        else:
                            # A truly absent sys.path entry is a fully observed
                            # state and can affect resolution order. A broken
                            # link is not equivalent and is handled by the
                            # successful lstat path.
                            hasher.update(b"missing-import-root\0")
                    except OSError as exc:
                        record_error("stat-import-root", exc, index=index, path=str(absolute))
                        hasher.update(
                            f"import-root-error:{type(exc).__qualname__}\0".encode("ascii")
                        )
                        reuse_safe = False
                    else:
                        hasher.update(b"unsupported-import-root\0")
                        reuse_safe = False
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                record_error("import-root", exc, index=index, path=str(absolute))
                hasher.update(f"import-root-error:{type(exc).__qualname__}\0".encode("ascii"))
                reuse_safe = False

    # Several ordinary CPython entries overlap (the interpreter root, Lib and
    # DLLs; a venv root and its site-packages).  Their ordered path semantics
    # were bound above. Walk each remaining byte tree only once while retaining
    # complete coverage of unclaimed modules and .pth files.
    selected_roots: list[tuple[Path, frozenset[str]]] = []
    for root in sorted(
        content_roots,
        key=lambda item: (len(item.parts), os.path.normcase(str(item))),
    ):
        if root in runtime_content_roots:
            # Runtime roots are never deduplicated away (M-006 correction 1b):
            # their bytes must be bound even when a project-core ancestor
            # was selected first.
            selected_roots.append((root, content_roots[root]))
            continue
        if covered_by(root, tuple(selected_roots)):
            continue
        selected_roots.append((root, content_roots[root]))

    for root in sorted(
        generated_content_roots,
        key=lambda item: (len(item.parts), os.path.normcase(str(item))),
    ):
        if not _hash_context_tree(
            hasher,
            root,
            label_prefix=f"sys.path:generated:{root}",
            seen=seen,
            excluded=excluded,
            skip_dirs=frozenset(),
            root_skip_dirs=frozenset(),
            hash_file_timestamps=False,
            hash_directory_timestamps=False,
        ):
            reuse_safe = False

    for root, skip_dirs in selected_roots:
        # ``mutants/`` is bound by the dedicated stable-content walk above.
        # Avoid descending into it again when the project root itself is an
        # effective import root.
        root_skip_dirs = frozenset({"mutants"}) if root == resolved_project_root else frozenset()
        if not _hash_context_tree(
            hasher,
            root,
            label_prefix=f"sys.path:content:{root}",
            seen=seen,
            excluded=excluded,
            skip_dirs=skip_dirs,
            root_skip_dirs=root_skip_dirs,
            ignore_boundary=_import_root_boundary(
                project_boundary,
                resolved_project_root,
                root,
            ),
        ):
            reuse_safe = False
    return reuse_safe


@component("distributions", identity=("project_root",))
def _installed_distribution_basis(
    project_root: Path,
    seen: set[Path],
    *,
    excluded: set[Path] | None = None,
    core_hasher: Any | None = None,
    core_seen: set[Path] | None = None,
) -> _DependencyBasis:
    """Hash installed distribution bytes; mark any incomplete basis unsafe.

    With ``core_hasher`` the same pass also feeds the terminal project core:
    project-contained distribution files and editable source trees are bound
    WITHOUT a gitignore boundary (decided M-061/B) — an editable install
    stays importable in place by the executed child, so its ignored bytes
    remain core drift, while the combined ambient digest prunes them through
    its boundaries.
    """

    excluded = excluded or set()
    core_seen = core_seen if core_seen is not None else set()
    core_reuse_safe = True
    hasher = observed_sha256(stream="distributions")
    _hash_verdict_relevant_environment(hasher)
    reuse_safe = _hash_runtime_identity(hasher, seen)
    try:
        resolved_project_root = project_root.resolve(strict=True)
    except (
        OSError,
        RuntimeError,
    ):
        resolved_project_root = _absolute_lexical_path(project_root)
    # ``_hash_context_tree`` excludes generic generated directories only when
    # they are direct children of a covered root.  Keep the coverage shortcut
    # conservative with the full root skip set: an explicitly-added import
    # root such as ``<project>/build`` was not walked with the project and must
    # be content-hashed independently rather than labelled ``content-covered``.
    covered_trees: list[tuple[Path, frozenset[str]]] = [
        (resolved_project_root, _CONTEXT_ROOT_SKIP_DIRS)
    ]
    try:
        distributions = list(importlib.metadata.distributions())
    except Exception as exc:  # pragma: no cover - importlib backend failure
        record_error("enumerate-distributions", exc)
        hasher.update(f"enumeration-error:{type(exc).__qualname__}".encode("ascii"))
        return _DependencyBasis(hasher.hexdigest(), False)

    @component("distribution-identity")
    def distribution_key(distribution: importlib.metadata.Distribution) -> tuple[str, str, str]:
        try:
            name = distribution.metadata.get("Name") or ""
            version = distribution.version or ""
            location = str(Path(str(distribution.locate_file(""))).resolve(strict=False))
        except Exception as exc:
            record_error("distribution-identity", exc)
            return ("", "", "")
        record_event("distribution-identity", name=name, version=version, location=location)
        return (name.casefold(), version, location.casefold())

    for distribution in sorted(distributions, key=distribution_key):
        name, version, location = distribution_key(distribution)
        with component_scope("distribution", name=name, version=version, location=location):
            identity = f"distribution:{name}:{version}:{location}"
            hasher.update(identity.encode("utf-8", errors="surrogateescape"))
            hasher.update(b"\0")
            if not name or not version:
                reuse_safe = False

            try:
                files = distribution.files
            except Exception as exc:
                record_error("distribution-file-inventory", exc, identity=identity)
                hasher.update(f"file-inventory-error:{type(exc).__qualname__}\0".encode("ascii"))
                reuse_safe = False
                files = None
            if files is None:
                hasher.update(b"missing-file-inventory\0")
                reuse_safe = False
            else:
                for entry in sorted(files, key=lambda item: str(item).casefold()):
                    try:
                        path = Path(str(distribution.locate_file(entry)))
                    except Exception as exc:
                        record_error(
                            "distribution-locate", exc, identity=identity, entry=str(entry)
                        )
                        hasher.update(
                            f"{identity}:{entry}:locate-error:{type(exc).__qualname__}\0".encode(
                                "utf-8", errors="surrogateescape"
                            )
                        )
                        reuse_safe = False
                        continue
                    try:
                        resolved_path = path.resolve(strict=False)
                    except (OSError, RuntimeError):  # fmt: skip
                        resolved_path = _absolute_lexical_path(path)
                    if resolved_path in excluded:
                        hasher.update(f"{identity}:{entry}:excluded\0".encode())
                        continue
                    entry_normalized = str(entry).replace("\\", "/")
                    if "__pycache__" in entry_normalized.split(
                        "/"
                    ) or entry_normalized.casefold().endswith(".pyc"):
                        # Derived bytecode is a function of the interpreter
                        # identity and the source bytes, both bound
                        # separately; its drift must not invalidate reuse
                        # (issue #195).
                        hasher.update(
                            f"{identity}:{entry}:derived-bytecode-skipped\0".encode(
                                "utf-8", errors="surrogateescape"
                            )
                        )
                        continue
                    if not _hash_context_file(
                        hasher,
                        path,
                        label=f"{identity}:{entry}",
                        seen=seen,
                    ):
                        reuse_safe = False
                    if (
                        core_hasher is not None
                        and _project_core_relative_path(resolved_path, project_root) is not None
                        and not _hash_context_file(
                            core_hasher,
                            resolved_path,
                            label=f"project-distribution:{identity}:{entry}",
                            seen=core_seen,
                        )
                    ):
                        core_reuse_safe = False

            try:
                direct_url = distribution.read_text("direct_url.json")
            except Exception as exc:
                record_error("distribution-direct-url", exc, identity=identity)
                hasher.update(
                    f"{identity}:direct-url-error:{type(exc).__qualname__}\0".encode("ascii")
                )
                reuse_safe = False
                continue
            if direct_url is None:
                continue
            try:
                direct_payload = json.loads(direct_url)
            except JSONDecodeError as exc:
                record_error("parse-direct-url", exc, identity=identity)
                hasher.update(f"{identity}:invalid-direct-url\0".encode())
                reuse_safe = False
                continue
            editable = (
                isinstance(direct_payload, dict)
                and isinstance(direct_payload.get("dir_info"), dict)
                and direct_payload["dir_info"].get("editable") is True
            )
            if not editable:
                continue
            editable_path = _editable_source_path(direct_url)
            if editable_path is None:
                hasher.update(f"{identity}:unresolved-editable\0".encode())
                reuse_safe = False
                continue
            # An editable install inside the project mirrors the project
            # walk's ignore boundary; external editable sources have none.
            project_boundary = GitignoreBoundary.load(project_root)
            editable_boundary = _project_descended_boundary(
                project_boundary,
                project_root,
                editable_path,
            )
            if not _hash_context_tree(
                hasher,
                editable_path,
                label_prefix=f"{identity}:editable",
                seen=seen,
                excluded=excluded,
                ignore_boundary=editable_boundary,
            ):
                reuse_safe = False
            # Decided M-061/B: the editable core walk deliberately passes no
            # ignore boundary, unlike the combined walk above.  An editable
            # install stays importable in place by the executed tests, so
            # ignored-but-readable bytes inside it stay terminally bound as
            # project (core) drift; only the combined ambient digest prunes
            # them via ``editable_boundary``.
            if (
                core_hasher is not None
                and _project_core_relative_path(editable_path, project_root) is not None
                and not _hash_context_tree(
                    core_hasher,
                    editable_path,
                    label_prefix=f"project-editable:{identity}",
                    seen=core_seen,
                    excluded=excluded,
                    skip_dirs=_CONTEXT_SKIP_DIRS,
                    root_skip_dirs=_CONTEXT_ROOT_SKIP_DIRS,
                )
            ):
                core_reuse_safe = False
            try:
                covered_trees.append((editable_path.resolve(strict=True), _CONTEXT_ROOT_SKIP_DIRS))
            except (OSError, RuntimeError) as exc:
                record_error("editable-coverage-resolution", exc, path=str(editable_path))
                reuse_safe = False

    if not _hash_effective_import_paths(
        hasher,
        project_root,
        seen,
        tuple(covered_trees),
        excluded,
    ):
        reuse_safe = False

    if core_hasher is not None and not _hash_project_import_core(
        core_hasher,
        project_root,
        core_seen,
        excluded,
    ):
        core_reuse_safe = False

    return _DependencyBasis(hasher.hexdigest(), reuse_safe, core_reuse_safe)


@component("context", identity=("project_root",))
def _build_stats_context_evidence(
    config: MutmutConfig,
    project_root: Path | None = None,
    *,
    excluded_paths: tuple[Path, ...] = (),
) -> _StatsContextEvidence:
    """Hash the combined context and its independently classified core.

    This intentionally prefers conservative invalidation to a guessed import
    graph. Every automatically staged project file, explicit external tree and
    installed-distribution file can alter tests. If any distribution cannot be
    fully content-hashed, the returned digest is marked ``no-reuse`` so current
    run evidence stays deterministic but prior verdicts cannot be reused.
    """
    root = (project_root or Path.cwd()).resolve()
    register_input_root(root)
    excluded_resolved: set[Path] = set()
    for excluded in excluded_paths:
        candidate = excluded if excluded.is_absolute() else root / excluded
        try:
            excluded_resolved.add(candidate.resolve(strict=False))
        except (
            OSError,
            RuntimeError,
        ):
            excluded_resolved.add(candidate.absolute())

    hasher = observed_sha256(stream="context")
    core_hasher = observed_sha256(stream="core")
    core_hasher.update(b"run-basis-core:v1\0")
    project_hasher = _HashFanout(hasher, core_hasher)
    config_values = config.model_dump(mode="json")
    config_payload = json.dumps(
        config_values,
        sort_keys=True,
        separators=(",", ":"),
    )
    with component_scope("configuration"):
        if is_observing():
            for name, value in config_values.items():
                record_token(
                    "config-field",
                    json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                    name=name,
                )
        project_hasher.update(config_payload.encode("utf-8"))
        project_hasher.update(b"\0")
    # Every pytest phase is pinned to one staged local config plus root and
    # confcut boundary. Project/config/dependency bytes below determine the
    # selected file; the schema marker prevents pre-boundary evidence reuse.
    project_hasher.update(b"pytest-boundary:v2\0")
    seen: set[Path] = set()
    project_boundary = GitignoreBoundary.load(root)
    core_complete = _hash_context_tree(
        project_hasher,
        root,
        label_prefix="project",
        seen=seen,
        excluded=excluded_resolved,
        ignore_boundary=project_boundary,
    )
    reuse_safe = core_complete
    if config.type_check_command:
        # ``type_check_command`` is intentionally a generic argv contract. An
        # executable can read scripts, plugins or configuration outside the
        # project/import trees, and argv alone cannot prove that dependency
        # closure. Let the run execute, but fail closed for cached verdicts and
        # CI authorization until a future structured checker specification can
        # declare and bind every external input.
        hasher.update(b"type-check-command:unbounded-external-closure\0")
        reuse_safe = False

    # Explicit mirrors and test roots can live outside the project
    # (``extra_paths`` is designed for sibling packages). Their complete bytes
    # remain part of the context even though the project walk cannot see them.
    for field_name, entries in (
        ("paths_to_mutate", config.paths_to_mutate),
        ("tests_dir", config.tests_dir),
        ("also_copy", config.also_copy),
        ("extra_paths", config.extra_paths),
    ):
        for configured in sorted(set(entries)):
            configured_path = Path(configured)
            absolute = _absolute_lexical_path(
                configured_path if configured_path.is_absolute() else root / configured_path
            )
            register_input_root(absolute)
            prefix = f"configured:{field_name}:{configured}"
            project_hasher.update(prefix.encode("utf-8"))
            project_hasher.update(b"\0")
            if absolute.is_file():
                try:
                    resolved_absolute = absolute.resolve(strict=False)
                except (
                    OSError,
                    RuntimeError,
                ):
                    resolved_absolute = absolute.absolute()
                if resolved_absolute in excluded_resolved:
                    project_hasher.update(b"excluded\0")
                    continue
                if not _hash_context_file(
                    project_hasher,
                    absolute,
                    label=prefix,
                    seen=seen,
                ):
                    reuse_safe = False
                    core_complete = False
                continue
            if not absolute.is_dir():
                try:
                    absolute.lstat()
                except FileNotFoundError:
                    project_hasher.update(b"missing\0")
                    # Absence is a complete, observable state. Optional
                    # ``also_copy`` defaults deliberately name candidates that
                    # do not exist in every project; a later appearance changes
                    # this marker to a file/tree digest and invalidates reuse.
                except OSError as exc:
                    record_error("stat-configured-path", exc, path=str(absolute), field=field_name)
                    project_hasher.update(
                        f"unreadable:{type(exc).__qualname__}\0".encode(
                            "utf-8", errors="surrogateescape"
                        )
                    )
                    reuse_safe = False
                    core_complete = False
                else:
                    # Broken links, devices and other unsupported entries are
                    # not the same as an observed absent optional path.
                    project_hasher.update(b"unsupported-configured-path\0")
                    reuse_safe = False
                    core_complete = False
                continue
            if not _hash_context_tree(
                project_hasher,
                absolute,
                label_prefix=prefix,
                seen=seen,
                excluded=excluded_resolved,
                # This is an explicitly configured execution/staging root,
                # not the implicit workspace root.  Generic names such as
                # build/html/dist are therefore source content here, exactly
                # as copy_also_copy_files treats their child directories.
                root_skip_dirs=frozenset(),
                # The entry itself is force-included (git add -f semantics);
                # ignore files at or below it still prune its contents.
                ignore_boundary=_configured_entry_boundary(
                    project_boundary,
                    root,
                    absolute,
                ),
            ):
                reuse_safe = False
                core_complete = False

    dependency_basis = _installed_distribution_basis(
        root,
        seen,
        excluded=excluded_resolved,
        core_hasher=core_hasher,
        # M-133: seed with the already-seen set so project files hashed by
        # the project-tree pass are not re-read and re-hashed by the
        # distribution pass (quadratic I/O + doubled race window).
        core_seen=set(seen),
    )
    hasher.update(b"installed-distributions\0")
    hasher.update(dependency_basis.digest.encode("ascii"))
    digest = hasher.hexdigest()
    core_complete = core_complete and dependency_basis.core_reuse_safe
    complete = dependency_basis.reuse_safe and reuse_safe
    fingerprint = f"{_NO_REUSE_CONTEXT_PREFIX}{digest}" if not complete else digest
    return _StatsContextEvidence(
        fingerprint=fingerprint,
        core_digest=core_hasher.hexdigest(),
        complete=complete,
        core_complete=core_complete,
    )


def build_stats_context_fingerprint(
    config: MutmutConfig,
    project_root: Path | None = None,
    *,
    excluded_paths: tuple[Path, ...] = (),
) -> str:
    """Return the combined project/config/dependency context fingerprint."""

    return _build_stats_context_evidence(
        config,
        project_root,
        excluded_paths=excluded_paths,
    ).fingerprint


def canonical_run_basis_config(config: MutmutConfig) -> str:
    """Serialize the effective run config needed to reproduce its basis."""
    return json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def build_run_basis_fingerprint(
    config: MutmutConfig,
    project_root: Path | None = None,
    *,
    excluded_paths: tuple[Path, ...] = (),
) -> str:
    """Return an authoritative run digest, rejecting incomplete evidence."""

    evidence = build_run_basis_evidence(
        config,
        project_root,
        excluded_paths=excluded_paths,
    )
    if not evidence.complete:
        raise ValueError("the complete execution basis could not be fingerprinted")
    return evidence.digest


@snapshot
def build_run_basis_evidence(
    config: MutmutConfig,
    project_root: Path | None = None,
    *,
    excluded_paths: tuple[Path, ...] = (),
) -> RunBasisEvidence:
    """Hash the engine and inputs without erasing completeness information."""

    import mutmut_win

    context_evidence = _build_stats_context_evidence(
        config,
        project_root,
        excluded_paths=excluded_paths,
    )
    payload = json.dumps(
        {
            "schema": 2,
            "engine_version": mutmut_win.__version__,
            "context_fingerprint": context_evidence.fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return RunBasisEvidence(
        digest=observed_sha256(payload.encode("utf-8"), stream="basis").hexdigest(),
        complete=context_evidence.complete,
        core_digest=context_evidence.core_digest,
        core_complete=context_evidence.core_complete,
    )


def save_stats(
    stats: MutmutStats,
    mutants_dir: Path = DEFAULT_STATS_DIR,
    *,
    refresh_file_fingerprints: bool = True,
) -> None:
    """Save *stats* to *mutants_dir*/mutmut-stats.json.

    The ``tests_by_mangled_function_name`` sets are serialised as sorted lists
    so the output is deterministic.

    Args:
        stats: The ``MutmutStats`` instance to persist.
        mutants_dir: Existing real target directory. Defaults to ``.mutmut-cache/``;
            callers must create and validate it before publication.
    """
    stats_path = mutants_dir / _STATS_FILENAME
    # Fingerprints are ALWAYS refreshed from the current duration keys at
    # save time (issue #130 / 360°-B1): the write moment is the measurement
    # truth, and files whose node IDs left the cache drop out automatically
    # (no stale entries to re-trigger collection forever).
    if refresh_file_fingerprints:
        stats.test_file_fingerprints = _fingerprint_test_files(stats.duration_by_test)
    payload = {
        "tests_by_mangled_function_name": {
            k: sorted(v) for k, v in stats.tests_by_mangled_function_name.items()
        },
        "duration_by_test": stats.duration_by_test,
        "stats_time": stats.stats_time,
        "test_file_fingerprints": stats.test_file_fingerprints,
        "context_fingerprint": stats.context_fingerprint,
        # Reserved for a future sound runtime capability.  Persisted cache
        # data is never itself a capability and is therefore always false.
        "mapping_is_authoritative": False,
    }
    _atomic_write_json(stats_path, payload)


def collect_or_load_stats(
    runner: PytestRunner,
    mutants_dir: Path = DEFAULT_STATS_DIR,
    *,
    context_fingerprint: str | None = None,
    allow_cache_reuse: bool = True,
) -> MutmutStats:
    """Load cached stats or collect fresh ones via *runner*.

    Loads the cache; any detected change (no cache, diagnostic-only basis,
    changed test set, changed context fingerprint, changed test files)
    triggers a FULL re-collection — the former "incremental update for new
    tests only" never existed in the implementation (M-135: the docstring
    promised it; the code has always re-run the complete suite).

    Behavior:
    1. Try to load cached stats from JSON (with context fingerprint check).
    2. List current tests and compare against cached test names.
    3. Any difference (new, removed, or no cache) triggers a full re-collection.
    4. A diagnostic-only execution basis disables cache reuse entirely.

    Args:
        runner: ``PytestRunner`` instance.
        mutants_dir: Directory where the stats JSON file lives.
        allow_cache_reuse: Whether a previously persisted mapping may be
            consumed. Diagnostic-only runs force a fresh collection even when
            the later context fingerprint appears stable.

    Returns:
        A ``MutmutStats`` instance.
    """
    cached = load_stats(mutants_dir)
    if cached is None:
        return _run_stats_collection(
            runner, mutants_dir, cached=None, context_fingerprint=context_fingerprint
        )

    if not allow_cache_reuse:
        print(
            "The initial execution basis was diagnostic-only — "
            "re-collecting the full test mapping without cache reuse."
        )
        return _run_stats_collection(
            runner,
            mutants_dir,
            cached=cached,
            context_fingerprint=context_fingerprint,
        )

    if context_fingerprint is not None and not context_allows_result_reuse(context_fingerprint):
        print(
            "Execution inputs could not be fingerprinted completely — "
            "re-collecting the full test mapping without cache reuse."
        )
        return _run_stats_collection(
            runner,
            mutants_dir,
            cached=cached,
            context_fingerprint=context_fingerprint,
        )

    if context_fingerprint is not None and cached.context_fingerprint != context_fingerprint:
        print("Stats inputs changed — re-collecting the full test mapping.")
        return _run_stats_collection(
            runner,
            mutants_dir,
            cached=cached,
            context_fingerprint=context_fingerprint,
        )

    # Incremental update: compare the live test list against the cache.
    current_tests = set(runner.collect_tests())
    all_known_tests = set(cached.duration_by_test.keys())
    new_tests = current_tests - all_known_tests
    removed_tests = all_known_tests - current_tests

    # Issue #130 / 360°-B1: in-place edits keep node IDs identical — compare
    # the per-file fingerprints recorded with the cache. A legacy cache
    # without the field reports every file as changed ONCE (self-healing:
    # the refreshed cache persists fingerprints).
    current_fps = _fingerprint_test_files(cached.duration_by_test.keys())
    changed_files = sorted(
        f for f, fp in current_fps.items() if cached.test_file_fingerprints.get(f) != fp
    )

    if new_tests:
        print(
            f"Found {len(new_tests)} new tests — re-collecting the full stats run "
            "(per-test collection is not implemented; the run is always complete)."
        )
    elif removed_tests:
        print(
            f"Found {len(removed_tests)} removed tests — re-collecting the full "
            "stats run before changing the cache."
        )
    elif changed_files:
        print(
            f"{len(changed_files)} test file(s) changed in place — re-collecting "
            "the full stats run so the test↔function mapping stays honest (issue #130)."
        )
    if new_tests or removed_tests or changed_files:
        return _run_stats_collection(
            runner,
            mutants_dir,
            cached=cached,
            context_fingerprint=context_fingerprint,
        )

    return cached


def _run_stats_collection(
    runner: PytestRunner,
    mutants_dir: Path,
    cached: MutmutStats | None = None,
    context_fingerprint: str | None = None,
) -> MutmutStats:
    """Run a fresh stats collection; never let a failure poison the cache.

    ``runner.run_stats()`` executes pytest as a subprocess with the stats
    plugin; the plugin writes ``mutmut-stats.json`` at session end — that
    file is the single source of truth (its ``stats_time`` is the accurate
    in-subprocess measurement, issue #99 / A2-RN-008: the parent used to
    re-save it with a near-zero ``process_time()``). The collection is
    ALWAYS the full suite — the former ``tests`` parameter was reserved-
    but-unused and its message a lie (issue #130 / 360°-B1; a targeted
    partial collection stays a documented future option in #132/C3).

    On success the loaded plugin JSON is re-saved once: the plugin knows
    nothing about test-FILE fingerprints, and without persisting them every
    later run would see "everything changed" (issue #130 / 360°-B1).
    ``stats_time`` is the loaded plugin value, so the RN-008 guarantee
    survives the re-save.

    On a FAILED run (issue #99 / A3-OS-006 + A2-RN-003): the freshly
    written JSON may be partial — it is neither loaded nor trusted; a
    fresh empty ``MutmutStats`` is returned (M-134: the former docstring
    claimed the pre-run cache is "restored and returned", but the code
    has always returned empty stats on failure; the pre-run cache FILE
    is untouched, so the next run can still load it). Without any cache,
    the full-suite fallback is announced loudly instead of silently
    degrading every mutant run.

    Args:
        runner: ``PytestRunner`` used to execute the stats run.
        mutants_dir: Directory where the stats JSON file lives.
        cached: The pre-run cache, used as fallback on failure.

    Returns:
        The freshly collected stats, or the fallback described above.
    """
    stats_path = mutants_dir / _STATS_FILENAME
    # A successful subprocess must publish a fresh file. Leaving the old file
    # in place made "exit 0 but plugin wrote nothing" indistinguishable from a
    # valid refresh and silently re-authorized stale data.
    try:
        stats_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(
            f"Warning: stats cache cannot be refreshed ({stats_path}: {exc}) — "
            "every mutant will run the full test suite (slow)."
        )
        return MutmutStats(context_fingerprint=context_fingerprint)
    try:
        exit_code = runner.run_stats(stats_path)
    except BaseException:
        if cached is not None:
            save_stats(cached, mutants_dir, refresh_file_fingerprints=False)
        raise
    if exit_code != 0:
        if cached is not None:
            print("Warning: stats collection failed — keeping the existing stats cache untouched.")
            save_stats(
                cached,
                mutants_dir,
                refresh_file_fingerprints=False,
            )  # heal a possibly partial plugin write without blessing new inputs
            return MutmutStats(context_fingerprint=context_fingerprint)
        print(
            "Warning: stats collection failed and no cache exists — every "
            "mutant will run the full test suite (slow)."
        )
        if stats_path.exists():
            stats_path.unlink()  # a partial write must not become tomorrow's cache
        return MutmutStats()

    stats = load_stats(mutants_dir)
    if stats is None:
        print(
            "Warning: stats collection wrote no data — every mutant will "
            "run the full test suite (slow)."
        )
        if cached is not None:
            save_stats(cached, mutants_dir, refresh_file_fingerprints=False)
        return MutmutStats(context_fingerprint=context_fingerprint)
    # Persist the file fingerprints alongside the plugin data (see above).
    stats.context_fingerprint = context_fingerprint
    stats.mapping_is_authoritative = False
    save_stats(stats, mutants_dir)
    return stats


# ---------------------------------------------------------------------------
# ListAllTestsResult — incremental stats update helper
# ---------------------------------------------------------------------------


class ListAllTestsResult:
    """Result of listing all currently collected test IDs.

    Used to perform incremental stats updates: obsolete test names that are
    no longer present are removed from the cached stats, and new tests are
    identified for a targeted re-run.

    Args:
        ids: Set of currently active pytest node IDs.
        stats: The loaded ``MutmutStats`` to compare against.
    """

    def __init__(self, *, ids: set[str], stats: MutmutStats) -> None:
        if not isinstance(ids, set):
            msg = "ids must be a set"
            raise TypeError(msg)
        self._ids = ids
        self._stats = stats

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def ids(self) -> set[str]:
        """Return the set of currently active test node IDs."""
        return self._ids

    def clear_out_obsolete_test_names(self, mutants_dir: Path = DEFAULT_STATS_DIR) -> None:
        """Remove test names that no longer exist from the cached stats.

        Cleans BOTH the per-mutant test mapping (whose dead node IDs end up
        in worker argfiles → pytest exit 4 → "suspicious" floods, issue #99 /
        A3-OS-007) and ``duration_by_test`` (whose dead keys would re-trigger
        the removed-tests cleanup on every run). Modifies *stats* in-place
        and persists the result if any entries were removed.

        Args:
            mutants_dir: Directory where the stats JSON file lives.
        """
        before = sum(len(v) for v in self._stats.tests_by_mangled_function_name.values())
        before_durations = len(self._stats.duration_by_test)

        for k in self._stats.tests_by_mangled_function_name:
            self._stats.tests_by_mangled_function_name[k] = {
                name for name in self._stats.tests_by_mangled_function_name[k] if name in self._ids
            }
        self._stats.duration_by_test = {
            name: duration
            for name, duration in self._stats.duration_by_test.items()
            if name in self._ids
        }

        after = sum(len(v) for v in self._stats.tests_by_mangled_function_name.values())
        removed = (before - after) + (before_durations - len(self._stats.duration_by_test))
        if removed:
            print(f"Removed {removed} obsolete test entries")
            save_stats(self._stats, mutants_dir)

    def new_tests(self) -> set[str]:
        """Return test IDs that are not yet present in the cached stats.

        Returns:
            Set of test node IDs that appear in *ids* but not in the current
            ``duration_by_test`` mapping.
        """
        return self._ids - set(self._stats.duration_by_test.keys())


# ---------------------------------------------------------------------------
# CI/CD stats export
# ---------------------------------------------------------------------------


@dataclass
class CicdStats:
    """Aggregated mutation run statistics for CI/CD export.

    Attributes:
        killed: Number of mutants killed by tests.
        survived: Number of surviving (un-killed) mutants.
        total: Total number of mutants generated.
        no_tests: Number of mutants with no covering tests.
        skipped: Number of explicitly skipped mutants.
        suspicious: Number of mutants with suspicious exit codes.
        timeout: Number of timed-out mutants, including legacy loop classifications.
        check_was_interrupted_by_user: Number of mutants interrupted by the user.
        segfault: Number of mutants that caused a segfault.
        caught_by_type_check: Number of mutants caught by the type checker.
        killed_by_infinite_loop: Historical diagnostic subset of ``timeout``.
            The field name is preserved for readers of the existing JSON schema.
        score: Mutation score as a percentage (0.0-100.0).
    """

    killed: int = 0
    survived: int = 0
    total: int = 0
    no_tests: int = 0
    skipped: int = 0
    suspicious: int = 0
    timeout: int = 0
    check_was_interrupted_by_user: int = 0
    segfault: int = 0
    caught_by_type_check: int = 0
    killed_by_infinite_loop: int = 0

    @property
    def effective_killed(self) -> int:
        """The kill class behind :attr:`score` (issue #91).

        A type-check rejection and a crash under a mutant are detections too.
        Historical loop classifications remain conservative timeouts (S3-003).
        """
        return self.killed + self.caught_by_type_check + self.segfault

    @property
    def scoreable(self) -> int:
        """The score denominator: mutants a verdict was possible for.

        ``skipped`` and ``no tests`` leave the denominator — printing the
        raw total next to the score invited verifying it with the wrong
        division (issue #122 / external QA SCO-001).
        """
        return self.total - self.skipped - self.no_tests

    @property
    def score(self) -> float:
        """Mutation score as a percentage.

        The numerator is the kill class: ``killed`` plus ``caught_by_type_check`` plus
        ``segfault`` — a crash under a mutant is a detection (issue #91).
        Buckets stay disjoint; aggregation happens only here.

        Returns:
            A float in [0.0, 100.0]; 0.0 if no testable mutants exist.
        """
        if self.scoreable <= 0:
            return 0.0
        return self.effective_killed / self.scoreable * 100.0


def compute_cicd_stats(results: list[tuple[str, str | None]]) -> CicdStats:
    """Compute CI/CD stats from a flat list of (mutant_name, status) pairs.

    Args:
        results: List of ``(mutant_name, status)`` tuples.  *status* is a
            string from ``constants.status_by_exit_code`` or ``None`` for
            unchecked mutants.

    Returns:
        A populated ``CicdStats`` instance.
    """
    stats = CicdStats(total=len(results))
    for _name, status in results:
        match status:
            case "killed":
                stats.killed += 1
            case "killed_by_infinite_loop":
                # S3-003: retain the historical diagnostic subset without granting
                # kill authority. This also protects results/export before a rerun.
                stats.timeout += 1
                stats.killed_by_infinite_loop += 1
            case "survived":
                stats.survived += 1
            case "no tests":
                stats.no_tests += 1
            case "skipped":
                stats.skipped += 1
            case "suspicious":
                stats.suspicious += 1
            case "timeout":
                stats.timeout += 1
            case "check was interrupted by user":
                stats.check_was_interrupted_by_user += 1
            case "segfault":
                stats.segfault += 1
            case "caught by type check":
                stats.caught_by_type_check += 1
    return stats


def save_cicd_stats(
    results: list[tuple[str, str | None]],
    mutants_dir: Path = Path("mutants"),
) -> CicdStats:
    """Compute and persist CI/CD stats to *mutants_dir*/mutmut-cicd-stats.json.

    Ported from ``save_cicd_stats`` in mutmut 3.5.0 ``__main__.py``.
    The output JSON is designed for consumption by CI/CD pipelines to gate
    pull requests based on mutation score.

    Args:
        results: List of ``(mutant_name, status)`` tuples.
        mutants_dir: Existing real directory where the JSON file will be
            written. Defaults to ``mutants/``; callers must create and validate
            it before publication.

    Returns:
        The computed ``CicdStats`` instance.
    """
    stats = compute_cicd_stats(results)
    cicd_path = mutants_dir / _CICD_STATS_FILENAME
    payload = {
        "killed": stats.killed,
        "survived": stats.survived,
        "total": stats.total,
        "no_tests": stats.no_tests,
        "skipped": stats.skipped,
        "suspicious": stats.suspicious,
        "timeout": stats.timeout,
        "check_was_interrupted_by_user": stats.check_was_interrupted_by_user,
        "segfault": stats.segfault,
        "caught_by_type_check": stats.caught_by_type_check,
        "killed_by_infinite_loop": stats.killed_by_infinite_loop,
        "score": stats.score,
    }
    _atomic_write_json(cicd_path, payload)
    return stats
