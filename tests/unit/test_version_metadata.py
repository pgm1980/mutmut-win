"""Regression test for Bug/Issue #72 — `--version` must follow pyproject.toml.

Pre-Sprint-26 ``src/mutmut_win/__init__.py`` carried a hardcoded
``__version__ = "2.0.4"`` that was never bumped through the v2.1.0 →
v2.4.0 releases. ``mutmut-win --version`` therefore reported a stale
version regardless of what was actually installed.

The fix replaces the constant with an ``importlib.metadata.version`` lookup
so that ``pyproject.toml`` becomes the single source of truth. Drift
becomes structurally impossible from this point on.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import mutmut_win


def test_module_version_matches_installed_metadata() -> None:
    """``mutmut_win.__version__`` must equal the metadata version of the package."""
    try:
        expected = version("mutmut-win")
    except PackageNotFoundError as exc:
        msg = (
            "mutmut-win must be installed (editable or wheel) for this test. "
            "Run `uv sync` or `pip install -e .` first."
        )
        raise AssertionError(msg) from exc

    assert mutmut_win.__version__ == expected, (
        f"__version__ drift detected: module says {mutmut_win.__version__!r}, "
        f"installed metadata says {expected!r}. The two must stay in sync — "
        f"see Issue #72."
    )


def test_module_version_is_not_the_stale_constant() -> None:
    """Specific regression: __version__ must not be the historical '2.0.4' constant."""
    # 2.0.4 was the value hardcoded in __init__.py through v2.1.0 → v2.4.0.
    # Any installation of v2.1.0 or later must report a different version.
    installed = version("mutmut-win")
    if installed != "2.0.4":
        assert mutmut_win.__version__ != "2.0.4", (
            f"__version__ still reports the stale '2.0.4' constant even though "
            f"installed metadata says {installed!r}. The importlib.metadata fix "
            f"is missing or regressed."
        )
