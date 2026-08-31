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

import contextlib
import hashlib
import importlib.metadata
import json
import math
import os
import stat
import sys
import sysconfig
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.atomic_file import atomic_write_bytes
from mutmut_win.constants import WORKSPACE_EXCLUDED_DIR_NAMES

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig
    from mutmut_win.runner import PytestRunner


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


def load_stats(mutants_dir: Path = Path("mutants")) -> MutmutStats | None:
    """Load stats from *mutants_dir*/mutmut-stats.json.

    Args:
        mutants_dir: Directory that contains the stats JSON file.
            Defaults to ``mutants/``.

    Returns:
        A populated ``MutmutStats`` instance, or ``None`` if the file does
        not exist or cannot be parsed.
    """
    stats_path = mutants_dir / _STATS_FILENAME
    try:
        with stats_path.open(encoding="utf-8") as f:
            raw_data: object = json.load(f)
    except (FileNotFoundError, JSONDecodeError, UnicodeDecodeError):
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
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            return None
        duration_by_test[key] = float(value)

    raw_time = data.pop("stats_time", 0.0)
    if (
        not isinstance(raw_time, (int, float))
        or isinstance(raw_time, bool)
        or not math.isfinite(raw_time)
        or raw_time < 0
    ):
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


_CONTEXT_SKIP_DIRS = WORKSPACE_EXCLUDED_DIR_NAMES
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


@dataclass(frozen=True)
class RunBasisEvidence:
    """Digest plus proof that the complete execution basis was observable."""

    digest: str
    complete: bool


def context_allows_result_reuse(context_fingerprint: str | None) -> bool:
    """Return whether *context_fingerprint* proves a reusable test basis."""

    return context_fingerprint is not None and not context_fingerprint.startswith(
        _NO_REUSE_CONTEXT_PREFIX
    )


def _skip_context_file(name: str) -> bool:
    """Exclude mutable coordination files and non-staged dotenv secrets."""

    folded = name.casefold()
    if folded in {".mutmut-win.run.lock", ".mutmut-win.run.lock.guard"} or (
        folded.startswith(".mutmut-win-") and folded.endswith((".run.lock", ".run.lock.guard"))
    ):
        return True
    return folded == ".env" or (
        folded.startswith(".env.")
        and folded not in {".env.example", ".env.sample", ".env.template"}
    )


def _same_file_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    """Compare identity and mutation-sensitive fields of two file stats."""

    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _same_path_binding(left: os.stat_result, right: os.stat_result) -> bool:
    """Compare two handles without Windows' incompatible ``st_ctime`` APIs."""

    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _absolute_lexical_path(path: Path) -> Path:
    """Return an absolute path without dereferencing its final binding."""

    # ``Path.resolve`` dereferences the binding we deliberately re-open below.
    return Path(os.path.abspath(os.fspath(path)))  # noqa: PTH100


def _hash_context_file(
    hasher: Any,
    path: Path,
    *,
    label: str,
    seen: set[Path],
) -> bool:
    """Hash one regular file and verify its path/identity stayed stable."""

    hasher.update(label.encode("utf-8", errors="surrogateescape"))
    hasher.update(b"\0")
    try:
        absolute = _absolute_lexical_path(path)
        hasher.update(str(absolute).encode("utf-8", errors="surrogateescape"))
        hasher.update(b"\0")
        if absolute in seen:
            hasher.update(b"already-hashed\0")
            return True
        with absolute.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                hasher.update(b"not-regular\0")
                return False
            while chunk := stream.read(1024 * 1024):
                hasher.update(chunk)
            after_handle = os.fstat(stream.fileno())
            # Re-open the lexical path while the hashed handle is still live.
            # On POSIX this catches rename-and-replace; on Windows it avoids
            # comparing ``fstat().st_ctime`` with the path-stat value, whose
            # semantics differ on current CPython releases.
            with absolute.open("rb") as rebound:
                rebound_handle = os.fstat(rebound.fileno())
        if not _same_file_snapshot(before, after_handle) or not _same_path_binding(
            after_handle, rebound_handle
        ):
            hasher.update(b"identity-changed\0")
            return False
        hasher.update(b"\0")
        seen.add(absolute)
        return True
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        hasher.update(b"unreadable:")
        hasher.update(type(exc).__qualname__.encode("ascii", errors="replace"))
        hasher.update(b"\0")
        return False


def _editable_source_path(direct_url: str) -> Path | None:
    """Return the local source directory named by a PEP 610 editable URL."""

    try:
        payload = json.loads(direct_url)
    except (JSONDecodeError, TypeError):
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
    raw_path = urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return Path(raw_path)


def _hash_context_tree(
    hasher: Any,
    root: Path,
    *,
    label_prefix: str,
    seen: set[Path],
    excluded: set[Path] | None = None,
    skip_dirs: frozenset[str] = _CONTEXT_SKIP_DIRS,
) -> bool:
    """Hash every stable file in one runtime-relevant tree."""

    reuse_safe = True
    excluded = excluded or set()

    def record_walk_error(_error: OSError) -> None:
        nonlocal reuse_safe
        reuse_safe = False

    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        hasher.update(f"{label_prefix}:missing\0".encode("utf-8", errors="surrogateescape"))
        return False
    if not resolved_root.is_dir():
        hasher.update(f"{label_prefix}:not-directory\0".encode())
        return False

    for root_str, dirs, files in os.walk(resolved_root, onerror=record_walk_error):
        directory = Path(root_str)
        retained_dirs: list[str] = []
        for dirname in sorted(dirs):
            if dirname.casefold() in skip_dirs:
                continue
            child = directory / dirname
            try:
                is_link = child.is_symlink() or child.is_junction()
            except OSError:
                is_link = True
            if is_link:
                hasher.update(
                    f"{label_prefix}:unfollowed-directory-link:{dirname}\0".encode(
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
            path = directory / name
            absolute = _absolute_lexical_path(path)
            if absolute in excluded:
                continue
            try:
                relative = path.relative_to(resolved_root).as_posix()
            except ValueError:
                relative = path.name
            if not _hash_context_file(
                hasher,
                path,
                label=f"{label_prefix}:{relative}",
                seen=seen,
            ):
                reuse_safe = False
    return reuse_safe


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
        hasher.update(len(encoded_name).to_bytes(8, "big"))
        hasher.update(encoded_name)
        hasher.update(len(encoded_value).to_bytes(8, "big"))
        hasher.update(encoded_value)


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


def _hash_effective_import_paths(
    hasher: Any,
    project_root: Path,
    seen: set[Path],
    covered_trees: tuple[tuple[Path, frozenset[str]], ...],
) -> bool:
    """Bind ordered import roots, including unclaimed modules and ``.pth``."""

    reuse_safe = True
    content_roots: set[Path] = set()
    hasher.update(b"effective-sys-path:v2\0")

    def covered_by(root: Path, candidates: tuple[tuple[Path, frozenset[str]], ...]) -> bool:
        for candidate, skipped_names in candidates:
            try:
                relative = root.relative_to(candidate)
            except ValueError:
                continue
            if not relative.parts or all(
                part.casefold() not in skipped_names for part in relative.parts
            ):
                return True
        return False

    for index, raw_entry in enumerate(sys.path):
        entry = raw_entry if isinstance(raw_entry, str) else os.fspath(raw_entry)
        absolute = _absolute_lexical_path(Path(entry) if entry else project_root)
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
                if covered_by(resolved, covered_trees):
                    hasher.update(b"content-covered\0")
                else:
                    content_roots.add(resolved)
            else:
                try:
                    absolute.lstat()
                except FileNotFoundError:
                    # A truly absent sys.path entry is a fully observed state
                    # and can affect resolution order. A broken link is not
                    # equivalent and is handled by the successful lstat path.
                    hasher.update(b"missing-import-root\0")
                except OSError as exc:
                    hasher.update(f"import-root-error:{type(exc).__qualname__}\0".encode("ascii"))
                    reuse_safe = False
                else:
                    hasher.update(b"unsupported-import-root\0")
                    reuse_safe = False
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            hasher.update(f"import-root-error:{type(exc).__qualname__}\0".encode("ascii"))
            reuse_safe = False

    # Several ordinary CPython entries overlap (the interpreter root, Lib and
    # DLLs; a venv root and its site-packages).  Their ordered path semantics
    # were bound above. Walk each remaining byte tree only once while retaining
    # complete coverage of unclaimed modules and .pth files.
    selected_roots: list[Path] = []
    for root in sorted(
        content_roots,
        key=lambda item: (len(item.parts), os.path.normcase(str(item))),
    ):
        existing = tuple((candidate, _IMPORT_CONTEXT_SKIP_DIRS) for candidate in selected_roots)
        if covered_by(root, existing):
            continue
        selected_roots.append(root)
    for root in selected_roots:
        if not _hash_context_tree(
            hasher,
            root,
            label_prefix=f"sys.path:content:{root}",
            seen=seen,
            skip_dirs=_IMPORT_CONTEXT_SKIP_DIRS,
        ):
            reuse_safe = False
    return reuse_safe


def _installed_distribution_basis(project_root: Path, seen: set[Path]) -> _DependencyBasis:
    """Hash installed distribution bytes; mark any incomplete basis unsafe."""

    hasher = hashlib.sha256()
    _hash_inherited_environment(hasher)
    reuse_safe = _hash_runtime_identity(hasher, seen)
    try:
        resolved_project_root = project_root.resolve(strict=True)
    except (OSError, RuntimeError):
        resolved_project_root = _absolute_lexical_path(project_root)
    covered_trees: list[tuple[Path, frozenset[str]]] = [(resolved_project_root, _CONTEXT_SKIP_DIRS)]
    try:
        distributions = list(importlib.metadata.distributions())
    except Exception as exc:  # pragma: no cover - importlib backend failure
        hasher.update(f"enumeration-error:{type(exc).__qualname__}".encode("ascii"))
        return _DependencyBasis(hasher.hexdigest(), False)

    def distribution_key(distribution: importlib.metadata.Distribution) -> tuple[str, str, str]:
        try:
            name = distribution.metadata.get("Name") or ""
            version = distribution.version or ""
            location = str(Path(str(distribution.locate_file(""))).resolve(strict=False))
        except Exception:
            return ("", "", "")
        return (name.casefold(), version, location.casefold())

    for distribution in sorted(distributions, key=distribution_key):
        name, version, location = distribution_key(distribution)
        identity = f"distribution:{name}:{version}:{location}"
        hasher.update(identity.encode("utf-8", errors="surrogateescape"))
        hasher.update(b"\0")
        if not name or not version:
            reuse_safe = False

        try:
            files = distribution.files
        except Exception as exc:
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
                    hasher.update(
                        f"{identity}:{entry}:locate-error:{type(exc).__qualname__}\0".encode(
                            "utf-8", errors="surrogateescape"
                        )
                    )
                    reuse_safe = False
                    continue
                if not _hash_context_file(
                    hasher,
                    path,
                    label=f"{identity}:{entry}",
                    seen=seen,
                ):
                    reuse_safe = False

        try:
            direct_url = distribution.read_text("direct_url.json")
        except Exception as exc:
            hasher.update(f"{identity}:direct-url-error:{type(exc).__qualname__}\0".encode("ascii"))
            reuse_safe = False
            continue
        if direct_url is None:
            continue
        try:
            direct_payload = json.loads(direct_url)
        except JSONDecodeError:
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
        if not _hash_context_tree(
            hasher,
            editable_path,
            label_prefix=f"{identity}:editable",
            seen=seen,
        ):
            reuse_safe = False
        try:
            covered_trees.append((editable_path.resolve(strict=True), _CONTEXT_SKIP_DIRS))
        except (OSError, RuntimeError):
            reuse_safe = False

    if not _hash_effective_import_paths(hasher, project_root, seen, tuple(covered_trees)):
        reuse_safe = False

    return _DependencyBasis(hasher.hexdigest(), reuse_safe)


def build_stats_context_fingerprint(
    config: MutmutConfig,
    project_root: Path | None = None,
    *,
    excluded_paths: tuple[Path, ...] = (),
) -> str:
    """Hash project bytes, configuration and the effective dependency basis.

    This intentionally prefers conservative invalidation to a guessed import
    graph. Every automatically staged project file, explicit external tree and
    installed-distribution file can alter tests. If any distribution cannot be
    fully content-hashed, the returned digest is marked ``no-reuse`` so current
    run evidence stays deterministic but prior verdicts cannot be reused.
    """
    root = (project_root or Path.cwd()).resolve()
    excluded_resolved: set[Path] = set()
    for excluded in excluded_paths:
        candidate = excluded if excluded.is_absolute() else root / excluded
        try:
            excluded_resolved.add(candidate.resolve(strict=False))
        except (OSError, RuntimeError):
            excluded_resolved.add(candidate.absolute())

    hasher = hashlib.sha256()
    config_payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    hasher.update(config_payload.encode("utf-8"))
    hasher.update(b"\0")
    # Every pytest phase is pinned to one staged local config plus root and
    # confcut boundary. Project/config/dependency bytes below determine the
    # selected file; the schema marker prevents pre-boundary evidence reuse.
    hasher.update(b"pytest-boundary:v2\0")
    seen: set[Path] = set()
    reuse_safe = _hash_context_tree(
        hasher,
        root,
        label_prefix="project",
        seen=seen,
        excluded=excluded_resolved,
    )
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
            prefix = f"configured:{field_name}:{configured}"
            hasher.update(prefix.encode("utf-8"))
            hasher.update(b"\0")
            if absolute.is_file():
                try:
                    resolved_absolute = absolute.resolve(strict=False)
                except (OSError, RuntimeError):
                    resolved_absolute = absolute.absolute()
                if resolved_absolute in excluded_resolved:
                    hasher.update(b"excluded\0")
                    continue
                if not _hash_context_file(
                    hasher,
                    absolute,
                    label=prefix,
                    seen=seen,
                ):
                    reuse_safe = False
                continue
            if not absolute.is_dir():
                try:
                    absolute.lstat()
                except FileNotFoundError:
                    hasher.update(b"missing\0")
                    # Absence is a complete, observable state. Optional
                    # ``also_copy`` defaults deliberately name candidates that
                    # do not exist in every project; a later appearance changes
                    # this marker to a file/tree digest and invalidates reuse.
                except OSError as exc:
                    hasher.update(
                        f"unreadable:{type(exc).__qualname__}\0".encode(
                            "utf-8", errors="surrogateescape"
                        )
                    )
                    reuse_safe = False
                else:
                    # Broken links, devices and other unsupported entries are
                    # not the same as an observed absent optional path.
                    hasher.update(b"unsupported-configured-path\0")
                    reuse_safe = False
                continue
            if not _hash_context_tree(
                hasher,
                absolute,
                label_prefix=prefix,
                seen=seen,
                excluded=excluded_resolved,
            ):
                reuse_safe = False

    dependency_basis = _installed_distribution_basis(root, seen)
    hasher.update(b"installed-distributions\0")
    hasher.update(dependency_basis.digest.encode("ascii"))
    digest = hasher.hexdigest()
    if not dependency_basis.reuse_safe or not reuse_safe:
        return f"{_NO_REUSE_CONTEXT_PREFIX}{digest}"
    return digest


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


def build_run_basis_evidence(
    config: MutmutConfig,
    project_root: Path | None = None,
    *,
    excluded_paths: tuple[Path, ...] = (),
) -> RunBasisEvidence:
    """Hash the engine and inputs without erasing completeness information."""

    import mutmut_win

    context_fingerprint = build_stats_context_fingerprint(
        config,
        project_root,
        excluded_paths=excluded_paths,
    )
    payload = json.dumps(
        {
            "schema": 2,
            "engine_version": mutmut_win.__version__,
            "context_fingerprint": context_fingerprint,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return RunBasisEvidence(
        digest=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        complete=context_allows_result_reuse(context_fingerprint),
    )


def save_stats(
    stats: MutmutStats,
    mutants_dir: Path = Path("mutants"),
    *,
    refresh_file_fingerprints: bool = True,
) -> None:
    """Save *stats* to *mutants_dir*/mutmut-stats.json.

    The ``tests_by_mangled_function_name`` sets are serialised as sorted lists
    so the output is deterministic.

    Args:
        stats: The ``MutmutStats`` instance to persist.
        mutants_dir: Existing real target directory. Defaults to ``mutants/``;
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
    mutants_dir: Path = Path("mutants"),
    *,
    context_fingerprint: str | None = None,
) -> MutmutStats:
    """Load cached stats or collect fresh ones via *runner*.

    If cached stats exist, checks for new tests and re-collects only for those
    (incremental update). Otherwise, runs a full stats collection.

    This mirrors mutmut 3.5.0's ``collect_or_load_stats()`` behavior:
    1. Try to load cached stats from JSON.
    2. If loaded, list current tests and compare against cached test names.
    3. If new tests found, re-run stats collection for those tests only.
    4. If no cached stats, run full collection.

    Args:
        runner: ``PytestRunner`` instance.
        mutants_dir: Directory where the stats JSON file lives.

    Returns:
        A ``MutmutStats`` instance.
    """
    cached = load_stats(mutants_dir)
    if cached is None:
        return _run_stats_collection(
            runner, mutants_dir, cached=None, context_fingerprint=context_fingerprint
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
    written JSON may be partial — it is neither loaded nor trusted; the
    pre-run *cached* copy is restored to disk (healing a partial write) and
    returned. Without any cache, the full-suite fallback is announced
    loudly instead of silently degrading every mutant run.

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
    with contextlib.suppress(FileNotFoundError):
        stats_path.unlink()
    try:
        exit_code = runner.run_stats()
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

    def clear_out_obsolete_test_names(self, mutants_dir: Path = Path("mutants")) -> None:
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
        killed: Number of mutants killed by tests, including infinite-loop
            kills (matching the run gate and the ``results`` command).
        survived: Number of surviving (un-killed) mutants.
        total: Total number of mutants generated.
        no_tests: Number of mutants with no covering tests.
        skipped: Number of explicitly skipped mutants.
        suspicious: Number of mutants with suspicious exit codes.
        timeout: Number of timed-out mutants.
        check_was_interrupted_by_user: Number of mutants interrupted by the user.
        segfault: Number of mutants that caused a segfault.
        caught_by_type_check: Number of mutants caught by the type checker.
        killed_by_infinite_loop: Subset of ``killed`` that was classified as
            an infinite loop by the IL detector.
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

        ``killed`` already includes infinite-loop kills (#86); the type
        checker and a crash under a mutant are detections too.
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

        The numerator is the kill class: ``killed`` (which already includes
        infinite-loop kills, #86) plus ``caught_by_type_check`` plus
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
                # An IL kill IS a kill — the run gate and `results` already
                # count it that way; before #86 it silently deflated the score.
                stats.killed += 1
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
