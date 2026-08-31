"""Adversarial contracts for the immutable pytest boundary schema v2."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest

import mutmut_win.pytest_boundary as pytest_boundary_module
from mutmut_win.atomic_file import create_exclusive_random_bytes
from mutmut_win.exceptions import PytestBoundaryError
from mutmut_win.pytest_boundary import PytestBoundary, prepare_pytest_boundary


def _project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "Project With Space"
    staging = project / "mutants"
    staging.mkdir(parents=True)
    return project, staging


def _prepare(project: Path, staging: Path, tests_dir: list[str] | None = None) -> PytestBoundary:
    return prepare_pytest_boundary(
        project_root=project,
        staging_root=staging,
        tests_dir=[] if tests_dir is None else tests_dir,
    )


def _keep_file_identity_live(path: Path) -> tuple[int, int]:
    """Prevent immediate inode reuse while a replacement is under test."""

    identity = path.stat().st_dev, path.stat().st_ino
    os.link(path, path.with_name(f".{path.name}.identity-anchor"))
    return identity


def test_schema_v2_round_trip_binds_root_config_and_allowed_paths(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    tests = staging / "tests"
    tests.mkdir()

    boundary = _prepare(project, staging, ["tests"])
    restored = PytestBoundary.from_dict(boundary.to_dict())

    assert boundary.schema == 2
    assert restored.arguments() == boundary.arguments()
    directories, files = restored.canonical_allowed_test_paths()
    assert directories == (staging.resolve(),)
    assert files == ()
    assert boundary.staging_dev == staging.stat().st_dev
    assert boundary.staging_ino == staging.stat().st_ino
    assert boundary.config_dev == Path(boundary.config_path).stat().st_dev
    assert boundary.config_ino == Path(boundary.config_path).stat().st_ino


def test_same_byte_config_replacement_is_identity_drift(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    config = staging / "pytest.ini"
    payload = b"[pytest]\n"
    config.write_bytes(payload)
    boundary = _prepare(project, staging)

    original_identity = _keep_file_identity_live(config)
    config.unlink()
    config.write_bytes(payload)
    assert (config.stat().st_dev, config.stat().st_ino) != original_identity

    with pytest.raises(PytestBoundaryError, match="identity changed"):
        boundary.arguments()


def test_in_place_config_tamper_still_fails_digest_validation(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    config = staging / "pytest.ini"
    config.write_bytes(b"[pytest]\n")
    boundary = _prepare(project, staging)

    config.write_bytes(b"[pytest]\naddopts = --collect-only\n")

    with pytest.raises(PytestBoundaryError, match="changed after the run boundary"):
        boundary.arguments()


def test_config_replacement_during_validation_is_caught_after_handle_read(
    tmp_path: Path,
) -> None:
    project, staging = _project(tmp_path)
    config = staging / "pytest.ini"
    payload = b"[pytest]\n"
    config.write_bytes(payload)
    boundary = _prepare(project, staging)
    replacement = staging / "replacement.ini"
    replacement.write_bytes(payload)
    original_read = pytest_boundary_module._read_bound_config

    def replace_after_read(path: Path, *, expected_dev: int, expected_ino: int) -> bytes:
        read_payload = original_read(
            path,
            expected_dev=expected_dev,
            expected_ino=expected_ino,
        )
        replacement.replace(config)
        return read_payload

    with (
        patch(
            "mutmut_win.pytest_boundary._read_bound_config",
            side_effect=replace_after_read,
        ),
        pytest.raises(PytestBoundaryError, match="config identity changed"),
    ):
        boundary.arguments()


def test_root_replacement_is_identity_drift_even_with_same_config_bytes(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    config = staging / "pytest.ini"
    payload = b"[pytest]\n"
    config.write_bytes(payload)
    boundary = _prepare(project, staging)
    moved = project / "original-mutants"

    staging.rename(moved)
    staging.mkdir()
    (staging / "pytest.ini").write_bytes(payload)

    with pytest.raises(PytestBoundaryError, match="staging root identity changed"):
        boundary.arguments()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Junction contract")
def test_windows_junction_retarget_is_rejected(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    payload = b"[pytest]\n"
    (staging / "pytest.ini").write_bytes(payload)
    boundary = _prepare(project, staging)
    moved = project / "original-mutants"
    external = tmp_path / "external"
    external.mkdir()
    (external / "pytest.ini").write_bytes(payload)
    staging.rename(moved)
    created = subprocess.run(  # noqa: S603 -- fixed shell and isolated tmp paths
        [
            os.environ["COMSPEC"],
            "/d",
            "/u",
            "/c",
            "mklink",
            "/J",
            str(staging),
            str(external),
        ],
        check=False,
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
    )
    if created.returncode != 0:
        moved.rename(staging)
        pytest.skip(f"Junction creation unavailable: {created.stderr or created.stdout}")
    try:
        with pytest.raises(PytestBoundaryError, match=r"redirected|reparse point"):
            boundary.arguments()
    finally:
        staging.rmdir()
        moved.rename(staging)


def test_random_fallback_preserves_fixed_and_random_name_collisions(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    fixed_collision = staging / ".mutmut-win-pytest.ini"
    fixed_payload = b"USER-OWNED-FIXTURE\r\n"
    fixed_collision.write_bytes(fixed_payload)
    first_token = "a" * 32
    second_token = "b" * 32
    random_collision = staging / f".mutmut-win-pytest-{first_token}.ini"
    random_payload = b"ANOTHER-USER-FILE\n"
    random_collision.write_bytes(random_payload)

    with patch(
        "mutmut_win.atomic_file.secrets.token_hex",
        side_effect=[first_token, second_token],
    ):
        boundary = _prepare(project, staging)

    assert fixed_collision.read_bytes() == fixed_payload
    assert random_collision.read_bytes() == random_payload
    assert Path(boundary.config_path).name == f".mutmut-win-pytest-{second_token}.ini"
    assert Path(boundary.config_path).read_bytes() == b"[pytest]\n"


def test_exclusive_random_helper_never_overwrites_after_collision_exhaustion(
    tmp_path: Path,
) -> None:
    token = "c" * 32
    collision = tmp_path / f"private-{token}.ini"
    sentinel = b"USER-SENTINEL\n"
    collision.write_bytes(sentinel)

    with (
        patch("mutmut_win.atomic_file.secrets.token_hex", return_value=token),
        pytest.raises(FileExistsError, match="unique exclusive file"),
    ):
        create_exclusive_random_bytes(
            tmp_path,
            b"[pytest]\n",
            prefix="private-",
            suffix=".ini",
        )

    assert collision.read_bytes() == sentinel
    assert list(tmp_path.iterdir()) == [collision]


def test_random_fallback_replacement_before_freeze_is_rejected(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    replacement = staging / "replacement.ini"
    replacement.write_bytes(b"[pytest]\n")
    original_snapshot = pytest_boundary_module._real_path_snapshot

    def replace_before_snapshot(
        path: Path,
        *,
        kind: Literal["directory", "file"],
        description: str,
    ) -> tuple[Path, os.stat_result]:
        if description == "staged pytest config" and path.name.startswith(".mutmut-win-pytest-"):
            replacement.replace(path)
        return original_snapshot(path, kind=kind, description=description)

    with (
        patch(
            "mutmut_win.pytest_boundary._real_path_snapshot",
            side_effect=replace_before_snapshot,
        ),
        pytest.raises(PytestBoundaryError, match="identity changed before freeze"),
    ):
        _prepare(project, staging)


def test_multi_directory_fallback_matches_pytest_search_order(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    first = staging / "tests" / "a"
    second = staging / "tests" / "b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    nested_config = first / "pytest.ini"
    nested_config.write_text("[pytest]\nmarkers = nested: nested\n", encoding="utf-8")

    boundary = _prepare(project, staging, ["tests/a", "tests/b"])

    assert Path(boundary.config_path) == nested_config.resolve()


def test_common_ancestor_config_precedes_nested_config(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    first = staging / "tests" / "a"
    second = staging / "tests" / "b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    common_config = staging / "tests" / "pytest.ini"
    common_config.write_text("[pytest]\nmarkers = common: common\n", encoding="utf-8")
    (first / "pytest.ini").write_text("[pytest]\nmarkers = nested: nested\n", encoding="utf-8")

    boundary = _prepare(project, staging, ["tests/a", "tests/b"])

    assert Path(boundary.config_path) == common_config.resolve()


def test_plain_setup_py_directory_does_not_suppress_per_directory_fallback(
    tmp_path: Path,
) -> None:
    project, staging = _project(tmp_path)
    first = staging / "tests" / "a"
    second = staging / "tests" / "b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    nested_config = first / "pytest.ini"
    nested_config.write_text("[pytest]\n", encoding="utf-8")
    (staging / "setup.py").mkdir()

    boundary = _prepare(project, staging, ["tests/a", "tests/b"])

    assert Path(boundary.config_path) == nested_config.resolve()


def test_regular_setup_py_suppresses_per_directory_fallback_like_pytest(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    first = staging / "tests" / "a"
    second = staging / "tests" / "b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (staging / "setup.py").write_text("# regular setup file\n", encoding="utf-8")

    boundary = _prepare(project, staging, ["tests/a", "tests/b"])

    assert Path(boundary.config_path).name.startswith(".mutmut-win-pytest-")


def test_setup_py_link_cannot_change_config_discovery(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    tests = staging / "tests"
    tests.mkdir()
    external_setup = tmp_path / "external-setup.py"
    external_setup.write_text("# external\n", encoding="utf-8")
    setup_link = staging / "setup.py"
    try:
        setup_link.symlink_to(external_setup)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    with pytest.raises(PytestBoundaryError, match=r"setup.py.*link or reparse"):
        _prepare(project, staging, ["tests"])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Junction contract")
def test_setup_py_junction_is_rejected_before_fallback_decision(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    tests = staging / "tests"
    tests.mkdir()
    external = tmp_path / "external-setup-directory"
    external.mkdir()
    setup_junction = staging / "setup.py"
    created = subprocess.run(  # noqa: S603 -- fixed shell and isolated tmp paths
        [
            os.environ["COMSPEC"],
            "/d",
            "/u",
            "/c",
            "mklink",
            "/J",
            str(setup_junction),
            str(external),
        ],
        check=False,
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
    )
    if created.returncode != 0:
        pytest.skip(f"Junction creation unavailable: {created.stderr or created.stdout}")
    try:
        with pytest.raises(PytestBoundaryError, match=r"setup.py.*link or reparse"):
            _prepare(project, staging, ["tests"])
    finally:
        setup_junction.rmdir()


def test_config_looking_directory_is_ignored_like_pytest_is_file(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    (staging / "pytest.ini").mkdir()

    boundary = _prepare(project, staging)

    assert Path(boundary.config_path).name.startswith(".mutmut-win-pytest-")


@pytest.mark.parametrize(
    ("major", "expected_name"),
    [("8.2.2", "pytest.ini"), ("9.0.3", "pytest.toml")],
)
def test_pytest_8_and_9_config_name_precedence(
    tmp_path: Path,
    major: str,
    expected_name: str,
) -> None:
    installed_major = int(pytest.__version__.split(".", 1)[0])
    expected_major = int(major.split(".", 1)[0])
    if installed_major != expected_major:
        pytest.skip("config parsing must use the matching installed pytest major")
    project, staging = _project(tmp_path)
    (staging / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (staging / "pytest.toml").write_text("[pytest]\n", encoding="utf-8")

    with patch("mutmut_win.pytest_boundary.importlib.metadata.version", return_value=major):
        boundary = _prepare(project, staging)

    assert Path(boundary.config_path).name == expected_name


def test_unknown_pytest_major_fails_closed(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)

    with (
        patch("mutmut_win.pytest_boundary.importlib.metadata.version", return_value="10.0.0"),
        pytest.raises(PytestBoundaryError, match="no validated config-discovery"),
    ):
        _prepare(project, staging)


def test_pytest_before_8_2_fails_closed(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)

    with (
        patch("mutmut_win.pytest_boundary.importlib.metadata.version", return_value="8.1.9"),
        pytest.raises(PytestBoundaryError, match=r"8\.1\.9.*no validated"),
    ):
        _prepare(project, staging)


def test_allowed_paths_include_staging_and_only_explicit_external_targets(
    tmp_path: Path,
) -> None:
    project, staging = _project(tmp_path)
    internal = staging / "tests"
    internal.mkdir()
    external_dir = tmp_path / "external suite"
    external_dir.mkdir()
    external_file = tmp_path / "single external test.py"
    external_file.write_text("def test_external(): pass\n", encoding="utf-8")

    boundary = _prepare(
        project,
        staging,
        ["tests", str(external_dir), str(external_file)],
    )
    directories, files = boundary.canonical_allowed_test_paths()
    identities = boundary.canonical_allowed_test_identities()

    assert set(directories) == {staging.resolve(), external_dir.resolve()}
    assert files == (external_file.resolve(),)
    assert identities[0].canonical_path == staging.resolve()
    assert identities[0].kind == "directory"
    assert (identities[0].st_dev, identities[0].st_ino) == (
        staging.stat().st_dev,
        staging.stat().st_ino,
    )
    external_records = {record.canonical_path: record for record in identities[1:]}
    assert external_records[external_dir.resolve()].kind == "directory"
    assert (
        external_records[external_dir.resolve()].st_dev,
        external_records[external_dir.resolve()].st_ino,
    ) == (external_dir.stat().st_dev, external_dir.stat().st_ino)
    assert external_records[external_file.resolve()].kind == "file"
    assert (
        external_records[external_file.resolve()].st_dev,
        external_records[external_file.resolve()].st_ino,
    ) == (external_file.stat().st_dev, external_file.stat().st_ino)


def test_external_test_file_same_byte_replacement_is_rejected(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    external_file = tmp_path / "external.py"
    payload = b"def test_external(): pass\n"
    external_file.write_bytes(payload)
    boundary = _prepare(project, staging, [str(external_file)])

    original_identity = _keep_file_identity_live(external_file)
    external_file.unlink()
    external_file.write_bytes(payload)
    assert (external_file.stat().st_dev, external_file.stat().st_ino) != original_identity

    with pytest.raises(PytestBoundaryError, match="test target identity changed"):
        boundary.canonical_allowed_test_paths()


def test_external_test_directory_replacement_is_rejected(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    external = tmp_path / "external-tests"
    external.mkdir()
    boundary = _prepare(project, staging, [str(external)])
    moved = tmp_path / "original-external-tests"

    external.rename(moved)
    external.mkdir()

    with pytest.raises(PytestBoundaryError, match="test target identity changed"):
        boundary.canonical_allowed_test_identities()


def test_missing_test_target_is_bound_to_absence(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    boundary = _prepare(project, staging, ["not-created-yet"])

    directories, files = boundary.canonical_allowed_test_paths()
    assert directories == (staging.resolve(),)
    assert files == ()
    (staging / "not-created-yet").mkdir()

    with pytest.raises(PytestBoundaryError, match="appeared during the run"):
        boundary.arguments()


@pytest.mark.parametrize("invalid", ["-c", "--rootdir=..", "@outside.args", "bad\n-c"])
def test_tests_dir_accepts_only_test_paths(tmp_path: Path, invalid: str) -> None:
    project, staging = _project(tmp_path)

    with pytest.raises(PytestBoundaryError, match=r"test target|must be paths"):
        _prepare(project, staging, [invalid])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path grammar")
@pytest.mark.parametrize("invalid", [r"C:relative_test.py", r"\rooted_test.py"])
def test_windows_drive_relative_and_root_relative_targets_are_rejected(
    tmp_path: Path,
    invalid: str,
) -> None:
    project, staging = _project(tmp_path)

    with pytest.raises(PytestBoundaryError, match="fully absolute or staging-relative"):
        _prepare(project, staging, [invalid])


def test_paths_with_spaces_and_windows_case_variants_round_trip(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    tests = staging / "Tests With Space"
    tests.mkdir()
    boundary = _prepare(project, staging, ["Tests With Space"])
    payload = boundary.to_dict()
    if sys.platform == "win32":
        payload["staging_root"] = str(payload["staging_root"]).swapcase()
        payload["config_path"] = str(payload["config_path"]).swapcase()

    restored = PytestBoundary.from_dict(payload)
    arguments = restored.arguments()

    assert " " in arguments[1]
    assert any(argument.startswith("--rootdir=") for argument in arguments)


def test_schema_one_payload_is_rejected(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    payload = _prepare(project, staging).to_dict()
    payload["schema"] = 1

    with pytest.raises(PytestBoundaryError, match="Unsupported pytest boundary schema 1"):
        PytestBoundary.from_dict(payload).arguments()


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("staging_dev", -1),
        ("staging_ino", -1),
        ("config_dev", -1),
        ("config_ino", 0),
    ],
)
def test_boundary_deserialization_rejects_unusable_identities(
    tmp_path: Path,
    field: str,
    invalid: int,
) -> None:
    project, staging = _project(tmp_path)
    payload = _prepare(project, staging).to_dict()
    payload[field] = invalid

    with pytest.raises(PytestBoundaryError, match="malformed pytest boundary"):
        PytestBoundary.from_dict(payload)


def test_schema_preserves_zero_device_and_wide_inode_values(tmp_path: Path) -> None:
    project, staging = _project(tmp_path)
    payload = _prepare(project, staging).to_dict()
    payload["staging_dev"] = 0
    payload["staging_ino"] = 2**100 + 123

    restored = PytestBoundary.from_dict(payload)

    assert restored.staging_dev == 0
    assert restored.staging_ino == 2**100 + 123


@pytest.mark.parametrize("invalid_kind", [[], {}, 1, None])
def test_test_path_deserialization_wraps_malformed_kind(
    tmp_path: Path,
    invalid_kind: object,
) -> None:
    project, staging = _project(tmp_path)
    tests = staging / "tests"
    tests.mkdir()
    payload = _prepare(project, staging, ["tests"]).to_dict()
    test_paths = payload["test_paths"]
    assert isinstance(test_paths, list)
    snapshot = test_paths[0]
    assert isinstance(snapshot, dict)
    snapshot["kind"] = invalid_kind

    with pytest.raises(PytestBoundaryError, match="malformed pytest test-path boundary"):
        PytestBoundary.from_dict(payload)


@pytest.mark.parametrize(("field", "invalid"), [("st_dev", -1), ("st_ino", -1)])
def test_test_path_deserialization_rejects_unusable_identities(
    tmp_path: Path,
    field: str,
    invalid: int,
) -> None:
    project, staging = _project(tmp_path)
    tests = staging / "tests"
    tests.mkdir()
    payload = _prepare(project, staging, ["tests"]).to_dict()
    test_paths = payload["test_paths"]
    assert isinstance(test_paths, list)
    snapshot = test_paths[0]
    assert isinstance(snapshot, dict)
    snapshot[field] = invalid

    with pytest.raises(PytestBoundaryError, match="malformed pytest test-path identity"):
        PytestBoundary.from_dict(payload)
