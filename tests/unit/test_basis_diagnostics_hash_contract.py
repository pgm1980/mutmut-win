"""Published hash observations retain bytes, update counts, and frame attribution."""

from __future__ import annotations

import hashlib
import hmac
import json

from mutmut_win import basis_diagnostics as diagnostics


def test_published_hash_report_accounts_for_chunks_streams_and_frame_returns(tmp_path):
    output = tmp_path / "hash-contract.json"
    key = bytes(range(32))

    @diagnostics.snapshot
    def build():
        left = diagnostics.observed_sha256(b"L0", stream="left")
        right = diagnostics.observed_sha256(b"R", stream="right")
        left.update(b"+")
        with diagnostics.component_scope("payload", name="shared-child"):
            left.update(b"abc")
            left.update(b"DE")
            right.update(b"uvw")
            right.update(b"x")
        left.update(b"tail")
        right.update(b"!!")
        return left.hexdigest(), right.hexdigest()

    with diagnostics.diagnostics_session(output) as collector:
        # Fix only the private test key, before any snapshot or token exists.
        collector.key = key
        actual = build()
        assert not output.exists()

    assert actual == (
        hashlib.sha256(b"L0+abcDEtail").hexdigest(),
        hashlib.sha256(b"Ruvwx!!").hexdigest(),
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"] is True
    assert report["errors"] == []
    assert len(report["snapshots"]) == 1
    snapshot = report["snapshots"][0]
    assert snapshot["status"] == "complete"
    # Each expected token hashes the known byte sequence independently of the
    # collector's update/attribution logic, including the noncontiguous root bytes.
    assert snapshot["streams"] == [
        {
            "id": 0,
            "name": "left",
            "updates": 5,
            "bytes": 12,
            "hmac": hmac.digest(key, b"L0+abcDEtail", hashlib.sha256).hex(),
            "attribution": [
                {"frame_id": 0, "updates": 2, "bytes": 3},
                {"frame_id": 1, "updates": 2, "bytes": 5},
                {"frame_id": 0, "updates": 1, "bytes": 4},
            ],
        },
        {
            "id": 1,
            "name": "right",
            "updates": 4,
            "bytes": 7,
            "hmac": hmac.digest(key, b"Ruvwx!!", hashlib.sha256).hex(),
            "attribution": [
                {"frame_id": 0, "updates": 1, "bytes": 1},
                {"frame_id": 1, "updates": 2, "bytes": 4},
                {"frame_id": 0, "updates": 1, "bytes": 2},
            ],
        },
    ]
    root, child = snapshot["frames"]
    assert (root["id"], root["parent_id"], root["kind"], root["status"]) == (
        0,
        None,
        "snapshot",
        "complete",
    )
    assert (child["id"], child["parent_id"], child["kind"], child["status"]) == (
        1,
        0,
        "payload",
        "complete",
    )
    assert root["hashes"] == [
        {
            "stream_id": 0,
            "stream": "left",
            "updates": 3,
            "bytes": 7,
            "hmac": hmac.digest(key, b"L0+tail", hashlib.sha256).hex(),
        },
        {
            "stream_id": 1,
            "stream": "right",
            "updates": 2,
            "bytes": 3,
            "hmac": hmac.digest(key, b"R!!", hashlib.sha256).hex(),
        },
    ]
    assert child["hashes"] == [
        {
            "stream_id": 0,
            "stream": "left",
            "updates": 2,
            "bytes": 5,
            "hmac": hmac.digest(key, b"abcDE", hashlib.sha256).hex(),
        },
        {
            "stream_id": 1,
            "stream": "right",
            "updates": 2,
            "bytes": 4,
            "hmac": hmac.digest(key, b"uvwx", hashlib.sha256).hex(),
        },
    ]


def test_published_empty_stream_has_no_update_or_frame_contribution(tmp_path):
    output = tmp_path / "empty-stream-contract.json"
    key = bytes(range(32))

    @diagnostics.snapshot
    def build():
        return diagnostics.observed_sha256(stream="empty").hexdigest()

    with diagnostics.diagnostics_session(output) as collector:
        collector.key = key
        actual = build()

    assert actual == hashlib.sha256(b"").hexdigest()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"] is True
    assert report["errors"] == []
    assert len(report["snapshots"]) == 1
    snapshot = report["snapshots"][0]
    assert snapshot["status"] == "complete"
    assert snapshot["streams"] == [
        {
            "id": 0,
            "name": "empty",
            "updates": 0,
            "bytes": 0,
            "hmac": hmac.digest(key, b"", hashlib.sha256).hex(),
            "attribution": [],
        }
    ]
    assert len(snapshot["frames"]) == 1
    assert snapshot["frames"][0]["hashes"] == []
