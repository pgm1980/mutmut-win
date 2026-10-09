"""S3-001: every inherited test input belongs to the reuse context."""

import hashlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win import stats


def _environment_digest() -> str:
    hasher = hashlib.sha256()
    stats._hash_verdict_relevant_environment(hasher)
    return hasher.hexdigest()


@pytest.mark.parametrize("name", ["STRICT_TESTS", "DEMO_TEST_INPUT", "USER_SETTING_CUSTOM"])
def test_unlisted_test_input_changes_reuse_context(name: str) -> None:
    """S3-001 binds changed, missing and empty inherited test inputs."""
    with pytest.MonkeyPatch.context() as patch:
        patch.delenv(name, raising=False)
        absent = _environment_digest()
        patch.setenv(name, "")
        empty = _environment_digest()
        patch.setenv(name, "strict")
        strict = _environment_digest()
        assert _environment_digest() == strict
        patch.setenv(name, "lax")
        lax = _environment_digest()
        assert len({absent, empty, strict, lax}) == 4
        patch.setenv(name, "strict")
        assert _environment_digest() == strict


@given(
    suffix=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_", min_size=1, max_size=20),
    value=st.text(
        alphabet=st.characters(exclude_categories=("Cs",), exclude_characters="\x00"), max_size=40
    ),
)
def test_arbitrary_environment_input_is_bound(suffix: str, value: str) -> None:
    """S3-001 exercises the product hash for arbitrary unknown input names."""
    with pytest.MonkeyPatch.context() as patch:
        name = "S3_APPLICATION_" + suffix
        patch.setenv(name, value)
        first = _environment_digest()
        patch.setenv(name, value + "_changed")
        assert _environment_digest() != first
        patch.setenv(name, value)
        assert _environment_digest() == first
