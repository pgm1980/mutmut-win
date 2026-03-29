"""TUI Result Browser for mutmut-win.

Provides a Textual-based interactive browser for mutation testing results.
Ported from mutmut 3.5.0 ResultBrowser, adapted to use mutmut_win's DB layer.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from threading import Thread
from typing import Any, ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static

from mutmut_win.constants import status_by_exit_code
from mutmut_win.db import DEFAULT_DB_PATH
from mutmut_win.models import MutationResult, SourceFileMutationData

#: CSS file co-located with this package
_CSS_PATH = Path(__file__).parent / "result_browser_layout.tcss"

#: Emoji per status (kept in sync with constants.py)
_EMOJI_BY_STATUS: dict[str, str] = {
    "survived": "🙁",
    "no tests": "🫥",
    "timeout": "⏰",
    "suspicious": "🤔",
    "skipped": "🔇",
    "caught by type check": "🧙",
    "check was interrupted by user": "🛑",
    "not checked": "?",
    "killed": "🎉",
    "segfault": "💥",
}

_STATUS_COLUMNS: list[tuple[str, Any]] = [("path", "Path")] + [
    (status, Text(emoji, justify="right")) for status, emoji in _EMOJI_BY_STATUS.items()
]


def _get_diff_for_mutant(mutant_name: str, path: Path | None = None) -> str:
    """Return a unified diff string for *mutant_name*.

    Args:
        mutant_name: Unique mutant identifier.
        path: Source file path. If ``None``, it is resolved from the mutants/ directory.

    Returns:
        Unified diff as a string, or an empty string if no diff is found.
    """
    import difflib

    mutants_dir = Path("mutants")

    if path is None:
        for py_file in mutants_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if mutant_name in content:
                path = py_file.relative_to(mutants_dir)
                break

    if path is None:
        return f"<mutant '{mutant_name}' not found>"

    mutant_file = mutants_dir / path
    orig_file = Path(path)

    if not mutant_file.exists():
        return f"<mutant file '{mutant_file}' not found>"
    if not orig_file.exists():
        return f"<original file '{orig_file}' not found>"

    orig_lines = orig_file.read_text(encoding="utf-8").splitlines(keepends=True)
    mutant_lines = mutant_file.read_text(encoding="utf-8").splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            orig_lines,
            mutant_lines,
            fromfile=str(orig_file),
            tofile=str(mutant_file),
        )
    )
    return "".join(diff) if diff else "<no diff>"


def _load_source_file_data() -> dict[str, tuple[SourceFileMutationData, dict[str, int]]]:
    """Load all SourceFileMutationData from the mutants/ meta files.

    Returns:
        Mapping of file path string to (SourceFileMutationData, status_counts) tuples.
    """
    result: dict[str, tuple[SourceFileMutationData, dict[str, int]]] = {}
    mutants_dir = Path("mutants")

    if not mutants_dir.is_dir():
        return result

    for meta_file in mutants_dir.rglob("*.meta"):
        try:
            rel_meta = meta_file.relative_to(mutants_dir)
        except ValueError:
            continue

        source_path = str(rel_meta).removesuffix(".meta")
        sfd = SourceFileMutationData(path=source_path)
        sfd.load()

        if not sfd.exit_code_by_key:
            continue

        counts: dict[str, int] = {}
        for exit_code in sfd.exit_code_by_key.values():
            status = status_by_exit_code.get(exit_code, "suspicious")
            counts[status] = counts.get(status, 0) + 1

        result[source_path] = sfd, counts

    return result


class ResultBrowser(App[None]):
    """Textual TUI app for browsing mutation testing results.

    Args:
        show_killed: When ``True``, killed mutants are included in the mutants table.
        db_path: Path to the SQLite results database (used as fallback data source).
    """

    CSS_PATH = str(_CSS_PATH)

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("q", "quit()", "Quit"),
        ("r", "retest_mutant()", "Retest mutant"),
        ("f", "retest_function()", "Retest function"),
        ("m", "retest_module()", "Retest module"),
        ("a", "apply_mutant()", "Apply mutant to disk"),
    ]

    def __init__(
        self,
        *args: Any,
        show_killed: bool = False,
        db_path: Path = DEFAULT_DB_PATH,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._show_killed = show_killed
        self._db_path = db_path
        self._loading_id: str | None = None
        self._source_data: dict[str, tuple[SourceFileMutationData, dict[str, int]]] = {}
        self._path_by_name: dict[str, str] = {}
        self._db_results: dict[str, MutationResult] = {}

    def compose(self) -> ComposeResult:
        """Build the widget tree."""
        with Container(classes="container"):
            yield DataTable(id="files")
            yield DataTable(id="mutants")
        with Widget(id="diff_view_widget"):
            yield Static(id="description")
            yield Static(id="diff_view")
        yield Footer()

    def on_mount(self) -> None:
        """Set up tables and load data after app mounts."""
        files_table: DataTable[str] = self.query_one("#files", DataTable)
        files_table.cursor_type = "row"
        for key, label in _STATUS_COLUMNS:
            files_table.add_column(key=key, label=label)

        mutants_table: DataTable[str] = self.query_one("#mutants", DataTable)
        mutants_table.cursor_type = "row"
        mutants_table.add_columns("name", "status")

        self._read_data()
        self._populate_files_table()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _read_data(self) -> None:
        """Load mutation data from meta files and DB into instance state."""
        self._source_data = _load_source_file_data()
        self._path_by_name = {}

        # Build name→path mapping from meta file data
        for file_path, (sfd, _counts) in self._source_data.items():
            for name in sfd.exit_code_by_key:
                self._path_by_name[name] = file_path

        # Fallback: load from SQLite DB when meta files are absent
        if not self._source_data:
            from mutmut_win.db import load_results

            raw_results = load_results(self._db_path)
            self._db_results = {r.mutant_name: r for r in raw_results}

    def _populate_files_table(self) -> None:
        """Refresh the files DataTable with current source data."""
        files_table: DataTable[str] = self.query_one("#files", DataTable)
        selected_row = files_table.cursor_row
        files_table.clear()

        for file_path, (_sfd, counts) in sorted(self._source_data.items()):
            row: list[Any] = [file_path] + [
                Text(str(counts.get(status, 0)), justify="right")
                for status, _label in _STATUS_COLUMNS[1:]
            ]
            files_table.add_row(*row, key=file_path)

        if not self._source_data and self._db_results:
            # Fallback: show DB results aggregated by a single synthetic row
            counts: dict[str, int] = {}
            for r in self._db_results.values():
                counts[r.status] = counts.get(r.status, 0) + 1
            row_data: list[Any] = ["(all mutants)"] + [
                Text(str(counts.get(status, 0)), justify="right")
                for status, _label in _STATUS_COLUMNS[1:]
            ]
            files_table.add_row(*row_data, key="__all__")

        files_table.move_cursor(row=selected_row)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row selection in either the files or mutants table."""
        if not event.row_key or not event.row_key.value:
            return

        table_id = event.data_table.id

        if table_id == "files":
            self._on_file_highlighted(event.row_key.value)
        elif table_id == "mutants":
            self._on_mutant_highlighted(event.row_key.value)

    def _on_file_highlighted(self, file_path: str) -> None:
        """Populate the mutants table for the highlighted file."""
        mutants_table: DataTable[str] = self.query_one("#mutants", DataTable)
        mutants_table.clear()

        if file_path == "__all__":
            for mutant_name, result in sorted(self._db_results.items()):
                status = result.status
                if status not in ("killed", "caught by type check") or self._show_killed:
                    emoji = _EMOJI_BY_STATUS.get(status, "?")
                    mutants_table.add_row(mutant_name, emoji, key=mutant_name)
            return

        if file_path not in self._source_data:
            return

        sfd, _counts = self._source_data[file_path]
        for mutant_name, exit_code in sfd.exit_code_by_key.items():
            status = status_by_exit_code.get(exit_code, "suspicious")
            if status not in ("killed", "caught by type check") or self._show_killed:
                emoji = _EMOJI_BY_STATUS.get(status, "?")
                mutants_table.add_row(mutant_name, emoji, key=mutant_name)

    def _on_mutant_highlighted(self, mutant_name: str) -> None:
        """Update the description and start loading the diff for the highlighted mutant."""
        description_view: Static = self.query_one("#description", Static)
        diff_view: Static = self.query_one("#diff_view", Static)

        self._loading_id = mutant_name

        # Gather status information
        file_path_str = self._path_by_name.get(mutant_name)
        exit_code: int | None = None
        estimated_duration: float | str = "?"
        duration: float | str = "?"
        type_check_error: str = "?"

        if file_path_str is not None and file_path_str in self._source_data:
            sfd, _counts = self._source_data[file_path_str]
            exit_code = sfd.exit_code_by_key.get(mutant_name)
            estimated_duration = sfd.estimated_time_of_tests_by_mutant.get(mutant_name, "?")
            duration = sfd.durations_by_key.get(mutant_name, "?")
            type_check_error = sfd.type_check_error_by_key.get(mutant_name, "?")
        elif mutant_name in self._db_results:
            db_result = self._db_results[mutant_name]
            exit_code = db_result.exit_code
            duration = db_result.duration if db_result.duration is not None else "?"

        status = status_by_exit_code.get(exit_code, "suspicious")
        view_tests_desc = "(press r to retest this mutant)"

        match status:
            case "killed":
                description = f"Killed ({exit_code=}): Mutant caused a test to fail 🎉"
            case "survived":
                description = (
                    f"Survived ({exit_code=}): No test detected this mutant. {view_tests_desc}"
                )
            case "skipped":
                description = f"Skipped ({exit_code=})"
            case "check was interrupted by user":
                description = f"User interrupted ({exit_code=})"
            case "caught by type check":
                description = f"Caught by type checker ({exit_code=}): {type_check_error}"
            case "timeout":
                dur_str = f"{duration:.3f}" if isinstance(duration, float) else str(duration)
                est_str = (
                    f"{estimated_duration:.3f}"
                    if isinstance(estimated_duration, float)
                    else str(estimated_duration)
                )
                description = (
                    f"Timeout ({exit_code=}): Timed out after {dur_str}s. "
                    f"Tests without mutation took {est_str}s. {view_tests_desc}"
                )
            case "no tests":
                description = (
                    f"Untested ({exit_code=}): "
                    "Skipped because selected tests do not execute this code."
                )
            case "segfault":
                description = (
                    f"Segfault ({exit_code=}): Running pytest with this mutant segfaulted."
                )
            case "suspicious":
                description = (
                    f"Unknown ({exit_code=}): "
                    "Running pytest with this mutant resulted in an unknown exit code."
                )
            case "not checked":
                description = "Not checked in the last mutmut-win run."
            case _:
                description = f"Unknown status ({exit_code=}, {status=})"

        description_view.update(f"\n {description}\n")
        diff_view.update("<loading code diff...>")

        # Load diff asynchronously to avoid blocking the UI
        path_for_diff = Path(file_path_str) if file_path_str else None

        def _load_thread() -> None:
            try:
                d = _get_diff_for_mutant(mutant_name, path=path_for_diff)
                if mutant_name == self._loading_id:
                    from rich.syntax import Syntax

                    self.call_from_thread(diff_view.update, Syntax(d, "diff"))
            except Exception as exc:  # show all errors inline
                self.call_from_thread(diff_view.update, f"<{type(exc).__name__}: {exc}>")

        thread = Thread(target=_load_thread, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _get_selected_mutant_name(self) -> str | None:
        """Return the mutant name from the current mutants table selection."""
        mutants_table: DataTable[str] = self.query_one("#mutants", DataTable)
        if mutants_table.cursor_row is None:
            return None
        row = mutants_table.get_row_at(mutants_table.cursor_row)
        return str(row[0]) if row else None

    def _run_subprocess_command(self, command: str, args: list[str]) -> None:
        """Suspend the TUI, run a mutmut-win sub-command, then resume.

        Args:
            command: Sub-command name (e.g. ``"run"``).
            args: Arguments for the sub-command.
        """
        with self.suspend():
            subprocess_args = [sys.executable, "-m", "mutmut_win", command, *args]
            print(">", *subprocess_args)
            subprocess.run(subprocess_args, check=False)  # noqa: S603 — controlled invocation
            input("Press Enter to return to browser...")

        self._read_data()
        self._populate_files_table()

    def action_retest_mutant(self) -> None:
        """Retest the currently selected mutant."""
        mutant_name = self._get_selected_mutant_name()
        if mutant_name:
            self._run_subprocess_command("run", [mutant_name])

    def action_retest_function(self) -> None:
        """Retest all mutants for the selected mutant's function."""
        mutant_name = self._get_selected_mutant_name()
        if mutant_name:
            pattern = mutant_name.rpartition("__mutmut_")[0] + "__mutmut_*"
            self._run_subprocess_command("run", [pattern])

    def action_retest_module(self) -> None:
        """Retest all mutants in the selected mutant's module."""
        mutant_name = self._get_selected_mutant_name()
        if mutant_name:
            pattern = mutant_name.rpartition(".")[0] + ".*"
            self._run_subprocess_command("run", [pattern])

    def action_apply_mutant(self) -> None:
        """Apply the currently selected mutant to the source file on disk."""
        mutant_name = self._get_selected_mutant_name()
        if mutant_name:
            self._run_subprocess_command("apply", [mutant_name])
