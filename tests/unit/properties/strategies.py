"""Reusable Hypothesis strategies for property-based tests (W3, TM-05).

Every strategy is round-trip-secured: generate → serialize → deserialize →
compare must preserve identity.  Used by tests/unit/properties/.
"""

from __future__ import annotations

from hypothesis import strategies as st

# --- Paths (relative, POSIX-safe, Windows-compatible) ---

_path_component = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd", "Pc", "Pd"),
        min_codepoint=0x61,
        max_codepoint=0x7A,
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: s not in {".", "..", ""})

relative_paths = st.lists(_path_component, min_size=1, max_size=5).map(
    lambda parts: "/".join(parts)
)

# --- Exit codes ---
exit_codes = st.integers(min_value=0, max_value=255)

# --- Mutant names ---
_mutant_suffix = st.integers(min_value=1, max_value=999)
_mutant_func = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=20,
)
mutant_names = st.builds(
    lambda func, num: f"src/mod.py::{func}__mutmut_{num}",
    _mutant_func,
    _mutant_suffix,
)

# --- Verdict statuses ---
verdict_statuses = st.sampled_from(
    ["killed", "survived", "timeout", "suspicious", "segfault", "no tests"]
)

# --- Stat/result payloads ---
stat_results = st.fixed_dictionaries(
    {
        "status": verdict_statuses,
        "exit_code": exit_codes,
        "duration": st.floats(min_value=0.0, max_value=3600.0, allow_nan=False),
    }
)

# --- Fingerprint digests ---
sha256_digests = st.text(
    alphabet="0123456789abcdef",
    min_size=64,
    max_size=64,
)

# --- ISO timestamps with timezone ---
iso_timestamps = st.builds(
    lambda y, m, d, h, mi, s: f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}+00:00",
    st.integers(min_value=2000, max_value=2099),
    st.integers(min_value=1, max_value=12),
    st.integers(min_value=1, max_value=28),
    st.integers(min_value=0, max_value=23),
    st.integers(min_value=0, max_value=59),
    st.integers(min_value=0, max_value=59),
)

# --- Node IDs (pytest) ---
node_ids = st.builds(
    lambda path, func: f"tests/{path}::{func}",
    _path_component,
    _mutant_func,
)

# --- Timeout model inputs ---
timeout_inputs = st.fixed_dictionaries(
    {
        "clean_run_seconds": st.floats(min_value=0.1, max_value=600.0, allow_nan=False),
        "multiplier": st.floats(min_value=1.0, max_value=10.0, allow_nan=False),
        "fallback_floor": st.floats(min_value=1.0, max_value=120.0, allow_nan=False),
    }
)

# --- Forensics payloads (JSON-compatible) ---
forensics_payloads = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=0, max_value=2**31 - 1)
    | st.text(max_size=100),
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Pc")),
            ),
            children,
            max_size=5,
        )
    ),
    max_leaves=10,
)
