"""CX221-070: pytest argument files must preserve validated target boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from _pytest.config.argparsing import Parser

from mutmut_win.exceptions import BadTestExecutionCommandsException
from mutmut_win.process.worker import _write_pytest_argfile, validated_pytest_targets

if TYPE_CHECKING:
    from pathlib import Path

_LINE_BREAKS = (
    pytest.param("\n", id="lf"),
    pytest.param("\r", id="cr"),
    pytest.param("\r\n", id="crlf"),
    pytest.param("\v", id="vertical-tab"),
    pytest.param("\f", id="form-feed"),
    pytest.param("\x1c", id="file-separator"),
    pytest.param("\x1d", id="group-separator"),
    pytest.param("\x1e", id="record-separator"),
    pytest.param("\x85", id="next-line"),
    pytest.param("\u2028", id="line-separator"),
    pytest.param("\u2029", id="paragraph-separator"),
)


@pytest.mark.parametrize("line_break", _LINE_BREAKS)
@pytest.mark.parametrize("boundary", ["validator", "writer"])
def test_all_pytest_parser_line_breaks_are_rejected_before_publication(
    tmp_path: Path, line_break: str, boundary: str
) -> None:
    target = f"tests/test_example.py::test_value[first{line_break}second]"
    parser_input = tmp_path / "parser-input.txt"
    parser_input.write_bytes(f"{target}\n".encode())

    # Exercise pytest's actual argparse reader without collecting tests or
    # starting a subprocess. Every spelling below splits this harmless value.
    parsed = Parser(_ispytest=True).parse_known_args(["--", f"@{parser_input}"])
    assert parsed.file_or_dir == ["tests/test_example.py::test_value[first", "second]"]

    publication = tmp_path / "unpublished"
    publication.mkdir()
    if boundary == "writer":
        with pytest.raises(BadTestExecutionCommandsException, match="NUL or line breaks"):
            _write_pytest_argfile([target], publication)
    else:
        with pytest.raises(BadTestExecutionCommandsException, match="NUL or line breaks"):
            validated_pytest_targets([target], field_name="tests_dir")
    assert list(publication.iterdir()) == []


@pytest.mark.parametrize("boundary", ["validator", "writer"])
def test_nul_target_is_rejected_before_publication(tmp_path: Path, boundary: str) -> None:
    target = "tests/test_example.py::test_value[first\0second]"
    publication = tmp_path / "unpublished"
    publication.mkdir()
    if boundary == "writer":
        with pytest.raises(BadTestExecutionCommandsException, match="NUL or line breaks"):
            _write_pytest_argfile([target], publication)
    else:
        with pytest.raises(BadTestExecutionCommandsException, match="NUL or line breaks"):
            validated_pytest_targets([target], field_name="MutationTask.tests")
    assert list(publication.iterdir()) == []


def test_pytest_parser_preserves_unicode_whitespace_target_bytes_and_order(tmp_path: Path) -> None:
    targets = [
        "tests/test zürich.py::test_münchen",
        "tests/test_unicode.py::test_value[東京 😀]",
        "tests/test_unicode.py::test_value[e\u0301\u00a0x\u2009y]",
        "tests/test_unicode.py::test_value[tab\tx]",
    ]
    validated = validated_pytest_targets(targets, field_name="tests_dir")
    argument_file = _write_pytest_argfile(validated, tmp_path)
    expected_bytes = "".join(f"{target}\n" for target in targets).encode("utf-8")
    assert argument_file.read_bytes() == expected_bytes

    parsed = Parser(_ispytest=True).parse_known_args(["--", f"@{argument_file}"])

    assert parsed.file_or_dir == targets
    assert [target.encode("utf-8") for target in parsed.file_or_dir] == [
        target.encode("utf-8") for target in targets
    ]
