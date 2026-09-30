"""Regex mutation engine for mutmut-win.

Mutates regex patterns found in ``re.*()`` calls. This is a unique feature
— no other Python mutation testing tool supports regex mutations.

The full 14-sub-mutator suite (v2.18.0), all string-based on a lightweight
class-span tokenizer (``_class_spans`` / ``_in_class``):
1. **Anchors (#1):** remove ``^ $ \\A \\Z \\b \\B``.
2. **Quantifiers (#2-#6):** removal; ``+``<->``*`` swap; short->range
   (``?``->``{1}``, ``+``->``{2,}``); reluctant greedy->lazy (``a+``->``a+?``);
   brace ``{n,m}`` quantity ±1.
3. **Shorthands (#11-#13):** negation (``\\d``<->``\\D``), nullification
   (``\\d``->``d``), to-any (``\\d``->``[\\d\\D]``).
4. **Character classes (#7-#10):** negation toggle (``[abc]``<->``[^abc]``),
   child-removal, range ±1 (``[a-z]``->``[b-z]``/``[a-y]``), to-any.
5. **Groups / look-around (#14, +15):** flip ``(?=)``<->``(?!)`` and
   ``(?<=)``<->``(?<!)``; capturing ``(abc)``->non-capturing ``(?:abc)``.

Every candidate is validated via ``re.compile()`` and de-duplicated — invalid
or repeated patterns are silently dropped; at most ``MAX_MUTATIONS_PER_PATTERN``
survive per pattern.
"""

from __future__ import annotations

import itertools
import re
import sys
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Highest valid Unicode codepoint (``sys.maxunicode``, 0x10FFFF on the
#: supported runtime); chr() raises for anything outside ``0.._MAX_UNICODE_CODEPOINT``.
_MAX_UNICODE_CODEPOINT: int = sys.maxunicode

#: Maximum mutations per single regex pattern (prevents combinatorial explosion
#: on pathological patterns). Raised in Phase 3 (v2.18.0) from 5 so the full
#: 14-sub-mutator suite can surface on a single construct.  Since M-100 the
#: candidate pipeline is consumed lazily, so this cap also bounds how many
#: candidates are ever materialized (memory is O(cap x pattern length), not
#: O(candidates x pattern length)).
MAX_MUTATIONS_PER_PATTERN: int = 12

# ---------------------------------------------------------------------------
# Quantifier patterns (applied to the raw regex string)
# ---------------------------------------------------------------------------
#: Matches a quantifier and its optional lazy marker. Group 1 is the base
#: quantifier (+, *, ?, {n}, {n,}, {n,m}); group 2 is "" (greedy) or "?" (lazy),
#: so ``a+?`` is captured as one unit instead of ``+`` and ``?`` separately.
_QUANTIFIER_RE = re.compile(
    r"""
    (?<![\\(])         # not after a backslash (\+) or '(' (the ? in (?=...) etc.)
    (                  # group 1: the base quantifier
        [+*?]          # simple quantifiers
      | \{\d+\}        # {n}
      | \{\d+,\d*\}    # {n,m} or {n,}
    )
    (\??)             # group 2: optional lazy marker
    """,
    re.VERBOSE,
)


def mutate_regex_pattern(pattern: str) -> list[str]:
    """Generate mutations for a single regex pattern string.

    Args:
        pattern: The raw regex pattern (without delimiters/quotes).

    Returns:
        A list of mutated patterns. Each is a valid regex (verified via
        ``re.compile``). At most ``MAX_MUTATIONS_PER_PATTERN`` are returned.
    """
    mutations_iter = itertools.chain(
        _iter_quantifiers(pattern),
        _iter_char_classes(pattern),
        _iter_anchors(pattern),
        _iter_classes(pattern),
        _iter_groups(pattern),
    )

    # Validate, dedupe (issue #132 / 360°-C5: two generators can emit the
    # same candidate — duplicates would create same-named mutants) and
    # filter invalid ones.  The chain is consumed lazily so the cap also
    # bounds materialization (M-100); ``seen`` tracks valid candidates only.
    valid: list[str] = []
    seen: set[str] = set()
    for m in mutations_iter:
        if m == pattern or m in seen:
            continue  # skip no-ops and duplicates
        if _is_valid_regex(m):
            valid.append(m)
            seen.add(m)
        if len(valid) >= MAX_MUTATIONS_PER_PATTERN:
            break

    return valid


def _brace_variants(brace: str) -> list[str]:
    """Quantity ±1 for a ``{n}`` / ``{n,m}`` / ``{n,}`` quantifier (#3/#4).

    Guards against negative counts and ``{0}``; the few remaining invalid
    candidates (e.g. ``{2,1}`` from ``{2,2}``) are dropped by the ``re.compile``
    gate in :func:`mutate_regex_pattern`.
    """
    inner = brace[1:-1]
    out: list[str] = []
    if "," in inner:
        lo_str, hi_str = inner.split(",")
        lo = int(lo_str)
        out.append(f"{{{lo + 1},{hi_str}}}")  # lo+1
        if lo > 0:
            out.append(f"{{{lo - 1},{hi_str}}}")  # lo-1
        if hi_str:  # bounded {n,m}
            hi = int(hi_str)
            out.append(f"{{{lo},{hi + 1}}}")  # hi+1
            out.append(f"{{{lo},{hi - 1}}}")  # hi-1 (may be invalid -> filtered)
    else:  # exact {n}
        n = int(inner)
        out.append(f"{{{n + 1}}}")
        if n > 1:
            out.append(f"{{{n - 1}}}")
    return out


def _iter_quantifiers(pattern: str) -> Iterator[str]:
    """Lazily yield quantifier mutations (sub-mutators #2-#6).

    Per quantifier: removal (#2); reluctant greedy->lazy (#6, skipping the exact
    ``{n}`` and an already-lazy quantifier); the require-count swaps (``+``<->``*``)
    and short->range tightenings (#5: ``?``->``{1}``, ``+``->``{2,}``); and brace
    ``{...}`` quantity ±1 (#3/#4). Invalid or duplicate candidates are dropped
    downstream by ``re.compile`` and the ``seen`` set in
    :func:`mutate_regex_pattern`.
    """
    class_spans = _class_spans(pattern)

    for match in _QUANTIFIER_RE.finditer(pattern):
        if _in_class(match.start(), class_spans):
            # Inside ``[...]`` these glyphs are literals (or class syntax),
            # never repetition operators.
            continue
        base, lazy = match.group(1), match.group(2)
        start, end = match.start(), match.end()
        is_exact = base.startswith("{") and "," not in base

        replacements: list[str] = [""]  # #2 removal of the whole quantifier
        if not lazy and not is_exact:
            replacements.append(base + "?")  # #6 reluctant: greedy -> lazy

        if base == "+":
            replacements.append("*")  # require-at-least-one -> require-zero-or-more
            replacements.append("{2,}")  # #5 short->range: at least two
        elif base == "*":
            replacements.append("+")  # require-zero-or-more -> require-at-least-one
        elif base == "?":
            replacements.append("{1}")  # #5 short->range: exactly one
        else:  # brace {n} / {n,m} / {n,} — the only remaining quantifier kind
            replacements.extend(_brace_variants(base))  # #3/#4 quantity ±1

        for repl in replacements:
            yield pattern[:start] + repl + pattern[end:]


def _mutate_quantifiers(pattern: str) -> list[str]:
    """List form of :func:`_iter_quantifiers` (kept for direct tests)."""
    return list(_iter_quantifiers(pattern))


#: Shorthand character-class letters (``\d \D \w \W \s \S``).
_SHORTHAND_LETTERS: frozenset[str] = frozenset("dDwWsS")


def _shorthand_positions(pattern: str) -> list[tuple[int, str]]:
    """Find unescaped shorthand classes (``\\d``, ``\\D``, ``\\w`` …) in *pattern*.

    Returns ``(backslash_index, letter)`` pairs. Escape-aware, so a literal
    ``\\\\d`` (an escaped backslash followed by ``d``) is NOT reported as a
    ``\\d`` shorthand.
    """
    positions: list[tuple[int, str]] = []
    i, n = 0, len(pattern)
    while i < n:
        if pattern[i] == "\\":
            if i + 1 < n and pattern[i + 1] in _SHORTHAND_LETTERS:
                positions.append((i, pattern[i + 1]))
            i += 2  # skip the whole escape pair
            continue
        i += 1
    return positions


def _iter_char_classes(pattern: str) -> Iterator[str]:
    """Lazily yield shorthand character-class mutations (#11-#13).

    Per unescaped shorthand (``\\d`` etc.): #11 negation (``\\d`` <-> ``\\D`` via
    a case swap), #12 nullification (``\\d`` -> the literal ``d``), and #13
    to-any (``\\d`` -> ``[\\d\\D]``). #13 fires only OUTSIDE a character class,
    since ``[\\d]`` -> ``[[\\d\\D]]`` would be a (wrong) nested class. Every
    occurrence is mutated, not just the first.
    """
    spans = _class_spans(pattern)
    for idx, letter in _shorthand_positions(pattern):
        negated = letter.swapcase()
        rest = pattern[idx + 2 :]
        # #11 negation: \d <-> \D
        yield f"{pattern[:idx]}\\{negated}{rest}"
        # #12 nullification: \d -> d
        yield f"{pattern[:idx]}{letter}{rest}"
        # #13 to-any: \d -> [\d\D] (outside a class only)
        if not _in_class(idx, spans):
            yield f"{pattern[:idx]}[\\{letter}\\{negated}]{rest}"


def _mutate_char_classes(pattern: str) -> list[str]:
    """List form of :func:`_iter_char_classes` (kept for direct tests)."""
    return list(_iter_char_classes(pattern))


#: A single-char range ``X-Y`` inside a class body (both ends unescaped).
_RANGE_RE = re.compile(r"(?<!\\)([^\\])-([^\\])")


def _class_members(content: str) -> list[tuple[int, int]]:
    """Split a character-class body into member units as ``(start, end)`` indices.

    A member is a single literal, an escaped pair (``\\d``, ``\\]``, ``\\\\``), or
    a range ``X-Y``. Used by #8 child-removal. The caller skips bodies that start
    with a literal ``]``, so the first char here is never the class terminator.
    """
    members: list[tuple[int, int]] = []
    i, n = 0, len(content)
    while i < n:
        start = i
        i += 2 if content[i] == "\\" and i + 1 < n else 1
        if i < n - 1 and content[i] == "-":  # a '-' with a char after it -> range
            i += 1  # consume '-'
            i += 2 if content[i] == "\\" and i + 1 < n else 1
        members.append((start, i))
    return members


def _iter_classes(pattern: str) -> Iterator[str]:
    """Lazily yield character-class mutations (sub-mutators #7-#10).

    Per ``[...]`` span: #7 negation toggle (``[abc]`` <-> ``[^abc]``); #10 to-any
    (``[...]`` -> ``[\\w\\W]``); #8 child-removal (drop one member, needs >= 2 so
    the class stays non-empty); #9 range ±1 (``[a-z]`` -> ``[b-z]`` / ``[a-y]``).
    #8/#9 are skipped for a body starting with a literal ``]`` (member parsing is
    unreliable there). Empty classes and invalid ranges (``b-a``) are dropped by
    the ``re.compile`` gate in :func:`mutate_regex_pattern`.

    ``body`` (the class minus a leading ``^``) and ``mark`` (the ``^`` or ``""``)
    are derived independently from ``negated`` so the two cannot compensate for a
    mutation in one another.
    """
    for start, end in _class_spans(pattern):
        inner = pattern[start + 1 : end - 1]  # everything between [ and ]
        negated = inner.startswith("^")
        body = inner[1:] if negated else inner
        mark = "^" if negated else ""
        before, after = pattern[:start], pattern[end:]

        # #7 negation toggle
        if negated:
            yield f"{before}[{body}]{after}"
        else:
            yield f"{before}[^{body}]{after}"
        # #10 to-any
        yield f"{before}[\\w\\W]{after}"

        if body.startswith("]"):
            continue  # literal-] first member: skip the parsing-based #8/#9

        # #8 child-removal (>= 2 members keeps the class non-empty)
        members = _class_members(body)
        if len(members) >= 2:
            for ms, me in members:
                yield f"{before}[{mark}{body[:ms] + body[me:]}]{after}"
        # #9 range ±1
        for m in _RANGE_RE.finditer(body):
            lo, hi = ord(m.group(1)), ord(m.group(2))
            for lo2, hi2 in ((lo + 1, hi), (lo, hi - 1)):
                # chr() is only defined on the Unicode codepoint domain: a
                # single-point range at either bound (U+0000 or U+10FFFF)
                # shifts one end out of it and used to abort generation.
                if not (0 <= lo2 <= _MAX_UNICODE_CODEPOINT and 0 <= hi2 <= _MAX_UNICODE_CODEPOINT):
                    continue
                new_body = body[: m.start()] + chr(lo2) + "-" + chr(hi2) + body[m.end() :]
                yield f"{before}[{mark}{new_body}]{after}"


def _mutate_classes(pattern: str) -> list[str]:
    """List form of :func:`_iter_classes` (kept for direct tests)."""
    return list(_iter_classes(pattern))


def _iter_groups(pattern: str) -> Iterator[str]:
    """Lazily yield group and look-around mutations (#14 + #15).

    #14 look-around flip: ``(?=)`` <-> ``(?!)`` and ``(?<=)`` <-> ``(?<!)``.
    #15 group->non-capturing: a plain capturing ``(`` becomes ``(?:``. Both are
    class-aware (a ``(`` inside ``[...]`` is a literal) and escape-aware (``\\(``
    is a literal paren). A non-capturing ``(?:`` and named/other ``(?...)`` groups
    are left alone by #15.
    """
    spans = _class_spans(pattern)
    i, n = 0, len(pattern)
    while i < n:
        if pattern[i] == "\\":
            i += 2
            continue
        if pattern[i] == "(" and not _in_class(i, spans):
            if pattern[i : i + 3] == "(?=":
                yield f"{pattern[:i]}(?!{pattern[i + 3 :]}"
            elif pattern[i : i + 3] == "(?!":
                yield f"{pattern[:i]}(?={pattern[i + 3 :]}"
            elif pattern[i : i + 4] == "(?<=":
                yield f"{pattern[:i]}(?<!{pattern[i + 4 :]}"
            elif pattern[i : i + 4] == "(?<!":
                yield f"{pattern[:i]}(?<={pattern[i + 4 :]}"
            elif i + 1 < n and pattern[i + 1] != "?":
                # plain capturing group -> non-capturing
                yield f"{pattern[: i + 1]}?:{pattern[i + 1 :]}"
        i += 1


def _mutate_groups(pattern: str) -> list[str]:
    """List form of :func:`_iter_groups` (kept for direct tests)."""
    return list(_iter_groups(pattern))


#: Escaped single-letter anchors (``\A \Z \b \B``). A frozenset, so a missing
#: next char (trailing backslash) is correctly NOT an anchor — the old
#: ``nxt in "AZbB"`` mis-fired because ``"" in "AZbB"`` is True (empty string is
#: a substring of every string).
_ESCAPED_ANCHORS: frozenset[str] = frozenset("AZbB")

#: Top-level anchors written as bare metacharacters.
_TOP_LEVEL_ANCHORS: frozenset[str] = frozenset("^$")


def _class_spans(pattern: str) -> list[tuple[int, int]]:
    """Locate every unescaped ``[...]`` character class in *pattern*.

    Returns ``(start, end)`` index pairs, where ``start`` is the index of the
    opening ``[`` and ``end`` is the index just past the closing ``]``. Handles
    escaped brackets (``\\[``, ``\\]``) and a literal ``]`` appearing as the
    first class member (``[]...]`` / ``[^]...]``). This is the structural
    foundation that keeps context-sensitive sub-mutators out of classes.
    """
    spans: list[tuple[int, int]] = []
    i, n = 0, len(pattern)
    while i < n:
        char = pattern[i]
        if char == "\\":
            i += 2
            continue
        if char == "[":
            j = i + 1
            if j < n and pattern[j] == "^":
                j += 1
            if j < n and pattern[j] == "]":
                # a ] right after [ or [^ is a literal member, not the end
                j += 1
            while j < n and pattern[j] != "]":
                j += 2 if pattern[j] == "\\" else 1
            end = min(j + 1, n)
            spans.append((i, end))
            i = end
            continue
        i += 1
    return spans


def _in_class(index: int, spans: list[tuple[int, int]]) -> bool:
    """``True`` if *index* falls within one of the *spans* (a ``[...]`` class)."""
    return any(start <= index < end for start, end in spans)


def _iter_anchors(pattern: str) -> Iterator[str]:
    """Lazily yield anchor removals (#1): ``^``, ``$``, ``\\A``, ``\\Z``, ``\\b``, ``\\B``.

    Uses the class-span tokenizer so a ``^`` inside ``[^...]`` (a class negation)
    and a ``\\b`` inside ``[\\b]`` (a backspace literal) are never mistaken for
    anchors. Each removal is a local string edit, leaving the rest byte-exact. A
    trailing backslash has no next char and is left alone.
    """
    spans = _class_spans(pattern)
    i, n = 0, len(pattern)
    while i < n:
        char = pattern[i]
        if char == "\\":
            if i + 1 < n and pattern[i + 1] in _ESCAPED_ANCHORS and not _in_class(i, spans):
                yield pattern[:i] + pattern[i + 2 :]
            i += 2
            continue
        if char in _TOP_LEVEL_ANCHORS and not _in_class(i, spans):
            yield pattern[:i] + pattern[i + 1 :]
        i += 1


def _mutate_anchors(pattern: str) -> list[str]:
    """List form of :func:`_iter_anchors` (kept for direct tests)."""
    return list(_iter_anchors(pattern))


def _is_valid_regex(pattern: str) -> bool:
    """Check if a pattern compiles without ambiguous-regex warnings.

    Python emits ``FutureWarning`` for constructs such as possible nested
    character sets.  Treating those as generated candidates would make the
    mutation suite noisy today and potentially change its meaning under a
    future regex parser.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            # ``re.compile`` is globally cached. If another caller compiled
            # this pattern while ignoring FutureWarning, a later validation
            # would otherwise become order-dependent and accept an ambiguous
            # candidate without re-parsing it. The exact supported runtime is
            # CPython 3.14.7; its uncached compiler is the deterministic seam.
            re._compiler.compile(pattern)  # type: ignore[attr-defined]
    except (
        re.error,
        OverflowError,
        FutureWarning,
    ):
        # Repetition counts >= 2**32-1 (e.g. ``a{4294967295}`` produced by the
        # {n+1} mutation) raise OverflowError instead of re.error
        # (issue #78 / A1-RX-001).
        return False
    return True
