"""Sibling-name budgets for long, valid Windows file names (M-010).

The sibling schema ``.{name}.mutmut-atomic-{token}.tmp`` adds 52 UTF-16
units to the target's base name.  From 204 units on, a perfectly valid
target name therefore made the sibling component exceed NTFS's 255-unit
limit and ``os.open`` failed with a raw ``OSError`` whose message named
only the random temp path — never the length as the cause.  The sibling
builder now truncates the EMBEDDED name (never the random token) to the
component budget and, where the parent allows it, to the legacy
total-path budget; an OS length rejection that truncation cannot cure is
translated into :class:`AtomicPathLengthError` naming the measured
lengths and the LongPathsEnabled option.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import mutmut_win.atomic_file as atomic_module
from mutmut_win.atomic_file import atomic_write_bytes


class TestSimulatedNtfsComponentLimit:
    def test_long_basename_sibling_is_truncated_to_the_ntfs_component_budget(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A valid 204-unit basename must stay publishable (deterministic).

        ``os.open`` is wrapped to enforce the NTFS component limit exactly
        as the real filesystem does, independent of the host's filesystem
        and LongPathsEnabled setting: any '.mutmut-atomic-' component above
        255 UTF-16 units is rejected with winerror 123.
        """
        real_open = os.open

        def ntfs_component_guard(
            path: str | os.PathLike[str],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            name = Path(str(path)).name
            if ".mutmut-atomic-" in name and len(name) > 255:  # ASCII: len == utf16
                raise OSError(22, "simulated NTFS component limit", str(path), 123)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", ntfs_component_guard)
        target = tmp_path / ("a" * 204)

        atomic_write_bytes(target, b"x")
        monkeypatch.undo()

        assert target.read_bytes() == b"x"
        assert not list(tmp_path.glob("*.mutmut-atomic-*.tmp"))


class TestRealFilePublication:
    def test_atomic_write_publishes_valid_204_char_basename(self, tmp_path: Path) -> None:
        """End-to-end on the real filesystem; supplementary to the simulation.

        Creating and deleting the 204-unit target itself proves the host
        can address such names at all; where LongPathsEnabled is off and
        the temp-dir prefix already exceeds the 259-unit budget, this
        precondition fails and the simulation test above carries the
        regression.
        """
        target = tmp_path / ("a" * 200 + ".txt")
        probe_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(target, probe_flags)
        except OSError as exc:
            pytest.skip(f"host cannot address a 204-unit basename (LongPathsEnabled off?): {exc}")
        os.close(fd)
        target.unlink()

        atomic_write_bytes(target, b"x")

        assert target.read_bytes() == b"x"
        assert not list(tmp_path.glob("*.mutmut-atomic-*.tmp"))


class TestLengthFailureDiagnosis:
    def test_sibling_length_failure_names_the_cause(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A length rejection surfaces as AtomicPathLengthError with hint.

        The sibling builder is pinned to an overlong name (294 units) so
        the OS rejection cannot be pre-empted by truncation, and ``os.open``
        is wrapped to reject sibling opens with winerror 123 regardless of
        the host filesystem.
        """
        token_box = {"value": None}
        real_open = os.open

        def refusing_sibling_open(
            path: str | os.PathLike[str],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            name = Path(str(path)).name
            if ".mutmut-atomic-" in name:
                raise OSError(22, "simulated name rejection", str(path), 123)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        def overlong_sibling(path: Path, token: str) -> str:  # noqa: ARG001 - signature parity with _sibling_name
            token_box["value"] = token
            return "y" * 243 + f".mutmut-atomic-{token}.tmp"

        monkeypatch.setattr(atomic_module, "_sibling_name", overlong_sibling, raising=False)
        monkeypatch.setattr(os, "open", refusing_sibling_open)
        target = tmp_path / "marker.sentinel"

        with pytest.raises(
            atomic_module.AtomicPathLengthError, match="LongPathsEnabled"
        ) as exc_info:
            atomic_write_bytes(target, b"x")
        monkeypatch.undo()

        assert exc_info.value.errno == 22
        assert getattr(exc_info.value, "winerror", None) == 123
        assert exc_info.value.filename is not None
        assert ".mutmut-atomic-" in str(exc_info.value.filename)
        assert isinstance(exc_info.value.__cause__, OSError)

    def test_length_classification_uses_winerror_not_exception_type(self) -> None:
        """winerror 3/206 arrive as FileNotFoundError; only winerror classifies."""
        is_length_failure = atomic_module._is_path_length_failure

        overlong_component = Path("C:\\") / ("d" * 300) / "leaf.txt"
        assert is_length_failure(FileNotFoundError(2, "simulated", "x", 206), overlong_component)
        assert is_length_failure(FileNotFoundError(2, "simulated", "x", 3), overlong_component)

        overlong_total = Path("C:\\") / ("a" * 250) / ("b" * 250)
        assert is_length_failure(OSError(22, "simulated", "x", 123), overlong_total)

        # Within both budgets, a winerror-3 failure is a genuine
        # "path not found" and must not be re-labelled.
        within_budgets = Path("C:\\projects") / "marker.sentinel"
        assert not is_length_failure(FileNotFoundError(2, "simulated", "x", 3), within_budgets)
        assert not is_length_failure(OSError(5, "simulated", "x", 5), within_budgets)
        assert not is_length_failure(OSError(22, "simulated", "x"), within_budgets)


class TestSiblingNameBudgets:
    """Pure string contracts of the sibling-name builder.

    The default parent ``C:\\`` (exactly 3 UTF-16 units) makes the legacy
    total-path budget coincide with the component budget (259 - 3 - 2 - 51
    = 203), so these tests pin the component rule; the total-path rule is
    pinned separately with longer parents below.
    """

    TOKEN = "ab" * 16

    @staticmethod
    def _sibling(name: str, parent: str = "C:\\") -> str:
        return atomic_module._sibling_name(Path(parent) / name, TestSiblingNameBudgets.TOKEN)

    def test_short_names_keep_the_exact_historic_schema(self) -> None:
        sibling = self._sibling("marker.sentinel")
        assert sibling == f".marker.sentinel.mutmut-atomic-{self.TOKEN}.tmp"

    def test_204_unit_basename_is_truncated_to_203(self) -> None:
        sibling = self._sibling("a" * 204)
        assert sibling == f".{'a' * 203}.mutmut-atomic-{self.TOKEN}.tmp"
        # A longer parent tightens the total-path budget below the
        # component budget: the embedding shrinks further, not the token.
        deeper = self._sibling("a" * 204, parent="C:\\d")
        assert deeper == f".{'a' * 202}.mutmut-atomic-{self.TOKEN}.tmp"

    def test_lone_surrogate_names_stay_measurable(self) -> None:
        # 202 'a' plus one lone surrogate (U+DC80) = 203 UTF-16 units: NTFS
        # accepts such names via surrogatepass, so the measurement must not
        # raise UnicodeEncodeError and the name must survive untruncated
        # (component and total-path budget both still fit at 255/259).
        name = "a" * 202 + "\udc80"
        assert atomic_module._utf16_len(name) == 203
        sibling = self._sibling(name)
        assert sibling == f".{name}.mutmut-atomic-{self.TOKEN}.tmp"

    def test_astral_boundary_truncates_whole_code_points(self) -> None:
        fits = "a" * 201 + "\U0001f600"
        assert atomic_module._utf16_len(fits) == 203
        assert self._sibling(fits) == f".{fits}.mutmut-atomic-{self.TOKEN}.tmp"

        # 204 units: the astral character counts as TWO units and is
        # dropped whole — never split into half a surrogate pair.
        overflows = "a" * 202 + "\U0001f600"
        assert self._sibling(overflows) == f".{'a' * 202}.mutmut-atomic-{self.TOKEN}.tmp"

    def test_meta_sidecar_overflow_is_truncated(self) -> None:
        # A 199-unit source basename plus '.meta' = 204 units: the derived
        # sidecar name is valid, only its sibling overflows.
        sibling = self._sibling("m" * 199 + ".meta")
        assert sibling == f".{'m' * 199}.met.mutmut-atomic-{self.TOKEN}.tmp"

    def test_total_path_budget_keeps_sibling_within_legacy_limits(self) -> None:
        for parent_units in (50, 150, 205, 206):
            parent = "C:\\" + "p" * (parent_units - 3)
            assert atomic_module._utf16_len(parent) == parent_units
            sibling = self._sibling("n" * 250, parent=parent)
            assert atomic_module._utf16_len(sibling) <= 255
            assert atomic_module._utf16_len(parent) + 1 + atomic_module._utf16_len(sibling) <= 259

    def test_parent_beyond_the_legacy_window_shrinks_embedding_to_zero(self) -> None:
        # Residual window (documented, diagnosed via AtomicPathLengthError):
        # a parent of 207 units cannot carry ANY sibling within 259 units;
        # the embedding shrinks to zero and the token keeps the name unique.
        parent = "C:\\" + "p" * (207 - 3)
        sibling = self._sibling("n" * 250, parent=parent)
        assert sibling == f"..mutmut-atomic-{self.TOKEN}.tmp"


_FORBIDDEN_NAME_CHARS = set('\\/:*?"<>|')


class TestSiblingNameProperty:
    @given(
        name=st.text(
            alphabet=st.characters(exclude_categories=("Cc",)),
            min_size=1,
            max_size=255,
        ).filter(
            lambda value: not (set(value) & _FORBIDDEN_NAME_CHARS) and value not in (".", "..")
        ),
        token=st.text(alphabet="0123456789abcdef", min_size=32, max_size=32),
    )
    def test_sibling_name_always_fits_both_budgets(self, name: str, token: str) -> None:
        utf16_len = atomic_module._utf16_len
        sibling = atomic_module._sibling_name(Path("C:\\") / name, token)

        assert sibling.startswith(".")
        assert sibling.endswith(f".mutmut-atomic-{token}.tmp")
        assert utf16_len(sibling) <= 255
        if utf16_len(name) <= 203:
            assert sibling == f".{name}.mutmut-atomic-{token}.tmp"
