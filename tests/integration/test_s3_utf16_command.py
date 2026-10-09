"""Actual Windows command-line limits, separate from the browser adapter."""

import subprocess
import sys

import pytest

from mutmut_win.process.foreground import ProcessContainmentError, run_foreground_contained


@pytest.mark.parametrize("character", ["x", "\U00010400"])
def test_native_command_length_counts_utf16(character: str) -> None:
    """Equal codepoint counts have different CreateProcessW outcomes."""
    command = [
        sys.executable,
        "-c",
        "import sys; raise SystemExit(0 if len(sys.argv[1]) == 18000 else 7)",
        character * 18000,
    ]
    serialized = subprocess.list2cmdline(command)
    assert len(serialized) < 32767
    if character == "x":
        assert len(serialized.encode("utf-16-le")) // 2 < 32767
        assert run_foreground_contained(command) == 0
    else:
        assert len(serialized.encode("utf-16-le")) // 2 > 32767
        with pytest.raises(ProcessContainmentError) as caught:
            run_foreground_contained(command)
        assert isinstance(caught.value.__cause__, OSError)
        assert caught.value.__cause__.winerror == 206
