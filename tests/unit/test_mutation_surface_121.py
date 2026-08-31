"""Issue #121 (external QA MUT-001, MUT-002): mutation-surface honesty.

MUT-001 — functions whose only mutable content is an f-string produced
ZERO mutants: ``operator_string`` only mutates ``SimpleString``
(inherited from upstream 3.5.0) and ``operator_return_value`` skipped
every ``BaseString`` return claiming other operators cover it — false
for ``FormattedString``. Such functions were invisible to every report.
Fix: f-string returns get the return-value mutation, and f-string
literal TEXT parts are mutated (format specs and expressions live in
``FormattedStringExpression`` and are provably untouched).

MUT-002 — one valid-but-unmanglable identifier (U+01C1, the mangling
separator) silently dropped the WHOLE file as "Unsupported syntax".
The skip is now function-granular: neighbours mutate normally, and the
warning names the engine limitation instead of blaming the syntax.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import libcst as cst
import pytest

from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.node_mutation import operator_return_value, operator_string

if TYPE_CHECKING:
    from pathlib import Path


def _fstring(code: str) -> cst.FormattedString:
    expr = cst.parse_expression(code)
    assert isinstance(expr, cst.FormattedString)
    return expr


# ---------------------------------------------------------------------------
# MUT-001 — operator level
# ---------------------------------------------------------------------------


class TestFormattedStringReturn:
    def test_fstring_return_yields_return_none(self) -> None:
        """The skip claimed 'already mutated by other operators' — false for
        FormattedString, which nothing else touches."""
        ret = cst.parse_statement("return f'hi {name}!'").body[0]
        assert isinstance(ret, cst.Return)
        variants = list(operator_return_value(ret))
        assert len(variants) == 1
        assert cst.Module([cst.SimpleStatementLine([variants[0]])]).code.strip() == "return None"

    def test_simple_string_return_stays_skipped(self) -> None:
        """SimpleString returns ARE covered by operator_string — no change."""
        ret = cst.parse_statement("return 'hi'").body[0]
        assert isinstance(ret, cst.Return)
        assert list(operator_return_value(ret)) == []


class TestFormattedStringTextMutation:
    def test_text_parts_are_xx_wrapped(self) -> None:
        variants = list(operator_string(_fstring("f'hi {name}!'")))
        rendered = [cst.Module([cst.SimpleStatementLine([cst.Expr(v)])]).code for v in variants]
        assert len(variants) == 2  # one per literal text part ('hi ' and '!')
        assert any("XXhi XX" in r for r in rendered)
        assert any("XX!XX" in r for r in rendered)

    def test_format_specs_are_never_touched(self) -> None:
        """The safety condition for this engine extension: specs and
        expressions live in FormattedStringExpression — provably untouched."""
        variants = list(operator_string(_fstring("f'{value:>10.2f} EUR'")))
        assert len(variants) == 1  # only the ' EUR' text part
        for variant in variants:
            rendered = cst.Module([cst.SimpleStatementLine([cst.Expr(variant)])]).code
            assert "{value:>10.2f}" in rendered

    def test_expression_only_fstring_yields_nothing(self) -> None:
        assert list(operator_string(_fstring("f'{value:>10.2f}'"))) == []

    def test_simple_strings_unchanged_behavior(self) -> None:
        """Regression pin: SimpleString mutation (XX-wrap + case) stays."""
        node = cst.SimpleString("'hi'")
        variants = list(operator_string(node))
        assert variants  # upstream behavior intact


# ---------------------------------------------------------------------------
# MUT-001 — engine level: the function is visible again
# ---------------------------------------------------------------------------


class TestFstringOnlyFunctionVisibility:
    def test_fstring_only_function_produces_mutants(self) -> None:
        """The report's probe: zero mutants, no trampoline, invisible
        everywhere. Now it must appear in the mutation surface."""
        source = "def fstring_only(name):\n    return f'hi {name}!'\n"
        mutated_code, mutant_names = mutate_file_contents("probe.py", source)
        assert mutant_names, "f-string-only function must not vanish"
        assert "fstring_only" in mutated_code
        assert "_mutmut_trampoline" in mutated_code

    def test_format_spec_only_function_produces_the_return_mutant(self) -> None:
        source = "def fstring_with_spec(value):\n    return f'{value:>10.2f}'\n"
        _mutated_code, mutant_names = mutate_file_contents("probe.py", source)
        assert len(mutant_names) >= 1  # at least return-None


# ---------------------------------------------------------------------------
# MUT-002 — function-granular mangling skip
# ---------------------------------------------------------------------------


class TestManglingSkipGranularity:
    _SOURCE = "def funcǁname(x):\n    return x + 1\n\ndef normal_neighbor(y):\n    return y * 2\n"

    def test_neighbour_function_still_mutates(self) -> None:
        """One offending function used to disable mutation for the entire
        file — silent coverage loss beyond the one-line warning."""
        with pytest.warns(SyntaxWarning, match="mangling separator"):
            mutated_code, mutant_names = mutate_file_contents("sep.py", self._SOURCE)
        assert any("normal_neighbor" in n for n in mutant_names)
        assert all("funcǁname" not in n for n in mutant_names)
        ast.parse(mutated_code)  # the written module must compile

    def test_offending_function_survives_unmutated(self) -> None:
        with pytest.warns(SyntaxWarning, match="mangling separator"):
            mutated_code, _names = mutate_file_contents("sep.py", self._SOURCE)
        assert "def funcǁname(x):" in mutated_code  # original kept verbatim

    def test_warning_names_the_limitation_not_the_syntax(self) -> None:
        with pytest.warns(SyntaxWarning) as caught:
            mutate_file_contents("sep.py", self._SOURCE)
        messages = [str(w.message) for w in caught]
        assert any("mangling separator" in m for m in messages)
        assert all("Unsupported syntax" not in m for m in messages)

    def test_create_mutants_for_file_collects_the_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "sep.py"
        src.write_text(self._SOURCE, encoding="utf-8")
        out = tmp_path / "mutants" / "sep_out.py"
        names, warns, _ = create_mutants_for_file(src, out)
        assert any("normal_neighbor" in n for n in names)
        assert any("mangling separator" in str(w.message) for w in warns)
        ast.parse(out.read_text(encoding="utf-8"))
