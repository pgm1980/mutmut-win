"""M-017 git-oracle corpus: boundary verdicts must match ``git check-ignore``.

``git check-ignore`` has a documented-quirk divergence for directory probes
under marker negations (``*`` / ``!*/``), so this corpus pins only the
unambiguous file cases plus the directory cases where the tool agrees with
gitignore(5) traversal semantics.

The M-016 folding corpus extends the oracle: with an effective
``core.ignorecase=true`` Git folds ignore-pattern case ASCII-only, so the
boundary must fold exactly there — and nowhere else.
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


#: M-016 (git 2.53.0.windows.2, NTFS): with an effective
#: ``core.ignorecase=true`` Git folds ignore-pattern case ASCII-only.
#: A path ending in ``/`` marks the leaf as a directory probe;
#: ``ignorecase="unset"`` removes the key (Git's documented default false).
FOLDING_CORPUS: tuple[tuple[str, str, str, bool], ...] = (
    ("Out/\n", "out/x.txt", "true", True),
    ("Out/\n", "out/x.txt", "false", False),
    ("Out/\n", "out/x.txt", "unset", False),
    ("*.LOG\n", "debug.log", "true", True),
    ("*.LOG\n", "debug.log", "false", False),
    ("*.log\n!Wichtig.log\n", "wichtig.log", "true", False),
    ("*.log\n!Wichtig.log\n", "wichtig.log", "false", True),
    ("\u00c4/\n", "\u00e4/x.txt", "true", False),
    ("\u00c4/\n", "\u00c4/x.txt", "true", True),
    ("\u00e4/\n", "\u00c4/x.txt", "true", False),
    ("Out/\n", "OUT/", "true", True),
    ("Out/\n", "OUT/", "false", False),
    ("*.pyc\n!VENDOR/\n", "vendor/x.pyc", "true", True),
    ("*\n!OUT/\n", "out/x.pyc", "true", True),
)


def _apply_ignorecase(repo: Path, ignorecase: str) -> None:
    if ignorecase == "unset":
        subprocess.run(  # noqa: S603  # git from PATH is the project contract
            ["git", "-C", str(repo), "config", "--unset", "core.ignorecase"],  # noqa: S607
            check=True,
        )
    else:
        subprocess.run(  # noqa: S603  # git from PATH is the project contract
            [  # noqa: S607
                "git",
                "-C",
                str(repo),
                "config",
                "core.ignorecase",
                ignorecase,
            ],
            check=True,
        )


@pytest.mark.integration
@pytest.mark.parametrize(("content", "path", "ignorecase", "expected"), FOLDING_CORPUS)
def test_boundary_matches_git_case_folding(
    tmp_path: Path,
    content: str,
    path: str,
    ignorecase: str,
    expected: bool,
) -> None:
    directory_leaf = path.endswith("/")
    clean_path = path[:-1] if directory_leaf else path
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # noqa: S603, S607  # git from PATH is the project contract
    _apply_ignorecase(repo, ignorecase)
    (repo / ".gitignore").write_text(content, encoding="utf-8")
    target = repo / clean_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if directory_leaf:
        target.mkdir()
        (target / "keep.txt").write_text("x", encoding="utf-8")
    else:
        target.write_text("x", encoding="utf-8")

    verdict = subprocess.run(  # noqa: S603  # git from PATH is the project contract
        ["git", "-C", str(repo), "check-ignore", "-q", "--", clean_path],  # noqa: S607
        check=False,
    )
    assert (verdict.returncode == 0) is expected

    parts = clean_path.split("/")
    boundary = GitignoreBoundary.load(repo)
    for part in parts[:-1]:
        boundary = boundary.enter(part)
    if directory_leaf:
        assert boundary.excludes_directory(parts[-1]) is expected
    else:
        assert boundary.excludes_file(parts[-1]) is expected

    shutil.rmtree(repo, ignore_errors=True)


@pytest.mark.integration
def test_tracked_file_beats_folded_pattern_like_git(tmp_path: Path) -> None:
    """M-016 tracked override: a ``git add -f`` file under a folded rule is
    never excluded — ``git check-ignore`` reports tracked files as not
    ignored, and so must the boundary."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # noqa: S603, S607  # git from PATH is the project contract
    _apply_ignorecase(repo, "true")
    (repo / ".gitignore").write_text("Out/\n", encoding="utf-8")
    out = repo / "out"
    out.mkdir()
    (out / "x.txt").write_text("x", encoding="utf-8")
    subprocess.run(  # noqa: S603  # git from PATH is the project contract
        ["git", "-C", str(repo), "add", "-f", "out/x.txt"],  # noqa: S607
        check=True,
    )

    verdict = subprocess.run(  # noqa: S603  # git from PATH is the project contract
        ["git", "-C", str(repo), "check-ignore", "-q", "--", "out/x.txt"],  # noqa: S607
        check=False,
    )
    assert verdict.returncode == 1  # git never reports tracked files as ignored

    boundary = GitignoreBoundary.load(repo)
    assert boundary.excludes_directory("out") is False
    assert boundary.enter("out").excludes_file("x.txt") is False

    shutil.rmtree(repo, ignore_errors=True)
