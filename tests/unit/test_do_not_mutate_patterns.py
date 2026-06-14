"""do_not_mutate_patterns regex node-exclusion (mutmut-3.6.0 surface backport).

Covers the config field (validation + string coercion) and the end-to-end node
skip threaded through ``mutate_file_contents`` into ``_skip_node_and_children``.
"""

from __future__ import annotations

import pytest
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
