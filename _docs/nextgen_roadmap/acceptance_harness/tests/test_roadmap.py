"""Strong kill-tests for the planned operators. Each is designed to kill BOTH
the current v2.14.0 mutants on the construct AND the planned operator's future
mutant(s). On correct code every assertion holds, so the suite is green today.
"""

import pytest

from roadmap import regex_targets as rt
from roadmap import targets as t


def test_ror():
    # kills <= (current) AND >, >=, ==, != (future ROR matrix #3)
    assert t.ror(1, 2) is True
    assert t.ror(2, 2) is False
    assert t.ror(3, 2) is False


def test_crcr():
    assert t.crcr() == 7  # kills +1 (current) AND 0/1/-1/-7 (future CRCR #15)


def test_negate_cond():
    # future `if not flag` (#22) flips both outcomes
    assert t.negate_cond(True) == "t"
    assert t.negate_cond(False) == "f"


def test_force_cond():
    assert t.force_cond(5) == "pos"
    assert t.force_cond(1) == "pos"      # kills current number 0 -> 1 (boundary at x=1)
    assert t.force_cond(0) == "nonpos"   # kills current > -> >=
    assert t.force_cond(-1) == "nonpos"  # future if True/False (#23)


def test_collections():
    # future emptying (#38) AND current inner-number mutants
    assert t.coll_list() == [1, 2, 3]
    assert t.coll_dict() == {"a": 1, "b": 2}
    assert t.coll_set() == {1, 2, 3}
    assert t.coll_tuple() == (1, 2, 3)


def test_match_guard():
    assert t.match_guard(5) == "pos"
    assert t.match_guard(1) == "pos"     # kills current guard number 0 -> 1
    assert t.match_guard(0) == "other"   # kills current guard `>` -> `>=`
    assert t.match_guard(-1) == "other"  # future guard True/False (#41)


def test_aod_uoi():
    # kills AOD a(2)/b(3) (#2), UOI -a etc. (#12), current + -> -,*,/ …
    assert t.aod_uoi(2, 3) == 5


def test_counter():
    # current `self.value = None` neutralize AND future assignment-removal (#29)
    assert t.Counter().get() == 5


def test_guard_raise():
    assert t.guard_raise(3) == 3
    assert t.guard_raise(0) == 0  # kills current `<` -> `<=` and number 0 -> 1 (boundary at x=0)
    # current raise-removal AND future exception-swap (#44): exact type+msg
    with pytest.raises(ValueError, match=r"^negative$"):
        t.guard_raise(-1)


def test_calc_static_class():
    # @staticmethod/@classmethod: 0 mutants today (skipped); after backport the
    # mutants (x*2 -> x/2, 2 -> 3, return None, …) must be killed here.
    assert t.Calc.double(4) == 8
    assert t.Calc.triple(4) == 12


# --- regex suite (#42) ------------------------------------------------------

def test_regex_digits():
    assert rt.all_digits("12") is True   # kills \d->\D, \d->literal d
    assert rt.all_digits("1a") is False  # kills \d->[\d\D]
    assert rt.all_digits("") is False    # kills + -> * (quantifier)
    assert rt.all_digits("1") is True    # kills + -> {2,} (short->range)


def test_regex_class():
    assert rt.only_abc("abc") is True    # kills range [a-c]->[a-b]
    assert rt.only_abc("abd") is False   # kills range ->[a-d], negation, to-any
    assert rt.only_abc("") is False
    assert rt.only_abc("a") is True      # kills + -> {2,} (short->range)


def test_regex_prefix():
    assert rt.has_foo_prefix("foobar") is True
    assert rt.has_foo_prefix("xfoo") is False  # kills ^ anchor removal


def test_regex_repeat():
    assert rt.repeat_ab("abab") == "ab"
    assert rt.repeat_ab("aba") is None         # kills (ab)+ quantifier change
    assert rt.repeat_ab("ab") == "ab"          # kills (ab)+ -> (ab){2,}
    # group->non-capturing would break .group(1) -> error -> killed


def test_regex_lookahead():
    assert rt.foo_before_bar("foobar") is True
    assert rt.foo_before_bar("foobaz") is False  # kills look-around flip (?=)->(?!)
