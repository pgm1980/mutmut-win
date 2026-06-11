"""Tests for browser IL awareness (Issue #87, audit A4-UI-002/003).

The TUI browser kept a private emoji map that predated the IL classifier:
IL-killed mutants rendered as "?" with no status column, leaked through the
killed-filter into the default view, and hit the catch-all description.
The emoji map is now derived from ``constants.emoji_by_status`` (single
source of truth), the kill-filter and the description match know the status.
"""

from __future__ import annotations

from mutmut_win.browser import (
    _EMOJI_BY_STATUS,
    _KILL_STATUSES,
    _STATUS_COLUMNS,
    _describe_mutant,
)
from mutmut_win.constants import emoji_by_status


class TestBrowserIlAwareness:
    def test_emoji_map_is_derived_from_constants(self) -> None:
        # Identity, not equality: a copy can drift again.
        assert _EMOJI_BY_STATUS is emoji_by_status
        assert "killed_by_infinite_loop" in _EMOJI_BY_STATUS

    def test_status_columns_include_il(self) -> None:
        assert any(status == "killed_by_infinite_loop" for status, _ in _STATUS_COLUMNS)

    def test_kill_statuses_cover_all_kill_classes(self) -> None:
        assert "killed" in _KILL_STATUSES
        assert "caught by type check" in _KILL_STATUSES
        assert "killed_by_infinite_loop" in _KILL_STATUSES
        assert "survived" not in _KILL_STATUSES
        assert "timeout" not in _KILL_STATUSES


class TestDescribeMutant:
    def test_il_kill_gets_an_honest_description(self) -> None:
        description = _describe_mutant("killed_by_infinite_loop", 38, 60.0, 1.0, "?")
        assert "infinite loop" in description.lower()
        assert "exit_code=38" in description
        assert "show" in description  # points the user at the forensics panel

    def test_existing_statuses_keep_their_descriptions(self) -> None:
        assert "🎉" in _describe_mutant("killed", 1, 0.5, 0.4, "?")
        assert "Survived" in _describe_mutant("survived", 0, 0.5, 0.4, "?")
        assert "Timed out after 0.500s" in _describe_mutant("timeout", 36, 0.5, 0.4, "?")
        assert "Unknown status" in _describe_mutant("nonsense", 99, 0.5, 0.4, "?")
