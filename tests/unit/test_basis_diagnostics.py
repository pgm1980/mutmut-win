"""Parity and evidence-completeness contracts for optional basis observations."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mutmut_win import basis_diagnostics as diagnostics

if TYPE_CHECKING:
    from typing import Any, Never


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


class _OpaqueValue:
    def __str__(self) -> str:
        return "PRIVATE_OPAQUE_STRING"

    def __repr__(self) -> str:
        return "PRIVATE_OPAQUE_REPR"


class _UnreadableFields(dict[str, object]):
    def items(self) -> Never:
        raise OSError("PRIVATE_FIELD_ACCESS_FAILURE")


class _UnreadableMetadataError(RuntimeError):
    @property
    def errno(self) -> int:
        raise OSError("PRIVATE_ERROR_METADATA_FAILURE")


def test_published_report_retains_session_and_snapshot_provenance(tmp_path: Path) -> None:
    output = tmp_path / "provenance.json"
    pid, thread_id = os.getpid(), threading.get_ident()

    @diagnostics.snapshot
    def build() -> bool:
        return True

    before = time.monotonic_ns()
    with diagnostics.diagnostics_session(output):
        assert build() is True
        assert not output.exists()
    after = time.monotonic_ns()

    report = _read(output)
    assert report["schema"] == 1
    assert report["pid"] == pid
    # The identifier is opaque: do not freeze its random value or exact length.
    assert isinstance(report["session_id"], str)
    assert report["session_id"]
    assert report["diagnostics_complete"] is True
    assert report["errors"] == []
    scope = report["token_scope"].casefold()
    assert "per-session" in scope
    assert "hmac-sha256" in scope
    assert "not exported" in scope
    assert len(report["snapshots"]) == 1
    snapshot = report["snapshots"][0]
    assert snapshot["sequence"] == 1
    assert snapshot["pid"] == pid
    assert snapshot["thread_id"] == thread_id
    assert snapshot["status"] == "complete"
    assert snapshot["result"] is True
    assert report["transitions"] == []

    stamps = [report["start"], snapshot["start"], snapshot["end"], report["end"]]
    assert all(set(stamp) == {"utc", "monotonic_ns"} for stamp in stamps)
    ticks = [stamp["monotonic_ns"] for stamp in stamps]
    assert all(type(value) is int for value in ticks)
    assert before <= ticks[0] <= ticks[1] <= ticks[2] <= ticks[3] <= after
    assert all(datetime.fromisoformat(stamp["utc"]).utcoffset() == timedelta(0) for stamp in stamps)


def test_published_safe_event_fields_preserve_values_without_object_representations(
    tmp_path: Path,
) -> None:
    known_path = tmp_path / "known-input-name"
    opaque = _OpaqueValue()

    @diagnostics.snapshot
    def observe() -> None:
        diagnostics.record_event(
            "safe-fields",
            payload={
                "none": None,
                "text": "known text",
                "flag": False,
                "integer": 17,
                "fraction": 2.5,
                "path": known_path,
                "sequence": (None, known_path, [True, 23]),
                "nested": {"retained": "known", 99: "PRIVATE_NONSTRING_KEY_VALUE"},
                "opaque": opaque,
            },
        )

    output = tmp_path / "safe-fields.json"
    with diagnostics.diagnostics_session(output):
        observe()

    report = _read(output)
    assert report["snapshots"][0]["frames"][0]["events"] == [
        {
            "kind": "safe-fields",
            "payload": {
                "none": None,
                "text": "known text",
                "flag": False,
                "integer": 17,
                "fraction": 2.5,
                "path": str(known_path),
                "sequence": [None, str(known_path), [True, 23]],
                "nested": {"retained": "known"},
                "opaque": {"type": "_OpaqueValue"},
            },
        }
    ]
    assert report["diagnostics_complete"] is True
    assert "PRIVATE_" not in output.read_text(encoding="utf-8")


def test_snapshot_return_values_remain_exact_and_unknown_results_have_a_type_label(
    tmp_path: Path,
) -> None:
    @diagnostics.snapshot
    def echo(value: object) -> object:
        return value

    opaque = _OpaqueValue()
    output = tmp_path / "results.json"
    with diagnostics.diagnostics_session(output):
        assert echo(None) is None
        assert echo(opaque) is opaque

    report = _read(output)
    assert [item["result"] for item in report["snapshots"]] == [None, {"type": "_OpaqueValue"}]
    assert report["diagnostics_complete"] is True
    assert "PRIVATE_" not in output.read_text(encoding="utf-8")


def test_error_events_keep_numeric_os_codes_and_omit_unavailable_codes_and_messages(
    tmp_path: Path,
) -> None:
    error = PermissionError(13, "PRIVATE_OS_ERROR_MESSAGE")
    error.winerror = 5

    @diagnostics.snapshot
    def observe() -> None:
        diagnostics.record_error("read-fixture", error, label="known-file")
        diagnostics.record_error("inspect-fixture", RuntimeError("PRIVATE_RUNTIME_MESSAGE"))

    output = tmp_path / "errors.json"
    with diagnostics.diagnostics_session(output):
        observe()

    report = _read(output)
    assert report["snapshots"][0]["frames"][0]["events"] == [
        {
            "kind": "error",
            "operation": "read-fixture",
            "exception_type": "PermissionError",
            "label": "known-file",
            "errno": 13,
            "winerror": 5,
        },
        {
            "kind": "error",
            "operation": "inspect-fixture",
            "exception_type": "RuntimeError",
        },
    ]
    assert report["errors"] == []
    assert report["diagnostics_complete"] is True
    assert "PRIVATE_" not in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("operation", ["record_event", "record_token", "record_error"])
def test_recording_failures_preserve_the_call_and_publish_precise_failure_attribution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    expected = _OpaqueValue()

    def unavailable_hmac(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("PRIVATE_HMAC_FAILURE")

    @diagnostics.snapshot
    def observe() -> object:
        if operation == "record_event":
            diagnostics.record_event("fixture", details=_UnreadableFields())
        elif operation == "record_token":
            # Restore the dependency before snapshot finalization/publication.
            with monkeypatch.context() as patch:
                patch.setattr(diagnostics.hmac, "new", unavailable_hmac)
                diagnostics.record_token("fixture", b"known observed bytes", name="known")
        else:
            diagnostics.record_error("fixture", _UnreadableMetadataError("PRIVATE_MESSAGE"))
        return expected

    output = tmp_path / f"{operation}-failure.json"
    with diagnostics.diagnostics_session(output):
        assert observe() is expected

    report = _read(output)
    assert report["errors"] == [{"operation": operation, "exception_type": "OSError"}]
    assert report["diagnostics_complete"] is False
    assert report["snapshots"][0]["status"] == "complete"
    assert report["snapshots"][0]["frames"][0]["events"] == []
    assert "PRIVATE_" not in output.read_text(encoding="utf-8")


def test_recording_between_snapshots_is_a_noop_without_diagnostic_faults(tmp_path: Path) -> None:
    @diagnostics.snapshot
    def observe() -> None:
        return None

    output = tmp_path / "between-snapshots.json"
    with diagnostics.diagnostics_session(output):
        diagnostics.record_event("outside-before", known=1)
        diagnostics.record_token("outside-before", b"known bytes", name="known")
        diagnostics.record_error("outside-before", RuntimeError("PRIVATE_MESSAGE"))
        observe()
        diagnostics.record_event("outside-after", known=2)
        diagnostics.record_token("outside-after", b"more known bytes", name="known")

    report = _read(output)
    assert report["errors"] == []
    assert report["diagnostics_complete"] is True
    assert report["snapshots"][0]["frames"][0]["events"] == []


def test_failure_to_record_a_diagnostic_fault_cannot_replace_the_canonical_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = LookupError("PRIVATE_CANONICAL_EXCEPTION")

    def unavailable_fault(_operation: str, _error: BaseException) -> None:
        raise OSError("PRIVATE_FAULT_SINK_FAILURE")

    @diagnostics.snapshot
    def observe() -> None:
        diagnostics.record_event("fixture", details=_UnreadableFields())
        raise original

    output = tmp_path / "fault-sink-failure.json"
    with diagnostics.diagnostics_session(output) as collector:
        monkeypatch.setattr(collector, "fault", unavailable_fault)
        with pytest.raises(LookupError) as caught:
            observe()
        assert caught.value is original

    report = _read(output)
    assert report["diagnostics_complete"] is False
    assert report["snapshots"][0]["status"] == "partial"
    assert report["snapshots"][0]["frames"][0]["events"] == [
        {"kind": "error", "operation": "snapshot", "exception_type": "LookupError"}
    ]
    assert "PRIVATE_" not in output.read_text(encoding="utf-8")


def test_declared_missing_input_root_does_not_prevent_a_valid_report(tmp_path: Path) -> None:
    missing_input = tmp_path / "declared-input-not-yet-present"

    @diagnostics.snapshot
    def observe() -> bool:
        diagnostics.register_input_root(missing_input)
        return False

    output = tmp_path / "missing-input.json"
    with diagnostics.diagnostics_session(output):
        assert observe() is False

    assert not missing_input.exists()
    report = _read(output)
    assert report["errors"] == []
    assert report["diagnostics_complete"] is True
    assert report["snapshots"][0]["result"] is False


def test_report_path_cannot_also_be_registered_as_an_exact_input_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "declared-input.json"

    @diagnostics.snapshot
    def observe() -> bool:
        diagnostics.register_input_root(output)
        return True

    with diagnostics.diagnostics_session(output):
        assert observe() is True

    assert not output.exists()
    assert "could not be published" in capsys.readouterr().err


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf")], ids=["nan", "inf", "minus-inf"]
)
def test_nonfinite_observation_never_publishes_nonstandard_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: float
) -> None:
    output = tmp_path / "nonfinite.json"

    @diagnostics.snapshot
    def build() -> bool:
        diagnostics.record_event("measurement", value=value)
        return True

    with diagnostics.diagnostics_session(output):
        actual = build()

    assert actual is True
    assert not output.exists()
    stderr = capsys.readouterr().err
    assert "could not be published" in stderr
    assert "ValueError" in stderr
    assert not diagnostics.is_observing()


def test_failed_input_root_resolution_keeps_publication_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    observed_root = tmp_path / "observed-input"
    observed_root.mkdir()
    output = observed_root / "report.json"
    resolve = Path.resolve
    private_message = "unavailable-local-input-private-detail"

    def resolve_with_unavailable_root(path: Path, strict: bool = False) -> Path:
        if path == observed_root:
            raise OSError(private_message)
        return resolve(path, strict=strict)

    @diagnostics.snapshot
    def build() -> bool:
        diagnostics.register_input_root(observed_root)
        return True

    # Initial output validation succeeds. Only the later local input-root
    # inspection fails; it is restored before publication is attempted.
    with diagnostics.diagnostics_session(output), monkeypatch.context() as patch:
        patch.setattr(Path, "resolve", resolve_with_unavailable_root)
        actual = build()

    assert actual is True
    assert not output.exists()
    stderr = capsys.readouterr().err
    assert "could not be published" in stderr
    assert "ValueError" in stderr
    assert private_message not in stderr
    assert not diagnostics.is_observing()
