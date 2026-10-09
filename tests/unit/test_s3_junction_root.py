"""S3-030: configured Junction mutation roots have one early domain contract."""

import os
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import copy_also_copy_files, walk_source_files


def _junction(link: Path, target: Path) -> None:
    command = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
    # The trusted Windows command creates only the two pytest-owned paths.
    result = subprocess.run(  # noqa: S603
        [str(command), "/d", "/u", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        encoding="utf-16-le",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert link.is_junction()


@pytest.mark.parametrize("entry_kind", ["relative", "absolute", "file"])
def test_junction_mutation_entry_is_rejected_before_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry_kind: str
) -> None:
    """A lexical Junction must not disappear through absolute-path resolution."""
    monkeypatch.chdir(tmp_path)
    real = tmp_path / "realpkg"
    real.mkdir()
    source = real / "core.py"
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    alias = tmp_path / "alias"
    _junction(alias, real)
    entry = (
        str(alias)
        if entry_kind == "absolute"
        else "alias/core.py"
        if entry_kind == "file"
        else "alias"
    )
    with pytest.raises(ValidationError, match="Junction.*mutation"):
        MutmutConfig(paths_to_mutate=[entry])
    assert source.read_text(encoding="utf-8") == "def value():\n    return 1\n"
    assert not (tmp_path / "mutants").exists()
    assert not (tmp_path / ".mutmut-cache").exists()


def test_ordinary_mutation_root_and_explicit_linked_data_remain_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mutation-root refusal does not revoke configured data mirroring."""
    monkeypatch.chdir(tmp_path)
    real = tmp_path / "realpkg"
    real.mkdir()
    (real / "core.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    (data / "owned.txt").write_text("fixture", encoding="utf-8")
    _junction(tmp_path / "linked_data", data)
    config = MutmutConfig(paths_to_mutate=["realpkg"], also_copy=["linked_data"])
    assert list(walk_source_files(config)) == [Path("realpkg/core.py")]
    copy_also_copy_files(config)
    assert (tmp_path / "mutants/linked_data/owned.txt").read_text(encoding="utf-8") == "fixture"
