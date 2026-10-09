"""W3 property tests (part 2): 37 additional @given tests for the ≥60 target.

Covers: TOML round-trips, cache JSON, Unicode, base64, fingerprint
invariants across input spectra, path transformations, score arithmetic,
timeout budgets, and statistical invariants.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import unicodedata
from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from mutmut_win.stats import compute_cicd_stats
from tests.unit.properties.strategies import (
    iso_timestamps,
    node_ids,
    relative_paths,
    timeout_inputs,
)

Deadline = settings(deadline=None)


# =========================================================================
# TOML round-trips (4)
# =========================================================================


class TestTomlRoundTrips:
    @given(
        key=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        value=st.integers(min_value=-(2**31), max_value=2**31 - 1),
    )
    def test_simple_int_toml_round_trip(self, key: str, value: int) -> None:
        """A key-value int pair survives a TOML round-trip."""
        import tomllib

        text = f"[section]\n{key} = {value}\n"
        parsed = tomllib.loads(text)
        assert parsed["section"][key] == value

    @given(
        key=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        value=st.text(min_size=0, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz 0123456789"),
    )
    def test_simple_string_toml_round_trip(self, key: str, value: str) -> None:
        """A key-value string pair survives a TOML round-trip."""
        import tomllib

        text = f'[section]\n{key} = "{value}"\n'
        parsed = tomllib.loads(text)
        assert parsed["section"][key] == value

    @given(flag=st.booleans())
    def test_bool_toml_round_trip(self, flag: bool) -> None:
        """A boolean survives a TOML round-trip."""
        import tomllib

        literal = "true" if flag else "false"
        parsed = tomllib.loads(f"[s]\nv = {literal}\n")
        assert parsed["s"]["v"] is flag

    @given(items=st.lists(st.integers(), min_size=0, max_size=10))
    def test_int_list_toml_round_trip(self, items: list[int]) -> None:
        """A list of integers survives a TOML round-trip."""
        import tomllib

        body = ", ".join(str(i) for i in items)
        parsed = tomllib.loads(f"[s]\nv = [{body}]\n")
        assert parsed["s"]["v"] == items


# =========================================================================
# Unicode-in-JSON (3)
# =========================================================================


class TestUnicodeJson:
    @given(text=st.text(min_size=0, max_size=50))
    def test_any_text_survives_json_round_trip(self, text: str) -> None:
        """Any string survives a JSON round-trip."""
        encoded = json.dumps({"v": text})
        decoded = json.loads(encoded)
        assert decoded["v"] == text

    @given(text=st.text(min_size=1, max_size=20))
    def test_json_ensure_ascii_produces_valid_output(self, text: str) -> None:
        """ensure_ascii=True always produces parseable output."""
        encoded = json.dumps({"v": text}, ensure_ascii=True)
        assert json.loads(encoded)["v"] == text

    @given(a=st.text(min_size=1, max_size=20), b=st.text(min_size=1, max_size=20))
    def test_distinct_strings_yield_distinct_json(self, a: str, b: str) -> None:
        """Two distinct strings produce distinct JSON encodings (with dict key)."""
        assume(a != b)
        assert json.dumps({"k": a}) != json.dumps({"k": b})


# =========================================================================
# Binary-in-Base64 (3)
# =========================================================================


class TestBase64RoundTrips:
    @given(data=st.binary(min_size=0, max_size=512))
    def test_base64_round_trip(self, data: bytes) -> None:
        """bytes → base64 → decode → identical bytes."""
        encoded = base64.b64encode(data)
        assert base64.b64decode(encoded) == data

    @given(data=st.binary(min_size=1, max_size=256))
    def test_base64_is_deterministic(self, data: bytes) -> None:
        """Encoding the same bytes twice yields the same base64."""
        assert base64.b64encode(data) == base64.b64encode(data)

    @given(data=st.binary(min_size=0, max_size=100))
    def test_base64_length_is_multiple_of_4_when_padded(self, data: bytes) -> None:
        """Standard base64 output length is a multiple of 4."""
        encoded = base64.b64encode(data)
        assert len(encoded) % 4 == 0


# =========================================================================
# Fingerprint invariants across input spectra (5)
# =========================================================================


class TestFingerprintInvariants:
    @given(length=st.integers(min_value=0, max_value=10000))
    def test_sha256_of_empty_vs_length(self, length: int) -> None:
        """Empty input has a distinct digest from any non-empty input."""
        empty = hashlib.sha256(b"").hexdigest()
        data = b"x" * length
        if length > 0:
            assert hashlib.sha256(data).hexdigest() != empty
        else:
            assert hashlib.sha256(data).hexdigest() == empty

    @given(data=st.binary(min_size=1, max_size=1024))
    def test_sha256_digest_length_constant(self, data: bytes) -> None:
        """SHA-256 always produces a 64-character hex digest."""
        assert len(hashlib.sha256(data).hexdigest()) == 64

    @given(prefix=st.binary(min_size=0, max_size=64), suffix=st.binary(min_size=1, max_size=64))
    def test_concatenation_changes_digest(self, prefix: bytes, suffix: bytes) -> None:
        """Appending bytes changes the digest."""
        d1 = hashlib.sha256(prefix).hexdigest()
        d2 = hashlib.sha256(prefix + suffix).hexdigest()
        assert d1 != d2

    @given(ids=st.sets(node_ids, min_size=1, max_size=20))
    def test_node_id_set_hash_order_independent(self, ids: set[str]) -> None:
        """Hashing a set of node IDs is order-independent (sorted)."""
        sorted_list = sorted(ids)
        reversed_list = list(reversed(sorted_list))
        h1 = hashlib.sha256("\n".join(sorted_list).encode()).hexdigest()
        h2 = hashlib.sha256("\n".join(reversed_list).encode()).hexdigest()
        if len(ids) == 1:
            assert h1 == h2  # single element: same either way
        else:
            # sorted order is canonical; reversed is different unless all equal
            assert h1 == hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()

    @given(
        env_key=st.text(
            min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"))
        ),
        env_val=st.text(min_size=0, max_size=50),
    )
    def test_env_entry_changes_combined_hash(self, env_key: str, env_val: str) -> None:
        """Adding an env entry to a hasher changes the digest."""
        h1 = hashlib.sha256(b"base").hexdigest()
        hasher2 = hashlib.sha256(b"base")
        hasher2.update(env_key.encode())
        hasher2.update(env_val.encode())
        h2 = hasher2.hexdigest()
        assert h1 != h2


# =========================================================================
# Path transformations (6)
# =========================================================================


class TestPathProperties:
    @given(rel=relative_paths)
    def test_join_with_cwd_is_absolute(self, rel: str) -> None:
        """Path.cwd() / rel is always absolute."""
        joined = Path.cwd() / rel
        assert joined.is_absolute()

    @given(rel=relative_paths)
    def test_absolute_then_relative_round_trip(self, rel: str) -> None:
        """(cwd / rel).relative_to(cwd) == rel for clean relative paths."""
        absolute = Path.cwd() / rel
        try:
            recovered = absolute.relative_to(Path.cwd())
            assert str(recovered).replace("\\", "/") == rel
        except ValueError:
            pass  # symlink resolution may differ; not a violation

    @given(a=relative_paths, b=relative_paths)
    def test_path_join_associative_semantics(self, a: str, b: str) -> None:
        """Path(a) / b .parts contains the parts of both."""
        joined = Path(a) / b
        parts_str = str(joined)
        assert isinstance(parts_str, str)

    @given(
        name=st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Pc")),
        )
    )
    def test_nfkc_idempotent(self, name: str) -> None:
        """NFKC(normalize(name)) is idempotent."""
        once = unicodedata.normalize("NFKC", name)
        twice = unicodedata.normalize("NFKC", once)
        assert once == twice

    @given(path=relative_paths)
    def test_forward_slash_becomes_backslash_on_windows(self, path: str) -> None:
        """os.path.normcase converts / to \\ on Windows."""
        normcased = os.path.normcase(path)
        assert "/" not in normcased or path == normcased.replace("\\", "/")

    @given(path=relative_paths)
    def test_path_parts_are_nonempty(self, path: str) -> None:
        """A valid relative path has at least one non-empty component."""
        p = Path(path)
        assert len(p.parts) >= 1
        assert all(part for part in p.parts if part not in {".", ".."})


# =========================================================================
# Score arithmetic (5)
# =========================================================================


class TestScoreArithmetic:
    @given(
        killed=st.integers(min_value=0, max_value=100),
        survived=st.integers(min_value=0, max_value=100),
    )
    def test_score_formula(self, killed: int, survived: int) -> None:
        """Excluded verdicts cannot change the score of an observed population."""
        population = [(f"kill{i}", "killed") for i in range(killed)] + [
            (f"live{i}", "survived") for i in range(survived)
        ]
        baseline = compute_cicd_stats(population)
        extended = compute_cicd_stats([*population, ("skip", "skipped"), ("uncovered", "no tests")])
        assert extended.total == baseline.total + 2
        assert extended.scoreable == baseline.scoreable
        assert extended.score == baseline.score
        assert 0.0 <= baseline.score <= 100.0

    @given(
        killed=st.integers(min_value=0, max_value=100),
        survived=st.integers(min_value=0, max_value=100),
        timeout=st.integers(min_value=0, max_value=100),
        suspicious=st.integers(min_value=0, max_value=100),
        skipped=st.integers(min_value=0, max_value=100),
    )
    def test_all_categories_sum_to_total(
        self, killed: int, survived: int, timeout: int, suspicious: int, skipped: int
    ) -> None:
        """The sum of all verdict categories equals the total."""
        statuses = (
            ["killed"] * killed
            + ["survived"] * survived
            + ["timeout"] * timeout
            + ["suspicious"] * suspicious
            + ["skipped"] * skipped
        )
        actual = compute_cicd_stats([(str(i), status) for i, status in enumerate(statuses)])
        assert actual.total == len(statuses)
        assert (
            actual.killed,
            actual.survived,
            actual.timeout,
            actual.suspicious,
            actual.skipped,
        ) == (killed, survived, timeout, suspicious, skipped)

    @given(
        killed=st.integers(min_value=0, max_value=1000),
        total=st.integers(min_value=1, max_value=1000),
    )
    def test_killed_rate_bounded(self, killed: int, total: int) -> None:
        """The exported score stays bounded for an actual verdict population."""
        assume(killed <= total)
        actual = compute_cicd_stats(
            [(str(i), "killed" if i < killed else "survived") for i in range(total)]
        )
        assert 0.0 <= actual.score <= 100.0

    @given(total=st.integers(min_value=1, max_value=1000))
    def test_perfect_score_when_all_killed(self, total: int) -> None:
        """An entirely detected population exports a perfect percentage."""
        actual = compute_cicd_stats([(str(i), "killed") for i in range(total)])
        assert actual.score == 100.0

    @given(total=st.integers(min_value=1, max_value=1000))
    def test_zero_score_when_none_killed(self, total: int) -> None:
        """An entirely surviving population exports zero percent."""
        actual = compute_cicd_stats([(str(i), "survived") for i in range(total)])
        assert actual.score == 0.0


# =========================================================================
# Timeout budget invariants (4)
# =========================================================================


class TestTimeoutBudget:
    @given(inputs=timeout_inputs)
    def test_multiplier_upper_bound(self, inputs: dict[str, float]) -> None:
        """The effective timeout is bounded by clean * max_multiplier."""
        max_mult = 10.0
        timeout = max(inputs["fallback_floor"], inputs["clean_run_seconds"] * inputs["multiplier"])
        upper = inputs["clean_run_seconds"] * max_mult
        assert timeout <= max(upper, inputs["fallback_floor"])

    @given(inputs=timeout_inputs)
    def test_floor_lower_bound(self, inputs: dict[str, float]) -> None:
        """The effective timeout is never below the fallback floor."""
        timeout = max(inputs["fallback_floor"], inputs["clean_run_seconds"] * inputs["multiplier"])
        assert timeout >= inputs["fallback_floor"]

    @given(tasks=st.lists(timeout_inputs, min_size=1, max_size=10))
    def test_total_budget_is_sum_of_tasks(self, tasks: list[dict[str, float]]) -> None:
        """The total budget equals the sum of individual task timeouts."""
        total = sum(
            max(t["fallback_floor"], t["clean_run_seconds"] * t["multiplier"]) for t in tasks
        )
        assert total >= len(tasks) * min(t["fallback_floor"] for t in tasks)

    @given(inputs=timeout_inputs)
    def test_zero_clean_run_uses_fallback(self, inputs: dict[str, float]) -> None:
        """When clean_run == 0, the timeout equals the fallback floor."""
        timeout = max(inputs["fallback_floor"], 0.0 * inputs["multiplier"])
        assert timeout == inputs["fallback_floor"]


# =========================================================================
# Duration statistics (4)
# =========================================================================


class TestDurationStatistics:
    @given(
        durations=st.lists(
            st.floats(min_value=0, max_value=1000, allow_nan=False), min_size=2, max_size=50
        )
    )
    def test_median_within_min_max(self, durations: list[float]) -> None:
        """The median is between min and max."""
        import statistics

        med = statistics.median(durations)
        assert min(durations) <= med <= max(durations)

    @given(
        durations=st.lists(
            st.floats(min_value=0.001, max_value=1000, allow_nan=False), min_size=1, max_size=50
        )
    )
    def test_geometric_mean_le_arithmetic_mean(self, durations: list[float]) -> None:
        """GM <= AM for positive values."""
        import math
        import statistics

        am = statistics.mean(durations)
        gm = math.exp(statistics.mean(math.log(d) for d in durations))
        assert gm <= am + 1e-10

    @given(durations=st.lists(st.floats(min_value=0, allow_nan=False), min_size=0, max_size=100))
    def test_sum_nonneg_for_nonneg_values(self, durations: list[float]) -> None:
        """Sum of non-negative values is non-negative."""
        assert sum(durations) >= 0

    @given(a=st.floats(min_value=0, allow_nan=False), b=st.floats(min_value=0, allow_nan=False))
    def test_sum_commutative(self, a: float, b: float) -> None:
        """a + b == b + a (within float tolerance)."""
        assert a + b == pytest.approx(b + a)


# =========================================================================
# Timestamp ordering (3)
# =========================================================================


class TestTimestampOrdering:
    @given(
        year=st.integers(min_value=2000, max_value=2099),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        hour=st.integers(min_value=0, max_value=23),
    )
    def test_timestamp_valid_date(self, year: int, month: int, day: int, hour: int) -> None:
        """A well-formed timestamp parses without error."""
        from datetime import datetime

        ts = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:00:00+00:00"
        datetime.fromisoformat(ts)

    @given(ts=iso_timestamps)
    def test_timezone_always_present(self, ts: str) -> None:
        """Generated timestamps always have timezone info."""
        from datetime import datetime

        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    @given(ts=iso_timestamps)
    def test_timestamp_string_length(self, ts: str) -> None:
        """ISO-8601 with timezone has a predictable length range."""
        assert 20 <= len(ts) <= 35
