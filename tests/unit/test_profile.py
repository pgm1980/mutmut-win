"""Phase 1 of the nextgen-operator roadmap: the mutation-profile scaffold.

``Profile`` (``basic`` < ``advanced`` < ``all``) gates which operators the
generator emits:

* ``advanced`` — the DEFAULT, and equal to today's behaviour: mutmut's 15
  base operators plus mutmut-win's 9 extras.
* ``basic`` — strips down to the 15 base operators (strict mutmut parity).
* ``all`` — adds the aggressive operators in a later phase; today it equals
  ``advanced`` (no ALL-tagged operators exist yet).

These tests pin the enum ordering/parsing, the registry tagging (exactly 15
base + 9 advanced, the nine named), and the pure ``operators_for_profile``
filter. They are the C1 wave of Phase 1.
"""

from __future__ import annotations

from collections import Counter
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win.config import MutmutConfig
from mutmut_win.constants import Profile
from mutmut_win.file_setup import (
    config_fingerprint_matches,
    create_mutants_for_file,
    write_all_mutants_to_file,
)
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.node_mutation import mutation_operators, operators_for_profile
from mutmut_win.orchestrator import MutationOrchestrator

if TYPE_CHECKING:
    from pathlib import Path

# The nine mutmut-win extras — everything beyond mutmut's 15-operator base —
# verified against the origin comments in node_mutation.py ("unique to
# mutmut-win" / "inspired by …"). Pinned here so a stray re-tag is caught.
_ADVANCED_EXTRA_NAMES = {
    "operator_regex",
    "operator_math_methods",
    "operator_return_value",
    "operator_conditional_expression",
    "operator_void_call_removal",
    "operator_raise_removal",
    "operator_collection_neutralize",
    "operator_comprehension_filter_removal",
    "operator_or_default",
}

# Phase 2 advanced operators (operator roadmap §3), grown wave by wave.
_PHASE2_ADVANCED_OPERATORS = {
    "operator_relational_matrix",  # W1 #3 ROR matrix
    "operator_number_crcr",  # W2 #15 number CRCR
    "operator_negate_condition",  # W3 #22 negate condition
    "operator_force_condition",  # W3 #23 force condition
    "operator_collection_empty",  # W4 #38 collection emptying
    "operator_match_guard",  # W5 #41 match-guard force
}

# Phase 4 all-tier aggressive operators (operator roadmap §4), grown wave by wave.
_PHASE4_ALL_OPERATORS = {
    "operator_aod",  # W1 #2 arithmetic operand deletion
    "operator_exception_swap",  # W1 #44 exception swap
}


class TestProfileEnum:
    def test_ordered_by_inclusiveness(self) -> None:
        assert Profile.BASIC < Profile.ADVANCED < Profile.ALL

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("basic", Profile.BASIC),
            ("advanced", Profile.ADVANCED),
            ("all", Profile.ALL),
            ("ADVANCED", Profile.ADVANCED),  # case-insensitive
            ("  all  ", Profile.ALL),  # surrounding whitespace tolerated
        ],
    )
    def test_from_name_parses(self, name: str, expected: Profile) -> None:
        assert Profile.from_name(name) is expected

    def test_from_name_rejects_unknown(self) -> None:
        with pytest.raises(ValueError, match="unknown mutation profile"):
            Profile.from_name("aggressive")

    @pytest.mark.parametrize("profile", list(Profile))
    def test_to_name_roundtrip(self, profile: Profile) -> None:
        assert Profile.from_name(profile.to_name()) is profile

    def test_to_name_is_lowercase(self) -> None:
        assert Profile.ADVANCED.to_name() == "advanced"


class TestRegistryTagging:
    def test_every_entry_carries_a_profile_tag(self) -> None:
        # Each registry row is (node_type, operator_fn, Profile).
        for entry in mutation_operators:
            assert len(entry) == 3
            assert isinstance(entry[2], Profile)

    def test_base_fifteen_advanced_and_all_grow(self) -> None:
        counts = Counter(prof for (_t, _op, prof) in mutation_operators)
        assert counts[Profile.BASIC] == 15  # mutmut parity — invariant across phases
        # advanced/all are pinned by NAME (the entry count runs higher once an
        # operator registers on several node types, e.g. negate/force on If).
        advanced_names = {
            op.__name__ for (_t, op, prof) in mutation_operators if prof is Profile.ADVANCED
        }
        assert advanced_names == _ADVANCED_EXTRA_NAMES | _PHASE2_ADVANCED_OPERATORS
        all_names = {op.__name__ for (_t, op, prof) in mutation_operators if prof is Profile.ALL}
        assert all_names == _PHASE4_ALL_OPERATORS

    def test_phase1_extras_and_phase2_operators_are_all_advanced(self) -> None:
        advanced = {
            op.__name__ for (_t, op, prof) in mutation_operators if prof is Profile.ADVANCED
        }
        assert _ADVANCED_EXTRA_NAMES.issubset(advanced)  # the 9 Phase-1 extras stay advanced
        assert _PHASE2_ADVANCED_OPERATORS.issubset(advanced)  # each Phase-2 op is advanced

    def test_base_entries_are_disjoint_from_the_extras(self) -> None:
        base_names = {op.__name__ for (_t, op, prof) in mutation_operators if prof is Profile.BASIC}
        assert base_names.isdisjoint(_ADVANCED_EXTRA_NAMES)
        # 15 base ENTRIES but 14 distinct names — operator_assignment is
        # registered twice (cst.Assign and cst.AnnAssign).
        assert len(base_names) == 14


class TestOperatorsForProfile:
    def test_basic_yields_only_the_base_operators(self) -> None:
        pairs = operators_for_profile(Profile.BASIC)
        assert len(pairs) == 15  # 15 base entries
        names = {op.__name__ for (_t, op) in pairs}
        assert names.isdisjoint(_ADVANCED_EXTRA_NAMES)

    def test_advanced_includes_every_advanced_entry(self) -> None:
        # Filter invariant (grows per phase without edits): advanced keeps every
        # entry tagged <= ADVANCED; basic keeps only the base entries.
        advanced_pairs = {(t, op) for (t, op, p) in mutation_operators if p <= Profile.ADVANCED}
        assert set(operators_for_profile(Profile.ADVANCED)) == advanced_pairs
        basic_pairs = {(t, op) for (t, op, p) in mutation_operators if p <= Profile.BASIC}
        assert set(operators_for_profile(Profile.BASIC)) == basic_pairs

    def test_advanced_is_a_strict_subset_of_all(self) -> None:
        # Phase 4 added ALL-tagged operators, so `all` now strictly includes
        # everything `advanced` has plus the aggressive operators.
        advanced = set(operators_for_profile(Profile.ADVANCED))
        all_ops = set(operators_for_profile(Profile.ALL))
        assert advanced < all_ops

    def test_all_includes_every_entry(self) -> None:
        # Filter invariant for ALL (grows per wave without test edits).
        all_pairs = {(t, op) for (t, op, p) in mutation_operators if p <= Profile.ALL}
        assert set(operators_for_profile(Profile.ALL)) == all_pairs

    def test_returns_two_tuples_without_the_profile_tag(self) -> None:
        for pair in operators_for_profile(Profile.ADVANCED):
            assert len(pair) == 2  # (node_type, operator_fn) — Profile stripped

    def test_basic_is_a_strict_subset_of_advanced(self) -> None:
        basic = set(operators_for_profile(Profile.BASIC))
        advanced = set(operators_for_profile(Profile.ADVANCED))
        assert basic < advanced  # strict: advanced has the 9 extras on top


class TestProfileThreadsThroughGeneration:
    """C2: the active profile reaches the generator through
    ``mutate_file_contents`` and ``write_all_mutants_to_file``.

    ``a or b`` is mutated by ``operator_or_default`` — an *advanced* extra — so
    basic must yield strictly fewer mutants than advanced, while the default
    stays equal to advanced (behaviour-neutral).
    """

    _OR_SNIPPET = "def pick(a, b):\n    return a or b\n"

    def test_basic_yields_fewer_mutants_than_advanced(self) -> None:
        _c1, basic_names = mutate_file_contents(
            "m.py", self._OR_SNIPPET, active_profile=Profile.BASIC
        )
        _c2, advanced_names = mutate_file_contents(
            "m.py", self._OR_SNIPPET, active_profile=Profile.ADVANCED
        )
        assert len(basic_names) < len(advanced_names)

    def test_default_is_behaviour_neutral_equals_advanced(self) -> None:
        _c1, default_names = mutate_file_contents("m.py", self._OR_SNIPPET)
        _c2, advanced_names = mutate_file_contents(
            "m.py", self._OR_SNIPPET, active_profile=Profile.ADVANCED
        )
        assert default_names == advanced_names

    def test_write_all_mutants_threads_the_profile(self) -> None:
        basic = write_all_mutants_to_file(
            out=StringIO(),
            source=self._OR_SNIPPET,
            filename="m.py",
            active_profile=Profile.BASIC,
        )
        advanced = write_all_mutants_to_file(
            out=StringIO(),
            source=self._OR_SNIPPET,
            filename="m.py",
            active_profile=Profile.ADVANCED,
        )
        assert len(basic) < len(advanced)


class TestMutationProfileConfig:
    """C3: ``MutmutConfig.mutation_profile`` parses profile names, defaults to
    advanced, rejects unknown values, and survives a model_dump round-trip.
    """

    def test_default_is_advanced(self) -> None:
        assert MutmutConfig().mutation_profile is Profile.ADVANCED

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("basic", Profile.BASIC),
            ("advanced", Profile.ADVANCED),
            ("all", Profile.ALL),
            ("ALL", Profile.ALL),  # case-insensitive, via Profile.from_name
            (Profile.BASIC, Profile.BASIC),  # an actual Profile passes through
        ],
    )
    def test_parses_name_or_profile(self, value: object, expected: Profile) -> None:
        assert MutmutConfig(mutation_profile=value).mutation_profile is expected

    def test_rejects_unknown_profile(self) -> None:
        with pytest.raises(ValidationError):
            MutmutConfig(mutation_profile="aggressive")

    @given(profile=st.sampled_from(list(Profile)))
    def test_model_dump_roundtrip(self, profile: Profile) -> None:
        original = MutmutConfig(mutation_profile=profile)
        restored = MutmutConfig(**original.model_dump())
        assert restored.mutation_profile is profile


class TestProfileWiredThroughGeneration:
    """C4: the configured profile reaches both generation paths — the real run
    (create_mutants_for_file, via the multiprocessing pool) and the dry-run
    preview (mutate_file_contents). ``a or b`` is mutated only by the advanced
    operator_or_default, so basic yields strictly fewer mutants.
    """

    _OR_SNIPPET = "def pick(a, b):\n    return a or b\n"

    def test_create_mutants_for_file_threads_the_profile(self, tmp_path: Path) -> None:
        src = tmp_path / "m.py"
        src.write_text(self._OR_SNIPPET, encoding="utf-8")
        # Distinct output paths so the unchanged-staging fast path never fires.
        basic, _w1, _f1 = create_mutants_for_file(
            src, tmp_path / "basic.py", active_profile=Profile.BASIC
        )
        advanced, _w2, _f2 = create_mutants_for_file(
            src, tmp_path / "advanced.py", active_profile=Profile.ADVANCED
        )
        assert len(basic) < len(advanced)

    def _dry_run_count(self, profile: Profile) -> int:
        cfg = MutmutConfig(paths_to_mutate=["src"], mutation_profile=profile)
        orch = MutationOrchestrator(cfg, runner=MagicMock(), executor=MagicMock())
        return orch.dry_run().total_mutants

    def test_dry_run_respects_the_config_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "m.py").write_text(self._OR_SNIPPET, encoding="utf-8")
        assert self._dry_run_count(Profile.BASIC) < self._dry_run_count(Profile.ADVANCED)

    def test_profile_change_invalidates_the_generation_fingerprint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A profile switch changes the mutant universe, so on unchanged source
        # it must regenerate (fast path disabled) rather than reuse stale
        # mutants — i.e. it must change the config fingerprint.
        monkeypatch.chdir(tmp_path)
        advanced = MutmutConfig(paths_to_mutate=["src"], mutation_profile=Profile.ADVANCED)
        assert config_fingerprint_matches(advanced) is False  # first run persists it
        assert config_fingerprint_matches(advanced) is True  # unchanged → fast path
        basic = MutmutConfig(paths_to_mutate=["src"], mutation_profile=Profile.BASIC)
        assert config_fingerprint_matches(basic) is False  # profile change → regenerate

    def test_pool_worker_threads_the_profile(self, tmp_path: Path) -> None:
        # The picklable pool worker carries the profile in its args tuple and
        # passes it on to create_mutants_for_file.
        from mutmut_win.orchestrator import _create_mutants_worker

        src = tmp_path / "m.py"
        src.write_text(self._OR_SNIPPET, encoding="utf-8")

        def _count(profile: Profile, out_name: str) -> int:
            args = (str(src), src, tmp_path / out_name, None, False, profile)
            _rel, names, err, _warns, _fast = _create_mutants_worker(args)
            assert err is None
            return len(names)

        assert _count(Profile.BASIC, "b.py") < _count(Profile.ADVANCED, "a.py")


class TestProfileStartupHint:
    """C5: the orchestrator announces the active profile + its operator count
    once per run, with a parity note only under basic (no warning tone).
    """

    def _orch(self, profile: Profile) -> MutationOrchestrator:
        return MutationOrchestrator(
            MutmutConfig(mutation_profile=profile),
            runner=MagicMock(),
            executor=MagicMock(),
        )

    def test_advanced_hint_is_a_single_exact_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Exact match pins the whole line so any string/void-call mutation of the
        # hint is killed; the count is the live advanced operator count (grows
        # per phase), so the assertion needs no per-wave edit.
        n = len(operators_for_profile(Profile.ADVANCED))
        self._orch(Profile.ADVANCED)._print_profile_hint()
        assert capsys.readouterr().out == f"profile=advanced — {n} operators active\n"

    def test_basic_hint_is_exact_and_adds_the_parity_note(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._orch(Profile.BASIC)._print_profile_hint()
        assert capsys.readouterr().out == (
            "profile=basic — 15 operators active\n"
            "  (basic = mutmut parity; '--profile advanced' or '--profile all' "
            "enables more operators)\n"
        )
