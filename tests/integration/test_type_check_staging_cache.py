"""M-063: the type checker must not write its cache into mutants/.

The checker runs with ``cwd = mutants/``; mypy's default ``.mypy_cache``
would therefore be created inside the staging tree and invalidate the strict
staging evidence.  The ephemeral environment must redirect checker caches
into the per-run runtime directory instead.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from mutmut_win.type_checking import run_type_checker

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.integration
def test_mypy_cache_is_redirected_out_of_the_staging_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real mypy must not create mutants/.mypy_cache under its cwd."""

    mutants = tmp_path / "mutants"
    package = mutants / "pkg"
    package.mkdir(parents=True)
    (package / "mod.py").write_text('x: int = "s"\n', encoding="utf-8")
    empty_config = tmp_path / "empty-mypy.ini"
    empty_config.write_text("", encoding="utf-8")
    monkeypatch.chdir(mutants)

    run_type_checker(
        [
            sys.executable,
            "-m",
            "mypy",
            "--output=json",
            f"--config-file={empty_config}",
            "pkg/",
        ]
    )

    assert not (mutants / ".mypy_cache").exists()
