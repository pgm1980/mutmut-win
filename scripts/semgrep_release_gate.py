"""Fail-closed Semgrep release gate for the Git-owned Python product surface.

The scanner never runs in the repository itself.  This wrapper inventories every
tracked or non-ignored untracked file in the release-relevant roots, copies the
files into an external byte-identical mirror, and proves that neither side moved
while Semgrep was running.  Runtime code, tests, shipped E2E fixtures, release
scripts, and project-authored benchmarks are all scanned without policy skips.

The module intentionally uses only the Python standard library so that the gate
does not depend on the environment it is intended to audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final

SEMGREP_VERSION: Final = "1.175.0"
SEMGREP_ENGINE: Final = "OSS"
SEMGREP_BOOTSTRAP_JOBS: Final = "4"
# Semgrep 1.175 uses shared-memory parallelism for ``--jobs``.  On constrained
# Windows CI runners, concurrent taint analyses can exceed the engine's
# fixpoint budget even though the identical scan completes serially.  A
# release gate values complete, deterministic analysis over throughput.
SEMGREP_SCAN_JOBS: Final = "1"
# Expanding the audited surface to shipped JSON fixtures added exactly four
# applicable rules to the historical 342-ID set (and no removals): the three
# ``json.aws.security`` S3/assume-role checks and Renovate's
# ``renovate-missing-minimum-release-age`` check.  The downloaded definition
# bundle itself remains byte-identical to the reviewed 1,074-rule contract.
SEMGREP_RULE_COUNT: Final = 346
SEMGREP_RULE_IDS_SHA256: Final = "4318213bc02b54092f7fe2b48fffe7afd77cdb92399df23c14b20a3b856a3feb"
RULE_DEFINITION_COUNT: Final = 1_074
RULE_DEFINITIONS_SHA256: Final = "b6e589b3bdcdf6eb2086765c0cdb3b128bda6d9b26e42cd36852e093cd1d601e"
RULE_BUNDLE_SIZE: Final = 2_192_939
RULE_BUNDLE_SHA256: Final = "76b5a021560070925e9b86f93d2e61153b72ab6a7e306c0d49e1677bb07cbce5"
EVIDENCE_SCHEMA_VERSION: Final = 1
SCAN_ROOTS: Final = ("src", "tests", "scripts", "benchmarks")
POLICY_SKIP_PREFIXES: Final[tuple[str, ...]] = ()
SEMGREP_IGNORE_FILE: Final = ".semgrepignore"

type Command = tuple[str, ...]
type Environment = Mapping[str, str]
type Runner = Callable[[Command, Path, Environment], subprocess.CompletedProcess[bytes]]
type ExecutableFinder = Callable[[str], str | None]


class GateError(RuntimeError):
    """A release-gate contract violation with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RuleContract:
    """Pinned identity of the rules applied by the local bundle scan."""

    count: int
    ids_sha256: str


DEFAULT_RULE_CONTRACT: Final = RuleContract(
    count=SEMGREP_RULE_COUNT,
    ids_sha256=SEMGREP_RULE_IDS_SHA256,
)


@dataclass(frozen=True)
class ShardContract:
    index: int
    size: int
    definition_count: int


@dataclass(frozen=True)
class BundleContract:
    shards: tuple[ShardContract, ...]
    definition_count: int
    definitions_sha256: str
    bundle_size: int
    bundle_sha256: str


DEFAULT_BUNDLE_CONTRACT: Final = BundleContract(
    shards=(
        ShardContract(0, 548_219, 268),
        ShardContract(1, 548_246, 268),
        ShardContract(2, 548_284, 269),
        ShardContract(3, 548_223, 269),
    ),
    definition_count=RULE_DEFINITION_COUNT,
    definitions_sha256=RULE_DEFINITIONS_SHA256,
    bundle_size=RULE_BUNDLE_SIZE,
    bundle_sha256=RULE_BUNDLE_SHA256,
)


@dataclass(frozen=True, order=True)
class FindingSignature:
    """A finding bound to its rule, span, involved lines, and full source context.

    ``file_sha256`` hashes the complete mirror file after strict UTF-8 decoding
    and normalization of CRLF or bare CR to LF.  Other Unicode separators stay
    byte-significant.  No synthetic trailing LF is added.  This makes ordinary
    CRLF/LF checkouts equivalent without allowing context outside the finding
    span to drift.
    """

    path: str
    check_id: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    lines_sha256: str
    file_sha256: str


_POPEN_RULE: Final = "python.lang.compatibility.python36.python36-compatibility-Popen2"
_IMPORT_RULE: Final = "python.lang.security.audit.non-literal-import.non-literal-import"
_EXEC_RULE: Final = "python.lang.security.audit.exec-detected.exec-detected"
_PICKLE_RULE: Final = "python.lang.security.deserialization.pickle.avoid-pickle"
_KILL_PROC_FILE_SHA: Final = "aff81671be553a2da9ef0a006baec1bdc8b01133601d3834da9a90fa72a2cb32"
_ARCHITECTURE_FILE_SHA: Final = "9ad23a3d71a02756b65dfba018d80d651aa4fa3681b207cb07c92c94aa08542c"
_CLASS_BODY_FILE_SHA: Final = "81ce773253c18c42ce5ace134f08c6a3290b05666709c43cc620686106c30706"
_DUPLICATE_DEFINITIONS_FILE_SHA: Final = (
    "874635fc0f8b82ef1d8ba4cac975e4bffc7f7712ad7f37d4191c21a7cd40637b"
)
_MODELS_FILE_SHA: Final = "cfcd968a3ee16aedadfe1b1a61a95b5418c62537b7c4a02db99cf9ee5915a43a"
_MUTANT_DIFF_FILE_SHA: Final = "94e89108069d2cd5f924ef02a3cd8f4e60057dc6cb328f94b23ebdf7cf71e967"
_MUTATION_ADVERSARIAL_FILE_SHA: Final = (
    "9bbaac97643cb3dffa9143688aac92a7f48372e2c5198f30ac616e4356b55f57"
)
_MUTATION_HARDENING_FILE_SHA: Final = (
    "f8661ec3c4a78e9d9daa1d519a29a791899ee5b892fdf08aeadfd4ad31943ce8"
)
_SITECUSTOMIZE_FILE_SHA: Final = "991169a46ec355325d51178e193e4df8caa6f6647c0a754a9542686f6c2b63bb"
_STATICMETHOD_FILE_SHA: Final = "d9707d4b429b3274fcebf64b52eaa9f747df9973c0045821b574569f7cae62ca"
_WRAPPER_CODEGEN_FILE_SHA: Final = (
    "4b4f889f82a17909ad29fad1c5f48ef667823442ac84a3b6f3ccd7df5137432b"
)


DEFAULT_FINDING_ALLOWLIST: Final = (
    FindingSignature(
        "tests/integration/test_kill_proc_tree.py",
        _POPEN_RULE,
        74,
        16,
        78,
        10,
        "5702c9eb93300dd4f618af4c583c67973c7e775c3ffa98aa4b9069377c04fd72",
        _KILL_PROC_FILE_SHA,
    ),
    FindingSignature(
        "tests/integration/test_kill_proc_tree.py",
        _POPEN_RULE,
        101,
        16,
        105,
        10,
        "5702c9eb93300dd4f618af4c583c67973c7e775c3ffa98aa4b9069377c04fd72",
        _KILL_PROC_FILE_SHA,
    ),
    FindingSignature(
        "tests/test_architecture.py",
        _IMPORT_RULE,
        40,
        20,
        40,
        46,
        "d454e85371f697f3da8ea2205f9a4db0316cc71e28d017a6b30cc8c0ffc9f40e",
        _ARCHITECTURE_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_class_body_injection.py",
        _EXEC_RULE,
        27,
        9,
        27,
        52,
        "25c3ef5ae09a655446756e71bc8771a63e517836bcf7c3a247d64597cd82d64a",
        _CLASS_BODY_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_class_body_injection.py",
        _EXEC_RULE,
        88,
        13,
        88,
        56,
        "8a53a564916e0e3791fddce82e7659a80d021ab5994563bbc4b1effabc7c4ba4",
        _CLASS_BODY_FILE_SHA,
    ),
    # The generated source and namespace are both test-owned constants.  This
    # executes the trampoline twice to prove that a source name containing the
    # reserved mutant delimiter remains reversible and collision-free.
    FindingSignature(
        "tests/unit/test_duplicate_definitions_220.py",
        _EXEC_RULE,
        193,
        5,
        193,
        83,
        "1dccd9aaa511115af8daeb45c3e8fd2fb3efbb8a13ae2d532846bc4c69de89a4",
        _DUPLICATE_DEFINITIONS_FILE_SHA,
    ),
    *(
        FindingSignature(
            "tests/unit/test_duplicate_definitions_220.py",
            _EXEC_RULE,
            line,
            5,
            line,
            62,
            "06bcfb77f28dc11c6fe59297f6856a66300b0b1ad39bd1d0709030d79bf8e1af",
            _DUPLICATE_DEFINITIONS_FILE_SHA,
        )
        for line in (277, 304, 314, 332)
    ),
    FindingSignature(
        "tests/unit/test_models.py",
        _PICKLE_RULE,
        52,
        20,
        52,
        52,
        "6a937709b5db729a4b42a4851a22eae5ec266c0d20a976a464e2c05add5783a2",
        _MODELS_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_models.py",
        _PICKLE_RULE,
        52,
        33,
        52,
        51,
        "6a937709b5db729a4b42a4851a22eae5ec266c0d20a976a464e2c05add5783a2",
        _MODELS_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_models.py",
        _PICKLE_RULE,
        70,
        20,
        70,
        53,
        "b9531179ddec5d36108a0b76b13811e43929d7302780880bdd417e44ff25a989",
        _MODELS_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_models.py",
        _PICKLE_RULE,
        70,
        33,
        70,
        52,
        "b9531179ddec5d36108a0b76b13811e43929d7302780880bdd417e44ff25a989",
        _MODELS_FILE_SHA,
    ),
    # ``expected`` is assembled from a literal source fixture immediately
    # above; executing it proves that apply preserved callable semantics.
    FindingSignature(
        "tests/unit/test_mutant_diff.py",
        _EXEC_RULE,
        581,
        9,
        583,
        10,
        "23d8ffb9e2cacc9b6edf4c0e7b02146b23771c7496f4e70ebf68d0964c05c0b9",
        _MUTANT_DIFF_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_mutation_adversarial_a5.py",
        _EXEC_RULE,
        28,
        9,
        30,
        10,
        "5897addaccc52f279bb3b7cf7fcdf624fdfce0be682c3fbf6877ea8e87d7c937",
        _MUTATION_ADVERSARIAL_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_mutation_hardening_round2.py",
        _EXEC_RULE,
        24,
        9,
        26,
        10,
        "c54d2d1f16e578eddbbb1066e364300b01e75e272915d3bb57eba022cd4fc58c",
        _MUTATION_HARDENING_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_sitecustomize_116.py",
        _EXEC_RULE,
        129,
        9,
        129,
        53,
        "ba4c905438034879a6644793f66ac51adcb4a57d38ff6cdbc25e616b32d92d54",
        _SITECUSTOMIZE_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_sitecustomize_116.py",
        _EXEC_RULE,
        139,
        9,
        139,
        53,
        "ba4c905438034879a6644793f66ac51adcb4a57d38ff6cdbc25e616b32d92d54",
        _SITECUSTOMIZE_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_staticmethod_mutation.py",
        _EXEC_RULE,
        22,
        5,
        22,
        26,
        "3acad4d2c553a254e64bd6d227214c405e05a9ff7138001ccf6ca734b279e1fc",
        _STATICMETHOD_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_wrapper_codegen.py",
        _EXEC_RULE,
        30,
        9,
        30,
        52,
        "25c3ef5ae09a655446756e71bc8771a63e517836bcf7c3a247d64597cd82d64a",
        _WRAPPER_CODEGEN_FILE_SHA,
    ),
    FindingSignature(
        "tests/unit/test_wrapper_codegen.py",
        _EXEC_RULE,
        50,
        9,
        50,
        42,
        "5645ddad68cc2f6be58271d12732f06c354fcc0e5df1e796ef3f18e847d3897c",
        _WRAPPER_CODEGEN_FILE_SHA,
    ),
)


@dataclass(frozen=True)
class _FileRecord:
    relative_path: str
    size: int
    sha256: str
    source_identity: tuple[int, ...]
    mirror_identity: tuple[int, ...]


@dataclass(frozen=True)
class _ArtifactRecord:
    relative_path: str
    size: int
    sha256: str
    identity: tuple[int, ...]


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sequence_digest(values: Sequence[str]) -> str:
    return _sha256_bytes("\n".join(values).encode("utf-8"))


def _default_runner(
    command: Command, cwd: Path, environment: Environment
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(  # noqa: S603 - executable is resolved and argv is never shelled
            command,
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            shell=False,
            timeout=1_800,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError(
            "command-execution", f"Could not execute release-gate command: {exc}"
        ) from exc


def _completed_bytes(
    result: subprocess.CompletedProcess[bytes], *, command_name: str
) -> tuple[bytes, bytes]:
    if not isinstance(result.stdout, bytes) or not isinstance(result.stderr, bytes):
        raise GateError("runner-contract", f"{command_name} runner output must be bytes")
    return result.stdout, result.stderr


def _run_checked(
    runner: Runner,
    command: Command,
    cwd: Path,
    environment: Environment,
    *,
    command_name: str,
) -> bytes:
    result = runner(command, cwd, environment)
    stdout, stderr = _completed_bytes(result, command_name=command_name)
    if result.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        detail = detail.splitlines()[0][:300] if detail else "no diagnostic"
        raise GateError(
            f"{command_name}-failed",
            f"{command_name} exited with {result.returncode}: {detail}",
        )
    return stdout


def _find_executable(name: str, finder: ExecutableFinder) -> str:
    executable = finder(name)
    if not executable:
        raise GateError("missing-executable", f"Required executable is unavailable: {name}")
    executable_path = Path(executable)
    if not executable_path.is_absolute():
        raise GateError("unsafe-executable", f"Executable path is not absolute: {name}")
    executable_stat = _lstat(executable_path, label=f"{name} executable")
    if not stat.S_ISREG(executable_stat.st_mode):
        raise GateError("unsafe-executable", f"Executable is not a regular file: {name}")
    return str(executable_path)


def _bind_semgrep_to_project_environment(
    executable: str,
    repository: Path,
    python_prefix: Path,
    python_base_prefix: Path,
    declared_project_environment: str | None,
) -> None:
    prefix = python_prefix.absolute()
    base_prefix = python_base_prefix.absolute()
    if os.path.normcase(str(prefix)) == os.path.normcase(str(base_prefix)):
        raise GateError("unsafe-executable", "Semgrep gate requires an active virtual environment")
    if not declared_project_environment:
        raise GateError(
            "unsafe-executable",
            "UV_PROJECT_ENVIRONMENT must name the active external release environment",
        )
    expected_prefix = Path(declared_project_environment)
    if not expected_prefix.is_absolute():
        raise GateError("unsafe-executable", "UV_PROJECT_ENVIRONMENT must be absolute")
    expected_prefix = expected_prefix.absolute()
    _validate_repository_directory(prefix)
    _validate_repository_directory(expected_prefix)
    pyvenv_stat = _lstat(expected_prefix / "pyvenv.cfg", label="external project pyvenv.cfg")
    if not stat.S_ISREG(pyvenv_stat.st_mode):
        raise GateError("unsafe-executable", "External project pyvenv.cfg is not a regular file")
    executable_path = Path(executable).absolute()
    try:
        resolved_prefix = prefix.resolve(strict=True)
        resolved_expected_prefix = expected_prefix.resolve(strict=True)
        resolved_repository = repository.resolve(strict=True)
        resolved_executable = executable_path.resolve(strict=True)
    except OSError as exc:
        raise GateError("unsafe-executable", f"Cannot resolve Python tool boundary: {exc}") from exc
    if os.path.normcase(str(resolved_prefix)) != os.path.normcase(str(resolved_expected_prefix)):
        raise GateError(
            "unsafe-executable",
            "Active Python environment does not match UV_PROJECT_ENVIRONMENT",
        )
    if _is_within(resolved_expected_prefix, resolved_repository) or _is_within(
        resolved_repository, resolved_expected_prefix
    ):
        raise GateError(
            "unsafe-executable",
            "UV_PROJECT_ENVIRONMENT and the release checkout must be disjoint",
        )
    scripts_directory = prefix / ("Scripts" if os.name == "nt" else "bin")
    scripts_stat = _lstat(scripts_directory, label="external virtualenv scripts directory")
    if not stat.S_ISDIR(scripts_stat.st_mode):
        raise GateError("unsafe-executable", "Virtualenv scripts path is not a directory")
    try:
        resolved_scripts = scripts_directory.resolve(strict=True)
    except OSError as exc:
        raise GateError("unsafe-executable", f"Cannot resolve scripts directory: {exc}") from exc
    if resolved_executable.parent != resolved_scripts:
        raise GateError(
            "unsafe-executable",
            "Semgrep executable is not in the project virtualenv scripts directory",
        )


def _has_reparse_attribute(file_stat: os.stat_result) -> bool:
    attributes = int(getattr(file_stat, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & reparse_flag)


def _identity(file_stat: os.stat_result) -> tuple[int, ...]:
    return (
        int(file_stat.st_dev),
        int(file_stat.st_ino),
        int(file_stat.st_mode),
        int(file_stat.st_nlink),
        int(file_stat.st_size),
        int(file_stat.st_mtime_ns),
        # Windows' CRT reports creation time for path stat but mirrors mtime for
        # fstat, so ctime cannot participate in the path/handle identity proof.
        int(getattr(file_stat, "st_file_attributes", 0)),
    )


def _handle_identity(file_stat: os.stat_result) -> tuple[int, ...]:
    """Identity fields that Windows reports consistently for lstat and fstat."""

    return (
        int(file_stat.st_dev),
        int(file_stat.st_ino),
        int(stat.S_IFMT(file_stat.st_mode)),
        int(file_stat.st_nlink),
        int(file_stat.st_size),
        int(file_stat.st_mtime_ns),
        int(getattr(file_stat, "st_file_attributes", 0)),
    )


def _directory_identity(file_stat: os.stat_result) -> tuple[int, ...]:
    return (
        int(file_stat.st_dev),
        int(file_stat.st_ino),
        int(file_stat.st_mode),
        int(getattr(file_stat, "st_file_attributes", 0)),
    )


def _lstat(path: Path, *, label: str) -> os.stat_result:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise GateError("unsafe-filesystem", f"Cannot inspect {label}: {exc}") from exc
    if stat.S_ISLNK(file_stat.st_mode) or _has_reparse_attribute(file_stat):
        raise GateError("link-or-reparse", f"Link or reparse point rejected: {label}")
    return file_stat


def _validate_repository_directory(repository: Path) -> None:
    file_stat = _lstat(repository, label="repository root")
    if not stat.S_ISDIR(file_stat.st_mode):
        raise GateError("unsafe-repository", "Repository root is not a directory")


def _canonical_inventory_path(raw_path: str) -> str:
    if not raw_path or "\x00" in raw_path or "\\" in raw_path:
        raise GateError("unsafe-path", f"Invalid Git-owned path: {raw_path!r}")
    posix_path = PurePosixPath(raw_path)
    windows_path = PureWindowsPath(raw_path)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise GateError("unsafe-path", f"Absolute or drive-qualified path rejected: {raw_path!r}")
    parts = posix_path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise GateError("unsafe-path", f"Traversal or empty component rejected: {raw_path!r}")
    if any(part.rstrip(" .") != part or ":" in part for part in parts):
        raise GateError("unsafe-path", f"Platform-ambiguous path rejected: {raw_path!r}")
    canonical = posix_path.as_posix()
    if canonical != raw_path:
        raise GateError("unsafe-path", f"Non-canonical Git-owned path rejected: {raw_path!r}")
    if canonical != SEMGREP_IGNORE_FILE and parts[0] not in SCAN_ROOTS:
        raise GateError("out-of-scope-path", f"Git returned an out-of-scope path: {canonical}")
    return canonical


def _collision_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _validate_inventory(raw_paths: Sequence[str]) -> tuple[str, ...]:
    canonical_paths: list[str] = []
    exact_paths: set[str] = set()
    collision_keys: dict[str, str] = {}
    for raw_path in raw_paths:
        canonical = _canonical_inventory_path(raw_path)
        if canonical in exact_paths:
            raise GateError("duplicate-path", f"Duplicate Git-owned path: {canonical}")
        key = _collision_key(canonical)
        previous = collision_keys.get(key)
        if previous is not None:
            raise GateError(
                "case-collision",
                f"Case or Unicode-normalization collision: {previous!r} and {canonical!r}",
            )
        exact_paths.add(canonical)
        collision_keys[key] = canonical
        canonical_paths.append(canonical)
    canonical_paths.sort()
    if SEMGREP_IGNORE_FILE not in exact_paths:
        raise GateError("missing-semgrepignore", f"{SEMGREP_IGNORE_FILE} is not Git-owned")
    return tuple(canonical_paths)


def _decode_nul_paths(output: bytes) -> tuple[str, ...]:
    if output and not output.endswith(b"\x00"):
        raise GateError("git-output", "NUL-delimited Git inventory lacks a final delimiter")
    try:
        decoded = output.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GateError("git-output", "Git inventory is not strict UTF-8") from exc
    raw_paths = decoded[:-1].split("\x00") if decoded else []
    return _validate_inventory(raw_paths)


def _inventory_command(git: str, repository: Path) -> Command:
    return (
        git,
        "-C",
        str(repository),
        "ls-files",
        "-z",
        "--cached",
        "--others",
        # Use only versioned per-directory ignore files.  ``--exclude-standard``
        # would additionally trust ambient global excludes and .git/info/exclude,
        # either of which can silently hide an untracked release-gate input.
        "--exclude-per-directory=.gitignore",
        "--",
        *SCAN_ROOTS,
        SEMGREP_IGNORE_FILE,
    )


def _unmerged_command(git: str, repository: Path) -> Command:
    return (
        git,
        "-C",
        str(repository),
        "ls-files",
        "-z",
        "--unmerged",
        "--",
        *SCAN_ROOTS,
        SEMGREP_IGNORE_FILE,
    )


def _read_inventory(
    git: str,
    repository: Path,
    runner: Runner,
    environment: Environment,
) -> tuple[str, ...]:
    unmerged = _run_checked(
        runner,
        _unmerged_command(git, repository),
        repository,
        environment,
        command_name="git-unmerged",
    )
    if unmerged:
        raise GateError("unmerged-files", "Release-gate scope contains unmerged index entries")
    output = _run_checked(
        runner,
        _inventory_command(git, repository),
        repository,
        environment,
        command_name="git-inventory",
    )
    return _decode_nul_paths(output)


def _assert_relative_file_ancestors(root: Path, relative_path: str) -> None:
    current = root
    parts = PurePosixPath(relative_path).parts
    for part in parts[:-1]:
        current /= part
        file_stat = _lstat(current, label=f"directory {relative_path}")
        if not stat.S_ISDIR(file_stat.st_mode):
            raise GateError(
                "unsafe-filesystem", f"Non-directory ancestor rejected: {relative_path}"
            )


def _collect_directory_identities(
    root: Path, inventory: Sequence[str]
) -> dict[str, tuple[int, ...]]:
    directories = {"."}
    for relative_path in inventory:
        parent = PurePosixPath(relative_path).parent
        while parent.as_posix() != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    identities: dict[str, tuple[int, ...]] = {}
    for relative_directory in sorted(directories):
        directory = (
            root if relative_directory == "." else root.joinpath(*relative_directory.split("/"))
        )
        file_stat = _lstat(directory, label=f"directory {relative_directory}")
        if not stat.S_ISDIR(file_stat.st_mode):
            raise GateError("unsafe-filesystem", f"Expected directory: {relative_directory}")
        identities[relative_directory] = _directory_identity(file_stat)
    return identities


def _read_fd_all(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _read_stable_file(root: Path, relative_path: str) -> tuple[bytes, tuple[int, ...]]:
    _assert_relative_file_ancestors(root, relative_path)
    path = root.joinpath(*relative_path.split("/"))
    before = _lstat(path, label=relative_path)
    if not stat.S_ISREG(before.st_mode):
        raise GateError(
            "non-regular-file", f"Git-owned path is not a regular file: {relative_path}"
        )
    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0)) | int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise GateError(
            "unsafe-filesystem", f"Cannot open Git-owned file {relative_path}: {exc}"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if _handle_identity(opened) != _handle_identity(before) or not stat.S_ISREG(opened.st_mode):
            raise GateError("toctou", f"File identity changed while opening: {relative_path}")
        first = _read_fd_all(descriptor)
        after_first = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        second = _read_fd_all(descriptor)
        after_second = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after_path = _lstat(path, label=relative_path)
    expected_identity = _identity(before)
    if not (
        _handle_identity(before)
        == _handle_identity(opened)
        == _handle_identity(after_first)
        == _handle_identity(after_second)
        == _handle_identity(after_path)
    ):
        raise GateError("toctou", f"File metadata changed while reading: {relative_path}")
    if first != second or len(first) != before.st_size:
        raise GateError("toctou", f"File bytes changed while reading: {relative_path}")
    return first, expected_identity


def _write_mirror_file(mirror: Path, relative_path: str, data: bytes) -> tuple[int, ...]:
    destination = mirror.joinpath(*relative_path.split("/"))
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GateError("mirror-write", f"Cannot create mirror directory: {relative_path}") from exc
    _assert_relative_file_ancestors(mirror, relative_path)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | int(getattr(os, "O_BINARY", 0))
        | int(getattr(os, "O_NOFOLLOW", 0))
    )
    try:
        descriptor = os.open(destination, flags, 0o600)
    except OSError as exc:
        raise GateError("mirror-write", f"Cannot create mirror file: {relative_path}") from exc
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise GateError("mirror-write", f"Short write in mirror: {relative_path}")
            view = view[written:]
        file_stat = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    mirrored, identity = _read_stable_file(mirror, relative_path)
    if mirrored != data or identity != _identity(file_stat):
        raise GateError("mirror-mismatch", f"Mirror is not byte-identical: {relative_path}")
    return identity


def _mirror_inventory(root: Path) -> tuple[str, ...]:
    discovered: list[str] = []
    for directory_name, directory_names, file_names in os.walk(root, followlinks=False):
        directory = Path(directory_name)
        relative_directory = directory.relative_to(root)
        directory_stat = _lstat(directory, label="mirror directory")
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise GateError("unsafe-mirror", "Mirror contains a non-directory ancestor")
        for child_name in directory_names:
            child = directory / child_name
            child_stat = _lstat(child, label="mirror directory")
            if not stat.S_ISDIR(child_stat.st_mode):
                raise GateError("unsafe-mirror", "Mirror contains a non-directory child")
        for file_name in file_names:
            relative = (relative_directory / file_name).as_posix()
            canonical = _canonical_inventory_path(relative)
            file_stat = _lstat(directory / file_name, label=canonical)
            if not stat.S_ISREG(file_stat.st_mode):
                raise GateError("unsafe-mirror", f"Mirror entry is not a regular file: {canonical}")
            discovered.append(canonical)
    return _validate_inventory(discovered)


def _copy_to_mirror(
    repository: Path,
    mirror: Path,
    inventory: Sequence[str],
) -> tuple[_FileRecord, ...]:
    records: list[_FileRecord] = []
    for relative_path in inventory:
        data, source_identity = _read_stable_file(repository, relative_path)
        mirror_identity = _write_mirror_file(mirror, relative_path, data)
        records.append(
            _FileRecord(
                relative_path=relative_path,
                size=len(data),
                sha256=_sha256_bytes(data),
                source_identity=source_identity,
                mirror_identity=mirror_identity,
            )
        )
    if _mirror_inventory(mirror) != tuple(inventory):
        raise GateError("mirror-inventory", "Mirror inventory differs from Git-owned inventory")
    return tuple(records)


def _verify_records(
    repository: Path,
    mirror: Path,
    records: Sequence[_FileRecord],
) -> None:
    expected_inventory = tuple(record.relative_path for record in records)
    if _mirror_inventory(mirror) != expected_inventory:
        raise GateError("mirror-inventory", "Mirror inventory changed during the scan")
    for record in records:
        source, source_identity = _read_stable_file(repository, record.relative_path)
        mirrored, mirror_identity = _read_stable_file(mirror, record.relative_path)
        if source_identity != record.source_identity:
            raise GateError("toctou", f"Source identity changed: {record.relative_path}")
        if mirror_identity != record.mirror_identity:
            raise GateError("toctou", f"Mirror identity changed: {record.relative_path}")
        if (
            len(source) != record.size
            or _sha256_bytes(source) != record.sha256
            or source != mirrored
        ):
            raise GateError("toctou", f"Source or mirror bytes changed: {record.relative_path}")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _assert_safe_cleanup_tree(root: Path, root_identity: tuple[int, ...]) -> None:
    root_stat = _lstat(root, label="temporary mirror cleanup root")
    if not stat.S_ISDIR(root_stat.st_mode) or _directory_identity(root_stat) != root_identity:
        raise GateError("unsafe-mirror-cleanup", "Temporary mirror root identity changed")
    for directory_name, directory_names, file_names in os.walk(root, followlinks=False):
        directory = Path(directory_name)
        directory_stat = _lstat(directory, label="temporary mirror cleanup directory")
        if not stat.S_ISDIR(directory_stat.st_mode):
            raise GateError("unsafe-mirror-cleanup", "Unsafe directory in temporary mirror")
        for child_name in directory_names:
            child_stat = _lstat(directory / child_name, label="temporary mirror cleanup directory")
            if not stat.S_ISDIR(child_stat.st_mode):
                raise GateError("unsafe-mirror-cleanup", "Unsafe child directory in mirror")
        for file_name in file_names:
            file_stat = _lstat(directory / file_name, label="temporary mirror cleanup file")
            if not stat.S_ISREG(file_stat.st_mode):
                raise GateError("unsafe-mirror-cleanup", "Unsafe file in temporary mirror")


@contextmanager
def _temporary_external_mirror(repository: Path) -> Iterator[Path]:
    mirror = Path(tempfile.mkdtemp(prefix="mutmut-win-semgrep-release-")).absolute()
    mirror_identity: tuple[int, ...] | None = None
    try:
        try:
            resolved_mirror = mirror.resolve(strict=True)
            resolved_repository = repository.resolve(strict=True)
        except OSError as exc:
            raise GateError("unsafe-mirror", f"Cannot resolve temporary mirror: {exc}") from exc
        if (
            _is_within(mirror, repository)
            or _is_within(repository, mirror)
            or _is_within(resolved_mirror, resolved_repository)
            or _is_within(resolved_repository, resolved_mirror)
        ):
            raise GateError(
                "non-external-mirror", "Temporary mirror is not external to the repository"
            )
        mirror_stat = _lstat(mirror, label="temporary mirror")
        if not stat.S_ISDIR(mirror_stat.st_mode):
            raise GateError("unsafe-mirror", "Temporary mirror is not a directory")
        mirror_identity = _directory_identity(mirror_stat)
        yield mirror
    finally:
        if os.path.lexists(mirror):
            if mirror_identity is None:
                # The directory was created by mkdtemp but rejected before an
                # identity could be frozen.  A regular, non-reparse directory is
                # still required before recursive cleanup.
                rejected_stat = _lstat(mirror, label="rejected temporary mirror")
                if not stat.S_ISDIR(rejected_stat.st_mode):
                    raise GateError("unsafe-mirror-cleanup", "Rejected mirror is unsafe")
                mirror_identity = _directory_identity(rejected_stat)
            _assert_safe_cleanup_tree(mirror, mirror_identity)
            try:
                shutil.rmtree(mirror)
            except OSError as exc:
                raise GateError(
                    "mirror-cleanup", f"Could not remove temporary mirror: {exc}"
                ) from exc


_OFFLINE_ENDPOINT: Final = "http://127.0.0.1:9"

# The rule bootstrap is the sole network-enabled subprocess in the gate.  Do
# not give that third-party process the caller's arbitrary environment: a
# denylist can never anticipate every credential spelling (GITHUB_TOKEN,
# AWS_SECRET_ACCESS_KEY, DATABASE_URL, ...).  Proxy values are an explicit
# exception because they may be required to reach the registry; callers must
# treat credentials embedded in those URLs as intentionally delegated to the
# bootstrap.  Certificate paths and basic OS/locale values carry no ambient
# account authority.
_REMOTE_PARENT_ENV_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "ALL_PROXY",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "NO_PROXY",
        "PATHEXT",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TZ",
        "WINDIR",
    }
)


def _remote_environment(
    parent: Environment,
    xdg_config_home: Path,
    *,
    semgrep_directory: Path,
) -> dict[str, str]:
    """Return a credential-minimal environment for registry bootstrap."""

    isolation_root = xdg_config_home.parent
    # Canonicalise allowed names so a case-variant mapping cannot create two
    # Windows environment entries with conflicting values.
    environment = {
        key.upper(): value
        for key, value in parent.items()
        if key.upper() in _REMOTE_PARENT_ENV_ALLOWLIST
    }
    environment.update(
        {
            "APPDATA": str(isolation_root / "appdata"),
            "HOME": str(isolation_root / "home"),
            "LOCALAPPDATA": str(isolation_root / "localappdata"),
            # The Semgrep console script and its packaged engine are both
            # resolved before this point.  A caller-controlled PATH would let
            # an unrelated executable participate in the security gate.
            "PATH": str(semgrep_directory),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
            "SEMGREP_SETTINGS_FILE": str(xdg_config_home / ".semgrep" / "settings.yml"),
            "TEMP": str(isolation_root / "temp"),
            "TMP": str(isolation_root / "temp"),
            "TMPDIR": str(isolation_root / "temp"),
            "USERPROFILE": str(isolation_root / "home"),
            "XDG_CACHE_HOME": str(isolation_root / "cache"),
            "XDG_CONFIG_HOME": str(xdg_config_home),
            "XDG_DATA_HOME": str(isolation_root / "data"),
            "XDG_STATE_HOME": str(isolation_root / "state"),
        }
    )
    return environment


def _offline_environment(remote_environment: Environment) -> dict[str, str]:
    environment = dict(remote_environment)
    environment.update(
        {
            "ALL_PROXY": _OFFLINE_ENDPOINT,
            "HTTP_PROXY": _OFFLINE_ENDPOINT,
            "HTTPS_PROXY": _OFFLINE_ENDPOINT,
            "NO_PROXY": "",
            "SEMGREP_APP_URL": _OFFLINE_ENDPOINT,
            "SEMGREP_FAIL_OPEN_URL": _OFFLINE_ENDPOINT,
            "SEMGREP_SEND_METRICS": "off",
            "SEMGREP_URL": _OFFLINE_ENDPOINT,
            "SEMGREP_VERSION_CHECK_URL": _OFFLINE_ENDPOINT,
            "UV_OFFLINE": "1",
            "all_proxy": _OFFLINE_ENDPOINT,
            "http_proxy": _OFFLINE_ENDPOINT,
            "https_proxy": _OFFLINE_ENDPOINT,
            "no_proxy": "",
        }
    )
    return environment


def _semgrep_dump_command(semgrep: str) -> Command:
    return (
        semgrep,
        "scan",
        "--oss-only",
        "--jobs",
        SEMGREP_BOOTSTRAP_JOBS,
        "--config",
        "auto",
        "--error",
        "--timeout",
        "120",
        "--time",
        "--json",
        "--disable-version-check",
        "--disable-nosem",
        "--exclude",
        SEMGREP_IGNORE_FILE,
        "--dump-command-for-core",
        ".",
    )


def _semgrep_bundle_command(semgrep: str, bundle: Path) -> Command:
    return (
        semgrep,
        "scan",
        "--oss-only",
        "--jobs",
        SEMGREP_SCAN_JOBS,
        "--config",
        str(bundle),
        "--no-rewrite-rule-ids",
        "--error",
        "--timeout",
        "120",
        "--time",
        "--json",
        "--disable-version-check",
        "--disable-nosem",
        "--metrics",
        "off",
        "--exclude",
        SEMGREP_IGNORE_FILE,
        ".",
    )


def _require_exact_empty_list(payload: dict[str, Any], field: str) -> None:
    value = payload.get(field)
    if not isinstance(value, list) or value:
        raise GateError("semgrep-json", f"Semgrep field {field!r} must be an empty list")


def _canonical_reported_path(raw_path: object, *, field: str) -> str:
    if not isinstance(raw_path, str):
        raise GateError("semgrep-json", f"Semgrep {field} path must be a string")
    normalized = raw_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return _canonical_inventory_path(normalized)


def _validate_reported_paths(raw_paths: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(raw_paths, list):
        raise GateError("semgrep-json", f"Semgrep {field} must be a list")
    paths = [_canonical_reported_path(path, field=field) for path in raw_paths]
    return _validate_inventory_with_no_required_ignore(paths, field=field)


def _validate_inventory_with_no_required_ignore(
    paths: Sequence[str], *, field: str
) -> tuple[str, ...]:
    exact: set[str] = set()
    collisions: dict[str, str] = {}
    for path in paths:
        if path in exact:
            raise GateError("semgrep-json", f"Duplicate path in Semgrep {field}: {path}")
        key = _collision_key(path)
        previous = collisions.get(key)
        if previous is not None:
            raise GateError(
                "semgrep-json",
                f"Case-colliding paths in Semgrep {field}: {previous!r}, {path!r}",
            )
        exact.add(path)
        collisions[key] = path
    return tuple(sorted(exact))


def _validate_optional_skips(paths_payload: dict[str, Any]) -> None:
    if "skipped" not in paths_payload:
        return
    skipped = paths_payload["skipped"]
    if not isinstance(skipped, list):
        raise GateError("semgrep-json", "Semgrep paths.skipped must be a list when present")
    for entry in skipped:
        if not isinstance(entry, dict) or "path" not in entry:
            raise GateError("semgrep-json", "Malformed Semgrep paths.skipped entry")
        path = _canonical_reported_path(entry["path"], field="paths.skipped")
        if path != SEMGREP_IGNORE_FILE and not _is_policy_skip(path):
            raise GateError("unexpected-policy-skip", f"Unexpected Semgrep skip: {path}")


def _is_policy_skip(path: str) -> bool:
    return any(
        path == prefix.rstrip("/") or path.startswith(prefix) for prefix in POLICY_SKIP_PREFIXES
    )


def _git_environment(parent: Environment) -> dict[str, str]:
    """Return a Git environment isolated from user/system config and excludes."""

    blocked_names = {
        "APPDATA",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "USERPROFILE",
        "XDG_CONFIG_HOME",
    }
    environment = {
        key: value
        for key, value in parent.items()
        if key.upper() not in blocked_names
        and not key.upper().startswith(("GIT_", "SEMGREP_", "UV_"))
    }
    # ``os.devnull`` is a real non-config sink on Windows (``nul``) and POSIX.
    # Explicit overrides also make the boundary independent of Git's fallback
    # rules for HOME, XDG_CONFIG_HOME, and the system config location.
    environment.update(
        {
            "APPDATA": os.devnull,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "HOME": os.devnull,
            "LOCALAPPDATA": os.devnull,
            "USERPROFILE": os.devnull,
            "XDG_CONFIG_HOME": os.devnull,
        }
    )
    return environment


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GateError("semgrep-json", f"Duplicate JSON key rejected: {key}")
        value[key] = item
    return value


def _reject_json_constant(constant: str) -> None:
    raise GateError("semgrep-json", f"Non-finite JSON constant rejected: {constant}")


def _load_strict_json(data: bytes, *, label: str) -> Any:
    try:
        text = data.decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_strict_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError("semgrep-json", f"{label} is not strict UTF-8 JSON") from exc


def _read_artifact(root: Path, relative_path: str) -> tuple[bytes, _ArtifactRecord]:
    data, identity = _read_stable_file(root, relative_path)
    return data, _ArtifactRecord(
        relative_path=relative_path,
        size=len(data),
        sha256=_sha256_bytes(data),
        identity=identity,
    )


def _verify_artifacts(root: Path, records: Sequence[_ArtifactRecord]) -> None:
    for record in records:
        data, identity = _read_stable_file(root, record.relative_path)
        if (
            identity != record.identity
            or len(data) != record.size
            or _sha256_bytes(data) != record.sha256
        ):
            raise GateError("toctou", f"Rule artifact changed: {record.relative_path}")


def _snapshot_absolute_artifact(path: Path) -> tuple[Path, _ArtifactRecord]:
    parent = path.parent
    _validate_repository_directory(parent)
    data, identity = _read_stable_file(parent, path.name)
    return parent, _ArtifactRecord(
        relative_path=path.name,
        size=len(data),
        sha256=_sha256_bytes(data),
        identity=identity,
    )


def _load_rule_bundle(
    control_root: Path,
    xdg_config_home: Path,
    bundle_contract: BundleContract,
) -> tuple[Path, bytes, tuple[_ArtifactRecord, ...]]:
    rules_directory = xdg_config_home / ".semgrep"
    rules_directory_stat = _lstat(rules_directory, label="Semgrep rules directory")
    if not stat.S_ISDIR(rules_directory_stat.st_mode):
        raise GateError("semgrep-shards", "Semgrep rules path is not a directory")
    expected_names = {f"semgrep_rules_{shard.index}.json" for shard in bundle_contract.shards}
    try:
        present_names = {
            child.name
            for child in rules_directory.iterdir()
            if child.name.startswith("semgrep_rules_")
        }
    except OSError as exc:
        raise GateError("semgrep-shards", f"Cannot inventory Semgrep rule shards: {exc}") from exc
    if present_names != expected_names:
        raise GateError(
            "semgrep-shards",
            f"Expected rule shards {sorted(expected_names)!r}, got {sorted(present_names)!r}",
        )

    rules: list[tuple[str, str, dict[str, Any]]] = []
    records: list[_ArtifactRecord] = []
    seen_ids: set[str] = set()
    for shard in sorted(bundle_contract.shards, key=lambda item: item.index):
        relative_path = f"xdg/.semgrep/semgrep_rules_{shard.index}.json"
        raw_shard, record = _read_artifact(control_root, relative_path)
        records.append(record)
        if len(raw_shard) != shard.size:
            raise GateError(
                "semgrep-shards",
                f"Rule shard {shard.index} size drift: {len(raw_shard)} != {shard.size}",
            )
        payload = _load_strict_json(raw_shard, label=f"Semgrep rule shard {shard.index}")
        if not isinstance(payload, dict) or set(payload) != {"rules"}:
            raise GateError(
                "semgrep-shards", f"Rule shard {shard.index} must contain only a rules list"
            )
        shard_rules = payload["rules"]
        if not isinstance(shard_rules, list) or len(shard_rules) != shard.definition_count:
            raise GateError(
                "semgrep-shards",
                f"Rule shard {shard.index} definition-count drift",
            )
        for rule in shard_rules:
            if not isinstance(rule, dict):
                raise GateError("semgrep-shards", "Every rule definition must be an object")
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_id:
                raise GateError("semgrep-shards", "Every rule definition needs a non-empty id")
            if rule_id in seen_ids:
                raise GateError("semgrep-shards", f"Duplicate rule definition ID: {rule_id}")
            seen_ids.add(rule_id)
            canonical_rule = _canonical_json(rule)
            rules.append((rule_id, canonical_rule, rule))

    rules.sort(key=lambda item: (item[0], item[1]))
    canonical_rules = tuple(item[1] for item in rules)
    if len(rules) != bundle_contract.definition_count:
        raise GateError("semgrep-bundle", "Rule definition-count drift")
    if _sequence_digest(canonical_rules) != bundle_contract.definitions_sha256:
        raise GateError("semgrep-bundle", "Canonical rule-definition content drift")
    bundle_bytes = _canonical_json({"rules": [item[2] for item in rules]}).encode("utf-8")
    if len(bundle_bytes) != bundle_contract.bundle_size:
        raise GateError("semgrep-bundle", "Canonical rule-bundle size drift")
    if _sha256_bytes(bundle_bytes) != bundle_contract.bundle_sha256:
        raise GateError("semgrep-bundle", "Canonical rule-bundle digest drift")

    bundle_relative_path = "community-rules.bundle.json"
    bundle_identity = _write_mirror_file(control_root, bundle_relative_path, bundle_bytes)
    bundle_record = _ArtifactRecord(
        relative_path=bundle_relative_path,
        size=len(bundle_bytes),
        sha256=_sha256_bytes(bundle_bytes),
        identity=bundle_identity,
    )
    records.append(bundle_record)
    return control_root / bundle_relative_path, bundle_bytes, tuple(records)


def _positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise GateError("semgrep-json", f"Semgrep {field} must be a positive integer")
    return value


def _finding_signature(result: object, mirror: Path) -> FindingSignature:
    if not isinstance(result, dict):
        raise GateError("semgrep-json", "Every Semgrep result must be an object")
    path = _canonical_reported_path(result.get("path"), field="result")
    check_id = result.get("check_id")
    if not isinstance(check_id, str) or not check_id:
        raise GateError("semgrep-json", "Every Semgrep result needs a non-empty check_id")
    start = result.get("start")
    end = result.get("end")
    extra = result.get("extra")
    if not isinstance(start, dict) or not isinstance(end, dict) or not isinstance(extra, dict):
        raise GateError("semgrep-json", "Semgrep result start/end/extra must be objects")
    start_line = _positive_int(start.get("line"), field="result.start.line")
    start_col = _positive_int(start.get("col"), field="result.start.col")
    end_line = _positive_int(end.get("line"), field="result.end.line")
    end_col = _positive_int(end.get("col"), field="result.end.col")
    if "is_ignored" in extra:
        raise GateError(
            "semgrep-findings",
            "Semgrep 1.175.0 --disable-nosem results must omit extra.is_ignored",
        )
    source_bytes, _identity_value = _read_stable_file(mirror, path)
    try:
        source_text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GateError("semgrep-findings", f"Finding source is not strict UTF-8: {path}") from exc
    normalized_source = source_text.replace("\r\n", "\n").replace("\r", "\n")
    source_lines = normalized_source.split("\n")
    if source_lines and source_lines[-1] == "":
        source_lines.pop()
    if not (1 <= start_line <= end_line <= len(source_lines)):
        raise GateError("semgrep-findings", f"Finding line range is outside source: {path}")
    if start_col > len(source_lines[start_line - 1]) + 1:
        raise GateError("semgrep-findings", f"Finding start column is outside source: {path}")
    if end_col > len(source_lines[end_line - 1]) + 1:
        raise GateError("semgrep-findings", f"Finding end column is outside source: {path}")
    if start_line == end_line and start_col > end_col:
        raise GateError("semgrep-findings", f"Finding columns are reversed: {path}")
    involved_lines = "\n".join(source_lines[start_line - 1 : end_line])
    return FindingSignature(
        path=path,
        check_id=check_id,
        start_line=start_line,
        start_col=start_col,
        end_line=end_line,
        end_col=end_col,
        lines_sha256=_sha256_bytes(involved_lines.encode("utf-8")),
        file_sha256=_sha256_bytes("\n".join(source_lines).encode("utf-8")),
    )


def _parse_semgrep_json(
    stdout: bytes,
    expected_targets: Sequence[str],
    rule_contract: RuleContract,
    mirror: Path,
    finding_allowlist: Sequence[FindingSignature],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[FindingSignature, ...]]:
    payload = _load_strict_json(stdout, label="Semgrep stdout")
    if not isinstance(payload, dict):
        raise GateError("semgrep-json", "Semgrep JSON root must be an object")
    if payload.get("version") != SEMGREP_VERSION:
        raise GateError("semgrep-version", f"Expected Semgrep {SEMGREP_VERSION}")
    if payload.get("engine_requested") != SEMGREP_ENGINE:
        raise GateError("semgrep-engine", f"Expected Semgrep engine {SEMGREP_ENGINE}")
    for field in ("errors", "skipped_rules"):
        _require_exact_empty_list(payload, field)
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise GateError("semgrep-json", "Semgrep results must be a list")

    time_payload = payload.get("time")
    if not isinstance(time_payload, dict):
        raise GateError("semgrep-json", "Semgrep time must be an object")
    fixpoint_timeouts = time_payload.get("fixpoint_timeouts")
    if not isinstance(fixpoint_timeouts, list) or fixpoint_timeouts:
        observed = _canonical_json(fixpoint_timeouts)[:500]
        raise GateError(
            "semgrep-json",
            f"Semgrep time.fixpoint_timeouts must be an empty list; observed={observed}",
        )
    raw_rules = time_payload.get("rules")
    if not isinstance(raw_rules, list):
        raise GateError("semgrep-json", "Semgrep time.rules must be a list")
    rule_ids: list[str] = []
    for rule_id in raw_rules:
        if not isinstance(rule_id, str) or not rule_id:
            raise GateError("semgrep-json", "Every Semgrep time.rules entry must be a non-empty ID")
        rule_ids.append(rule_id)
    unique_rule_ids = tuple(sorted(set(rule_ids)))
    if len(unique_rule_ids) != len(rule_ids):
        raise GateError("semgrep-rules", "Semgrep time.rules contains duplicate rule IDs")
    if len(unique_rule_ids) != rule_contract.count:
        raise GateError(
            "semgrep-rules",
            f"Expected {rule_contract.count} unique Semgrep rules, got {len(unique_rule_ids)}",
        )
    if _sequence_digest(unique_rule_ids) != rule_contract.ids_sha256:
        raise GateError("semgrep-rules", "Semgrep rule-ID digest differs from the pinned contract")

    paths_payload = payload.get("paths")
    if not isinstance(paths_payload, dict):
        raise GateError("semgrep-json", "Semgrep paths must be an object")
    scanned = _validate_reported_paths(paths_payload.get("scanned"), field="paths.scanned")
    expected = tuple(sorted(expected_targets))
    if scanned != expected:
        missing = sorted(set(expected) - set(scanned))
        extra = sorted(set(scanned) - set(expected))
        raise GateError(
            "semgrep-targets",
            f"Semgrep target mismatch; missing={missing[:5]!r}, extra={extra[:5]!r}",
        )
    _validate_optional_skips(paths_payload)
    findings = tuple(sorted(_finding_signature(result, mirror) for result in raw_results))
    expected_findings = tuple(sorted(finding_allowlist))
    if Counter(findings) != Counter(expected_findings):
        finding_missing = list((Counter(expected_findings) - Counter(findings)).elements())
        finding_extra = list((Counter(findings) - Counter(expected_findings)).elements())
        raise GateError(
            "semgrep-findings",
            f"Adjudicated finding mismatch; "
            f"missing={finding_missing[:2]!r}, extra={finding_extra[:2]!r}",
        )
    return scanned, unique_rule_ids, findings


def _manifest_digest(records: Sequence[_FileRecord]) -> str:
    manifest = [
        {"path": record.relative_path, "sha256": record.sha256, "size": record.size}
        for record in records
    ]
    return _sha256_bytes(_canonical_json(manifest).encode("utf-8"))


def _success_evidence(
    records: Sequence[_FileRecord],
    targets: Sequence[str],
    policy_skips: Sequence[str],
    rule_ids: Sequence[str],
    findings: Sequence[FindingSignature],
    bundle_contract: BundleContract,
) -> dict[str, object]:
    finding_values = [
        {
            "check_id": finding.check_id,
            "end": [finding.end_line, finding.end_col],
            "file_sha256": finding.file_sha256,
            "lines_sha256": finding.lines_sha256,
            "path": finding.path,
            "start": [finding.start_line, finding.start_col],
        }
        for finding in sorted(findings)
    ]
    return {
        "gate": "semgrep-release",
        "manifest": {
            "file_count": len(records),
            "sha256": _manifest_digest(records),
        },
        "policy": {
            "skip_count": len(policy_skips),
            "skips": list(policy_skips),
        },
        "scanner": {
            "bootstrap_command": list(_semgrep_dump_command("semgrep")),
            "bundle": {
                "bytes": bundle_contract.bundle_size,
                "definition_count": bundle_contract.definition_count,
                "definitions_sha256": bundle_contract.definitions_sha256,
                "sha256": bundle_contract.bundle_sha256,
                "shard_count": len(bundle_contract.shards),
            },
            "command": list(
                _semgrep_bundle_command("semgrep", Path("<external-community-rules.bundle.json>"))
            ),
            "allowed_finding_count": len(findings),
            "engine": SEMGREP_ENGINE,
            "error_count": 0,
            "finding_count": len(findings),
            "finding_signatures_sha256": _sha256_bytes(
                _canonical_json(finding_values).encode("utf-8")
            ),
            "fixpoint_timeout_count": 0,
            "inline_suppression_field_contract": "extra.is_ignored absent",
            "inline_suppressions_disabled": True,
            "rule_count": len(rule_ids),
            "rule_ids_sha256": _sequence_digest(rule_ids),
            "skipped_rule_count": 0,
            "unexpected_finding_count": 0,
            "version": SEMGREP_VERSION,
        },
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "status": "pass",
        "targets": {
            "count": len(targets),
            "paths": list(targets),
            "sha256": _sequence_digest(targets),
        },
    }


def run_release_gate(
    repository: Path,
    *,
    runner: Runner = _default_runner,
    executable_finder: ExecutableFinder = shutil.which,
    rule_contract: RuleContract = DEFAULT_RULE_CONTRACT,
    bundle_contract: BundleContract = DEFAULT_BUNDLE_CONTRACT,
    finding_allowlist: Sequence[FindingSignature] = DEFAULT_FINDING_ALLOWLIST,
    environment: Environment | None = None,
    python_prefix: Path | None = None,
    python_base_prefix: Path | None = None,
) -> dict[str, object]:
    """Run the pinned Semgrep release gate and return canonicalizable evidence."""

    candidate = repository.absolute()
    parent_environment = dict(os.environ if environment is None else environment)
    git_environment = _git_environment(parent_environment)
    _validate_repository_directory(candidate)
    git = _find_executable("git", executable_finder)
    semgrep = _find_executable("semgrep", executable_finder)
    _bind_semgrep_to_project_environment(
        semgrep,
        candidate,
        Path(sys.prefix) if python_prefix is None else python_prefix,
        Path(sys.base_prefix) if python_base_prefix is None else python_base_prefix,
        parent_environment.get("UV_PROJECT_ENVIRONMENT"),
    )
    semgrep_parent, semgrep_record = _snapshot_absolute_artifact(Path(semgrep))
    root_output = _run_checked(
        runner,
        (git, "-C", str(candidate), "rev-parse", "--show-toplevel"),
        candidate,
        git_environment,
        command_name="git-root",
    )
    try:
        reported_root = Path(root_output.decode("utf-8", errors="strict").strip()).absolute()
    except UnicodeDecodeError as exc:
        raise GateError("git-output", "Git repository root is not strict UTF-8") from exc
    if os.path.normcase(str(reported_root)) != os.path.normcase(str(candidate)):
        raise GateError("wrong-repository-root", "Requested path is not the Git repository root")

    inventory = _read_inventory(git, candidate, runner, git_environment)
    directory_identities = _collect_directory_identities(candidate, inventory)
    targets = tuple(
        path for path in inventory if path != SEMGREP_IGNORE_FILE and not _is_policy_skip(path)
    )
    policy_skips = tuple(path for path in inventory if _is_policy_skip(path))
    if not targets:
        raise GateError("empty-targets", "Semgrep release-gate target set is empty")

    with (
        _temporary_external_mirror(candidate) as mirror,
        _temporary_external_mirror(candidate) as control_root,
    ):
        if _is_within(control_root, mirror) or _is_within(mirror, control_root):
            raise GateError("unsafe-control-root", "Rule control root overlaps source mirror")
        xdg_config_home = control_root / "xdg"
        try:
            xdg_config_home.mkdir()
        except OSError as exc:
            raise GateError(
                "unsafe-control-root", f"Cannot create isolated XDG root: {exc}"
            ) from exc
        xdg_stat = _lstat(xdg_config_home, label="isolated XDG root")
        if not stat.S_ISDIR(xdg_stat.st_mode) or any(xdg_config_home.iterdir()):
            raise GateError("unsafe-control-root", "Isolated XDG root is not fresh and empty")
        for directory_name in (
            "appdata",
            "cache",
            "data",
            "home",
            "localappdata",
            "state",
            "temp",
        ):
            isolated_directory = control_root / directory_name
            try:
                isolated_directory.mkdir()
            except OSError as exc:
                raise GateError(
                    "unsafe-control-root",
                    f"Cannot create isolated user directory {directory_name}: {exc}",
                ) from exc
            isolated_stat = _lstat(
                isolated_directory, label=f"isolated user directory {directory_name}"
            )
            if not stat.S_ISDIR(isolated_stat.st_mode) or any(isolated_directory.iterdir()):
                raise GateError(
                    "unsafe-control-root",
                    f"Isolated user directory is not fresh: {directory_name}",
                )
        remote_environment = _remote_environment(
            parent_environment,
            xdg_config_home,
            semgrep_directory=semgrep_parent,
        )
        offline_environment = _offline_environment(remote_environment)
        records = _copy_to_mirror(candidate, mirror, inventory)
        mirror_directory_identities = _collect_directory_identities(mirror, inventory)
        if _collect_directory_identities(candidate, inventory) != directory_identities:
            raise GateError("toctou", "Repository directory identity changed during mirroring")
        _verify_records(candidate, mirror, records)
        _run_checked(
            runner,
            _semgrep_dump_command(semgrep),
            mirror,
            remote_environment,
            command_name="semgrep-rule-dump",
        )
        _verify_artifacts(semgrep_parent, (semgrep_record,))
        _verify_records(candidate, mirror, records)
        bundle_path, _bundle_bytes, artifact_records = _load_rule_bundle(
            control_root,
            xdg_config_home,
            bundle_contract,
        )
        artifact_directories = _collect_directory_identities(
            control_root, [record.relative_path for record in artifact_records]
        )
        result = runner(
            _semgrep_bundle_command(semgrep, bundle_path),
            mirror,
            offline_environment,
        )
        stdout, stderr = _completed_bytes(result, command_name="semgrep-bundle")
        if result.returncode not in {0, 1}:
            detail = stderr.decode("utf-8", errors="replace").strip().splitlines()
            first_line = detail[0][:300] if detail else "no diagnostic"
            raise GateError(
                "semgrep-failed",
                f"Semgrep exited with {result.returncode}: {first_line}",
            )
        scanned, rule_ids, findings = _parse_semgrep_json(
            stdout,
            targets,
            rule_contract,
            mirror,
            finding_allowlist,
        )
        expected_returncode = 1 if findings else 0
        if result.returncode != expected_returncode:
            raise GateError(
                "semgrep-returncode",
                f"Semgrep return-code drift: {result.returncode} != {expected_returncode}",
            )
        if _read_inventory(git, candidate, runner, git_environment) != inventory:
            raise GateError("toctou", "Git-owned inventory changed during the Semgrep scan")
        if _collect_directory_identities(candidate, inventory) != directory_identities:
            raise GateError("toctou", "Repository directory identity changed during the scan")
        if _collect_directory_identities(mirror, inventory) != mirror_directory_identities:
            raise GateError("toctou", "Mirror directory identity changed during the scan")
        if (
            _collect_directory_identities(
                control_root, [record.relative_path for record in artifact_records]
            )
            != artifact_directories
        ):
            raise GateError("toctou", "Rule-artifact directory identity changed during the scan")
        _verify_artifacts(control_root, artifact_records)
        _verify_artifacts(semgrep_parent, (semgrep_record,))
        _verify_records(candidate, mirror, records)
        return _success_evidence(
            records,
            scanned,
            policy_skips,
            rule_ids,
            findings,
            bundle_contract,
        )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="Git repository root to audit (default: current directory)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _argument_parser().parse_args(argv)
    try:
        evidence = run_release_gate(arguments.repository)
    except GateError as exc:
        failure = {
            "error_code": exc.code,
            "gate": "semgrep-release",
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "status": "fail",
        }
        print(_canonical_json(failure), file=sys.stderr)
        print(f"semgrep release gate failed: {exc}", file=sys.stderr)
        return 1
    print(_canonical_json(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
