"""Validation utilities.

Designed to trigger boolean-logic mutations (and/or/not), comparison
mutations, return-value mutations (True/False), and deepcopy mutations.
"""

from __future__ import annotations

import copy
import re


def is_positive(value: int | float) -> bool:
    """Return True if value > 0."""
    return value > 0


def is_non_negative(value: int | float) -> bool:
    """Return True if value >= 0."""
    return value >= 0


def is_in_range(value: int | float, low: int | float, high: int | float) -> bool:
    """Return True if low <= value <= high."""
    return low <= value <= high


def is_between_exclusive(value: float, low: float, high: float) -> bool:
    """Return True if low < value < high."""
    return low < value < high


def validate_email(email: str) -> bool:
    """Return True if email matches a basic email pattern."""
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_password(password: str) -> bool:
    """Return True if password meets complexity requirements.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*)
    """
    if len(password) < 8:
        return False
    if not any(ch.isupper() for ch in password):
        return False
    if not any(ch.islower() for ch in password):
        return False
    if not any(ch.isdigit() for ch in password):
        return False
    if not any(ch in "!@#$%^&*" for ch in password):
        return False
    return True


def all_truthy(values: list[object]) -> bool:
    """Return True only if every value in the list is truthy."""
    for v in values:
        if not v:
            return False
    return True


def any_falsy(values: list[object]) -> bool:
    """Return True if at least one value in the list is falsy."""
    for v in values:
        if not v:
            return True
    return False


def coerce_bool(value: object) -> bool:
    """Coerce common string representations to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        if value.lower() in ("true", "yes", "1", "on"):
            return True
        if value.lower() in ("false", "no", "0", "off"):
            return False
        raise ValueError(f"Cannot coerce {value!r} to bool")
    raise TypeError(f"Unsupported type: {type(value)}")


def validate_range(
    value: float,
    min_val: float | None = None,
    max_val: float | None = None,
    inclusive: bool = True,
) -> bool:
    """Return True if value is within optional [min_val, max_val] bounds."""
    if min_val is not None:
        if inclusive and value < min_val:
            return False
        if not inclusive and value <= min_val:
            return False
    if max_val is not None:
        if inclusive and value > max_val:
            return False
        if not inclusive and value >= max_val:
            return False
    return True


def is_subset(small: list[object], large: list[object]) -> bool:
    """Return True if every element of small is contained in large."""
    for item in small:
        if item not in large:
            return False
    return True


def has_duplicates(items: list[object]) -> bool:
    """Return True if the list contains any duplicate values."""
    seen: set[object] = set()
    for item in items:
        if item in seen:
            return True
        seen.add(item)
    return False


def deep_copy_if_mutable(obj: list[object] | dict[str, object]) -> list[object] | dict[str, object]:
    """Return a deep copy of obj."""
    return copy.deepcopy(obj)


def validate_username(username: str) -> bool:
    """Return True if username is 3-20 alphanumeric characters (or underscores)."""
    if len(username) < 3:
        return False
    if len(username) > 20:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_]+$", username))


def validate_port(port: int) -> bool:
    """Return True if port is a valid TCP/UDP port number (1-65535)."""
    return 1 <= port <= 65535


def none_of(values: list[object]) -> bool:
    """Return True if all values are falsy."""
    return not any(bool(v) for v in values)


def exactly_one(values: list[object]) -> bool:
    """Return True if exactly one value is truthy."""
    count = 0
    for v in values:
        if v:
            count += 1
        if count > 1:
            return False
    return count == 1
