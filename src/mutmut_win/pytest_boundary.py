"""One immutable pytest configuration/root boundary for every run phase."""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeGuard

from mutmut_win.atomic_file import create_exclusive_random_bytes
from mutmut_win.exceptions import PytestBoundaryError

_BOUNDARY_SCHEMA = 2
_LEGACY_CONFIG_NAMES = (
    "pytest.ini",
    ".pytest.ini",
    "pyproject.toml",
    "tox.ini",
    "setup.cfg",
)
_PYTEST_9_CONFIG_NAMES = ("pytest.toml", ".pytest.toml", *_LEGACY_CONFIG_NAMES)
_EMPTY_CONFIG_BYTES = b"[pytest]\n"
_EMPTY_CONFIG_PREFIX = ".mutmut-win-pytest-"
_EMPTY_CONFIG_SUFFIX = ".ini"

_TestPathKind = Literal["directory", "file", "missing"]


def _is_int(value: object) -> TypeGuard[int]:
    return type(value) is int


def _is_test_path_kind(value: object) -> TypeGuard[_TestPathKind]:
    return isinstance(value, str) and value in {"directory", "file", "missing"}


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _absolute_lexical(path: Path) -> Path:
    # Deliberately normalize without resolving links: comparison with the
    # separately resolved path is how initial indirection is detected.
    return Path(os.path.abspath(os.fspath(path)))  # noqa: PTH100


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _identity(file_stat: os.stat_result) -> tuple[int, int]:
    return file_stat.st_dev, file_stat.st_ino


def _usable_identity(file_stat: os.stat_result, description: str) -> tuple[int, int]:
    identity = _identity(file_stat)
    if identity[0] < 0 or identity[1] <= 0:
        raise PytestBoundaryError(
            f"{description} filesystem does not expose a stable device/inode identity."
        )
    return identity


def _reject_indirected_components(path: Path, description: str) -> None:
    """Reject symlink/reparse indirection in every existing path component."""

    for component in reversed((path, *path.parents)):
        try:
            component_stat = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PytestBoundaryError(
                f"Could not inspect a {description} path component: {component}"
            ) from exc
        if stat.S_ISLNK(component_stat.st_mode) or _is_reparse_point(component_stat):
            raise PytestBoundaryError(
                f"{description} path contains a link or reparse point: {component}"
            )


def _real_path_snapshot(
    path: Path,
    *,
    kind: Literal["directory", "file"],
    description: str,
) -> tuple[Path, os.stat_result]:
    """Return a canonical real-path snapshot, rejecting all indirection."""

    lexical = _absolute_lexical(path)
    _reject_indirected_components(lexical, description)
    try:
        resolved = lexical.resolve(strict=True)
        leaf = lexical.lstat()
    except (OSError, RuntimeError) as exc:
        raise PytestBoundaryError(f"Could not inspect {description}: {lexical}") from exc
    if stat.S_ISLNK(leaf.st_mode) or _is_reparse_point(leaf):
        raise PytestBoundaryError(f"{description} must not be a link or reparse point: {lexical}")
    if kind == "directory" and not stat.S_ISDIR(leaf.st_mode):
        raise PytestBoundaryError(f"{description} must be a directory: {lexical}")
    if kind == "file" and not stat.S_ISREG(leaf.st_mode):
        raise PytestBoundaryError(f"{description} must be a regular file: {lexical}")
    if kind == "file" and leaf.st_nlink != 1:
        raise PytestBoundaryError(f"{description} must not be hard-linked: {lexical}")
    try:
        resolved_stat = resolved.stat()
    except OSError as exc:
        raise PytestBoundaryError(f"Could not stat {description}: {resolved}") from exc
    leaf_identity = _usable_identity(leaf, description)
    resolved_identity = _usable_identity(resolved_stat, description)
    if leaf_identity != resolved_identity:
        raise PytestBoundaryError(f"{description} changed while it was inspected: {lexical}")
    return resolved, resolved_stat


def _pytest_config_names() -> tuple[str, ...]:
    """Return config precedence for the installed, basis-bound pytest."""

    try:
        version = importlib.metadata.version("pytest")
        parts = version.split(".", 2)
        major = int(parts[0])
        minor = int(parts[1])
    except (IndexError, ValueError, importlib.metadata.PackageNotFoundError) as exc:
        raise PytestBoundaryError("Could not determine the installed pytest version.") from exc
    if major == 8 and minor >= 2:
        return _LEGACY_CONFIG_NAMES
    if major == 9:
        return _PYTEST_9_CONFIG_NAMES
    raise PytestBoundaryError(
        f"pytest {version} has no validated config-discovery boundary implementation."
    )


def _test_path_text(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "\x00" in raw or "\n" in raw or "\r" in raw:
        raise PytestBoundaryError(f"Invalid pytest test target {raw!r}.")
    if raw.startswith(("-", "@")):
        raise PytestBoundaryError(
            f"pytest tests_dir entries must be paths, not options or argument files: {raw!r}"
        )
    path_text = raw.split("::", 1)[0]
    if not path_text:
        raise PytestBoundaryError(f"Invalid pytest test target {raw!r}.")
    return path_text


def _test_path(raw: str) -> Path:
    path = Path(_test_path_text(raw))
    if os.name == "nt" and not path.is_absolute() and (path.drive or path.root):
        raise PytestBoundaryError(
            f"pytest test target must be fully absolute or staging-relative: {raw!r}"
        )
    return path


def _actual_test_path(raw: str, staging_root: Path) -> Path:
    path = _test_path(raw)
    return _absolute_lexical(path if path.is_absolute() else staging_root / path)


def _mapped_test_start(
    raw: str,
    *,
    project_root: Path,
    staging_root: Path,
) -> Path | None:
    """Map one configured test target to its staged discovery directory."""

    path = _test_path(raw)
    if path.is_absolute():
        try:
            path = path.resolve(strict=False).relative_to(project_root)
        except (
            OSError,
            RuntimeError,
            ValueError,
        ):
            # Explicit external tests are identity-bound separately. They must
            # not move pytest's authoritative staging configuration boundary.
            return None
    candidate = (staging_root / path).resolve(strict=False)
    try:
        candidate.relative_to(staging_root)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate.parent
    if candidate.is_dir():
        return candidate
    return None


def _mapped_test_starts(
    staging_root: Path,
    project_root: Path,
    tests_dir: list[str],
) -> list[Path]:
    starts: list[Path] = []
    for raw in tests_dir:
        candidate = _mapped_test_start(
            raw,
            project_root=project_root,
            staging_root=staging_root,
        )
        if candidate is not None and candidate not in starts:
            starts.append(candidate)
    return starts


def _common_start(staging_root: Path, starts: list[Path]) -> Path:
    if not starts:
        return staging_root
    try:
        common = Path(os.path.commonpath([str(path) for path in starts])).resolve(strict=False)
        common.relative_to(staging_root)
    except (
        OSError,
        RuntimeError,
        ValueError,
    ):
        return staging_root
    return common


def _bounded_ancestors(start: Path, staging_root: Path) -> tuple[Path, ...]:
    try:
        start.relative_to(staging_root)
    except ValueError as exc:  # pragma: no cover - caller maps starts into staging
        raise PytestBoundaryError("pytest config search escaped staging.") from exc
    result: list[Path] = []
    current = start
    while True:
        result.append(current)
        if current == staging_root:
            return tuple(result)
        parent = current.parent
        if parent == current:
            raise PytestBoundaryError("pytest config search reached the filesystem root.")
        current = parent


def _load_config_candidate(candidate: Path) -> object | None:
    try:
        from _pytest.config.findpaths import load_config_dict_from_file
    except ImportError as exc:  # pragma: no cover - guarded by pytest preflight
        raise PytestBoundaryError(
            "The installed pytest cannot resolve its config boundary."
        ) from exc

    resolved, _candidate_stat = _real_path_snapshot(
        candidate,
        kind="file",
        description="staged pytest config",
    )
    try:
        return load_config_dict_from_file(resolved)
    except (
        KeyboardInterrupt,
        SystemExit,
    ):
        raise
    except BaseException as exc:
        raise PytestBoundaryError(
            f"Could not parse staged pytest config {candidate}: {exc}"
        ) from exc


def _bounded_locate_config(
    staging_root: Path,
    starts: tuple[Path, ...],
) -> Path | None:
    """Mirror pytest's ordered locate_config search without leaving staging."""

    config_names = _pytest_config_names()
    found_pyproject: Path | None = None
    for start in starts:
        for current in _bounded_ancestors(start, staging_root):
            for name in config_names:
                candidate = current / name
                try:
                    leaf = candidate.lstat()
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise PytestBoundaryError(
                        f"Could not inspect staged pytest config {candidate}."
                    ) from exc
                if stat.S_ISLNK(leaf.st_mode) or _is_reparse_point(leaf):
                    raise PytestBoundaryError(
                        f"pytest config must be a real regular file inside staging: {candidate}"
                    )
                if not stat.S_ISREG(leaf.st_mode):
                    # Match Path.is_file() in pytest's locate_config: a plain
                    # directory or special leaf with a config-looking name is
                    # not a candidate. Links/reparse points remain fail-closed.
                    continue
                parsed = _load_config_candidate(candidate)
                resolved = candidate.resolve(strict=True)
                if name == "pyproject.toml" and found_pyproject is None:
                    found_pyproject = resolved
                if parsed is not None:
                    return resolved
    return found_pyproject


def _has_bounded_setup_py(common: Path, staging_root: Path) -> bool:
    """Mirror pytest's setup.py presence probe without following links."""

    for ancestor in _bounded_ancestors(common, staging_root):
        candidate = ancestor / "setup.py"
        try:
            leaf = candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PytestBoundaryError(f"Could not inspect staged setup.py {candidate}.") from exc
        if stat.S_ISLNK(leaf.st_mode) or _is_reparse_point(leaf):
            raise PytestBoundaryError(
                f"staged setup.py must not be a link or reparse point: {candidate}"
            )
        if stat.S_ISREG(leaf.st_mode):
            return True
    return False


def _local_config_path(
    staging_root: Path,
    project_root: Path,
    tests_dir: list[str],
) -> Path | None:
    """Mirror pytest 8/9 discovery, bounded strictly to the staging root."""

    starts = _mapped_test_starts(staging_root, project_root, tests_dir)
    common = _common_start(staging_root, starts)
    config = _bounded_locate_config(staging_root, (common,))
    if config is not None:
        return config

    # pytest checks setup.py before its per-directory fallback. A setup.py
    # fixes rootdir but does not itself become an ini/config file.
    if _has_bounded_setup_py(common, staging_root):
        return None
    if starts != [common]:
        return _bounded_locate_config(staging_root, tuple(starts))
    return None


@dataclass(frozen=True)
class _TestPathSnapshot:
    lexical_path: str
    canonical_path: str
    kind: _TestPathKind
    st_dev: int | None
    st_ino: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "lexical_path": self.lexical_path,
            "canonical_path": self.canonical_path,
            "kind": self.kind,
            "st_dev": self.st_dev,
            "st_ino": self.st_ino,
        }

    @classmethod
    def from_dict(cls, value: object) -> _TestPathSnapshot:
        if not isinstance(value, dict):
            raise PytestBoundaryError("Worker received a malformed pytest test-path boundary.")
        lexical_path = value.get("lexical_path")
        canonical_path = value.get("canonical_path")
        kind = value.get("kind")
        st_dev = value.get("st_dev")
        st_ino = value.get("st_ino")
        if (
            not isinstance(lexical_path, str)
            or not isinstance(canonical_path, str)
            or not _is_test_path_kind(kind)
        ):
            raise PytestBoundaryError("Worker received a malformed pytest test-path boundary.")
        if kind == "missing":
            if st_dev is not None or st_ino is not None:
                raise PytestBoundaryError(
                    "Worker received a malformed missing pytest test-path boundary."
                )
        elif not _is_int(st_dev) or st_dev < 0 or not _is_int(st_ino) or st_ino <= 0:
            raise PytestBoundaryError("Worker received a malformed pytest test-path identity.")
        return cls(
            lexical_path=lexical_path,
            canonical_path=canonical_path,
            kind=kind,
            st_dev=st_dev,
            st_ino=st_ino,
        )


def _snapshot_test_paths(tests_dir: list[str], staging_root: Path) -> tuple[_TestPathSnapshot, ...]:
    snapshots: list[_TestPathSnapshot] = []
    seen: set[str] = set()
    for raw in tests_dir:
        lexical = _actual_test_path(raw, staging_root)
        key = os.path.normcase(str(lexical))
        if key in seen:
            continue
        seen.add(key)
        try:
            leaf = lexical.lstat()
        except FileNotFoundError:
            _reject_indirected_components(lexical.parent, "pytest test target")
            try:
                canonical = lexical.resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                raise PytestBoundaryError(
                    f"Could not resolve missing pytest test target {lexical}."
                ) from exc
            snapshots.append(
                _TestPathSnapshot(
                    lexical_path=str(lexical),
                    canonical_path=str(canonical),
                    kind="missing",
                    st_dev=None,
                    st_ino=None,
                )
            )
            continue
        except OSError as exc:
            raise PytestBoundaryError(f"Could not inspect pytest test target {lexical}.") from exc

        if stat.S_ISDIR(leaf.st_mode):
            kind: Literal["directory", "file"] = "directory"
        elif stat.S_ISREG(leaf.st_mode):
            kind = "file"
        else:
            raise PytestBoundaryError(
                f"pytest test target must be a real directory or regular file: {lexical}"
            )
        canonical, target_stat = _real_path_snapshot(
            lexical,
            kind=kind,
            description="pytest test target",
        )
        snapshots.append(
            _TestPathSnapshot(
                lexical_path=str(lexical),
                canonical_path=str(canonical),
                kind=kind,
                st_dev=target_stat.st_dev,
                st_ino=target_stat.st_ino,
            )
        )
    return tuple(snapshots)


def _validate_bound_path(
    path_text: str,
    *,
    expected_dev: int,
    expected_ino: int,
    kind: Literal["directory", "file"],
    description: str,
) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        raise PytestBoundaryError(f"{description} path must be absolute.")
    _reject_indirected_components(path, description)
    try:
        resolved = path.resolve(strict=True)
        resolved_stat = resolved.stat()
        leaf = path.lstat()
    except (OSError, RuntimeError) as exc:
        raise PytestBoundaryError(f"{description} escaped or disappeared.") from exc
    if stat.S_ISLNK(leaf.st_mode) or _is_reparse_point(leaf):
        raise PytestBoundaryError(f"{description} became a link or reparse point.")
    if kind == "directory" and not stat.S_ISDIR(leaf.st_mode):
        raise PytestBoundaryError(f"{description} is no longer a directory.")
    if kind == "file" and not stat.S_ISREG(leaf.st_mode):
        raise PytestBoundaryError(f"{description} is no longer a regular file.")
    if kind == "file" and leaf.st_nlink != 1:
        raise PytestBoundaryError(f"{description} became hard-linked.")
    if expected_dev < 0 or expected_ino <= 0:
        raise PytestBoundaryError(f"{description} has no usable frozen identity.")
    if _usable_identity(leaf, description) != (expected_dev, expected_ino):
        raise PytestBoundaryError(f"{description} identity changed after it was frozen.")
    if _usable_identity(resolved_stat, description) != (expected_dev, expected_ino):
        raise PytestBoundaryError(f"{description} was redirected after it was frozen.")
    return resolved


def _validate_test_path(snapshot: _TestPathSnapshot) -> Path | None:
    lexical = Path(snapshot.lexical_path)
    canonical = Path(snapshot.canonical_path)
    if not lexical.is_absolute() or not canonical.is_absolute():
        raise PytestBoundaryError("pytest test-path boundary paths must be absolute.")
    if snapshot.kind == "missing":
        _reject_indirected_components(lexical.parent, "pytest test target")
        try:
            lexical.lstat()
        except FileNotFoundError:
            try:
                current = lexical.resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                raise PytestBoundaryError(
                    f"Could not revalidate missing pytest test target {lexical}."
                ) from exc
            if not _same_path(current, canonical):
                raise PytestBoundaryError(
                    f"Missing pytest test target path changed after it was frozen: {lexical}"
                ) from None
            return None
        except OSError as exc:
            raise PytestBoundaryError(
                f"Could not revalidate missing pytest test target {lexical}."
            ) from exc
        raise PytestBoundaryError(f"Missing pytest test target appeared during the run: {lexical}")

    if snapshot.st_dev is None or snapshot.st_ino is None:  # pragma: no cover - parsed invariant
        raise PytestBoundaryError("pytest test target has no frozen identity.")
    resolved = _validate_bound_path(
        snapshot.lexical_path,
        expected_dev=snapshot.st_dev,
        expected_ino=snapshot.st_ino,
        kind=snapshot.kind,
        description="pytest test target",
    )
    if not _same_path(resolved, canonical):
        raise PytestBoundaryError(
            f"pytest test target canonical path changed after it was frozen: {lexical}"
        )
    return resolved


def _read_bound_config(path: Path, *, expected_dev: int, expected_ino: int) -> bytes:
    try:
        with path.open("rb") as config_file:
            before = os.fstat(config_file.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or _usable_identity(before, "staged pytest config") != (expected_dev, expected_ino)
                or before.st_nlink != 1
            ):
                raise PytestBoundaryError("Staged pytest config identity changed before reading.")
            payload = config_file.read()
            after = os.fstat(config_file.fileno())
    except PytestBoundaryError:
        raise
    except OSError as exc:
        raise PytestBoundaryError(f"Could not read staged pytest config {path}.") from exc
    if (
        _usable_identity(after, "staged pytest config") != (expected_dev, expected_ino)
        or after.st_size != before.st_size
        or after.st_mtime_ns != before.st_mtime_ns
        or len(payload) != after.st_size
    ):
        raise PytestBoundaryError(f"Staged pytest config changed while it was read: {path}")
    return payload


@dataclass(frozen=True)
class PytestAllowedPathIdentity:
    """One validated collection root or exact file with its frozen identity."""

    canonical_path: Path
    kind: Literal["directory", "file"]
    st_dev: int
    st_ino: int


def _allowed_identity_sort_key(record: PytestAllowedPathIdentity) -> tuple[str, str]:
    return (
        os.path.normcase(str(record.canonical_path)),
        record.kind,
    )


@dataclass(frozen=True)
class PytestBoundary:
    """Serialized proof of the exact staged pytest execution boundary."""

    staging_root: str
    config_path: str
    config_sha256: str
    staging_dev: int
    staging_ino: int
    config_dev: int
    config_ino: int
    test_paths: tuple[_TestPathSnapshot, ...]
    schema: int = _BOUNDARY_SCHEMA

    def _validated_paths(self) -> tuple[Path, Path]:
        if self.schema != _BOUNDARY_SCHEMA:
            raise PytestBoundaryError(f"Unsupported pytest boundary schema {self.schema}.")
        root = _validate_bound_path(
            self.staging_root,
            expected_dev=self.staging_dev,
            expected_ino=self.staging_ino,
            kind="directory",
            description="pytest staging root",
        )
        config = _validate_bound_path(
            self.config_path,
            expected_dev=self.config_dev,
            expected_ino=self.config_ino,
            kind="file",
            description="pytest config",
        )
        try:
            config.relative_to(root)
        except ValueError as exc:
            raise PytestBoundaryError("pytest config escaped the frozen staging root.") from exc

        payload = _read_bound_config(
            config,
            expected_dev=self.config_dev,
            expected_ino=self.config_ino,
        )
        actual_digest = hashlib.sha256(payload).hexdigest()
        if actual_digest != self.config_sha256:
            raise PytestBoundaryError(
                f"Staged pytest config changed after the run boundary was prepared: {config}"
            )
        for snapshot in self.test_paths:
            _validate_test_path(snapshot)
        # Catch config/root replacements that raced the handle read or target
        # validation. The final returned paths therefore come from fresh,
        # identity-bound resolutions rather than an earlier path snapshot.
        config = _validate_bound_path(
            self.config_path,
            expected_dev=self.config_dev,
            expected_ino=self.config_ino,
            kind="file",
            description="pytest config",
        )
        root = _validate_bound_path(
            self.staging_root,
            expected_dev=self.staging_dev,
            expected_ino=self.staging_ino,
            kind="directory",
            description="pytest staging root",
        )
        try:
            config.relative_to(root)
        except ValueError as exc:
            raise PytestBoundaryError("pytest config escaped the frozen staging root.") from exc
        return root, config

    def arguments(self) -> list[str]:
        """Validate the snapshot and return invariant pytest CLI arguments."""

        root, config = self._validated_paths()
        return [
            "-c",
            str(config),
            f"--rootdir={root}",
            f"--confcutdir={root}",
        ]

    def canonical_allowed_test_paths(self) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
        """Return validated canonical allowed directories and exact files.

        The first tuple always contains the staging root. Existing explicit
        targets outside staging add either one directory root or one exact file;
        targets inside staging are already covered by the staging root.
        """

        identities = self.canonical_allowed_test_identities()
        return (
            tuple(record.canonical_path for record in identities if record.kind == "directory"),
            tuple(record.canonical_path for record in identities if record.kind == "file"),
        )

    def canonical_allowed_test_identities(self) -> tuple[PytestAllowedPathIdentity, ...]:
        """Return fully revalidated canonical collection identity records.

        The first record is always the staging directory with the identity
        frozen in this boundary. Existing explicit targets outside staging
        follow as directory roots or exact files. Missing targets are absence-
        bound by validation but do not authorize a collection location.
        """

        root, _config = self._validated_paths()
        external: dict[tuple[str, str], PytestAllowedPathIdentity] = {}
        for snapshot in self.test_paths:
            target = _validate_test_path(snapshot)
            if target is None:
                continue
            try:
                target.relative_to(root)
                is_internal = True
            except ValueError:
                is_internal = False
            if not is_internal:
                if snapshot.kind == "missing":  # pragma: no cover - target is not None
                    raise PytestBoundaryError("missing pytest test target unexpectedly resolved.")
                if snapshot.st_dev is None or snapshot.st_ino is None:  # pragma: no cover
                    raise PytestBoundaryError("pytest test target has no frozen identity.")
                record = PytestAllowedPathIdentity(
                    canonical_path=target,
                    kind=snapshot.kind,
                    st_dev=snapshot.st_dev,
                    st_ino=snapshot.st_ino,
                )
                external[(os.path.normcase(str(target)), snapshot.kind)] = record

        root_record = PytestAllowedPathIdentity(
            canonical_path=root,
            kind="directory",
            st_dev=self.staging_dev,
            st_ino=self.staging_ino,
        )

        return (root_record, *sorted(external.values(), key=_allowed_identity_sort_key))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "staging_root": self.staging_root,
            "config_path": self.config_path,
            "config_sha256": self.config_sha256,
            "staging_dev": self.staging_dev,
            "staging_ino": self.staging_ino,
            "config_dev": self.config_dev,
            "config_ino": self.config_ino,
            "test_paths": [snapshot.to_dict() for snapshot in self.test_paths],
        }

    @classmethod
    def from_dict(cls, value: object) -> PytestBoundary:
        if not isinstance(value, dict):
            raise PytestBoundaryError("Worker received no valid pytest boundary.")
        schema = value.get("schema")
        staging_root = value.get("staging_root")
        config_path = value.get("config_path")
        config_sha256 = value.get("config_sha256")
        staging_dev = value.get("staging_dev")
        staging_ino = value.get("staging_ino")
        config_dev = value.get("config_dev")
        config_ino = value.get("config_ino")
        raw_test_paths = value.get("test_paths")
        if (
            not _is_int(schema)
            or not isinstance(staging_root, str)
            or not isinstance(config_path, str)
            or not isinstance(config_sha256, str)
            or len(config_sha256) != 64
            or any(char not in "0123456789abcdef" for char in config_sha256)
            or not _is_int(staging_dev)
            or staging_dev < 0
            or not _is_int(staging_ino)
            or staging_ino <= 0
            or not _is_int(config_dev)
            or config_dev < 0
            or not _is_int(config_ino)
            or config_ino <= 0
            or not isinstance(raw_test_paths, list)
        ):
            raise PytestBoundaryError("Worker received a malformed pytest boundary.")
        test_paths = tuple(_TestPathSnapshot.from_dict(item) for item in raw_test_paths)
        return cls(
            schema=schema,
            staging_root=staging_root,
            config_path=config_path,
            config_sha256=config_sha256,
            staging_dev=staging_dev,
            staging_ino=staging_ino,
            config_dev=config_dev,
            config_ino=config_ino,
            test_paths=test_paths,
        )


def prepare_pytest_boundary(
    *,
    project_root: Path,
    staging_root: Path,
    tests_dir: list[str],
) -> PytestBoundary:
    """Select/materialize and identity-bind one staged pytest boundary."""

    try:
        project = project_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PytestBoundaryError("Could not resolve the pytest project boundary.") from exc
    if not project.is_dir():
        raise PytestBoundaryError("pytest project boundary must reference a directory.")
    staging, staging_stat = _real_path_snapshot(
        staging_root,
        kind="directory",
        description="pytest staging root",
    )
    try:
        staging.relative_to(project)
    except ValueError as exc:
        raise PytestBoundaryError("pytest staging must remain inside the project root.") from exc

    test_paths = _snapshot_test_paths(tests_dir, staging)
    config = _local_config_path(staging, project, tests_dir)
    fallback_identity: tuple[int, int] | None = None
    if config is None:
        try:
            config, fallback_identity = create_exclusive_random_bytes(
                staging,
                _EMPTY_CONFIG_BYTES,
                prefix=_EMPTY_CONFIG_PREFIX,
                suffix=_EMPTY_CONFIG_SUFFIX,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise PytestBoundaryError(
                f"Could not publish a private staged pytest config in {staging}."
            ) from exc

    config, config_stat = _real_path_snapshot(
        config,
        kind="file",
        description="staged pytest config",
    )
    if fallback_identity is not None and _identity(config_stat) != fallback_identity:
        raise PytestBoundaryError("Private staged pytest config identity changed before freeze.")
    try:
        config.relative_to(staging)
    except ValueError as exc:
        raise PytestBoundaryError("pytest config must remain inside staging.") from exc
    payload = _read_bound_config(
        config,
        expected_dev=config_stat.st_dev,
        expected_ino=config_stat.st_ino,
    )
    if fallback_identity is not None and payload != _EMPTY_CONFIG_BYTES:
        raise PytestBoundaryError("Private staged pytest config changed before freeze.")
    boundary = PytestBoundary(
        staging_root=str(staging),
        config_path=str(config),
        config_sha256=hashlib.sha256(payload).hexdigest(),
        staging_dev=staging_stat.st_dev,
        staging_ino=staging_stat.st_ino,
        config_dev=config_stat.st_dev,
        config_ino=config_stat.st_ino,
        test_paths=test_paths,
    )
    boundary.arguments()
    return boundary
