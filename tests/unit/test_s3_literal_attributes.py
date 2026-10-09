"""S3-015: literal attribute mutations retain a complete compilable file."""

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.mutation import mutate_file_contents


@pytest.mark.parametrize("literal", ["0x10", "0o10", "0b10", "1.5"])
def test_literal_attribute_does_not_discard_healthy_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, literal: str
) -> None:
    """Three integer spellings and a float control preserve both populations."""
    monkeypatch.chdir(tmp_path)
    attribute = "as_integer_ratio" if literal == "1.5" else "bit_length"
    source = f"def value():\n    return {literal}.{attribute}()\n\ndef other():\n    return 2\n"
    compile(source, "<original>", "exec")
    path = Path("module.py")
    path.write_text(source, encoding="utf-8")
    output = Path("mutants/module.py")
    names, diagnostics, reused = create_mutants_for_file(path, output)
    assert not diagnostics, [str(item.message) for item in diagnostics]
    assert not reused
    compile(output.read_text(encoding="utf-8"), "<generated>", "exec")
    assert any(name.startswith("x_value__mutmut_") for name in names)
    assert any(name.startswith("x_other__mutmut_") for name in names)
    assert path.read_text(encoding="utf-8") == source
    cached_names, cached_diagnostics, cached = create_mutants_for_file(path, output)
    assert cached
    assert cached_names == names
    assert not cached_diagnostics


@settings(max_examples=24)
@given(st.integers(min_value=0, max_value=65535), st.sampled_from(["x", "o", "b"]))
def test_nondecimal_attribute_mutants_compile(value: int, radix: str) -> None:
    """The engine preserves Python grammar for arbitrary supported integer bases."""
    literal = format(value, "#" + radix)
    source = f"def value():\n    return {literal}.bit_length()\n"
    generated, names = mutate_file_contents("module.py", source)
    assert names
    compile(generated, "<attribute-mutants>", "exec")
