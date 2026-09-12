"""Controlled integration checks for canonical basis observations."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from typing import TYPE_CHECKING

import mutmut_win.stats as stats
from mutmut_win.basis_diagnostics import diagnostics_session, observed_sha256, snapshot
from mutmut_win.config import MutmutConfig

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


@snapshot
def _tree_basis(root: Path) -> stats.RunBasisEvidence:
    hasher = observed_sha256(stream="tree-probe")
    complete = stats._hash_context_tree(hasher, root, label_prefix="fixture", seen=set())
    return stats.RunBasisEvidence(hasher.hexdigest(), complete)


def _frames(report: dict, kind: str, sequence: int = 0) -> list[dict]:
    return [frame for frame in report["snapshots"][sequence]["frames"] if frame["kind"] == kind]


def test_canonical_basis_all_fields_match_with_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "sample.py").write_text("value = 42\n", encoding="utf-8")
    monkeypatch.setattr(stats.sys, "path", [str(project)])
    monkeypatch.setattr(stats.importlib.metadata, "distributions", list)
    config = MutmutConfig(paths_to_mutate=["sample.py"], tests_dir=[])
    baseline = stats.build_run_basis_evidence(config, project)
    output = tmp_path / "basis.json"
    with diagnostics_session(output):
        observed = stats.build_run_basis_evidence(config, project)
        repeated = stats.build_run_basis_evidence(config, project)
        assert not output.exists()
    assert observed == repeated == baseline
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"]
    assert report["snapshots"][0]["result"]["digest"] == baseline.digest
    assert {stream["name"] for stream in report["snapshots"][0]["streams"]} == {
        "context",
        "core",
        "distributions",
        "basis",
    }
    assert not report["transitions"][0]["result_changed"]
    assert not report["transitions"][0]["frame_changes"]
    assert not report["transitions"][0]["stream_observations_changed"]


def test_walk_error_preserves_bytes_but_records_incompleteness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "sample.py").write_text("value = 42\n", encoding="utf-8")
    walk = os.walk
    fail = False

    def walk_with_optional_error(root, *, onerror):
        if fail:
            onerror(PermissionError(errno.EACCES, "test-only read failure", str(project / "child")))
        yield from walk(root, onerror=onerror)

    monkeypatch.setattr(stats.os, "walk", walk_with_optional_error)
    output = tmp_path / "walk.json"
    with diagnostics_session(output):
        before = _tree_basis(project)
        fail = True
        after = _tree_basis(project)
    assert before.digest == after.digest
    assert before.complete
    assert not after.complete
    report = json.loads(output.read_text(encoding="utf-8"))
    trees = _frames(report, "tree", 1)
    assert trees[0]["result"] is False
    assert any(event.get("operation") == "walk" for event in trees[0]["events"])
    assert report["transitions"][0]["result_changed"]
    assert report["transitions"][0]["frame_changes"]


def test_metadata_change_has_stable_content_token(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = project / "sample.py"
    source.write_text("value = 42\n", encoding="utf-8")
    original = source.stat()
    output = tmp_path / "metadata.json"
    with diagnostics_session(output):
        before = _tree_basis(project)
        os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns + 10_000_000))
        after = _tree_basis(project)
    assert before.complete
    assert after.complete
    assert before.digest != after.digest
    report = json.loads(output.read_text(encoding="utf-8"))
    assert _frames(report, "content", 0)[0]["hashes"] == _frames(report, "content", 1)[0]["hashes"]
    assert _frames(report, "metadata", 0) != _frames(report, "metadata", 1)
    file_events = _frames(report, "file")[0]["events"]
    assert [event["role"] for event in file_events if event["kind"] == "file-observation"] == [
        "before",
        "after-handle",
        "rebound",
    ]


def test_actual_environment_entry_changes_private_token_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @snapshot
    def environment_basis() -> stats.RunBasisEvidence:
        hasher = observed_sha256(stream="environment-probe")
        stats._hash_inherited_environment(hasher)
        return stats.RunBasisEvidence(hasher.hexdigest(), True)

    monkeypatch.setenv("MUTMUT_DIAGNOSTIC_TEST_SECRET", "first-secret-never-in-report")
    output = tmp_path / "environment.json"
    with diagnostics_session(output):
        before = environment_basis()
        monkeypatch.setenv("MUTMUT_DIAGNOSTIC_TEST_SECRET", "second-secret-never-in-report")
        after = environment_basis()
    assert before.digest != after.digest
    text = output.read_text(encoding="utf-8")
    assert "first-secret-never-in-report" not in text
    assert "second-secret-never-in-report" not in text
    report = json.loads(text)
    changes = report["transitions"][0]["frame_changes"]
    entries = [change for change in changes if change["path"][-1]["kind"] == "environment-entry"]
    assert len(entries) == 1
    assert entries[0]["path"][-1]["identity"]["name"] == "MUTMUT_DIAGNOSTIC_TEST_SECRET"


def test_fanout_forwards_each_byte_once(tmp_path: Path) -> None:
    @snapshot
    def fanout_basis() -> stats.RunBasisEvidence:
        left = observed_sha256(b"prefix", stream="left")
        right = observed_sha256(stream="right")
        fanout = stats._HashFanout(left, right)
        fanout.update(b"shared")
        return stats.RunBasisEvidence(left.hexdigest(), True, right.hexdigest(), True)

    output = tmp_path / "fanout.json"
    with diagnostics_session(output):
        value = fanout_basis()
    assert value.digest == hashlib.sha256(b"prefixshared").hexdigest()
    assert value.core_digest == hashlib.sha256(b"shared").hexdigest()
    report = json.loads(output.read_text(encoding="utf-8"))
    streams = report["snapshots"][0]["streams"]
    assert [(item["name"], item["bytes"]) for item in streams] == [("left", 12), ("right", 6)]


def test_file_observation_events_publish_all_six_bound_metadata_values(tmp_path: Path) -> None:
    project = tmp_path / "input"
    project.mkdir()
    source = project / "sample.py"
    source.write_bytes(b"value = 42\n")

    @snapshot
    def observe() -> bool:
        hasher = observed_sha256(stream="file-contract")
        return stats._hash_context_file(hasher, source, label="fixture", seen=set())

    output = tmp_path / "file-observations.json"
    with source.open("rb") as handle:
        # Use a bound handle on Windows: path-stat ctime has different semantics.
        expected_stat = os.fstat(handle.fileno())
        with diagnostics_session(output):
            assert observe() is True
        after_stat = os.fstat(handle.fileno())

    expected_fields = {
        "st_dev": expected_stat.st_dev,
        "st_ino": expected_stat.st_ino,
        "st_mode": expected_stat.st_mode,
        "st_size": expected_stat.st_size,
        "st_mtime_ns": expected_stat.st_mtime_ns,
        "st_ctime_ns": expected_stat.st_ctime_ns,
    }
    assert expected_fields == {
        "st_dev": after_stat.st_dev,
        "st_ino": after_stat.st_ino,
        "st_mode": after_stat.st_mode,
        "st_size": after_stat.st_size,
        "st_mtime_ns": after_stat.st_mtime_ns,
        "st_ctime_ns": after_stat.st_ctime_ns,
    }
    report = json.loads(output.read_text(encoding="utf-8"))
    file_frames = [frame for frame in report["snapshots"][0]["frames"] if frame["kind"] == "file"]
    assert len(file_frames) == 1
    assert file_frames[0]["events"] == [
        {"kind": "file-observation", "role": "before", "fields": expected_fields},
        {"kind": "file-observation", "role": "after-handle", "fields": expected_fields},
        {"kind": "file-observation", "role": "rebound", "fields": expected_fields},
    ]
    assert report["diagnostics_complete"] is True
