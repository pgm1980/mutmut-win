"""Unit tests for mutmut_win.trampoline."""

import unicodedata

import pytest

from mutmut_win.trampoline import (
    CLASS_NAME_SEPARATOR,
    create_trampoline_lookup,
    mangle_function_name,
    trampoline_impl,
)

_SEP = CLASS_NAME_SEPARATOR
#: U+FF2B FULLWIDTH LATIN CAPITAL LETTER K - NFKC-normalizes to "K".
_FULLWIDTH_K = "\uff2b"
#: U+FF23 FULLWIDTH LATIN CAPITAL LETTER C - NFKC-normalizes to "C".
_FULLWIDTH_C = "\uff23"
#: U+212A KELVIN SIGN - NFKC-normalizes to "K".
_KELVIN_K = "\u212a"

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

    def test_nfkc_variant_top_level_name_hex_encodes_the_raw_identifier(self) -> None:
        # CPython's tokenizer binds the NFKC form of every identifier, so the
        # legacy private name for U+FF2B would compile to the same binding as
        # a genuine "K" definition (M-041).  The RAW spelling is encoded -
        # normalizing before encoding would re-create the collision.
        result = mangle_function_name(name=_FULLWIDTH_K, class_name=None)
        assert result == f"xq_{_FULLWIDTH_K.encode('utf-8').hex()}"

    def test_nfkc_normal_identifiers_keep_the_legacy_encoding_byte_for_byte(self) -> None:
        assert mangle_function_name(name="f", class_name="C") == f"x{_SEP}C{_SEP}f"
        # Precomposed U+00E4 is already NFKC-normal and therefore stays legacy.
        assert mangle_function_name(name="\u00e4", class_name=None) == "x_\u00e4"

    def test_non_nfkc_class_name_hex_encodes_class_and_function_component(self) -> None:
        result = mangle_function_name(name="m", class_name=_FULLWIDTH_C)
        assert result == f"xq{_SEP}{_FULLWIDTH_C.encode('utf-8').hex()}{_SEP}{b'm'.hex()}"

    def test_non_nfkc_function_name_in_nfkc_normal_class_hex_encodes_both(self) -> None:
        result = mangle_function_name(name=_FULLWIDTH_K, class_name="C", definition_ordinal=2)
        assert result == (f"xq{_SEP}{b'C'.hex()}{_SEP}{_FULLWIDTH_K.encode('utf-8').hex()}{_SEP}2")

    def test_nfkc_equivalent_raw_names_map_to_nfkc_distinct_private_names(self) -> None:
        mangled = [
            mangle_function_name(name=variant, class_name=None)
            for variant in ("K", _FULLWIDTH_K, _KELVIN_K)
        ]
        assert len(mangled) == len(set(mangled)) == 3
        assert len({unicodedata.normalize("NFKC", value) for value in mangled}) == 3
        # Every private name is NFKC-stable in itself: the compiled module
        # cannot re-collapse two distinct generated identifiers.
        for value in mangled:
            assert unicodedata.normalize("NFKC", value) == value

    def test_fullwidth_underscore_connector_is_hex_encoded(self) -> None:
        # U+FF3F FULLWIDTH LOW LINE is a valid identifier CONTINUATION
        # character but NFKC-normalizes to "_", so the legacy private name
        # would collide with the plain-underscore spelling.
        name = "a\uff3fb"
        assert unicodedata.normalize("NFKC", name) != name
        encoded = name.encode("utf-8").hex()
        assert mangle_function_name(name=name, class_name=None) == f"xq_{encoded}"


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
# Issue #107: the recording moved to the hit_recording kernel module —
# patches target THAT module now (record_trampoline_hit resolves its
# module-local _get_max_stack_depth, not the __main__ BWC re-export).


class TestRecordTrampolineHit:
    def test_records_hit_when_unlimited(self) -> None:
        """F4: with max_stack_depth=-1, every hit is recorded."""
        from unittest.mock import patch

        from mutmut_win import hit_recording
        from mutmut_win._state import _reset_globals, _stats

        # Issue #110 / QX-017: the depth cache lives in _state and resets
        # with the rest — no manual cache poking anymore.
        _reset_globals()
        with patch("mutmut_win.hit_recording._get_max_stack_depth", return_value=-1):
            hit_recording.record_trampoline_hit("x_my_func")
        assert "x_my_func" in _stats
        _stats.clear()

    def test_does_not_record_when_depth_limit_reached(self) -> None:
        """F4: when max_stack_depth is 0 (already exhausted), hit is discarded."""
        from unittest.mock import patch

        from mutmut_win import hit_recording
        from mutmut_win._state import _stats

        _stats.clear()
        # max_depth=1 but no pytest/unittest frame in stack → depth exhausted → discard
        with patch("mutmut_win.hit_recording._get_max_stack_depth", return_value=1):
            hit_recording.record_trampoline_hit("x_should_be_discarded")
        # The name should NOT be in _stats because no pytest frame was found within 1 frame
        assert "x_should_be_discarded" not in _stats
        _stats.clear()

    def test_records_hit_when_depth_negative_one(self) -> None:
        """F4: -1 means unlimited — name is always added."""
        from unittest.mock import patch

        from mutmut_win import hit_recording
        from mutmut_win._state import _stats

        _stats.clear()
        with patch("mutmut_win.hit_recording._get_max_stack_depth", return_value=-1):
            hit_recording.record_trampoline_hit("x_unlimited_hit")
        assert "x_unlimited_hit" in _stats
        _stats.clear()

    def test_get_max_stack_depth_caches_value(self) -> None:
        """F4: _get_max_stack_depth() caches the config value after first call.

        Instrumentation-proof (Sprint-34 dogfooding find): the config object
        is built BEFORE the patch context and the cache reset happens with
        the mock fully armed. Under ``MUTANT_UNDER_TEST=stats`` in a staging
        that trampolines config.py, the model construction itself records
        trampoline hits — those consult ``_get_max_stack_depth`` and would
        otherwise populate the cache through a half-configured mock.
        """
        from unittest.mock import patch

        from mutmut_win import hit_recording
        from mutmut_win._state import _reset_globals
        from mutmut_win.config import MutmutConfig

        cfg = MutmutConfig(max_stack_depth=5)
        with patch("mutmut_win.config.load_config", return_value=cfg) as mock_load:
            _reset_globals()
            # First call loads config.
            depth1 = hit_recording._get_max_stack_depth()
            calls_after_first = mock_load.call_count
            # Second call must use the cache (no additional load).
            depth2 = hit_recording._get_max_stack_depth()
        assert depth1 == 5
        assert depth2 == 5
        assert calls_after_first == 1
        assert mock_load.call_count == calls_after_first
        _reset_globals()
