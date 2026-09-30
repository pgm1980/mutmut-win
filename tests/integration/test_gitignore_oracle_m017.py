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

#: (gitignore content, path, expected-ignored) — verified against
#: git 2.53.0.windows.2 via ``git check-ignore -v``.
CORPUS: tuple[tuple[str, str, bool], ...] = (
    ("*.pyc\n!vendor/\n", "vendor/x.pyc", True),
    ("*\n!*/\n", "a/b.txt", True),
    ("*\n!a/\n", "a/sub/x.pyc", True),
    ("a/**\n!a/\n", "a/x.pyc", True),
    ("vendor/\n!vendor/\n", "vendor/x.pyc", False),
    ("/*\n!/src/\n!*.pyc\n", "src/sub", False),
    ("/*\n!/src/\n!*.pyc\n", "src/x.pyc", False),
)


@pytest.mark.integration
@pytest.mark.parametrize(("content", "path", "expected"), CORPUS)
def test_boundary_matches_git_check_ignore(
    tmp_path: Path,
    content: str,
    path: str,
    expected: bool,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # noqa: S603, S607  # git from PATH is the project contract
    (repo / ".gitignore").write_text(content, encoding="utf-8")
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x", encoding="utf-8")

    verdict = subprocess.run(  # noqa: S603  # git from PATH is the project contract
        ["git", "-C", str(repo), "check-ignore", "-q", "--", path],  # noqa: S607
        check=False,
    )
    assert (verdict.returncode == 0) is expected

    parts = path.split("/")
    boundary = GitignoreBoundary.load(repo)
    for part in parts[:-1]:
        boundary = boundary.enter(part)
    leaf_is_dir = target.is_dir()
    if leaf_is_dir:
        assert boundary.excludes_directory(parts[-1]) is expected
    else:
        assert boundary.excludes_file(parts[-1]) is expected

    shutil.rmtree(repo, ignore_errors=True)
