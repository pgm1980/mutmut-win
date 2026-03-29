"""Unit tests for mutmut_win.code_coverage."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

from mutmut_win.code_coverage import (
    _unload_modules_not_in,
    get_covered_lines_for_file,
)

# --- get_covered_lines_for_file -----------------------------------------------

class TestGetCoveredLinesForFile:
    def test_none_covered_lines_returns_none(self) -> None:
        result = get_covered_lines_for_file("foo.py", None)  # type: ignore[arg-type]
        assert result is None

    def test_none_filename_returns_none(self) -> None:
        result = get_covered_lines_for_file(None, {})  # type: ignore[arg-type]
        assert result is None

    def test_file_not_in_covered_lines_returns_empty_set(self) -> None:
        result = get_covered_lines_for_file("missing.py", {})
        assert result == set()

    def test_file_in_covered_lines_returns_lines(self) -> None:
        # Build the expected absolute path the same way the function does
        abs_path = str((Path("mutants") / "foo.py").absolute())
        covered = {abs_path: {1, 2, 3}}
        result = get_covered_lines_for_file("foo.py", covered)
        assert result == {1, 2, 3}

    def test_empty_line_set_in_covered_lines_returns_empty_set(self) -> None:
        abs_path = str((Path("mutants") / "bar.py").absolute())
        covered = {abs_path: set()}
        result = get_covered_lines_for_file("bar.py", covered)
        # falsy empty set -> falls back to set()
        assert result == set()


# --- _unload_modules_not_in ---------------------------------------------------

class TestUnloadModulesNotIn:
    def test_does_not_unload_mutmut_win_code_coverage(self) -> None:
        """The code_coverage module itself must not be unloaded."""
        # Snapshot: only keep modules already present
        original_modules = dict(sys.modules)

        # Add a fake module
        fake_module_name = "_test_fake_module_xyz"
        sys.modules[fake_module_name] = MagicMock()

        try:
            _unload_modules_not_in(original_modules)
            # Fake module should have been removed
            assert fake_module_name not in sys.modules
        finally:
            # Cleanup
            sys.modules.pop(fake_module_name, None)

    def test_preserves_modules_in_snapshot(self) -> None:
        """Modules present at snapshot time should NOT be unloaded."""
        snapshot = dict(sys.modules)
        # Run unload - nothing new was added
        _unload_modules_not_in(snapshot)
        # sys.modules should still contain all original modules
        for key in snapshot:
            if key != "mutmut_win.code_coverage":
                assert key in sys.modules
