"""Allow running as ``python -m mutmut_win``."""

from mutmut_win.cli import cli

from mutmut_win.exceptions import MutmutProgrammaticFailException  # noqa: F401 — imported by trampoline_impl  # isort: skip


def record_trampoline_hit(name: str) -> None:
    """Record that a trampoline function was called during stats collection.

    Called by the injected trampoline code when MUTANT_UNDER_TEST == 'stats'.

    Args:
        name: The mangled function name that was hit.
    """
    from mutmut_win._state import _stats

    _stats.add(name)


if __name__ == "__main__":
    cli()
