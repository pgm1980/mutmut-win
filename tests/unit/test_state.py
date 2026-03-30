"""Unit tests for mutmut_win._state — shared trampoline hit tracking state."""

from __future__ import annotations

import mutmut_win._state as state


class TestStateDefaults:
    def test_stats_is_a_set(self) -> None:
        assert isinstance(state._stats, set)

    def test_tests_by_mangled_is_defaultdict(self) -> None:
        from collections import defaultdict

        assert isinstance(state.tests_by_mangled_function_name, defaultdict)

    def test_duration_by_test_is_dict(self) -> None:
        assert isinstance(state.duration_by_test, dict)

    def test_stats_time_is_none_initially(self) -> None:
        # After reset it should be None
        state._reset_globals()
        assert state.stats_time is None


class TestResetGlobals:
    def test_clears_stats(self) -> None:
        state._stats.add("some_function__mutmut_1")
        state._reset_globals()
        assert state._stats == set()

    def test_clears_tests_by_mangled(self) -> None:
        state.tests_by_mangled_function_name["foo"].add("tests/test_foo.py::test_x")
        state._reset_globals()
        assert len(state.tests_by_mangled_function_name) == 0

    def test_clears_duration_by_test(self) -> None:
        state.duration_by_test["tests/test_foo.py::test_x"] = 0.5
        state._reset_globals()
        assert state.duration_by_test == {}

    def test_resets_stats_time_to_none(self) -> None:
        state.stats_time = 3.14
        state._reset_globals()
        assert state.stats_time is None

    def test_idempotent_on_empty_state(self) -> None:
        state._reset_globals()
        state._reset_globals()  # second call should not raise
        assert state._stats == set()
        assert len(state.tests_by_mangled_function_name) == 0


class TestStateWriteAndRead:
    def test_adding_to_stats(self) -> None:
        state._reset_globals()
        state._stats.add("pkg.my_func__mutmut_1")
        assert "pkg.my_func__mutmut_1" in state._stats

    def test_defaultdict_auto_creates_set(self) -> None:
        state._reset_globals()
        state.tests_by_mangled_function_name["new_key"].add("tests/t.py::test_a")
        assert state.tests_by_mangled_function_name["new_key"] == {"tests/t.py::test_a"}

    def test_duration_accumulation(self) -> None:
        state._reset_globals()
        state.duration_by_test["tests/t.py::test_a"] = 0.3
        state.duration_by_test["tests/t.py::test_a"] = (
            state.duration_by_test.get("tests/t.py::test_a", 0.0) + 0.2
        )
        assert state.duration_by_test["tests/t.py::test_a"] == 0.5
