"""S3-012: decoder limits cannot escape metadata recovery or confer authority."""

from pathlib import Path

import pytest

from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.models import SourceFileMutationData, read_owned_source_metadata


@pytest.mark.parametrize("heal", [True, False])
@pytest.mark.parametrize(
    "payload", ['{"x":' + "1" * 4301 + "}", "[" * 20000 + "0" + "]" * 20000],
    ids=["integer-limit", "deep-json"],
)
def test_decoder_limits_reset_metadata_without_false_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str, heal: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both decoder failures reset previous authority; read-only reads preserve bytes."""
    monkeypatch.chdir(tmp_path)
    source = Path("module.py")
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    output = Path("mutants/module.py")
    healthy_names, warnings, reused = create_mutants_for_file(source, output)
    assert healthy_names and not warnings and not reused
    model = SourceFileMutationData(path="module.py")
    model.load()
    assert model.source_hash and model.generation_fingerprint and model.generated_hash
    assert model.exit_code_by_key
    assert read_owned_source_metadata(model.meta_path) is not None
    original_source = source.read_bytes()
    generated = output.read_bytes()
    model.meta_path.write_bytes(payload.encode())

    assert read_owned_source_metadata(model.meta_path) is None
    assert model.meta_path.read_bytes() == payload.encode()
    model.load(heal_corrupt=heal)
    assert not model.exit_code_by_key
    assert model.source_hash is model.generated_hash is model.generation_fingerprint is None
    assert model.source_mtime is model.source_size is None
    assert not model.durations_by_key
    assert not model.estimated_time_of_tests_by_mutant
    assert not model.type_check_error_by_key
    if heal:
        assert not model.meta_path.exists()
        assert "corrupted meta file" in capsys.readouterr().err
    else:
        assert model.meta_path.read_bytes() == payload.encode()
        assert not capsys.readouterr().err
    assert source.read_bytes() == original_source
    assert output.read_bytes() == generated
    rebuilt_names, rebuilt_warnings, rebuilt_reused = create_mutants_for_file(source, output)
    assert rebuilt_names == healthy_names
    assert not rebuilt_warnings
    assert not rebuilt_reused
    assert read_owned_source_metadata(model.meta_path) is not None
    assert source.read_bytes() == original_source
