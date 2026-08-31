"""Tests for the trampoline hit-recording kernel module (Issue #107).

A4-QX-001 (~1.4s measured): generated mutant files imported
``record_trampoline_hit`` from ``mutmut_win.__main__``, which statically
pulls ``cli`` — click + textual/rich + the orchestrator chain — into EVERY
user test process during stats runs.  Inside the trampolined build artifact
the same edge (band-3 module -> __main__ -> cli) broke the import-linter
layer contract, forcing Sprint 32 to skip the architecture gate in
mutants/ (the documented QX-001 marker).

The recording now lives in ``mutmut_win.hit_recording``: a bottom-band
kernel module whose module level imports NOTHING of mutmut_win (lazy
``_state``/``config`` inside the functions) — the artifact's import chain
is feather-light and stays inside the bottom band, so the architecture
gate holds everywhere again and the QX-001 skip marker is REMOVED.

QX-020 slice: the per-hit cost was the heavy first import, not the
steady-state ``sys.modules`` lookup — with the light chain the late-import
inside the trampoline body stays (deliberate cut: the template keeps the
upstream-mutmut property that plain runs never import mutmut_win at all).
"""

from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from mutmut_win import _state
from mutmut_win._state import _reset_globals
from mutmut_win.hit_recording import _get_max_stack_depth, record_trampoline_hit
from mutmut_win.trampoline import trampoline_impl


class TestTemplateImportsTheKernel:
    def test_stats_branch_imports_hit_recording(self) -> None:
        assert "from mutmut_win.hit_recording import record_trampoline_hit" in trampoline_impl

    def test_fail_branch_imports_exceptions_directly(self) -> None:
        # The exception always lived in the bottom band — the template just
        # took the heavy __main__ detour to reach it.
        assert (
            "from mutmut_win.exceptions import MutmutProgrammaticFailException" in trampoline_impl
        )

    def test_template_never_touches_dunder_main(self) -> None:
        # The whole point of QX-001: no generated file may pull the CLI
        # chain via __main__.
        assert "__main__" not in trampoline_impl


class TestKernelImportIsLight:
    def test_import_pulls_no_cli_chain_and_is_fast(self) -> None:
        # Measured in a FRESH interpreter — in this process mutmut_win is
        # long loaded. The sys.modules check is the real QX-001 proof; the
        # duration bound is regression protection (generous for cold CI).
        probe = (
            "import json, sys, time\n"
            "t0 = time.perf_counter()\n"
            "import mutmut_win.hit_recording\n"
            "duration = time.perf_counter() - t0\n"
            "heavy = [m for m in ('click', 'textual', 'rich', 'pytest')\n"
            "         if any(k == m or k.startswith(m + '.') for k in sys.modules)]\n"
            "print(json.dumps({'duration': duration, 'heavy': heavy}))\n"
        )
        result = subprocess.run(  # noqa: S603 — fully controlled command
            [sys.executable, "-c", probe],
            capture_output=True,
            encoding="utf-8",
            timeout=60,
            check=True,
        )
        report = json.loads(result.stdout.strip().splitlines()[-1])
        assert report["heavy"] == [], f"kernel import pulled heavy modules: {report['heavy']}"
        assert report["duration"] < 1.0, f"kernel import took {report['duration']:.3f}s"


class TestRecordTrampolineHit:
    """Behaviour moved verbatim from __main__ (patches must target the
    kernel module now — record_trampoline_hit resolves its module-local
    ``_get_max_stack_depth``, not the __main__ re-export)."""

    def test_records_hit_when_unlimited(self) -> None:
        _reset_globals()
        with patch("mutmut_win.hit_recording._get_max_stack_depth", return_value=-1):
            record_trampoline_hit("x_my_func")
        assert "x_my_func" in _state._stats
        _reset_globals()

    def test_discards_hit_when_depth_exhausted_without_test_frame(self) -> None:
        _reset_globals()
        with patch("mutmut_win.hit_recording._get_max_stack_depth", return_value=1):
            record_trampoline_hit("x_should_be_discarded")
        # No pytest/unittest frame within 1 frame of the recorder itself.
        assert "x_should_be_discarded" not in _state._stats
        _reset_globals()

    def test_discards_hit_when_real_stack_ends_before_depth_limit(self) -> None:
        _reset_globals()
        short_frame = SimpleNamespace(
            # A user filename containing the substring "pytest" is not itself
            # a pytest framework frame.
            f_code=SimpleNamespace(co_filename="C:/project/pytest_helpers.py"),
            f_back=None,
        )
        with (
            patch("mutmut_win.hit_recording._get_max_stack_depth", return_value=10),
            patch("inspect.currentframe", return_value=short_frame),
        ):
            record_trampoline_hit("x_short_stack")

        assert "x_short_stack" not in _state._stats
        _reset_globals()

    def test_records_hit_when_a_real_pytest_package_frame_is_found(self) -> None:
        _reset_globals()
        pytest_frame = SimpleNamespace(
            f_code=SimpleNamespace(co_filename="C:/venv/Lib/site-packages/_pytest/runner.py"),
            f_back=None,
        )
        source_frame = SimpleNamespace(
            f_code=SimpleNamespace(co_filename="C:/project/service.py"),
            f_back=pytest_frame,
        )
        with (
            patch("mutmut_win.hit_recording._get_max_stack_depth", return_value=2),
            patch("inspect.currentframe", return_value=source_frame),
        ):
            record_trampoline_hit("x_framework_stack")

        assert "x_framework_stack" in _state._stats
        _reset_globals()

    def test_get_max_stack_depth_uses_the_state_cache(self) -> None:
        _reset_globals()
        _state._cached_max_stack_depth = 5
        assert _get_max_stack_depth() == 5
        _reset_globals()


class TestDunderMainBwcReExports:
    def test_old_staging_trees_still_resolve_via_dunder_main(self) -> None:
        # Trees generated before v2.11.0 import from __main__ — the
        # re-export must stay identical to the kernel function (the config
        # fingerprint regenerates them on the next config change, but a
        # plain package upgrade does not touch the staging tree).
        import mutmut_win.__main__ as dunder_main

        assert dunder_main.record_trampoline_hit is record_trampoline_hit
