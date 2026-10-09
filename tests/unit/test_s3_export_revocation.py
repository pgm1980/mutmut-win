"""S3-009: failed revocation is an explicit CLI error, never a fresh export."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli


@pytest.mark.parametrize("collision", ["locked-file", "directory"])
def test_export_revocation_error_identifies_stale_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, collision: str
) -> None:
    """Real Windows sharing and directory collisions keep bytes and report refusal."""
    monkeypatch.chdir(tmp_path)
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    old_export = b'{"score":100.0,"previous":true}\n'
    if collision == "directory":
        artifact.mkdir()
        retained = artifact / "owner.txt"
        retained.write_bytes(old_export)
        result = CliRunner().invoke(cli, ["export-cicd-stats"])
        assert retained.read_bytes() == old_export
    else:
        artifact.write_bytes(old_export)
        identity = artifact.stat()
        # CPython's Windows file handle omits FILE_SHARE_DELETE; hold it through return.
        with artifact.open("rb") as held:
            result = CliRunner().invoke(cli, ["export-cicd-stats"])
            assert held.read() == old_export
            after = artifact.stat()
            assert (after.st_dev, after.st_ino) == (identity.st_dev, identity.st_ino)
        assert artifact.read_bytes() == old_export
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert str(artifact) in result.stderr
    assert "Could not revoke previous CI/CD artifact" in result.stderr
    assert "stale" in result.stderr
    assert "must not be used" in result.stderr
    assert "Saved CI/CD stats" not in result.output
    assert "Traceback (most recent call last)" not in result.output


def test_unlocked_previous_export_is_revoked_before_empty_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Healthy revocation removes the old artifact even when no new result exists."""
    monkeypatch.chdir(tmp_path)
    artifact = Path("mutants/mutmut-cicd-stats.json")
    artifact.parent.mkdir()
    artifact.write_bytes(b'{"score":100.0}\n')
    result = CliRunner().invoke(cli, ["export-cicd-stats"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "No results found" in result.stderr
    assert not artifact.exists()
