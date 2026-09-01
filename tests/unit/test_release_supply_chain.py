"""Static release-contract regressions for metadata and GitHub CI."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
_GITATTRIBUTES_PATH = _PROJECT_ROOT / ".gitattributes"
_EXPECTED_BRANCH = "fix/v2.21.0-release-blockers"
_INTEGRATED_COMMIT = "55d25dfff2225ffb3e4a2b56ead4a3c190d054cf"
_INTEGRATED_TREE = "761e264a91a52bda4c284f3f36fe53954d7fff2b"
_LIVE_START = "<!-- LIVE_STATE_START -->"
_LIVE_END = "<!-- LIVE_STATE_END -->"
_ARCHIVE_START = "<!-- ARCHIVE_START -->"
_ARCHIVE_END = "<!-- ARCHIVE_END -->"
_RELEASE_SEQUENCE = (
    "<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> "
    "annotated-tag -> github-release -->"
)
_SEMGREP_SYNC = "uv sync --locked --only-group security --no-install-project"
_SEMGREP_GATE = "uv run --no-sync python -I scripts/semgrep_release_gate.py"
_HARNESS_BASELINE_REVISION = "v2.20.0"
_HARNESS_BASELINE_COMMIT = "db71e53e637114ebf893b8fb98f0a21de5998440"
_STATE_KEYS = {
    "current_sprint",
    "sprint_goal",
    "branch",
    "started_at",
    "housekeeping_done",
    "memory_updated",
    "github_issues_closed",
    "sprint_backlog_written",
    "semgrep_passed",
    "tests_passed",
    "documentation_updated",
}
_LICENSE_EXPRESSION = "ISC AND BSD-3-Clause AND PSF-2.0"
_PSF_LICENSE_HEADING = "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2"
_PSF_LICENSE_SHA256 = "35936f8ff79198c68a38a9bb1912fa131fc7b840ca5928feea09dc96e5c66b8d"
_PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_ALLOWED_ACTIONS = {
    "actions/checkout",
    "actions/download-artifact",
    "actions/setup-python",
    "actions/upload-artifact",
    "astral-sh/setup-uv",
}


def _git(*args: str) -> bytes:
    git = shutil.which("git")
    assert git is not None, "release-contract tests require Git"
    return subprocess.run(  # noqa: S603 - shutil.which resolves the trusted Git executable
        [git, *args],
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _require_git_checkout() -> None:
    if not (_PROJECT_ROOT / ".git").exists():
        pytest.skip("repository-state contract requires Git checkout metadata")


def _marked_region(text: str, start: str, end: str) -> str:
    assert text.count(start) == 1
    assert text.count(end) == 1
    before, remainder = text.split(start, 1)
    region, after = remainder.split(end, 1)
    assert before or after
    return region


def _without_archive(text: str) -> str:
    assert text.count(_ARCHIVE_START) == 1
    assert text.count(_ARCHIVE_END) == 1
    before, remainder = text.split(_ARCHIVE_START, 1)
    _archive, after = remainder.split(_ARCHIVE_END, 1)
    return before + after


def _parse_state_frontmatter(text: str) -> dict[str, str | bool]:
    lines = text.splitlines()
    assert lines[0] == "---"
    closing = lines.index("---", 1)
    result: dict[str, str | bool] = {}
    for line in lines[1:closing]:
        key, separator, raw_value = line.partition(":")
        assert separator
        assert key not in result
        value = raw_value.strip()
        if value in {"true", "false"}:
            result[key] = value == "true"
        else:
            assert len(value) >= 2
            assert value[0] == value[-1] == '"'
            result[key] = value[1:-1]
    return result


def _dependency_body(export: bytes) -> bytes:
    lines = export.splitlines(keepends=True)
    first_requirement = next(index for index, line in enumerate(lines) if not line.startswith(b"#"))
    return b"".join(lines[first_requirement:])


def test_git_checkout_normalizes_text_bytes_for_cross_platform_artifacts() -> None:
    """Git checkouts must not make packaged policy/source bytes host-dependent."""
    _require_git_checkout()
    assert _GITATTRIBUTES_PATH.read_bytes() == b"* text=auto eol=lf\n"

    owned_paths = (
        _git("ls-files", "--cached", "--others", "--exclude-standard").decode().splitlines()
    )
    assert [path for path in owned_paths if Path(path).name == ".gitattributes"] == [
        ".gitattributes"
    ]

    attr_samples = [
        ".semgrepignore",
        "tests/unit/test_release_supply_chain.py",
        "_docs/nextgen_roadmap/acceptance_harness/pyproject.toml",
    ]
    attributes = _git("check-attr", "text", "eol", "--", *attr_samples).decode()
    for path in attr_samples:
        assert f"{path}: text: auto" in attributes
        assert f"{path}: eol: lf" in attributes

    for line in _git("ls-files", "--eol").decode().splitlines():
        assert line.startswith(("i/lf", "i/none", "i/-text")), line

    candidate_names: set[str] = set()
    for command in (
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        candidate_names.update(
            name.decode(errors="surrogateescape") for name in _git(*command).split(b"\0") if name
        )
    for name in sorted(candidate_names):
        path = _PROJECT_ROOT / name
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if b"\0" in raw:
            continue
        assert not raw.startswith(b"\xef\xbb\xbf"), name
        assert b"\r" not in raw, name
        raw.decode("utf-8")


def test_live_repository_state_documents_match_release_version() -> None:
    """Machine-read live state must not steer release work toward an old version."""
    _require_git_checkout()
    version = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    expected = f"v{version}"
    state_path = _PROJECT_ROOT / ".sprint" / "state.md"
    state = _parse_state_frontmatter(state_path.read_text(encoding="utf-8"))
    assert set(state) == _STATE_KEYS
    current_sprint = state["current_sprint"]
    assert isinstance(current_sprint, str)
    assert current_sprint.isdecimal()
    assert state["branch"] == _EXPECTED_BRANCH
    assert expected in str(state["sprint_goal"])
    assert state["semgrep_passed"] is True
    assert state["tests_passed"] is True
    assert state["documentation_updated"] is True
    assert state["memory_updated"] is True
    assert state["housekeeping_done"] is False
    assert state["github_issues_closed"] is False
    boolean_keys = _STATE_KEYS - {"current_sprint", "sprint_goal", "branch", "started_at"}
    assert all(isinstance(state[key], bool) for key in boolean_keys)

    backlog_matches = list(
        (_PROJECT_ROOT / "_docs" / "sprint backlogs").glob(f"*{state['current_sprint']}*")
    )
    assert state["sprint_backlog_written"] is bool(backlog_matches)
    assert len(backlog_matches) == 1
    if state["housekeeping_done"]:
        assert all(state[key] is True for key in boolean_keys - {"housekeeping_done"})

    live_paths = [
        state_path,
        _PROJECT_ROOT / "MEMORY.md",
        _PROJECT_ROOT / ".serena" / "memories" / "current_state.md",
        _PROJECT_ROOT / ".serena" / "memories" / "project_overview.md",
    ]
    forbidden_active_claims = (
        "all` reserved",
        "runs only its covering tests",
        "semgrep pro since",
        "original sources are never modified",
        "merge to main → version bump",
        "gates → merge → bump",
    )
    for path in live_paths:
        text = path.read_text(encoding="utf-8")
        live = _marked_region(text, _LIVE_START, _LIVE_END)
        assert expected in live, f"{path.relative_to(_PROJECT_ROOT)} is stale: {expected} missing"
        assert _EXPECTED_BRANCH in live
        assert _INTEGRATED_COMMIT in live
        assert _INTEGRATED_TREE in live
        for finding_id in ("MW220-112", "MW220-113", "MW220-114", "MW220-115"):
            assert finding_id in live
        assert "not a PASS" in live or "keinen CI-PASS" in live
        assert set(re.findall(r"\bv\d+\.\d+\.\d+\b", live)) == {expected}
        assert set(re.findall(r"\b(?:feature|fix)/[A-Za-z0-9._/-]+", live)) == {_EXPECTED_BRANCH}
        assert "development pause" not in live.lower()
        non_archived = _without_archive(text).lower()
        assert all(claim not in non_archived for claim in forbidden_active_claims)
        assert text.index(_LIVE_END) < text.index(_ARCHIVE_START) < text.index(_ARCHIVE_END)

    for path in (
        _PROJECT_ROOT / "README.md",
        _PROJECT_ROOT / "MEMORY.md",
        _PROJECT_ROOT / ".serena" / "memories" / "project_overview.md",
    ):
        assert _RELEASE_SEQUENCE in path.read_text(encoding="utf-8")

    roadmap = _PROJECT_ROOT / "bug_reporting" / "BUGFIXUNG_ROADMAP.md"
    assert roadmap.is_file()
    for path in (
        _PROJECT_ROOT / "MEMORY.md",
        _PROJECT_ROOT / ".serena" / "memories" / "current_state.md",
    ):
        live = _marked_region(path.read_text(encoding="utf-8"), _LIVE_START, _LIVE_END)
        assert "bug_reporting/BUGFIXUNG_ROADMAP.md" in live


def test_review_reports_bind_complete_follow_up_findings_and_status() -> None:
    """The review contract must not hide a blocker behind a loose substring check."""

    analysis = (_PROJECT_ROOT / "bug_reporting" / "ANALYSE_MUTMUTWIN220.md").read_text(
        encoding="utf-8"
    )
    roadmap = (_PROJECT_ROOT / "bug_reporting" / "BUGFIXUNG_ROADMAP.md").read_text(encoding="utf-8")
    expected_ids = {f"MW220-{number:03d}" for number in range(1, 116)}
    assert expected_ids <= set(re.findall(r"MW220-\d{3}", analysis))
    assert "115 Befunde (30 P0, 56 P1, 29 P2; MW220-001 bis -115)" in analysis
    assert "115 fortlaufende Befunde sind bestätigt: 30 P0, 56 P1 und 29 P2" in roadmap

    analysis_rows = {
        match.group("id"): match.group(0)
        for match in re.finditer(
            r"^\| (?P<id>MW220-\d{3}) \| P[012] \|.*\|$",
            analysis,
            flags=re.MULTILINE,
        )
    }
    assert "kein Produktions-TOCTOU-Befund" in analysis_rows["MW220-113"]
    assert "`--jobs 1`" in analysis_rows["MW220-114"]
    assert "wiederholte reale Windows-Läufe grün" in analysis_rows["MW220-114"]
    assert "GitHub Issue #133" in analysis
    assert "completed 1/1" in analysis
    assert "kein zusätzlicher MW220-116-Produktionsfix erforderlich" in analysis
    assert "GitHub-Issue-#133-Repro" in roadmap
    assert "Es ist kein MW220-116 erforderlich" in roadmap
    assert analysis_rows["MW220-115"].startswith("| MW220-115 | P2 |")
    assert "Teilstring" in analysis_rows["MW220-115"]

    for report in (analysis, roadmap):
        assert "Follow-up-Integration" in report
        assert "integrierter Rebuild" in report
        assert "Tag und GitHub-Release" in report or "Tag und Release" in report
        assert "Billing" in report
        assert "kein PASS" in report or "kein CI-PASS" in report

    assert "2.002 Tests und 44 Skips" in analysis
    assert "2.002/44" in roadmap
    assert "MW220-115 | implementiert und vollständig regressionstestverifiziert" in analysis

    stale_claims = (
        "Fix und erneute Cross-Platform-Typmatrix ausstehend",
        "deterministische Ursache/Fix und wiederholte Windows-/Ubuntu-Gateevidenz ausstehend",
        "verbleibende POSIX-Identitätslücke",
        "vollständig neue lokale und Remote-Matrix",
    )
    assert all(claim not in analysis for claim in stale_claims)


def test_install_guides_are_byte_identical_and_pin_the_release_version() -> None:
    """The maintained install copies must never steer users to different releases."""
    _require_git_checkout()
    canonical = (_PROJECT_ROOT / "_config" / "mutmut-win-install.md").read_bytes()
    documentation = (
        _PROJECT_ROOT / "_docs" / "installation" / "mutmut-win-install.md"
    ).read_bytes()
    assert documentation == canonical
    version = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    text = canonical.decode("utf-8")
    assert f"**Version:** v{version}" in text
    assert f"mutmut-win.git@v{version}" in text
    assert f"mutmut-win, version {version}" in text


def test_acceptance_harness_lock_matches_its_declared_release_baseline() -> None:
    """The standalone executable harness must not silently resolve another tag."""
    _require_git_checkout()
    harness = _PROJECT_ROOT / "_docs" / "nextgen_roadmap" / "acceptance_harness"
    project = tomllib.loads((harness / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((harness / "uv.lock").read_text(encoding="utf-8"))
    source = project["tool"]["uv"]["sources"]["mutmut-win"]
    assert source == {
        "git": "https://github.com/pgm1980/mutmut-win.git",
        "rev": _HARNESS_BASELINE_REVISION,
    }
    revision = source["rev"]
    assert revision == _HARNESS_BASELINE_REVISION
    locked_package = next(package for package in lock["package"] if package["name"] == "mutmut-win")
    assert locked_package["version"] == revision.removeprefix("v")
    locked_source = locked_package["source"]["git"]
    assert locked_source == (
        f"https://github.com/pgm1980/mutmut-win.git?rev={revision}#{_HARNESS_BASELINE_COMMIT}"
    )
    harness_project = next(
        package for package in lock["package"] if package["name"] == "roadmap-specs"
    )
    declared = next(
        dependency
        for dependency in harness_project["metadata"]["requires-dev"]["dev"]
        if dependency["name"] == "mutmut-win"
    )
    assert declared == {
        "name": "mutmut-win",
        "git": f"https://github.com/pgm1980/mutmut-win.git?rev={revision}",
    }
    provenance = (harness / "README_PROVENANCE.md").read_text(encoding="utf-8")
    assert f"standalone environment pins `@{revision}`" in provenance
    assert "once profiles exist" not in provenance.lower()

    roadmap = (harness / "ROADMAP_SPEC.md").read_text(encoding="utf-8")
    assert "[`../MUTMUT_WIN_OPERATOR_ROADMAP.md`](../MUTMUT_WIN_OPERATOR_ROADMAP.md)" in roadmap
    assert (harness.parent / "MUTMUT_WIN_OPERATOR_ROADMAP.md").is_file()
    roadmap_lower = roadmap.lower()
    assert "pragma `block` / `start`-`end`" in roadmap_lower
    assert "`do_not_mutate_patterns` (regex)" in roadmap
    assert "configuration key is implemented" in roadmap
    for stale_claim in ("once profiles exist", "unrecognized", "unknown key", "not wired"):
        assert stale_claim not in roadmap_lower


def test_active_governance_uses_only_the_canonical_semgrep_release_gate() -> None:
    """Machine-read guidance and executable hooks must not recreate raw false greens."""
    claude = (_PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    completion = (
        _PROJECT_ROOT / ".serena" / "memories" / "task_completion_checklist.md"
    ).read_text(encoding="utf-8")
    commands = (_PROJECT_ROOT / ".serena" / "memories" / "suggested_commands.md").read_text(
        encoding="utf-8"
    )
    design = (
        _PROJECT_ROOT / "_docs" / "design spec" / "software_design_specification.md"
    ).read_text(encoding="utf-8")
    backlog = (_PROJECT_ROOT / "_docs" / "product backlog" / "product_backlog.md").read_text(
        encoding="utf-8"
    )
    active_backlog = backlog.split("## Epics und Sprint-Zuordnung", 1)[0]

    hook_dir = _PROJECT_ROOT / ".claude" / "hooks"
    verify_hook = (hook_dir / "verify-after-agent.sh").read_text(encoding="utf-8")
    pre_commit = (hook_dir / "git-pre-commit.sh").read_bytes()
    installed_pre_commit = (hook_dir / "git-hooks" / "pre-commit").read_bytes()
    assert pre_commit == installed_pre_commit
    pre_commit_text = pre_commit.decode("utf-8")
    reminder = (hook_dir / "post-compact-reminder.sh").read_text(encoding="utf-8")
    sprint_gate = (hook_dir / "sprint-gate.sh").read_text(encoding="utf-8")

    exact_command_authorities = (
        claude,
        completion,
        commands,
        active_backlog,
        verify_hook,
        pre_commit_text,
    )
    assert all(_SEMGREP_GATE in text for text in exact_command_authorities)
    assert all(_SEMGREP_SYNC in text for text in (claude, completion, commands, active_backlog))
    assert "scripts/semgrep_release_gate.py" in design
    assert "vollständigen Git-owned Scope" in reminder

    active_authorities = (
        *exact_command_authorities,
        design,
        reminder,
        sprint_gate,
    )
    for text in active_authorities:
        lowered = text.lower()
        assert "semgrep scan" not in lowered
        assert "--config auto" not in lowered
        assert "--changed-files" not in lowered

    for executor in (verify_hook, pre_commit_text):
        invocations = [
            line.strip()
            for line in executor.splitlines()
            if line.strip().startswith("SEMGREP_OUTPUT=$(")
        ]
        assert invocations == [f"SEMGREP_OUTPUT=$({_SEMGREP_GATE} 2>&1)"]
        assert "uvx" not in executor
        assert "command -v semgrep" not in executor

    semgrep_state_check = sprint_gate.split("# Live check 4:", 1)[1].split(
        'if [[ -n "$BLOCKERS" ]]', 1
    )[0]
    assert "git log" not in semgrep_state_check
    assert "semgrep_passed:" in sprint_gate
    settings = json.loads((_PROJECT_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "Bash(semgrep *)" not in settings["permissions"]["allow"]
    subagent_hooks = settings["hooks"]["SubagentStop"][0]["hooks"]
    verify_settings = next(
        hook for hook in subagent_hooks if hook["command"].endswith("verify-after-agent.sh")
    )
    assert verify_settings["command"] == "bash .claude/hooks/verify-after-agent.sh"
    assert verify_settings["timeout"] >= 600

    version = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    assert ">=3.12,<3.15" in claude
    assert f"mutmut-win.git@v{version}" in claude
    assert "Semgrep CLI                 | 1.175.0 (uv.lock)" in claude
    assert "Python 3.14 Features nutzen" not in claude
    assert "3.14.3" not in claude
    assert ">=0.6.0" not in claude


def test_dependency_export_body_is_path_independent_and_pinned(tmp_path: Path) -> None:
    """Audit evidence must hash dependencies, not an absolute output-file header."""
    uv = shutil.which("uv")
    assert uv is not None, "release-contract tests require uv"
    command = [
        uv,
        "export",
        "--frozen",
        "--all-extras",
        "--all-groups",
        "--no-hashes",
        "--no-emit-project",
    ]
    stdout = subprocess.run(  # noqa: S603 - shutil.which resolves the trusted uv executable
        command,
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    outputs = [tmp_path / "first.txt", tmp_path / "path with spaces" / "second.txt"]
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603 - trusted uv executable and test-owned output path
            [*command, "--output-file", str(output)],
            cwd=_PROJECT_ROOT,
            check=True,
            capture_output=True,
        )
    bodies = [_dependency_body(stdout), *(_dependency_body(path.read_bytes()) for path in outputs)]
    assert bodies[0] == bodies[1] == bodies[2]
    assert hashlib.sha256(bodies[0]).hexdigest() == (
        "7deef5fd17ec5e7aa60cb18c6be87e3d1a8478af3d7e1262d0bb2155bbd1fdd6"
    )


def test_python_metadata_matches_fail_closed_runtime_support() -> None:
    pyproject = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    lock = tomllib.loads((_PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
    readme = (_PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    locked_build_backend = ["hatchling==1.32.0", "editables==0.5"]
    assert pyproject["build-system"]["requires"] == locked_build_backend
    assert pyproject["dependency-groups"]["build"] == locked_build_backend
    assert pyproject["dependency-groups"]["security"] == ["semgrep==1.175.0"]
    locked_project = next(package for package in lock["package"] if package["name"] == "mutmut-win")
    locked_semgrep = next(package for package in lock["package"] if package["name"] == "semgrep")
    assert locked_project["dev-dependencies"]["security"] == [{"name": "semgrep"}]
    assert locked_project["metadata"]["requires-dev"]["security"] == [
        {"name": "semgrep", "specifier": "==1.175.0"}
    ]
    assert locked_semgrep["version"] == "1.175.0"
    assert locked_semgrep["source"] == {"registry": "https://pypi.org/simple"}
    assert locked_semgrep["sdist"]["hash"].startswith("sha256:")
    assert locked_semgrep["wheels"]
    assert all(wheel["hash"].startswith("sha256:") for wheel in locked_semgrep["wheels"])
    assert project["requires-python"] == ">=3.12,<3.15"
    assert lock["requires-python"] == ">=3.12, <3.15"
    assert "Programming Language :: Python :: Implementation :: CPython" in project["classifiers"]
    for version in ("3.12", "3.13", "3.14"):
        assert f"Programming Language :: Python :: {version}" in project["classifiers"]
    assert "CPython 3.12\N{EN DASH}3.14" in readme
    assert "uv sync --locked --only-group security --no-install-project" in readme
    assert "uv run --no-sync python -I scripts/semgrep_release_gate.py" in readme


def test_cpython_derivative_license_contract_is_complete() -> None:
    pyproject = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    license_text = (_PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    readme = (_PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert project["license"] == _LICENSE_EXPRESSION
    assert "License :: OSI Approved :: Python Software Foundation License" in project["classifiers"]
    assert _PSF_LICENSE_HEADING in license_text
    assert "Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved" in license_text
    assert "atomic STARTUPINFOEX Job-list assignment" in license_text
    assert "seekable bootstrap storage plus a separate parent-liveness pipe" in license_text
    assert _LICENSE_EXPRESSION in readme
    psf_license = _PSF_LICENSE_HEADING + license_text.split(_PSF_LICENSE_HEADING, 1)[1]
    normalized_psf_license = psf_license.replace("\r\n", "\n").rstrip()
    assert hashlib.sha256(normalized_psf_license.encode()).hexdigest() == _PSF_LICENSE_SHA256


def test_wheel_and_sdist_embed_the_exact_composite_license(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "315532800"
    subprocess.run(  # noqa: S603 - current interpreter and fixed Hatchling module
        [
            sys.executable,
            "-m",
            "hatchling",
            "build",
            "-d",
            str(dist_dir),
        ],
        cwd=_PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    wheel_files = list(dist_dir.glob("*.whl"))
    sdist_files = list(dist_dir.glob("*.tar.gz"))
    assert len(wheel_files) == 1
    assert len(sdist_files) == 1
    expected_license = (_PROJECT_ROOT / "LICENSE").read_bytes()

    with zipfile.ZipFile(wheel_files[0]) as wheel:
        license_members = [
            name for name in wheel.namelist() if name.endswith(".dist-info/licenses/LICENSE")
        ]
        assert len(license_members) == 1
        assert wheel.read(license_members[0]) == expected_license

    with tarfile.open(sdist_files[0], mode="r:gz") as sdist:
        sdist_roots = {
            member.name.split("/", 1)[0]
            for member in sdist.getmembers()
            if member.name and "/" in member.name
        }
        assert len(sdist_roots) == 1
        sdist_root = next(iter(sdist_roots))
        license_members = [
            member
            for member in sdist.getmembers()
            if member.isfile() and member.name == f"{sdist_root}/LICENSE"
        ]
        assert len(license_members) == 1
        license_stream = sdist.extractfile(license_members[0])
        assert license_stream is not None
        assert license_stream.read() == expected_license
        gate_members = [
            member
            for member in sdist.getmembers()
            if member.isfile() and member.name == f"{sdist_root}/scripts/semgrep_release_gate.py"
        ]
        assert len(gate_members) == 1
        gate_stream = sdist.extractfile(gate_members[0])
        assert gate_stream is not None
        assert (
            gate_stream.read() == (_PROJECT_ROOT / "scripts/semgrep_release_gate.py").read_bytes()
        )
        policy_members = [
            member
            for member in sdist.getmembers()
            if member.isfile() and member.name == f"{sdist_root}/.semgrepignore"
        ]
        assert len(policy_members) == 1
        policy_stream = sdist.extractfile(policy_members[0])
        assert policy_stream is not None
        assert policy_stream.read() == (_PROJECT_ROOT / ".semgrepignore").read_bytes()


def test_ci_uses_only_full_sha_pinned_allowlisted_actions() -> None:
    workflow = _WORKFLOW_PATH.read_text(encoding="utf-8")
    action_references = re.findall(r"^\s*uses:\s*([^\s#]+)", workflow, flags=re.MULTILINE)

    assert action_references
    assert all(_PINNED_ACTION.fullmatch(reference) for reference in action_references)
    assert {reference.split("@", 1)[0] for reference in action_references} <= _ALLOWED_ACTIONS


def test_ci_covers_supported_matrix_and_separate_release_gates() -> None:
    workflow = _WORKFLOW_PATH.read_text(encoding="utf-8")
    quality_job = workflow.split("\n  quality:\n", 1)[1].split("\n  security:\n", 1)[0]
    security_job = workflow.split("\n  security:\n", 1)[1].split("\n  tests:\n", 1)[0]
    tests_job = workflow.split("\n  tests:\n", 1)[1].split("\n  pytest-compat:\n", 1)[0]
    audit_job = workflow.split("\n  audit:\n", 1)[1].split("\n  build:\n", 1)[0]

    assert "os: [windows-latest, ubuntu-latest]" in workflow
    assert 'python-version: ["3.12", "3.13", "3.14"]' in workflow
    assert "os: [windows-latest, ubuntu-latest]" in audit_job
    assert 'python-version: ["3.12", "3.13", "3.14"]' in audit_job
    for job in (
        "lock",
        "quality",
        "security",
        "tests",
        "pytest-compat",
        "audit",
        "build",
        "artifacts",
    ):
        assert re.search(rf"^  {job}:$", workflow, flags=re.MULTILINE)
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "pull_request_target" not in workflow
    assert "permissions: write" not in workflow
    assert "id-token: write" not in workflow
    assert "UV_FROZEN" not in workflow
    backend_bootstrap = "uv sync --locked --only-group build --no-install-project"
    full_sync = "uv sync --locked --extra dev --group build --no-build-isolation"
    assert workflow.count(backend_bootstrap) == 4
    assert workflow.count(full_sync) == 3
    for job in (quality_job, tests_job, audit_job):
        assert job.index(backend_bootstrap) < job.index(full_sync)
    assert "os: [windows-latest, ubuntu-latest]" in security_job
    security_sync = "uv sync --locked --only-group security --no-install-project"
    security_command = "uv run --no-sync python -I scripts/semgrep_release_gate.py"
    security_run_lines = re.findall(r"^\s*run:\s*(.+?)\s*$", security_job, re.MULTILINE)
    assert security_run_lines == [security_sync, security_command]
    assert not re.search(r"\buvx\b", workflow)
    assert "semgrep scan --config auto" not in workflow
    assert "uv run --no-sync mypy src/ scripts/" in quality_job
    pytest_floor_command = "uv run --isolated --frozen --no-dev --no-cache --with pytest==8.2.2"
    assert workflow.count(pytest_floor_command) == 1
    locked_workflow = workflow.replace(pytest_floor_command, "uv run --no-sync")
    assert not re.search(r"\buv run (?!\-\-no-sync\b)", locked_workflow)
    assert not re.search(r"^  (?:release|publish):$", workflow, flags=re.MULTILINE)
    assert "uv run --no-sync uv build --offline --no-build-isolation" in workflow
    assert "diff --recursive --brief" in workflow
    assert "uv pip install --offline --no-build-isolation --no-deps" in workflow
