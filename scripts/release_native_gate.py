"""Pinned Windows-native release checks with fail-closed supply-chain handling.

The gate downloads only the three native assets pinned in
``release_native_tools.json``, hashes every complete archive before opening it,
extracts one exact executable member, verifies the executable's own version
output, and then runs the canonical workflow and secret-scanning commands in a
minimal environment.  It also resolves the locked Zizmor distribution strictly
from the active environment and runs both offline personas.  The worktree secret
scan uses a mirror of the clean, tracked checkout, so ignored dependency
environments cannot make release evidence depend on a particular runner.

This module intentionally uses only the Python standard library.  Invoke it from
the frozen ``release`` dependency group so actionlint receives the exact locked
Pyflakes executable.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import winreg
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import IO, TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from http.client import HTTPMessage

type Command = tuple[str, ...]
type Environment = Mapping[str, str]

TARGET_PYTHON: Final = (3, 14, 7)
PYFLAKES_VERSION: Final = "3.4.0"
MANIFEST_SCHEMA_VERSION: Final = 1
MAX_ARCHIVE_BYTES: Final = 100 * 1024 * 1024
MAX_EXECUTABLE_BYTES: Final = 64 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS: Final = 60.0
COMMAND_TIMEOUT_SECONDS: Final = 600
DOWNLOAD_CHUNK_BYTES: Final = 1024 * 1024
_REDIRECT_HOSTS: Final = frozenset({"github.com", "release-assets.githubusercontent.com"})
_FORBIDDEN_GITLEAKS_POLICY_FILES: Final = frozenset({".gitleaks.toml", ".gitleaksignore"})
_GIT_FOR_WINDOWS_REGISTRY_KEY: Final = r"SOFTWARE\GitForWindows"
_GIT_FOR_WINDOWS_VERSION: Final = re.compile(
    rb"git version [1-9][0-9]*\.[0-9]+\.[0-9]+\.windows\.[1-9][0-9]*(?:\r?\n)?"
)


class GateError(RuntimeError):
    """A native release-gate violation with a stable diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ToolPin:
    """Immutable identity and archive contract for one native executable."""

    name: str
    version: str
    url: str
    sha256: str
    archive_member: str
    version_args: tuple[str, ...]


EXPECTED_TOOL_PINS: Final = (
    ToolPin(
        name="actionlint",
        version="1.7.12",
        url=(
            "https://github.com/rhysd/actionlint/releases/download/"
            "v1.7.12/actionlint_1.7.12_windows_amd64.zip"
        ),
        sha256="6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
        archive_member="actionlint.exe",
        version_args=("-version",),
    ),
    ToolPin(
        name="shellcheck",
        version="0.11.0",
        url=(
            "https://github.com/koalaman/shellcheck/releases/download/"
            "v0.11.0/shellcheck-v0.11.0.zip"
        ),
        sha256="8a4e35ab0b331c85d73567b12f2a444df187f483e5079ceffa6bda1faa2e740e",
        archive_member="shellcheck.exe",
        version_args=("--version",),
    ),
    ToolPin(
        name="gitleaks",
        version="8.30.1",
        url=(
            "https://github.com/gitleaks/gitleaks/releases/download/"
            "v8.30.1/gitleaks_8.30.1_windows_x64.zip"
        ),
        sha256="d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
        archive_member="gitleaks.exe",
        version_args=("version",),
    ),
)


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GateError("manifest-duplicate-key", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _pin_as_json(pin: ToolPin) -> dict[str, object]:
    return {
        "name": pin.name,
        "version": pin.version,
        "url": pin.url,
        "sha256": pin.sha256,
        "archive_member": pin.archive_member,
        "version_args": list(pin.version_args),
    }


def load_manifest(path: Path) -> tuple[ToolPin, ...]:
    """Load only the exact reviewed native-tool contract."""

    try:
        text = path.read_text(encoding="utf-8")
        raw = cast(
            "object",
            json.loads(text, object_pairs_hook=_strict_object),
        )
    except GateError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(
            "manifest-unreadable",
            "native-tool manifest is not strict UTF-8 JSON",
        ) from exc

    expected: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "tools": [_pin_as_json(pin) for pin in EXPECTED_TOOL_PINS],
    }
    if raw != expected:
        raise GateError(
            "manifest-contract",
            "native-tool manifest differs from the reviewed URL, version, hash, or member pins",
        )
    return EXPECTED_TOOL_PINS


def _validate_download_url(url: str, *, initial: bool) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _REDIRECT_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        phase = "asset" if initial else "redirect"
        raise GateError("download-url", f"untrusted {phase} URL")
    if initial and parsed.hostname != "github.com":
        raise GateError("download-url", "asset URL must start at github.com")


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject an untrusted redirect before urllib follows that individual hop."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        # ``HTTPRedirectHandler.http_error_302`` resolves relative Location
        # values before dispatching here, so this validates every resolved hop.
        _validate_download_url(newurl, initial=False)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_verified_archive(pin: ToolPin, destination: Path) -> None:
    """Download and hash the complete archive without interpreting its contents."""

    _validate_download_url(pin.url, initial=True)
    request = urllib.request.Request(  # noqa: S310 - exact HTTPS URL and digest are pinned
        pin.url,
        headers={"Accept": "application/octet-stream", "User-Agent": "mutmut-win-release-gate/1"},
        method="GET",
    )
    digest = hashlib.sha256()
    total = 0
    opener = urllib.request.build_opener(_AllowlistedRedirectHandler())
    try:
        with opener.open(
            request,
            timeout=DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            _validate_download_url(response.geturl(), initial=False)
            with destination.open("xb") as output:
                while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
                    total += len(chunk)
                    if total > MAX_ARCHIVE_BYTES:
                        raise GateError("archive-size", f"{pin.name} archive exceeds size limit")
                    digest.update(chunk)
                    output.write(chunk)
    except GateError:
        destination.unlink(missing_ok=True)
        raise
    except (OSError, urllib.error.URLError) as exc:
        destination.unlink(missing_ok=True)
        raise GateError("download-failed", f"could not download pinned {pin.name} archive") from exc

    if total == 0 or digest.hexdigest() != pin.sha256:
        destination.unlink(missing_ok=True)
        raise GateError("archive-digest", f"SHA-256 mismatch for {pin.name} archive")


ZIZMOR_VERSION: Final = "1.30.0"


def _validate_archive_name(name: str) -> None:
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise GateError("archive-path", "archive contains an unsafe member name")


def extract_exact_executable(pin: ToolPin, archive: Path, destination: Path) -> None:
    """Validate the full ZIP directory and extract only the pinned member."""

    try:
        with zipfile.ZipFile(archive, mode="r") as zipped:
            members = zipped.infolist()
            names: set[str] = set()
            selected: zipfile.ZipInfo | None = None
            for member in members:
                _validate_archive_name(member.filename)
                if member.filename in names:
                    raise GateError("archive-duplicate", "archive contains duplicate member names")
                names.add(member.filename)
                unix_mode = member.external_attr >> 16
                dos_attributes = member.external_attr & 0xFFFF
                if member.flag_bits & 0x1:
                    raise GateError("archive-encrypted", "archive contains an encrypted member")
                if stat.S_ISLNK(unix_mode) or dos_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise GateError("archive-link", "archive contains a link or reparse member")
                if member.filename == pin.archive_member:
                    selected = member

            if selected is None or selected.is_dir():
                raise GateError("archive-member", f"missing exact {pin.archive_member} member")
            if selected.file_size <= 0 or selected.file_size > MAX_EXECUTABLE_BYTES:
                raise GateError("executable-size", f"invalid extracted size for {pin.name}")

            destination.parent.mkdir(parents=True, exist_ok=False)
            with zipped.open(selected, mode="r") as source, destination.open("xb") as output:
                shutil.copyfileobj(source, output, length=DOWNLOAD_CHUNK_BYTES)
    except GateError:
        destination.unlink(missing_ok=True)
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        destination.unlink(missing_ok=True)
        raise GateError("archive-invalid", f"invalid {pin.name} ZIP archive") from exc

    if destination.stat().st_size != selected.file_size:
        destination.unlink(missing_ok=True)
        raise GateError("executable-size", f"truncated extracted executable for {pin.name}")


def _run_command(
    command: Command,
    *,
    purpose: str,
    cwd: Path,
    environment: Environment,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(  # noqa: S603 - every executable is resolved or digest-pinned
            command,
            cwd=cwd,
            env=dict(environment),
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GateError("command-failed", f"{purpose} did not complete") from exc
    if result.returncode != 0:
        # Never replay scanner output here: even redacted scanners cannot make
        # arbitrary workflow diagnostics safe to print into public CI logs.
        raise GateError("command-nonzero", f"{purpose} exited with {result.returncode}")
    return result


def validate_tool_version(pin: ToolPin, result: subprocess.CompletedProcess[bytes]) -> None:
    try:
        text = (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GateError("tool-version", f"{pin.name} emitted non-UTF-8 version output") from exc
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n") if line.strip()]
    valid = False
    if pin.name == "actionlint":
        valid = bool(lines) and lines[0] == pin.version
    elif pin.name == "shellcheck":
        valid = lines.count(f"version: {pin.version}") == 1
    elif pin.name == "gitleaks":
        valid = lines == [pin.version]
    if not valid:
        raise GateError("tool-version", f"{pin.name} did not report exact version {pin.version}")


def validate_git_for_windows_version(result: subprocess.CompletedProcess[bytes]) -> None:
    """Accept exactly one canonical Git-for-Windows version line."""

    if result.stderr or _GIT_FOR_WINDOWS_VERSION.fullmatch(result.stdout) is None:
        raise GateError("git-version", "Git did not report one strict Git-for-Windows version line")


def locate_locked_pyflakes() -> Path:
    """Resolve Pyflakes from this interpreter's locked environment, never PATH."""

    try:
        observed = importlib.metadata.version("pyflakes")
    except importlib.metadata.PackageNotFoundError as exc:
        raise GateError(
            "pyflakes-missing",
            "locked Pyflakes distribution is not installed",
        ) from exc
    if observed != PYFLAKES_VERSION:
        raise GateError(
            "pyflakes-version",
            f"expected Pyflakes {PYFLAKES_VERSION}, observed {observed}",
        )

    scripts = Path(sysconfig.get_path("scripts")).resolve(strict=True)
    executable = (scripts / "pyflakes.exe").resolve(strict=True)
    if executable.parent != scripts or not executable.is_file():
        raise GateError("pyflakes-path", "Pyflakes executable is outside the active environment")
    return executable


def locate_locked_zizmor() -> Path:
    """Resolve Zizmor from this interpreter's locked environment, never PATH."""

    try:
        observed = importlib.metadata.version("zizmor")
    except importlib.metadata.PackageNotFoundError as exc:
        raise GateError(
            "zizmor-missing",
            "locked Zizmor distribution is not installed",
        ) from exc
    if observed != ZIZMOR_VERSION:
        raise GateError(
            "zizmor-version",
            f"expected Zizmor {ZIZMOR_VERSION}, observed {observed}",
        )

    try:
        scripts = Path(sysconfig.get_path("scripts")).resolve(strict=True)
        executable = (scripts / "zizmor.exe").resolve(strict=True)
    except OSError as exc:
        raise GateError(
            "zizmor-path",
            "Zizmor executable is unavailable in the active environment",
        ) from exc
    if executable.parent != scripts or not executable.is_file():
        raise GateError("zizmor-path", "Zizmor executable is outside the active environment")
    return executable


def locate_system_git() -> Path:
    """Resolve 64-bit system Git for Windows without consulting ambient PATH."""

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            _GIT_FOR_WINDOWS_REGISTRY_KEY,
            access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            raw_install_path, value_type = winreg.QueryValueEx(key, "InstallPath")
    except OSError as exc:
        raise GateError("git-registry", "system Git for Windows is not registered") from exc

    if (
        value_type != winreg.REG_SZ
        or not isinstance(raw_install_path, str)
        or not raw_install_path
        or raw_install_path != raw_install_path.strip()
        or "\x00" in raw_install_path
    ):
        raise GateError("git-registry", "Git for Windows InstallPath is invalid")

    configured_root = Path(raw_install_path)
    if not configured_root.is_absolute():
        raise GateError("git-registry", "Git for Windows InstallPath must be absolute")
    try:
        install_root = configured_root.resolve(strict=True)
        command_directory = install_root / "cmd"
        command_metadata = command_directory.lstat()
        resolved_command_directory = command_directory.resolve(strict=True)
        configured_executable = command_directory / "git.exe"
        executable_metadata = configured_executable.lstat()
        executable = configured_executable.resolve(strict=True)
    except OSError as exc:
        raise GateError("git-path", "registered Git for Windows executable is unavailable") from exc

    command_attributes = getattr(command_metadata, "st_file_attributes", 0)
    executable_attributes = getattr(executable_metadata, "st_file_attributes", 0)
    if (
        not install_root.is_dir()
        or command_directory.is_symlink()
        or command_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or not stat.S_ISDIR(command_metadata.st_mode)
        or resolved_command_directory.parent != install_root
        or executable.parent != resolved_command_directory
        or not executable.is_relative_to(install_root)
        or configured_executable.is_symlink()
        or executable_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or not stat.S_ISREG(executable_metadata.st_mode)
    ):
        raise GateError(
            "git-path",
            "registered Git executable is not a contained regular cmd/git.exe",
        )
    return executable


def sanitized_environment(
    *,
    temp_root: Path,
    git: Path,
    pyflakes: Path,
    zizmor: Path,
    tools: Mapping[str, Path],
) -> dict[str, str]:
    """Create a minimal deterministic environment without caller credentials."""

    system_root = Path(os.environ.get("SYSTEMROOT", "C:/Windows")).resolve(strict=True)
    system32 = (system_root / "System32").resolve(strict=True)
    command_processor = (system32 / "cmd.exe").resolve(strict=True)
    private_home = temp_root / "home"
    private_temp = temp_root / "tmp"
    private_config = private_home / ".config"
    private_home.mkdir(parents=True, exist_ok=False)
    private_temp.mkdir(parents=True, exist_ok=False)
    private_config.mkdir(parents=True, exist_ok=False)

    support_path_entries = {
        pyflakes.parent,
        zizmor.parent,
        Path(sys.executable).resolve(strict=True).parent,
        system32,
        *(tool.parent for tool in tools.values()),
    }
    support_path_entries.discard(git.parent)
    path_value = os.pathsep.join(
        (
            str(git.parent),
            *(
                str(item)
                for item in sorted(support_path_entries, key=lambda item: str(item).casefold())
            ),
        )
    )
    return {
        "APPDATA": str(private_config),
        "COMSPEC": str(command_processor),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": str(private_home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "LOCALAPPDATA": str(private_home),
        "NO_COLOR": "1",
        "PAGER": "cat",
        "PATH": path_value,
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1",
        # actionlint forwards this exact option to the pinned ShellCheck. It
        # prevents repository, ancestor, or user .shellcheckrc suppression.
        "SHELLCHECK_OPTS": "--norc",
        "SYSTEMROOT": str(system_root),
        "TEMP": str(private_temp),
        "TMP": str(private_temp),
        "TZ": "UTC",
        "USERPROFILE": str(private_home),
        "WINDIR": str(system_root),
        "XDG_CONFIG_HOME": str(private_config),
    }


def actionlint_command(
    actionlint: Path,
    shellcheck: Path,
    pyflakes: Path,
    config: Path,
    workflow: Path,
) -> Command:
    return (
        str(actionlint),
        "-no-color",
        "-config-file",
        str(config),
        "-shellcheck",
        str(shellcheck),
        "-pyflakes",
        str(pyflakes),
        str(workflow),
    )


def zizmor_commands(zizmor: Path, workflow: Path) -> tuple[Command, Command]:
    """Return both mandatory offline Zizmor personas in a fixed order."""

    base = (
        str(zizmor),
        "--offline",
        "--strict-collection",
        "--no-config",
        "--no-ignores",
    )
    return (
        (*base, "--persona=regular", str(workflow)),
        (*base, "--persona=pedantic", str(workflow)),
    )


def gitleaks_worktree_command(gitleaks: Path, mirror: Path) -> Command:
    return (
        str(gitleaks),
        "dir",
        "--no-banner",
        "--no-color",
        "--redact=100",
        "--timeout=300",
        str(mirror),
    )


def gitleaks_history_command(gitleaks: Path, repository: Path) -> Command:
    # Include HEAD explicitly: in a detached GitHub checkout, ``--all`` alone
    # need not include the checked-out commit after the temporary ref is removed.
    return (
        str(gitleaks),
        "git",
        "--no-banner",
        "--no-color",
        "--redact=100",
        "--timeout=300",
        "--log-opts=--all HEAD --full-history -m",
        str(repository),
    )


def _git_output(
    git: Path,
    arguments: Sequence[str],
    *,
    repository: Path,
    environment: Environment,
    purpose: str,
) -> bytes:
    command = (str(git), *arguments)
    return _run_command(
        command,
        purpose=purpose,
        cwd=repository,
        environment=environment,
    ).stdout


def assert_clean_complete_checkout(
    git: Path,
    repository: Path,
    environment: Environment,
) -> None:
    """Bind scans to one clean, complete checkout; detached HEAD is permitted."""

    top = (
        _git_output(
            git,
            ("rev-parse", "--show-toplevel"),
            repository=repository,
            environment=environment,
            purpose="resolve Git checkout",
        )
        .decode("utf-8", errors="strict")
        .strip()
    )
    if Path(top).resolve(strict=True) != repository.resolve(strict=True):
        raise GateError("git-root", "native release gate is not running at the checkout root")
    shallow = _git_output(
        git,
        ("rev-parse", "--is-shallow-repository"),
        repository=repository,
        environment=environment,
        purpose="verify complete Git history",
    ).strip()
    if shallow != b"false":
        raise GateError("git-shallow", "complete Git history is required for the release scan")
    dirty = _git_output(
        git,
        ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        repository=repository,
        environment=environment,
        purpose="verify clean release checkout",
    )
    if dirty:
        raise GateError("git-dirty", "release checkout contains tracked or non-ignored changes")


def assert_no_local_gitleaks_policy(repository: Path) -> None:
    """Reject even ignored or broken local policy files before Gitleaks starts."""

    for name in sorted(_FORBIDDEN_GITLEAKS_POLICY_FILES):
        path = repository / name
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise GateError(
                "gitleaks-policy",
                "could not prove that repository-local Gitleaks policy is absent",
            ) from exc
        raise GateError(
            "gitleaks-policy",
            "repository-local Gitleaks suppression or configuration is not permitted",
        )


def _validate_git_path(path: str) -> PurePosixPath:
    candidate = PurePosixPath(path)
    windows = PureWindowsPath(path)
    if (
        not path
        or "\x00" in path
        or "\\" in path
        or candidate.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise GateError("git-path", "Git index contains an unsafe path")
    return candidate


def tracked_paths(
    git: Path,
    repository: Path,
    environment: Environment,
) -> tuple[PurePosixPath, ...]:
    """Return stage-zero regular files from the index without quoted paths."""

    raw = _git_output(
        git,
        ("ls-files", "--stage", "-z"),
        repository=repository,
        environment=environment,
        purpose="inventory tracked worktree",
    )
    result: list[PurePosixPath] = []
    seen: set[str] = set()
    for record in raw.split(b"\x00"):
        if not record:
            continue
        metadata, separator, encoded_path = record.partition(b"\t")
        if not separator:
            raise GateError("git-index", "malformed Git index record")
        fields = metadata.split(b" ")
        if len(fields) != 3 or fields[0] not in {b"100644", b"100755"} or fields[2] != b"0":
            raise GateError("git-index", "Git index contains a non-regular or non-stage-zero entry")
        try:
            text_path = encoded_path.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise GateError("git-path", "Git path is not canonical UTF-8") from exc
        path = _validate_git_path(text_path)
        canonical = path.as_posix()
        if canonical in seen:
            raise GateError("git-index", "Git index repeats a path")
        seen.add(canonical)
        if canonical.casefold() in _FORBIDDEN_GITLEAKS_POLICY_FILES:
            raise GateError(
                "gitleaks-policy",
                "repository-local Gitleaks suppression or configuration is not permitted",
            )
        result.append(path)
    if not result:
        raise GateError("git-index", "Git index inventory is empty")
    return tuple(sorted(result, key=lambda item: item.as_posix().encode("utf-8")))


def create_tracked_mirror(repository: Path, mirror: Path, paths: Sequence[PurePosixPath]) -> None:
    """Copy regular tracked checkout bytes to an external scan-only mirror."""

    root = repository.resolve(strict=True)
    mirror.mkdir(parents=True, exist_ok=False)
    for relative in paths:
        source = repository.joinpath(*relative.parts)
        try:
            resolved = source.resolve(strict=True)
            metadata = source.lstat()
        except OSError as exc:
            raise GateError("worktree-read", "tracked worktree file is unavailable") from exc
        file_attributes = getattr(metadata, "st_file_attributes", 0)
        if (
            not resolved.is_relative_to(root)
            or source.is_symlink()
            or file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or not source.is_file()
        ):
            raise GateError("worktree-link", "tracked worktree path is not a regular in-tree file")
        destination = mirror.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with source.open("rb") as input_file, destination.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file, length=DOWNLOAD_CHUNK_BYTES)
        except OSError as exc:
            raise GateError("worktree-read", "could not mirror tracked worktree bytes") from exc


def _assert_target_runtime() -> None:
    if sys.platform != "win32" or sys.version_info[:3] != TARGET_PYTHON:
        raise GateError("runtime", "native release gate requires Windows and CPython 3.14.7")
    if platform.python_implementation() != "CPython":
        raise GateError("runtime", "native release gate requires CPython")
    if platform.machine().casefold() not in {"amd64", "x86_64"}:
        raise GateError("architecture", "native release gate requires Windows x64")


def run_gate(repository: Path) -> None:
    """Run the complete pinned native release gate."""

    _assert_target_runtime()
    repository = repository.resolve(strict=True)
    manifest = repository / "scripts" / "release_native_tools.json"
    workflow = repository / ".github" / "workflows" / "ci.yml"
    if not workflow.is_file():
        raise GateError("workflow-missing", "canonical CI workflow is missing")
    pins = load_manifest(manifest)
    git = locate_system_git()
    pyflakes = locate_locked_pyflakes()
    zizmor = locate_locked_zizmor()

    with tempfile.TemporaryDirectory(prefix="mutmut-win-native-gate-") as raw_temp:
        temp_root = Path(raw_temp).resolve(strict=True)
        installed: dict[str, Path] = {}
        for pin in pins:
            archive = temp_root / f"{pin.name}.zip"
            executable = temp_root / "tools" / pin.name / pin.archive_member
            download_verified_archive(pin, archive)
            extract_exact_executable(pin, archive, executable)
            installed[pin.name] = executable.resolve(strict=True)

        environment = sanitized_environment(
            temp_root=temp_root,
            git=git,
            pyflakes=pyflakes,
            zizmor=zizmor,
            tools=installed,
        )
        git_version = _run_command(
            (str(git), "--version"),
            purpose="verify Git executable",
            cwd=repository,
            environment=environment,
        )
        validate_git_for_windows_version(git_version)
        for pin in pins:
            result = _run_command(
                (str(installed[pin.name]), *pin.version_args),
                purpose=f"verify {pin.name} version",
                cwd=repository,
                environment=environment,
            )
            validate_tool_version(pin, result)

        assert_clean_complete_checkout(git, repository, environment)
        assert_no_local_gitleaks_policy(repository)
        paths = tracked_paths(git, repository, environment)
        mirror = temp_root / "worktree"
        create_tracked_mirror(repository, mirror, paths)
        actionlint_config = temp_root / "actionlint.yaml"
        actionlint_config.write_bytes(b"")

        _run_command(
            actionlint_command(
                installed["actionlint"],
                installed["shellcheck"],
                pyflakes,
                actionlint_config,
                workflow,
            ),
            purpose="actionlint with ShellCheck and locked Pyflakes",
            cwd=repository,
            environment=environment,
        )
        for persona, command in zip(
            ("regular", "pedantic"),
            zizmor_commands(zizmor, workflow),
            strict=True,
        ):
            _run_command(
                command,
                purpose=f"Zizmor {persona} offline workflow audit",
                cwd=repository,
                environment=environment,
            )
        _run_command(
            gitleaks_worktree_command(installed["gitleaks"], mirror),
            purpose="Gitleaks tracked-worktree scan",
            cwd=repository,
            environment=environment,
        )
        _run_command(
            gitleaks_history_command(installed["gitleaks"], repository),
            purpose="Gitleaks complete-history scan",
            cwd=repository,
            environment=environment,
        )
        assert_clean_complete_checkout(git, repository, environment)


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    try:
        run_gate(repository)
    except GateError as exc:
        print(f"release-native-gate: FAILED [{exc.code}] {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as exc:
        print(
            f"release-native-gate: FAILED [unexpected-io] {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    print(
        "release-native-gate: OK (actionlint, ShellCheck, Pyflakes, "
        "Zizmor regular/pedantic, Gitleaks worktree/history)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
