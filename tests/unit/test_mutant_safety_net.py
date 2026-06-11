"""Tests for the generated-mutant safety net + operator crash guards (Issue #78).

Audit findings A1-MT-007 (invalid mutant file written before validation, kept
on disk, silent), A1-MT-011 (U+01C1 identifier crashes the run), A1-NM-007
(1e400 -> repr(inf) -> CSTValidationError kills the file), A1-NM-009
(duplicate-keyword mutant), A1-RX-001 (OverflowError bypasses re.error
validation).  The safety net structurally contains the whole Bug-#68/BUG-1
class: a file whose generated mutants do not compile is copied unmutated with
a loud warning instead of poisoning the mutants/ staging.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from unittest.mock import patch

import libcst as cst

from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.node_mutation import operator_dict_arguments, operator_number
from mutmut_win.regex_mutation import mutate_regex_pattern

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Safety net: validate-then-write (A1-MT-007)
# ---------------------------------------------------------------------------


class TestValidateThenWrite:
    def test_invalid_generated_output_falls_back_to_original(self, tmp_path: Path) -> None:
        """If the engine produces non-compiling output, the original source is
        written instead, no mutant names are returned, and a warning is
        collected — the run continues instead of breaking the clean gate."""
        source = "def f():\n    return 1\n"
        src_file = tmp_path / "mod.py"
        src_file.write_text(source, encoding="utf-8")
        out_file = tmp_path / "out.py"

        def _broken_writer(*, out, **_kwargs):  # type: ignore[no-untyped-def]  # mock matches kw-call shape
            out.write("def broken(:\n    pass\n")
            return ["x_f__mutmut_1"]

        with patch("mutmut_win.file_setup.write_all_mutants_to_file", _broken_writer):
            names, warns = create_mutants_for_file(src_file, out_file)

        assert names == []
        written = out_file.read_text(encoding="utf-8")
        assert written == source  # original, not the broken output
        assert any("do not compile" in str(w.message) for w in warns)

    def test_end_to_end_output_always_compiles(self, tmp_path: Path) -> None:
        """Adversarial multiline-or pattern (A1-NM-001 / Bug-#68 class): the
        written file must compile — either via valid mutants (post-#73) or
        via the unmutated-fallback (this issue)."""
        source = "def f(a, b, c):\n    x = (a +\n         b or c)\n    return x\n"
        src_file = tmp_path / "mod.py"
        src_file.write_text(source, encoding="utf-8")
        out_file = tmp_path / "out.py"

        create_mutants_for_file(src_file, out_file)

        ast.parse(out_file.read_text(encoding="utf-8"))  # must not raise

    def test_u01c1_identifier_does_not_crash_run(self, tmp_path: Path) -> None:
        """A legal identifier containing U+01C1 (the mangling separator) must
        not crash mutant generation (A1-MT-011) — file is copied unmutated."""
        source = "def aǁb():\n    return 1\n"
        src_file = tmp_path / "mod.py"
        src_file.write_text(source, encoding="utf-8")
        out_file = tmp_path / "out.py"

        names, warns = create_mutants_for_file(src_file, out_file)

        assert names == []
        assert out_file.read_text(encoding="utf-8") == source
        assert len(warns) >= 1


# ---------------------------------------------------------------------------
# Operator crash guards
# ---------------------------------------------------------------------------


class TestOperatorNumberInfinityGuard:
    def test_float_overflowing_to_inf_is_skipped(self) -> None:
        # 1e400 is a legal float literal evaluating to inf; repr(inf) is not
        # a valid float token (A1-NM-007).
        assert list(operator_number(cst.Float("1e400"))) == []

    def test_imaginary_overflowing_to_inf_is_skipped(self) -> None:
        assert list(operator_number(cst.Imaginary("1e400j"))) == []

    def test_normal_float_still_mutated(self) -> None:
        mutants = list(operator_number(cst.Float("1.5")))
        assert len(mutants) == 1
        assert mutants[0].value == "2.5"

    def test_normal_integer_still_mutated(self) -> None:
        mutants = list(operator_number(cst.Integer("41")))
        assert len(mutants) == 1
        assert mutants[0].value == "42"


class TestDictArgumentsDuplicateGuard:
    def test_colliding_keyword_mutation_is_skipped(self) -> None:
        # dict(a=1, aXX=2): mutating a -> aXX would duplicate the existing
        # keyword and produce a SyntaxError mutant (A1-NM-009).
        node = cst.parse_expression("dict(a=1, aXX=2)")
        assert isinstance(node, cst.Call)
        mutated = list(operator_dict_arguments(node))
        rendered = [cst.Module(body=[]).code_for_node(m) for m in mutated]
        assert rendered == ["dict(a=1, aXXXX=2)"]

    def test_normal_keywords_still_mutated(self) -> None:
        node = cst.parse_expression("dict(a=1, b=2)")
        assert isinstance(node, cst.Call)
        mutated = list(operator_dict_arguments(node))
        rendered = [cst.Module(body=[]).code_for_node(m) for m in mutated]
        assert rendered == ["dict(aXX=1, b=2)", "dict(a=1, bXX=2)"]


class TestRegexOverflowGuard:
    def test_maxrepeat_boundary_does_not_raise(self) -> None:
        # a{4294967294} is a valid pattern; the {n+1} mutation produces
        # a{4294967295}, whose re.compile raises OverflowError, not re.error
        # (A1-RX-001).
        results = mutate_regex_pattern("a{4294967294}")
        assert "a{4294967295}" not in results

    def test_normal_quantifier_still_mutated(self) -> None:
        results = mutate_regex_pattern("a{3}")
        assert "a{4}" in results
