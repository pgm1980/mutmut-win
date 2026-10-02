"""The name-consistency gate proves runtime mutant-name dispatch (M-053).

The forced-fail run proves only that the trampoline wrapper is installed
and reads ``MUTANT_UNDER_TEST``: its ``fail`` sentinel terminates inside
the trampoline BEFORE the name-prefix dispatch.  A layout whose runtime
import names diverge from the generated mutant names — for example a
mutated tree imported through an ``extra_paths`` root that
``get_mutant_name`` does not strip — would therefore dispatch every task
to the ORIGINAL function and report silent survivors.

The stats run records the actual runtime keys
(``orig.__module__ + '.' + orig.__name__``); the gate compares them with
the function keys of every generated mutant and fails closed on a provable
dotted-suffix divergence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.config import MutmutConfig
from mutmut_win.db import load_current_run
from mutmut_win.exceptions import MutantNameDispatchError
from mutmut_win.models import MutationTask, TaskCompleted
from mutmut_win.orchestrator import MutationOrchestrator, _verify_runtime_mutant_names
from mutmut_win.stats import MutmutStats, RunBasisEvidence

if TYPE_CHECKING:
    from pathlib import Path

_LIB_MOD = (
    "def double(value):\n    return 2 * value\n\n\ndef halve(value):\n    return value // 2\n"
)


def _stats(keys: dict[str, set[str]]) -> MutmutStats:
    """Build stats whose mapping carries exactly the given runtime keys."""
    return MutmutStats(
        tests_by_mangled_function_name=keys,
        duration_by_test={node: 0.05 for nodes in keys.values() for node in nodes},
    )


# ---------------------------------------------------------------------------
# _verify_runtime_mutant_names (pure helper)
# ---------------------------------------------------------------------------


class TestVerifyRuntimeMutantNamesUnit:
    def test_runtime_key_missing_a_stripped_root_fails_closed(self) -> None:
        # The extra_paths layout of the original finding: generation names
        # carry 'lib.' while the runtime import name does not.
        generated = {
            "lib.pkg.mod.x_double__mutmut_1",
            "lib.pkg.mod.x_double__mutmut_2",
        }
        stats = _stats({"pkg.mod.x_double": {"tests/test_mod.py::test_double"}})
        with pytest.raises(MutantNameDispatchError) as excinfo:
            _verify_runtime_mutant_names(generated, stats)
        message = str(excinfo.value)
        assert "pkg.mod.x_double" in message
        assert "lib.pkg.mod.x_double" in message

    def test_runtime_key_with_extra_prefix_fails_closed(self) -> None:
        # The documented get_mutant_name limitation direction: the tests
        # import 'src.pkg.mod' while the mutant names strip 'src.'.
        generated = {"pkg.mod.x_double__mutmut_1"}
        stats = _stats({"src.pkg.mod.x_double": {"tests/test_mod.py::test_double"}})
        with pytest.raises(MutantNameDispatchError, match=r"src\.pkg\.mod\.x_double"):
            _verify_runtime_mutant_names(generated, stats)

    def test_matching_keys_pass(self) -> None:
        generated = {"lib.pkg.mod.x_double__mutmut_1"}
        stats = _stats({"lib.pkg.mod.x_double": {"tests/test_mod.py::test_double"}})
        _verify_runtime_mutant_names(generated, stats)

    def test_empty_mapping_passes(self) -> None:
        # No recorded hits — no runtime proof possible, no gate decision.
        _verify_runtime_mutant_names({"lib.pkg.mod.x_double__mutmut_1"}, _stats({}))

    def test_empty_generation_set_passes(self) -> None:
        _verify_runtime_mutant_names(set(), _stats({"pkg.mod.x_double": {"t"}}))

    def test_double_import_only_warns(self, capsys: pytest.CaptureFixture[str]) -> None:
        # The module is imported under two names (e.g. via extra_paths AND
        # the project root); dispatch for the GENERATED key was observed at
        # runtime, so the suffix twin is an alias, not a dead dispatch.
        generated = {"lib.pkg.mod.x_double__mutmut_1"}
        stats = _stats(
            {
                "pkg.mod.x_double": {"tests/test_a.py::test_a"},
                "lib.pkg.mod.x_double": {"tests/test_b.py::test_b"},
            }
        )
        _verify_runtime_mutant_names(generated, stats)
        out = capsys.readouterr().out
        assert "Warning" in out
        assert "pkg.mod.x_double" in out

    def test_unrelated_cache_key_is_ignored(self, capsys: pytest.CaptureFixture[str]) -> None:
        # A cached runtime key with NO dotted-suffix relation to any
        # generated key proves nothing (cache old-keys); it must neither
        # abort the run nor warn.
        generated = {"lib.pkg.mod.x_double__mutmut_1"}
        stats = _stats({"other.mod.x_gone": {"tests/old.py::test_old"}})
        _verify_runtime_mutant_names(generated, stats)
        assert capsys.readouterr().out == ""

    def test_malformed_mutant_name_is_ignored(self) -> None:
        # Names without a well-formed numeric '__mutmut_' suffix cannot be
        # trampoline-dispatched; the gate skips them instead of crashing
        # (decision documented in the gate docstring).
        _verify_runtime_mutant_names({"not.a.mutant.name"}, _stats({"not.a.mutant.name": {"t"}}))

    def test_partial_suffix_without_component_boundary_is_no_divergence(self) -> None:
        # 'x_double' is a substring of 'lib.pkg.mod.x_double' but NOT a
        # dotted suffix — it cannot be a runtime module key of that module.
        generated = {"lib.pkg.mod.x_double__mutmut_1"}
        stats = _stats({"ble": {"t"}})
        _verify_runtime_mutant_names(generated, stats)

    def test_message_lists_at_most_five_example_pairs(self) -> None:
        generated = {f"lib.pkg{i}.mod.x_f{i}__mutmut_1" for i in range(7)}
        stats = _stats({f"pkg{i}.mod.x_f{i}": {f"tests/test_{i}.py::test_{i}"} for i in range(7)})
        with pytest.raises(MutantNameDispatchError) as excinfo:
            _verify_runtime_mutant_names(generated, stats)
        example_lines = [line for line in str(excinfo.value).splitlines() if "!=" in line]
        assert len(example_lines) == 5


_IDENTIFIERS = (
    st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True)
    .filter(lambda s: "__mutmut_" not in s)
    .filter(lambda s: not s.startswith("x_"))
)


class TestVerifyRuntimeMutantNamesProperty:
    @settings(max_examples=50, deadline=None)
    @given(
        root=_IDENTIFIERS,
        module=st.lists(_IDENTIFIERS, min_size=1, max_size=4),
        func=_IDENTIFIERS,
    )
    def test_shorter_runtime_key_always_fails(
        self, root: str, module: list[str], func: str
    ) -> None:
        generated_key = ".".join([root, *module, f"x_{func}"])
        runtime_key = ".".join([*module, f"x_{func}"])
        generated = {f"{generated_key}__mutmut_1"}
        stats = _stats({runtime_key: {"tests/test_x.py::test_x"}})
        with pytest.raises(MutantNameDispatchError):
            _verify_runtime_mutant_names(generated, stats)

    @settings(max_examples=50, deadline=None)
    @given(
        root=_IDENTIFIERS,
        module=st.lists(_IDENTIFIERS, min_size=1, max_size=4),
        func=_IDENTIFIERS,
    )
    def test_matching_runtime_key_never_fails(
        self, root: str, module: list[str], func: str
    ) -> None:
        generated_key = ".".join([root, *module, f"x_{func}"])
        stats = _stats({generated_key: {"tests/test_x.py::test_x"}})
        _verify_runtime_mutant_names({f"{generated_key}__mutmut_1"}, stats)

    @settings(max_examples=50, deadline=None)
    @given(
        root=_IDENTIFIERS,
        module=st.lists(_IDENTIFIERS, min_size=1, max_size=4),
        func=_IDENTIFIERS,
    )
    def test_observed_generated_key_never_fails_despite_alias(
        self, root: str, module: list[str], func: str
    ) -> None:
        # The suffix-related generated key itself was observed at runtime
        # (double import): warning, never an abort.
        generated_key = ".".join([root, *module, f"x_{func}"])
        runtime_key = ".".join([*module, f"x_{func}"])
        stats = _stats(
            {
                runtime_key: {"tests/test_a.py::test_a"},
                generated_key: {"tests/test_b.py::test_b"},
            }
        )
        _verify_runtime_mutant_names({f"{generated_key}__mutmut_1"}, stats)


# ---------------------------------------------------------------------------
# Pipeline: the gate runs after step 3 and before any verdict producer
# ---------------------------------------------------------------------------


def _project(tmp_path: Path) -> None:
    (tmp_path / "lib" / "pkg").mkdir(parents=True)
    (tmp_path / "lib" / "pkg" / "mod.py").write_text(_LIB_MOD, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(
        "def test_shapes():\n    assert True\n",
        encoding="utf-8",
    )


def _killing_executor() -> MagicMock:
    executor = MagicMock()
    captured: list[MutationTask] = []

    def fake_start(tasks: list[MutationTask]) -> None:
        captured.clear()
        captured.extend(tasks)

    def fake_events() -> Any:
        return iter(
            TaskCompleted(mutant_name=task.mutant_name, worker_pid=1, exit_code=1, duration=0.05)
            for task in captured
        )

    executor.start.side_effect = fake_start
    executor.get_events.side_effect = fake_events
    executor.captured = captured
    return executor


def _runner() -> MagicMock:
    runner = MagicMock()
    runner.run_clean_test.return_value = 0
    runner.run_stats.return_value = None
    runner.collect_tests.return_value = []
    runner.run_forced_fail.return_value = 1
    runner.last_forced_fail_attributed = True
    return runner


def _patch_stats(monkeypatch: pytest.MonkeyPatch, keys: dict[str, set[str]]) -> None:
    import mutmut_win.orchestrator as orch_mod

    def collected_stats(_runner: object, **kwargs: object) -> MutmutStats:
        result = _stats(keys)
        result.context_fingerprint = str(kwargs["context_fingerprint"])
        return result

    monkeypatch.setattr(orch_mod, "collect_or_load_stats", collected_stats)
    monkeypatch.setattr(
        orch_mod,
        "build_stats_context_fingerprint",
        lambda *_args, **_kwargs: "b" * 64,
    )
    monkeypatch.setattr(
        orch_mod,
        "build_run_basis_evidence",
        lambda *_args, **_kwargs: RunBasisEvidence("a" * 64, True),
    )


class TestPipelineFailsClosedBeforeDispatch:
    @pytest.fixture(autouse=True)
    def _cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path)

    def _orchestrate(
        self, tmp_path: Path, executor: MagicMock, **kwargs: Any
    ) -> MutationOrchestrator:
        return MutationOrchestrator(
            MutmutConfig(paths_to_mutate=["lib"], tests_dir=["tests/"], max_children=1),
            runner=_runner(),
            executor=executor,
            db_path=tmp_path / "gate.sqlite",
            **kwargs,
        )

    def test_divergent_runtime_key_aborts_before_any_dispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulated extra_paths layout: generation produces
        # 'lib.pkg.mod.x_double__mutmut_N' while the runtime import name
        # would be 'pkg.mod' (mutants/lib on PYTHONPATH).
        _patch_stats(monkeypatch, {"pkg.mod.x_double": {"tests/test_mod.py::test_double"}})
        executor = _killing_executor()
        orch = self._orchestrate(tmp_path, executor)
        with pytest.raises(MutantNameDispatchError) as excinfo:
            orch.run()
        message = str(excinfo.value)
        assert "pkg.mod.x_double" in message
        assert "lib.pkg.mod.x_double" in message
        assert executor.start.call_count == 0
        current = load_current_run(tmp_path / "gate.sqlite")
        assert current is not None
        assert current.status == "failed"

    def test_matching_runtime_key_dispatches_normally(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_stats(monkeypatch, {"lib.pkg.mod.x_double": {"tests/test_mod.py::test_double"}})
        executor = _killing_executor()
        orch = self._orchestrate(tmp_path, executor)
        summary = orch.run()
        assert executor.start.call_count == 1
        assert executor.captured
        assert summary.killed == len(executor.captured)

    def test_empty_mapping_dispatches_normally(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_stats(monkeypatch, {})
        executor = _killing_executor()
        orch = self._orchestrate(tmp_path, executor)
        orch.run()
        assert executor.start.call_count == 1

    def test_gate_uses_the_unfiltered_generation_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Partial run via --mutant-names selecting only 'halve': the
        # divergent 'double' key is provable only through the COMPLETE
        # generation set, not the filtered tasks.
        _patch_stats(monkeypatch, {"pkg.mod.x_double": {"tests/test_mod.py::test_double"}})
        executor = _killing_executor()
        orch = self._orchestrate(
            tmp_path, executor, mutant_names=("lib.pkg.mod.x_halve__mutmut_1",)
        )
        with pytest.raises(MutantNameDispatchError):
            orch.run()
        assert executor.start.call_count == 0
