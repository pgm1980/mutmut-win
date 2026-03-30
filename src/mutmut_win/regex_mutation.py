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
#: Matches quantifiers: +, *, ?, {n}, {n,}, {n,m}
_QUANTIFIER_RE = re.compile(
    r"""
    (?<!\\)        # not preceded by a backslash (avoid matching \+ etc.)
    (
        [+*?]      # simple quantifiers
      | \{\d+\}    # {n}
      | \{\d+,\d*\}  # {n,m} or {n,}
    )
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

    # Validate all mutations and filter invalid ones.
    valid: list[str] = []
    for m in mutations:
        if m == pattern:
            continue  # skip no-ops
        if _is_valid_regex(m):
            valid.append(m)
        if len(valid) >= MAX_MUTATIONS_PER_PATTERN:
            break

    return valid


def _mutate_quantifiers(pattern: str) -> list[str]:
    """Mutate quantifiers in the pattern.

    - ``+`` → removed (require exactly the preceding element)
    - ``*`` → ``+`` (require at least one)
    - ``?`` → removed (require exactly one)
    - ``{n}`` → ``{n-1}`` and ``{n+1}``
    - ``{n,m}`` → ``{n+1,m}`` and ``{n,m-1}``
    """
    results: list[str] = []

    for match in _QUANTIFIER_RE.finditer(pattern):
        q = match.group(0)
        start, end = match.start(), match.end()

        replacements: list[str] = []
        if q == "+":
            replacements.append("")  # remove +
        elif q == "*":
            replacements.append("+")  # * → +
        elif q == "?":
            replacements.append("")  # remove ?
        elif q.startswith("{") and q.endswith("}"):
            inner = q[1:-1]
            if "," in inner:
                parts = inner.split(",")
                lo = int(parts[0])
                hi_str = parts[1]
                if hi_str:
                    hi = int(hi_str)
                    if lo + 1 <= hi:
                        replacements.append(f"{{{lo + 1},{hi}}}")
                    if hi - 1 >= lo:
                        replacements.append(f"{{{lo},{hi - 1}}}")
                else:
                    # {n,} → {n+1,}
                    replacements.append(f"{{{lo + 1},}}")
            else:
                n = int(inner)
                if n > 1:
                    replacements.append(f"{{{n - 1}}}")
                replacements.append(f"{{{n + 1}}}")

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


def _mutate_anchors(pattern: str) -> list[str]:
    """Remove anchors ``^`` and ``$``.

    Only removes ``^`` at the start and ``$`` at the end to avoid
    false positives from ``^`` inside character classes like ``[^a-z]``.
    """
    results: list[str] = []

    if pattern.startswith("^"):
        results.append(pattern[1:])

    if pattern.endswith("$") and not pattern.endswith("\\$"):
        results.append(pattern[:-1])

    return results


def _is_valid_regex(pattern: str) -> bool:
    """Check if a pattern compiles as a valid regex."""
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True
