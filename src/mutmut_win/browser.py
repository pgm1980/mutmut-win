"""TUI Result Browser for mutmut-win.

Provides a Textual-based interactive browser for mutation testing results.
Ported from mutmut 3.5.0 ResultBrowser, adapted to use mutmut_win's DB layer.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Any, ClassVar, Final

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static

from mutmut_win.constants import emoji_by_status, status_by_exit_code
from mutmut_win.db import (
    DEFAULT_DB_PATH,
    RunBasisIncompleteness,
    known_run_basis_incompleteness,
)
from mutmut_win.exceptions import CacheEnvironmentError, CorruptCacheError, ProcessContainmentError
from mutmut_win.models import (
    MutationResult,
    SourceFileMutationData,
    read_owned_source_metadata,
)
from mutmut_win.process.foreground import run_foreground_contained

if TYPE_CHECKING:
    from textual.binding import Binding
    from textual.visual import VisualType

    from mutmut_win.db import MutationRunState

#: CSS file co-located with this package
_CSS_PATH = Path(__file__).parent / "result_browser_layout.tcss"

#: Emoji per status — the constants.py map IS the source of truth.  The
#: private copy this replaced predated the IL classifier and had drifted
#: (no killed_by_infinite_loop entry, audit A4-UI-002).
_EMOJI_BY_STATUS: dict[str, str] = emoji_by_status

#: Statuses that count as a kill — hidden from the mutants table unless
#: --show-killed is given.
_KILL_STATUSES: frozenset[str] = frozenset(
    {"killed", "caught by type check", "killed_by_infinite_loop"}
)

_STATUS_COLUMNS: list[tuple[str, Any]] = [("path", "Path")] + [
    (status, Text(emoji, justify="right")) for status, emoji in _EMOJI_BY_STATUS.items()
]

#: Maximum command-line length accepted for a package ``__init__`` retest.
#: ``CreateProcessW`` caps ``lpCommandLine`` at 32,767 UTF-16 code units
#: *including* the terminating NUL, and the explicit mutant-name list of a
#: large ``__init__`` file travels on exactly that one command line:
#: :func:`subprocess.list2cmdline` reproduces the quoting that
#: ``AtomicJobPopen`` (M-057) then hands to ``CreateProcessW``.  The
#: ~750-character reserve below the hard kernel limit keeps
#: environment-specific ``sys.executable`` paths and future launcher
#: changes safely inside it; an oversized retest is refused rather than
#: started only to die at process creation (M-058).
_RETEST_COMMAND_LINE_LIMIT: Final[int] = 32_000


def _describe_mutant(
    status: str,
    exit_code: int | None,
    duration: float | str,
    estimated_duration: float | str,
    type_check_error: str,
) -> str:
    """Return the one-line status description shown above the diff view.

    Args:
        status: Status string from ``constants.status_by_exit_code``.
        exit_code: Raw pytest/classifier exit code, or ``None`` if unknown.
        duration: Measured run duration in seconds, or ``"?"``.
        estimated_duration: Baseline test duration in seconds, or ``"?"``.
        type_check_error: Type checker output for type-check kills, or ``"?"``.

    Returns:
        A human-readable description of the mutant's outcome.
    """
    view_tests_desc = "(press r to retest this mutant)"

    match status:
        case "killed":
            return f"Killed ({exit_code=}): Mutant caused a test to fail 🎉"
        case "killed_by_infinite_loop":
            return (
                f"Killed — infinite loop ({exit_code=}): The IL detector classified "
                "this mutant as non-terminating 🌀 "
                "Run 'mutmut-win show <mutant>' for the forensics behind the verdict."
            )
        case "survived":
            return f"Survived ({exit_code=}): No test detected this mutant. {view_tests_desc}"
        case "skipped":
            return f"Skipped ({exit_code=})"
        case "check was interrupted by user":
            return f"User interrupted ({exit_code=})"
        case "caught by type check":
            return f"Caught by type checker ({exit_code=}): {type_check_error}"
        case "timeout":
            dur_str = f"{duration:.3f}" if isinstance(duration, float) else str(duration)
            est_str = (
                f"{estimated_duration:.3f}"
                if isinstance(estimated_duration, float)
                else str(estimated_duration)
            )
            return (
                f"Timeout ({exit_code=}): Timed out after {dur_str}s. "
                f"Tests without mutation took {est_str}s. {view_tests_desc}"
            )
        case "no tests":
            return (
                f"Untested ({exit_code=}): Skipped because selected tests do not execute this code."
            )
        case "segfault":
            return f"Segfault ({exit_code=}): Running pytest with this mutant segfaulted."
        case "suspicious":
            return (
                f"Unknown ({exit_code=}): "
                "Running pytest with this mutant resulted in an unknown exit code."
            )
        case "not checked":
            return "Not checked in the last mutmut-win run."
        case _:
            return f"Unknown status ({exit_code=}, {status=})"


def _get_diff_for_mutant(mutant_name: str, path: Path | None = None) -> str:
    """Return the per-mutant function diff for *mutant_name*.

    Single source (issue #108 / A4-UI-007): the rendering is
    ``mutant_diff.render_function_diff`` — the same diff ``show`` prints.
    The previous implementation diffed the WHOLE file (trampoline plus all
    mutant variants, identical output for every mutant), and the DB
    fallback searched file contents for the QUALIFIED name, which never
    appears there — only path discovery differs per case now:

    * known *path* (meta-backed): render directly,
    * unknown: resolve via the config walk (``get_diff_for_mutant``),
    * meta files absent (DB-only fallback): locate the staged owner via
      the canonical module identity
      (``mutant_diff.locate_staged_source_for_mutant``), then render —
      never a file-content scan, whose first local-name hit can belong to
      a different module or a longer mutant ordinal (M-115).

    Args:
        mutant_name: Unique mutant identifier.
        path: Source file path. If ``None``, it is resolved from the
            mutants/ directory.

    Returns:
        Unified diff as a string, or a ``<...>`` marker line on failure.
    """
    from mutmut_win import mutant_diff

    if path is not None:
        return mutant_diff.render_function_diff(path, mutant_name)

    from mutmut_win.config import load_config

    try:
        return mutant_diff.get_diff_for_mutant(mutant_name, load_config())
    except FileNotFoundError:
        pass  # no meta files (DB-only state) — locate the owner by identity

    try:
        staged_rel = mutant_diff.locate_staged_source_for_mutant(mutant_name)
        return mutant_diff.render_function_diff(staged_rel, mutant_name)
    except FileNotFoundError:
        # Locating and provenance gaps are display-level "not found";
        # byte-verification refusals (StaleStagingError etc.) propagate.
        return f"<mutant '{mutant_name}' not found>"


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
        # Project fixtures may legitimately use the same suffix.  Only an
        # explicitly schema-marked sidecar whose generated companion matches
        # its committed hash belongs to mutmut-win; browsing must never heal
        # or delete arbitrary lookalikes.
        if read_owned_source_metadata(meta_file) is None:
            continue
        try:
            rel_meta = meta_file.relative_to(mutants_dir)
        except ValueError:
            continue

        source_path = str(rel_meta).removesuffix(".meta")
        sfd = SourceFileMutationData(path=source_path)
        sfd.load(heal_corrupt=False)

        if not sfd.exit_code_by_key:
            continue

        counts: dict[str, int] = {}
        for exit_code in sfd.exit_code_by_key.values():
            status = status_by_exit_code.get(exit_code, "suspicious")
            counts[status] = counts.get(status, 0) + 1

        result[source_path] = sfd, counts

    return result


@dataclass(frozen=True)
class _DiffRequest:
    """M-119: one pending diff computation for the single daemon worker.

    The latest-wins slot means at most one diff is computed at a time;
    a newer request silently replaces an older, not-yet-started one.
    """

    generation: int
    mutant_name: str
    path: Path | None


class ResultBrowser(App[None]):
    """Textual TUI app for browsing mutation testing results.

    Args:
        show_killed: When ``True``, killed mutants are included in the mutants table.
        db_path: Path to the SQLite results database (used as fallback data source).
    """

    CSS_PATH = str(_CSS_PATH)

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("q", "quit()", "Quit"),
        ("r", "retest_mutant()", "Retest mutant"),
        ("f", "retest_function()", "Retest function"),
        ("m", "retest_module()", "Retest module"),
        ("a", "apply_mutant()", "Apply mutant to disk"),
        ("t", "view_tests()", "View tests for mutant"),
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
        # M-117: monotonic request generation for diff staleness. Only the
        # app thread writes; workers read. Replaces the old _loading_id.
        self._diff_generation: int = 0
        # M-119: single lazy daemon worker with latest-wins slot.
        self._diff_worker: Thread | None = None
        self._diff_condition = threading.Condition()
        self._diff_request: _DiffRequest | None = None
        self._diff_worker_stop = False
        self._source_data: dict[str, tuple[SourceFileMutationData, dict[str, int]]] = {}
        self._path_by_name: dict[str, str] = {}
        self._db_results: dict[str, MutationResult] = {}
        self._current_run_names: set[str] | None = None
        self._current_run_state: MutationRunState | None = None
        self._run_state_error: str | None = None
        self._unmapped_current_names: set[str] = set()

    def compose(self) -> ComposeResult:
        """Build the widget tree."""
        yield Static(id="run_status")
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
        self._update_run_status()
        self._populate_files_table()

    def _update_run_status(self) -> None:
        """Render the persisted attempt status independently of verdict rows."""
        run_status: Static = self.query_one("#run_status", Static)
        if self._run_state_error is not None:
            run_status.add_class("evidence-invalidated")
            warning = Text()
            warning.append(
                "CORRUPT PERSISTED RUN EVIDENCE - NOT RELEASE-READY\n",
                style="bold white on red",
            )
            warning.append(
                "execution_basis_complete=false; release_ready=false; "
                f"error={self._run_state_error}",
                style="bold red",
            )
            run_status.update(warning)
        elif self._current_run_state is None:
            run_status.remove_class("evidence-invalidated")
            run_status.update("No persisted mutation run")
        else:
            current = self._current_run_state
            if current.evidence_invalidated:
                run_status.add_class("evidence-invalidated")
                warning = Text()
                warning.append(
                    "STALE / INVALIDATED EVIDENCE - NOT RELEASE-READY\n",
                    style="bold white on red",
                )
                warning.append(
                    "evidence_invalidated=true; release_ready=false; "
                    f"run={current.run_id[:8]}; recorded_run_state={current.status}; "
                    f"completed_mutants={len(current.completed_names)}/"
                    f"{len(current.planned_names)}; "
                    f"pending={len(current.pending_names)}; "
                    f"plan_finalized={current.plan_finalized}; started={current.started_at}",
                    style="bold red",
                )
                run_status.update(warning)
                return

            basis_issue = known_run_basis_incompleteness(current)
            if current.status == "completed" and (
                basis_issue is not None or not current.is_full_run
            ):
                run_status.add_class("evidence-invalidated")
                warning = Text()
                if basis_issue is RunBasisIncompleteness.MALFORMED:
                    warning.append(
                        "MALFORMED EXECUTION BASIS - NOT RELEASE-READY\n",
                        style="bold white on red",
                    )
                    detail_style = "bold red"
                elif not current.is_full_run:
                    warning.append(
                        "SUBSET RUN - NOT RELEASE-READY\n",
                        style="bold black on yellow",
                    )
                    detail_style = "bold yellow"
                else:
                    warning.append(
                        "INCOMPLETE EXECUTION BASIS - NOT RELEASE-READY\n",
                        style="bold black on yellow",
                    )
                    detail_style = "bold yellow"
                basis_complete = basis_issue is None
                basis_detail = "" if basis_issue is None else f"basis_reason={basis_issue.value}; "
                warning.append(
                    f"execution_basis_complete={str(basis_complete).lower()}; "
                    "release_ready=false; "
                    f"run_scope={'full' if current.is_full_run else 'subset'}; "
                    f"{basis_detail}"
                    f"run={current.run_id[:8]}; recorded_run_state={current.status}; "
                    f"completed_mutants={len(current.completed_names)}/"
                    f"{len(current.planned_names)}; pending={len(current.pending_names)}",
                    style=detail_style,
                )
                run_status.update(warning)
                return

            run_status.remove_class("evidence-invalidated")
            run_status.update(
                f"Run {current.run_id[:8]}: status={current.status}, "
                f"completed={len(current.completed_names)}/{len(current.planned_names)}, "
                f"pending={len(current.pending_names)}, "
                f"plan_finalized={current.plan_finalized}, started={current.started_at}"
            )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _read_data(self) -> None:
        """Load mutation data from meta files and DB into instance state."""
        self._source_data = _load_source_file_data()
        self._path_by_name = {}
        self._db_results = {}
        self._current_run_names = None
        self._current_run_state = None
        self._run_state_error = None
        self._unmapped_current_names = set()

        # A persisted run snapshot, when present, is the display authority.
        # Meta files and the historical mutant table are reusable caches and
        # may still contain verdicts from a prior or only partially completed
        # invocation (MW220-021).
        from mutmut_win.db import load_latest_run_results

        try:
            current_run, latest_results = load_latest_run_results(self._db_path)
        except (CorruptCacheError, CacheEnvironmentError) as exc:
            self._run_state_error = str(exc)
            return
        if current_run is not None:
            self._current_run_state = current_run
            self._current_run_names = set(current_run.planned_names)
            self._db_results = {result.mutant_name: result for result in latest_results}

            current_source_data: dict[str, tuple[SourceFileMutationData, dict[str, int]]] = {}
            for file_path, (sfd, _old_counts) in self._source_data.items():
                current_names = [
                    name for name in sfd.exit_code_by_key if name in self._current_run_names
                ]
                if not current_names:
                    continue
                counts: dict[str, int] = {}
                for name in current_names:
                    result = self._db_results[name]
                    counts[result.status] = counts.get(result.status, 0) + 1
                    self._path_by_name[name] = file_path
                current_source_data[file_path] = (sfd, counts)
            mapped_names = set(self._path_by_name)
            self._unmapped_current_names = self._current_run_names - mapped_names
            self._source_data = current_source_data
            return

        # Build name→path mapping from meta file data
        for file_path, (sfd, _counts) in self._source_data.items():
            for name in sfd.exit_code_by_key:
                self._path_by_name[name] = file_path

        # Fallback: load from SQLite DB when meta files are absent
        if not self._source_data:
            self._db_results = {result.mutant_name: result for result in latest_results}

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

        if self._unmapped_current_names:
            missing_counts: dict[str, int] = {}
            for name in self._unmapped_current_names:
                status = self._db_results[name].status
                missing_counts[status] = missing_counts.get(status, 0) + 1
            missing_cells: list[Any] = [
                Text(str(missing_counts.get(status, 0)), justify="right")
                for status, _label in _STATUS_COLUMNS[1:]
            ]
            missing_row: list[Any] = ["(metadata missing)", *missing_cells]
            files_table.add_row(*missing_row, key="__unmapped__")

        if not self._source_data and self._db_results and not self._unmapped_current_names:
            # Fallback: show DB results aggregated by a single synthetic row
            db_counts: dict[str, int] = {}
            for r in self._db_results.values():
                db_counts[r.status] = db_counts.get(r.status, 0) + 1
            all_cells: list[Any] = [
                Text(str(db_counts.get(status, 0)), justify="right")
                for status, _label in _STATUS_COLUMNS[1:]
            ]
            all_row: list[Any] = ["(all mutants)", *all_cells]
            files_table.add_row(*all_row, key="__all__")

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
        # M-120: invalidate in-flight diff requests and neutralize the
        # detail display — a previous mutant's description and diff must
        # not survive a file switch or an empty mutants table.
        self._invalidate_diff_requests()
        from textual.css.query import NoMatches

        try:
            description_view: Static = self.query_one("#description", Static)
            diff_view: Static = self.query_one("#diff_view", Static)
            description_view.update("")
            diff_view.update("")
        except NoMatches:
            pass

        mutants_table: DataTable[str] = self.query_one("#mutants", DataTable)
        mutants_table.clear()

        if file_path == "__all__":
            for mutant_name, result in sorted(self._db_results.items()):
                status = result.status
                if status not in _KILL_STATUSES or self._show_killed:
                    emoji = _EMOJI_BY_STATUS.get(status, "?")
                    mutants_table.add_row(mutant_name, emoji, key=mutant_name)
            return

        if file_path == "__unmapped__":
            for mutant_name in sorted(self._unmapped_current_names):
                status = self._db_results[mutant_name].status
                if status not in _KILL_STATUSES or self._show_killed:
                    emoji = _EMOJI_BY_STATUS.get(status, "?")
                    mutants_table.add_row(mutant_name, emoji, key=mutant_name)
            return

        if file_path not in self._source_data:
            return

        sfd, _counts = self._source_data[file_path]
        for mutant_name, exit_code in sfd.exit_code_by_key.items():
            if self._current_run_names is not None and mutant_name not in self._current_run_names:
                continue
            db_result = self._db_results.get(mutant_name)
            status = (
                db_result.status
                if db_result is not None
                else status_by_exit_code.get(exit_code, "suspicious")
            )
            if status not in _KILL_STATUSES or self._show_killed:
                emoji = _EMOJI_BY_STATUS.get(status, "?")
                mutants_table.add_row(mutant_name, emoji, key=mutant_name)

    # ------------------------------------------------------------------
    # M-117/M-118/M-119/M-120: generation-based, single-worker diff loading
    # ------------------------------------------------------------------

    def _invalidate_diff_requests(self) -> int:
        """Invalidate all in-flight diff requests; return the new generation.

        M-117: only called from the app thread. The monotonic counter makes
        A→B→A highlight sequences distinguishable without comparing mutant
        names. M-120: also called on file highlight to clear stale detail.
        """
        self._diff_generation += 1
        return self._diff_generation

    def _publish_diff(self, generation: int, content: VisualType) -> None:
        """Update the diff view only when *generation* is still current.

        M-117: both the success and the error path publish through this
        method, so a stale error can never overwrite a newer diff.
        """
        if generation != self._diff_generation:
            return
        from textual.css.query import NoMatches

        try:
            diff_view: Static = self.query_one("#diff_view", Static)
        except NoMatches:
            return  # app is shutting down
        diff_view.update(content)

    def _post_diff_from_thread(self, generation: int, content: VisualType) -> None:
        """Marshal a diff publication to the app thread safely (M-118).

        ``call_from_thread`` raises ``RuntimeError`` once the app has
        stopped — an unhandled exception from the diff thread after app
        end used to print a traceback.
        """
        import contextlib

        with contextlib.suppress(RuntimeError):
            self.call_from_thread(self._publish_diff, generation, content)

    def _start_diff_worker(self) -> None:
        """Lazily start the single daemon diff worker (M-119)."""
        if self._diff_worker is not None and self._diff_worker.is_alive():
            return

        def _worker_loop() -> None:
            while True:
                with self._diff_condition:
                    while self._diff_request is None and not self._diff_worker_stop:
                        self._diff_condition.wait()
                    if self._diff_worker_stop:
                        return
                    request = self._diff_request
                    self._diff_request = None
                if request is None:
                    continue
                # Early exit: a newer request already arrived.
                if request.generation != self._diff_generation:
                    continue
                try:
                    from rich.syntax import Syntax

                    d = _get_diff_for_mutant(request.mutant_name, path=request.path)
                    content: VisualType = Syntax(d, "diff")
                except Exception as exc:
                    from rich.text import Text as RichText

                    content = RichText(f"<{type(exc).__name__}: {exc}>")
                self._post_diff_from_thread(request.generation, content)

        self._diff_worker = Thread(target=_worker_loop, daemon=True, name="mutmut-diff-worker")
        self._diff_worker.start()

    def _submit_diff_request(self, generation: int, mutant_name: str, path: Path | None) -> None:
        """Submit a diff request to the latest-wins slot (M-119)."""
        self._start_diff_worker()
        with self._diff_condition:
            self._diff_request = _DiffRequest(
                generation=generation, mutant_name=mutant_name, path=path
            )
            self._diff_condition.notify()

    def _stop_diff_worker(self) -> None:
        """Stop the diff worker (called on unmount)."""
        with self._diff_condition:
            self._diff_worker_stop = True
            self._diff_condition.notify_all()

    def on_unmount(self) -> None:
        """Clean up the diff worker when the app ends (M-119)."""
        self._stop_diff_worker()

    def _on_mutant_highlighted(self, mutant_name: str) -> None:
        """Update the description and submit the diff to the single worker."""
        description_view: Static = self.query_one("#description", Static)
        diff_view: Static = self.query_one("#diff_view", Static)

        generation = self._invalidate_diff_requests()

        # Gather status information
        file_path_str = self._path_by_name.get(mutant_name)
        exit_code: int | None = None
        estimated_duration: float | str = "?"
        duration: float | str = "?"
        type_check_error: str = "?"
        status = "not checked"

        if file_path_str is not None and file_path_str in self._source_data:
            sfd, _counts = self._source_data[file_path_str]
            exit_code = sfd.exit_code_by_key.get(mutant_name)
            estimated_duration = sfd.estimated_time_of_tests_by_mutant.get(mutant_name, "?")
            duration = sfd.durations_by_key.get(mutant_name, "?")
            type_check_error = sfd.type_check_error_by_key.get(mutant_name, "?")
            status = status_by_exit_code.get(exit_code, "suspicious")
        if mutant_name in self._db_results:
            db_result = self._db_results[mutant_name]
            exit_code = db_result.exit_code
            duration = db_result.duration if db_result.duration is not None else "?"
            # The database persists the canonical verdict.  Re-deriving it
            # from the exit code loses information for classifier-produced
            # statuses and turns legacy rows with a NULL code into
            # "suspicious" in the fallback UI.
            status = db_result.status

        description = _describe_mutant(
            status, exit_code, duration, estimated_duration, type_check_error
        )

        description_view.update(f"\n {description}\n")
        diff_view.update("<loading code diff...>")

        # M-119: submit to the single daemon worker instead of spawning
        # an unbounded thread per highlight.
        path_for_diff = Path(file_path_str) if file_path_str else None
        self._submit_diff_request(generation, mutant_name, path_for_diff)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _get_selected_mutant_name(self) -> str | None:
        """Return the mutant name from the current mutants table selection.

        Issue #109 / A4-UI-010: ``cursor_row`` is 0 even on an EMPTY table,
        so ``get_row_at(0)`` raised ``RowDoesNotExist`` and every action
        binding crashed before any mutant was listed — the ``None`` guard
        alone was dead code.
        """
        mutants_table: DataTable[str] = self.query_one("#mutants", DataTable)
        if mutants_table.row_count == 0 or mutants_table.cursor_row is None:
            return None
        row = mutants_table.get_row_at(mutants_table.cursor_row)
        return str(row[0]) if row else None

    def _run_subprocess_command(self, command: str, args: list[str]) -> None:
        """Suspend the TUI, run a contained mutmut-win sub-command, then resume.

        The child runs inside a kill-on-close Windows Job Object
        (:func:`mutmut_win.process.foreground.run_foreground_contained`), so
        a hard TUI death (window close, Task Manager) cannot leave the
        mutation-run process tree running (M-057 / issue #158).  Containment
        is fail-closed: when no Job Object can be established the failure is
        reported on the suspended console and NO uncontained fallback launch
        happens.

        Args:
            command: Sub-command name (e.g. ``"run"``).
            args: Arguments for the sub-command.
        """
        with self.suspend():
            subprocess_args = [sys.executable, "-m", "mutmut_win", command, *args]
            print(">", *subprocess_args)
            try:
                exit_code = run_foreground_contained(subprocess_args)
            except ProcessContainmentError as exc:
                print(f"refusing to start an uncontained child: {exc}")
            else:
                print(f"[{command} exit code: {exit_code}]")
            input("Press Enter to return to browser...")

        self._read_data()
        self._update_run_status()
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
        """Retest all mutants in the selected mutant's module — exactly that module.

        The module boundary comes from the loaded metadata mapping
        (``_path_by_name``), never from a guess off the mutant name: for a
        mutant from a package ``__init__.py`` the name's dotted prefix
        names the PACKAGE (``get_mutant_name`` deliberately drops
        ``__init__``), so the historical ``<prefix>.*`` glob selected every
        mutant of every submodule — fnmatch ``*`` crosses dots, which in a
        one-package ``src/`` layout effectively retested the whole project
        (M-058 / BC-065).

        Fail-closed (decided M-058 = A): a name without a metadata mapping
        (DB-only, unmapped, or stale) is refused with a warning instead of
        guessed at — without the mapping it is undecidable whether the
        name comes from a package ``__init__``.  No metadata is healed on
        read (M-026).

        Package ``__init__`` files pass the exact, sorted mutant-name list
        of that one file — deliberately including names outside the
        current run plan (snapshot mode: a whole-module retest wants every
        mutant of the file, and the browser's mapping may only cover the
        plan).  The price: mutants generated after the browser loaded its
        data are not covered until the metadata is rebuilt.  Normal
        modules keep the short ``<module>.*`` glob, which also catches
        newly generated mutants.

        The explicit list must fit on a single Windows command line (see
        ``_RETEST_COMMAND_LINE_LIMIT``); an empty list would make ``run``
        fall back to a FULL run, so it is refused as well.
        """
        mutant_name = self._get_selected_mutant_name()
        if not mutant_name:
            return

        file_path = self._path_by_name.get(mutant_name)
        if file_path is None or file_path not in self._source_data:
            self.notify(
                f"Retest module refused for {mutant_name}: no metadata maps this "
                "mutant name to a source file (unmapped or stale name), so the "
                "module boundary cannot be established. Retest the single mutant "
                "or re-run generation to rebuild the mapping.",
                title="Retest module",
                severity="warning",
                markup=False,
            )
            return

        if Path(file_path).name.casefold() == "__init__.py":
            sfd, _counts = self._source_data[file_path]
            names = sorted(sfd.exit_code_by_key)
            if not names:
                # `run` without name arguments means ALL mutants — an empty
                # list must never degrade into a full project retest.
                self.notify(
                    f"Retest module refused for {file_path}: the metadata lists "
                    "no mutants for this file; refusing instead of starting a "
                    "full run.",
                    title="Retest module",
                    severity="warning",
                    markup=False,
                )
                return
            command_line = subprocess.list2cmdline(
                [sys.executable, "-m", "mutmut_win", "run", *names]
            )
            if len(command_line) > _RETEST_COMMAND_LINE_LIMIT:
                self.notify(
                    f"Retest module refused for {file_path}: the explicit list of "
                    f"{len(names)} mutant names needs {len(command_line)} command-line "
                    f"characters, beyond the Windows limit of "
                    f"{_RETEST_COMMAND_LINE_LIMIT}. Start it manually with a subset: "
                    "mutmut-win run <mutant names>",
                    title="Retest module",
                    severity="warning",
                    markup=False,
                )
                return
            self.notify(
                f"Retesting package __init__ {file_path}: {len(names)} mutants "
                "of this file only (no submodules)",
                markup=False,
            )
            self._run_subprocess_command("run", names)
            return

        pattern = mutant_name.rpartition(".")[0] + ".*"
        self.notify(f"Retesting module {file_path} ({pattern})", markup=False)
        self._run_subprocess_command("run", [pattern])

    def action_apply_mutant(self) -> None:
        """Apply the currently selected mutant to the source file on disk."""
        mutant_name = self._get_selected_mutant_name()
        if mutant_name:
            self._run_subprocess_command("apply", [mutant_name])

    def action_view_tests(self) -> None:
        """Show tests mapped to the currently selected mutant."""
        mutant_name = self._get_selected_mutant_name()
        if mutant_name:
            self._run_subprocess_command("tests-for-mutant", [mutant_name])
