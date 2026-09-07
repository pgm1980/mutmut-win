"""Static release-contract regressions for metadata and GitHub CI."""

from __future__ import annotations

import ast
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
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
_GITATTRIBUTES_PATH = _PROJECT_ROOT / ".gitattributes"
_IS_GENERATED_MUTATION_STAGING = (
    _PROJECT_ROOT.name.casefold() == "mutants"
    and (_PROJECT_ROOT / ".mutmut-config-fingerprint").is_file()
    and not (_PROJECT_ROOT / ".git").exists()
)
pytestmark = pytest.mark.skipif(
    _IS_GENERATED_MUTATION_STAGING,
    reason="repository governance contracts are intentionally outside executable mutation staging",
)
_LIVE_START = "<!-- LIVE_STATE_START -->"
_LIVE_END = "<!-- LIVE_STATE_END -->"
_ARCHIVE_START = "<!-- ARCHIVE_START -->"
_ARCHIVE_END = "<!-- ARCHIVE_END -->"
_PUBLICATION_START = "<!-- PUBLICATION_STATE_START -->"
_PUBLICATION_STATE = "<!-- PUBLICATION_STATE: external-live-check-required -->"
_PUBLICATION_END = "<!-- PUBLICATION_STATE_END -->"
_PUBLICATION_SENTENCE = (
    "Publication status for v{version} is external mutable state. These immutable bytes "
    "assert neither presence nor absence; verify the exact annotated tag and matching "
    "GitHub release before use."
)
_RELEASE_PHASE_PREFIX = "<!-- RELEASE_PHASE: "
_RELEASE_PHASE_STATUS_PREFIX = "<!-- RELEASE_PHASE_STATUS: "
_PHASE_GOAL_SUFFIX = {
    "in_progress": "in progress",
    "candidate_validated": "candidate validated",
    "released": "released",
}
_PHASE_STATUS = {
    "in_progress": "implementation-and-final-gates-open",
    "candidate_validated": "local-candidate-gates-validated-publication-external",
    "released": "tagged-release-housekeeping-complete",
}
_HOUSEKEEPING_PATHS = {
    ".serena/memories/current_state.md",
    ".serena/memories/project_overview.md",
    ".serena/memories/style_conventions.md",
    ".sprint/state.md",
    "MEMORY.md",
    "bug_reporting/ANALYSE_MUTMUTWIN221.md",
    "bug_reporting/BUGFIXUNG_ROADMAP.md",
}
_RELEASE_SEQUENCE = (
    "<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> "
    "integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->"
)
_SEMGREP_SYNC = "uv sync --locked --only-group security --no-install-project"
_SEMGREP_GATE = "uv run --no-sync python -I scripts/semgrep_release_gate.py"
_NATIVE_RELEASE_SYNC = "uv sync --locked --only-group release --no-install-project"
_NATIVE_RELEASE_GATE = "uv run --no-sync python -I scripts/release_native_gate.py"
_MINIMUM_RELEASE_VERSION = "2.21.1"
_HARNESS_BASELINE_REVISION = "v2.20.0"
_HARNESS_BASELINE_COMMIT = "db71e53e637114ebf893b8fb98f0a21de5998440"
_EXACT_RUNTIME_CONTRACT = (
    "**Verbindlicher Laufzeitvertrag:** Windows und exakt CPython 3.14.7; andere "
    "Python-Versionen, Implementierungen und Betriebssysteme sind nicht unterstützt."
)
_SOURCE_ENCODING_CONTRACT = (
    "Python-Quelltext wird gemäß PEP 263 dekodiert; projektinterne Metadaten bleiben UTF-8."
)
_STATE_KEYS = {
    "current_sprint",
    "sprint_goal",
    "branch",
    "started_at",
    "phase",
    "candidate_commit",
    "candidate_tree",
    "integrated_commit",
    "integrated_tree",
    "release_tag",
    "housekeeping_done",
    "memory_updated",
    "github_issues_closed",
    "sprint_backlog_written",
    "semgrep_passed",
    "tests_passed",
    "documentation_updated",
}
_LICENSE_EXPRESSION = "ISC AND BSD-3-Clause AND PSF-2.0"
_CPYTHON_DERIVATIVE_HEADING = "Portions adapted from CPython 3.12-3.14"
_CPYTHON_DERIVATIVE_SHA256 = "5c38c4fc924cb1b413580c8c43b9ce2794ed992655583dc49a08a75f2478b73a"
_PSF_LICENSE_HEADING = "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2"
_PSF_LICENSE_SHA256 = "35936f8ff79198c68a38a9bb1912fa131fc7b840ca5928feea09dc96e5c66b8d"
_RELEASE_TOOL_PROVENANCE_START = "<!-- RELEASE_TOOL_PROVENANCE_START -->"
_RELEASE_TOOL_PROVENANCE_END = "<!-- RELEASE_TOOL_PROVENANCE_END -->"
_PINNED_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_LIVE_BRANCH_REF = re.compile(
    # A slash is deliberately a valid left boundary: this finds the branch
    # portion inside arbitrary remote/tag-qualified refs as well as bare refs.
    r"(?<![A-Za-z0-9._-])"
    r"(?:(?:origin|refs/heads|refs/remotes/origin)/)?"
    r"((?:feature|fix)/(?:[A-Za-z0-9._-]*[A-Za-z0-9_-])"
    r"(?:/(?:[A-Za-z0-9._-]*[A-Za-z0-9_-]))*)"
    r"(?![A-Za-z0-9._/-])"
)
_GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_ACTIONS = {
    "actions/checkout",
    "actions/download-artifact",
    "actions/setup-python",
    "actions/upload-artifact",
    "astral-sh/setup-uv",
}
_MW221_STATUSES = {
    "ACCEPTED_LIMITATION",
    "CLOSED_PROCESS",
    "IMPLEMENTED_PENDING_FINAL",
    "MIXED",
    "OPEN_PROCESS",
    "OPEN_PRODUCT",
    "OUT_OF_TARGET",
    "REJECTED_AS_BUG",
    "VERIFIED_FIXED",
}
_CX221_STATUSES = _MW221_STATUSES | {"FIX_IN_PROGRESS"}


def _semver_tuple(version: str) -> tuple[int, int, int]:
    """Return the strict three-component numeric release version."""

    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def _assert_active_ref_matches_release_stage(
    package_version: str,
    active_version: str,
    *,
    final: bool = False,
) -> None:
    """Allow only the release itself or its immediate patch predecessor."""

    package = _semver_tuple(package_version)
    active = _semver_tuple(active_version)
    if final:
        assert package >= _semver_tuple(_MINIMUM_RELEASE_VERSION), (
            f"final release metadata must not regress below {_MINIMUM_RELEASE_VERSION}: "
            f"package={package_version}"
        )
        assert active == package, (
            "a final release state requires the active install ref to equal "
            f"the package version: package={package_version}, active={active_version}"
        )
        return
    assert active == package or (active[:2] == package[:2] and active[2] + 1 == package[2]), (
        "active install ref must equal the package version or its immediate "
        f"patch predecessor: package={package_version}, active={active_version}"
    )


def _single_match_version(pattern: str, text: str, *, label: str) -> str:
    """Return one active command version and reject missing or duplicate pins."""

    matches: list[re.Match[str]] = list(re.finditer(pattern, text, flags=re.MULTILINE))
    versions = [match.group(1) for match in matches]
    assert len(matches) == 1, f"expected one {label} release pin, found {versions}"
    return matches[0].group(1)


def _git(*args: str) -> bytes:
    git = shutil.which("git")
    assert git is not None, "release-contract tests require Git"
    return subprocess.run(  # noqa: S603 - shutil.which resolves the trusted Git executable
        [git, *args],
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _optional_exact_ref_commit(ref: str) -> str | None:
    """Resolve one fully qualified ref without Git's ambiguous DWIM lookup."""

    try:
        raw = _git(
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        )
    except subprocess.CalledProcessError:
        return None
    commit = raw.decode("ascii").strip()
    assert _GIT_OBJECT_ID.fullmatch(commit), f"invalid commit identity for {ref}: {commit!r}"
    return commit


def _exact_branch_identities(branch: str) -> tuple[tuple[str, str], ...]:
    """Return distinct ``(commit, tree)`` identities from exact local/remote refs."""

    identities: set[tuple[str, str]] = set()
    for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
        commit = _optional_exact_ref_commit(ref)
        if commit is None:
            continue
        tree = (
            _git(
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{commit}^{{tree}}",
            )
            .decode("ascii")
            .strip()
        )
        assert _GIT_OBJECT_ID.fullmatch(tree), f"invalid tree identity for {ref}: {tree!r}"
        identities.add((commit, tree))
    return tuple(sorted(identities))


def _source_branch_identities(
    branch: str,
    *,
    github_actions: bool,
    github_head_ref: str,
    github_head_sha: str,
) -> tuple[tuple[str, str], ...]:
    """Include GitHub's exact fork-head object when no origin ref can exist."""

    identities = set(_exact_branch_identities(branch))
    if github_actions and github_head_ref:
        assert github_head_ref == branch
        assert _GIT_OBJECT_ID.fullmatch(github_head_sha), "GitHub PR head SHA is missing or invalid"
        commit = (
            _git(
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{github_head_sha}^{{commit}}",
            )
            .decode("ascii")
            .strip()
        )
        assert commit == github_head_sha
        tree = (
            _git(
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{commit}^{{tree}}",
            )
            .decode("ascii")
            .strip()
        )
        assert _GIT_OBJECT_ID.fullmatch(tree)
        identities.add((commit, tree))
    return tuple(sorted(identities))


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


def _release_tool_provenance(text: str) -> dict[tuple[str, str], str]:
    region = _marked_region(
        text,
        _RELEASE_TOOL_PROVENANCE_START,
        _RELEASE_TOOL_PROVENANCE_END,
    )
    assert region.startswith("\n| Autorität | Tool/Artefakt | SHA-256 |\n|---|---|---|\n")
    rows = re.findall(
        r"^\| (?P<authority>Native GitHub asset|PyPI / `uv\.lock`) "
        r"\| (?P<artifact>[^|\n]+?) \| `(?P<digest>[0-9a-f]{64})` \|$",
        region,
        flags=re.MULTILINE,
    )
    assert len(rows) == 6
    mapping: dict[tuple[str, str], str] = {}
    for authority, artifact, digest in rows:
        key = (authority, artifact)
        assert key not in mapping
        mapping[key] = digest
    return mapping


def _expected_release_tool_provenance() -> dict[tuple[str, str], str]:
    manifest = json.loads(
        (_PROJECT_ROOT / "scripts" / "release_native_tools.json").read_text(encoding="utf-8")
    )
    native_labels = {
        "actionlint": "actionlint 1.7.12 ZIP",
        "shellcheck": "ShellCheck 0.11.0 ZIP",
        "gitleaks": "Gitleaks 8.30.1 Windows x64 ZIP",
    }
    expected = {
        ("Native GitHub asset", native_labels[tool["name"]]): tool["sha256"]
        for tool in manifest["tools"]
    }

    lock = tomllib.loads((_PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
    zizmor = next(package for package in lock["package"] if package["name"] == "zizmor")
    expected[("PyPI / `uv.lock`", "zizmor 1.30.0 sdist")] = zizmor["sdist"]["hash"].removeprefix(
        "sha256:"
    )
    wheel_labels = {
        "zizmor-1.30.0-py3-none-win_amd64.whl": "zizmor 1.30.0 Windows amd64 wheel",
        "zizmor-1.30.0-py3-none-manylinux_2_28_x86_64.whl": (
            "zizmor 1.30.0 manylinux build-host wheel"
        ),
    }
    for wheel in zizmor["wheels"]:
        filename = wheel["url"].rsplit("/", 1)[-1]
        if filename in wheel_labels:
            expected[("PyPI / `uv.lock`", wheel_labels[filename])] = wheel["hash"].removeprefix(
                "sha256:"
            )
    assert len(expected) == 6
    return expected


def _publication_contract(version: str) -> str:
    return "\n".join(
        (
            _PUBLICATION_START,
            _PUBLICATION_STATE,
            _PUBLICATION_SENTENCE.format(version=version),
            _PUBLICATION_END,
        )
    )


def _live_state_contract(version: str, branch: str, phase: str) -> str:
    """Return the complete closed LIVE block for one lifecycle phase."""
    return (
        "\n\n"
        f"<!-- RELEASE_PHASE: {phase} -->\n"
        f"<!-- RELEASE_PHASE_STATUS: {_PHASE_STATUS[phase]} -->\n"
        f"<!-- RELEASE_TARGET: v{version} -->\n"
        f"<!-- RELEASE_BRANCH: `{branch}` -->\n"
        "<!-- RELEASE_ROADMAP: bug_reporting/BUGFIXUNG_ROADMAP.md -->\n"
        "<!-- RELEASE_PUBLICATION_AUTHORITY: canonical-external-block -->\n\n"
    )


def _assert_publication_references_are_structural(text: str, version: str) -> None:
    """Allow the target version only in closed, non-assertive machine contexts."""
    contract = _publication_contract(version)
    assert text.count(contract) == 1
    remaining = text.replace(contract, "", 1)
    escaped = re.escape(version)
    release_target_line = f"<!-- RELEASE_TARGET: v{version} -->"
    if _LIVE_START in text or _LIVE_END in text:
        assert text.count(_LIVE_START) == 1
        assert text.count(_LIVE_END) == 1
        live = _marked_region(text, _LIVE_START, _LIVE_END)
        assert live.count(release_target_line) == 1
        assert text.count(release_target_line) == 1
    else:
        assert release_target_line not in text
    git_url = rf"https://github\.com/pgm1980/mutmut-win\.git@v{escaped}"
    structural_patterns = (
        rf'^pip install "mutmut-win @ git\+{git_url}"$',
        rf'^uv add "mutmut-win @ git\+{git_url}" --dev$',
        rf'^\s*"mutmut-win @ git\+{git_url}",$',
        rf'^branch: "fix/v{escaped}-[A-Za-z0-9._/-]+"$',
        rf"^<!-- RELEASE_BRANCH: `fix/v{escaped}-[A-Za-z0-9._/-]+` -->$",
        rf'^sprint_goal: "v{escaped}: '
        rf'(?:in progress|candidate validated|released)"$',
        rf'^release_tag: "v{escaped}"$',
        rf"^<!-- RELEASE_TARGET: v{escaped} -->$",
        rf"^\*\*Version:\*\* v{escaped} "
        rf"\(verbindlicher Versionsstand dieser Anleitung\)$",
        rf"^Erwartete Ausgabe: `mutmut-win, version {escaped}`$",
    )
    for pattern in structural_patterns:
        remaining = re.sub(pattern, "<STRUCTURAL_VERSION_REF>", remaining, flags=re.MULTILINE)
    assert re.search(rf"(?<!\d)v?{escaped}(?!\d)", remaining, re.IGNORECASE) is None


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


def _sprint_backlog_relative_path(current_sprint: str) -> str:
    """Return the one active backlog path without allowing historical siblings."""

    assert re.fullmatch(r"[1-9][0-9]*", current_sprint)
    return f"_docs/sprint backlogs/sprint_{current_sprint}_backlog.md"


def _assert_sprint_backlog_matches_lifecycle(
    backlog: str,
    *,
    current_sprint: str,
    target_version: str,
    branch: str,
    phase: str,
) -> None:
    """Bind the active backlog to its branch and honest lifecycle gate state."""

    assert phase in _PHASE_GOAL_SUFFIX
    assert backlog.startswith(f"# Sprint {current_sprint} Backlog\n")
    assert f"| **Ziel** | v{target_version} |" in backlog
    assert "| **Scope** | Windows und exakt CPython 3.14.7 |" in backlog
    assert re.findall(
        r"^\| \*\*Branch\*\* \| `([^`\r\n]+)` \|$",
        backlog,
        flags=re.MULTILINE,
    ) == [branch]
    assert "| **Analyse** | `bug_reporting/ANALYSE_MUTMUTWIN221.md` |" in backlog
    assert "| **Roadmap** | `bug_reporting/BUGFIXUNG_ROADMAP.md` |" in backlog
    assert "billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`" in backlog
    assert "weder PASS noch FAIL" in backlog
    assert backlog.count(_RELEASE_SEQUENCE) == 1
    checkboxes = re.findall(r"^- \[(?P<state>[ xX])\] (?P<label>.+)$", backlog, re.MULTILINE)
    assert len(checkboxes) == 9
    expected_state = "x" if phase == "released" else " "
    assert {state.casefold() for state, _label in checkboxes} == {expected_state}


def _assert_sprint_state_is_coherent(
    state: dict[str, str | bool], package_version: str
) -> tuple[str, str]:
    """Validate lifecycle invariants without requiring one transient state."""
    assert set(state) == _STATE_KEYS
    current_sprint = state["current_sprint"]
    assert isinstance(current_sprint, str)
    assert re.fullmatch(r"[1-9][0-9]*", current_sprint)
    branch = state["branch"]
    assert isinstance(branch, str)
    assert branch == "main" or re.fullmatch(r"fix/v\d+\.\d+\.\d+(?:-[A-Za-z0-9._-]+)+", branch)

    sprint_goal = state["sprint_goal"]
    assert isinstance(sprint_goal, str)
    target_matches = re.findall(r"\bv(\d+\.\d+\.\d+)\b", sprint_goal)
    assert len(target_matches) == 1
    target_version = target_matches[0]
    package_parts = tuple(int(part) for part in package_version.split("."))
    target_parts = tuple(int(part) for part in target_version.split("."))
    assert target_parts[:2] == package_parts[:2]
    assert package_parts[2] <= target_parts[2] <= package_parts[2] + 1
    if branch != "main":
        assert branch.startswith(f"fix/v{target_version}-")

    phase = state["phase"]
    assert isinstance(phase, str)
    assert phase in _PHASE_GOAL_SUFFIX
    assert sprint_goal == f"v{target_version}: {_PHASE_GOAL_SUFFIX[phase]}"

    started_at = state["started_at"]
    assert isinstance(started_at, str)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", started_at)
    assert date.fromisoformat(started_at).isoformat() == started_at

    provenance_keys = {
        "candidate_commit",
        "candidate_tree",
        "integrated_commit",
        "integrated_tree",
        "release_tag",
    }
    provenance = {key: state[key] for key in provenance_keys}
    assert all(isinstance(value, str) for value in provenance.values())

    boolean_keys = (
        _STATE_KEYS
        - {
            "current_sprint",
            "sprint_goal",
            "branch",
            "started_at",
            "phase",
        }
        - provenance_keys
    )
    assert all(isinstance(state[key], bool) for key in boolean_keys)
    # A green final suite can only describe the exact version under test. During
    # development it is legitimate for metadata still to expose the released
    # predecessor while the LIVE state names the next patch candidate.
    if state["tests_passed"]:
        assert package_parts >= _semver_tuple(_MINIMUM_RELEASE_VERSION)
        assert target_version == package_version
    if state["housekeeping_done"]:
        assert all(state[key] is True for key in boolean_keys - {"housekeeping_done"})

    if phase == "in_progress":
        assert branch != "main"
        assert state["tests_passed"] is False
        assert state["semgrep_passed"] is False
        assert state["housekeeping_done"] is False
        assert set(provenance.values()) == {""}
    elif phase == "candidate_validated":
        assert branch != "main"
        assert state["tests_passed"] is True
        assert state["semgrep_passed"] is True
        assert state["documentation_updated"] is True
        assert state["memory_updated"] is True
        assert state["housekeeping_done"] is False
        assert set(provenance.values()) == {""}
    else:
        assert branch == "main"
        assert state["housekeeping_done"] is True
        assert state["release_tag"] == f"v{target_version}"
        for key in provenance_keys - {"release_tag"}:
            assert _GIT_OBJECT_ID.fullmatch(str(state[key])), key
    return target_version, branch


def _assert_live_branch_matches_state(live: str, branch: str) -> None:
    """Bind every LIVE block to one explicit branch and reject stale refs."""
    assert f"`{branch}`" in live
    expected_refs = set() if branch == "main" else {branch}
    assert set(_LIVE_BRANCH_REF.findall(live)) == expected_refs


def _assert_live_phase_matches_state(
    live: str, phase: str, target_version: str, branch: str
) -> None:
    """Require a closed machine-only LIVE block with no contradictory prose."""
    assert live == _live_state_contract(target_version, branch, phase)


def _assert_checkout_identity_matches_state(
    branch: str,
    *,
    checkout_branch: str,
    head_commit: str,
    head_tree: str,
    head_parents: tuple[str, ...],
    source_ref_identities: tuple[tuple[str, str], ...],
    main_ref_identities: tuple[tuple[str, str], ...],
    github_actions: bool = False,
    github_head_ref: str = "",
    github_ref_name: str = "",
) -> None:
    """Bind checkout state to exact refs or one byte-identical integration merge.

    A version-controlled tree cannot truthfully rename its source branch while
    it is being merged.  The same state is therefore valid either at the exact
    declared branch tip, or at a two-parent merge whose second parent is that
    tip and whose tree is byte-identical to it.  The latter may be the actual
    ``main`` tip, a local detached checkout of that tip, or GitHub's detached
    pull-request merge based on an exact ``main`` ref.
    """

    def require_object_id(value: str, *, label: str) -> None:
        assert _GIT_OBJECT_ID.fullmatch(value), f"invalid {label} identity: {value!r}"

    require_object_id(head_commit, label="HEAD commit")
    require_object_id(head_tree, label="HEAD tree")
    for parent in head_parents:
        require_object_id(parent, label="HEAD parent")
    assert source_ref_identities, f"no exact local or origin ref exists for {branch}"
    for commit, tree in (*source_ref_identities, *main_ref_identities):
        require_object_id(commit, label="ref commit")
        require_object_id(tree, label="ref tree")

    source_identities = set(source_ref_identities)
    main_commits = {commit for commit, _tree in main_ref_identities}

    def assert_github_ref(expected: str) -> None:
        if not github_actions:
            return
        observed = github_head_ref or github_ref_name
        assert observed == expected, f"GitHub checkout ref must be {expected!r}, got {observed!r}"

    # Direct source/main tips and their exact detached checkouts.
    if (head_commit, head_tree) in source_identities:
        assert checkout_branch in {"", branch}
        assert_github_ref(branch)
        return

    # A candidate tree integrated with a merge commit must retain exact byte
    # identity and must be the merge's second parent. Fast-forward or octopus
    # ancestry cannot prove the reviewed source-tree boundary.
    assert branch != "main"
    assert len(head_parents) == 2
    assert len({head_commit, *head_parents}) == 3
    assert (head_parents[1], head_tree) in source_identities

    if checkout_branch == "main":
        assert head_commit in main_commits
        assert_github_ref("main")
        return

    assert checkout_branch == ""
    if head_commit in main_commits:
        # Local detached validation or a detached main-push checkout.
        assert_github_ref("main")
        return

    # GitHub checks out a synthetic PR merge that is not yet the main ref.
    # Its first parent must nevertheless be the exact current main tip.
    assert github_actions
    assert github_head_ref == branch
    assert head_parents[0] in main_commits


def _assert_release_worktree_is_clean() -> None:
    """Require every Git-relevant byte to belong to the commit under test."""

    hidden_ignore_query = (
        "ls-files",
        "-z",
        "--others",
        "--ignored",
        "--exclude-per-directory=.gitignore",
        "--",
        ":(icase,glob).gitignore",
        ":(icase,glob)**/.gitignore",
    )
    assert not _git(*hidden_ignore_query), (
        "final release checkout contains an untracked .gitignore that can conceal inputs"
    )
    dirty_queries = (
        (("diff", "--name-only", "-z", "--"), "unstaged tracked changes"),
        (("diff", "--cached", "--name-only", "-z", "--"), "staged changes"),
        (("ls-files", "--unmerged", "-z", "--"), "unmerged entries"),
        (
            ("ls-files", "-z", "--others", "--exclude-per-directory=.gitignore", "--", "."),
            "untracked files",
        ),
    )
    for command, label in dirty_queries:
        assert not _git(*command), f"final release checkout contains {label}"


def _assert_checkout_matches_state(branch: str, *, require_clean: bool = False) -> None:
    """Read exact local/remote Git identities and apply the pure contract."""

    if require_clean:
        _assert_release_worktree_is_clean()

    checkout_branch = _git("branch", "--show-current").decode("utf-8").strip()
    head_commit = (
        _git("rev-parse", "--verify", "--end-of-options", "HEAD^{commit}").decode("ascii").strip()
    )
    head_tree = (
        _git("rev-parse", "--verify", "--end-of-options", "HEAD^{tree}").decode("ascii").strip()
    )
    parent_line = _git("rev-list", "--parents", "-n", "1", "HEAD").decode("ascii").split()
    assert parent_line
    assert parent_line[0] == head_commit

    github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    github_head_ref = os.environ.get("GITHUB_HEAD_REF", "")
    _assert_checkout_identity_matches_state(
        branch,
        checkout_branch=checkout_branch,
        head_commit=head_commit,
        head_tree=head_tree,
        head_parents=tuple(parent_line[1:]),
        source_ref_identities=_source_branch_identities(
            branch,
            github_actions=github_actions,
            github_head_ref=github_head_ref,
            github_head_sha=os.environ.get("MUTMUT_GITHUB_HEAD_SHA", ""),
        ),
        main_ref_identities=_exact_branch_identities("main"),
        github_actions=github_actions,
        github_head_ref=github_head_ref,
        github_ref_name=os.environ.get("GITHUB_REF_NAME", ""),
    )


def _assert_released_provenance_identity(
    *,
    current_sprint: str,
    candidate_commit: str,
    candidate_tree: str,
    integrated_commit: str,
    integrated_tree: str,
    integrated_parents: tuple[str, ...],
    tag_object_type: str,
    tag_commit: str,
    tag_tree: str,
    housekeeping_commit: str,
    housekeeping_parents: tuple[str, ...],
    housekeeping_paths: tuple[str, ...],
) -> None:
    """Bind released housekeeping to one reviewed candidate and annotated tag."""
    sprint_backlog_path = _sprint_backlog_relative_path(current_sprint)
    allowed_housekeeping_paths = _HOUSEKEEPING_PATHS | {sprint_backlog_path}
    object_ids = (
        candidate_commit,
        candidate_tree,
        integrated_commit,
        integrated_tree,
        tag_commit,
        tag_tree,
        housekeeping_commit,
        *integrated_parents,
        *housekeeping_parents,
    )
    assert all(_GIT_OBJECT_ID.fullmatch(value) for value in object_ids)
    assert tag_object_type == "tag"
    assert tag_commit == integrated_commit
    assert tag_tree == integrated_tree == candidate_tree
    assert len(integrated_parents) == 2
    assert integrated_parents[1] == candidate_commit
    assert len({integrated_commit, *integrated_parents}) == 3
    assert housekeeping_commit != integrated_commit
    assert housekeeping_parents == (integrated_commit,)
    assert housekeeping_paths
    assert len(housekeeping_paths) == len(set(housekeeping_paths))
    assert set(housekeeping_paths) <= allowed_housekeeping_paths
    assert {
        ".sprint/state.md",
        "MEMORY.md",
        sprint_backlog_path,
        "bug_reporting/ANALYSE_MUTMUTWIN221.md",
        "bug_reporting/BUGFIXUNG_ROADMAP.md",
    } <= set(housekeeping_paths)


def _assert_released_checkout_matches_state(state: dict[str, str | bool]) -> None:
    """Resolve exact Git objects for a machine-declared released state."""
    assert state["phase"] == "released"
    tag = str(state["release_tag"])
    tag_ref = f"refs/tags/{tag}"
    candidate_commit = str(state["candidate_commit"])
    integrated_commit = str(state["integrated_commit"])
    head_commit = (
        _git("rev-parse", "--verify", "--end-of-options", "HEAD^{commit}").decode("ascii").strip()
    )
    integrated_line = (
        _git("rev-list", "--parents", "-n", "1", integrated_commit).decode("ascii").split()
    )
    housekeeping_line = _git("rev-list", "--parents", "-n", "1", "HEAD").decode("ascii").split()
    housekeeping_paths = tuple(
        name.decode("utf-8", errors="strict")
        for name in _git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            integrated_commit,
            head_commit,
        ).split(b"\0")
        if name
    )
    assert integrated_line
    assert integrated_line[0] == integrated_commit
    assert housekeeping_line
    assert housekeeping_line[0] == head_commit
    _assert_released_provenance_identity(
        current_sprint=str(state["current_sprint"]),
        candidate_commit=candidate_commit,
        candidate_tree=str(state["candidate_tree"]),
        integrated_commit=integrated_commit,
        integrated_tree=str(state["integrated_tree"]),
        integrated_parents=tuple(integrated_line[1:]),
        tag_object_type=_git("cat-file", "-t", tag_ref).decode("ascii").strip(),
        tag_commit=_git("rev-parse", "--verify", "--end-of-options", f"{tag_ref}^{{commit}}")
        .decode("ascii")
        .strip(),
        tag_tree=_git("rev-parse", "--verify", "--end-of-options", f"{tag_ref}^{{tree}}")
        .decode("ascii")
        .strip(),
        housekeeping_commit=head_commit,
        housekeeping_parents=tuple(housekeeping_line[1:]),
        housekeeping_paths=housekeeping_paths,
    )
    assert (
        _git(
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{candidate_commit}^{{tree}}",
        )
        .decode("ascii")
        .strip()
        == state["candidate_tree"]
    )


def _assert_review_statuses_match_lifecycle(
    mw_statuses: dict[str, str],
    cx_statuses: dict[str, str],
    *,
    tests_passed: bool,
    housekeeping_done: bool,
) -> None:
    """Prevent an allowlisted pending status from certifying final closure."""
    if housekeeping_done:
        assert mw_statuses["MW221-003"] == "CLOSED_PROCESS"
    else:
        assert mw_statuses["MW221-003"] == "OPEN_PROCESS"
    if not tests_passed:
        return
    assert not {
        "IMPLEMENTED_PENDING_FINAL",
        "FIX_IN_PROGRESS",
        "OPEN_PRODUCT",
    }.intersection(mw_statuses.values())
    assert set(cx_statuses.values()) == {"VERIFIED_FIXED"}
    assert {
        finding_id for finding_id, status in mw_statuses.items() if status == "OPEN_PROCESS"
    } <= {"MW221-003"}
    if housekeeping_done:
        assert "OPEN_PROCESS" not in mw_statuses.values()


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
    """Machine-read state must be coherent without pinning a transient success claim."""
    _require_git_checkout()
    version = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    state_path = _PROJECT_ROOT / ".sprint" / "state.md"
    state = _parse_state_frontmatter(state_path.read_text(encoding="utf-8"))
    target_version, branch = _assert_sprint_state_is_coherent(state, version)
    _assert_checkout_matches_state(
        branch,
        require_clean=bool(state["tests_passed"] or state["housekeeping_done"]),
    )
    if state["phase"] == "released":
        _assert_released_checkout_matches_state(state)
    if state["memory_updated"]:
        memory = (_PROJECT_ROOT / "MEMORY.md").read_text(encoding="utf-8")
        refresh_match = re.search(r"^> Last refresh: (\d{4}-\d{2}-\d{2})\.", memory, re.MULTILINE)
        assert refresh_match is not None
        assert date.fromisoformat(refresh_match.group(1)) >= date.fromisoformat(
            str(state["started_at"])
        )

    assert state["sprint_backlog_written"] is True
    current_sprint = str(state["current_sprint"])
    backlog_path = _PROJECT_ROOT / _sprint_backlog_relative_path(current_sprint)
    assert backlog_path.is_file()
    backlog = backlog_path.read_text(encoding="utf-8")
    _assert_sprint_backlog_matches_lifecycle(
        backlog,
        current_sprint=current_sprint,
        target_version=target_version,
        branch=branch,
        phase=str(state["phase"]),
    )

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
        assert f"v{target_version}" in live, (
            f"{path.relative_to(_PROJECT_ROOT)} is stale: v{target_version} missing"
        )
        _assert_live_branch_matches_state(live, branch)
        _assert_live_phase_matches_state(
            live,
            str(state["phase"]),
            target_version,
            branch,
        )
        assert "development pause" not in live.lower()
        non_archived = _without_archive(text).lower()
        assert all(claim not in non_archived for claim in forbidden_active_claims)
        assert text.index(_LIVE_END) < text.index(_ARCHIVE_START) < text.index(_ARCHIVE_END)

    for path in (
        _PROJECT_ROOT / "README.md",
        _PROJECT_ROOT / "MEMORY.md",
        _PROJECT_ROOT / ".serena" / "memories" / "project_overview.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert text.count("<!-- RELEASE_SEQUENCE:") == 1
        assert _RELEASE_SEQUENCE in text

    roadmap = _PROJECT_ROOT / "bug_reporting" / "BUGFIXUNG_ROADMAP.md"
    assert roadmap.is_file()
    for path in (
        _PROJECT_ROOT / "MEMORY.md",
        _PROJECT_ROOT / ".serena" / "memories" / "current_state.md",
    ):
        live = _marked_region(path.read_text(encoding="utf-8"), _LIVE_START, _LIVE_END)
        assert "bug_reporting/BUGFIXUNG_ROADMAP.md" in live


def test_sprint_state_contract_accepts_honest_lifecycle_transitions() -> None:
    """Development, validated-candidate and released states stay distinct."""
    in_progress: dict[str, str | bool] = {
        "current_sprint": "38",
        "sprint_goal": "v2.21.1: in progress",
        "branch": "fix/v2.21.1-windows314",
        "started_at": "2026-09-01",
        "phase": "in_progress",
        "candidate_commit": "",
        "candidate_tree": "",
        "integrated_commit": "",
        "integrated_tree": "",
        "release_tag": "",
        "housekeeping_done": False,
        "memory_updated": True,
        "github_issues_closed": False,
        "sprint_backlog_written": True,
        "semgrep_passed": False,
        "tests_passed": False,
        "documentation_updated": True,
    }
    assert _assert_sprint_state_is_coherent(in_progress, "2.21.0") == (
        "2.21.1",
        "fix/v2.21.1-windows314",
    )

    candidate = in_progress | {
        "sprint_goal": "v2.21.1: candidate validated",
        "phase": "candidate_validated",
        "tests_passed": True,
        "semgrep_passed": True,
    }
    _assert_sprint_state_is_coherent(candidate, "2.21.1")

    closed = dict.fromkeys(_STATE_KEYS, True)
    closed.update(
        {
            "current_sprint": "38",
            "sprint_goal": "v2.21.1: released",
            "branch": "main",
            "started_at": "2026-09-01",
            "phase": "released",
            "candidate_commit": "1" * 40,
            "candidate_tree": "a" * 40,
            "integrated_commit": "2" * 40,
            "integrated_tree": "a" * 40,
            "release_tag": "v2.21.1",
            "housekeeping_done": True,
        }
    )
    _assert_sprint_state_is_coherent(closed, "2.21.1")

    stale_green = in_progress | {"tests_passed": True}
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(stale_green, "2.21.0")

    premature_housekeeping = closed | {"tests_passed": False}
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(premature_housekeeping, "2.21.1")

    rolled_back = closed | {"sprint_goal": "v2.21.0: released"}
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(rolled_back, "2.21.0")

    mismatched_fix_branch = in_progress | {"branch": "fix/v2.21.2-windows314"}
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(mismatched_fix_branch, "2.21.0")

    fake_released = in_progress | {
        "sprint_goal": "v2.21.1: released",
    }
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(fake_released, "2.21.0")
    fake_published = in_progress | {
        "sprint_goal": "v2.21.1: published",
    }
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(fake_published, "2.21.0")

    fake_shipped = in_progress | {"sprint_goal": "v2.21.1: shipped"}
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(fake_shipped, "2.21.0")

    for invalid_date in ("nonsense", "20260902", "2026-W36-3"):
        malformed_date = in_progress | {"started_at": invalid_date}
        with pytest.raises(AssertionError):
            _assert_sprint_state_is_coherent(malformed_date, "2.21.0")

    for invalid_sprint in ("0", "038", "\uff13\uff18", "38/../39"):
        malformed_sprint = in_progress | {"current_sprint": invalid_sprint}
        with pytest.raises(AssertionError):
            _assert_sprint_state_is_coherent(malformed_sprint, "2.21.0")

    fake_candidate_on_main = candidate | {"branch": "main"}
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(fake_candidate_on_main, "2.21.1")

    fake_release_without_gates = closed | {
        "tests_passed": False,
        "semgrep_passed": False,
        "housekeeping_done": False,
    }
    with pytest.raises(AssertionError):
        _assert_sprint_state_is_coherent(fake_release_without_gates, "2.21.1")


def test_sprint_backlog_contract_distinguishes_candidate_and_released() -> None:
    current_sprint = "39"
    target_version = "2.21.1"
    candidate_branch = "fix/v2.21.1-windows314"
    backlog = (_PROJECT_ROOT / _sprint_backlog_relative_path(current_sprint)).read_text(
        encoding="utf-8"
    )
    branch_line = f"| **Branch** | `{candidate_branch}` |"
    main_line = "| **Branch** | `main` |"

    for phase in ("in_progress", "candidate_validated"):
        _assert_sprint_backlog_matches_lifecycle(
            backlog,
            current_sprint=current_sprint,
            target_version=target_version,
            branch=candidate_branch,
            phase=phase,
        )

    checked_candidate = backlog.replace("- [ ] ", "- [x] ", 1)
    with pytest.raises(AssertionError):
        _assert_sprint_backlog_matches_lifecycle(
            checked_candidate,
            current_sprint=current_sprint,
            target_version=target_version,
            branch=candidate_branch,
            phase="candidate_validated",
        )

    duplicate_branch = backlog.replace(branch_line, f"{branch_line}\n{main_line}", 1)
    with pytest.raises(AssertionError):
        _assert_sprint_backlog_matches_lifecycle(
            duplicate_branch,
            current_sprint=current_sprint,
            target_version=target_version,
            branch=candidate_branch,
            phase="candidate_validated",
        )

    released = backlog.replace(branch_line, main_line, 1).replace("- [ ] ", "- [x] ")
    _assert_sprint_backlog_matches_lifecycle(
        released,
        current_sprint=current_sprint,
        target_version=target_version,
        branch="main",
        phase="released",
    )

    for invalid_released in (
        released.replace("- [x] ", "- [ ] ", 1),
        released.replace(main_line, branch_line, 1),
        re.sub(r"^- \[x\] ", "- ", released, count=1, flags=re.MULTILINE),
    ):
        with pytest.raises(AssertionError):
            _assert_sprint_backlog_matches_lifecycle(
                invalid_released,
                current_sprint=current_sprint,
                target_version=target_version,
                branch="main",
                phase="released",
            )


def test_live_branch_contract_rejects_stale_or_implicit_refs() -> None:
    _assert_live_branch_matches_state("Current branch: `fix/v2.21.1-repair`.", "fix/v2.21.1-repair")
    _assert_live_branch_matches_state("Current branch: `main`.", "main")
    _assert_live_branch_matches_state(
        "Current branch: `main`; ordinary resource path `prefix/foo`.", "main"
    )

    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state("Current branch: main.", "main")
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `main`; old `fix/v2.21.1-repair`.", "main"
        )
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `main`; old `origin/fix/v2.21.1-repair`.", "main"
        )
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `main`; old `refs/heads/fix/v2.21.1-repair`.", "main"
        )
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `main`; old `refs/remotes/origin/fix/v2.21.1-repair`.",
            "main",
        )
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `main`; old `upstream/fix/v2.21.1-repair`.",
            "main",
        )
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `main`; old `refs/remotes/upstream/fix/v2.21.1-repair`.",
            "main",
        )
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `main`; old `refs/tags/fix/v2.21.1-repair`.",
            "main",
        )
    with pytest.raises(AssertionError):
        _assert_live_branch_matches_state(
            "Current branch: `fix/v2.21.1-repair`; stale `feature/old`.",
            "fix/v2.21.1-repair",
        )


def test_live_phase_contract_rejects_stale_or_transient_candidate_prose() -> None:
    in_progress = _live_state_contract("2.21.1", "fix/v2.21.1-repair", "in_progress")
    _assert_live_phase_matches_state(
        in_progress,
        "in_progress",
        "2.21.1",
        "fix/v2.21.1-repair",
    )
    candidate = _live_state_contract("2.21.1", "fix/v2.21.1-repair", "candidate_validated")
    _assert_live_phase_matches_state(
        candidate,
        "candidate_validated",
        "2.21.1",
        "fix/v2.21.1-repair",
    )

    for stale_prose in (
        "Final verification remains incomplete.",
        "Work continues and the gates await execution.",
        "Die Freigabe steht aus; die Arbeit dauert an.",
    ):
        with pytest.raises(AssertionError):
            _assert_live_phase_matches_state(
                f"{candidate}{stale_prose}\n",
                "candidate_validated",
                "2.21.1",
                "fix/v2.21.1-repair",
            )
    with pytest.raises(AssertionError):
        _assert_live_phase_matches_state(
            candidate.replace("candidate_validated", "in_progress", 1),
            "candidate_validated",
            "2.21.1",
            "fix/v2.21.1-repair",
        )


def test_released_provenance_requires_annotated_tag_and_direct_housekeeping_parent() -> None:
    current_sprint = "39"
    sprint_backlog_path = _sprint_backlog_relative_path(current_sprint)
    candidate_commit = "1" * 40
    base_commit = "2" * 40
    integrated_commit = "3" * 40
    housekeeping_commit = "4" * 40
    candidate_tree = "a" * 40
    housekeeping_paths = (
        ".sprint/state.md",
        "MEMORY.md",
        sprint_backlog_path,
        "bug_reporting/ANALYSE_MUTMUTWIN221.md",
        "bug_reporting/BUGFIXUNG_ROADMAP.md",
    )
    valid = {
        "current_sprint": current_sprint,
        "candidate_commit": candidate_commit,
        "candidate_tree": candidate_tree,
        "integrated_commit": integrated_commit,
        "integrated_tree": candidate_tree,
        "integrated_parents": (base_commit, candidate_commit),
        "tag_object_type": "tag",
        "tag_commit": integrated_commit,
        "tag_tree": candidate_tree,
        "housekeeping_commit": housekeeping_commit,
        "housekeeping_parents": (integrated_commit,),
        "housekeeping_paths": housekeeping_paths,
    }
    _assert_released_provenance_identity(**valid)

    invalid_variants = (
        {"tag_object_type": "commit"},
        {"tag_commit": candidate_commit},
        {"tag_tree": "b" * 40},
        {"integrated_parents": (base_commit, "5" * 40)},
        {"housekeeping_parents": (base_commit,)},
        {"housekeeping_parents": (integrated_commit, base_commit)},
        {"current_sprint": "38"},
        {
            "housekeeping_paths": tuple(
                path for path in housekeeping_paths if path != sprint_backlog_path
            )
        },
        {
            "housekeeping_paths": (
                *housekeeping_paths,
                "_docs/sprint backlogs/sprint_38_backlog.md",
            )
        },
        {"housekeeping_paths": (*housekeeping_paths, "src/mutmut_win/cli.py")},
    )
    for override in invalid_variants:
        with pytest.raises(AssertionError):
            _assert_released_provenance_identity(**(valid | override))


def test_checkout_identity_accepts_source_and_byte_identical_integration() -> None:
    branch = "fix/v2.21.1-repair"
    base_commit = "1" * 40
    source_commit = "2" * 40
    merge_commit = "3" * 40
    base_tree = "a" * 40
    source_tree = "b" * 40
    source_refs = ((source_commit, source_tree),)
    main_before_merge = ((base_commit, base_tree),)
    main_after_merge = ((merge_commit, source_tree),)

    _assert_checkout_identity_matches_state(
        branch,
        checkout_branch=branch,
        head_commit=source_commit,
        head_tree=source_tree,
        head_parents=(base_commit,),
        source_ref_identities=source_refs,
        main_ref_identities=main_before_merge,
    )
    _assert_checkout_identity_matches_state(
        branch,
        checkout_branch="",
        head_commit=source_commit,
        head_tree=source_tree,
        head_parents=(base_commit,),
        source_ref_identities=source_refs,
        main_ref_identities=main_before_merge,
    )

    for checkout_branch in ("main", ""):
        _assert_checkout_identity_matches_state(
            branch,
            checkout_branch=checkout_branch,
            head_commit=merge_commit,
            head_tree=source_tree,
            head_parents=(base_commit, source_commit),
            source_ref_identities=source_refs,
            main_ref_identities=main_after_merge,
        )

    _assert_checkout_identity_matches_state(
        branch,
        checkout_branch="",
        head_commit=merge_commit,
        head_tree=source_tree,
        head_parents=(base_commit, source_commit),
        source_ref_identities=source_refs,
        main_ref_identities=main_before_merge,
        github_actions=True,
        github_head_ref=branch,
        github_ref_name="135/merge",
    )
    _assert_checkout_identity_matches_state(
        branch,
        checkout_branch="",
        head_commit=merge_commit,
        head_tree=source_tree,
        head_parents=(base_commit, source_commit),
        source_ref_identities=source_refs,
        main_ref_identities=main_after_merge,
        github_actions=True,
        github_ref_name="main",
    )


def test_checkout_identity_rejects_wrong_head_tree_parent_and_github_ref() -> None:
    branch = "fix/v2.21.1-repair"
    base_commit = "1" * 40
    source_commit = "2" * 40
    merge_commit = "3" * 40
    wrong_commit = "4" * 40
    base_tree = "a" * 40
    source_tree = "b" * 40
    wrong_tree = "c" * 40
    source_refs = ((source_commit, source_tree),)
    main_before_merge = ((base_commit, base_tree),)
    main_after_merge = ((merge_commit, source_tree),)

    invalid_cases = (
        {
            "checkout_branch": branch,
            "head_commit": wrong_commit,
            "head_tree": source_tree,
            "head_parents": (base_commit,),
            "main_ref_identities": main_before_merge,
        },
        {
            "checkout_branch": branch,
            "head_commit": source_commit,
            "head_tree": wrong_tree,
            "head_parents": (base_commit,),
            "main_ref_identities": main_before_merge,
        },
        {
            "checkout_branch": "main",
            "head_commit": merge_commit,
            "head_tree": source_tree,
            "head_parents": (base_commit, wrong_commit),
            "main_ref_identities": main_after_merge,
        },
        {
            "checkout_branch": "main",
            "head_commit": merge_commit,
            "head_tree": source_tree,
            "head_parents": (base_commit, source_commit, wrong_commit),
            "main_ref_identities": main_after_merge,
        },
        {
            "checkout_branch": "main",
            "head_commit": merge_commit,
            "head_tree": source_tree,
            "head_parents": (base_commit, source_commit),
            "main_ref_identities": main_before_merge,
        },
    )
    for case in invalid_cases:
        with pytest.raises(AssertionError):
            _assert_checkout_identity_matches_state(
                branch,
                source_ref_identities=source_refs,
                **case,
            )

    with pytest.raises(AssertionError):
        _assert_checkout_identity_matches_state(
            branch,
            checkout_branch="",
            head_commit=merge_commit,
            head_tree=source_tree,
            head_parents=(base_commit, source_commit),
            source_ref_identities=source_refs,
            main_ref_identities=main_before_merge,
            github_actions=True,
            github_head_ref="fix/v2.21.1-other",
            github_ref_name="135/merge",
        )
    with pytest.raises(AssertionError):
        _assert_checkout_identity_matches_state(
            branch,
            checkout_branch="",
            head_commit=merge_commit,
            head_tree=source_tree,
            head_parents=(base_commit, source_commit),
            source_ref_identities=source_refs,
            main_ref_identities=main_after_merge,
            github_actions=True,
            github_ref_name="v2.21.1",
        )


def test_checkout_wrapper_uses_exact_local_and_remote_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch = "fix/v2.21.1-repair"
    base_commit = "1" * 40
    source_commit = "2" * 40
    base_tree = "a" * 40
    source_tree = "b" * 40
    calls: list[tuple[str, ...]] = []
    responses = {
        ("branch", "--show-current"): f"{branch}\n".encode(),
        ("rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"): (
            f"{source_commit}\n".encode()
        ),
        ("rev-parse", "--verify", "--end-of-options", "HEAD^{tree}"): (f"{source_tree}\n".encode()),
        ("rev-list", "--parents", "-n", "1", "HEAD"): (f"{source_commit} {base_commit}\n".encode()),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"refs/heads/{branch}^{{commit}}",
        ): f"{source_commit}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            "refs/heads/main^{commit}",
        ): f"{base_commit}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{source_commit}^{{commit}}",
        ): f"{source_commit}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{source_commit}^{{tree}}",
        ): f"{source_tree}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{base_commit}^{{tree}}",
        ): f"{base_tree}\n".encode(),
    }

    def fake_git(*args: str) -> bytes:
        calls.append(args)
        try:
            return responses[args]
        except KeyError:
            if args[:3] == ("rev-parse", "--verify", "--end-of-options"):
                raise subprocess.CalledProcessError(1, args) from None
            raise AssertionError(f"unexpected git invocation: {args!r}") from None

    monkeypatch.setattr(sys.modules[__name__], "_git", fake_git)
    clean_check = MagicMock()
    monkeypatch.setattr(
        sys.modules[__name__],
        "_assert_release_worktree_is_clean",
        clean_check,
    )
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)

    _assert_checkout_matches_state(branch)
    clean_check.assert_not_called()
    _assert_checkout_matches_state(branch, require_clean=True)
    clean_check.assert_called_once_with()

    assert (
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"refs/heads/{branch}^{{commit}}",
    ) in calls
    assert (
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"refs/remotes/origin/{branch}^{{commit}}",
    ) in calls
    assert (
        "rev-parse",
        "--verify",
        "--end-of-options",
        "refs/heads/main^{commit}",
    ) in calls
    assert (
        "rev-parse",
        "--verify",
        "--end-of-options",
        "refs/remotes/origin/main^{commit}",
    ) in calls


def test_github_fork_head_is_bound_by_its_exact_event_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch = "fix/v2.21.1-fork"
    source_commit = "2" * 40
    source_tree = "b" * 40
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> bytes:
        calls.append(args)
        if args == (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{source_commit}^{{commit}}",
        ):
            return f"{source_commit}\n".encode()
        if args == (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{source_commit}^{{tree}}",
        ):
            return f"{source_tree}\n".encode()
        if args[:3] == ("rev-parse", "--verify", "--end-of-options"):
            raise subprocess.CalledProcessError(1, args)
        raise AssertionError(f"unexpected git invocation: {args!r}")

    monkeypatch.setattr(sys.modules[__name__], "_git", fake_git)
    identities = _source_branch_identities(
        branch,
        github_actions=True,
        github_head_ref=branch,
        github_head_sha=source_commit,
    )

    assert identities == ((source_commit, source_tree),)
    assert calls
    with pytest.raises(AssertionError):
        _source_branch_identities(
            branch,
            github_actions=True,
            github_head_ref=branch,
            github_head_sha="not-an-object-id",
        )


@pytest.mark.parametrize(
    ("dirty_command", "label"),
    [
        (("diff", "--name-only", "-z", "--"), "unstaged tracked changes"),
        (("diff", "--cached", "--name-only", "-z", "--"), "staged changes"),
        (("ls-files", "--unmerged", "-z", "--"), "unmerged entries"),
        (
            ("ls-files", "-z", "--others", "--exclude-per-directory=.gitignore", "--", "."),
            "untracked files",
        ),
    ],
)
def test_final_release_checkout_rejects_git_relevant_dirty_bytes(
    dirty_command: tuple[str, ...],
    label: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git(*args: str) -> bytes:
        return b"dirty-path\0" if args == dirty_command else b""

    monkeypatch.setattr(sys.modules[__name__], "_git", fake_git)

    with pytest.raises(AssertionError, match=label):
        _assert_release_worktree_is_clean()


@pytest.mark.parametrize(
    "hidden_ignore",
    [
        b"src/.gitignore\0",
        b".hypothesis/.gitignore\0",
        b".import_linter_cache/.gitignore\0",
        b".mypy_cache/.gitignore\0",
        b".pytest_cache/.gitignore\0",
        b".ruff_cache/.gitignore\0",
        b".venv/.gitignore\0",
        b".venv/.GITIGNORE\0",
    ],
)
def test_final_release_checkout_rejects_untracked_ignore_control(
    hidden_ignore: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hidden_ignore_query = (
        "ls-files",
        "-z",
        "--others",
        "--ignored",
        "--exclude-per-directory=.gitignore",
        "--",
        ":(icase,glob).gitignore",
        ":(icase,glob)**/.gitignore",
    )

    def fake_git(*args: str) -> bytes:
        return hidden_ignore if args == hidden_ignore_query else b""

    monkeypatch.setattr(sys.modules[__name__], "_git", fake_git)

    with pytest.raises(AssertionError, match=r"untracked \.gitignore"):
        _assert_release_worktree_is_clean()


def test_hidden_ignore_query_matches_case_variants(tmp_path: Path) -> None:
    git = shutil.which("git")
    assert git is not None, "release-contract tests require Git"
    repository = tmp_path / "case-insensitive-ignore-query"
    repository.mkdir()
    subprocess.run(  # noqa: S603 - shutil.which resolves the trusted Git executable
        [git, "init", "--quiet"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    (repository / ".gitignore").write_text("cache/.GITIGNORE\n", encoding="utf-8")
    cache = repository / "cache"
    cache.mkdir()
    (cache / ".GITIGNORE").write_text("*.hidden\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603 - shutil.which resolves the trusted Git executable
        [
            git,
            "ls-files",
            "-z",
            "--others",
            "--ignored",
            "--exclude-per-directory=.gitignore",
            "--",
            ":(icase,glob).gitignore",
            ":(icase,glob)**/.gitignore",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
    )

    assert result.stdout == b"cache/.GITIGNORE\0"


def test_in_suite_import_linter_disables_checkout_local_cache() -> None:
    source = (_PROJECT_ROOT / "tests" / "test_architecture.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "test_import_linter_contracts_hold"
    )
    script_assignments = [
        node
        for node in function.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "script" for target in node.targets)
    ]
    assert len(script_assignments) == 1
    script_names = [
        node for node in ast.walk(function) if isinstance(node, ast.Name) and node.id == "script"
    ]
    assert len(script_names) == 2
    assert sum(isinstance(node.ctx, ast.Store) for node in script_names) == 1
    assert sum(isinstance(node.ctx, ast.Load) for node in script_names) == 1
    script_assignment = script_assignments[0]
    embedded = ast.parse(ast.literal_eval(script_assignment.value))
    expected_embedded = ast.parse(
        "from importlinter.cli import lint_imports\n"
        "import sys\n"
        "sys.exit(lint_imports(no_cache=True))"
    )
    assert ast.dump(embedded, include_attributes=False) == ast.dump(
        expected_embedded, include_attributes=False
    )

    result_assignment = next(
        node
        for node in function.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "result" for target in node.targets)
    )
    assert isinstance(result_assignment.value, ast.Call)
    invocation = result_assignment.value
    assert isinstance(invocation.func, ast.Attribute)
    assert isinstance(invocation.func.value, ast.Name)
    assert (invocation.func.value.id, invocation.func.attr) == ("subprocess", "run")
    assert len(invocation.args) == 1
    argv = invocation.args[0]
    assert isinstance(argv, ast.List)
    expected_argv = ast.parse("[sys.executable, '-c', script]", mode="eval").body
    assert ast.dump(argv, include_attributes=False) == ast.dump(
        expected_argv, include_attributes=False
    )


def test_final_release_checkout_accepts_only_ignored_untracked_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> bytes:
        calls.append(args)
        return b""

    monkeypatch.setattr(sys.modules[__name__], "_git", fake_git)

    _assert_release_worktree_is_clean()

    assert calls == [
        (
            "ls-files",
            "-z",
            "--others",
            "--ignored",
            "--exclude-per-directory=.gitignore",
            "--",
            ":(icase,glob).gitignore",
            ":(icase,glob)**/.gitignore",
        ),
        ("diff", "--name-only", "-z", "--"),
        ("diff", "--cached", "--name-only", "-z", "--"),
        ("ls-files", "--unmerged", "-z", "--"),
        ("ls-files", "-z", "--others", "--exclude-per-directory=.gitignore", "--", "."),
    ]


def test_checkout_wrapper_accepts_exact_github_pr_merge_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch = "fix/v2.21.1-repair"
    base_commit = "1" * 40
    source_commit = "2" * 40
    merge_commit = "3" * 40
    base_tree = "a" * 40
    source_tree = "b" * 40
    responses = {
        ("branch", "--show-current"): b"",
        ("rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"): (
            f"{merge_commit}\n".encode()
        ),
        ("rev-parse", "--verify", "--end-of-options", "HEAD^{tree}"): (f"{source_tree}\n".encode()),
        ("rev-list", "--parents", "-n", "1", "HEAD"): (
            f"{merge_commit} {base_commit} {source_commit}\n".encode()
        ),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"refs/remotes/origin/{branch}^{{commit}}",
        ): f"{source_commit}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            "refs/remotes/origin/main^{commit}",
        ): f"{base_commit}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{source_commit}^{{commit}}",
        ): f"{source_commit}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{source_commit}^{{tree}}",
        ): f"{source_tree}\n".encode(),
        (
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{base_commit}^{{tree}}",
        ): f"{base_tree}\n".encode(),
    }

    def fake_git(*args: str) -> bytes:
        try:
            return responses[args]
        except KeyError:
            if args[:3] == ("rev-parse", "--verify", "--end-of-options"):
                raise subprocess.CalledProcessError(1, args) from None
            raise AssertionError(f"unexpected git invocation: {args!r}") from None

    monkeypatch.setattr(sys.modules[__name__], "_git", fake_git)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_HEAD_REF", branch)
    monkeypatch.setenv("GITHUB_REF_NAME", "135/merge")
    monkeypatch.setenv("MUTMUT_GITHUB_HEAD_SHA", source_commit)

    _assert_checkout_matches_state(branch)

    monkeypatch.setenv("GITHUB_HEAD_REF", "fix/v2.21.1-other")
    with pytest.raises(AssertionError):
        _assert_checkout_matches_state(branch)


def test_review_status_contract_rejects_pending_final_claims() -> None:
    mw_statuses = {
        "MW221-001": "VERIFIED_FIXED",
        "MW221-003": "OPEN_PROCESS",
    }
    cx_statuses = {"CX221-001": "VERIFIED_FIXED"}
    _assert_review_statuses_match_lifecycle(
        mw_statuses,
        cx_statuses,
        tests_passed=True,
        housekeeping_done=False,
    )

    with pytest.raises(AssertionError):
        _assert_review_statuses_match_lifecycle(
            mw_statuses | {"MW221-001": "IMPLEMENTED_PENDING_FINAL"},
            cx_statuses,
            tests_passed=True,
            housekeeping_done=False,
        )
    with pytest.raises(AssertionError):
        _assert_review_statuses_match_lifecycle(
            mw_statuses,
            cx_statuses | {"CX221-001": "IMPLEMENTED_PENDING_FINAL"},
            tests_passed=True,
            housekeeping_done=False,
        )
    with pytest.raises(AssertionError):
        _assert_review_statuses_match_lifecycle(
            mw_statuses,
            cx_statuses,
            tests_passed=True,
            housekeeping_done=True,
        )
    with pytest.raises(AssertionError):
        _assert_review_statuses_match_lifecycle(
            mw_statuses | {"MW221-003": "CLOSED_PROCESS"},
            cx_statuses,
            tests_passed=True,
            housekeeping_done=False,
        )

    _assert_review_statuses_match_lifecycle(
        mw_statuses | {"MW221-003": "CLOSED_PROCESS"},
        cx_statuses,
        tests_passed=True,
        housekeeping_done=True,
    )


def test_review_reports_bind_complete_follow_up_findings_and_status() -> None:
    """Review ledgers must be structurally complete without certifying their prose."""

    analysis = (_PROJECT_ROOT / "bug_reporting" / "ANALYSE_MUTMUTWIN220.md").read_text(
        encoding="utf-8"
    )
    follow_up = (_PROJECT_ROOT / "bug_reporting" / "ANALYSE_MUTMUTWIN221.md").read_text(
        encoding="utf-8"
    )
    roadmap = (_PROJECT_ROOT / "bug_reporting" / "BUGFIXUNG_ROADMAP.md").read_text(encoding="utf-8")
    expected_ids = {f"MW220-{number:03d}" for number in range(1, 116)}
    assert set(re.findall(r"MW220-\d{3}", analysis)) == expected_ids
    assert analysis.count("<!-- MW221_SCOPE_ADDENDUM_START -->") == 1
    assert analysis.count("<!-- MW221_SCOPE_ADDENDUM_END -->") == 1

    expected_follow_up_ids = {f"MW221-{number:03d}" for number in range(1, 47)}
    follow_up_rows = list(
        re.finditer(
            r"^\| (?P<id>MW221-\d{3}) \| P[012] \| (?P<status>[A-Z_]+) \|.*\|$",
            follow_up,
            flags=re.MULTILINE,
        )
    )
    assert {match.group("id") for match in follow_up_rows} == expected_follow_up_ids
    assert len(follow_up_rows) == len(expected_follow_up_ids)
    assert {match.group("status") for match in follow_up_rows} <= _MW221_STATUSES
    mw_statuses = {match.group("id"): match.group("status") for match in follow_up_rows}

    expected_codex_ids = {f"CX221-{number:03d}" for number in range(1, 67)}
    codex_rows = list(
        re.finditer(
            r"^\| (?P<id>CX221-\d{3}) \| (?P<priority>P[012]) \| "
            r"(?P<status>[A-Z_]+) \|.*\|$",
            follow_up,
            flags=re.MULTILINE,
        )
    )
    assert {match.group("id") for match in codex_rows} == expected_codex_ids
    assert len(codex_rows) == len(expected_codex_ids)
    assert {match.group("status") for match in codex_rows} <= _CX221_STATUSES
    cx_statuses = {match.group("id"): match.group("status") for match in codex_rows}
    cx_priorities = {match.group("id"): match.group("priority") for match in codex_rows}
    assert {finding_id for finding_id, priority in cx_priorities.items() if priority == "P0"} == {
        "CX221-027",
        "CX221-059",
    }
    assert {finding_id for finding_id, priority in cx_priorities.items() if priority == "P2"} == {
        "CX221-033",
        "CX221-035",
        "CX221-039",
        "CX221-046",
        "CX221-062",
    }
    state = _parse_state_frontmatter(
        (_PROJECT_ROOT / ".sprint" / "state.md").read_text(encoding="utf-8")
    )
    if not state["tests_passed"]:
        assert set(cx_statuses.values()) == {"IMPLEMENTED_PENDING_FINAL"}
    _assert_review_statuses_match_lifecycle(
        mw_statuses,
        cx_statuses,
        tests_passed=bool(state["tests_passed"]),
        housekeeping_done=bool(state["housekeeping_done"]),
    )
    roadmap_ids = re.findall(
        r"^[ \t]*\|?[ \t]*(CX221-\d{3})[ \t]*\|",
        roadmap,
        flags=re.MULTILINE,
    )
    assert set(roadmap_ids) == expected_codex_ids
    assert len(roadmap_ids) == len(expected_codex_ids)
    assert "66 getrennt geführten Codex-Follow-up-Findings" in roadmap
    assert "ANALYSE_MUTMUTWIN221.md" in roadmap
    assert "Windows und exakt CPython 3.14.7" in follow_up
    assert "2 P0, 59 P1 und 5 P2" in follow_up
    assert "2 P0, 59 P1 und 5 P2" in roadmap
    assert "gelockte Repository-`.venv` binden" not in roadmap

    expected_provenance = _expected_release_tool_provenance()
    for report in (follow_up, roadmap):
        dates = re.findall(r"^\*\*Stand:\*\* (\d{4}-\d{2}-\d{2})$", report, re.MULTILINE)
        assert dates == ["2026-09-07"]
        assert date.fromisoformat(dates[0]) >= date(2026, 9, 7)
        assert _release_tool_provenance(report) == expected_provenance
        assert "a2fcf298b84d3d8498a3d718bb63f0abe26823bf68a11f0f439620f8f2f878f0" not in report
        assert "Zizmor 1.30.0 ZIP" not in report


def test_release_tool_provenance_rejects_swapped_or_mislabeled_digests() -> None:
    report = (_PROJECT_ROOT / "bug_reporting" / "ANALYSE_MUTMUTWIN221.md").read_text(
        encoding="utf-8"
    )
    expected = _expected_release_tool_provenance()
    actionlint = expected[("Native GitHub asset", "actionlint 1.7.12 ZIP")]
    shellcheck = expected[("Native GitHub asset", "ShellCheck 0.11.0 ZIP")]
    swapped = report.replace(actionlint, "HASH_PLACEHOLDER", 1)
    swapped = swapped.replace(shellcheck, actionlint, 1).replace("HASH_PLACEHOLDER", shellcheck, 1)
    assert _release_tool_provenance(swapped) != expected

    mislabeled = report.replace("actionlint 1.7.12 ZIP", "actionlint 1.7.13 ZIP", 1)
    assert _release_tool_provenance(mislabeled) != expected


def test_release_tool_provenance_rejects_missing_duplicate_extra_or_free_hash_rows() -> None:
    report = (_PROJECT_ROOT / "bug_reporting" / "ANALYSE_MUTMUTWIN221.md").read_text(
        encoding="utf-8"
    )
    region = _marked_region(
        report,
        _RELEASE_TOOL_PROVENANCE_START,
        _RELEASE_TOOL_PROVENANCE_END,
    )
    row = next(line for line in region.splitlines() if "actionlint 1.7.12 ZIP" in line)

    for invalid in (
        report.replace(f"{row}\n", "", 1),
        report.replace(f"{row}\n", f"{row}\n{row}\n", 1),
        report.replace(
            _RELEASE_TOOL_PROVENANCE_END,
            f"| Native GitHub asset | extra 1.0 ZIP | `{'0' * 64}` |\n"
            f"{_RELEASE_TOOL_PROVENANCE_END}",
            1,
        ),
        report.replace(f"{row}\n", "", 1) + f"\nfree digest: {row}\n",
    ):
        with pytest.raises(AssertionError):
            _release_tool_provenance(invalid)


def test_active_consumer_docs_share_the_canonical_release_pin() -> None:
    """Every active install command must follow the canonical guide release."""

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
    installed_version = _single_match_version(
        r'^uv add "mutmut-win @ git\+https://github\.com/pgm1980/'
        r'mutmut-win\.git@v(\d+\.\d+\.\d+)" --dev$',
        text,
        label="canonical guide command",
    )
    expected_output_version = _single_match_version(
        r"^Erwartete Ausgabe: `mutmut-win, version (\d+\.\d+\.\d+)`$",
        text,
        label="canonical guide expected output",
    )
    assert expected_output_version == installed_version
    sprint_state = _parse_state_frontmatter(
        (_PROJECT_ROOT / ".sprint" / "state.md").read_text(encoding="utf-8")
    )
    final_release_state = bool(sprint_state["tests_passed"] or sprint_state["housekeeping_done"])
    _assert_active_ref_matches_release_stage(
        version,
        installed_version,
        final=final_release_state,
    )

    readme = (_PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    readme_pip_version = _single_match_version(
        r'^pip install "mutmut-win @ git\+https://github\.com/pgm1980/'
        r'mutmut-win\.git@v(\d+\.\d+\.\d+)"$',
        readme,
        label="README pip command",
    )
    readme_uv_version = _single_match_version(
        r'^uv add "mutmut-win @ git\+https://github\.com/pgm1980/'
        r'mutmut-win\.git@v(\d+\.\d+\.\d+)" --dev$',
        readme,
        label="README uv command",
    )
    assert readme_pip_version == readme_uv_version == installed_version

    claude = (_PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    claude_dependency_version = _single_match_version(
        r'^[ \t]*"mutmut-win @ git\+https://github\.com/pgm1980/'
        r'mutmut-win\.git@v(\d+\.\d+\.\d+)",$',
        claude,
        label="CLAUDE dependency",
    )
    claude_uv_version = _single_match_version(
        r'^uv add "mutmut-win @ git\+https://github\.com/pgm1980/'
        r'mutmut-win\.git@v(\d+\.\d+\.\d+)" --dev$',
        claude,
        label="CLAUDE uv command",
    )
    assert claude_dependency_version == claude_uv_version == installed_version
    assert "werden deren Mutanten ehrlich als `no tests` verbucht" not in text
    assert ".pth`-Datei temporär umbenennen" not in text


def test_immutable_release_docs_do_not_claim_live_publication_state() -> None:
    """Bind immutable docs to one neutral external-publication contract."""
    version = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    marker = f"v{version}".casefold()
    paths = (
        _PROJECT_ROOT / "README.md",
        _PROJECT_ROOT / "CLAUDE.md",
        _PROJECT_ROOT / "MEMORY.md",
        _PROJECT_ROOT / ".sprint" / "state.md",
        _PROJECT_ROOT / ".serena" / "memories" / "current_state.md",
        _PROJECT_ROOT / ".serena" / "memories" / "project_overview.md",
        _PROJECT_ROOT / "_config" / "mutmut-win-install.md",
        _PROJECT_ROOT / "_docs" / "installation" / "mutmut-win-install.md",
    )
    for path in paths:
        raw_text = path.read_text(encoding="utf-8")
        assert raw_text.count(_PUBLICATION_START) == 1, path.relative_to(_PROJECT_ROOT)
        assert raw_text.count(_PUBLICATION_END) == 1, path.relative_to(_PROJECT_ROOT)
        assert raw_text.count(_PUBLICATION_STATE) == 1, path.relative_to(_PROJECT_ROOT)
        assert _marked_region(raw_text, _PUBLICATION_START, _PUBLICATION_END) == (
            f"\n{_PUBLICATION_STATE}\n{_PUBLICATION_SENTENCE.format(version=version)}\n"
        )
        _assert_publication_references_are_structural(raw_text, version)
        text = raw_text.casefold()
        assert marker in text, path.relative_to(_PROJECT_ROOT)


@pytest.mark.parametrize(
    "claim",
    [
        "Release v2.21.1 is live.",
        "Die Version v2.21.1 wurde publiziert.",
        "v2.21.1 has not been released.",
        "v2.21.1 is released.",
        "Published release: v2.21.1.",
        "Published release: V2.21.1.",
        "The release is live for @v2.21.1 now.",
        "The GitHub release for 2.21.1 exists.",
        "v2.21.1\n\nis released.",
        "https://github.com/pgm1980/mutmut-win.git@v2.21.1 is released.",
        "The published branch is fix/v2.21.1-release-complete.",
        "<!-- RELEASE_TARGET: v2.21.1 -->\nThis target is released.",
    ],
)
def test_publication_contract_rejects_claims_in_every_lifecycle_phase(claim: str) -> None:
    text = f"{_publication_contract('2.21.1')}\n{claim}\n"
    with pytest.raises(AssertionError):
        _assert_publication_references_are_structural(text, "2.21.1")


def test_release_stage_ref_rejects_non_adjacent_or_cross_series_versions() -> None:
    """Candidate prose cannot authorize an arbitrary stale or future ref."""

    _assert_active_ref_matches_release_stage("2.21.2", "2.21.2")
    _assert_active_ref_matches_release_stage("2.21.2", "2.21.1")
    for invalid in ("2.21.0", "2.21.3", "2.20.2", "3.21.1"):
        with pytest.raises(AssertionError):
            _assert_active_ref_matches_release_stage("2.21.2", invalid)

    _assert_active_ref_matches_release_stage("2.21.2", "2.21.2", final=True)
    with pytest.raises(AssertionError):
        _assert_active_ref_matches_release_stage("2.21.2", "2.21.1", final=True)
    with pytest.raises(AssertionError):
        _assert_active_ref_matches_release_stage("2.21.0", "2.21.0", final=True)


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

    assert "==3.14.7" in claude
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
        "56d652215797acef3307d59f7ea9849c4146e9b71aa9d62f5c7427598e813da4"
    )


def test_python_metadata_matches_exact_windows_runtime_support() -> None:
    pyproject = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    lock = tomllib.loads((_PROJECT_ROOT / "uv.lock").read_text(encoding="utf-8"))
    readme = (_PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    contract_docs = tuple(
        path.read_text(encoding="utf-8")
        for path in (
            _PROJECT_ROOT / "_docs" / "architecture spec" / "architecture_specification.md",
            _PROJECT_ROOT / "_docs" / "design spec" / "software_design_spec.md",
            _PROJECT_ROOT / "_docs" / "design spec" / "software_design_specification.md",
        )
    )

    locked_build_backend = ["hatchling==1.32.0", "editables==0.5"]
    assert pyproject["build-system"]["requires"] == locked_build_backend
    assert pyproject["dependency-groups"]["build"] == locked_build_backend
    assert pyproject["dependency-groups"]["security"] == ["semgrep==1.175.0"]
    locked_release_tools = [
        "check-wheel-contents==0.6.3",
        "pyflakes==3.4.0",
        "twine==7.0.0",
        "zizmor==1.30.0",
    ]
    assert pyproject["dependency-groups"]["release"] == locked_release_tools
    assert lock["version"] == 1
    assert lock["revision"] == 3
    locked_projects = [package for package in lock["package"] if package["name"] == "mutmut-win"]
    assert len(locked_projects) == 1
    locked_project = locked_projects[0]
    assert locked_project["source"] == {"editable": "."}
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
    release_names = [requirement.partition("==")[0] for requirement in locked_release_tools]
    assert locked_project["dev-dependencies"]["release"] == [
        {"name": name} for name in release_names
    ]
    assert locked_project["metadata"]["requires-dev"]["release"] == [
        {"name": name, "specifier": requirement.removeprefix(name)}
        for name, requirement in zip(release_names, locked_release_tools, strict=True)
    ]
    production_names = {dependency["name"] for dependency in locked_project["dependencies"]}
    assert production_names.isdisjoint(release_names)
    release_wheel_contract = {
        "check-wheel-contents": (
            "0.6.3",
            "check_wheel_contents-0.6.3.tar.gz",
            "sha256:10e6939e2fe4e6ce1edf2ff6ec6157808677e80782e78021ae139dd88473a442",
            "check_wheel_contents-0.6.3-py3-none-any.whl",
            "sha256:5ae39c8c434b972f0740d04610759168590713175aab584b012b1b84f6771874",
        ),
        "pyflakes": (
            "3.4.0",
            "pyflakes-3.4.0.tar.gz",
            "sha256:b24f96fafb7d2ab0ec5075b7350b3d2d2218eab42003821c06344973d3ea2f58",
            "pyflakes-3.4.0-py2.py3-none-any.whl",
            "sha256:f742a7dbd0d9cb9ea41e9a24a918996e8170c799fa528688d40dd582c8265f4f",
        ),
        "twine": (
            "7.0.0",
            "twine-7.0.0.tar.gz",
            "sha256:85cdb29c518efef867360ae4acd4b0dfd61c8654a22fca08e6f8539f05022177",
            "twine-7.0.0-py3-none-any.whl",
            "sha256:b854164df26db268af05f49aa5c0344b10e27a494343ff05b1e0bad3b135f5a7",
        ),
        "zizmor": (
            "1.30.0",
            "zizmor-1.30.0.tar.gz",
            "sha256:9a17ac3bb043afbbd9d3c8b6f309fa5b319c6a32e3259fbaf050f6fcd3d0a9cd",
            "zizmor-1.30.0-py3-none-win_amd64.whl",
            "sha256:ca321b5b1cb85d08ac0c3c86275bfd5a6b5564c176437e3b41e10bd1e4463296",
        ),
    }
    for package_name, (
        package_version,
        sdist_filename,
        sdist_hash,
        wheel_filename,
        wheel_hash,
    ) in release_wheel_contract.items():
        locked_packages = [
            package for package in lock["package"] if package["name"] == package_name
        ]
        assert len(locked_packages) == 1
        locked_package = locked_packages[0]
        assert locked_package["version"] == package_version
        assert locked_package["source"] == {"registry": "https://pypi.org/simple"}
        sdist_url = locked_package["sdist"]["url"]
        assert sdist_url.startswith("https://files.pythonhosted.org/packages/")
        assert "?" not in sdist_url
        assert "#" not in sdist_url
        assert sdist_url.rsplit("/", 1)[-1] == sdist_filename
        assert locked_package["sdist"]["hash"] == sdist_hash
        matching_wheels = [
            wheel
            for wheel in locked_package["wheels"]
            if wheel["url"].rsplit("/", 1)[-1] == wheel_filename
        ]
        assert len(matching_wheels) == 1
        assert matching_wheels[0]["url"].startswith("https://files.pythonhosted.org/packages/")
        assert "?" not in matching_wheels[0]["url"]
        assert "#" not in matching_wheels[0]["url"]
        assert matching_wheels[0]["hash"] == wheel_hash
        assert all(wheel["hash"].startswith("sha256:") for wheel in locked_package["wheels"])
    locked_zizmor = next(package for package in lock["package"] if package["name"] == "zizmor")
    linux_zizmor_wheels = [
        wheel
        for wheel in locked_zizmor["wheels"]
        if wheel["url"].endswith("/zizmor-1.30.0-py3-none-manylinux_2_28_x86_64.whl")
    ]
    assert len(linux_zizmor_wheels) == 1
    assert linux_zizmor_wheels[0]["hash"] == (
        "sha256:9c08a7c34b33ed6f9a3a3d28fcf8c64e3e078c53c51bc9ce05c32ec3ba7feae9"
    )
    assert project["requires-python"] == "==3.14.7"
    assert lock["requires-python"] == "==3.14.7"
    assert "Operating System :: Microsoft :: Windows" in project["classifiers"]
    assert "Programming Language :: Python :: Implementation :: CPython" in project["classifiers"]
    assert "Programming Language :: Python :: 3.14" in project["classifiers"]
    for unsupported_version in ("3.12", "3.13"):
        assert (
            f"Programming Language :: Python :: {unsupported_version}" not in project["classifiers"]
        )
    assert "exactly CPython 3.14.7 on Windows" in readme
    assert "WSL/Linux and macOS) are\nexplicitly unsupported" in readme
    assert "`st_ino == 0`" in readme
    for filesystem_boundary in ("exFAT", "SMB", "OneDrive", "reparse"):
        assert filesystem_boundary in readme
    assert "fails closed" in readme
    assert "uv sync --locked --only-group security --no-install-project" in readme
    assert "uv run --no-sync python -I scripts/semgrep_release_gate.py" in readme
    for contract_doc in contract_docs:
        assert _EXACT_RUNTIME_CONTRACT in contract_doc
        assert _SOURCE_ENCODING_CONTRACT in contract_doc
        assert "GitHub Release" in contract_doc
        for stale_contract in (
            "3.14.3",
            "Python >=3.11",
            "Python >= 3.11",
            "Python ≥3.11",
            "Python >=3.12",
            "Python >= 3.12",
            "Python ≥3.12",
            "Non-Windows: `ImportError`",
            "PyPI Distribution",
            "PyPI Source",
            "uv publish",
        ):
            assert stale_contract not in contract_doc


def test_active_scope_release_and_backlog_docs_are_structurally_current() -> None:
    architecture = (
        _PROJECT_ROOT / "_docs" / "architecture spec" / "architecture_specification.md"
    ).read_text(encoding="utf-8")
    design = (_PROJECT_ROOT / "_docs" / "design spec" / "software_design_spec.md").read_text(
        encoding="utf-8"
    )
    product = (_PROJECT_ROOT / "_docs" / "product backlog" / "product_backlog.md").read_text(
        encoding="utf-8"
    )
    sprint = (_PROJECT_ROOT / "_docs" / "sprint backlogs" / "sprint_39_backlog.md").read_text(
        encoding="utf-8"
    )
    codebase = (_PROJECT_ROOT / ".serena" / "memories" / "codebase_structure.md").read_text(
        encoding="utf-8"
    )
    checklist = (_PROJECT_ROOT / ".serena" / "memories" / "task_completion_checklist.md").read_text(
        encoding="utf-8"
    )
    commands = (_PROJECT_ROOT / ".serena" / "memories" / "suggested_commands.md").read_text(
        encoding="utf-8"
    )
    claude = (_PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    operator = (
        _PROJECT_ROOT / "_docs" / "nextgen_roadmap" / "MUTMUT_WIN_OPERATOR_ROADMAP.md"
    ).read_text(encoding="utf-8")

    build_contract = architecture.split("### 6.3 Build & Distribution", 1)[1].split("---", 1)[0]
    for required in (
        "uv sync --locked --extra dev --group build --no-build-isolation",
        "Zwei-Parent-Merge",
        "byteidentisch",
        "SOURCE_DATE_EPOCH",
        "--offline",
        "SHA256SUMS",
        "Windows-/CPython-3.14.7",
        "annotiertes Tag",
        "GitHub Release",
        _RELEASE_SEQUENCE,
    ):
        assert required in build_contract
    for unbound in ("\nuv sync\n", "\nuv run pytest\n", "\nuv build\n"):
        assert unbound not in build_contract

    assert "mutmut auf Linux" not in design
    assert "Benchmark ohne Linux-Supportzusage" not in design
    assert "Windows mit exakt CPython 3.14.7" in design

    assert product.startswith(
        "# Product Backlog - mutmut-win\n".replace(" - ", " \N{EM DASH} ")
        + "\n**Version:** 3.0.0\n**Datum:** 2026-09-07\n**Status:** Active\n"
    )
    velocity_rows = re.findall(
        r"^\| Sprint \d+ \| (?P<planned>\d+) \| (?P<done>\d+) \|",
        product,
        flags=re.MULTILINE,
    )
    assert sum(int(planned) for planned, _done in velocity_rows) == 650
    assert sum(int(done) for _planned, done in velocity_rows) == 625
    assert (
        "**Historische numerisch erfasste Summe bis einschließlich Sprint 36:** 650 SP\n"
        "geplant - 625 SP erledigt (96 %).".replace(" - ", " \N{EM DASH} ")
    ) in product
    active_dod = product.split("## Definition of Done (DoD)", 1)[1].split(
        "## Epics und Sprint-Zuordnung", 1
    )[0]
    assert "- [x]" not in active_dod.casefold()
    assert "historischer Snapshot, Stand 2026-09-07" in product
    assert "vor Sprint- oder Releaseabschluss\nextern live neu zu prüfen" in product

    assert codebase.startswith("# Codebase Structure & Layer Architecture (v2.21.1 / Sprint 39)")
    assert (
        "volatile\n> LOC, module-size, file-count, and suite-count snapshots "
        "are intentionally\n> omitted" in codebase
    )
    assert "Suite size" not in codebase
    assert not re.search(r"(?:~\s*)?\d[\d.]*k? LOC|\b\d+ modules\b", codebase)
    assert "GitHub Actions defines Windows/CPython-3.14.7" in codebase
    assert "No GitHub Actions CI" not in codebase

    assert "Binding runtime contract:** Windows with exactly CPython 3.14.7" in operator
    assert "Regex-Implementierung = stringbasierter Class-Span-Tokenizer" in operator
    assert "ursprünglich erwogene private `re._parser`-API" in operator
    assert "</content>" not in operator

    for local_gate_doc in (claude, product, sprint, checklist, commands):
        assert _NATIVE_RELEASE_SYNC in local_gate_doc
        assert _NATIVE_RELEASE_GATE in local_gate_doc
        assert "Zizmor 1.30.0" in local_gate_doc
        assert "regular" in local_gate_doc
        assert "pedantic" in local_gate_doc
        for hardening_flag in ("--strict-collection", "--no-config", "--no-ignores"):
            assert hardening_flag in local_gate_doc
        assert "kein viertes Manifest" in local_gate_doc or (
            "not a fourth native manifest asset" in local_gate_doc
        )

    for github_only_doc in (
        architecture,
        design,
        sprint,
        codebase,
    ):
        pypi_lines = [
            line.casefold() for line in github_only_doc.splitlines() if "pypi" in line.casefold()
        ]
        assert pypi_lines
        assert all(
            any(
                negation in line
                for negation in ("kein", "nicht", " no ", " not ", "ausgeschlossen")
            )
            for line in pypi_lines
        )


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
    assert license_text.splitlines().count(_CPYTHON_DERIVATIVE_HEADING) == 1
    assert license_text.splitlines().count(_PSF_LICENSE_HEADING) == 1
    assert license_text.index(_CPYTHON_DERIVATIVE_HEADING) < license_text.index(
        _PSF_LICENSE_HEADING
    )
    assert (
        'The phrase "Portions adapted from CPython 3.12-3.14" describes source provenance '
        "only; it does not declare a supported runtime range."
    ) in license_text
    assert (
        "The supported and audited product runtime is Windows with exactly CPython 3.14.7; "
        "retained POSIX implementation code is outside the product contract."
    ) in license_text
    assert "audited for CPython 3.12-3.14" not in license_text
    assert _LICENSE_EXPRESSION in readme
    derivative_license = (
        _CPYTHON_DERIVATIVE_HEADING + license_text.split(_CPYTHON_DERIVATIVE_HEADING, 1)[1]
    )
    normalized_derivative_license = derivative_license.replace("\r\n", "\n").rstrip()
    assert hashlib.sha256(normalized_derivative_license.encode()).hexdigest() == (
        _CPYTHON_DERIVATIVE_SHA256
    )
    psf_license = _PSF_LICENSE_HEADING + license_text.split(_PSF_LICENSE_HEADING, 1)[1]
    normalized_psf_license = psf_license.replace("\r\n", "\n").rstrip()
    assert hashlib.sha256(normalized_psf_license.encode()).hexdigest() == _PSF_LICENSE_SHA256


def test_runtime_scope_comments_do_not_reintroduce_unsupported_platforms() -> None:
    kill_proc_source = (
        _PROJECT_ROOT / "tests" / "integration" / "test_kill_proc_tree.py"
    ).read_text(encoding="utf-8")
    supported_comment = "project requires exactly CPython 3.14.7 on Windows"
    assert kill_proc_source.count(supported_comment) == 2
    assert "project requires Python >=3.12" not in kill_proc_source

    operator_roadmap = (
        _PROJECT_ROOT / "_docs" / "nextgen_roadmap" / "MUTMUT_WIN_OPERATOR_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "exactly CPython 3.14.7" in operator_roadmap
    assert ("3.12" + chr(0x2013) + "3.14") not in operator_roadmap
    assert ("3.12" + chr(0x2192) + "3.14") not in operator_roadmap

    constants = (_PROJECT_ROOT / "src" / "mutmut_win" / "constants.py").read_text(encoding="utf-8")
    assert "supported Windows runtime" in constants
    assert "no POSIX runtime or CI-support commitment" in constants
    assert "kept for WSL/Linux CI" not in constants


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

        native_gate_members = [
            member
            for member in sdist.getmembers()
            if member.isfile() and member.name == f"{sdist_root}/scripts/release_native_gate.py"
        ]
        assert len(native_gate_members) == 1
        native_gate_stream = sdist.extractfile(native_gate_members[0])
        assert native_gate_stream is not None
        assert (
            native_gate_stream.read()
            == (_PROJECT_ROOT / "scripts/release_native_gate.py").read_bytes()
        )

        native_manifest_members = [
            member
            for member in sdist.getmembers()
            if member.isfile() and member.name == f"{sdist_root}/scripts/release_native_tools.json"
        ]
        assert len(native_manifest_members) == 1
        native_manifest_stream = sdist.extractfile(native_manifest_members[0])
        assert native_manifest_stream is not None
        assert (
            native_manifest_stream.read()
            == (_PROJECT_ROOT / "scripts/release_native_tools.json").read_bytes()
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


def test_real_cli_unit_surfaces_use_an_external_workspace_fixture() -> None:
    fixture_source = (_PROJECT_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "def isolated_cli_workspace(" in fixture_source
    assert 'workspace = tmp_path / "cli-workspace"' in fixture_source
    assert "monkeypatch.chdir(workspace)" in fixture_source

    marker = 'pytestmark = pytest.mark.usefixtures("isolated_cli_workspace")'
    for relative_path in (
        "tests/unit/test_ci_output_discipline.py",
        "tests/unit/test_cli.py",
        "tests/unit/test_closure_117.py",
        "tests/unit/test_contract_120.py",
        "tests/unit/test_db_purge.py",
        "tests/unit/test_exception_hygiene_114.py",
        "tests/unit/test_interrupt_honesty.py",
        "tests/unit/test_pool_collapse_127.py",
        "tests/unit/test_surface_hardening_220.py",
    ):
        source = (_PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert marker in source, relative_path


def test_ci_covers_exact_windows_runtime_and_separate_release_gates() -> None:
    workflow = _WORKFLOW_PATH.read_text(encoding="utf-8")
    quality_job = workflow.split("\n  quality:\n", 1)[1].split("\n  security:\n", 1)[0]
    security_job = workflow.split("\n  security:\n", 1)[1].split("\n  tests:\n", 1)[0]
    tests_job = workflow.split("\n  tests:\n", 1)[1].split("\n  pytest-compat:\n", 1)[0]
    pytest_compat_job = workflow.split("\n  pytest-compat:\n", 1)[1].split("\n  audit:\n", 1)[0]
    audit_job = workflow.split("\n  audit:\n", 1)[1].split("\n  build:\n", 1)[0]
    build_job = workflow.split("\n  build:\n", 1)[1].split("\n  artifacts:\n", 1)[0]
    artifacts_job = workflow.split("\n  artifacts:\n", 1)[1]

    supported_runtime_jobs = (
        quality_job,
        security_job,
        tests_job,
        pytest_compat_job,
        audit_job,
        artifacts_job,
    )
    for job in supported_runtime_jobs:
        assert "runs-on: windows-latest" in job
        assert 'python-version: "3.14.7"' in job
        assert "ubuntu" not in job.lower()
        assert "matrix:" not in job
    assert "runs-on: ubuntu-24.04" in build_job
    assert "needs: [lock, quality, security, tests, pytest-compat, audit]" in build_job
    assert "only the reproducible build host, not a supported runtime" in build_job
    assert 'python-version: "3.14.7"' in build_job
    assert 'python-version: "3.12"' not in workflow
    assert 'python-version: "3.13"' not in workflow
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
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
    assert 'MUTMUT_GITHUB_HEAD_SHA: "${{ github.event.pull_request.head.sha }}"' in workflow
    external_project_environment = (
        'UV_PROJECT_ENVIRONMENT: "${{ github.workspace }}/../mutmut-win-ci-environment"'
    )
    assert workflow.count(external_project_environment) == 1
    external_hypothesis_storage = (
        'HYPOTHESIS_STORAGE_DIRECTORY: "${{ github.workspace }}/../mutmut-win-hypothesis"'
    )
    assert workflow.count(external_hypothesis_storage) == 1
    tests_job = workflow[workflow.index("  tests:\n") : workflow.index("\n  pytest-compat:")]
    assert tests_job.count("fetch-depth: 0") == 1
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
    security_sync = "uv sync --locked --only-group security --no-install-project"
    security_command = "uv run --no-sync python -I scripts/semgrep_release_gate.py"
    security_run_lines = re.findall(r"^\s*run:\s*(.+?)\s*$", security_job, re.MULTILINE)
    assert security_run_lines == [
        security_sync,
        security_command,
        _NATIVE_RELEASE_SYNC,
        _NATIVE_RELEASE_GATE,
    ]
    assert security_job.count("fetch-depth: 0") == 1
    assert not re.search(r"\buvx\b", workflow)
    assert "semgrep scan --config auto" not in workflow
    quality_run_commands = re.findall(r"^        run: ([^\r\n]+)$", quality_job, re.MULTILINE)
    expected_quality_gate_commands = [
        "uv run --no-sync ruff check --no-cache .",
        "uv run --no-sync ruff format --no-cache --check .",
        "uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/",
        "uv run --no-sync lint-imports --no-cache",
    ]
    assert [
        command for command in quality_run_commands if command.startswith("uv run --no-sync")
    ] == expected_quality_gate_commands
    architecture_test = (_PROJECT_ROOT / "tests" / "test_architecture.py").read_text(
        encoding="utf-8"
    )
    assert "lint_imports(no_cache=True)" in architecture_test
    assert "lint_imports())" not in architecture_test
    for relative_path in (
        "README.md",
        "CLAUDE.md",
        ".serena/memories/style_conventions.md",
        ".serena/memories/task_completion_checklist.md",
        ".serena/memories/suggested_commands.md",
        "_docs/architecture spec/architecture_specification.md",
        "_docs/product backlog/product_backlog.md",
        "_docs/sprint backlogs/sprint_39_backlog.md",
        "bug_reporting/BUGFIXUNG_ROADMAP.md",
    ):
        active_contract = (_PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "UV_PROJECT_ENVIRONMENT" in active_contract, relative_path
        assert "HYPOTHESIS_STORAGE_DIRECTORY" in active_contract, relative_path
        for cacheless_contract in (
            "ruff check --no-cache",
            "ruff format --no-cache",
            "mypy --no-incremental --cache-dir=nul",
            "lint-imports --no-cache",
        ):
            assert cacheless_contract in active_contract, (relative_path, cacheless_contract)
        if relative_path != "bug_reporting/BUGFIXUNG_ROADMAP.md":
            operational_commands = re.findall(
                r"`(uv run --no-sync (?:pytest|ruff check|ruff format|mypy|lint-imports)[^`]*)`",
                active_contract,
            )
            operational_commands.extend(
                re.findall(
                    r"(?m)^\s*(uv run --no-sync "
                    r"(?:pytest|ruff check|ruff format|mypy|lint-imports)[^\r\n]*)\s*$",
                    active_contract,
                )
            )
            assert operational_commands, relative_path
            for command in operational_commands:
                normalized = " ".join(command.split())
                if normalized.startswith("uv run --no-sync pytest"):
                    assert "-p no:cacheprovider" in normalized, (relative_path, normalized)
                elif normalized.startswith("uv run --no-sync ruff"):
                    assert "--no-cache" in normalized, (relative_path, normalized)
                elif normalized.startswith("uv run --no-sync mypy"):
                    assert "--no-incremental" in normalized, (relative_path, normalized)
                    assert "--cache-dir=nul" in normalized, (relative_path, normalized)
                else:
                    assert normalized.startswith("uv run --no-sync lint-imports --no-cache"), (
                        relative_path,
                        normalized,
                    )
    assert "name: Tests and coverage (Windows, CPython 3.14.7)" in tests_job
    assert "timeout-minutes: 120" in tests_job
    assert (
        "uv run --no-sync pytest -q --cov=mutmut_win --cov-report=term-missing\n"
        "          -p no:cacheprovider\n"
        "          -W error::pytest.PytestUnhandledThreadExceptionWarning"
    ) in tests_job
    pytest_floor_command = "uv run --isolated --frozen --no-dev --no-cache"
    assert workflow.count(pytest_floor_command) == 1
    pytest_floor_lock = _PROJECT_ROOT / ".github" / "pytest-8.2.2-windows-py314.txt"
    pytest_floor_requirements = pytest_floor_lock.read_text(encoding="utf-8")
    assert "--with-requirements .github/pytest-8.2.2-windows-py314.txt" in pytest_compat_job
    assert 'UV_REQUIRE_HASHES: "1"' in pytest_compat_job
    assert "--with pytest==8.2.2" not in workflow
    expected_floor_packages = {
        "colorama==0.4.6",
        "iniconfig==2.3.0",
        "packaging==26.0",
        "pluggy==1.6.0",
        "pytest==8.2.2",
    }
    requirement_blocks = re.split(r"(?m)(?=^[a-z0-9-]+==)", pytest_floor_requirements)
    requirement_blocks = [block for block in requirement_blocks if block.strip()]
    assert {
        block.split(maxsplit=1)[0].rstrip("\\") for block in requirement_blocks
    } == expected_floor_packages
    assert all(block.count("--hash=sha256:") >= 2 for block in requirement_blocks)
    locked_workflow = workflow.replace(pytest_floor_command, "uv run --no-sync")
    assert not re.search(r"\buv run (?!\-\-no-sync\b)", locked_workflow)
    assert not re.search(r"^  (?:release|publish):$", workflow, flags=re.MULTILINE)
    assert "uv run --no-sync uv build --offline --no-build-isolation" in workflow
    assert "set -euo pipefail" in build_job
    assert 'for build_dir in "${first_dir}" "${second_dir}"; do' in build_job
    assert "${#wheels[@]} != 1 || ${#sdists[@]} != 1" in build_job
    assert 'sha256sum -- "${wheel_name}" "${sdist_name}"' in build_job
    assert 'unzip -Z1 "${wheel_name}" | LC_ALL=C sort > WHEEL-INVENTORY.txt' in build_job
    assert 'tar -tzf "${sdist_name}" | LC_ALL=C sort > SDIST-INVENTORY.txt' in build_job
    evidence_names = ("SHA256SUMS", "WHEEL-INVENTORY.txt", "SDIST-INVENTORY.txt")
    for evidence_name in evidence_names:
        assert (
            f'diff --unified "${{first_dir}}/{evidence_name}" "${{second_dir}}/{evidence_name}"'
        ) in build_job
        assert f'"${{first_dir}}"/{evidence_name}' in build_job
        assert f'"${{second_dir}}"/{evidence_name}' in build_job
    assert 'diff --recursive --brief "${first_dir}" "${second_dir}"' in build_job
    assert "dist/evidence/dist-first" in build_job
    assert "dist/evidence/dist-second" in build_job
    assert "dist/evidence/**" in build_job
    release_sync = (
        "uv sync --locked --only-group build --only-group release\n          --no-install-project"
    )
    assert build_job.count(release_sync) == 1
    release_version_probe = (
        "assert (v('twine'), v('check-wheel-contents'), v('pyflakes'), v('zizmor')) "
        "== ('7.0.0', '0.6.3', '3.4.0', '1.30.0')"
    )
    assert release_version_probe in build_job
    hardened_zizmor_prefix = (
        "uv run --no-sync zizmor --offline --strict-collection --no-config --no-ignores --persona="
    )
    assert build_job.count(hardened_zizmor_prefix) == 2
    assert workflow.count(hardened_zizmor_prefix) == 2
    assert not re.search(
        r"uv run --no-sync zizmor(?![^\n]*--no-config[^\n]*--no-ignores)[^\n]*",
        workflow,
    )
    assert "--persona=regular .github/workflows/ci.yml" in build_job
    assert "--persona=pedantic .github/workflows/ci.yml" in build_job
    assert "uv run --no-sync python -I -m twine check --strict" in build_job
    assert "uv run --no-sync check-wheel-contents --no-config --package src/mutmut_win" in build_job

    hash_read = (
        "$hashFile = Join-Path (Resolve-Path -LiteralPath dist).Path "
        '"evidence\\dist-first\\SHA256SUMS"'
    )
    hash_verify = (
        "Get-FileHash -LiteralPath $artifactsByName[$artifactName].FullName -Algorithm SHA256"
    )
    wheel_environment = '$wheelEnvironment = Join-Path $env:RUNNER_TEMP "mutmut-win-artifact-wheel"'
    wheel_python = '$wheelPython = Join-Path $wheelEnvironment "Scripts\\python.exe"'
    wheel_executable = '$wheelExecutable = Join-Path $wheelEnvironment "Scripts\\mutmut-win.exe"'
    sdist_environment = '$sdistEnvironment = Join-Path $env:RUNNER_TEMP "mutmut-win-artifact-sdist"'
    sdist_python = '$sdistPython = Join-Path $sdistEnvironment "Scripts\\python.exe"'
    sdist_executable = '$sdistExecutable = Join-Path $sdistEnvironment "Scripts\\mutmut-win.exe"'
    first_install = 'uv venv --python "3.14.7" $wheelEnvironment'
    assert hash_read in artifacts_job
    assert "Missing SHA256SUMS release evidence" in artifacts_job
    assert "$hashLines.Count -ne $artifactsByName.Count" in artifacts_job
    assert r"if ($line -cnotmatch '\A(?<hash>[0-9a-f]{64})  (?<name>[^/\\]+)\z')" in artifacts_job
    assert "$verified.ContainsKey($artifactName)" in artifacts_job
    assert "$verified.Count -ne $artifactsByName.Count" in artifacts_job
    assert hash_verify in artifacts_job
    assert "if ($actualHash -cne $expectedHash)" in artifacts_job
    assert 'throw "SHA-256 mismatch for $artifactName"' in artifacts_job
    assert artifacts_job.index(hash_read) < artifacts_job.index(hash_verify)
    assert artifacts_job.index(hash_verify) < artifacts_job.index(first_install)
    assert '$observedVersion = [string]::Join("`n", @(& $Executable --version))' in artifacts_job
    assert 'if ($observedVersion -cne "mutmut-win, version 2.21.1")' in artifacts_job
    assert 'throw "Unexpected installed version: $observedVersion"' in artifacts_job
    assert artifacts_job.count('"mutmut-win, version 2.21.1"') == 1
    for external_smoke_path in (
        wheel_environment,
        wheel_python,
        wheel_executable,
        sdist_environment,
        sdist_python,
        sdist_executable,
    ):
        assert artifacts_job.count(external_smoke_path) == 1
    assert ".artifact-wheel" not in artifacts_job
    assert ".artifact-sdist" not in artifacts_job
    assert artifacts_job.count("Assert-MutmutVersion $") == 2
    wheel_version_check = "Assert-MutmutVersion $wheelExecutable"
    sdist_install = 'uv venv --python "3.14.7" $sdistEnvironment'
    sdist_version_check = "Assert-MutmutVersion $sdistExecutable"
    assert artifacts_job.index(wheel_environment) < artifacts_job.index(first_install)
    assert artifacts_job.index(first_install) < artifacts_job.index(wheel_version_check)
    assert artifacts_job.index(sdist_environment) < artifacts_job.index(sdist_install)
    assert artifacts_job.index(wheel_version_check) < artifacts_job.index(sdist_install)
    assert artifacts_job.index(sdist_install) < artifacts_job.index(sdist_version_check)
    assert "uv pip install --offline --no-build-isolation --no-deps" in workflow
