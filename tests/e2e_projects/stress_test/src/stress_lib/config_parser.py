"""Configuration parsing and manipulation.

Designed to trigger mutations on: dict literal mutations (dict(key=value)),
augmented assignments, nested key access, and default-value expressions.
"""

from __future__ import annotations

import copy


# Sentinel for missing values
_MISSING = object()

DEFAULT_CONFIG: dict[str, object] = dict(
    debug=False,
    max_retries=3,
    timeout=30,
    log_level="INFO",
    max_connections=10,
    retry_delay=1.0,
    enable_cache=True,
    cache_ttl=300,
)


def parse_config(raw: dict[str, object]) -> dict[str, object]:
    """Parse a raw config dict, filling in defaults for missing keys."""
    result: dict[str, object] = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in raw.items():
        result[key] = value
    return result


def merge_configs(*configs: dict[str, object]) -> dict[str, object]:
    """Merge multiple config dicts. Later configs take precedence."""
    merged: dict[str, object] = {}
    for cfg in configs:
        for key, value in cfg.items():
            merged[key] = value
    return merged


def get_nested(data: dict[str, object], *keys: str, default: object = None) -> object:
    """Get a value from a nested dict using a sequence of keys."""
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, _MISSING)  # type: ignore[attr-defined]
        if current is _MISSING:
            return default
    return current


def set_nested(data: dict[str, object], value: object, *keys: str) -> None:
    """Set a value in a nested dict, creating intermediate dicts as needed."""
    if not keys:
        return
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]  # type: ignore[assignment]
    current[keys[-1]] = value


def flatten_config(
    data: dict[str, object], prefix: str = "", separator: str = "."
) -> dict[str, object]:
    """Flatten a nested config dict into a flat dict with compound keys."""
    result: dict[str, object] = {}
    for key, value in data.items():
        full_key = f"{prefix}{separator}{key}" if prefix else key
        if isinstance(value, dict):
            nested = flatten_config(value, full_key, separator)
            result.update(nested)
        else:
            result[full_key] = value
    return result


def unflatten_config(
    data: dict[str, object], separator: str = "."
) -> dict[str, object]:
    """Expand a flat config dict back into nested form."""
    result: dict[str, object] = {}
    for compound_key, value in data.items():
        parts = compound_key.split(separator)
        set_nested(result, value, *parts)
    return result


def validate_config(config: dict[str, object], schema: dict[str, type]) -> list[str]:
    """Validate config against a schema dict (key -> expected type).

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []
    for key, expected_type in schema.items():
        if key not in config:
            errors.append(f"Missing required key: {key!r}")
            continue
        value = config[key]
        if not isinstance(value, expected_type):
            errors.append(
                f"Key {key!r}: expected {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
    return errors


def count_keys(data: dict[str, object]) -> int:
    """Count total keys in a nested dict recursively."""
    total = 0
    for value in data.values():
        total += 1
        if isinstance(value, dict):
            total += count_keys(value)
    return total


def config_diff(
    base: dict[str, object], updated: dict[str, object]
) -> dict[str, tuple[object, object]]:
    """Return keys where values differ: {key: (old, new)}."""
    diff: dict[str, tuple[object, object]] = {}
    all_keys = set(base.keys()) | set(updated.keys())
    for key in all_keys:
        old = base.get(key, _MISSING)
        new = updated.get(key, _MISSING)
        if old != new:
            diff[key] = (old, new)
    return diff


def apply_overrides(
    config: dict[str, object], overrides: dict[str, object]
) -> dict[str, object]:
    """Return a new config with overrides applied (deep copy)."""
    result = copy.deepcopy(config)
    for key, value in overrides.items():
        result[key] = value
    return result
