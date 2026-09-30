"""Browser TUI action harness tests (M-057 / issue #158).

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

    getattr(app, action)()

    assert launched == [[sys.executable, "-m", "mutmut_win", command, *expected_args]]
