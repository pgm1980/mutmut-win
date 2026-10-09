"""Pin the supported template-string operator boundary on CPython 3.14.7."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import libcst as cst
import pytest
from pydantic import BaseModel

from mutmut_win.mutation import mutate_file_contents
from mutmut_win.node_mutation import operator_return_value, operator_string


class TemplateObservation(BaseModel):
    """Actual runtime result of a generated template or formatted expression."""

    strings: tuple[str, ...] = ()
    values: tuple[int, ...] = ()
    expressions: tuple[str, ...] = ()
    text: str | None = None


@pytest.mark.parametrize(("prefix", "expected_count"), [("t", 0), ("f", 3)])
def test_exact_template_fixture_and_formatted_control(
    tmp_path: Path, prefix: str, expected_count: int
) -> None:
    """The documented exact fixture preserves runtime meaning and operator count."""
    source = f'def value(x):\n    return {prefix}"hello {{x}}!"\n'
    generated, names = mutate_file_contents("sample.py", source)
    print(prefix, list(names))
    assert len(names) == expected_count
    expression = cst.parse_expression(f'{prefix}"hello {{x}}!"')
    assert isinstance(expression, cst.BaseString)
    assert len(list(operator_string(expression))) == (0 if prefix == "t" else 2)
    assert len(list(operator_return_value(cst.Return(expression)))) == (0 if prefix == "t" else 1)
    probe = tmp_path / "generated_probe.py"
    probe.write_text(
        generated
        + "\nfrom pydantic import BaseModel\n"
        + "from string.templatelib import Template\n"
        + "class Observation(BaseModel):\n"
        + "    strings: tuple[str, ...] = ()\n"
        + "    values: tuple[int, ...] = ()\n"
        + "    expressions: tuple[str, ...] = ()\n"
        + "    text: str | None = None\n"
        + "result = value(7)\n"
        + "if isinstance(result, Template):\n"
        + "    observed = Observation(strings=result.strings, values=result.values,\n"
        + "        expressions=tuple(part.expression for part in result.interpolations))\n"
        + "else:\n"
        + "    observed = Observation(text=result)\n"
        + "print(observed.model_dump_json())\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", str(probe)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = TemplateObservation.model_validate_json(result.stdout)
    print(observed.model_dump_json())
    if prefix == "t":
        assert observed.strings == ("hello ", "!")
        assert observed.values == (7,)
        assert observed.expressions == ("x",)
        assert observed.text is None
    else:
        assert observed.text == "hello 7!"
        assert observed.strings == ()
        assert observed.values == ()
        assert observed.expressions == ()


def test_template_interpolation_expression_remains_mutable() -> None:
    """The literal boundary does not disable supported operators inside expressions."""
    source = 'def value(x, y):\n    return t"sum={x + y}"\n'
    generated, names = mutate_file_contents("sample.py", source)
    assert names
    assert 't"sum={x - y}"' in generated
    compile(generated, "generated-template", "exec")
