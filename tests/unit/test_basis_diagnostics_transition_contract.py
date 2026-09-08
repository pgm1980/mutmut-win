"""Public report contracts for component identity and consecutive observations."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from mutmut_win import basis_diagnostics as diagnostics

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class Evidence:
    digest: str
    complete: bool = True
    core_digest: str | None = None
    core_complete: bool = True


def test_added_and_removed_empty_component_does_not_change_stream_attribution(tmp_path):
    output = tmp_path / "component-transitions.json"

    @diagnostics.snapshot
    def build(include_optional):
        hasher = diagnostics.observed_sha256(stream="content")
        if include_optional:
            with diagnostics.component_scope("optional", name="extra"):
                pass
        with diagnostics.component_scope("file", name="stable"):
            hasher.update(b"unchanged")
        return Evidence(hasher.hexdigest())

    with diagnostics.diagnostics_session(output):
        build(False)
        build(True)
        build(False)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"] is True
    assert [snapshot["frames"][-1]["id"] for snapshot in report["snapshots"]] == [1, 2, 1]
    path = [
        {"kind": "snapshot", "identity": {}, "occurrence": 0},
        {"kind": "optional", "identity": {"name": "extra"}, "occurrence": 0},
    ]
    empty_component = {"status": "complete", "result": None, "events": [], "hashes": []}
    assert report["transitions"] == [
        {
            "from_sequence": 1,
            "to_sequence": 2,
            "result_changed": False,
            "status_changed": False,
            "frame_changes": [
                {
                    "path": path,
                    "before_frame_id": None,
                    "after_frame_id": 1,
                    "before": None,
                    "after": empty_component,
                }
            ],
            "stream_observations_changed": False,
        },
        {
            "from_sequence": 2,
            "to_sequence": 3,
            "result_changed": False,
            "status_changed": False,
            "frame_changes": [
                {
                    "path": path,
                    "before_frame_id": 1,
                    "after_frame_id": None,
                    "before": empty_component,
                    "after": None,
                }
            ],
            "stream_observations_changed": False,
        },
    ]


def test_stream_numbers_are_not_component_changes(tmp_path):
    output = tmp_path / "stream-number-transitions.json"

    @diagnostics.snapshot
    def build(include_empty):
        if include_empty:
            diagnostics.observed_sha256(stream="empty")
        hasher = diagnostics.observed_sha256(b"same", stream="content")
        return Evidence(hasher.hexdigest())

    with diagnostics.diagnostics_session(output):
        build(False)
        build(True)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"] is True
    assert [
        snapshot["frames"][0]["hashes"][0]["stream_id"] for snapshot in report["snapshots"]
    ] == [0, 1]
    assert report["transitions"] == [
        {
            "from_sequence": 1,
            "to_sequence": 2,
            "result_changed": False,
            "status_changed": False,
            "frame_changes": [],
            "stream_observations_changed": True,
        }
    ]


def test_component_result_and_events_are_preserved_in_change_details(tmp_path):
    output = tmp_path / "component-value-transitions.json"
    key = b"known test key for independent HMAC oracle"

    @diagnostics.component("reader")
    def read(hasher, after):
        hasher.update(b"same")
        diagnostics.record_event("observation", phase="after" if after else "before")
        return after

    @diagnostics.snapshot
    def build(after):
        hasher = diagnostics.observed_sha256(stream="content")
        assert read(hasher, after) is after
        return Evidence(hasher.hexdigest())

    with diagnostics.diagnostics_session(output) as collector:
        collector.key = key
        build(False)
        build(True)
    report = json.loads(output.read_text(encoding="utf-8"))
    expected_hash = {
        "stream": "content",
        "updates": 1,
        "bytes": 4,
        "hmac": hmac.new(key, b"same", hashlib.sha256).hexdigest(),
    }
    assert report["diagnostics_complete"] is True
    assert report["transitions"] == [
        {
            "from_sequence": 1,
            "to_sequence": 2,
            "result_changed": False,
            "status_changed": False,
            "frame_changes": [
                {
                    "path": [
                        {"kind": "snapshot", "identity": {}, "occurrence": 0},
                        {"kind": "reader", "identity": {}, "occurrence": 0},
                    ],
                    "before_frame_id": 1,
                    "after_frame_id": 1,
                    "before": {
                        "status": "complete",
                        "result": False,
                        "events": [{"kind": "observation", "phase": "before"}],
                        "hashes": [expected_hash],
                    },
                    "after": {
                        "status": "complete",
                        "result": True,
                        "events": [{"kind": "observation", "phase": "after"}],
                        "hashes": [expected_hash],
                    },
                }
            ],
            "stream_observations_changed": False,
        }
    ]


def test_partial_snapshot_is_visible_in_consecutive_status_changes(tmp_path):
    output = tmp_path / "partial-transitions.json"

    @diagnostics.snapshot
    def build(fail):
        with diagnostics.component_scope("reader"):
            if fail:
                raise ValueError("controlled local operation failure")
        return Evidence("stable")

    with diagnostics.diagnostics_session(output):
        build(False)
        with pytest.raises(ValueError, match="controlled local operation failure"):
            build(True)
        build(False)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"] is False
    assert report["errors"] == []
    for index, transition in enumerate(report["transitions"]):
        before, after = ("complete", "partial") if index == 0 else ("partial", "complete")
        assert transition["from_sequence"] == index + 1
        assert transition["to_sequence"] == index + 2
        assert transition["result_changed"] is True
        assert transition["status_changed"] is True
        assert transition["stream_observations_changed"] is False
        assert {change["path"][-1]["kind"] for change in transition["frame_changes"]} == {
            "snapshot",
            "reader",
        }
        for change in transition["frame_changes"]:
            assert change["before"]["status"] == before
            assert change["after"]["status"] == after
            assert change["before_frame_id"] == change["after_frame_id"]


def test_identity_dictionary_order_does_not_create_component_changes(tmp_path):
    output = tmp_path / "identity-order-transitions.json"

    @diagnostics.snapshot
    def build(identity):
        hasher = diagnostics.observed_sha256(stream="content")
        with diagnostics.component_scope("file", **identity):
            hasher.update(b"stable")
        return Evidence(hasher.hexdigest())

    with diagnostics.diagnostics_session(output):
        build({"name": "alpha", "category": "source"})
        build({"category": "source", "name": "alpha"})
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"] is True
    assert report["transitions"][0]["frame_changes"] == []
    assert report["transitions"][0]["stream_observations_changed"] is False


def test_component_occurrences_preserve_identity_and_compact_hierarchy(
    tmp_path: Path,
) -> None:
    output = tmp_path / "components.json"

    @diagnostics.snapshot
    def build() -> bool:
        with diagnostics.component_scope("branch", name="left"):
            with diagnostics.component_scope("leaf", group="g", index=1):
                pass
            # Equal identities with a different insertion order remain equal.
            with diagnostics.component_scope("leaf", index=1, group="g"):
                pass
            with diagnostics.component_scope("leaf", group="g", index=1):
                pass
            with diagnostics.component_scope("leaf", group="g", index=2):
                pass
        with (
            diagnostics.component_scope("branch", name="right"),
            diagnostics.component_scope("leaf", group="g", index=1),
        ):
            pass
        return True

    with diagnostics.diagnostics_session(output):
        assert build() is True

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"] is True
    assert report["errors"] == []
    frames = report["snapshots"][0]["frames"]
    assert [(frame["kind"], frame["identity"], frame["occurrence"]) for frame in frames] == [
        ("snapshot", {}, 0),
        ("branch", {"name": "left"}, 0),
        ("leaf", {"group": "g", "index": 1}, 0),
        ("leaf", {"group": "g", "index": 1}, 1),
        ("leaf", {"group": "g", "index": 1}, 2),
        ("leaf", {"group": "g", "index": 2}, 0),
        ("branch", {"name": "right"}, 0),
        ("leaf", {"group": "g", "index": 1}, 0),
    ]
    # IDs may be opaque, but must uniquely connect each child to its parent.
    assert all(type(frame["id"]) is int for frame in frames)
    assert len({frame["id"] for frame in frames}) == len(frames)
    root, left, *_, right, right_leaf = frames
    assert root["parent_id"] is None
    assert left["parent_id"] == right["parent_id"] == root["id"]
    assert all(frame["parent_id"] == left["id"] for frame in frames[2:6])
    assert right_leaf["parent_id"] == right["id"]
    for frame in frames:
        assert frame["status"] == "complete"
        assert frame["events"] == []
        assert frame["hashes"] == []
        # Published parent IDs carry the hierarchy without repeated ancestor
        # chains or a second, untrimmed copy of the frame list.
        assert "path" not in frame
