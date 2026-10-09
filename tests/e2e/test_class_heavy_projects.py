"""Real class-method trampolines that consume validated Pydantic computed fields.

This bounded fixture establishes its own positive mutation population. It does
not establish the causes of historical models/browser failures or universal
framework support. Unrelated errors and harness timeouts must fail normally.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from mutmut_win.db import known_run_basis_incompleteness, load_latest_run_results
from mutmut_win.mutation import mutate_file_contents

if TYPE_CHECKING:
    from pathlib import Path

from tests.e2e.e2e_util import PYDANTIC_HEAVY, cache_db, copy_project, run_cli

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class _ClassMutationMetadata(BaseModel):
    """Persisted bindings needed by the independent population oracle."""

    source_hash: str
    generated_hash: str
    exit_code_by_key: dict[str, int | None]


def test_pydantic_heavy_fixture_suite_is_green_untrampolined(tmp_path: Path) -> None:
    """Mirror oracle: the fixture's own suite passes without trampolines."""

    project = copy_project(PYDANTIC_HEAVY, tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert " failed" not in result.stdout


def test_pydantic_heavy_full_engine_run_completes(tmp_path: Path) -> None:
    """Require actual class instrumentation, complete evidence and causal kills."""

    project = copy_project(PYDANTIC_HEAVY, tmp_path)
    source = project / "src/pydantic_heavy/models.py"
    _, names = mutate_file_contents(str(source), source.read_text(encoding="utf-8"))
    assert names, "The framework fixture must produce a positive mutation population"
    assert all("DiscountedOrderǁrequires_payment__mutmut_" in name for name in names)
    result = run_cli(project, "run", "--no-progress", timeout=900)
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    state, verdicts = load_latest_run_results(cache_db(project))
    assert state is not None
    expected = {f"pydantic_heavy.models.{name}" for name in names}
    assert set(state.planned_names) == expected
    assert state.status == "completed" and state.is_full_run
    assert not state.pending_names
    assert known_run_basis_incompleteness(state) is None
    assert {verdict.mutant_name for verdict in verdicts} == expected
    assert all(verdict.status == "killed" for verdict in verdicts)
    generated = project / "mutants/src/pydantic_heavy/models.py"
    metadata = _ClassMutationMetadata.model_validate_json(
        generated.with_suffix(".py.meta").read_text(encoding="utf-8")
    )
    assert set(metadata.exit_code_by_key) == expected
    assert metadata.source_hash == hashlib.sha256(source.read_bytes()).hexdigest()
    assert metadata.generated_hash == hashlib.sha256(generated.read_bytes()).hexdigest()
    print(f"class population={len(expected)}; killed={len(verdicts)}; basis=complete")
