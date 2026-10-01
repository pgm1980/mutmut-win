"""M-017 git-oracle corpus: boundary verdicts must match ``git check-ignore``.

``git check-ignore`` has a documented-quirk divergence for directory probes
under marker negations (``*`` / ``!*/``), so this corpus pins only the
unambiguous file cases plus the directory cases where the tool agrees with
gitignore(5) traversal semantics.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from mutmut_win.gitignore_boundary import GitignoreBoundary

if TYPE_CHECKING:
    from pathlib import Path

#: (gitignore content, path, expected-ignored, is-directory) — verified
#: against git 2.53.0.windows.2 via ``git check-ignore -v``.  Directory
#: entries exercise the ``excludes_directory`` branch with real directory
#: targets (AR-18 / TQ-005: the original corpus only created files).
CORPUS: tuple[tuple[str, str, bool, bool], ...] = (
    # File cases (unchanged from M-017)
    ("*.pyc\n!vendor/\n", "vendor/x.pyc", True, False),
    ("*\n!*/\n", "a/b.txt", True, False),
    ("*\n!a/\n", "a/sub/x.pyc", True, False),
    ("a/**\n!a/\n", "a/x.pyc", True, False),
    ("vendor/\n!vendor/\n", "vendor/x.pyc", False, False),
    ("/*\n!/src/\n!*.pyc\n", "src/sub", False, True),
    ("/*\n!/src/\n!*.pyc\n", "src/x.pyc", False, False),
    # Directory cases: real directories exercise the marker-precedence and
    # whitelist-idiom branches that file-only corpora never reach (AR-18).
    ("*\n!*/\n", "a", False, True),
    ("*\n!a/\n", "a", False, True),
    ("*\n!a/\n", "a/sub", True, True),
    ("*\n!*/\n", "a/sub", False, True),
    ("vendor/\n", "vendor", True, True),
    ("vendor/\n!vendor/\n", "vendor", False, True),
    ("*\n!*/\n!x.pyc\n", "a/sub/x.pyc", False, False),
    ("*\n!*/\n!x.pyc\n", "a/sub", False, True),
)


@pytest.mark.integration
@pytest.mark.parametrize(("content", "path", "expected", "is_dir"), CORPUS)
def test_boundary_matches_git_check_ignore(
    tmp_path: Path,
    content: str,
    path: str,
    expected: bool,
    is_dir: bool,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # noqa: S603, S607  # git from PATH is the project contract
    (repo / ".gitignore").write_text(content, encoding="utf-8")
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if is_dir:
        target.mkdir(exist_ok=True)
        # Git needs at least one tracked-or-untracked file inside to
        # reliably answer check-ignore for the directory; add a sentinel.
        sentinel = target / ".gitkeep"
        sentinel.write_text("", encoding="utf-8")
    else:
        target.write_text("x", encoding="utf-8")

    verdict = subprocess.run(  # noqa: S603  # git from PATH is the project contract
        ["git", "-C", str(repo), "check-ignore", "-q", "--", path],  # noqa: S607
        check=False,
    )
    # Distinguish check-ignore's exit 0/1 (verdict) from error codes (>=2):
    # only 0 and 1 are meaningful ignore decisions.
    assert verdict.returncode in (0, 1), (
        f"git check-ignore failed with exit {verdict.returncode}, not a verdict"
    )
    assert (verdict.returncode == 0) is expected

    parts = path.split("/")
    boundary = GitignoreBoundary.load(repo)
    for part in parts[:-1]:
        boundary = boundary.enter(part)
    leaf_is_dir = target.is_dir()
    assert leaf_is_dir == is_dir, (
        f"fixture mismatch: expected {'dir' if is_dir else 'file'}, got "
        f"{'dir' if leaf_is_dir else 'file'} at {path}"
    )
    if leaf_is_dir:
        assert boundary.excludes_directory(parts[-1]) is expected
    else:
        assert boundary.excludes_file(parts[-1]) is expected

    shutil.rmtree(repo, ignore_errors=True)
