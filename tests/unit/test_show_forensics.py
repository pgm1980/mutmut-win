"""Tests for the IL forensics panel in `show` (Issue #87, audit A4-UI-001).

An IL verdict (exit 38) kills a mutant based on a psutil triple-check, but
`show` rendered only the diff — the forensics persisted since #85 were
invisible, so a user could not audit WHY the detector fired.  `show` now
appends a forensics panel for IL-killed mutants, NULL-safe for rows written
before v2.8.0 (forensics column is NULL there).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from click.testing import CliRunner

import mutmut_win.cli as cli_module
from mutmut_win.cli import _format_forensics_panel
from mutmut_win.db import create_db, save_result

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_FORENSICS: dict[str, object] = {
    "cpu_pct_mean": 96.5,
    "cpu_pct_max": 99.0,
    "output_growth_bytes": 0,
    "running_ratio": 1.0,
    "samples_collected": 19,
    "window_seconds": 10.0,
    "last_output_tail": "test_spin ...",
    "confidence": "high",
}


class TestFormatForensicsPanel:
    def test_non_il_status_renders_nothing(self) -> None:
        assert _format_forensics_panel("killed", None) is None
        assert _format_forensics_panel("survived", _FORENSICS) is None
        assert _format_forensics_panel(None, None) is None

    def test_full_forensics_panel(self) -> None:
        panel = _format_forensics_panel("killed_by_infinite_loop", _FORENSICS)
        assert panel is not None
        assert "confidence: high" in panel
        assert "96.5" in panel  # cpu mean
        assert "99.0" in panel  # cpu max
        assert "0 bytes" in panel  # output growth
        assert "10.0" in panel  # window seconds
        assert "1.00" in panel  # running ratio
        assert "19" in panel  # samples
        assert "test_spin ..." in panel  # output tail

    def test_pre_v28_row_without_forensics_is_null_safe(self) -> None:
        panel = _format_forensics_panel("killed_by_infinite_loop", None)
        assert panel is not None
        assert "No forensics recorded" in panel

    def test_partial_forensics_dict_is_null_safe(self) -> None:
        # Tolerant against schema drift: missing keys must not raise.
        panel = _format_forensics_panel("killed_by_infinite_loop", {"confidence": "low"})
        assert panel is not None
        assert "confidence: low" in panel


class TestShowCommandForensics:
    def _invoke_show(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, with_db_row: bool
    ) -> str:
        db_path = tmp_path / "results.sqlite"
        if with_db_row:
            create_db(db_path)
            save_result(
                db_path, "pkg.x_f__mutmut_1", "killed_by_infinite_loop", 38, 60.0, None, _FORENSICS
            )
        (tmp_path / "mutants").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli_module, "DEFAULT_DB_PATH", db_path)
        monkeypatch.setattr(cli_module, "load_config", lambda: None)
        monkeypatch.setattr(
            cli_module,
            "resolve_mutant",
            lambda _pattern, _config: ("pkg.x_f__mutmut_1", SimpleNamespace(path="src/pkg.py")),
        )
        monkeypatch.setattr(cli_module, "render_function_diff", lambda _path, _name: "-old\n+new")
        result = CliRunner().invoke(cli_module.show, ["pkg.x_f__mutmut_1"])
        assert result.exit_code == 0, result.output
        return result.output

    def test_show_appends_panel_for_il_kill(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output = self._invoke_show(tmp_path, monkeypatch, with_db_row=True)
        assert "-old\n+new" in output  # diff still rendered
        assert "Infinite-loop verdict" in output
        assert "confidence: high" in output

    def test_show_without_db_row_renders_diff_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output = self._invoke_show(tmp_path, monkeypatch, with_db_row=False)
        assert "-old\n+new" in output
        assert "Infinite-loop verdict" not in output

    def test_show_with_glob_pattern_finds_forensics_panel(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-A9 (#127): the DB lookup used the RAW user pattern — `show`
        # with a glob rendered the diff but silently lost the forensics
        # panel. The pattern is resolved ONCE; header, diff and DB lookup
        # all use the resolved name.
        from types import SimpleNamespace

        db_path = tmp_path / "results.sqlite"
        create_db(db_path)
        save_result(
            db_path, "pkg.x_f__mutmut_1", "killed_by_infinite_loop", 38, 60.0, None, _FORENSICS
        )
        (tmp_path / "mutants").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli_module, "DEFAULT_DB_PATH", db_path)
        monkeypatch.setattr(cli_module, "load_config", lambda: None)
        monkeypatch.setattr(
            cli_module,
            "resolve_mutant",
            lambda _pattern, _config: ("pkg.x_f__mutmut_1", SimpleNamespace(path="src/pkg.py")),
        )
        monkeypatch.setattr(cli_module, "render_function_diff", lambda _path, _name: "-old\n+new")

        result = CliRunner().invoke(cli_module.show, ["pkg.x_f__mutmut_*"])

        assert result.exit_code == 0, result.output
        assert "# pkg.x_f__mutmut_1" in result.output  # header shows the RESOLVED name
        assert "Infinite-loop verdict" in result.output
