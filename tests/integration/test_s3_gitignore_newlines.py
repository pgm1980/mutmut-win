"""S3-010: only Git line endings delimit ignore patterns."""

import subprocess
from pathlib import Path

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import walk_source_files
from mutmut_win.gitignore_boundary import GitignoreBoundary


@pytest.mark.integration
@pytest.mark.parametrize(
    "separator", ["\x0b", "\x0c", "\x85", "\u2028", "\u2029", "\r", "\n", "\r\n"]
)
def test_gitignore_comment_boundary_matches_real_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, separator: str
) -> None:
    """Unicode separators and bare CR remain inside a comment; LF starts a rule."""
    # Git on PATH is the documented project dependency; arguments are fixture-owned.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)  # noqa: S603, S607
    (tmp_path / ".gitignore").write_bytes(("# comment" + separator + "victim.py\n").encode())
    source = tmp_path / "victim.py"
    source.write_bytes(b"VALUE = 1\n")
    # The Git oracle receives a fixed option list and a literal filename after --.
    oracle = subprocess.run(  # noqa: S603
        # Git on PATH is the documented project dependency.
        ["git", "-C", str(tmp_path), "check-ignore", "-q", "--", "victim.py"],  # noqa: S607
        check=False,
    )
    expected = separator in {"\n", "\r\n"}
    assert oracle.returncode == (0 if expected else 1)
    assert GitignoreBoundary.load(tmp_path).excludes_file("victim.py") is expected
    monkeypatch.chdir(tmp_path)
    discovered = set(walk_source_files(MutmutConfig(paths_to_mutate=["."])))
    assert (Path("victim.py") in discovered) is not expected
    assert source.read_bytes() == b"VALUE = 1\n"
