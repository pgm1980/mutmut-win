"""Published hash observations retain bytes, update counts, and frame attribution."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING

from mutmut_win import basis_diagnostics as diagnostics

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


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


def test_active_digest_is_exact_bytes_and_reading_it_does_not_consume_hash_state(
    tmp_path: Path,
) -> None:
    @diagnostics.snapshot
    def observe() -> tuple[bytes, bytes, str]:
        hasher = diagnostics.observed_sha256(b"prefix:", stream="digest-contract")
        hasher.update(b"known payload")
        first = hasher.digest()
        hasher.update(b":tail")
        return first, hasher.digest(), hasher.hexdigest()

    output = tmp_path / "digest.json"
    with diagnostics.diagnostics_session(output):
        first, final, hexadecimal = observe()

    assert type(first) is bytes
    assert type(final) is bytes
    assert first == hashlib.sha256(b"prefix:known payload").digest()
    assert final == hashlib.sha256(b"prefix:known payload:tail").digest()
    assert hexadecimal == hashlib.sha256(b"prefix:known payload:tail").hexdigest()
    assert json.loads(output.read_text(encoding="utf-8"))["diagnostics_complete"] is True


def test_private_token_events_bind_known_bytes_and_keep_their_safe_identity(tmp_path: Path) -> None:
    key = bytes(range(32))
    first = b"PRIVATE_FIRST_OBSERVED_VALUE"
    second = b"PRIVATE_SECOND_OBSERVED_VALUE"

    @diagnostics.snapshot
    def observe() -> None:
        diagnostics.record_token("configuration-value", first, name="FIRST", scope="fixture")
        diagnostics.record_token("configuration-value", second, name="SECOND", scope="fixture")

    output = tmp_path / "tokens.json"
    with diagnostics.diagnostics_session(output) as collector:
        # The existing hash-contract fixture establishes this known-key oracle.
        collector.key = key
        observe()

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["snapshots"][0]["frames"][0]["events"] == [
        {
            "kind": "configuration-value",
            "name": "FIRST",
            "scope": "fixture",
            "token": hmac.digest(key, first, hashlib.sha256).hex(),
        },
        {
            "kind": "configuration-value",
            "name": "SECOND",
            "scope": "fixture",
            "token": hmac.digest(key, second, hashlib.sha256).hex(),
        },
    ]
    assert report["diagnostics_complete"] is True
    text = output.read_text(encoding="utf-8")
    assert first.decode("ascii") not in text
    assert second.decode("ascii") not in text
    assert key.hex() not in text


def test_report_names_a_provider_fault_without_replacing_canonical_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "provider-fault.json"
    private_message = "provider-only-private-detail"

    def unavailable_provider(*_args: object, **_kwargs: object) -> None:
        raise OSError(private_message)

    @diagnostics.snapshot
    def build() -> str:
        # Restore the auxiliary provider before later updates and finalization.
        with monkeypatch.context() as patch:
            patch.setattr(diagnostics.hmac, "new", unavailable_provider)
            hasher = diagnostics.observed_sha256(b"canonical", stream="context")
        hasher.update(b"-tail")
        return hasher.hexdigest()

    with diagnostics.diagnostics_session(output):
        actual = build()

    assert actual == hashlib.sha256(b"canonical-tail").hexdigest()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["snapshots"][0]["status"] == "complete"
    assert report["diagnostics_complete"] is False
    assert report["errors"] == [{"operation": "begin_hash_stream", "exception_type": "OSError"}]
    stderr = capsys.readouterr().err
    assert "incomplete" in stderr
    assert private_message not in output.read_text(encoding="utf-8")
    assert private_message not in stderr
    assert not diagnostics.is_observing()
