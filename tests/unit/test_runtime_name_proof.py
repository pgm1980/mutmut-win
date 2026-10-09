"""Adversarial validation of the bounded clean runtime-name journal."""

from __future__ import annotations

import hashlib
import json
import mmap
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win import _state
from mutmut_win import runtime_names as names
from mutmut_win.exceptions import MutantNameDispatchError
from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.orchestrator import _verify_runtime_mutant_names
from mutmut_win.stats import MutmutStats
from mutmut_win.trampoline import trampoline_impl

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def recorder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[names._Recorder]:
    directory = tmp_path / "proof"
    directory.mkdir()
    monkeypatch.setenv("MUTANT_UNDER_TEST", "")
    monkeypatch.setenv("MUTMUT_CLEAN_NAMES_PATH", str(directory))
    monkeypatch.setenv("MUTMUT_CLEAN_NAMES_TOKEN", "a" * 64)
    monkeypatch.setattr(names, "_recorder", None)
    monkeypatch.setattr(names, "_installed", True)
    monkeypatch.setattr(names, "_exit_code", None)
    names.start_pytest()
    actual = names._ensure_recorder()
    try:
        yield actual
    finally:
        actual.control.close()


def _finish(recorder: names._Recorder) -> frozenset[str]:
    names.finish_pytest(0)
    names._finish_at_exit()
    return names.collect_runtime_names(recorder.directory, recorder.ticket.token)


@given(st.text(min_size=1, max_size=100))
def test_entry_roundtrip_preserves_exact_unicode_name(value: str) -> None:
    entry = names._Entry(kind="name", value=value)
    assert names._Entry.model_validate_json(entry.model_dump_json()) == entry


@given(st.integers(min_value=1, max_value=2**31 - 1), st.binary(min_size=16, max_size=16))
def test_ticket_roundtrip_preserves_identity(pid: int, identifier: bytes) -> None:
    ticket = names._Ticket(
        schema_version=3,
        phase="clean",
        generation_policy="clean-called-v3",
        participant_id=identifier.hex(),
        parent_participant_id=None,
        issuer_pid=pid,
        token="a" * 64,
    )
    assert names._Ticket.model_validate_json(ticket.model_dump_json()) == ticket


@pytest.mark.parametrize("raw", [b"{}", b"broken", b"[]", b'{"kind":"unknown","value":"x"}'])
def test_entry_rejects_malformed_frames(raw: bytes) -> None:
    with pytest.raises(ValidationError):
        names._Entry.model_validate_json(raw)


@pytest.mark.parametrize("observed", [[], ["pkg.x_a"], ["pkg.x_a", "pkg.x_b", "pkg.x_a"]])
def test_fresh_root_exact_names_and_valid_empty(
    recorder: names._Recorder, observed: list[str]
) -> None:
    for name in observed:
        names.record_runtime_name(name)
    assert _finish(recorder) == set(observed)


@pytest.mark.parametrize(
    "fault", ["pending", "serialization", "name_limit", "byte_limit", "partial_record", "ready"]
)
def test_second_publication_failure_is_sticky_after_old_name(
    recorder: names._Recorder, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    names.record_runtime_name("pkg.x_a")
    events = names._path(recorder.directory, recorder.ticket, "events")
    original_bytes = events.read_bytes()
    original_limit = names._MAX_BYTES

    def fail_serialization(_entry: names._Entry) -> str:
        raise ValueError("injected serialization failure")

    def fail_record(path: Path, _entry: names._Entry) -> None:
        with path.open("ab") as stream:
            stream.write(b'{"kind":')
        raise OSError("injected partial record failure")

    original_append = names._append

    def fail_ready(actual: names._Recorder, entry: names._Entry) -> None:
        original_append(actual, entry)
        actual.control.close()

    if fault == "pending":
        recorder.control.close()
    elif fault == "serialization":
        monkeypatch.setattr(names._Entry, "model_dump_json", fail_serialization)
    elif fault == "name_limit":
        monkeypatch.setattr(names, "_MAX_NAMES", 1)
    elif fault == "byte_limit":
        monkeypatch.setattr(names, "_MAX_BYTES", len(original_bytes))
    elif fault == "partial_record":
        monkeypatch.setattr(names, "_write_part", fail_record)
    else:
        monkeypatch.setattr(names, "_append", fail_ready)

    with pytest.raises((ValueError, OSError)):
        names.record_runtime_name("pkg.x_b")
    assert recorder.invalid
    if fault in {"pending", "ready"}:
        # Invalidity is now persisted in the existing control file even if a
        # new marker cannot be created; inspect it through a coherent view.
        with (
            names._path(recorder.directory, recorder.ticket, "control").open("rb") as stream,
            mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as control,
        ):
            assert (
                control[0] == names._INVALID
                or names._path(recorder.directory, recorder.ticket, "invalid").exists()
            )
    else:
        assert recorder.control[0] == names._INVALID
    with pytest.raises(RuntimeError, match="closed or invalid"):
        names.record_runtime_name("pkg.x_a")
    assert events.read_bytes().startswith(original_bytes)
    monkeypatch.setattr(names, "_MAX_BYTES", original_limit)
    with pytest.raises((ValueError, OSError)):
        _finish(recorder)


def test_closed_child_map_and_failed_poison_marker_cannot_reuse_ready(
    recorder: names._Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    child_ticket = names._create_ticket(recorder.directory, recorder.ticket)
    names._begin(recorder)
    names._append(recorder, names._Entry(kind="child", value=child_ticket.participant_id))
    recorder.control[0] = names._READY
    monkeypatch.setattr(names, "_recorder", None)
    names._resume_spawn(child_ticket.model_dump_json())
    child = names._ensure_recorder()
    names.record_runtime_name("pkg.x_a")
    _pid, entries = names._read_part(recorder.directory, child_ticket)
    assert entries == [names._Entry(kind="name", value="pkg.x_a")]
    child.control.close()
    original_touch = Path.touch

    def fail_marker(path: Path, *args: object, **kwargs: object) -> None:
        if path.suffix == ".invalid":
            raise PermissionError("injected poison marker denial")
        original_touch(path, *args, **kwargs)

    monkeypatch.setattr(Path, "touch", fail_marker)
    with pytest.raises((PermissionError, ValueError)):
        names.record_runtime_name("pkg.x_b")
    with pytest.raises((PermissionError, RuntimeError)):
        names.record_runtime_name("pkg.x_a")
    assert child.invalid
    monkeypatch.setattr(names, "_recorder", recorder)
    with pytest.raises(ValueError, match="runtime-name"):
        _finish(recorder)


def test_late_call_invalidates_already_closed_root(recorder: names._Recorder) -> None:
    names.record_runtime_name("pkg.x_a")
    assert _finish(recorder) == {"pkg.x_a"}
    with pytest.raises(RuntimeError, match="closed or invalid"):
        names.record_runtime_name("pkg.x_b")
    with pytest.raises(ValueError, match="runtime-name"):
        names.collect_runtime_names(recorder.directory, recorder.ticket.token)


@pytest.mark.parametrize("exit_code", [1, 2, 3, 4, 5, 36])
def test_root_failure_never_becomes_complete(recorder: names._Recorder, exit_code: int) -> None:
    names.record_runtime_name("pkg.x_a")
    names.finish_pytest(exit_code)
    names._finish_at_exit()
    with pytest.raises(ValueError, match="incomplete"):
        names.collect_runtime_names(recorder.directory, recorder.ticket.token)


@pytest.mark.parametrize(
    "damage",
    [
        "missing_control",
        "missing_events",
        "missing_parent",
        "extra_file",
        "wrong_nonce",
        "wrong_phase",
        "wrong_policy",
        "zero_owner",
        "wrong_owner",
        "unready",
        "partial",
        "blank_record",
        "missing_phase",
        "missing_policy",
    ],
)
def test_reader_rejects_damaged_current_proof(recorder: names._Recorder, damage: str) -> None:
    names.record_runtime_name("pkg.x_a")
    assert _finish(recorder) == {"pkg.x_a"}
    directory = recorder.directory
    control_path = names._path(directory, recorder.ticket, "control")
    events_path = names._path(directory, recorder.ticket, "events")
    parent_path = directory / "parent.json"
    if damage.startswith("missing_") and damage[8:] in {"control", "events", "parent"}:
        {"control": control_path, "events": events_path, "parent": parent_path}[damage[8:]].unlink()
    elif damage == "extra_file":
        (directory / "foreign.invalid").write_bytes(b"foreign")
    elif damage == "wrong_nonce":
        parent = json.loads(parent_path.read_text(encoding="utf-8"))
        parent["token"] = "b" * 64
        parent_path.write_text(json.dumps(parent), encoding="utf-8")
    elif damage == "partial":
        with events_path.open("ab") as events:
            events.write(b'{"kind":')
    else:
        with control_path.open("r+b") as stream, mmap.mmap(stream.fileno(), 0) as control:
            if damage in {"zero_owner", "wrong_owner"}:
                control[8:16] = (0 if damage == "zero_owner" else os.getpid() + 100_000).to_bytes(
                    8, "little"
                )
            elif damage == "unready":
                control[0] = names._UNREADY
            elif damage == "blank_record":
                events_path.write_bytes(b"\n")
                control[16:24] = (1).to_bytes(8, "little")
            else:
                parent = json.loads(parent_path.read_text(encoding="utf-8"))
                if damage == "wrong_phase":
                    parent["phase"] = "stats"
                elif damage == "wrong_policy":
                    parent["generation_policy"] = "clean-called-v2"
                else:
                    del parent["phase" if damage == "missing_phase" else "generation_policy"]
                    parent_path.write_text(json.dumps(parent), encoding="utf-8")
                raw = json.dumps(parent).encode("utf-8")
                control[4:8] = len(raw).to_bytes(4, "little")
                control[64 : 64 + len(raw)] = raw
    with pytest.raises((ValueError, OSError)):
        names.collect_runtime_names(directory, recorder.ticket.token)


@pytest.mark.parametrize("kind", ["missing", "unready", "orphan", "foreign_owner"])
def test_child_ticket_cannot_disappear_or_change_owner(
    recorder: names._Recorder, kind: str
) -> None:
    child = names._create_ticket(recorder.directory, recorder.ticket)
    if kind != "orphan":
        names._begin(recorder)
        names._append(recorder, names._Entry(kind="child", value=child.participant_id))
        recorder.control[0] = names._READY
    if kind == "missing":
        names._path(recorder.directory, child, "control").unlink()
    elif kind == "foreign_owner":
        path = names._path(recorder.directory, child, "control")
        with path.open("r+b") as stream, mmap.mmap(stream.fileno(), 0) as control:
            bad = child.model_copy(update={"issuer_pid": child.issuer_pid + 1})
            raw = bad.model_dump_json().encode("utf-8")
            control[4:8] = len(raw).to_bytes(4, "little")
            control[64 : 64 + len(raw)] = raw
            control[8:16] = (os.getpid() + 1).to_bytes(8, "little")
            control[0] = names._READY
            control[1] = 1
    with pytest.raises((ValueError, OSError)):
        _finish(recorder)


def test_real_trampoline_threads_preserve_unique_names(recorder: names._Recorder) -> None:
    module = ModuleType("thread_target")
    # Controlled engine template plus fixed generated fixture functions only.
    exec(  # noqa: S102
        trampoline_impl + "\n".join(f"def function_{n}(): return {n}\n" for n in range(64)),
        module.__dict__,
    )

    def call(number: int) -> int:
        function = getattr(module, f"function_{number % 64}")
        return int(module._mutmut_trampoline(function, {}, (), {}))

    with ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(call, range(512)))
    assert result == [number % 64 for number in range(512)]
    assert _finish(recorder) == {f"thread_target.function_{number}" for number in range(64)}


@settings(max_examples=20)
@given(st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=20))
def test_entry_frames_are_individually_complete(observations: list[str]) -> None:
    raw = b"".join(
        names._Entry(kind="name", value=value).model_dump_json().encode("utf-8") + b"\n"
        for value in observations
    )
    actual = [names._Entry.model_validate_json(line).value for line in raw.splitlines()]
    assert actual == observations


def test_event_growth_does_not_resize_fixed_control(recorder: names._Recorder) -> None:
    expected = {f"pkg.x_function_{number}_" + "a" * 100 for number in range(200)}
    for name in expected:
        names.record_runtime_name(name)
    assert names._path(recorder.directory, recorder.ticket, "events").stat().st_size > 4096
    assert names._path(recorder.directory, recorder.ticket, "control").stat().st_size == 4096
    assert _finish(recorder) == expected


def test_default_name_limit_invalidates_without_truncation(recorder: names._Recorder) -> None:
    recorder.names = {f"existing_{n}" for n in range(100_000)}
    with pytest.raises(ValueError, match="name limit exceeded"):
        names.record_runtime_name("new_name")
    assert recorder.control[0] == names._INVALID
    assert "new_name" not in recorder.names
    with pytest.raises(ValueError, match="incomplete"):
        _finish(recorder)


def test_generated_methods_recursion_and_unused_aliases_record_only_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recorder: names._Recorder
) -> None:
    monkeypatch.chdir(tmp_path)
    source = Path("src/pkg/mod.py")
    source.parent.mkdir(parents=True)
    source.write_text(
        "def recurse(n):\n    return recurse(n - 1) if n else 2\n"
        "def unused():\n    return 7\n"
        "class Box:\n    def value(self):\n        return 2\n"
        "    @staticmethod\n    def static():\n        return 3\n"
        "    @classmethod\n    def klass(cls):\n        return 4\n",
        encoding="utf-8",
    )
    target = Path("mutants") / source
    generated_names, _, _ = create_mutants_for_file(source, target)
    assert generated_names
    code = target.read_text(encoding="utf-8")
    canonical = ModuleType("pkg.mod")
    alias = ModuleType("src.pkg.mod")
    # Engine-generated controlled fixture code under two real module namespaces.
    exec(compile(code, str(target), "exec"), canonical.__dict__)  # noqa: S102
    # The second namespace is loaded separately to exercise actual alias calls.
    exec(compile(code, str(target), "exec"), alias.__dict__)  # noqa: S102
    monkeypatch.setattr(_state, "_cached_max_stack_depth", 0)
    assert alias.recurse(3) == 2
    assert alias.Box().value() == 2
    assert alias.Box.static() == 3
    assert alias.Box.klass() == 4
    assert recorder.names == {
        "src.pkg.mod.x_recurse",
        "src.pkg.mod.xǁBoxǁvalue",
        "src.pkg.mod.xǁBoxǁstatic",
    }
    generated = set(
        json.loads(target.with_name(target.name + ".meta").read_text())["exit_code_by_key"]
    )
    assert not any("klass" in name or "unused" in name for name in recorder.names)
    assert not any("klass" in name for name in generated)
    with pytest.raises(MutantNameDispatchError, match="cannot address"):
        _verify_runtime_mutant_names(
            generated, MutmutStats(), runtime_names=frozenset(recorder.names)
        )
    canonical.recurse(1)
    canonical.Box().value()
    canonical.Box.static()
    _verify_runtime_mutant_names(generated, MutmutStats(), runtime_names=_finish(recorder))


def test_old_generation_policy_cannot_reuse_trampoline_without_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = Path("mod.py")
    source.write_text("def value():\n    return 2\n", encoding="utf-8")
    output = Path("mutants/mod.py")
    assert create_mutants_for_file(source, output)[0]
    meta = output.with_name(output.name + ".meta")
    data = json.loads(meta.read_text(encoding="utf-8"))
    old_policy = json.dumps(
        {
            "source_newline_policy": "preserve-v1",
            "profile": "advanced",
            "do_not_mutate_patterns": [],
            "covered_lines": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    data["generation_fingerprint"] = hashlib.sha256(old_policy.encode()).hexdigest()
    meta.write_text(json.dumps(data), encoding="utf-8")
    assert not create_mutants_for_file(source, output)[2]
    assert create_mutants_for_file(source, output)[2]


def test_old_canonical_stats_cannot_neutralize_fresh_alias_calls() -> None:
    stats = MutmutStats(tests_by_mangled_function_name={"pkg.mod.x_value": {"old_test"}})
    with pytest.raises(MutantNameDispatchError, match="clean run cannot address"):
        _verify_runtime_mutant_names(
            {"pkg.mod.x_value__mutmut_1"}, stats, runtime_names=frozenset({"src.pkg.mod.x_value"})
        )
