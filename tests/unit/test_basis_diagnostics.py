"""Parity and evidence-completeness contracts for optional basis observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from mutmut_win import basis_diagnostics as diagnostics


@dataclass(frozen=True)
class Evidence:
    digest: str
    complete: bool = True
    core_digest: str | None = None
    core_complete: bool = True


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_inactive_observation_returns_original_hash_and_has_no_side_effects():
    digest = diagnostics.observed_sha256(b"start", stream="context")
    assert type(digest) is type(hashlib.sha256())
    digest.update(b"end")
    assert digest.digest() == hashlib.sha256(b"startend").digest()
    diagnostics.record_event("unused", detail="safe")
    diagnostics.record_token("unused", b"unused private value")
    diagnostics.register_input_root(Path("unused"))
    assert not diagnostics.is_observing()


def test_active_snapshot_preserves_hash_result_and_completeness(tmp_path):
    output = tmp_path / "observations.json"
    secret = b"DO-NOT-SERIALIZE-this-environment-value"

    @diagnostics.component("environment", identity=("name",))
    def feed(hasher, name, value):
        hasher.update(value)
        diagnostics.record_token("environment-value", value, name=name)
        return False

    @diagnostics.snapshot
    def build():
        assert diagnostics.is_observing()
        hasher = diagnostics.observed_sha256(b"prefix", stream="context")
        assert feed(hasher, "EXAMPLE_SECRET", secret) is False
        hasher.update(b"suffix")
        return Evidence(hasher.hexdigest(), complete=False, core_digest="core")

    with diagnostics.diagnostics_session(output):
        first, second = build(), build()
        assert not output.exists()
    expected = hashlib.sha256(b"prefix" + secret + b"suffix").hexdigest()
    assert first == second == Evidence(expected, complete=False, core_digest="core")
    report = _read(output)
    assert report["diagnostics_complete"] is True
    assert len(report["snapshots"]) == 2
    assert report["snapshots"][0]["result"]["complete"] is False
    assert report["snapshots"][0]["frames"][1]["result"] is False
    assert report["transitions"][0]["frame_changes"] == []
    assert report["transitions"][0]["stream_observations_changed"] is False
    assert secret.decode() not in output.read_text(encoding="utf-8")
    stream = report["snapshots"][0]["streams"][0]
    assert stream["updates"] == 3
    assert stream["bytes"] == len(b"prefix" + secret + b"suffix")
    assert [entry["frame_id"] for entry in stream["attribution"]] == [0, 1, 0]


def test_duplicate_component_occurrences_and_event_only_deltas_are_retained(tmp_path):
    output = tmp_path / "observations.json"

    @diagnostics.snapshot
    def build(second):
        hasher = diagnostics.observed_sha256(stream="context")
        for index in range(2):
            with diagnostics.component_scope("directory", path="same-path"):
                hasher.update(b"same")
                if second and index == 1:
                    diagnostics.record_error("walk", PermissionError(13, "PRIVATE_MESSAGE"))
        return Evidence(hasher.hexdigest(), complete=not second)

    with diagnostics.diagnostics_session(output):
        first, second = build(False), build(True)
    assert first.digest == second.digest
    report = _read(output)
    frames = report["snapshots"][1]["frames"]
    assert [frame["occurrence"] for frame in frames[1:]] == [0, 1]
    changes = report["transitions"][0]["frame_changes"]
    assert len(changes) == 1
    assert changes[0]["path"][-1]["occurrence"] == 1
    assert changes[0]["after"]["events"][0]["errno"] == 13
    assert report["transitions"][0]["result_changed"] is True
    assert "PRIVATE_MESSAGE" not in output.read_text(encoding="utf-8")


def test_changed_direct_updates_and_empty_stream_creation_are_visible(tmp_path):
    output = tmp_path / "observations.json"

    @diagnostics.snapshot
    def build(data):
        hasher = diagnostics.observed_sha256(data, stream="direct")
        if data == b"second":
            diagnostics.observed_sha256(stream="empty")
        return Evidence(hasher.hexdigest())

    with diagnostics.diagnostics_session(output):
        build(b"first")
        build(b"second")
    transition = _read(output)["transitions"][0]
    assert transition["result_changed"] is True
    assert transition["stream_observations_changed"] is True
    assert len(transition["frame_changes"]) == 1
    assert transition["frame_changes"][0]["path"][0]["kind"] == "snapshot"


def test_canonical_exception_is_preserved_with_partial_snapshot(tmp_path):
    output = tmp_path / "observations.json"
    original = RuntimeError("unexported error message")

    @diagnostics.snapshot
    @diagnostics.component("operation")
    def build():
        diagnostics.observed_sha256(b"prefix", stream="partial")
        raise original

    with pytest.raises(RuntimeError) as caught, diagnostics.diagnostics_session(output):
        build()
    assert caught.value is original
    report = _read(output)
    assert report["diagnostics_complete"] is False
    assert report["snapshots"][0]["status"] == "partial"
    assert report["snapshots"][0]["frames"][1]["status"] == "partial"
    assert "unexported error message" not in output.read_text(encoding="utf-8")
    assert not diagnostics.is_observing()


def test_recording_failure_does_not_change_hash_or_result(tmp_path, monkeypatch, capsys):
    output = tmp_path / "observations.json"

    def fail_recording(*_args):
        raise OSError("diagnostic recorder only")

    monkeypatch.setattr(diagnostics._Capture, "record_update", fail_recording)

    @diagnostics.snapshot
    def build():
        hasher = diagnostics.observed_sha256(b"first", stream="context")
        hasher.update(b"second")
        return Evidence(hasher.hexdigest())

    with diagnostics.diagnostics_session(output):
        result = build()
    assert result == Evidence(hashlib.sha256(b"firstsecond").hexdigest())
    report = _read(output)
    assert report["diagnostics_complete"] is False
    assert len(report["errors"]) == 2
    assert "incomplete" in capsys.readouterr().err


@pytest.mark.parametrize("phase", ["begin_component", "snapshot_result", "begin_hash_stream"])
def test_auxiliary_failures_never_replace_operation(tmp_path, monkeypatch, capsys, phase):
    output = tmp_path / "observations.json"

    def fail(*_args, **_kwargs):
        raise ValueError("observer failed")

    if phase == "begin_component":
        original = diagnostics._Capture.begin_frame

        def fail_child(self, kind, identity, parent):
            return original(self, kind, identity, parent) if kind == "snapshot" else fail()

        monkeypatch.setattr(diagnostics._Capture, "begin_frame", fail_child)
    elif phase == "snapshot_result":
        monkeypatch.setattr(diagnostics, "_result", fail)
    else:
        monkeypatch.setattr(diagnostics._Capture, "begin_stream", fail)

    @diagnostics.snapshot
    @diagnostics.component("helper")
    def build():
        return Evidence(diagnostics.observed_sha256(b"canonical", stream="context").hexdigest())

    with diagnostics.diagnostics_session(output):
        result = build()
    assert result == Evidence(hashlib.sha256(b"canonical").hexdigest())
    assert _read(output)["diagnostics_complete"] is False
    assert "incomplete" in capsys.readouterr().err


def test_output_must_be_absolute_new_and_have_existing_parent(tmp_path):
    with (
        pytest.raises(ValueError, match="absolute"),
        diagnostics.diagnostics_session(Path("x.json")),
    ):
        pytest.fail("must reject before entry")
    output = tmp_path / "existing.json"
    output.write_text("preserved", encoding="utf-8")
    with pytest.raises(ValueError, match="new file"), diagnostics.diagnostics_session(output):
        pytest.fail("must reject before entry")
    assert output.read_text(encoding="utf-8") == "preserved"
    with (
        pytest.raises(ValueError, match="parent must already exist"),
        diagnostics.diagnostics_session(tmp_path / "absent" / "report.json"),
    ):
        pytest.fail("must reject before entry")
    assert not (tmp_path / "absent").exists()


def test_output_cannot_be_inside_cwd_input_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with (
        pytest.raises(ValueError, match="execution input"),
        diagnostics.diagnostics_session(tmp_path / "report.json"),
    ):
        pytest.fail("must reject before entry")
    assert not (tmp_path / "report.json").exists()


def test_late_discovered_input_root_prevents_publication_without_altering_run(tmp_path, capsys):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output = input_root / "report.json"

    @diagnostics.snapshot
    def build():
        diagnostics.register_input_root(input_root)
        return Evidence("unchanged")

    with diagnostics.diagnostics_session(output):
        result = build()
    assert result == Evidence("unchanged")
    assert not output.exists()
    assert "could not be published" in capsys.readouterr().err


def test_registered_exact_root_does_not_block_sibling_output(tmp_path):
    input_root = tmp_path / "input"
    input_root.mkdir()
    output = tmp_path / "report.json"

    @diagnostics.snapshot
    def build():
        diagnostics.register_input_root(input_root)
        return Evidence("unchanged")

    with diagnostics.diagnostics_session(output):
        build()
    assert _read(output)["diagnostics_complete"] is True


def test_output_created_during_run_is_not_overwritten_or_exception_masked(tmp_path, capsys):
    output = tmp_path / "report.json"
    original = RuntimeError("original")

    def operation():
        output.write_text("other evidence", encoding="utf-8")
        raise original

    with pytest.raises(RuntimeError) as caught, diagnostics.diagnostics_session(output):
        operation()
    assert caught.value is original
    assert output.read_text(encoding="utf-8") == "other evidence"
    assert "could not be published" in capsys.readouterr().err


def test_private_tokens_are_comparable_only_within_one_session(tmp_path):
    secret = b"low-entropy private setting"

    @diagnostics.snapshot
    def build():
        diagnostics.record_token("setting", secret, key="xoption")
        return Evidence("same")

    reports = []
    for index in range(2):
        output = tmp_path / f"report-{index}.json"
        with diagnostics.diagnostics_session(output) as collector:
            build()
            build()
        text = output.read_text(encoding="utf-8")
        assert secret.decode() not in text
        assert collector.key.hex() not in text
        reports.append(json.loads(text))
    tokens = [
        [snapshot["frames"][0]["events"][0]["token"] for snapshot in report["snapshots"]]
        for report in reports
    ]
    assert tokens[0][0] == tokens[0][1]
    assert tokens[1][0] == tokens[1][1]
    assert tokens[0][0] != tokens[1][0]


def test_no_snapshots_is_not_reported_as_complete(tmp_path):
    output = tmp_path / "report.json"
    with diagnostics.diagnostics_session(output):
        pass
    assert _read(output)["diagnostics_complete"] is False
