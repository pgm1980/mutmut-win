"""Allow running as ``python -m mutmut_win``."""

from mutmut_win.cli import cli

from mutmut_win.exceptions import MutmutProgrammaticFailException  # noqa: F401 — imported by trampoline_impl (pre-v2.11.0 staging trees)  # isort: skip

# BWC re-exports for staging trees generated before v2.11.0 — their
# trampolines import the hit recording from here. The kernel moved to
# mutmut_win.hit_recording (issue #107 / A4-QX-001: this module statically
# pulls the whole CLI chain via `from mutmut_win.cli import cli` above).
from mutmut_win.hit_recording import _get_max_stack_depth as _get_max_stack_depth
from mutmut_win.hit_recording import record_trampoline_hit as record_trampoline_hit

if __name__ == "__main__":
    cli()
