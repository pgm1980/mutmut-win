"""Byte fidelity through actual staging, show and apply (CX221-069)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import libcst as cst
import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.constants import Profile
from mutmut_win.exceptions import StaleStagingError
from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.models import SourceFileMutationData
from mutmut_win.mutant_diff import (
    apply_mutant,
    get_diff_for_mutant,
    read_mutant_function,
    read_mutants_module,
    render_function_diff_bytes,
)
from mutmut_win.mutation import mutate_file_contents

_SOURCES = {
    "lf_multiline": b'def f():\n    text = """first\nsecond"""\n    return True\n',
    "lf_continuation": b"def f():\n    value = 1 + \\\n        2\n    return True\n",
    "mixed": b"# header\r\ndef f():\r\n    value = 1\n    return True\r\n",
    "crlf": b"def f():\r\n    return True\r\n",
    "no_final_newline": b"def f():\n    return True",
    "bare_cr": b"def f():\r    return True\r",
}


def _source_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: bytes) -> Path:
    monkeypatch.chdir(tmp_path)
    source_path = Path("src/mod.py")
    source_path.parent.mkdir()
    source_path.write_bytes(source)
    return source_path


def _boolean_mutant(source_path: Path) -> str:
    data = SourceFileMutationData(path=source_path.as_posix())
    data.load()
    module = read_mutants_module(source_path)
    return next(
        name
        for name in data.exit_code_by_key
        if "return False" in module.code_for_node(read_mutant_function(module, name))
    )


def _assert_patch_and_apply(tmp_path: Path, source_path: Path, source: bytes) -> None:
    mutant = _boolean_mutant(source_path)
    expected = source.replace(b"return True", b"return False")
    config = MutmutConfig(paths_to_mutate=["src/"])
    assert "return False" in get_diff_for_mutant(mutant, config)
    patch_bytes = render_function_diff_bytes(source_path, mutant)

    # Git's LF-delimited patch format must preserve CRLF and a bare-CR source
    # as bytes as well; the latter is one physical Git line with no final LF.
    git = shutil.which("git")
    assert git is not None, "Git is required for the source-fidelity regression"
    patch_root = tmp_path / "patch-target"
    patch_source = patch_root / source_path
    patch_source.parent.mkdir(parents=True)
    patch_source.write_bytes(source)
    # Trusted Git receives fixed arguments and a patch for this local fixture.
    applied = subprocess.run(  # noqa: S603 - trusted Git, fixed arguments and local fixture
        [git, "-c", "core.autocrlf=false", "apply", "-"],
        cwd=patch_root,
        input=patch_bytes,
        capture_output=True,
        check=False,
    )
    assert applied.returncode == 0, applied.stderr.decode(errors="replace")
    assert patch_source.read_bytes() == expected

    apply_mutant(mutant, config)
    assert source_path.read_bytes() == expected
    assert source_path.with_suffix(".py.mutmut-orig.bak").read_bytes() == source
    # Python accepts all these physical newline forms under its universal
    # newline rule; preserving them must not introduce a syntax error.
    compile(source_path.read_bytes(), str(source_path), "exec")


@pytest.mark.parametrize("case", list(_SOURCES))
def test_real_generation_show_patch_apply_preserve_source_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    source = _SOURCES[case]
    source_path = _source_project(tmp_path, monkeypatch, source)
    staged_path = Path("mutants") / source_path
    _names, warnings, fast_path = create_mutants_for_file(
        source_path, staged_path, active_profile=Profile.BASIC
    )
    assert not warnings
    assert not fast_path
    data = SourceFileMutationData(path=source_path.as_posix())
    data.load()
    assert data.generated_hash == hashlib.sha256(staged_path.read_bytes()).hexdigest()
    _assert_patch_and_apply(tmp_path, source_path, source)


def _stage_legacy_windows_generation(source_path: Path, source: bytes) -> str:
    """Write authentic old-policy bytes with valid source/generated hashes."""
    normalized = source.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    generated, names = mutate_file_contents(
        source_path.as_posix(), normalized, active_profile=Profile.BASIC
    )
    legacy_bytes = generated.replace("\n", "\r\n").encode("utf-8")
    staged_path = Path("mutants") / source_path
    staged_path.parent.mkdir(parents=True)
    staged_path.write_bytes(legacy_bytes)
    legacy_fingerprint = hashlib.sha256(
        json.dumps(
            {"profile": "basic", "do_not_mutate_patterns": [], "covered_lines": None},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    data = SourceFileMutationData(
        path=source_path.as_posix(),
        exit_code_by_key=dict.fromkeys(f"mod.{name}" for name in names),
        source_hash=hashlib.sha256(source).hexdigest(),
        generated_hash=hashlib.sha256(legacy_bytes).hexdigest(),
        generation_fingerprint=legacy_fingerprint,
    )
    data.save_generation_metadata()
    return legacy_fingerprint


@pytest.mark.parametrize("case", ["lf_multiline", "lf_continuation", "mixed"])
@pytest.mark.parametrize("consumer", ["show", "apply"])
def test_legacy_body_drift_refuses_show_and_apply_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str, consumer: str
) -> None:
    source = _SOURCES[case]
    source_path = _source_project(tmp_path, monkeypatch, source)
    _stage_legacy_windows_generation(source_path, source)
    mutant = _boolean_mutant(source_path)
    backup = source_path.with_suffix(".py.mutmut-orig.bak")
    backup.write_bytes(b"existing backup must survive")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    config = MutmutConfig(paths_to_mutate=["src/"])
    operation = get_diff_for_mutant if consumer == "show" else apply_mutant
    with pytest.raises(StaleStagingError, match=r"re-run.*mutmut-win run"):
        operation(mutant, config)
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("case", ["lf_multiline", "lf_continuation", "mixed", "crlf"])
def test_legacy_generation_policy_regenerates_once_then_allows_faithful_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    source = _SOURCES[case]
    source_path = _source_project(tmp_path, monkeypatch, source)
    legacy_fingerprint = _stage_legacy_windows_generation(source_path, source)
    staged_path = Path("mutants") / source_path
    names, warnings, fast_path = create_mutants_for_file(
        source_path, staged_path, active_profile=Profile.BASIC
    )
    assert not warnings
    assert not fast_path
    data = SourceFileMutationData(path=source_path.as_posix())
    data.load()
    assert data.generation_fingerprint != legacy_fingerprint
    assert data.generated_hash == hashlib.sha256(staged_path.read_bytes()).hexdigest()
    reused_names, reused_warnings, reused = create_mutants_for_file(
        source_path, staged_path, active_profile=Profile.BASIC
    )
    assert reused
    assert not reused_warnings
    assert reused_names == names
    _assert_patch_and_apply(tmp_path, source_path, source)


def test_compatible_legacy_body_can_still_be_shown_and_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = b"def f():\n    return True\n"
    source_path = _source_project(tmp_path, monkeypatch, source)
    _stage_legacy_windows_generation(source_path, source)
    _assert_patch_and_apply(tmp_path, source_path, source)


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_pragma_scanner_recognizes_python_universal_newlines(newline: str) -> None:
    source = newline.join(
        [
            "def skipped():  # pragma: no mutate block",
            "    return True",
            "",
            "def live():",
            "    return True",
            "",
        ]
    )
    generated, names = mutate_file_contents("mod.py", source, active_profile=Profile.BASIC)
    assert names
    assert all("live" in name for name in names)
    assert isinstance(cst.parse_module(generated), cst.Module)
