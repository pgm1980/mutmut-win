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

import pytest

from mutmut_win.constants import Profile
from mutmut_win.node_mutation import mutation_operators, operators_for_profile

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

    def test_exactly_fifteen_base_nine_advanced_zero_all(self) -> None:
        counts = Counter(prof for (_t, _op, prof) in mutation_operators)
        assert counts[Profile.BASIC] == 15
        assert counts[Profile.ADVANCED] == 9
        assert counts[Profile.ALL] == 0  # aggressive operators arrive in a later phase

    def test_advanced_extras_are_exactly_the_nine(self) -> None:
        advanced = {
            op.__name__ for (_t, op, prof) in mutation_operators if prof is Profile.ADVANCED
        }
        assert advanced == _ADVANCED_EXTRA_NAMES

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

    def test_advanced_yields_base_plus_extras(self) -> None:
        assert len(operators_for_profile(Profile.ADVANCED)) == 24  # 15 + 9

    def test_all_equals_advanced_in_phase_one(self) -> None:
        # No ALL-tagged operators exist yet, so `all` == `advanced` until the
        # aggressive operators land in a later phase.
        assert len(operators_for_profile(Profile.ALL)) == len(
            operators_for_profile(Profile.ADVANCED)
        )

    def test_returns_two_tuples_without_the_profile_tag(self) -> None:
        for pair in operators_for_profile(Profile.ADVANCED):
            assert len(pair) == 2  # (node_type, operator_fn) — Profile stripped

    def test_basic_is_a_strict_subset_of_advanced(self) -> None:
        basic = set(operators_for_profile(Profile.BASIC))
        advanced = set(operators_for_profile(Profile.ADVANCED))
        assert basic < advanced  # strict: advanced has the 9 extras on top
