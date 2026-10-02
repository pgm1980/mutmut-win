"""do_not_mutate_patterns regex node-exclusion (mutmut-3.6.0 surface backport).

Covers the config field (validation + string coercion) and the end-to-end node
skip threaded through ``mutate_file_contents`` into ``_skip_node_and_children``.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win.config import MutmutConfig
from mutmut_win.mutation import mutate_file_contents

_FUNCS = "def keep_me():\n    return 1 + 2\n\n\ndef skip_me():\n    return 3 + 4\n"
_CLASSES = (
    "class Keep:\n    def m(self):\n        return 1 + 1\n\n\n"
    "class Skip:\n    def m(self):\n        return 2 + 2\n"
)


def _names(source: str, patterns: list[str]) -> list[str]:
    _code, names = mutate_file_contents("m.py", source, do_not_mutate_patterns=patterns)
    return list(names)


class TestConfigField:
    def test_bad_regex_rejected_at_load(self) -> None:
        with pytest.raises(ValidationError, match="not a valid regex"):
            MutmutConfig(do_not_mutate_patterns=["(unclosed"])

    def test_good_patterns_accepted(self) -> None:
        cfg = MutmutConfig(do_not_mutate_patterns=[r"test_.*", r"_internal"])
        assert cfg.do_not_mutate_patterns == [r"test_.*", r"_internal"]

    def test_single_string_coerced_to_list(self) -> None:
        cfg = MutmutConfig(do_not_mutate_patterns="solo_.*")
        assert cfg.do_not_mutate_patterns == ["solo_.*"]

    def test_default_is_empty(self) -> None:
        assert MutmutConfig().do_not_mutate_patterns == []


class TestNodeSkip:
    def test_no_patterns_mutates_every_function(self) -> None:
        names = _names(_FUNCS, [])
        assert any("keep_me" in n for n in names)
        assert any("skip_me" in n for n in names)

    def test_matched_function_is_skipped(self) -> None:
        names = _names(_FUNCS, ["skip_me"])
        assert any("keep_me" in n for n in names)  # sibling still mutates
        assert not any("skip_me" in n for n in names)

    def test_regex_skips_all_matching_functions(self) -> None:
        # `.*_me$` matches both names via re.search -> nothing left to mutate
        assert _names(_FUNCS, [r".*_me$"]) == []

    def test_matched_class_skips_its_methods(self) -> None:
        names = _names(_CLASSES, ["Skip"])
        assert any("Keep" in n for n in names)  # the other class still mutates
        assert not any("Skip" in n for n in names)


_TWO_METHODS = (
    "class Keep:\n    def shared(self):\n        return 1 + 1\n\n\n"
    "class Drop:\n    def shared(self):\n        return 2 + 2\n"
)


class TestQualifiedNameMatching:
    """do_not_mutate_patterns may match the QUALIFIED ``Class.method`` name, not
    only the bare method name (external QA v2.19.0: matcher was name-only)."""

    def test_qualified_pattern_targets_one_class_method(self) -> None:
        # `Drop\.shared` skips ONLY Drop.shared; Keep.shared still mutates
        names = _names(_TWO_METHODS, [r"Drop\.shared"])
        assert any("Keepǁshared" in n for n in names)
        assert not any("Dropǁshared" in n for n in names)

    def test_bare_method_name_still_matches_every_class(self) -> None:
        # backward compatibility: a simple name skips the method in EVERY class
        assert not any("shared" in n for n in _names(_TWO_METHODS, ["shared"]))

    def test_qualified_class_anchor(self) -> None:
        # an anchored class pattern skips only that class
        names = _names(_TWO_METHODS, [r"^Keep$"])
        assert not any("Keep" in n for n in names)
        assert any("Drop" in n for n in names)

    def test_anchored_bare_name_matches_via_the_simple_name(self) -> None:
        # `^shared$` matches the SIMPLE name but NOT the qualified "Class.shared",
        # so the simple-name half of the OR is load-bearing (skips both methods)
        assert not any("shared" in n for n in _names(_TWO_METHODS, [r"^shared$"]))

    def test_anchored_qualified_pattern_requires_a_correct_class_stack(self) -> None:
        # `^Drop\.shared$` matches only when the stack is exactly ["Drop"]; a
        # broken on_visit push or on_leave pop would yield "shared" /
        # "Keep.Drop.shared" and miss it. Pins the qualified name end to end.
        names = _names(_TWO_METHODS, [r"^Drop\.shared$"])
        assert not any("Dropǁshared" in n for n in names)
        assert any("Keepǁshared" in n for n in names)

    @pytest.mark.parametrize(
        ("inner_class", "patterns"),
        [
            pytest.param(
                "    @deco\n    class Inner:\n        x = 1\n",
                [r"^Outer\.m$"],
                id="decorated-inner-class",
            ),
            pytest.param(
                "    class Inner:\n        x = 1\n",
                [r"^Outer\.Inner$", r"^Outer\.m$"],
                id="pattern-skipped-inner-class",
            ),
        ],
    )
    def test_skipped_nested_class_keeps_outer_qualifier(
        self, inner_class: str, patterns: list[str]
    ) -> None:
        # M-038 regression: libcst calls on_leave for EVERY ClassDef, including
        # ones skipped by on_visit (decorator rule or pattern hit). The blind
        # pop used to remove the OUTER class entry, so `^Outer\.m$` no longer
        # matched `m` and the explicitly excluded method was mutated anyway.
        source = (
            "class Outer:\n"
            f"{inner_class}"
            "    def m(self):\n"
            "        return 1 + 1\n"
            "    def n(self):\n"
            "        return 2 + 2\n"
        )
        names = _names(source, patterns)
        assert not any("Outerǁm" in n for n in names), names
        assert any("Outerǁn" in n for n in names), names

    def test_skipped_local_class_in_method_keeps_outer_qualifier(self) -> None:
        # Same desynchronisation through a decorated class LOCAL to a method:
        # on_leave(Local) must not pop the enclosing `Outer` entry.
        source = (
            "class Outer:\n"
            "    def a(self):\n"
            "        @deco\n"
            "        class Local:\n"
            "            pass\n"
            "        return 1 + 1\n"
            "    def m(self):\n"
            "        return 2 + 2\n"
        )
        names = _names(source, [r"^Outer\.m$"])
        assert not any("Outerǁm" in n for n in names), names
        assert any("Outerǁa" in n for n in names), names


@given(st.lists(st.sampled_from(["decorated", "pattern", "plain"]), max_size=4))
@settings(deadline=None)
def test_qualified_pattern_survives_arbitrary_inner_class_skips(kinds: list[str]) -> None:
    """Anchored qualified patterns keep working after ANY mix of skipped inner classes.

    Deco<N> classes are skipped by the decorator rule only, Skip<N> by the
    pattern, Keep<N> are plain — the three skip paths must all leave the
    `Outer` qualifier intact for the methods declared after them.
    """
    parts = ["class Outer:\n"]
    for index, kind in enumerate(kinds):
        if kind == "decorated":
            parts.append(f"    @deco\n    class Deco{index}:\n        x = {index + 1}\n")
        elif kind == "pattern":
            parts.append(f"    class Skip{index}:\n        x = {index + 2}\n")
        else:
            parts.append(f"    class Keep{index}:\n        x = {index + 3}\n")
    parts += [
        "    def target(self):\n        return 1 + 1\n",
        "    def other(self):\n        return 2 + 2\n",
        "class Second:\n    def m(self):\n        return 3 + 3\n",
    ]
    source = "".join(parts)
    patterns = [r"^Outer\.Skip\d+$", r"^Outer\.target$", r"^Second\.m$"]
    names = _names(source, patterns)
    assert not any("Outerǁtarget" in n for n in names), names
    assert not any("Secondǁm" in n for n in names), names
    assert any("Outerǁother" in n for n in names), names
