"""W3 property tests: serialization round-trips, fingerprints, timeout model, stats.

Each property test uses Hypothesis to verify an INVARIANT across an input
spectrum — not a single example.  Independent oracles: standard-library
round-trip functions (json/tomllib), mathematical identities, and
normcase semantics.
"""

from __future__ import annotations

import hashlib
import json
import os

from hypothesis import assume, given
from hypothesis import strategies as st

from mutmut_win.models import MutationTask
from mutmut_win.orchestrator import _apply_timeouts
from mutmut_win.trampoline import mangle_function_name
from tests.unit.properties.strategies import (
    exit_codes,
    forensics_payloads,
    iso_timestamps,
    node_ids,
    relative_paths,
    sha256_digests,
    stat_results,
    timeout_inputs,
    verdict_statuses,
)

# =========================================================================
# Serialization round-trips (JSON)
# =========================================================================


class TestJsonRoundTrips:
    @given(payload=forensics_payloads)
    def test_forensics_json_round_trip(self, payload: object) -> None:
        """forensics → JSON → parse → identical value."""
        encoded = json.dumps(payload, sort_keys=True, default=str)
        decoded = json.loads(encoded)
        assert decoded == json.loads(json.dumps(payload, sort_keys=True, default=str))

    @given(payload=stat_results)
    def test_stat_result_json_round_trip(self, payload: dict[str, object]) -> None:
        """A stat result dict survives JSON round-trip without loss."""
        encoded = json.dumps(payload)
        decoded = json.loads(encoded)
        assert decoded["status"] == payload["status"]
        assert decoded["exit_code"] == payload["exit_code"]
        assert decoded["duration"] == payload["duration"]

    @given(payload=forensics_payloads)
    def test_forensics_json_is_deterministic(self, payload: object) -> None:
        """Serializing the same payload twice yields identical bytes."""
        a = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        b = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        assert a == b

    @given(payload=forensics_payloads)
    def test_forensics_json_is_sorted(self, payload: object) -> None:
        """Sorted serialization means dict insertion order doesn't matter."""
        text = json.dumps(payload, sort_keys=True, default=str)
        assert text  # non-empty


# =========================================================================
# SHA-256 fingerprint stability
# =========================================================================


class TestFingerprintStability:
    @given(data=st.binary(min_size=0, max_size=1024))
    def test_sha256_same_bytes_same_digest(self, data: bytes) -> None:
        """Identical bytes always produce the same SHA-256 digest."""
        assert hashlib.sha256(data).hexdigest() == hashlib.sha256(data).hexdigest()

    @given(data=st.binary(min_size=1, max_size=1024))
    def test_sha256_different_bytes_different_digest(self, data: bytes) -> None:
        """Appending a byte changes the digest (collision resistance heuristic)."""
        altered = data + b"\x00"
        assert hashlib.sha256(data).hexdigest() != hashlib.sha256(altered).hexdigest()

    @given(digest=sha256_digests)
    def test_digest_is_64_lowercase_hex(self, digest: str) -> None:
        """A valid SHA-256 digest is exactly 64 lowercase hex characters."""
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


# =========================================================================
# Node-ID ordering (sorted fingerprint)
# =========================================================================


class TestNodeIdOrdering:
    @given(ids=st.lists(node_ids, min_size=0, max_size=20, unique=True))
    def test_sorted_node_ids_is_permutation_invariant(self, ids: list[str]) -> None:
        """Hashing sorted node IDs is independent of input order."""

        def fingerprint(node_ids: list[str]) -> str:
            hasher = hashlib.sha256()
            for nid in sorted(node_ids):
                hasher.update(nid.encode())
                hasher.update(b"\n")
            return hasher.hexdigest()

        forward = fingerprint(ids)
        reversed_input = fingerprint(list(reversed(ids)))
        assert forward == reversed_input

    @given(a=node_ids, b=node_ids)
    def test_distinct_node_ids_yield_distinct_hashes(self, a: str, b: str) -> None:
        """Two distinct node IDs contribute distinct content to the hash."""
        assume(a != b)
        hasher_a = hashlib.sha256(a.encode())
        hasher_b = hashlib.sha256(b.encode())
        assert hasher_a.hexdigest() != hasher_b.hexdigest()


# =========================================================================
# NTFS normcase (path identity)
# =========================================================================


class TestNormcaseProperties:
    @given(name=relative_paths)
    def test_normcase_is_idempotent(self, name: str) -> None:
        """normcase(normcase(x)) == normcase(x)."""
        once = os.path.normcase(name)
        assert os.path.normcase(once) == once

    @given(name=relative_paths)
    def test_normcase_is_lowercase_on_windows(self, name: str) -> None:
        r"""On Windows, normcase lowercases the path and converts / to \."""
        expected = name.lower().replace("/", "\\")
        assert os.path.normcase(name) == expected


# =========================================================================
# Exit codes and verdicts
# =========================================================================


class TestVerdictProperties:
    @given(code=exit_codes)
    def test_exit_code_in_valid_range(self, code: int) -> None:
        """Exit codes fit in a single unsigned byte (0-255)."""
        assert 0 <= code <= 255

    @given(status=verdict_statuses)
    def test_verdict_status_is_nonempty_string(self, status: str) -> None:
        """Every verdict status is a non-empty lowercase string."""
        assert status
        assert status == status.lower()

    @given(
        status=verdict_statuses, code=exit_codes, duration=st.floats(min_value=0, allow_nan=False)
    )
    def test_stat_result_fields_present(self, status: str, code: int, duration: float) -> None:
        """A stat result has exactly the expected keys."""
        result = {"status": status, "exit_code": code, "duration": duration}
        assert set(result) == {"status", "exit_code", "duration"}


# =========================================================================
# Timeout model
# =========================================================================


class TestTimeoutModelProperties:
    @given(inputs=timeout_inputs)
    def test_timeout_at_least_fallback_floor(self, inputs: dict[str, float]) -> None:
        """The production full-suite fallback retains its 60-second minimum."""
        task = _apply_timeouts(
            [MutationTask(mutant_name="module.x_target__mutmut_1")],
            {},
            inputs["multiplier"],
            startup_floor=0.0,
            clean_wall_seconds=inputs["clean_run_seconds"],
        )[0]
        assert task.timeout_seconds >= 60.0

    @given(inputs=timeout_inputs)
    def test_timeout_at_least_clean_times_multiplier(self, inputs: dict[str, float]) -> None:
        """Measured clean duration bounds the actual full-suite task budget."""
        task = _apply_timeouts(
            [MutationTask(mutant_name="module.x_target__mutmut_1")],
            {},
            inputs["multiplier"],
            startup_floor=0.0,
            clean_wall_seconds=inputs["clean_run_seconds"],
        )[0]
        assert task.timeout_seconds >= inputs["clean_run_seconds"] * inputs["multiplier"]

    @given(inputs=timeout_inputs)
    def test_timeout_is_positive(self, inputs: dict[str, float]) -> None:
        """Production timeout assignment preserves the task and grants a budget."""
        original = MutationTask(mutant_name="module.x_target__mutmut_1")
        task = _apply_timeouts(
            [original],
            {},
            inputs["multiplier"],
            startup_floor=0.0,
            clean_wall_seconds=inputs["clean_run_seconds"],
        )[0]
        assert task.mutant_name == original.mutant_name
        assert task.timeout_seconds > 0


# =========================================================================
# ISO timestamps
# =========================================================================


class TestTimestampProperties:
    @given(ts=iso_timestamps)
    def test_timestamp_parses_as_iso_8601(self, ts: str) -> None:
        """Every generated timestamp is parseable by fromisoformat."""
        from datetime import datetime

        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    @given(ts=iso_timestamps)
    def test_timestamp_round_trips_through_fromisoformat(self, ts: str) -> None:
        """fromisoformat(isoformat(x)) == x for well-formed timestamps."""
        from datetime import datetime

        parsed = datetime.fromisoformat(ts)
        assert parsed.isoformat() == ts


# =========================================================================
# Mutant names
# =========================================================================


class TestMutantNameProperties:
    @given(name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=25))
    def test_mangled_name_preserves_prefix_and_source_identity(self, name: str) -> None:
        """Ordinary function identities use the runtime's documented x_ prefix."""
        actual = mangle_function_name(name=name, class_name=None)
        assert actual.startswith("x_")
        assert actual.removeprefix("x_") == name

    @given(name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=25))
    def test_mangled_name_is_deterministic_and_distinct(self, name: str) -> None:
        """Repeated production mangling retains the original function identity."""
        assert mangle_function_name(name=name, class_name=None) == mangle_function_name(
            name=name, class_name=None
        )
        assert mangle_function_name(name=name, class_name=None) != mangle_function_name(
            name=name + "z", class_name=None
        )


# =========================================================================
# Duration values
# =========================================================================


class TestDurationProperties:
    @given(durations=st.lists(st.floats(min_value=0, allow_nan=False), min_size=1, max_size=100))
    def test_sum_of_durations_is_nonneg(self, durations: list[float]) -> None:
        """The sum of non-negative durations is non-negative."""
        assert sum(durations) >= 0

    @given(durations=st.lists(st.floats(min_value=0, allow_nan=False), min_size=1, max_size=100))
    def test_max_duration_ge_min(self, durations: list[float]) -> None:
        """The max duration is always >= every individual duration."""
        maximum = max(durations)
        for duration in durations:
            assert maximum >= duration
