"""Tests for config_parser — ~65% well covered."""

from __future__ import annotations

import pytest

from stress_lib.config_parser import (
    parse_config,
    merge_configs,
    get_nested,
    set_nested,
    flatten_config,
    unflatten_config,
    validate_config,
    count_keys,
    config_diff,
    apply_overrides,
    DEFAULT_CONFIG,
)


class TestParseConfig:
    def test_empty_uses_defaults(self) -> None:
        config = parse_config({})
        assert config["max_retries"] == 3
        assert config["timeout"] == 30
        assert config["log_level"] == "INFO"

    def test_override_defaults(self) -> None:
        config = parse_config({"timeout": 60})
        assert config["timeout"] == 60
        assert config["max_retries"] == 3  # default unchanged

    def test_extra_keys(self) -> None:
        config = parse_config({"custom_key": "custom_value"})
        assert config["custom_key"] == "custom_value"

    def test_does_not_modify_original(self) -> None:
        raw = {"timeout": 60}
        parse_config(raw)
        assert raw == {"timeout": 60}

    def test_debug_default_is_false(self) -> None:
        config = parse_config({})
        assert config["debug"] is False


class TestMergeConfigs:
    def test_two_dicts(self) -> None:
        result = merge_configs({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_later_wins(self) -> None:
        result = merge_configs({"a": 1}, {"a": 99})
        assert result["a"] == 99

    def test_three_dicts(self) -> None:
        result = merge_configs({"a": 1}, {"b": 2}, {"c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_empty(self) -> None:
        result = merge_configs({})
        assert result == {}


class TestGetNested:
    def test_single_level(self) -> None:
        data = {"key": "value"}
        assert get_nested(data, "key") == "value"

    def test_two_levels(self) -> None:
        data = {"outer": {"inner": 42}}
        assert get_nested(data, "outer", "inner") == 42

    def test_missing_key_returns_default(self) -> None:
        data = {"a": 1}
        assert get_nested(data, "missing") is None

    def test_custom_default(self) -> None:
        data = {"a": 1}
        assert get_nested(data, "missing", default="fallback") == "fallback"

    def test_intermediate_not_dict(self) -> None:
        data = {"a": "string"}
        assert get_nested(data, "a", "b") is None


class TestSetNested:
    def test_single_level(self) -> None:
        data: dict[str, object] = {}
        set_nested(data, "hello", "key")
        assert data["key"] == "hello"

    def test_two_levels(self) -> None:
        data: dict[str, object] = {}
        set_nested(data, 42, "outer", "inner")
        assert data["outer"] == {"inner": 42}  # type: ignore[comparison-overlap]

    def test_overwrite(self) -> None:
        data: dict[str, object] = {"x": {"y": 1}}
        set_nested(data, 99, "x", "y")
        assert data["x"] == {"y": 99}  # type: ignore[comparison-overlap]

    def test_no_keys(self) -> None:
        data: dict[str, object] = {}
        set_nested(data, "value")
        assert data == {}


class TestFlattenConfig:
    def test_flat_already(self) -> None:
        data = {"a": 1, "b": 2}
        result = flatten_config(data)
        assert result == {"a": 1, "b": 2}

    def test_nested(self) -> None:
        data = {"a": {"b": {"c": 1}}}
        result = flatten_config(data)
        assert result == {"a.b.c": 1}

    def test_custom_separator(self) -> None:
        data = {"a": {"b": 1}}
        result = flatten_config(data, separator="/")
        assert result == {"a/b": 1}


class TestUnflattenConfig:
    def test_basic(self) -> None:
        data = {"a.b.c": 1}
        result = unflatten_config(data)
        assert result == {"a": {"b": {"c": 1}}}

    def test_flat(self) -> None:
        data = {"a": 1, "b": 2}
        result = unflatten_config(data)
        assert result == {"a": 1, "b": 2}


class TestValidateConfig:
    def test_valid(self) -> None:
        config: dict[str, object] = {"host": "localhost", "port": 8080}
        schema = {"host": str, "port": int}
        errors = validate_config(config, schema)
        assert errors == []

    def test_missing_key(self) -> None:
        config: dict[str, object] = {"host": "localhost"}
        schema = {"host": str, "port": int}
        errors = validate_config(config, schema)
        assert len(errors) == 1
        assert "port" in errors[0]

    def test_wrong_type(self) -> None:
        config: dict[str, object] = {"port": "not_an_int"}
        schema = {"port": int}
        errors = validate_config(config, schema)
        assert len(errors) == 1
        assert "port" in errors[0]


class TestCountKeys:
    def test_flat(self) -> None:
        assert count_keys({"a": 1, "b": 2}) == 2

    def test_nested(self) -> None:
        assert count_keys({"a": {"b": 1, "c": 2}}) == 3  # a + b + c

    def test_empty(self) -> None:
        assert count_keys({}) == 0


class TestConfigDiff:
    def test_no_diff(self) -> None:
        cfg = {"a": 1, "b": 2}
        assert config_diff(cfg, cfg) == {}

    def test_changed_value(self) -> None:
        base = {"a": 1}
        updated = {"a": 2}
        diff = config_diff(base, updated)
        assert "a" in diff
        assert diff["a"][0] == 1
        assert diff["a"][1] == 2

    def test_added_key(self) -> None:
        diff = config_diff({}, {"new": "val"})
        assert "new" in diff

    def test_removed_key(self) -> None:
        diff = config_diff({"old": 1}, {})
        assert "old" in diff


class TestApplyOverrides:
    def test_basic(self) -> None:
        config = {"a": 1, "b": 2}
        result = apply_overrides(config, {"b": 99})
        assert result["b"] == 99
        assert result["a"] == 1

    def test_does_not_modify_original(self) -> None:
        config = {"a": 1}
        apply_overrides(config, {"a": 99})
        assert config["a"] == 1

    def test_add_new_key(self) -> None:
        result = apply_overrides({}, {"new": "val"})
        assert result["new"] == "val"


class TestDefaultConfig:
    def test_has_expected_keys(self) -> None:
        assert "debug" in DEFAULT_CONFIG
        assert "max_retries" in DEFAULT_CONFIG
        assert "timeout" in DEFAULT_CONFIG

    def test_max_retries_is_positive(self) -> None:
        assert isinstance(DEFAULT_CONFIG["max_retries"], int)
        assert DEFAULT_CONFIG["max_retries"] > 0  # type: ignore[operator]
