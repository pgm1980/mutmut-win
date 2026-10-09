"""Exercise forced-fail attribution through real generated code and pytest children."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from pydantic import BaseModel

from mutmut_win.config import MutmutConfig
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.process.worker import consume_forced_fail_proof
from mutmut_win.runner import PytestRunner


class AttributionCase(BaseModel):
    """Describe a real child suite and its expected forced-fail attribution."""

    name: str
    body: str
    attributed: bool
    forced_exit: int = 1
    conftest: str = ""


_IMPORTS = "from pkg.mod import value\nimport os\nimport pytest\n"
_BODY = "\ndef test_value():\n    assert value() == 2\n"
_IMPORT_ASSERTION = "\nVALUE = value()\ndef test_value():\n    assert VALUE == 2\n"

_CASES = (
    AttributionCase(name="import_constant", body=_IMPORT_ASSERTION, attributed=True, forced_exit=2),
    AttributionCase(
        name="eager_strategy",
        body=(
            "from hypothesis import given, settings, strategies as st\n"
            "VALUES = st.sampled_from([value()])\n"
            "@settings(max_examples=2, deadline=None)\n"
            "@given(VALUES)\n"
            "def test_value(result):\n    assert result == 2\n"
        ),
        attributed=True,
        forced_exit=2,
    ),
    AttributionCase(
        name="parametrize",
        body=(
            "@pytest.mark.parametrize('result', [value()])\n"
            "def test_value(result):\n    assert result == 2\n"
        ),
        attributed=True,
        forced_exit=2,
    ),
    AttributionCase(name="body", body=_BODY, attributed=True),
    AttributionCase(
        name="fixture",
        body=(
            "@pytest.fixture\ndef result():\n    return value()\n"
            "def test_value(result):\n    assert result == 2\n"
        ),
        attributed=True,
    ),
    AttributionCase(
        name="foreign_collection_failure",
        body=(
            "if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
            "    raise ValueError('independent collection error')\n" + _BODY
        ),
        attributed=False,
        forced_exit=2,
    ),
    AttributionCase(
        name="same_named_faux_exception",
        body=(
            "class MutmutProgrammaticFailException(Exception):\n    pass\n"
            "MutmutProgrammaticFailException.__module__ = 'mutmut_win.exceptions'\n"
            "if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
            "    raise MutmutProgrammaticFailException('Failed programmatically')\n" + _BODY
        ),
        attributed=False,
        forced_exit=2,
    ),
    AttributionCase(
        name="warning_and_tail_text",
        body=(
            "import warnings\n"
            "if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
            "    warnings.warn('MutmutProgrammaticFailException', stacklevel=1)\n"
            "    print('mutmut_win.exceptions.MutmutProgrammaticFailException')\n"
            "    raise ValueError('MutmutProgrammaticFailException')\n" + _BODY
        ),
        attributed=False,
        forced_exit=2,
    ),
    AttributionCase(
        name="collection_skip_after_real_exception",
        body=(
            "try:\n    value()\n"
            "except Exception:\n    pytest.skip('handled', allow_module_level=True)\n" + _BODY
        ),
        attributed=False,
        forced_exit=5,
    ),
    AttributionCase(
        name="collection_xfail_after_real_exception",
        body="try:\n    value()\nexcept Exception:\n    pytest.xfail('handled')\n" + _BODY,
        attributed=False,
        forced_exit=2,
    ),
    AttributionCase(
        name="expected_body_xfail",
        body=(
            "@pytest.mark.xfail(os.environ.get('MUTANT_UNDER_TEST') == 'fail', reason='expected')\n"
            "def test_value():\n    assert value() == 2\n"
        ),
        attributed=False,
        forced_exit=0,
    ),
    AttributionCase(
        name="collection_proof_write_failure",
        body=_IMPORT_ASSERTION,
        attributed=False,
        forced_exit=2,
        conftest=(
            "import os\n"
            "def pytest_configure():\n"
            "    if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
            "        os.environ['MUTMUT_FORCED_FAIL_PROOF_PATH'] = os.getcwd()\n"
        ),
    ),
    AttributionCase(
        name="collection_wrong_token",
        body=_IMPORT_ASSERTION,
        attributed=False,
        forced_exit=2,
        conftest=(
            "import os\nfrom pathlib import Path\n"
            "def pytest_sessionfinish():\n"
            "    if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
            "        Path(os.environ['MUTMUT_FORCED_FAIL_PROOF_PATH']).write_bytes(b'wrong')\n"
        ),
    ),
)


def _stage_runner(
    root: Path, body: str, extra_args: list[str], conftest: str = "", timeout: int = 120
) -> PytestRunner:
    source = "def value():\n    return 2\n"
    for subtree in (root, root / "mutants"):
        package = subtree / "src" / "pkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        tests = subtree / "tests"
        tests.mkdir()
        (tests / "test_value.py").write_text(_IMPORTS + body, encoding="utf-8")
        if conftest:
            (subtree / "conftest.py").write_text(conftest, encoding="utf-8")
    (root / "src" / "pkg" / "mod.py").write_text(source, encoding="utf-8")
    generated, names = mutate_file_contents("mod.py", source)
    assert names, "The attribution probe must exercise real generated trampolines"
    (root / "mutants" / "src" / "pkg" / "mod.py").write_text(generated, encoding="utf-8")
    return PytestRunner(
        MutmutConfig(
            paths_to_mutate=["src/pkg"],
            tests_dir=["tests"],
            clean_run_timeout=120,
            forced_fail_timeout=timeout,
            pytest_add_cli_args=extra_args,
        )
    )


@pytest.mark.parametrize("case", _CASES, ids=[case.name for case in _CASES])
def test_real_child_forced_fail_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: AttributionCase
) -> None:
    """Attribute actual failed reports, preserving unrelated and expected failures."""
    monkeypatch.chdir(tmp_path)
    runner = _stage_runner(tmp_path, case.body, [], case.conftest)
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    assert runner.collect_tests(), runner.last_diagnostic_output
    assert runner.run_forced_fail("pkg.mod.value__mutmut_1") == case.forced_exit, (
        runner.last_diagnostic_output
    )
    assert runner.last_forced_fail_attributed is case.attributed, runner.last_diagnostic_output


def test_import_only_collection_with_continue_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Require a collection proof even when no product call can reach a test body."""
    monkeypatch.chdir(tmp_path)
    runner = _stage_runner(
        tmp_path, _IMPORT_ASSERTION, ["--continue-on-collection-errors", "--maxfail=0"]
    )
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    assert runner.collect_tests(), runner.last_diagnostic_output
    assert runner.run_forced_fail("pkg.mod.value__mutmut_1") != 0
    assert runner.last_forced_fail_attributed is True, runner.last_diagnostic_output


def test_collection_proof_followed_by_timeout_is_not_attributed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep a timed-out phase invalid even after a genuine failed report."""
    monkeypatch.chdir(tmp_path)
    runner = _stage_runner(
        tmp_path,
        _IMPORT_ASSERTION,
        [],
        "import os\nimport time\n"
        "def pytest_sessionfinish():\n"
        "    if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
        "        print('collection completed before hang', flush=True)\n"
        "        time.sleep(30)\n",
        timeout=5,
    )
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    assert runner.run_forced_fail("pkg.mod.value__mutmut_1") == 36
    assert "collection completed before hang" in (runner.last_diagnostic_output or "")
    assert runner.last_forced_fail_attributed is None


@given(payload=st.binary(max_size=96))
@example(payload=b"expected-token")
def test_forced_fail_token_requires_exact_bytes(payload: bytes) -> None:
    """Accept only the armed token and remove every consumed proof file."""
    with TemporaryDirectory(prefix="mutmut-s3-proof-") as directory:
        proof = Path(directory) / "proof"
        proof.write_bytes(payload)
        assert consume_forced_fail_proof(proof, "expected-token") is (payload == b"expected-token")
        assert not proof.exists()


class PhaseAttributionCase(BaseModel):
    """Describe observable whole-phase attribution without reproducing its algorithm."""

    name: str
    body: str
    attributed: bool
    secondary: str = ""
    secondary_name: str = "test_zzz_other.py"
    conftest: str = ""


_COLLECTION_TRY = "\ntry:\n    VALUE = value()\nexcept Exception as exc:\n"
_COLLECTION_TEST = "\ndef test_value():\n    assert VALUE == 2\n"
_LATER_FOREIGN = (
    "\nif os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
    "    raise ValueError('independent collection error')\n"
    "def test_other():\n    assert True\n"
)
_MIXED_GROUP = (
    _COLLECTION_TRY
    + ("    raise ExceptionGroup('mixed', [exc, ValueError('independent')]) from None\n")
    + _COLLECTION_TEST
)
_PHASE_CASES = [
    PhaseAttributionCase(
        name="explicit_collection_cause",
        attributed=True,
        body=_COLLECTION_TRY + "    raise RuntimeError('wrapper') from exc\n" + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="explicit_body_cause",
        attributed=True,
        body="\ndef test_value():\n    try:\n        assert value() == 2\n"
        "    except Exception as exc:\n        raise RuntimeError('wrapper') from exc\n",
    ),
    PhaseAttributionCase(
        name="pure_nested_shared_group",
        attributed=True,
        body=_COLLECTION_TRY + "    raise ExceptionGroup('outer', ["
        "ExceptionGroup('inner', [exc, exc])]) from None\n" + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="group_explicit_cause",
        attributed=True,
        body=_COLLECTION_TRY + "    wrapped = RuntimeError('wrapper')\n"
        "    wrapped.__cause__ = exc\n"
        "    raise ExceptionGroup('pure', [wrapped, exc]) from None\n" + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(name="mixed_group", attributed=False, body=_MIXED_GROUP),
    PhaseAttributionCase(
        name="mixed_group_with_genuine_cause",
        attributed=False,
        body=_COLLECTION_TRY + "    raise ExceptionGroup('mixed', ["
        "ValueError('independent')]) from exc\n" + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="implicit_context",
        attributed=False,
        body=_COLLECTION_TRY + "    raise RuntimeError('independent')\n" + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="suppressed_context",
        attributed=False,
        body=_COLLECTION_TRY
        + "    raise RuntimeError('independent') from None\n"
        + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="cause_cycle",
        attributed=False,
        body=_COLLECTION_TRY + "    wrapped = RuntimeError('cycle')\n"
        "    wrapped.__cause__ = wrapped\n    raise wrapped from wrapped\n" + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="skip_with_explicit_cause",
        attributed=False,
        body=_COLLECTION_TRY + "    raise pytest.skip.Exception('skip', "
        "allow_module_level=True) from exc\n" + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="xfail_with_explicit_cause",
        attributed=False,
        body=_COLLECTION_TRY
        + "    raise pytest.xfail.Exception('xfail') from exc\n"
        + _COLLECTION_TEST,
    ),
    PhaseAttributionCase(
        name="later_foreign_collection",
        attributed=False,
        body=_IMPORT_ASSERTION,
        secondary=_LATER_FOREIGN,
    ),
    PhaseAttributionCase(
        name="earlier_foreign_collection",
        attributed=False,
        body=_IMPORT_ASSERTION,
        secondary=_LATER_FOREIGN,
        secondary_name="test_aaa_other.py",
    ),
    PhaseAttributionCase(
        name="later_mixed_group",
        attributed=False,
        body=_IMPORT_ASSERTION,
        secondary=_MIXED_GROUP,
    ),
    PhaseAttributionCase(
        name="later_foreign_runtime",
        attributed=False,
        body=_BODY,
        secondary="\ndef test_other():\n"
        "    if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
        "        raise ValueError('independent runtime error')\n    assert True\n",
    ),
    *[
        PhaseAttributionCase(
            name=f"later_{hook}_failure",
            attributed=False,
            body=_IMPORT_ASSERTION,
            conftest="import os\nimport pytest\n@pytest.hookimpl(trylast=True)\n"
            f"def {hook}():\n"
            "    if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
            "        raise RuntimeError('independent finalization error')\n",
        )
        for hook in ("pytest_sessionfinish", "pytest_unconfigure")
    ],
    PhaseAttributionCase(
        name="later_keyboard_interrupt",
        attributed=False,
        body=_BODY,
        secondary="\ndef test_other():\n"
        "    if os.environ.get('MUTANT_UNDER_TEST') == 'fail':\n"
        "        raise KeyboardInterrupt('independent interruption')\n    assert True\n",
    ),
]


@pytest.mark.parametrize("case", _PHASE_CASES, ids=[case.name for case in _PHASE_CASES])
def test_whole_phase_forced_fail_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: PhaseAttributionCase
) -> None:
    """Require all failed reports and finalization to support the forced-fail proof."""
    monkeypatch.chdir(tmp_path)
    runner = _stage_runner(
        tmp_path, case.body, ["--continue-on-collection-errors", "--maxfail=0"], case.conftest
    )
    if case.secondary:
        for subtree in (tmp_path, tmp_path / "mutants"):
            (subtree / "tests" / case.secondary_name).write_text(
                _IMPORTS + case.secondary, encoding="utf-8"
            )
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    assert runner.collect_tests(), runner.last_diagnostic_output
    assert runner.run_forced_fail("pkg.mod.value__mutmut_1") not in (0, 36), (
        runner.last_diagnostic_output
    )
    assert runner.last_forced_fail_attributed is case.attributed, runner.last_diagnostic_output
