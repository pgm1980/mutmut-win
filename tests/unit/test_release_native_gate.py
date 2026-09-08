"""Adversarial contracts for the pinned Windows-native release gate."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import replace
from http.client import HTTPMessage
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import pytest

from scripts import release_native_gate as gate

if TYPE_CHECKING:
    import urllib.request
    from collections.abc import Callable
    from types import TracebackType

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _PROJECT_ROOT / "scripts" / "release_native_tools.json"


class _Response:
    def __init__(self, payload: bytes, final_url: str) -> None:
        self._stream = io.BytesIO(payload)
        self._final_url = final_url

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._final_url

    def __enter__(self) -> _Response:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


class _Opener:
    def __init__(
        self,
        callback: Callable[[urllib.request.Request, float], _Response],
    ) -> None:
        self._callback = callback

    def open(self, request: urllib.request.Request, timeout: float) -> _Response:
        return self._callback(request, timeout)


def _replace_download_opener(
    monkeypatch: pytest.MonkeyPatch,
    callback: Callable[[urllib.request.Request, float], _Response],
) -> None:
    def fake_build_opener(*handlers: object) -> _Opener:
        assert len(handlers) == 1
        assert isinstance(handlers[0], gate._AllowlistedRedirectHandler)
        return _Opener(callback)

    monkeypatch.setattr(gate.urllib.request, "build_opener", fake_build_opener)


class _RegistryKey:
    def __enter__(self) -> _RegistryKey:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback


def _replace_git_registry(
    monkeypatch: pytest.MonkeyPatch,
    install_path: object,
    value_type: int = gate.winreg.REG_SZ,
) -> None:
    registry_key = _RegistryKey()

    def fake_open_key(
        root: object,
        sub_key: str,
        reserved: int = 0,
        access: int = 0,
    ) -> _RegistryKey:
        assert root == gate.winreg.HKEY_LOCAL_MACHINE
        assert sub_key == gate._GIT_FOR_WINDOWS_REGISTRY_KEY
        assert reserved == 0
        assert access == gate.winreg.KEY_READ | gate.winreg.KEY_WOW64_64KEY
        return registry_key

    def fake_query_value(key: object, name: str) -> tuple[object, int]:
        assert key is registry_key
        assert name == "InstallPath"
        return install_path, value_type

    monkeypatch.setattr(gate.winreg, "OpenKey", fake_open_key)
    monkeypatch.setattr(gate.winreg, "QueryValueEx", fake_query_value)


def _zip_bytes(members: list[tuple[zipfile.ZipInfo | str, bytes]]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w") as archive:
        for name, payload in members:
            archive.writestr(name, payload)
    return stream.getvalue()


def _completed(stdout: bytes, stderr: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=(), returncode=0, stdout=stdout, stderr=stderr)


def test_checked_in_manifest_is_the_exact_reviewed_contract() -> None:
    assert gate.load_manifest(_MANIFEST) == gate.EXPECTED_TOOL_PINS
    assert [pin.name for pin in gate.EXPECTED_TOOL_PINS] == [
        "actionlint",
        "shellcheck",
        "gitleaks",
    ]
    assert [pin.version for pin in gate.EXPECTED_TOOL_PINS] == ["1.7.12", "0.11.0", "8.30.1"]
    assert [pin.sha256 for pin in gate.EXPECTED_TOOL_PINS] == [
        "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
        "8a4e35ab0b331c85d73567b12f2a444df187f483e5079ceffa6bda1faa2e740e",
        "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
    ]


def test_manifest_rejects_duplicate_keys(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"schema_version":1,"schema_version":1,"tools":[]}', encoding="utf-8")

    with pytest.raises(gate.GateError, match="duplicate JSON key") as error:
        gate.load_manifest(manifest)

    assert error.value.code == "manifest-duplicate-key"


def test_manifest_rejects_any_changed_pin(tmp_path: Path) -> None:
    raw = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    raw["tools"][0]["sha256"] = "0" * 64
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(gate.GateError, match="differs from the reviewed") as error:
        gate.load_manifest(manifest)

    assert error.value.code == "manifest-contract"


def test_download_hashes_complete_archive_before_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"pinned archive bytes"
    pin = replace(
        gate.EXPECTED_TOOL_PINS[0],
        sha256=hashlib.sha256(payload).hexdigest(),
    )

    def fake_urlopen(
        request: urllib.request.Request,
        timeout: float,
    ) -> _Response:
        assert request.full_url == pin.url
        assert timeout == gate.DOWNLOAD_TIMEOUT_SECONDS
        return _Response(payload, "https://release-assets.githubusercontent.com/pinned")

    _replace_download_opener(monkeypatch, fake_urlopen)
    destination = tmp_path / "asset.zip"
    gate.download_verified_archive(pin, destination)

    assert destination.read_bytes() == payload


def test_download_rejects_digest_before_archive_can_be_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pin = gate.EXPECTED_TOOL_PINS[0]

    def fake_urlopen(
        request: urllib.request.Request,
        timeout: float,
    ) -> _Response:
        del request, timeout
        return _Response(b"not the pinned archive", pin.url)

    _replace_download_opener(monkeypatch, fake_urlopen)
    destination = tmp_path / "asset.zip"

    with pytest.raises(gate.GateError, match="SHA-256 mismatch") as error:
        gate.download_verified_archive(pin, destination)

    assert error.value.code == "archive-digest"
    assert not destination.exists()


def test_download_rejects_untrusted_redirect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pin = gate.EXPECTED_TOOL_PINS[0]

    def fake_urlopen(
        request: urllib.request.Request,
        timeout: float,
    ) -> _Response:
        del request, timeout
        return _Response(b"irrelevant", "https://attacker.invalid/actionlint.zip")

    _replace_download_opener(monkeypatch, fake_urlopen)

    with pytest.raises(gate.GateError, match="untrusted redirect") as error:
        gate.download_verified_archive(pin, tmp_path / "asset.zip")

    assert error.value.code == "download-url"


def test_redirect_handler_allows_each_resolved_allowlisted_https_hop() -> None:
    handler = gate._AllowlistedRedirectHandler()
    request = gate.urllib.request.Request(gate.EXPECTED_TOOL_PINS[0].url)

    first = handler.redirect_request(
        request,
        io.BytesIO(),
        302,
        "Found",
        HTTPMessage(),
        "https://release-assets.githubusercontent.com/intermediate",
    )
    assert first is not None
    assert first.full_url == "https://release-assets.githubusercontent.com/intermediate"

    second = handler.redirect_request(
        first,
        io.BytesIO(),
        307,
        "Temporary Redirect",
        HTTPMessage(),
        "https://github.com/final",
    )
    assert second is not None
    assert second.full_url == "https://github.com/final"


@pytest.mark.parametrize(
    "redirect_url",
    [
        "http://release-assets.githubusercontent.com/downgrade",
        "https://attacker.invalid/tool.zip",
        "https://attacker@github.com/tool.zip",
    ],
)
def test_redirect_handler_rejects_each_untrusted_resolved_hop(redirect_url: str) -> None:
    handler = gate._AllowlistedRedirectHandler()
    request = gate.urllib.request.Request(gate.EXPECTED_TOOL_PINS[0].url)

    with pytest.raises(gate.GateError, match="untrusted redirect") as error:
        handler.redirect_request(
            request,
            io.BytesIO(),
            302,
            "Found",
            HTTPMessage(),
            redirect_url,
        )

    assert error.value.code == "download-url"


def test_extractor_writes_only_the_exact_executable_member(tmp_path: Path) -> None:
    pin = gate.EXPECTED_TOOL_PINS[0]
    archive = tmp_path / "asset.zip"
    archive.write_bytes(
        _zip_bytes(
            [
                ("README.md", b"documentation"),
                (pin.archive_member, b"native executable"),
            ]
        )
    )
    destination = tmp_path / "tool" / pin.archive_member

    gate.extract_exact_executable(pin, archive, destination)

    assert destination.read_bytes() == b"native executable"
    assert not (destination.parent / "README.md").exists()


@pytest.mark.parametrize("unsafe_name", ["../escape.exe", "/absolute.exe", "C:/drive.exe"])
def test_extractor_rejects_unsafe_members_even_beside_the_pinned_member(
    tmp_path: Path,
    unsafe_name: str,
) -> None:
    pin = gate.EXPECTED_TOOL_PINS[0]
    archive = tmp_path / "asset.zip"
    archive.write_bytes(
        _zip_bytes(
            [
                (pin.archive_member, b"native executable"),
                (unsafe_name, b"escape"),
            ]
        )
    )

    with pytest.raises(gate.GateError) as error:
        gate.extract_exact_executable(pin, archive, tmp_path / "tool" / pin.archive_member)

    assert error.value.code == "archive-path"


def test_extractor_rejects_duplicate_member_names(tmp_path: Path) -> None:
    pin = gate.EXPECTED_TOOL_PINS[0]
    archive = tmp_path / "asset.zip"
    with pytest.warns(UserWarning, match="Duplicate name"):
        archive.write_bytes(
            _zip_bytes(
                [
                    (pin.archive_member, b"first"),
                    (pin.archive_member, b"second"),
                ]
            )
        )

    with pytest.raises(gate.GateError, match="duplicate") as error:
        gate.extract_exact_executable(pin, archive, tmp_path / "tool" / pin.archive_member)

    assert error.value.code == "archive-duplicate"


def test_extractor_rejects_symlink_members(tmp_path: Path) -> None:
    pin = gate.EXPECTED_TOOL_PINS[0]
    symlink = zipfile.ZipInfo("link")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    archive = tmp_path / "asset.zip"
    archive.write_bytes(
        _zip_bytes(
            [
                (pin.archive_member, b"native executable"),
                (symlink, b"outside"),
            ]
        )
    )

    with pytest.raises(gate.GateError, match="link or reparse") as error:
        gate.extract_exact_executable(pin, archive, tmp_path / "tool" / pin.archive_member)

    assert error.value.code == "archive-link"


@pytest.mark.parametrize(
    ("pin", "output"),
    [
        (gate.EXPECTED_TOOL_PINS[0], b"1.7.12\ninstalled by release page\n"),
        (gate.EXPECTED_TOOL_PINS[1], b"ShellCheck\nversion: 0.11.0\nlicense: GPLv3\n"),
        (gate.EXPECTED_TOOL_PINS[2], b"8.30.1\n"),
    ],
)
def test_exact_native_version_output_is_accepted(pin: gate.ToolPin, output: bytes) -> None:
    gate.validate_tool_version(pin, _completed(output))


@pytest.mark.parametrize(
    ("pin", "output"),
    [
        (gate.EXPECTED_TOOL_PINS[0], b"1.7.13\n"),
        (gate.EXPECTED_TOOL_PINS[1], b"version: 0.10.0\n"),
        (gate.EXPECTED_TOOL_PINS[2], b"gitleaks version 8.30.1\n"),
    ],
)
def test_changed_or_ambiguous_native_version_output_is_rejected(
    pin: gate.ToolPin,
    output: bytes,
) -> None:
    with pytest.raises(gate.GateError, match="exact version") as error:
        gate.validate_tool_version(pin, _completed(output))

    assert error.value.code == "tool-version"


def test_system_git_uses_64_bit_hklm_install_path_and_ignores_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_root = tmp_path / "trusted-git"
    trusted_git = install_root / "cmd" / "git.exe"
    trusted_git.parent.mkdir(parents=True)
    trusted_git.write_bytes(b"trusted Git for Windows")
    attacker_directory = tmp_path / "attacker"
    attacker_directory.mkdir()
    (attacker_directory / "git.exe").write_bytes(b"PATH impostor")
    monkeypatch.setenv("PATH", str(attacker_directory))
    monkeypatch.setattr(
        gate.shutil,
        "which",
        lambda _name: pytest.fail("ambient PATH must not be consulted for Git"),
    )
    _replace_git_registry(monkeypatch, str(install_root))

    assert gate.locate_system_git() == trusted_git.resolve(strict=True)


def test_system_git_rejects_missing_registry_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del tmp_path
    registry_key = _RegistryKey()
    monkeypatch.setattr(gate.winreg, "OpenKey", lambda *_args, **_kwargs: registry_key)

    def missing_value(_key: object, _name: str) -> tuple[object, int]:
        raise FileNotFoundError

    monkeypatch.setattr(gate.winreg, "QueryValueEx", missing_value)

    with pytest.raises(gate.GateError, match="not registered") as error:
        gate.locate_system_git()

    assert error.value.code == "git-registry"


@pytest.mark.parametrize(
    ("install_path", "value_type"),
    [
        (None, gate.winreg.REG_SZ),
        ("", gate.winreg.REG_SZ),
        (" relative-git ", gate.winreg.REG_SZ),
        ("relative-git", gate.winreg.REG_SZ),
        (r"C:\Program Files\Git", gate.winreg.REG_BINARY),
    ],
)
def test_system_git_rejects_invalid_registry_value(
    monkeypatch: pytest.MonkeyPatch,
    install_path: object,
    value_type: int,
) -> None:
    _replace_git_registry(monkeypatch, install_path, value_type)

    with pytest.raises(gate.GateError, match="InstallPath") as error:
        gate.locate_system_git()

    assert error.value.code == "git-registry"


def test_system_git_rejects_executable_resolved_outside_install_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_root = tmp_path / "registered-git"
    configured_git = install_root / "cmd" / "git.exe"
    configured_git.parent.mkdir(parents=True)
    configured_git.write_bytes(b"reparse placeholder")
    external_git = tmp_path / "outside" / "git.exe"
    external_git.parent.mkdir()
    external_git.write_bytes(b"external executable")
    _replace_git_registry(monkeypatch, str(install_root))

    real_resolve = gate.Path.resolve
    external_resolved = real_resolve(external_git, strict=True)

    def escape_registered_path(path: Path, strict: bool = False) -> Path:
        if path == configured_git:
            return external_resolved
        return real_resolve(path, strict=strict)

    monkeypatch.setattr(gate.Path, "resolve", escape_registered_path)

    with pytest.raises(gate.GateError, match="contained regular") as error:
        gate.locate_system_git()

    assert error.value.code == "git-path"


def test_system_git_rejects_non_regular_registered_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_root = tmp_path / "registered-git"
    (install_root / "cmd" / "git.exe").mkdir(parents=True)
    _replace_git_registry(monkeypatch, str(install_root))

    with pytest.raises(gate.GateError, match="contained regular") as error:
        gate.locate_system_git()

    assert error.value.code == "git-path"


def test_exact_git_for_windows_version_line_is_accepted() -> None:
    gate.validate_git_for_windows_version(_completed(b"git version 2.51.0.windows.1\r\n"))


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (b"git version 2.51.0\n", b""),
        (b"git version 2.51.0.windows.1\nsecond line\n", b""),
        (b"git version 2.51.0.windows.1\n", b"unexpected warning\n"),
    ],
)
def test_false_or_multiline_git_version_is_rejected(stdout: bytes, stderr: bytes) -> None:
    with pytest.raises(gate.GateError, match="strict Git-for-Windows") as error:
        gate.validate_git_for_windows_version(_completed(stdout, stderr))

    assert error.value.code == "git-version"


def test_commands_bind_shellcheck_pyflakes_worktree_and_detached_head(tmp_path: Path) -> None:
    actionlint = tmp_path / "actionlint.exe"
    shellcheck = tmp_path / "shellcheck.exe"
    pyflakes = tmp_path / "pyflakes.exe"
    gitleaks = tmp_path / "gitleaks.exe"
    zizmor = tmp_path / "zizmor.exe"
    config = tmp_path / "actionlint.yaml"
    workflow = tmp_path / "ci.yml"
    mirror = tmp_path / "mirror"

    assert gate.actionlint_command(actionlint, shellcheck, pyflakes, config, workflow) == (
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
    assert gate.gitleaks_worktree_command(gitleaks, mirror)[1:] == (
        "dir",
        "--no-banner",
        "--no-color",
        "--redact=100",
        "--timeout=300",
        str(mirror),
    )
    history = gate.gitleaks_history_command(gitleaks, tmp_path)
    assert "--log-opts=--all HEAD --full-history -m" in history
    assert history[-1] == str(tmp_path)
    assert gate.zizmor_commands(zizmor, workflow) == (
        (
            str(zizmor),
            "--offline",
            "--strict-collection",
            "--no-config",
            "--no-ignores",
            "--persona=regular",
            str(workflow),
        ),
        (
            str(zizmor),
            "--offline",
            "--strict-collection",
            "--no-config",
            "--no-ignores",
            "--persona=pedantic",
            str(workflow),
        ),
    )


def test_locked_zizmor_is_resolved_only_from_the_active_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    executable = scripts / "zizmor.exe"
    executable.write_bytes(b"locked executable")
    monkeypatch.setattr(gate.importlib.metadata, "version", lambda _name: gate.ZIZMOR_VERSION)
    monkeypatch.setattr(gate.sysconfig, "get_path", lambda _name: str(scripts))

    assert gate.locate_locked_zizmor() == executable.resolve(strict=True)


def test_locked_zizmor_rejects_missing_wrong_or_unresolved_installations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_name: str) -> str:
        raise gate.importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(gate.importlib.metadata, "version", missing)
    with pytest.raises(gate.GateError) as missing_error:
        gate.locate_locked_zizmor()
    assert missing_error.value.code == "zizmor-missing"

    monkeypatch.setattr(gate.importlib.metadata, "version", lambda _name: "1.30.1")
    with pytest.raises(gate.GateError) as version_error:
        gate.locate_locked_zizmor()
    assert version_error.value.code == "zizmor-version"

    monkeypatch.setattr(gate.importlib.metadata, "version", lambda _name: gate.ZIZMOR_VERSION)
    monkeypatch.setattr(gate.sysconfig, "get_path", lambda _name: str(tmp_path / "missing"))
    with pytest.raises(gate.GateError) as path_error:
        gate.locate_locked_zizmor()
    assert path_error.value.code == "zizmor-path"


@pytest.mark.parametrize("persona", ["regular", "pedantic"])
def test_nonzero_zizmor_persona_is_a_fatal_gate_error(tmp_path: Path, persona: str) -> None:
    with pytest.raises(gate.GateError) as error:
        gate._run_command(
            (sys.executable, "-c", "raise SystemExit(9)"),
            purpose=f"Zizmor {persona} offline workflow audit",
            cwd=tmp_path,
            environment=os.environ,
        )
    assert error.value.code == "command-nonzero"


def test_complete_gate_always_runs_both_zizmor_personas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: CI\n", encoding="utf-8")
    (repository / "scripts").mkdir()

    git = tmp_path / "git.exe"
    pyflakes = tmp_path / "pyflakes.exe"
    zizmor = tmp_path / "zizmor.exe"
    for executable in (git, pyflakes, zizmor):
        executable.write_bytes(b"executable")

    calls: list[tuple[tuple[str, ...], str]] = []

    def fake_extract(
        pin: gate.ToolPin,
        archive: Path,
        destination: Path,
    ) -> None:
        del pin, archive
        destination.parent.mkdir(parents=True, exist_ok=False)
        destination.write_bytes(b"native executable")

    def fake_run(
        command: gate.Command,
        *,
        purpose: str,
        cwd: Path,
        environment: gate.Environment,
        timeout: int = gate.COMMAND_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess[bytes]:
        del cwd, environment, timeout
        calls.append((command, purpose))
        if purpose == "verify Git executable":
            return _completed(b"git version 2.51.0.windows.1\n")
        return _completed(b"")

    def fake_mirror(
        source: Path,
        destination: Path,
        paths: tuple[PurePosixPath, ...],
    ) -> None:
        del source, paths
        destination.mkdir()

    monkeypatch.setattr(gate, "_assert_target_runtime", lambda: None)
    monkeypatch.setattr(gate, "load_manifest", lambda _path: gate.EXPECTED_TOOL_PINS)
    monkeypatch.setattr(gate, "locate_system_git", lambda: git)
    monkeypatch.setattr(gate, "locate_locked_pyflakes", lambda: pyflakes)
    monkeypatch.setattr(gate, "locate_locked_zizmor", lambda: zizmor)
    monkeypatch.setattr(
        gate,
        "download_verified_archive",
        lambda _pin, destination: destination.write_bytes(b"archive"),
    )
    monkeypatch.setattr(gate, "extract_exact_executable", fake_extract)
    monkeypatch.setattr(gate, "sanitized_environment", lambda **_kwargs: {})
    monkeypatch.setattr(gate, "_run_command", fake_run)
    monkeypatch.setattr(gate, "validate_tool_version", lambda _pin, _result: None)
    monkeypatch.setattr(gate, "assert_clean_complete_checkout", lambda *_args: None)
    monkeypatch.setattr(gate, "assert_no_local_gitleaks_policy", lambda _path: None)
    monkeypatch.setattr(gate, "tracked_paths", lambda *_args: ())
    monkeypatch.setattr(gate, "create_tracked_mirror", fake_mirror)

    gate.run_gate(repository)

    assert ((str(git), "--version"), "verify Git executable") in calls
    zizmor_calls = [(command, purpose) for command, purpose in calls if command[0] == str(zizmor)]
    assert zizmor_calls == [
        (
            (
                str(zizmor),
                "--offline",
                "--strict-collection",
                "--no-config",
                "--no-ignores",
                "--persona=regular",
                str(workflow),
            ),
            "Zizmor regular offline workflow audit",
        ),
        (
            (
                str(zizmor),
                "--offline",
                "--strict-collection",
                "--no-config",
                "--no-ignores",
                "--persona=pedantic",
                str(workflow),
            ),
            "Zizmor pedantic offline workflow audit",
        ),
    ]


def test_sanitized_environment_drops_caller_tokens_and_tool_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("GITLEAKS_CONFIG_TOML", "allow everything")
    monkeypatch.setenv("SHELLCHECK_OPTS", "--exclude=all")
    monkeypatch.setenv("PYFLAKES", "attacker.exe")
    executable = Path(sys.executable).resolve()
    trusted_git = tmp_path / "trusted-git" / "cmd" / "git.exe"

    environment = gate.sanitized_environment(
        temp_root=tmp_path,
        git=trusted_git,
        pyflakes=executable,
        zizmor=executable,
        tools={"actionlint": executable, "shellcheck": executable, "gitleaks": executable},
    )

    assert "GITHUB_TOKEN" not in environment
    assert "GITLEAKS_CONFIG_TOML" not in environment
    assert environment["SHELLCHECK_OPTS"] == "--norc"
    assert "PYFLAKES" not in environment
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_CONFIG_GLOBAL"] == os.devnull
    assert environment["PATH"].split(os.pathsep)[0] == str(trusted_git.parent)
    assert environment["HOME"].startswith(str(tmp_path))


def test_checkout_preflight_supports_detached_head_but_requires_full_clean_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git_output(
        git: Path,
        arguments: tuple[str, ...],
        *,
        repository: Path,
        environment: gate.Environment,
        purpose: str,
    ) -> bytes:
        del git, environment, purpose
        assert repository == tmp_path
        calls.append(arguments)
        if arguments == ("rev-parse", "--show-toplevel"):
            return f"{tmp_path}\n".encode()
        if arguments == ("rev-parse", "--is-shallow-repository"):
            return b"false\n"
        if arguments == ("status", "--porcelain=v1", "-z", "--untracked-files=all"):
            return b""
        raise AssertionError(arguments)

    monkeypatch.setattr(gate, "_git_output", fake_git_output)
    gate.assert_clean_complete_checkout(Path("git.exe"), tmp_path, {})

    assert not any("symbolic-ref" in call for call in calls)
    assert ("status", "--porcelain=v1", "-z", "--untracked-files=all") in calls


def test_git_inventory_is_nul_delimited_utf8_and_rejects_local_gitleaks_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    regular = b"100644 " + b"a" * 40 + b" 0\tsrc/caf\xc3\xa9.py\x00"

    monkeypatch.setattr(gate, "_git_output", lambda *_args, **_kwargs: regular)
    assert gate.tracked_paths(Path("git.exe"), tmp_path, {}) == (
        PurePosixPath("src/caf\N{LATIN SMALL LETTER E WITH ACUTE}.py"),
    )

    policy = b"100644 " + b"b" * 40 + b" 0\t.gitleaksignore\x00"
    monkeypatch.setattr(gate, "_git_output", lambda *_args, **_kwargs: policy)
    with pytest.raises(gate.GateError, match="suppression") as error:
        gate.tracked_paths(Path("git.exe"), tmp_path, {})
    assert error.value.code == "gitleaks-policy"


@pytest.mark.parametrize("policy_name", [".gitleaks.toml", ".gitleaksignore"])
def test_ignored_or_untracked_root_gitleaks_policy_is_rejected(
    tmp_path: Path,
    policy_name: str,
) -> None:
    (tmp_path / policy_name).write_text("ignored by Git", encoding="utf-8")

    with pytest.raises(gate.GateError, match="suppression or configuration") as error:
        gate.assert_no_local_gitleaks_policy(tmp_path)

    assert error.value.code == "gitleaks-policy"


def test_absent_root_gitleaks_policy_is_accepted(tmp_path: Path) -> None:
    gate.assert_no_local_gitleaks_policy(tmp_path)


def test_release_group_and_workflow_invoke_the_native_gate_from_full_history() -> None:
    project = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pyflakes==3.4.0" in project["dependency-groups"]["release"]
    assert f"zizmor=={gate.ZIZMOR_VERSION}" in project["dependency-groups"]["release"]
    lock = tomllib.loads((_PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_pyflakes = [package for package in lock["package"] if package["name"] == "pyflakes"]
    assert len(locked_pyflakes) == 1
    assert locked_pyflakes[0]["version"] == "3.4.0"

    workflow = (_PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    security = workflow.split("  security:\n", 1)[1].split("\n  tests:\n", 1)[0]
    assert "fetch-depth: 0" in security
    assert "uv sync --locked --only-group release --no-install-project" in security
    assert "uv run --no-sync python -I scripts/release_native_gate.py" in security
