"""String manipulation utilities.

Designed to trigger string-method mutations (.lower/.upper, .strip/.lstrip/.rstrip,
.find/.rfind, .split/.rsplit, .removeprefix/.removesuffix, .ljust/.rjust),
string-literal mutations, and lambda-function mutations.
"""

from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    """Replace consecutive whitespace with a single space and strip ends."""
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length characters, appending suffix if truncated."""
    if max_length < 0:
        raise ValueError("max_length must be >= 0")
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]
    return text[: max_length - len(suffix)] + suffix


def pad_center(text: str, width: int, fillchar: str = " ") -> str:
    """Center text in a field of given width using fillchar."""
    if len(fillchar) != 1:
        raise ValueError("fillchar must be exactly one character")
    return text.center(width, fillchar)


def count_vowels(text: str) -> int:
    """Return the count of vowels (a, e, i, o, u) in text (case-insensitive)."""
    count = 0
    vowels = "aeiouAEIOU"
    for ch in text:
        if ch in vowels:
            count += 1
    return count


def reverse_words(text: str) -> str:
    """Reverse the order of words in text."""
    words = text.split()
    return " ".join(reversed(words))


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def slug(text: str) -> str:
    """Convert text to a URL-safe slug (lowercase, hyphens, no special chars)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")
    return text


def remove_prefix_suffix(text: str, prefix: str, suffix: str) -> str:
    """Remove prefix and suffix from text if present."""
    result = text.removeprefix(prefix)
    result = result.removesuffix(suffix)
    return result


def wrap_text(text: str, width: int) -> list[str]:
    """Split text into lines of at most width characters, splitting on spaces."""
    if width <= 0:
        raise ValueError("width must be > 0")
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def is_palindrome(text: str) -> bool:
    """Return True if text is a palindrome (case-insensitive, ignores spaces)."""
    cleaned = text.lower().replace(" ", "")
    return cleaned == cleaned[::-1]


def count_occurrences(text: str, sub: str) -> int:
    """Count non-overlapping occurrences of sub in text."""
    if not sub:
        return 0
    count = 0
    start = 0
    while True:
        pos = text.find(sub, start)
        if pos == -1:
            break
        count += 1
        start = pos + len(sub)
    return count


def first_non_repeating(text: str) -> str | None:
    """Return the first character in text that does not repeat, or None."""
    freq: dict[str, int] = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    for ch in text:
        if freq[ch] == 1:
            return ch
    return None


def title_case(text: str) -> str:
    """Convert text to title case (first letter of each word capitalised)."""
    return " ".join(word.capitalize() for word in text.split())


def lpad(text: str, width: int, fillchar: str = "0") -> str:
    """Left-pad text to width using fillchar."""
    return text.rjust(width, fillchar)


def rpad(text: str, width: int, fillchar: str = " ") -> str:
    """Right-pad text to width using fillchar."""
    return text.ljust(width, fillchar)


def split_at(text: str, delimiter: str, max_parts: int = -1) -> list[str]:
    """Split text at delimiter, returning at most max_parts parts."""
    if max_parts < 0:
        return text.split(delimiter)
    return text.split(delimiter, max_parts)


def replace_all(text: str, replacements: dict[str, str]) -> str:
    """Apply all replacements (old -> new) in order to text."""
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def interleave(a: str, b: str) -> str:
    """Interleave characters from a and b. Remaining chars appended at end."""
    result = []
    for i in range(min(len(a), len(b))):
        result.append(a[i])
        result.append(b[i])
    if len(a) > len(b):
        result.append(a[len(b):])
    else:
        result.append(b[len(a):])
    return "".join(result)
