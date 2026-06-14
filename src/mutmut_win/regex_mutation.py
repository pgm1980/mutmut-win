"""Regex mutation engine for mutmut-win.

Mutates regex patterns found in ``re.*()`` calls. This is a unique feature
— no other Python mutation testing tool supports regex mutations.

Supports three categories of mutations:
1. **Quantifier mutations:** ``+`` → remove, ``*`` → ``+``, ``?`` → remove, ``{n}`` → ``{n±1}``
2. **Character-class mutations:** ``\\d`` ↔ ``\\D``, ``\\w`` ↔ ``\\W``, ``\\s`` ↔ ``\\S``
3. **Anchor mutations:** ``^`` → remove, ``$`` → remove

All generated mutations are validated via ``re.compile()`` — invalid regex
patterns are silently filtered out.
"""

from __future__ import annotations

import re

#: Maximum mutations per single regex pattern (prevents explosion).
MAX_MUTATIONS_PER_PATTERN: int = 5

# ---------------------------------------------------------------------------
# Character-class swap pairs
# ---------------------------------------------------------------------------
_CHAR_CLASS_SWAPS: dict[str, str] = {
    r"\d": r"\D",
    r"\D": r"\d",
    r"\w": r"\W",
    r"\W": r"\w",
    r"\s": r"\S",
    r"\S": r"\s",
}

# ---------------------------------------------------------------------------
# Quantifier patterns (applied to the raw regex string)
# ---------------------------------------------------------------------------
#: Matches a quantifier and its optional lazy marker. Group 1 is the base
#: quantifier (+, *, ?, {n}, {n,}, {n,m}); group 2 is "" (greedy) or "?" (lazy),
#: so ``a+?`` is captured as one unit instead of ``+`` and ``?`` separately.
_QUANTIFIER_RE = re.compile(
    r"""
    (?<!\\)            # not preceded by a backslash (avoid matching \+ etc.)
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
    mutations: list[str] = []

    mutations.extend(_mutate_quantifiers(pattern))
    mutations.extend(_mutate_char_classes(pattern))
    mutations.extend(_mutate_anchors(pattern))

    # Validate, dedupe (issue #132 / 360°-C5: two generators can emit the
    # same candidate — duplicates would create same-named mutants) and
    # filter invalid ones.
    valid: list[str] = []
    seen: set[str] = set()
    for m in mutations:
        if m == pattern or m in seen:
            continue  # skip no-ops and duplicates
        seen.add(m)
        if _is_valid_regex(m):
            valid.append(m)
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


def _mutate_quantifiers(pattern: str) -> list[str]:
    """Mutate quantifiers (sub-mutators #2-#6).

    Per quantifier: removal (#2); reluctant greedy->lazy (#6, skipping the exact
    ``{n}`` and an already-lazy quantifier); the require-count swaps (``+``<->``*``)
    and short->range tightenings (#5: ``?``->``{1}``, ``+``->``{2,}``); and brace
    ``{...}`` quantity ±1 (#3/#4). Invalid or duplicate candidates are dropped
    downstream by ``re.compile`` and the ``seen`` set in
    :func:`mutate_regex_pattern`.
    """
    results: list[str] = []

    for match in _QUANTIFIER_RE.finditer(pattern):
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
            mutated = pattern[:start] + repl + pattern[end:]
            results.append(mutated)

    return results


def _mutate_char_classes(pattern: str) -> list[str]:
    """Swap shorthand character classes: ``\\d`` ↔ ``\\D``, etc."""
    results: list[str] = []

    for original, swapped in _CHAR_CLASS_SWAPS.items():
        # Only swap if the original actually appears in the pattern.
        idx = pattern.find(original)
        if idx != -1:
            mutated = pattern[:idx] + swapped + pattern[idx + len(original) :]
            results.append(mutated)

    return results


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


def _mutate_anchors(pattern: str) -> list[str]:
    """Remove anchors (#1): ``^``, ``$``, ``\\A``, ``\\Z``, ``\\b``, ``\\B``.

    Uses the class-span tokenizer so a ``^`` inside ``[^...]`` (a class negation)
    and a ``\\b`` inside ``[\\b]`` (a backspace literal) are never mistaken for
    anchors. Each removal is a local string edit, leaving the rest byte-exact. A
    trailing backslash has no next char and is left alone.
    """
    results: list[str] = []
    spans = _class_spans(pattern)
    i, n = 0, len(pattern)
    while i < n:
        char = pattern[i]
        if char == "\\":
            if i + 1 < n and pattern[i + 1] in _ESCAPED_ANCHORS and not _in_class(i, spans):
                results.append(pattern[:i] + pattern[i + 2 :])
            i += 2
            continue
        if char in _TOP_LEVEL_ANCHORS and not _in_class(i, spans):
            results.append(pattern[:i] + pattern[i + 1 :])
        i += 1
    return results


def _is_valid_regex(pattern: str) -> bool:
    """Check if a pattern compiles as a valid regex."""
    try:
        re.compile(pattern)
    except (re.error, OverflowError):
        # Repetition counts >= 2**32-1 (e.g. ``a{4294967295}`` produced by the
        # {n+1} mutation) raise OverflowError instead of re.error
        # (issue #78 / A1-RX-001).
        return False
    return True
