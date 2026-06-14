"""Regex targets for the 14-sub-mutator suite (advanced #42).

Each pattern is compiled INSIDE its function (not at module level) on purpose:
mutmut-win mutates function bodies, so a module-level ``_X = re.compile(...)``
would never see the regex operator. With the ``re.compile(r"...")`` call inside
the function, the regex sub-mutators fire on the pattern literal. Inputs in the
tests are chosen so each sub-mutation changes the match result (and is thus
killable). See ROADMAP_SPEC.md for the per-sub-mutator expectation table.
"""

import re


def all_digits(s):
    # \d+ : shorthand \d (-> \D / d / [\d\D]); quantifier + (removal / * / {n,} / lazy)
    return bool(re.compile(r"\d+").fullmatch(s))


def only_abc(s):
    # [a-c]+ : char-class range +-1, negation, child-removal, to-any; quantifier +
    return bool(re.compile(r"[a-c]+").fullmatch(s))


def has_foo_prefix(s):
    # ^foo : anchor removal ^
    return bool(re.compile(r"^foo").search(s))


def repeat_ab(s):
    # (ab)+ : group->non-capturing (killed via .group(1)), quantifier +
    m = re.compile(r"(ab)+").fullmatch(s)
    return m.group(1) if m else None


def foo_before_bar(s):
    # foo(?=bar) : look-around flip (?=) -> (?!)
    return bool(re.compile(r"foo(?=bar)").match(s))
