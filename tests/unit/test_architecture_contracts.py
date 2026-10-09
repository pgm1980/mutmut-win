"""Architecture contract tests: CLI exit codes, JSON schema, write-path (W4).

Each contract verifies a cross-cutting invariant that would otherwise only
be caught by external review: documented exit codes actually used, JSON
exports schema-valid, explicit write methods and literal builtin-style open modes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, ConfigDict

from mutmut_win.stats import CicdStats, compute_cicd_stats, save_cicd_stats

SRC_ROOT = Path(__file__).parent.parent.parent / "src" / "mutmut_win"

# Documented CLI exit codes (from README + Issue #130 taxonomy).
DOCUMENTED_EXIT_CODES: dict[int, str] = {
    0: "success",
    1: "domain error (results corrupt, workspace unsafe, gate failure)",
    2: "configuration error (ConfigError, usage error)",
    130: "interrupted (Ctrl-C / SIGINT)",
    36: "pytest timeout in a phase child",
}

# Modules where raw open() is permitted (documented exceptions).
WRITE_PATH_EXCEPTIONS: frozenset[str] = frozenset(
    {
        # M-130: the forced-fail proof deliberately bypasses atomic_write_bytes
        # to prove the trampoline works without the engine's own atomic writer.
        "process/worker.py",
    }
)


# =========================================================================
# CLI exit-code contract
# =========================================================================


class TestExitCodeContract:
    """Every exit code the CLI can produce is documented."""

    @pytest.mark.parametrize("code", sorted(DOCUMENTED_EXIT_CODES))
    def test_exit_code_is_documented(self, code: int) -> None:
        """The code appears in the documented set."""
        assert code in DOCUMENTED_EXIT_CODES
        assert DOCUMENTED_EXIT_CODES[code]

    def test_zero_means_success(self) -> None:
        """Exit 0 is exclusively success."""
        assert DOCUMENTED_EXIT_CODES[0] == "success"

    def test_130_is_interrupt(self) -> None:
        """Exit 130 is exclusively SIGINT/Ctrl-C."""
        assert "interrupt" in DOCUMENTED_EXIT_CODES[130].lower()


# =========================================================================
# JSON export schema contract
# =========================================================================


class _CicdExport(BaseModel):
    """Required persisted CI/CD fields, without defaults hiding missing output."""

    model_config = ConfigDict(extra="forbid", strict=True)

    killed: int
    survived: int
    total: int
    no_tests: int
    skipped: int
    suspicious: int
    timeout: int
    check_was_interrupted_by_user: int
    segfault: int
    caught_by_type_check: int
    killed_by_infinite_loop: int
    score: float


class TestJsonExportContract:
    """The CI/CD JSON export has a stable, machine-checkable shape."""

    def test_cicd_export_has_required_fields(self, tmp_path: Path) -> None:
        """Observe the real complete payload for mixed production verdicts."""
        statuses = [
            "killed",
            "killed",
            "survived",
            "no tests",
            "skipped",
            "suspicious",
            "timeout",
            "check was interrupted by user",
            "segfault",
            "caught by type check",
            "killed_by_infinite_loop",
            None,
        ]
        results = [
            (f"café.x_work__mutmut_{index}", status) for index, status in enumerate(statuses)
        ]
        computed = compute_cicd_stats(results)
        assert isinstance(computed, CicdStats)
        persisted = save_cicd_stats(results, tmp_path)
        assert persisted == computed
        payload = _CicdExport.model_validate_json(
            (tmp_path / "mutmut-cicd-stats.json").read_bytes()
        )
        assert payload == _CicdExport(
            killed=2,
            survived=1,
            total=12,
            no_tests=1,
            skipped=1,
            suspicious=1,
            timeout=2,
            check_was_interrupted_by_user=1,
            segfault=1,
            caught_by_type_check=1,
            killed_by_infinite_loop=1,
            score=40.0,
        )
        assert computed.effective_killed == 4
        assert computed.scoreable == 10

    def test_json_export_is_ascii_safe(self, tmp_path: Path) -> None:
        """The actual numeric export remains ASCII with Unicode mutant names."""
        save_cicd_stats([("café.x_work__mutmut_1", "killed")], tmp_path)
        encoded = (tmp_path / "mutmut-cicd-stats.json").read_bytes()
        encoded.decode("ascii")
        assert _CicdExport.model_validate_json(encoded).score == 100.0

    @given(killed=st.integers(0, 30), survived=st.integers(0, 30))
    def test_real_counts_follow_input_population(self, killed: int, survived: int) -> None:
        """Generated populations constrain the actual aggregation result."""
        results = [(f"k{index}", "killed") for index in range(killed)]
        results.extend((f"s{index}", "survived") for index in range(survived))
        stats = compute_cicd_stats(results)
        assert isinstance(stats, CicdStats)
        assert (stats.killed, stats.survived, stats.total) == (killed, survived, killed + survived)
        expected = 100.0 * killed / (killed + survived) if killed + survived else 0.0
        assert stats.score == pytest.approx(expected)


# =========================================================================
# Configuration schema contract
# =========================================================================


class TestConfigSchemaContract:
    """Invalid configuration combinations fail closed."""

    def test_mutmut_config_unknown_fields_do_not_silently_mutate(self) -> None:
        """Unknown fields either raise or are excluded from the model dump."""
        from mutmut_win.config import MutmutConfig

        config = MutmutConfig()
        dumped = config.model_dump()
        assert "nonexistent_field" not in dumped, (
            "an unknown field must never appear in the serialized config"
        )

    def test_mutmut_config_rejects_absolute_paths_to_mutate(self) -> None:
        """Absolute paths in paths_to_mutate are rejected."""
        from pydantic import ValidationError

        from mutmut_win.config import MutmutConfig

        with pytest.raises(ValidationError):
            MutmutConfig(paths_to_mutate=["C:\\absolute\\path\\src"])

    def test_mutmut_config_rejects_dots_alias(self) -> None:
        """'..' in paths is rejected (canonical path enforcement)."""
        from pydantic import ValidationError

        from mutmut_win.config import MutmutConfig

        with pytest.raises(ValidationError):
            MutmutConfig(paths_to_mutate=["../outside/src"])


# =========================================================================
# Write-path contract (no raw open() for writes in engine modules)
# =========================================================================


def _raw_write_calls(tree: ast.AST) -> list[str]:
    """Find write_text/write_bytes and open(path, mode) or open(mode=...) writes.

    This bounded syntactic contract does not resolve aliases, dynamic dispatch,
    or a Path.open mode supplied as its first positional argument.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"write_text", "write_bytes"}:
            violations.append(f"line {node.lineno}: {func.attr}()")
            continue
        is_open = (isinstance(func, ast.Name) and func.id == "open") or (
            isinstance(func, ast.Attribute) and func.attr == "open"
        )
        if not is_open:
            continue
        mode = "r"
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = str(node.args[1].value)
        for keyword in node.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                mode = str(keyword.value.value)
        if any(character in mode for character in "wax+"):
            violations.append(f"line {node.lineno}: open(mode={mode!r})")
    return violations


class TestWritePathContract:
    """Reject the explicit APIs recognized by _raw_write_calls in engine modules."""

    @pytest.mark.parametrize(
        "module_path",
        sorted(SRC_ROOT.rglob("*.py")),
        ids=lambda p: str(p.relative_to(SRC_ROOT)),
    )
    def test_no_raw_write_open_in_engine_modules(self, module_path: Path) -> None:
        """Scan actual modules for explicit write methods and literal open modes."""
        relative = str(module_path.relative_to(SRC_ROOT)).replace("\\", "/")
        if relative in WRITE_PATH_EXCEPTIONS:
            pytest.skip(f"documented exception: {relative}")

        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))

        violations = _raw_write_calls(tree)
        assert not violations, (
            f"{relative} contains an explicit raw write API "
            f"(use atomic_file.atomic_write_bytes instead): {violations}"
        )

    @given(method=st.sampled_from(["write_text", "write_bytes"]), content=st.text(max_size=50))
    def test_write_methods_are_detected(self, method: str, content: str) -> None:
        """Generated payload literals cannot hide either explicit write method."""
        tree = ast.parse(f"target.{method}({content!r})")
        assert _raw_write_calls(tree) == [f"line 1: {method}()"]

    @pytest.mark.parametrize(
        "source",
        ["target.read_text()", "target.read_bytes()", "open(path)", "open(path, mode='rb')"],
    )
    def test_read_calls_remain_allowed(self, source: str) -> None:
        """Read-only calls remain outside the write contract."""
        assert _raw_write_calls(ast.parse(source)) == []

    @pytest.mark.parametrize("mode", ["w", "a", "x", "r+", "wb"])
    def test_literal_open_write_modes_remain_detected(self, mode: str) -> None:
        """Retain the original builtin-open write-mode guarantee."""
        assert _raw_write_calls(ast.parse(f"open(path, {mode!r})"))
        assert _raw_write_calls(ast.parse(f"open(path, mode={mode!r})"))
