"""Native regression checks for bounded stack hit attribution."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

if TYPE_CHECKING:
    from pathlib import Path


class HitObservation(BaseModel):
    """Hits and runtime identity emitted by a standalone native interpreter."""

    hits: list[str]
    pid: int
    depth: int


@pytest.mark.parametrize("directory", ["service", "pytest", "_pytest", "unittest"])
@pytest.mark.parametrize("depth", [4, -1], ids=["bounded", "unlimited"])
def test_native_hits_do_not_depend_on_directory(tmp_path: Path, directory: str, depth: int) -> None:
    """The same standalone source cannot acquire a runner frame from its path."""
    source = (
        "import os, sys\n"
        "from pydantic import BaseModel\n"
        "from mutmut_win import _state\n"
        "from mutmut_win.hit_recording import record_trampoline_hit\n"
        "class Observation(BaseModel):\n"
        "    hits: list[str]\n"
        "    pid: int\n"
        "    depth: int\n"
        "_state._stats.clear()\n"
        "_state._cached_max_stack_depth = int(sys.argv[1])\n"
        "record_trampoline_hit('SENTINEL')\n"
        "print(Observation(hits=sorted(_state._stats),pid=os.getpid(),"
        "depth=_state._cached_max_stack_depth).model_dump_json())\n"
    )
    path = tmp_path / directory / "probe.py"
    path.parent.mkdir()
    path.write_text(source, encoding="utf-8")
    # Execute only the current interpreter and the exact fixture written above.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(path), str(depth)],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = HitObservation.model_validate_json(result.stdout)
    print(directory, observed.model_dump_json())
    assert observed.pid > 0
    assert observed.depth == depth
    assert observed.hits == (["SENTINEL"] if depth == -1 else [])
