"""Regression tests for the 2026-08-30 adversarial cache/path review."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.constants import Profile
from mutmut_win.exceptions import OrchestratorError, UnsafeStagingError
from mutmut_win.file_setup import (
    config_fingerprint_matches,
    create_mutants_for_file,
    persist_config_fingerprint,
    walk_source_files,
)
from mutmut_win.models import SourceFileMutationData
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.stats import build_stats_context_fingerprint

if TYPE_CHECKING:
    from pathlib import Path


def test_parent_traversal_mutation_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    with pytest.raises(ValidationError, match="outside the project root"):
        MutmutConfig(paths_to_mutate=["../outside"])


def test_load_config_anchors_absolute_paths_to_requested_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source = project / "src"
    source.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        f'[tool.mutmut]\npaths_to_mutate = ["{source.as_posix()}"]\n',
        encoding="utf-8",
    )

    config = load_config(project)

    assert config.paths_to_mutate == ["src"]


def test_dot_walk_prunes_its_own_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    staged = tmp_path / "mutants" / "app.py"
    staged.parent.mkdir()
    staged.write_text("VALUE = 2\n", encoding="utf-8")
    internal = tmp_path / "bug_reporting" / "repro.py"
    internal.parent.mkdir()
    internal.write_text("VALUE = 3\n", encoding="utf-8")

    files = {path.resolve() for path in walk_source_files(MutmutConfig(paths_to_mutate=["."]))}

    assert (tmp_path / "app.py").resolve() in files
    assert staged.resolve() not in files
    assert internal.resolve() not in files


def test_write_guard_rejects_any_destination_outside_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "mod.py"
    source.write_text("def f():\n    return 1\n", encoding="utf-8")

    with pytest.raises(UnsafeStagingError, match="escapes"):
        create_mutants_for_file(source, tmp_path / "escaped.py")


def test_unexpected_generation_value_error_aborts_without_publishing_empty_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "mod.py"
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    output = tmp_path / "mutants" / "mod.py"
    output.parent.mkdir()

    def fail_generation(**_kwargs: object) -> list[str]:
        raise ValueError("internal mutation invariant failed")

    monkeypatch.setattr("mutmut_win.file_setup.write_all_mutants_to_file", fail_generation)

    with pytest.raises(ValueError, match="invariant"):
        create_mutants_for_file(source, output)

    assert not output.exists()


def test_same_size_same_mtime_source_change_misses_fast_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src" / "mod.py"
    source.parent.mkdir()
    source.write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
    output = tmp_path / "mutants" / "src" / "mod.py"

    first, _warnings, first_fast = create_mutants_for_file(source, output)
    original_stat = source.stat()
    source.write_text("def f(a):\n    return a - 1\n", encoding="utf-8")
    os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    second, _warnings, second_fast = create_mutants_for_file(source, output)

    assert first
    assert second
    assert first_fast is False
    assert second_fast is False
    assert "return a - 1" in output.read_text(encoding="utf-8")


def test_fingerprint_includes_regex_exclusions_and_covered_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()
    old = MutmutConfig(paths_to_mutate=["src"], do_not_mutate_patterns=["^old$"])
    new = MutmutConfig(paths_to_mutate=["src"], do_not_mutate_patterns=["^new$"])

    assert config_fingerprint_matches(old, {"src/mod.py": {2}}) is False
    assert config_fingerprint_matches(old, {"src/mod.py": {2}}) is True
    assert config_fingerprint_matches(new, {"src/mod.py": {2}}) is False
    assert config_fingerprint_matches(new, {"src/mod.py": {3}}) is False


def test_compare_only_fingerprint_does_not_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config = MutmutConfig(paths_to_mutate=["src"])

    assert config_fingerprint_matches(config, persist=False) is False
    assert not (tmp_path / "mutants" / ".mutmut-config-fingerprint").exists()


def test_generation_error_does_not_commit_new_universe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src" / "mod.py"
    source.parent.mkdir()
    source.write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
    old = MutmutConfig(paths_to_mutate=["src"], max_children=1, mutation_profile=Profile.BASIC)
    new = old.model_copy(update={"mutation_profile": Profile.ALL})
    persist_config_fingerprint(old)

    def fail_supervised(
        file_args: list[object], **_kwargs: object
    ) -> list[tuple[str, list[str], Exception, list[str], bool]]:
        rel_path = str(file_args[0][0])  # type: ignore[index]
        return [(rel_path, [], RuntimeError("fault injection"), [], False)]

    monkeypatch.setattr("mutmut_win.process.run_generation_supervised", fail_supervised)
    orchestrator = MutationOrchestrator(new, runner=MagicMock(), executor=MagicMock())

    with pytest.raises(OrchestratorError, match="incomplete"):
        orchestrator._generate_mutants()

    assert config_fingerprint_matches(old, persist=False) is True
    assert config_fingerprint_matches(new, persist=False) is False


def test_stats_context_detects_helper_content_with_restored_stat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src" / "mod.py"
    helper = tmp_path / "tests" / "helper.py"
    source.parent.mkdir()
    helper.parent.mkdir()
    source.write_text("VALUE = 1\n", encoding="utf-8")
    helper.write_text("VALUE = 1\n", encoding="utf-8")
    config = MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests"])
    before = build_stats_context_fingerprint(config)
    stat = helper.stat()

    helper.write_text("VALUE = 2\n", encoding="utf-8")
    os.utime(helper, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    assert build_stats_context_fingerprint(config) != before


def test_stats_context_hashes_explicit_external_fixture_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    external = tmp_path / "shared-fixtures"
    project.mkdir()
    external.mkdir()
    fixture = external / "cases.json"
    fixture.write_text('{"expected": 1}\n', encoding="utf-8")
    monkeypatch.chdir(project)
    config = MutmutConfig(paths_to_mutate=["."], extra_paths=["../shared-fixtures"])
    before = build_stats_context_fingerprint(config)
    stat = fixture.stat()

    fixture.write_text('{"expected": 2}\n', encoding="utf-8")
    os.utime(fixture, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    assert build_stats_context_fingerprint(config) != before


def test_stats_context_hashes_local_test_fixture_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    fixture = tests / "cases.json"
    fixture.write_text('{"expected": 1}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config = MutmutConfig(paths_to_mutate=["."], tests_dir=["tests"])
    before = build_stats_context_fingerprint(config)
    stat = fixture.stat()

    fixture.write_text('{"expected": 2}\n', encoding="utf-8")
    os.utime(fixture, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    assert build_stats_context_fingerprint(config) != before


def test_stats_context_skips_mixed_case_tooling_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    hidden = tmp_path / ".GiT" / "generated.py"
    hidden.parent.mkdir()
    hidden.write_text("VALUE = 1\n", encoding="utf-8")
    config = MutmutConfig(paths_to_mutate=["."])
    before = build_stats_context_fingerprint(config)

    hidden.write_text("VALUE = 2\n", encoding="utf-8")

    assert build_stats_context_fingerprint(config) == before


def test_type_corrupt_exit_code_discards_meta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data = SourceFileMutationData(path="src/mod.py")
    data.meta_path.parent.mkdir(parents=True)
    data.meta_path.write_text(
        json.dumps({"exit_code_by_key": {"m": []}}),
        encoding="utf-8",
    )

    data.load()

    assert data.exit_code_by_key == {}
    assert not data.meta_path.exists()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"exit_code_by_key": []},
        {"durations_by_key": {"m": float("nan")}},
        {"type_check_error_by_key": {"m": []}},
        {"source_hash": "not-a-digest"},
        {"generation_fingerprint": 7},
    ],
)
def test_structurally_corrupt_meta_is_discarded(
    payload: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data = SourceFileMutationData(path="src/mod.py")
    data.meta_path.parent.mkdir(parents=True)
    data.meta_path.write_text(json.dumps(payload), encoding="utf-8")

    data.load()

    assert data.exit_code_by_key == {}
    assert not data.meta_path.exists()
