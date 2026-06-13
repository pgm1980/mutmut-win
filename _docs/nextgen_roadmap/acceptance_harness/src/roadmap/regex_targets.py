"""Regex targets for the planned 14-sub-mutator suite (advanced #42).
Each pattern is passed as a string literal to `re.compile(...)`, so mutmut-win's
regex operator sees it. Inputs in the tests are chosen so each sub-mutation
changes the match result (and thus is killable). See ROADMAP_SPEC.md for the
per-sub-mutator expectation table.
"""

import re

_DIGITS = re.compile(r"\d+")          # shorthand \d (+ negation/any/nullify), quantifier +
_CLASS = re.compile(r"[a-c]+")        # char-class range ±1, negation, to-any
_PREFIX = re.compile(r"^foo")         # anchor removal
_REPEAT = re.compile(r"(ab)+")        # group->non-capturing (capture is used below), quantifier
_LOOK = re.compile(r"foo(?=bar)")     # look-around flip


def all_digits(s):
    return bool(_DIGITS.fullmatch(s))


def only_abc(s):
    return bool(_CLASS.fullmatch(s))


def has_foo_prefix(s):
    return bool(_PREFIX.search(s))


def repeat_ab(s):
    m = _REPEAT.fullmatch(s)
    return m.group(1) if m else None   # using group(1) kills group->non-capturing


def foo_before_bar(s):
    return bool(_LOOK.match(s))
