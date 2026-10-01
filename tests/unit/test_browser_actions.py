"""Browser TUI action harness tests (M-057 / issue #158, M-058 / BC-065).

``ResultBrowser._run_subprocess_command`` used to launch
``python -m mutmut_win ...`` via a bare ``subprocess.run`` — the only
uncontained start of a long-lived mutmut-win process tree: a hard TUI
death (terminal window close, Task Manager) left the whole mutation-run
child tree running.  These tests pin the launcher boundary: every TUI
action MUST go through ``run_foreground_contained`` (kill-on-close Job
Object) and MUST NOT call ``subprocess.run``/``subprocess.Popen``
directly.  A GLOBAL tripwire patch on the ``subprocess`` module fails any
uncontained launch loudly, independently of how browser.py imports it
(mutation-testing pin: killing the launcher import must turn these red).
The console contract (``>``-echo, fail-closed message, the return prompt)
is pinned too — the suspended terminal is the error channel.

``action_retest_module`` (M-058) derives its scope from the metadata
mapping instead of guessing it off the mutant name: a mutant from a
package ``__init__.py`` is named after the PACKAGE
(``get_mutant_name`` drops ``__init__``), so the old ``<prefix>.*`` glob
selected every mutant of every submodule (fnmatch ``*`` crosses dots) —
in a one-package ``src/`` layout effectively the whole project.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from mutmut_win.browser import ResultBrowser
from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.models import SourceFileMutationData
from mutmut_win.test_mapping import match_mutant_names

if TYPE_CHECKING:
    from pathlib import Path

_RETURN_PROMPT = "Press Enter to return to browser..."


def _uncontained_launch(*_args: object, **_kwargs: object) -> int:
    """Tripwire for direct subprocess launches — a containment regression."""
    raise AssertionError("uncontained subprocess launch")


@pytest.fixture
def browser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ResultBrowser, list[str], list[tuple[object, ...]]]:
    """A ResultBrowser with the TUI internals reduced to recording no-ops.

    Returns the app, the refresh recorder list (no-op ``_read_data`` /
    ``_update_run_status`` / ``_populate_files_table``), and the recorder
    list of every ``input()`` call's positional arguments.
    """
    app = ResultBrowser(db_path=tmp_path / "absent.sqlite")
    refreshed: list[str] = []
    input_calls: list[tuple[object, ...]] = []

    monkeypatch.setattr(ResultBrowser, "suspend", lambda _self: contextlib.nullcontext())
    monkeypatch.setattr(app, "_read_data", lambda: refreshed.append("read"))
    monkeypatch.setattr(app, "_update_run_status", lambda: refreshed.append("status"))
    monkeypatch.setattr(app, "_populate_files_table", lambda: refreshed.append("files"))
    monkeypatch.setattr("builtins.input", lambda *args: (input_calls.append(args), "")[1])
    return app, refreshed, input_calls


def test_run_subprocess_command_uses_contained_launcher(
    browser: tuple[ResultBrowser, list[str], list[tuple[object, ...]]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The sub-command must run via run_foreground_contained, never raw subprocess."""
    app, refreshed, input_calls = browser
    launched: list[list[str]] = []

    def fake_launcher(cmd: list[str]) -> int:
        launched.append(list(cmd))
        return 0

    # raising=False keeps the pre-fix run RED for the right reason (the
    # global tripwire below fires) instead of dying on a missing attribute.
    monkeypatch.setattr("mutmut_win.browser.run_foreground_contained", fake_launcher, raising=False)
    monkeypatch.setattr(subprocess, "run", _uncontained_launch)
    monkeypatch.setattr(subprocess, "Popen", _uncontained_launch)

    app._run_subprocess_command("run", ["m.x_f__mutmut_1"])

    assert launched == [[sys.executable, "-m", "mutmut_win", "run", "m.x_f__mutmut_1"]]
    assert refreshed == ["read", "status", "files"]
    assert input_calls == [(_RETURN_PROMPT,)]
    out = capsys.readouterr().out
    # Console echo of the command line: "> <exe> -m mutmut_win run m.x_f__mutmut_1"
    assert out.startswith("> ")
    assert f"> {sys.executable} -m mutmut_win run m.x_f__mutmut_1" in out
    assert "[run exit code: 0]" in out


def test_run_subprocess_command_fail_closed_on_containment_error(
    browser: tuple[ResultBrowser, list[str], list[tuple[object, ...]]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No Job Object -> clear message, NO uncontained fallback, refresh still runs."""
    app, refreshed, input_calls = browser

    def refusing_launcher(_cmd: list[str]) -> int:
        raise ProcessContainmentError("no Job Object available")

    monkeypatch.setattr(
        "mutmut_win.browser.run_foreground_contained", refusing_launcher, raising=False
    )
    monkeypatch.setattr(subprocess, "run", _uncontained_launch)
    monkeypatch.setattr(subprocess, "Popen", _uncontained_launch)

    app._run_subprocess_command("apply", ["m.x_f__mutmut_1"])

    # Anchored at line start: the fail-closed notice is the whole line,
    # not a substring hidden inside other output.
    assert re.search(
        r"(?m)^refusing to start an uncontained child: no Job Object available$",
        capsys.readouterr().out,
    )
    assert input_calls == [(_RETURN_PROMPT,)]
    assert refreshed == ["read", "status", "files"]


@pytest.mark.parametrize(
    ("action", "command", "expected_args"),
    [
        ("action_retest_mutant", "run", ["m.x_f__mutmut_1"]),
        ("action_retest_function", "run", ["m.x_f__mutmut_*"]),
        ("action_retest_module", "run", ["m.*"]),
        ("action_apply_mutant", "apply", ["m.x_f__mutmut_1"]),
        ("action_view_tests", "tests-for-mutant", ["m.x_f__mutmut_1"]),
    ],
)
def test_binding_actions_route_through_contained_launcher(
    browser: tuple[ResultBrowser, list[str], list[tuple[object, ...]]],
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    command: str,
    expected_args: list[str],
) -> None:
    """All five key bindings (r/f/m/a/t) launch through the contained launcher."""
    app, _refreshed, _input_calls = browser
    launched: list[list[str]] = []

    def fake_launcher(cmd: list[str]) -> int:
        launched.append(list(cmd))
        return 0

    monkeypatch.setattr("mutmut_win.browser.run_foreground_contained", fake_launcher, raising=False)
    monkeypatch.setattr(app, "_get_selected_mutant_name", lambda: "m.x_f__mutmut_1")
    monkeypatch.setattr(subprocess, "run", _uncontained_launch)
    monkeypatch.setattr(subprocess, "Popen", _uncontained_launch)
    # M-058: the 'm' binding derives its scope from the metadata mapping
    # and is refused without one — provide a normal-module mapping so this
    # test keeps pinning the LAUNCHER routing for all five bindings.
    _load_source_state(app, {"src\\m.py": ["m.x_f__mutmut_1"]})

    getattr(app, action)()

    assert launched == [[sys.executable, "-m", "mutmut_win", command, *expected_args]]


# ----------------------------------------------------------------------
# M-058 / BC-065: action_retest_module scope via exact name mapping
# ----------------------------------------------------------------------

_INIT_FILE = "src\\my_lib\\__init__.py"
_SUB_FILE = "src\\my_lib\\sub.py"
_TOP_FILE = "src\\mod.py"

_INIT_NAMES = ["my_lib.x_f__mutmut_1", "my_lib.x_g__mutmut_1"]
_SUB_NAME = "my_lib.sub.x_h__mutmut_1"
_TOP_NAME = "mod.x_k__mutmut_1"


@pytest.fixture
def retest_browser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]]:
    """A ResultBrowser reduced to the M-058 scope layer.

    ``_run_subprocess_command`` and ``notify`` are replaced by recorders
    (no child process, no running Textual app required — ``notify`` may
    otherwise depend on an active app).  Selection starts as ``None``;
    tests point ``_get_selected_mutant_name`` at the mutant under test.
    """
    app = ResultBrowser(db_path=tmp_path / "absent.sqlite")
    launched: list[tuple[str, list[str]]] = []
    notifications: list[dict[str, object]] = []
    monkeypatch.setattr(
        app, "_run_subprocess_command", lambda command, args: launched.append((command, list(args)))
    )
    monkeypatch.setattr(
        app,
        "notify",
        lambda message, **kwargs: notifications.append({"message": message, **kwargs}),
    )
    monkeypatch.setattr(app, "_get_selected_mutant_name", lambda: None)
    return app, launched, notifications


def _load_source_state(
    app: ResultBrowser,
    files: dict[str, list[str]],
) -> None:
    """Install ``_source_data``/``_path_by_name`` like ``_read_data`` would."""
    app._source_data = {
        path: (SourceFileMutationData(path=path, exit_code_by_key=dict.fromkeys(names)), {})
        for path, names in files.items()
    }
    app._path_by_name = {name: path for path, names in files.items() for name in names}


def test_retest_module_package_init_passes_exact_file_mutants(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
) -> None:
    """An __init__ mutant retests exactly that file's mutants — no submodules.

    Pre-fix red: the guessed pattern ``my_lib.*`` crossed the dots and
    also selected ``my_lib.sub.x_h__mutmut_1`` (and every deeper module).
    """
    app, launched, _notifications = retest_browser
    _load_source_state(app, {_INIT_FILE: list(_INIT_NAMES), _SUB_FILE: [_SUB_NAME]})
    app._get_selected_mutant_name = lambda: _INIT_NAMES[0]  # type: ignore[method-assign]

    app.action_retest_module()

    assert launched == [("run", sorted(_INIT_NAMES))]
    # The effective `run` selection (exact names, run through the real
    # matcher) is exactly the __init__ file's mutants.
    all_names = [*_INIT_NAMES, _SUB_NAME]
    assert set(match_mutant_names(launched[0][1], all_names)) == set(_INIT_NAMES)


def test_retest_module_package_init_includes_names_outside_current_plan(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
) -> None:
    """Snapshot mode: the __init__ list covers the WHOLE file, not just the plan.

    ``_read_data`` fills ``_path_by_name`` only for names of the current
    run, but the explicit list is built from the meta file's full
    ``exit_code_by_key`` — a module retest wants every mutant of the
    file, including ones outside the persisted plan.
    """
    app, launched, _notifications = retest_browser
    names = [*_INIT_NAMES, "my_lib.x_z__mutmut_1"]
    _load_source_state(app, {_INIT_FILE: names})
    app._current_run_names = {_INIT_NAMES[0]}  # snapshot restricted to one name
    app._get_selected_mutant_name = lambda: _INIT_NAMES[0]  # type: ignore[method-assign]

    app.action_retest_module()

    assert launched == [("run", sorted(names))]


def test_retest_module_shows_selected_module(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
) -> None:
    """The selected module is displayed before the retest starts (both shapes)."""
    app, launched, notifications = retest_browser
    _load_source_state(app, {_INIT_FILE: list(_INIT_NAMES), _SUB_FILE: [_SUB_NAME]})

    app._get_selected_mutant_name = lambda: _INIT_NAMES[0]  # type: ignore[method-assign]
    app.action_retest_module()
    app._get_selected_mutant_name = lambda: _SUB_NAME  # type: ignore[method-assign]
    app.action_retest_module()

    assert len(launched) == 2
    init_display, module_display = notifications[0], notifications[1]
    assert _INIT_FILE in str(init_display["message"])
    assert init_display.get("markup") is False  # paths may contain markup metacharacters
    assert _SUB_FILE in str(module_display["message"])
    assert module_display.get("markup") is False


@pytest.mark.parametrize(
    ("file_path", "mutant_name", "expected_pattern"),
    [
        (_SUB_FILE, _SUB_NAME, "my_lib.sub.*"),
        (_TOP_FILE, _TOP_NAME, "mod.*"),  # top-level module without a package
    ],
    ids=["subpackage-module", "top-level-module"],
)
def test_retest_module_normal_module_keeps_pattern(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
    file_path: str,
    mutant_name: str,
    expected_pattern: str,
) -> None:
    """Normal modules keep the short pattern (also catches new mutants)."""
    app, launched, _notifications = retest_browser
    _load_source_state(app, {file_path: [mutant_name]})
    app._get_selected_mutant_name = lambda: mutant_name  # type: ignore[method-assign]

    app.action_retest_module()

    assert launched == [("run", [expected_pattern])]


def test_retest_module_refuses_unmapped_name(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
) -> None:
    """DB-only / unmapped name -> refused with a warning, never a guessed scope.

    Without a mapping it is undecidable whether the name comes from a
    package ``__init__`` — fail closed instead of guessing (M-058 = A).
    """
    app, launched, notifications = retest_browser
    _load_source_state(app, {_INIT_FILE: list(_INIT_NAMES), _SUB_FILE: [_SUB_NAME]})
    app._path_by_name = {}  # name exists only in the DB — no metadata mapping
    app._get_selected_mutant_name = lambda: "my_lib.orphan__mutmut_1"  # type: ignore[method-assign]

    app.action_retest_module()

    assert launched == []
    assert len(notifications) == 1
    refused = notifications[0]
    assert refused.get("severity") == "warning"
    assert refused.get("markup") is False
    assert "my_lib.orphan__mutmut_1" in str(refused["message"])


def test_retest_module_refuses_stale_mapping(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
) -> None:
    """A name whose mapped file left ``_source_data`` (stale) is refused."""
    app, launched, notifications = retest_browser
    _load_source_state(app, {_INIT_FILE: list(_INIT_NAMES)})
    app._path_by_name = {"my_lib.x_f__mutmut_1": "src\\my_lib\\gone.py"}
    app._get_selected_mutant_name = lambda: "my_lib.x_f__mutmut_1"  # type: ignore[method-assign]

    app.action_retest_module()

    assert launched == []
    assert len(notifications) == 1
    assert notifications[0].get("severity") == "warning"
    assert "my_lib.x_f__mutmut_1" in str(notifications[0]["message"])


def test_retest_module_refuses_empty_init_name_list(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
) -> None:
    """An empty explicit list MUST NOT launch — ``run`` without names is a FULL run."""
    app, launched, notifications = retest_browser
    _load_source_state(app, {_INIT_FILE: [], _SUB_FILE: [_SUB_NAME]})
    app._path_by_name = {"my_lib.x_f__mutmut_1": _INIT_FILE}
    app._get_selected_mutant_name = lambda: "my_lib.x_f__mutmut_1"  # type: ignore[method-assign]

    app.action_retest_module()

    assert launched == []
    assert notifications[0].get("severity") == "warning"


def test_retest_module_refuses_overlong_command_line(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
) -> None:
    """An __init__ name list beyond the CreateProcessW limit is refused.

    Explicit names travel on one Windows command line (list2cmdline →
    CreateProcessW, 32 767 chars incl. NUL — M-057 launcher).  Refusing
    beats a partial retest that dies at process creation.  Pre-fix red:
    there was no length guard at all.
    """
    app, launched, notifications = retest_browser
    big_names = sorted(f"my_lib.x_{'f' * 40}_{i}__mutmut_1" for i in range(800))
    _load_source_state(app, {_INIT_FILE: big_names})
    app._get_selected_mutant_name = lambda: big_names[0]  # type: ignore[method-assign]
    command_line = subprocess.list2cmdline([sys.executable, "-m", "mutmut_win", "run", *big_names])
    assert len(command_line) > 32767  # the probe really is beyond the kernel limit

    app.action_retest_module()

    assert launched == []
    assert len(notifications) == 1
    refused = notifications[0]
    assert refused.get("severity") == "warning"
    assert refused.get("markup") is False
    assert "mutmut-win run" in str(refused["message"])


@pytest.mark.parametrize("at_limit", [True, False], ids=["exactly-at-limit", "one-over-limit"])
def test_retest_module_command_line_limit_boundary(
    retest_browser: tuple[ResultBrowser, list[tuple[str, list[str]]], list[dict[str, object]]],
    at_limit: bool,
) -> None:
    """Knapp unter/über der Grenze: exactly at the limit launches, +1 refuses."""
    from mutmut_win.browser import _RETEST_COMMAND_LINE_LIMIT

    def cmdline_len(name: str) -> int:
        return len(subprocess.list2cmdline([sys.executable, "-m", "mutmut_win", "run", name]))

    base = "my_lib.x_f__mutmut_1"
    padding = _RETEST_COMMAND_LINE_LIMIT - cmdline_len(base)
    assert padding > 0  # the probe stays tunable on any interpreter path length
    name = base + "f" * (padding + (1 if at_limit is False else 0))
    assert cmdline_len(name) == _RETEST_COMMAND_LINE_LIMIT + (0 if at_limit else 1)

    app, launched, notifications = retest_browser
    _load_source_state(app, {_INIT_FILE: [name]})
    app._get_selected_mutant_name = lambda: name  # type: ignore[method-assign]

    app.action_retest_module()

    if at_limit:
        assert launched == [("run", [name])]
        assert notifications[0].get("severity") != "warning"
    else:
        assert launched == []
        assert notifications[0].get("severity") == "warning"


def test_retest_module_package_init_never_selects_submodule_mutants() -> None:
    """Property: __init__ retest arguments never select submodule mutants.

    Hypothesis drives the submodule names — whatever siblings the package
    has, the explicit ``__init__`` list selects exactly that file's
    mutants (no fixture: @given must not combine with function-scoped
    fixtures).
    """
    from pathlib import Path

    from hypothesis import given
    from hypothesis import strategies as st

    @given(
        st.lists(
            st.from_regex("[a-z][a-z0-9_]{0,8}", fullmatch=True),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    def check(submodules: list[str]) -> None:
        app = ResultBrowser(db_path=Path("N:/absent.sqlite"))
        sub_names = [f"my_lib.{s}.x_h__mutmut_1" for s in submodules]
        files: dict[str, list[str]] = {_INIT_FILE: list(_INIT_NAMES)}
        for sub_name, module in zip(sub_names, submodules, strict=True):
            files[f"src\\my_lib\\{module}.py"] = [sub_name]
        _load_source_state(app, files)
        launched: list[tuple[str, list[str]]] = []
        app._run_subprocess_command = (  # type: ignore[method-assign]
            lambda command, args: launched.append((command, list(args)))
        )
        app.notify = lambda _message, **_kwargs: None  # type: ignore[method-assign]
        app._get_selected_mutant_name = lambda: _INIT_NAMES[0]  # type: ignore[method-assign]

        app.action_retest_module()

        candidates = [*_INIT_NAMES, *sub_names]
        selected = match_mutant_names(launched[0][1], candidates)
        assert set(selected) == set(_INIT_NAMES)

    check()
