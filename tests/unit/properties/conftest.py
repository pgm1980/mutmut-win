"""Hypothesis profiles for property-based tests (W3 acceptance criteria).

Usage:
    pytest --hypothesis-profile=ci       # fast: 20 examples (default for CI)
    pytest --hypothesis-profile=nightly  # thorough: 500 examples
    pytest                               # default: 100 examples
"""

from __future__ import annotations

from hypothesis import settings

settings.register_profile("ci", max_examples=20, deadline=None)
settings.register_profile("default", max_examples=100, deadline=None)
settings.register_profile("nightly", max_examples=500, deadline=None)

settings.load_profile("default")
