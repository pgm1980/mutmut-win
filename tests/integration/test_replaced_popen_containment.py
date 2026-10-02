"""Integration: a replaced Popen wrapper around the real Popen is refused.

M-144 / AR-05 (T7 of the R1 decision, P08_ENTSCHEIDUNGEN Z. 387-402): a
function wrapper that delegates to the real ``subprocess.Popen`` and returns
the real instance must be refused by ``_popen_contained`` before any Job
creation.  The recorded ``creationflags`` prove the ``CREATE_SUSPENDED``
passthrough, and the marker file proves the terminated child never ran any
user code under that documented precondition.  Not part of the mutation run
(real processes).
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any

import pytest

from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.process import worker as worker_module

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows suspended-resume contract"),
]

_CHILD_SLEEP_SECONDS = 30
_POLL_INTERVAL_SECONDS = 0.1
_REAP_DEADLINE_SECONDS = 10.0


def test_wrapper_around_real_popen_is_refused_suspended_and_ran_no_user_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refusal before Job creation; suspended child dies without a marker."""
    marker = tmp_path / "user-code-ran.marker"
    child_code = (
        "import pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text('ran', encoding='ascii')\n"
        f"time.sleep({_CHILD_SLEEP_SECONDS})\n"
    )

    recorded: dict[str, Any] = {}
    real_popen = subprocess.Popen

    def recording_wrapper(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        recorded["creationflags"] = kwargs.get("creationflags", 0)
        instance = real_popen(*args, **kwargs)  # type: ignore[arg-type,unused-ignore]
        recorded["instance"] = instance
        return instance

    monkeypatch.setattr(subprocess, "Popen", recording_wrapper)

    with pytest.raises(ProcessContainmentError, match="replaced after import"):
        worker_module._popen_contained(
            [sys.executable, "-c", child_code, str(marker)],
            creationflags=worker_module._contained_creationflags(0),
        )

    instance = recorded["instance"]
    assert isinstance(instance, real_popen)
    # The wrapper passed the suspension through unchanged (documented
    # precondition for "no user code ran").
    assert int(recorded["creationflags"]) & worker_module._CREATE_SUSPENDED

    # The refusal terminated the still-suspended child before test end.
    deadline = time.monotonic() + _REAP_DEADLINE_SECONDS
    while time.monotonic() < deadline and instance.poll() is None:
        time.sleep(_POLL_INTERVAL_SECONDS)
    assert instance.poll() is not None, "the refused child survived the refusal kill"
    # No user code ran: the very first child statement never executed.
    assert not marker.exists()
