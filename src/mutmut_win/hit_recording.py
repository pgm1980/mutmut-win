"""Trampoline hit-recording kernel — imported by the generated artifact.

Every trampolined source file imports :func:`record_trampoline_hit` from
here during stats runs (``MUTANT_UNDER_TEST=stats``).  This module is the
ONLY mutmut-win code the generated artifact pulls besides
``mutmut_win.exceptions``, so it must stay feather-light:

* Module level imports nothing of mutmut_win (``_state``/``config`` load
  lazily inside the functions) — issue #107 / A4-QX-001: the previous home
  in ``__main__`` statically pulled click + textual + the orchestrator
  chain (~1.4s) into every user test process, and broke the import-linter
  layer contract inside the build artifact (band-3 file -> __main__ ->
  cli), forcing an architecture-gate skip in mutants/.
* It lives in the BOTTOM band of the layer contract next to ``_state`` —
  the artifact's import chain never points upward again.

``__main__`` keeps BWC re-exports for staging trees generated before
v2.11.0.
"""

from __future__ import annotations


def _is_test_runner_filename(filename: str) -> bool:
    """Return whether *filename* belongs to a pytest/unittest package frame."""
    components = filename.replace("\\", "/").split("/")
    return any(component in {"pytest", "_pytest", "unittest"} for component in components)


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
        found_test_frame = False
        try:
            while remaining and frame:
                filename = frame.f_code.co_filename
                if _is_test_runner_filename(filename):
                    found_test_frame = True
                    break
                frame = frame.f_back
                remaining -= 1
        finally:
            # Frame objects participate in reference cycles; do not retain the
            # inspected stack beyond this extremely hot instrumentation path.
            del frame
        if not found_test_frame:
            # Either the configured depth was exhausted or the real stack ended
            # early.  Both mean no test frame was proven — discard the hit.
            return

    from mutmut_win._state import _stats

    _stats.add(name)
