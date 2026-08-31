from __future__ import annotations

import copy
import json
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scripts import semgrep_release_gate as gate

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


TEST_RULE_IDS = ("python.rule.alpha", "python.rule.beta")
TEST_RULE_CONTRACT = gate.RuleContract(
    count=len(TEST_RULE_IDS),
    ids_sha256=gate._sequence_digest(TEST_RULE_IDS),
)

TEST_SHARD_RULES: tuple[tuple[dict[str, object], ...], ...] = (
    (
        {
            "id": "definition.alpha",
            "languages": ["python"],
            "message": "alpha",
            "pattern": "eval(...) ",
            "severity": "WARNING",
        },
    ),
    (
        {
            "id": "definition.beta",
            "languages": ["python"],
            "message": "beta",
            "pattern": "exec(...) ",
            "severity": "ERROR",
        },
    ),
    (),
    (),
)


def _shard_bytes(
    shard_rules: Sequence[Sequence[dict[str, object]]] = TEST_SHARD_RULES,
) -> dict[int, bytes]:
    return {
        index: gate._canonical_json({"rules": list(rules)}).encode("utf-8")
        for index, rules in enumerate(shard_rules)
    }


def _bundle_contract(
    shard_rules: Sequence[Sequence[dict[str, object]]] = TEST_SHARD_RULES,
) -> gate.BundleContract:
    raw_shards = _shard_bytes(shard_rules)
    sortable: list[tuple[str, str, dict[str, object]]] = []
    for rules in shard_rules:
        for rule in rules:
            rule_id = rule.get("id")
            assert isinstance(rule_id, str)
            sortable.append((rule_id, gate._canonical_json(rule), rule))
    sortable.sort(key=lambda item: (item[0], item[1]))
    canonical_rules = tuple(item[1] for item in sortable)
    bundle = gate._canonical_json({"rules": [item[2] for item in sortable]}).encode("utf-8")
    return gate.BundleContract(
        shards=tuple(
            gate.ShardContract(index, len(raw_shards[index]), len(rules))
            for index, rules in enumerate(shard_rules)
        ),
        definition_count=len(sortable),
        definitions_sha256=gate._sequence_digest(canonical_rules),
        bundle_size=len(bundle),
        bundle_sha256=gate._sha256_bytes(bundle),
    )


TEST_BUNDLE_CONTRACT = _bundle_contract()
TEST_SOURCE_LINE = "    assert True"
TEST_SOURCE = f"def test_a():\n{TEST_SOURCE_LINE}"
TEST_FINDING = gate.FindingSignature(
    path="tests/test_a.py",
    check_id="python.test.assertion",
    start_line=2,
    start_col=5,
    end_line=2,
    end_col=16,
    lines_sha256=gate._sha256_bytes(TEST_SOURCE_LINE.encode("utf-8")),
    file_sha256=gate._sha256_bytes(TEST_SOURCE.encode("utf-8")),
)
_MISSING = object()


def _result(
    *,
    path: str = TEST_FINDING.path,
    check_id: str = TEST_FINDING.check_id,
    start_line: int = TEST_FINDING.start_line,
    start_col: int = TEST_FINDING.start_col,
    end_line: int = TEST_FINDING.end_line,
    end_col: int = TEST_FINDING.end_col,
    is_ignored: object = _MISSING,
) -> dict[str, object]:
    extra: dict[str, object] = {}
    if is_ignored is not _MISSING:
        extra["is_ignored"] = is_ignored
    return {
        "check_id": check_id,
        "path": path,
        "start": {"line": start_line, "col": start_col},
        "end": {"line": end_line, "col": end_col},
        "extra": extra,
    }


def _payload(
    scanned: list[str],
    *,
    results: list[object] | None = None,
    rules: list[object] | None = None,
    paths_extra: dict[str, object] | None = None,
    **overrides: object,
) -> dict[str, object]:
    paths: dict[str, object] = {"scanned": scanned}
    if paths_extra:
        paths.update(paths_extra)
    payload: dict[str, object] = {
        "version": gate.SEMGREP_VERSION,
        "engine_requested": gate.SEMGREP_ENGINE,
        "results": [_result()] if results is None else results,
        "errors": [],
        "skipped_rules": [],
        "time": {
            "fixpoint_timeouts": [],
            "rules": list(reversed(TEST_RULE_IDS)) if rules is None else rules,
        },
        "paths": paths,
    }
    payload.update(overrides)
    return payload


def _payload_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


@dataclass
class FakeRunner:
    repository: Path
    inventory: list[str]
    payload: dict[str, object]
    bundle_returncode: int = 1
    bundle_stderr: bytes = b""
    dump_returncode: int = 0
    dump_stderr: bytes = b""
    final_inventory: list[str] | None = None
    shards: dict[int, bytes] = field(default_factory=_shard_bytes)
    extra_shards: dict[str, bytes] = field(default_factory=dict)
    on_dump: Callable[[Path, Mapping[str, str]], None] | None = None
    on_scan: Callable[[Path, Mapping[str, str], gate.Command], None] | None = None
    calls: list[tuple[gate.Command, Path, dict[str, str]]] = field(default_factory=list)
    inventory_calls: int = 0

    def __call__(
        self,
        command: gate.Command,
        cwd: Path,
        environment: gate.Environment,
    ) -> subprocess.CompletedProcess[bytes]:
        captured_environment = dict(environment)
        self.calls.append((command, cwd, captured_environment))
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, f"{self.repository}\n".encode(), b"")
        if "--unmerged" in command:
            return subprocess.CompletedProcess(command, 0, b"", b"")
        if "ls-files" in command:
            self.inventory_calls += 1
            inventory = (
                self.final_inventory
                if self.inventory_calls > 1 and self.final_inventory is not None
                else self.inventory
            )
            stdout = b"\x00".join(path.encode() for path in inventory) + b"\x00"
            return subprocess.CompletedProcess(command, 0, stdout, b"")
        if "--dump-command-for-core" in command:
            xdg_root = Path(captured_environment["XDG_CONFIG_HOME"])
            rules_directory = xdg_root / ".semgrep"
            rules_directory.mkdir()
            for index, content in self.shards.items():
                (rules_directory / f"semgrep_rules_{index}.json").write_bytes(content)
            for name, content in self.extra_shards.items():
                (rules_directory / name).write_bytes(content)
            if self.on_dump:
                self.on_dump(cwd, captured_environment)
            return subprocess.CompletedProcess(
                command,
                self.dump_returncode,
                b"core command",
                self.dump_stderr,
            )
        if "scan" in command:
            if self.on_scan:
                self.on_scan(cwd, captured_environment, command)
            return subprocess.CompletedProcess(
                command,
                self.bundle_returncode,
                _payload_bytes(self.payload),
                self.bundle_stderr,
            )
        raise AssertionError(f"unexpected command: {command!r}")


@dataclass(frozen=True)
class Project:
    repository: Path
    inventory: list[str]
    targets: list[str]
    tools: dict[str, str]
    python_prefix: Path
    python_base_prefix: Path

    def finder(self, name: str) -> str | None:
        return self.tools.get(name)


@pytest.fixture
def project(tmp_path: Path) -> Project:
    repository = tmp_path / "repository"
    files = {
        ".semgrepignore": b"tests/e2e_projects/\n",
        "src/package/a.py": b"value = b'\\x00\\xff'\n",
        "tests/test_a.py": b"def test_a():\r\n    assert True\r\n",
        "tests/e2e_projects/vendor.py": b"exec(input())\n",
        "scripts/helper.py": b"print('helper')\n",
    }
    for relative_path, content in files.items():
        path = repository.joinpath(*relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    tools_directory = tmp_path / "tools"
    tools_directory.mkdir()
    python_prefix = repository / ".venv"
    scripts_directory = python_prefix / ("Scripts" if os.name == "nt" else "bin")
    scripts_directory.mkdir(parents=True)
    (python_prefix / "pyvenv.cfg").write_text("home = controlled\n")
    python_base_prefix = tmp_path / "base-python"
    python_base_prefix.mkdir()
    suffix = ".exe" if os.name == "nt" else ""
    tools: dict[str, str] = {}
    git_executable = tools_directory / f"git{suffix}"
    git_executable.write_bytes(b"controlled git executable")
    tools["git"] = str(git_executable)
    semgrep_executable = scripts_directory / f"semgrep{suffix}"
    semgrep_executable.write_bytes(b"controlled semgrep executable")
    tools["semgrep"] = str(semgrep_executable)
    inventory = sorted(files)
    targets = sorted(
        path
        for path in inventory
        if path != gate.SEMGREP_IGNORE_FILE and not gate._is_policy_skip(path)
    )
    return Project(
        repository,
        inventory,
        targets,
        tools,
        python_prefix,
        python_base_prefix,
    )


def _run(
    project: Project,
    runner: FakeRunner,
    *,
    bundle_contract: gate.BundleContract = TEST_BUNDLE_CONTRACT,
    finding_allowlist: Sequence[gate.FindingSignature] = (TEST_FINDING,),
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    parent_environment = (
        {
            "PATH": str(Path(project.tools["semgrep"]).parent),
            "SEMGREP_APP_TOKEN": "must-not-leak",
            "semgrep_registry_url": "must-not-leak-case-insensitively",
            "GIT_INDEX_FILE": "foreign-index",
            "git_config_count": "1",
            "GIT_CONFIG_KEY_0": "core.excludesFile",
            "GIT_CONFIG_VALUE_0": "foreign-ignore",
            "HOME": "inherited-home",
            "USERPROFILE": "inherited-profile",
            "APPDATA": "inherited-appdata",
            "LOCALAPPDATA": "inherited-localappdata",
            "nEtRc": "inherited-netrc-must-not-leak",
            "PYTHONHOME": "counterfeit-python-home",
            "pythonpath": "counterfeit-import-root",
            "tmpdir": "inherited-temp-must-not-leak",
            "UV_INDEX": "https://counterfeit.invalid/simple",
            "XDG_CONFIG_HOME": "inherited-xdg-must-not-leak",
        }
        if environment is None
        else environment
    )
    return gate.run_release_gate(
        project.repository,
        runner=runner,
        executable_finder=project.finder,
        rule_contract=TEST_RULE_CONTRACT,
        bundle_contract=bundle_contract,
        finding_allowlist=finding_allowlist,
        environment=parent_environment,
        python_prefix=project.python_prefix,
        python_base_prefix=project.python_base_prefix,
    )


def _parse(
    project: Project,
    payload: object,
    *,
    allowlist: Sequence[gate.FindingSignature] = (TEST_FINDING,),
    targets: Sequence[str] | None = None,
    rule_contract: gate.RuleContract = TEST_RULE_CONTRACT,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[gate.FindingSignature, ...]]:
    return gate._parse_semgrep_json(
        _payload_bytes(payload),
        project.targets if targets is None else targets,
        rule_contract,
        project.repository,
        allowlist,
    )


def test_production_contracts_and_twenty_findings_are_fully_pinned() -> None:
    assert gate.SEMGREP_VERSION == "1.175.0"
    assert (
        gate.RuleContract(
            count=342,
            ids_sha256="90e5e07621bf32da358a4f056b15c1a14f48b8929a6a03099108fd5b12c198f6",
        )
        == gate.DEFAULT_RULE_CONTRACT
    )
    assert (
        gate.BundleContract(
            shards=(
                gate.ShardContract(0, 548_219, 268),
                gate.ShardContract(1, 548_246, 268),
                gate.ShardContract(2, 548_284, 269),
                gate.ShardContract(3, 548_223, 269),
            ),
            definition_count=1_074,
            definitions_sha256="b6e589b3bdcdf6eb2086765c0cdb3b128bda6d9b26e42cd36852e093cd1d601e",
            bundle_size=2_192_939,
            bundle_sha256="76b5a021560070925e9b86f93d2e61153b72ab6a7e306c0d49e1677bb07cbce5",
        )
        == gate.DEFAULT_BUNDLE_CONTRACT
    )
    assert len(gate.DEFAULT_FINDING_ALLOWLIST) == 20
    assert len(set(gate.DEFAULT_FINDING_ALLOWLIST)) == 20
    assert gate.DEFAULT_FINDING_ALLOWLIST[0].start_line == 74
    assert gate.DEFAULT_FINDING_ALLOWLIST[-1].lines_sha256 == (
        "5645ddad68cc2f6be58271d12732f06c354fcc0e5df1e796ef3f18e847d3897c"
    )


def test_success_uses_remote_dump_then_exact_offline_local_bundle(project: Project) -> None:
    observed: dict[str, object] = {}

    def inspect_scan(mirror: Path, environment: Mapping[str, str], command: gate.Command) -> None:
        bundle = Path(command[command.index("--config") + 1])
        observed["mirror"] = mirror
        observed["bundle_path"] = bundle
        observed["bundle"] = bundle.read_bytes()
        observed["source_bytes"] = {
            path: mirror.joinpath(*path.split("/")).read_bytes() for path in project.inventory
        }
        observed["offline_environment"] = dict(environment)

    runner = FakeRunner(
        project.repository,
        project.inventory,
        _payload(project.targets),
        on_scan=inspect_scan,
    )
    evidence = _run(project, runner)

    assert evidence["status"] == "pass"
    assert evidence["targets"] == {
        "count": 3,
        "paths": project.targets,
        "sha256": gate._sequence_digest(project.targets),
    }
    scanner = evidence["scanner"]
    assert isinstance(scanner, dict)
    assert scanner["bundle"] == {
        "bytes": TEST_BUNDLE_CONTRACT.bundle_size,
        "definition_count": 2,
        "definitions_sha256": TEST_BUNDLE_CONTRACT.definitions_sha256,
        "sha256": TEST_BUNDLE_CONTRACT.bundle_sha256,
        "shard_count": 4,
    }
    assert scanner["allowed_finding_count"] == 1
    assert scanner["finding_count"] == 1
    assert scanner["unexpected_finding_count"] == 0
    assert scanner["inline_suppressions_disabled"] is True
    assert scanner["inline_suppression_field_contract"] == "extra.is_ignored absent"
    assert scanner["rule_count"] == 2
    assert scanner["rule_ids_sha256"] == TEST_RULE_CONTRACT.ids_sha256

    semgrep_calls = [call for call in runner.calls if "scan" in call[0]]
    assert len(semgrep_calls) == 2
    dump_command, dump_cwd, dump_environment = semgrep_calls[0]
    scan_command, scan_cwd, scan_environment = semgrep_calls[1]
    assert dump_command[0] == project.tools["semgrep"]
    assert "--dump-command-for-core" in dump_command
    assert dump_command[dump_command.index("--config") + 1] == "auto"
    assert "--metrics" not in dump_command
    assert "--disable-nosem" in dump_command
    assert {key.upper() for key in dump_environment if key.upper().startswith("SEMGREP_")} == {
        "SEMGREP_SETTINGS_FILE"
    }
    assert all(not key.upper().startswith("UV_") for key in dump_environment)
    assert all(not key.upper().startswith("GIT_") for key in dump_environment)
    assert dump_environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert dump_environment["PYTHONNOUSERSITE"] == "1"
    assert dump_environment["PYTHONSAFEPATH"] == "1"
    assert "PYTHONHOME" not in dump_environment
    assert "pythonpath" not in dump_environment
    assert all(key.upper() != "NETRC" for key in dump_environment)
    isolated_xdg = Path(dump_environment["XDG_CONFIG_HOME"])
    isolation_root = isolated_xdg.parent
    assert Path(dump_environment["SEMGREP_SETTINGS_FILE"]) == (
        isolated_xdg / ".semgrep" / "settings.yml"
    )
    assert Path(dump_environment["HOME"]) == isolation_root / "home"
    assert Path(dump_environment["USERPROFILE"]) == isolation_root / "home"
    assert Path(dump_environment["APPDATA"]) == isolation_root / "appdata"
    assert Path(dump_environment["LOCALAPPDATA"]) == isolation_root / "localappdata"
    assert Path(dump_environment["XDG_CACHE_HOME"]) == isolation_root / "cache"
    assert Path(dump_environment["TEMP"]) == isolation_root / "temp"
    assert Path(dump_environment["TMP"]) == isolation_root / "temp"
    assert Path(dump_environment["TMPDIR"]) == isolation_root / "temp"
    assert Path(dump_environment["XDG_CONFIG_HOME"]) != Path("inherited-xdg-must-not-leak")

    assert scan_command[0] == project.tools["semgrep"]
    assert "auto" not in scan_command
    assert "--dump-command-for-core" not in scan_command
    assert "--no-rewrite-rule-ids" in scan_command
    assert scan_command[scan_command.index("--metrics") + 1] == "off"
    bundle_path = Path(scan_command[scan_command.index("--config") + 1])
    assert bundle_path.is_absolute()
    assert not bundle_path.is_relative_to(scan_cwd)
    assert dump_cwd == scan_cwd
    assert scan_environment["XDG_CONFIG_HOME"] == dump_environment["XDG_CONFIG_HOME"]
    assert scan_environment["SEMGREP_SEND_METRICS"] == "off"
    assert scan_environment["UV_OFFLINE"] == "1"
    assert "SEMGREP_APP_TOKEN" not in scan_environment
    for name in (
        "SEMGREP_APP_URL",
        "SEMGREP_FAIL_OPEN_URL",
        "SEMGREP_URL",
        "SEMGREP_VERSION_CHECK_URL",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        assert scan_environment[name] == "http://127.0.0.1:9"
    assert (
        observed["bundle"]
        == gate._canonical_json(
            {"rules": [TEST_SHARD_RULES[0][0], TEST_SHARD_RULES[1][0]]}
        ).encode()
    )
    assert observed["source_bytes"] == {
        path: project.repository.joinpath(*path.split("/")).read_bytes()
        for path in project.inventory
    }
    assert not bundle_path.exists()
    assert not Path(dump_environment["XDG_CONFIG_HOME"]).exists()
    git_calls = [call for call in runner.calls if call not in semgrep_calls]
    assert git_calls
    for _command, _cwd, git_environment in git_calls:
        assert all(not key.upper().startswith("GIT_") for key in git_environment)


def test_success_evidence_is_canonical_and_ignores_timing(project: Project) -> None:
    first_payload = _payload(project.targets)
    first_time = first_payload["time"]
    assert isinstance(first_time, dict)
    first_time["total_time"] = 999.0
    second_payload = _payload(project.targets)
    second_time = second_payload["time"]
    assert isinstance(second_time, dict)
    second_time["total_time"] = 0.001
    first = _run(project, FakeRunner(project.repository, project.inventory, first_payload))
    second = _run(project, FakeRunner(project.repository, project.inventory, second_payload))
    assert first == second
    canonical = gate._canonical_json(first)
    assert canonical == gate._canonical_json(json.loads(canonical))
    assert str(project.repository) not in canonical


def _control_with_shards(
    tmp_path: Path, shards: Mapping[int, bytes], extras: Mapping[str, bytes] | None = None
) -> tuple[Path, Path]:
    control = tmp_path / "control"
    rules_directory = control / "xdg" / ".semgrep"
    rules_directory.mkdir(parents=True)
    for index, content in shards.items():
        (rules_directory / f"semgrep_rules_{index}.json").write_bytes(content)
    for name, content in (extras or {}).items():
        (rules_directory / name).write_bytes(content)
    return control, control / "xdg"


def test_bundle_loader_canonicalizes_four_shards_and_writes_exact_bundle(tmp_path: Path) -> None:
    control, xdg = _control_with_shards(tmp_path, _shard_bytes())
    bundle_path, bundle_bytes, records = gate._load_rule_bundle(control, xdg, TEST_BUNDLE_CONTRACT)
    assert len(records) == 5
    assert bundle_path.read_bytes() == bundle_bytes
    assert len(bundle_bytes) == TEST_BUNDLE_CONTRACT.bundle_size
    assert gate._sha256_bytes(bundle_bytes) == TEST_BUNDLE_CONTRACT.bundle_sha256
    gate._verify_artifacts(control, records)


@pytest.mark.parametrize("missing_index", range(4))
def test_bundle_loader_requires_every_exact_shard(tmp_path: Path, missing_index: int) -> None:
    shards = _shard_bytes()
    del shards[missing_index]
    control, xdg = _control_with_shards(tmp_path, shards)
    with pytest.raises(gate.GateError) as error:
        gate._load_rule_bundle(control, xdg, TEST_BUNDLE_CONTRACT)
    assert error.value.code == "semgrep-shards"


def test_bundle_loader_rejects_extra_shard(tmp_path: Path) -> None:
    control, xdg = _control_with_shards(
        tmp_path, _shard_bytes(), {"semgrep_rules_4.json": b'{"rules":[]}'}
    )
    with pytest.raises(gate.GateError, match="Expected rule shards"):
        gate._load_rule_bundle(control, xdg, TEST_BUNDLE_CONTRACT)


@pytest.mark.parametrize(
    "invalid_payload",
    [
        [],
        {"rules": [], "metadata": {}},
        {"rules": "not-a-list"},
        {"rules": ["not-an-object"]},
        {"rules": [{"message": "missing id"}]},
    ],
)
def test_bundle_loader_rejects_invalid_rule_shapes(tmp_path: Path, invalid_payload: object) -> None:
    shards = _shard_bytes()
    shards[0] = _payload_bytes(invalid_payload)
    contract = replace(
        TEST_BUNDLE_CONTRACT,
        shards=(
            replace(TEST_BUNDLE_CONTRACT.shards[0], size=len(shards[0])),
            *TEST_BUNDLE_CONTRACT.shards[1:],
        ),
    )
    control, xdg = _control_with_shards(tmp_path, shards)
    with pytest.raises(gate.GateError) as error:
        gate._load_rule_bundle(control, xdg, contract)
    assert error.value.code == "semgrep-shards"


def test_bundle_loader_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    duplicate = copy.deepcopy(TEST_SHARD_RULES)
    duplicate[1][0]["id"] = "definition.alpha"
    shards = _shard_bytes(duplicate)
    contract = _bundle_contract(duplicate)
    control, xdg = _control_with_shards(tmp_path, shards)
    with pytest.raises(gate.GateError, match="Duplicate rule"):
        gate._load_rule_bundle(control, xdg, contract)


def test_bundle_loader_rejects_raw_size_definition_and_content_drift(tmp_path: Path) -> None:
    changed = copy.deepcopy(TEST_SHARD_RULES)
    changed[0][0]["message"] = "drift"
    control, xdg = _control_with_shards(tmp_path, _shard_bytes(changed))
    with pytest.raises(gate.GateError) as raw_error:
        gate._load_rule_bundle(control, xdg, TEST_BUNDLE_CONTRACT)
    assert raw_error.value.code in {"semgrep-shards", "semgrep-bundle"}

    control_two, xdg_two = _control_with_shards(tmp_path / "second", _shard_bytes())
    wrong_count = replace(TEST_BUNDLE_CONTRACT, definition_count=3)
    with pytest.raises(gate.GateError, match="definition-count"):
        gate._load_rule_bundle(control_two, xdg_two, wrong_count)

    control_three, xdg_three = _control_with_shards(tmp_path / "third", _shard_bytes())
    wrong_digest = replace(TEST_BUNDLE_CONTRACT, definitions_sha256="0" * 64)
    with pytest.raises(gate.GateError, match="content drift"):
        gate._load_rule_bundle(control_three, xdg_three, wrong_digest)


def test_bundle_loader_rejects_bundle_size_and_digest_drift(tmp_path: Path) -> None:
    control, xdg = _control_with_shards(tmp_path / "size", _shard_bytes())
    with pytest.raises(gate.GateError, match="size drift"):
        gate._load_rule_bundle(
            control,
            xdg,
            replace(TEST_BUNDLE_CONTRACT, bundle_size=TEST_BUNDLE_CONTRACT.bundle_size + 1),
        )
    control_two, xdg_two = _control_with_shards(tmp_path / "digest", _shard_bytes())
    with pytest.raises(gate.GateError, match="digest drift"):
        gate._load_rule_bundle(
            control_two,
            xdg_two,
            replace(TEST_BUNDLE_CONTRACT, bundle_sha256="0" * 64),
        )


def test_bundle_loader_rejects_duplicate_keys_nonfinite_and_invalid_utf8(tmp_path: Path) -> None:
    invalid_values = (
        b'{"rules":[],"rules":[]}',
        b'{"rules":[{"id":"x","value":NaN}]}',
        b"\xff",
    )
    for index, invalid in enumerate(invalid_values):
        shards = _shard_bytes()
        shards[0] = invalid
        contract = replace(
            TEST_BUNDLE_CONTRACT,
            shards=(
                replace(TEST_BUNDLE_CONTRACT.shards[0], size=len(invalid)),
                *TEST_BUNDLE_CONTRACT.shards[1:],
            ),
        )
        control, xdg = _control_with_shards(tmp_path / str(index), shards)
        with pytest.raises(gate.GateError) as error:
            gate._load_rule_bundle(control, xdg, contract)
        assert error.value.code == "semgrep-json"


def test_rule_shard_and_bundle_changes_during_local_scan_are_fatal(project: Project) -> None:
    def mutate_shard(_mirror: Path, environment: Mapping[str, str], _command: gate.Command) -> None:
        shard = Path(environment["XDG_CONFIG_HOME"]) / ".semgrep" / "semgrep_rules_0.json"
        shard.write_bytes(shard.read_bytes() + b" ")

    with pytest.raises(gate.GateError) as shard_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets),
                on_scan=mutate_shard,
            ),
        )
    assert shard_error.value.code == "toctou"

    def mutate_bundle(
        _mirror: Path, _environment: Mapping[str, str], command: gate.Command
    ) -> None:
        bundle = Path(command[command.index("--config") + 1])
        bundle.write_bytes(bundle.read_bytes() + b" ")

    with pytest.raises(gate.GateError) as bundle_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets),
                on_scan=mutate_bundle,
            ),
        )
    assert bundle_error.value.code == "toctou"


def test_locked_semgrep_executable_change_during_gate_is_fatal(project: Project) -> None:
    def mutate_executable(_mirror: Path, _environment: Mapping[str, str]) -> None:
        Path(project.tools["semgrep"]).write_bytes(b"changed executable")

    runner = FakeRunner(
        project.repository,
        project.inventory,
        _payload(project.targets),
        on_dump=mutate_executable,
    )
    with pytest.raises(gate.GateError) as error:
        _run(project, runner)
    assert error.value.code == "toctou"


def test_exact_finding_signature_accepts_rc1_and_ignores_diagnostic_extra_lines(
    project: Project,
) -> None:
    result = _result()
    extra = result["extra"]
    assert isinstance(extra, dict)
    extra["lines"] = "registry output may omit or vary this diagnostic"
    scanned, rules, findings = _parse(project, _payload(project.targets, results=[result]))
    assert scanned == tuple(project.targets)
    assert rules == tuple(sorted(TEST_RULE_IDS))
    assert findings == (TEST_FINDING,)


def test_finding_line_hash_is_stable_across_crlf_and_lf(project: Project) -> None:
    crlf = _parse(project, _payload(project.targets))[2]
    (project.repository / "tests" / "test_a.py").write_bytes(b"def test_a():\n    assert True\n")
    lf = _parse(project, _payload(project.targets))[2]
    assert crlf == lf == (TEST_FINDING,)


@pytest.mark.parametrize(
    "results",
    [
        [],
        [_result(), _result()],
        [_result(check_id="python.unexpected")],
        [_result(start_col=6)],
        [_result(end_col=15)],
        [_result(is_ignored=True)],
        [_result(is_ignored=False)],
        [_result(is_ignored=None)],
        [_result(is_ignored="wrong type")],
    ],
)
def test_missing_extra_duplicate_shifted_or_is_ignored_findings_are_fatal(
    project: Project, results: list[object]
) -> None:
    with pytest.raises(gate.GateError) as error:
        _parse(project, _payload(project.targets, results=results))
    assert error.value.code == "semgrep-findings"


def test_changed_full_source_line_invalid_utf8_and_bad_ranges_are_fatal(project: Project) -> None:
    source = project.repository / "tests" / "test_a.py"
    source.write_bytes(b"def test_a_with_changed_context():\n    assert True\n")
    with pytest.raises(gate.GateError, match="finding mismatch"):
        _parse(project, _payload(project.targets))

    source.write_bytes(b"def test_a():\n    assert False\n")
    with pytest.raises(gate.GateError, match="finding mismatch"):
        _parse(project, _payload(project.targets))

    source.write_bytes(b"def test_a():\n    \xff\n")
    with pytest.raises(gate.GateError, match="strict UTF-8"):
        _parse(project, _payload(project.targets))

    source.write_bytes(b"def test_a():\n    assert True\n")
    for result in (_result(start_line=0), _result(end_line=99), _result(start_col=99)):
        with pytest.raises(gate.GateError) as error:
            _parse(project, _payload(project.targets, results=[result]))
        assert error.value.code in {"semgrep-json", "semgrep-findings"}


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("errors", [{"message": "parse failed"}]),
        ("skipped_rules", [{"id": "skipped"}]),
        ("results", None),
    ],
)
def test_semgrep_errors_skipped_rules_and_result_shape_are_fatal(
    project: Project, field: str, bad_value: object
) -> None:
    payload = _payload(project.targets)
    payload[field] = bad_value
    with pytest.raises(gate.GateError) as error:
        _parse(project, payload)
    assert error.value.code == "semgrep-json"


def test_fixpoint_timeouts_are_fatal(project: Project) -> None:
    payload = _payload(project.targets)
    time_payload = payload["time"]
    assert isinstance(time_payload, dict)
    time_payload["fixpoint_timeouts"] = ["rule"]
    with pytest.raises(gate.GateError, match="fixpoint_timeouts"):
        _parse(project, payload)


@pytest.mark.parametrize(
    "rules",
    [
        [TEST_RULE_IDS[0]],
        [TEST_RULE_IDS[0], TEST_RULE_IDS[0]],
        [TEST_RULE_IDS[0], "wrong-rule"],
        [TEST_RULE_IDS[0], {}],
    ],
)
def test_applied_rule_count_uniqueness_shape_and_digest_are_strict(
    project: Project, rules: list[object]
) -> None:
    with pytest.raises(gate.GateError) as error:
        _parse(project, _payload(project.targets, rules=rules))
    assert error.value.code in {"semgrep-json", "semgrep-rules"}


@pytest.mark.parametrize(
    "scanned",
    [
        [],
        ["src/package/a.py"],
        ["src/package/a.py", "src/extra.py"],
        ["src/package/a.py", "src/package/a.py"],
        ["src/A.py", "src/a.py"],
        ["../src/a.py"],
        ["C:/src/a.py"],
    ],
)
def test_scanned_targets_are_exact_safe_and_collision_free(
    project: Project, scanned: list[str]
) -> None:
    with pytest.raises(gate.GateError) as error:
        _parse(project, _payload(scanned))
    assert error.value.code in {"semgrep-json", "semgrep-targets", "unsafe-path"}


def test_only_semgrepignore_and_e2e_policy_skips_are_allowed(project: Project) -> None:
    payload = _payload(
        project.targets,
        paths_extra={
            "skipped": [
                {"path": ".semgrepignore"},
                {"path": "tests/e2e_projects"},
                {"path": "tests\\e2e_projects\\vendor.py"},
            ]
        },
    )
    _parse(project, payload)
    paths = payload["paths"]
    assert isinstance(paths, dict)
    skipped = paths["skipped"]
    assert isinstance(skipped, list)
    skipped.append({"path": "src/hidden.py"})
    with pytest.raises(gate.GateError) as error:
        _parse(project, payload)
    assert error.value.code == "unexpected-policy-skip"


@pytest.mark.parametrize(
    "stdout",
    [b"not-json", b"\xff", b"[]", b"\xef\xbb\xbf{}", b'{"version":NaN}'],
)
def test_semgrep_stdout_is_one_strict_json_object(project: Project, stdout: bytes) -> None:
    with pytest.raises(gate.GateError) as error:
        gate._parse_semgrep_json(
            stdout,
            project.targets,
            TEST_RULE_CONTRACT,
            project.repository,
            (TEST_FINDING,),
        )
    assert error.value.code == "semgrep-json"


def test_rc1_requires_exact_allowlist_rc0_and_rc_greater_one_are_fatal(project: Project) -> None:
    with pytest.raises(gate.GateError) as zero_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets),
                bundle_returncode=0,
            ),
        )
    assert zero_error.value.code == "semgrep-returncode"

    with pytest.raises(gate.GateError) as missing_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets, results=[]),
                bundle_returncode=0,
            ),
        )
    assert missing_error.value.code == "semgrep-findings"

    with pytest.raises(gate.GateError) as fatal_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets),
                bundle_returncode=2,
                bundle_stderr=b"fatal scanner error",
            ),
        )
    assert fatal_error.value.code == "semgrep-failed"


@pytest.mark.parametrize(
    ("raw_path", "code"),
    [
        ("src/../outside.py", "unsafe-path"),
        ("/src/absolute.py", "unsafe-path"),
        ("C:/src/drive.py", "unsafe-path"),
        ("src\\escape.py", "unsafe-path"),
        ("src//ambiguous.py", "unsafe-path"),
        ("src/./ambiguous.py", "unsafe-path"),
        ("src/trailing. /file.py", "unsafe-path"),
        ("other/file.py", "out-of-scope-path"),
    ],
)
def test_inventory_rejects_unsafe_and_out_of_scope_paths(raw_path: str, code: str) -> None:
    with pytest.raises(gate.GateError) as error:
        gate._validate_inventory([gate.SEMGREP_IGNORE_FILE, raw_path])
    assert error.value.code == code


def test_inventory_rejects_case_unicode_collisions_and_bad_git_output() -> None:
    with pytest.raises(gate.GateError, match="collision"):
        gate._validate_inventory([".semgrepignore", "src/A.py", "src/a.py"])
    with pytest.raises(gate.GateError, match="collision"):
        gate._validate_inventory(
            [
                ".semgrepignore",
                "src/caf\N{LATIN SMALL LETTER E WITH ACUTE}.py",
                "src/cafe\N{COMBINING ACUTE ACCENT}.py",
            ]
        )
    with pytest.raises(gate.GateError, match="final delimiter"):
        gate._decode_nul_paths(b".semgrepignore")
    with pytest.raises(gate.GateError, match="strict UTF-8"):
        gate._decode_nul_paths(b".semgrepignore\x00src/\xff.py\x00")


def test_source_mirror_and_inventory_toctou_are_fatal(project: Project) -> None:
    def mutate_source(
        _mirror: Path, _environment: Mapping[str, str], _command: gate.Command
    ) -> None:
        (project.repository / "src" / "package" / "a.py").write_bytes(b"changed\n")

    with pytest.raises(gate.GateError) as source_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets),
                on_scan=mutate_source,
            ),
        )
    assert source_error.value.code == "toctou"

    def mutate_mirror(
        mirror: Path, _environment: Mapping[str, str], _command: gate.Command
    ) -> None:
        (mirror / "src" / "package" / "a.py").write_bytes(b"changed\n")

    with pytest.raises(gate.GateError) as mirror_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets),
                on_scan=mutate_mirror,
            ),
        )
    assert mirror_error.value.code == "toctou"

    with pytest.raises(gate.GateError) as inventory_error:
        _run(
            project,
            FakeRunner(
                project.repository,
                project.inventory,
                _payload(project.targets),
                final_inventory=[*project.inventory, "src/new.py"],
            ),
        )
    assert inventory_error.value.code == "toctou"


def test_symlink_and_reparse_sources_are_rejected(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = project.repository / "src" / "package" / "a.py"
    external = tmp_path / "external.py"
    external.write_text("external = True\n")
    source.unlink()
    try:
        source.symlink_to(external)
    except OSError:
        source.write_bytes(b"placeholder\n")
        regular_stat = source.lstat()
        values = list(regular_stat)
        values[0] = stat.S_IFLNK | 0o777
        symlink_stat = os.stat_result(values)
        original_lstat = Path.lstat

        def controlled_lstat(path: Path) -> os.stat_result:
            if os.path.normcase(str(path)) == os.path.normcase(str(source)):
                return symlink_stat
            return original_lstat(path)

        monkeypatch.setattr(Path, "lstat", controlled_lstat)
    runner = FakeRunner(project.repository, project.inventory, _payload(project.targets))
    with pytest.raises(gate.GateError) as error:
        _run(project, runner)
    assert error.value.code == "link-or-reparse"


def test_missing_relative_nonregular_and_linked_executables_are_rejected(
    project: Project, tmp_path: Path
) -> None:
    runner = FakeRunner(project.repository, project.inventory, _payload(project.targets))
    with pytest.raises(gate.GateError) as missing:
        gate.run_release_gate(
            project.repository,
            runner=runner,
            executable_finder=lambda _name: None,
            rule_contract=TEST_RULE_CONTRACT,
            bundle_contract=TEST_BUNDLE_CONTRACT,
            finding_allowlist=(TEST_FINDING,),
        )
    assert missing.value.code == "missing-executable"

    with pytest.raises(gate.GateError) as relative:
        gate.run_release_gate(
            project.repository,
            runner=runner,
            executable_finder=lambda name: name,
            rule_contract=TEST_RULE_CONTRACT,
            bundle_contract=TEST_BUNDLE_CONTRACT,
            finding_allowlist=(TEST_FINDING,),
        )
    assert relative.value.code == "unsafe-executable"

    directory = tmp_path / "not-an-executable"
    directory.mkdir()
    with pytest.raises(gate.GateError) as nonregular:
        gate._find_executable("semgrep", lambda _name: str(directory))
    assert nonregular.value.code == "unsafe-executable"

    link = tmp_path / "semgrep-link"
    try:
        link.symlink_to(project.tools["semgrep"])
    except OSError:
        return
    with pytest.raises(gate.GateError) as linked:
        gate._find_executable("semgrep", lambda _name: str(link))
    assert linked.value.code == "link-or-reparse"

    outside_prefix = tmp_path / "outside-prefix"
    outside_prefix.mkdir()
    with pytest.raises(gate.GateError) as outside:
        gate._bind_semgrep_to_project_environment(
            project.tools["semgrep"],
            project.repository,
            outside_prefix,
            project.python_base_prefix,
        )
    assert outside.value.code == "unsafe-executable"


def test_semgrep_is_bound_to_active_exact_repository_virtualenv(project: Project) -> None:
    gate._bind_semgrep_to_project_environment(
        project.tools["semgrep"],
        project.repository,
        project.python_prefix,
        project.python_base_prefix,
    )
    with pytest.raises(gate.GateError, match="active virtual environment"):
        gate._bind_semgrep_to_project_environment(
            project.tools["semgrep"],
            project.repository,
            project.python_prefix,
            project.python_prefix,
        )

    sibling_prefix = project.repository.parent / "sibling-venv"
    sibling_scripts = sibling_prefix / ("Scripts" if os.name == "nt" else "bin")
    sibling_scripts.mkdir(parents=True)
    (sibling_prefix / "pyvenv.cfg").write_text("home = sibling\n")
    with pytest.raises(gate.GateError, match=r"repository \.venv"):
        gate._bind_semgrep_to_project_environment(
            project.tools["semgrep"],
            project.repository,
            sibling_prefix,
            project.python_base_prefix,
        )


def test_release_scan_is_serial_but_rule_bootstrap_remains_sharded() -> None:
    """The full scan must not reintroduce Windows fixpoint contention."""
    bootstrap = gate._semgrep_dump_command("semgrep")
    scan = gate._semgrep_bundle_command("semgrep", Path("bundle.json"))

    assert bootstrap[bootstrap.index("--jobs") + 1] == gate.SEMGREP_BOOTSTRAP_JOBS == "4"
    assert scan[scan.index("--jobs") + 1] == gate.SEMGREP_SCAN_JOBS == "1"


def test_temporary_mirror_must_be_external(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    inside = project.repository / "temporary-mirror"

    def inside_factory(*_args: object, **_kwargs: object) -> str:
        inside.mkdir()
        return str(inside)

    monkeypatch.setattr(tempfile, "mkdtemp", inside_factory)
    with (
        pytest.raises(gate.GateError) as error,
        gate._temporary_external_mirror(project.repository),
    ):
        pass
    assert error.value.code == "non-external-mirror"
    assert not inside.exists()


def test_main_emits_canonical_pass_and_fail_evidence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    success: dict[str, object] = {
        "schema_version": 1,
        "gate": "semgrep-release",
        "status": "pass",
    }
    monkeypatch.setattr(gate, "run_release_gate", lambda _repository: success)
    assert gate.main(["--repository", "."]) == 0
    assert capsys.readouterr().out == gate._canonical_json(success) + "\n"

    def fail(_repository: Path) -> dict[str, object]:
        raise gate.GateError("controlled", "failure")

    monkeypatch.setattr(gate, "run_release_gate", fail)
    assert gate.main(["--repository", "."]) == 1
    stderr = capsys.readouterr().err.splitlines()
    assert json.loads(stderr[0])["error_code"] == "controlled"
    assert stderr[1] == "semgrep release gate failed: failure"
