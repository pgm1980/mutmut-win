"""Case-only source changes must rebuild the corresponding staging identity."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import copy_also_copy_files, copy_src_dir, create_mutants_for_file


@pytest.mark.parametrize("configured", [False, True])
@pytest.mark.parametrize("rename_directory", [False, True])
def test_case_rename_refreshes_import_and_generation_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured: bool,
    rename_directory: bool,
) -> None:
    """Preserve live import spelling and discard generation under the old name."""
    monkeypatch.chdir(tmp_path)
    old_relative = Path("src/Helper/module.py" if rename_directory else "src/pkg/Helper.py")
    old_source = tmp_path / old_relative
    old_source.parent.mkdir(parents=True)
    old_source.write_text("def value():\n    return 2\n", encoding="utf-8")
    config = MutmutConfig(paths_to_mutate=["src"], also_copy=["src"])
    mirror = copy_also_copy_files if configured else copy_src_dir
    mirror(config)
    old_staged = tmp_path / "mutants" / old_relative
    names, _, fast_path = create_mutants_for_file(old_relative, old_staged)
    assert names
    assert not fast_path
    assert old_staged.with_name(old_staged.name + ".meta").is_file()

    old_entry = old_source.parent if rename_directory else old_source
    new_entry = old_entry.with_name(old_entry.name.lower())
    intermediate = old_entry.with_name("rename_intermediate")
    assert old_entry.resolve().is_relative_to(tmp_path.resolve())
    assert intermediate.resolve().is_relative_to(tmp_path.resolve())
    old_entry.rename(intermediate)
    intermediate.rename(new_entry)
    new_source = new_entry / "module.py" if rename_directory else new_entry
    new_relative = new_source.relative_to(tmp_path)
    new_staged = tmp_path / "mutants" / new_relative
    mirror(config)

    staged_entry = new_staged.parent if rename_directory else new_staged
    assert staged_entry.name in {entry.name for entry in staged_entry.parent.iterdir()}
    assert old_entry.name not in {entry.name for entry in staged_entry.parent.iterdir()}
    assert new_staged.read_bytes() == new_source.read_bytes()
    assert not new_staged.with_name(new_staged.name + ".meta").exists()

    names_after, _, fast_path_after = create_mutants_for_file(new_relative, new_staged)
    assert names_after == names
    assert not fast_path_after
    sidecar = new_staged.with_name(new_staged.name + ".meta")
    assert sidecar.name in {entry.name for entry in sidecar.parent.iterdir()}
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    expected_prefix = "helper.module." if rename_directory else "pkg.helper."
    assert metadata["exit_code_by_key"]
    assert all(key.startswith(expected_prefix) for key in metadata["exit_code_by_key"])
    before = (new_staged.read_bytes(), sidecar.read_bytes())
    mirror(config)
    assert (new_staged.read_bytes(), sidecar.read_bytes()) == before
    assert create_mutants_for_file(new_relative, new_staged)[2]

    uv = shutil.which("uv")
    assert uv is not None
    for root in (tmp_path / "src", tmp_path / "mutants" / "src"):
        # The fixed probe runs through uv in the externally synchronized environment.
        result = subprocess.run(  # noqa: S603
            [
                uv,
                "run",
                "--no-sync",
                "--project",
                str(Path(__file__).resolve().parents[2]),
                "python",
                "-I",
                "-c",
                f"import sys; sys.path.insert(0, {str(root)!r}); "
                f"from {expected_prefix[:-1]} import value; print(value())",
            ],
            capture_output=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == b"2"


@pytest.mark.parametrize("configured", [False, True])
def test_case_rename_preserves_independent_metadata_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured: bool
) -> None:
    """A live metadata fixture remains a mirror and is never deleted as a sidecar."""
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src/Helper.py"
    source.parent.mkdir()
    source.write_text("VALUE = 2\n", encoding="utf-8")
    fixture = source.with_name(source.name + ".meta")
    fixture.write_bytes(b"independent caller fixture")
    config = MutmutConfig(paths_to_mutate=[], also_copy=["src"])
    mirror = copy_also_copy_files if configured else copy_src_dir
    mirror(config)
    for original in (source, fixture):
        temporary = original.with_name("rename_intermediate")
        original.rename(temporary)
        temporary.rename(original.with_name(original.name.lower()))
    mirror(config)
    staged = tmp_path / "mutants/src"
    assert {entry.name for entry in staged.iterdir()} == {"helper.py", "helper.py.meta"}
    assert (staged / "helper.py").read_bytes() == source.read_bytes()
    assert (staged / "helper.py.meta").read_bytes() == b"independent caller fixture"
