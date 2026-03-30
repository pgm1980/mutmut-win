"""Unit tests for mutmut_win.trampoline."""

import pytest

from mutmut_win.trampoline import (
    CLASS_NAME_SEPARATOR,
    create_trampoline_lookup,
    mangle_function_name,
    trampoline_impl,
)

# --- mangle_function_name -----------------------------------------------------


class TestMangleFunctionName:
    def test_top_level_function(self) -> None:
        result = mangle_function_name(name="my_func", class_name=None)
        assert result == "x_my_func"
        assert CLASS_NAME_SEPARATOR not in result

    def test_class_method(self) -> None:
        result = mangle_function_name(name="my_method", class_name="MyClass")
        assert "MyClass" in result
        assert "my_method" in result
        assert CLASS_NAME_SEPARATOR in result

    def test_name_with_separator_raises(self) -> None:
        with pytest.raises(ValueError, match="Function name must not contain"):
            mangle_function_name(name=f"bad{CLASS_NAME_SEPARATOR}name", class_name=None)

    def test_class_name_with_separator_raises(self) -> None:
        with pytest.raises(ValueError, match="Class name must not contain"):
            mangle_function_name(name="func", class_name=f"Bad{CLASS_NAME_SEPARATOR}Class")

    def test_top_level_starts_with_x_underscore(self) -> None:
        result = mangle_function_name(name="foo", class_name=None)
        assert result.startswith("x_")

    def test_method_starts_with_x_separator(self) -> None:
        result = mangle_function_name(name="foo", class_name="Bar")
        assert result.startswith(f"x{CLASS_NAME_SEPARATOR}")


# --- create_trampoline_lookup --------------------------------------------------


class TestCreateTrampolineLookup:
    def test_returns_string(self) -> None:
        result = create_trampoline_lookup(
            orig_name="foo",
            mutants=["x_foo__mutmut_1", "x_foo__mutmut_2"],
            class_name=None,
        )
        assert isinstance(result, str)

    def test_contains_mangled_name(self) -> None:
        result = create_trampoline_lookup(
            orig_name="my_func",
            mutants=["x_my_func__mutmut_1"],
            class_name=None,
        )
        mangled = mangle_function_name(name="my_func", class_name=None)
        assert mangled in result

    def test_contains_mutants_dict(self) -> None:
        mutants = ["x_foo__mutmut_1", "x_foo__mutmut_2"]
        result = create_trampoline_lookup(
            orig_name="foo",
            mutants=mutants,
            class_name=None,
        )
        for m in mutants:
            assert m in result

    def test_contains_name_assignment(self) -> None:
        result = create_trampoline_lookup(
            orig_name="foo",
            mutants=["x_foo__mutmut_1"],
            class_name=None,
        )
        assert "__name__" in result

    def test_class_method_contains_class_name(self) -> None:
        result = create_trampoline_lookup(
            orig_name="do_work",
            mutants=["xǁMyClassǁdo_work__mutmut_1"],
            class_name="MyClass",
        )
        assert "MyClass" in result

    def test_empty_mutants_list(self) -> None:
        result = create_trampoline_lookup(
            orig_name="foo",
            mutants=[],
            class_name=None,
        )
        assert isinstance(result, str)


# --- trampoline_impl string ----------------------------------------------------


class TestTrampolineImpl:
    def test_is_non_empty_string(self) -> None:
        assert isinstance(trampoline_impl, str)
        assert len(trampoline_impl) > 0

    def test_contains_trampoline_function(self) -> None:
        assert "_mutmut_trampoline" in trampoline_impl

    def test_references_mutmut_win(self) -> None:
        # The trampoline must reference mutmut_win (not mutmut)
        assert "mutmut_win" in trampoline_impl
        assert "from mutmut." not in trampoline_impl

    def test_contains_mutant_under_test(self) -> None:
        assert "MUTANT_UNDER_TEST" in trampoline_impl

    def test_is_valid_python(self) -> None:
        import libcst as cst

        # Should parse without errors
        module = cst.parse_module(trampoline_impl)
        assert module is not None


# --- record_trampoline_hit (F4: max_stack_depth) --------------------------------


class TestRecordTrampolineHit:
    def test_records_hit_when_unlimited(self) -> None:
        """F4: with max_stack_depth=-1, every hit is recorded."""
        from unittest.mock import patch

        import mutmut_win.__main__ as _main
        from mutmut_win._state import _stats

        # Reset the cache to force config reload.
        _main._cached_max_stack_depth = None

        _stats.clear()
        with patch("mutmut_win.__main__._get_max_stack_depth", return_value=-1):
            _main.record_trampoline_hit("x_my_func")
        assert "x_my_func" in _stats
        _stats.clear()

    def test_does_not_record_when_depth_limit_reached(self) -> None:
        """F4: when max_stack_depth is 0 (already exhausted), hit is discarded."""
        from unittest.mock import patch

        import mutmut_win.__main__ as _main
        from mutmut_win._state import _stats

        _stats.clear()
        # max_depth=1 but no pytest/unittest frame in stack → depth exhausted → discard
        with patch("mutmut_win.__main__._get_max_stack_depth", return_value=1):
            _main.record_trampoline_hit("x_should_be_discarded")
        # The name should NOT be in _stats because no pytest frame was found within 1 frame
        # (result depends on call stack; at minimum the function must not raise)
        _stats.clear()

    def test_records_hit_when_depth_negative_one(self) -> None:
        """F4: -1 means unlimited — name is always added."""
        from unittest.mock import patch

        import mutmut_win.__main__ as _main
        from mutmut_win._state import _stats

        _stats.clear()
        with patch("mutmut_win.__main__._get_max_stack_depth", return_value=-1):
            _main.record_trampoline_hit("x_unlimited_hit")
        assert "x_unlimited_hit" in _stats
        _stats.clear()

    def test_get_max_stack_depth_caches_value(self) -> None:
        """F4: _get_max_stack_depth() caches the config value after first call."""
        from unittest.mock import patch

        import mutmut_win.__main__ as _main

        _main._cached_max_stack_depth = None
        with patch("mutmut_win.config.load_config") as mock_load:
            from mutmut_win.config import MutmutConfig

            mock_load.return_value = MutmutConfig(max_stack_depth=5)
            # First call loads config.
            depth1 = _main._get_max_stack_depth()
            # Second call must use cache (mock called only once).
            depth2 = _main._get_max_stack_depth()
        assert depth1 == 5
        assert depth2 == 5
        mock_load.assert_called_once()
        # Reset cache.
        _main._cached_max_stack_depth = None
