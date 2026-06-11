"""Allow running as ``python -m mutmut_win``."""

from mutmut_win.cli import cli

from mutmut_win.exceptions import MutmutProgrammaticFailException  # noqa: F401 — imported by trampoline_impl  # isort: skip


def _get_max_stack_depth() -> int:
    """Return the configured max_stack_depth, caching after first load.

    The cache lives in ``_state`` (issue #110 / A4-QX-017) so that
    ``_reset_globals`` covers it together with the other trampoline state.

    Returns:
        The ``max_stack_depth`` value from the current project config.
        Returns ``-1`` (unlimited) if the config cannot be loaded.
    """
    from mutmut_win import _state

    if _state._cached_max_stack_depth is None:
        try:
            from mutmut_win.config import load_config

            _state._cached_max_stack_depth = load_config().max_stack_depth
        except Exception:  # broad catch: trampoline must not crash under any circumstance
            _state._cached_max_stack_depth = -1
    return _state._cached_max_stack_depth


def record_trampoline_hit(name: str) -> None:
    """Record that a trampoline function was called during stats collection.

    Called by the injected trampoline code when MUTANT_UNDER_TEST == 'stats'.
    Mirrors ``mutmut 3.5.0 record_trampoline_hit``: when ``max_stack_depth``
    is set, the call stack is walked up to that many frames looking for a
    pytest or unittest frame.  If none is found within the limit the hit is
    discarded (the mutation is too deep to be reliably exercised by tests).

    Args:
        name: The mangled function name that was hit.
    """
    max_depth = _get_max_stack_depth()
    if max_depth != -1:
        import inspect

        frame = inspect.currentframe()
        remaining = max_depth
        while remaining and frame:
            filename = frame.f_code.co_filename
            if "pytest" in filename or "unittest" in filename:
                break
            frame = frame.f_back
            remaining -= 1
        if not remaining:
            # Depth limit reached without finding a test frame — discard hit.
            return

    from mutmut_win._state import _stats

    _stats.add(name)


if __name__ == "__main__":
    cli()
