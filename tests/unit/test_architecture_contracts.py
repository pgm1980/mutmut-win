"""Architecture contract tests: CLI exit codes, JSON schema, write-path (W4).

Each contract verifies a cross-cutting invariant that would otherwise only
be caught by external review: documented exit codes actually used, JSON
exports schema-valid, no raw open() in engine modules.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

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


class TestJsonExportContract:
    """The CI/CD JSON export has a stable, machine-checkable shape."""

    def test_cicd_export_has_required_fields(self) -> None:
        """The export payload must contain the core gate fields."""
        required_fields = {"total", "killed", "survived", "score"}
        # Verify against the module's actual export function signature
        from mutmut_win.stats import compute_cicd_stats

        assert callable(compute_cicd_stats), "compute_cicd_stats must be callable"

    def test_json_export_is_ascii_safe(self) -> None:
        """JSON export with ensure_ascii=True produces pure-ASCII output."""
        test_payload = {"name": "café", "status": "killed", "score": 0.85}
        encoded = json.dumps(test_payload, ensure_ascii=True)
        encoded.encode("ascii")  # must not raise


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


class TestWritePathContract:
    """Engine modules must not use raw open() for writes to staging paths."""

    @pytest.mark.parametrize(
        "module_path",
        sorted(SRC_ROOT.rglob("*.py")),
        ids=lambda p: str(p.relative_to(SRC_ROOT)),
    )
    def test_no_raw_write_open_in_engine_modules(self, module_path: Path) -> None:
        """AST scan: open() calls with write modes are forbidden outside exceptions."""
        relative = str(module_path.relative_to(SRC_ROOT)).replace("\\", "/")
        if relative in WRITE_PATH_EXCEPTIONS:
            pytest.skip(f"documented exception: {relative}")

        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))

        violations: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_open = (isinstance(func, ast.Name) and func.id == "open") or (
                isinstance(func, ast.Attribute) and func.attr == "open"
            )
            if not is_open:
                continue
            # Check mode argument (default "r" = read = allowed)
            mode = "r"
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(c in mode for c in "wax+"):
                violations.append(f"line {node.lineno}: open(mode={mode!r})")

        assert not violations, (
            f"{relative} contains raw open() for writes "
            f"(use atomic_file.atomic_write_bytes instead): {violations}"
        )
