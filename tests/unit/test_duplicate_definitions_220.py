"""Adversarial MW220-016 coverage for repeated same-named definitions."""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path
from typing import cast

import libcst as cst
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from mutmut_win.config import MutmutConfig
from mutmut_win.constants import Profile
from mutmut_win.db import load_results, save_results
from mutmut_win.file_setup import get_mutant_name
from mutmut_win.models import SourceFileMutationData
from mutmut_win.mutant_diff import (
    _find_function_in_scope,
    apply_mutant,
    get_diff_for_mutant,
)
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.test_mapping import (
    FunctionDefinitionLocation,
    function_definition_location_from_key,
    orig_function_and_class_names_from_key,
    tests_for_mutant_names,
)
from mutmut_win.trampoline import CLASS_NAME_SEPARATOR, mangle_function_name
from mutmut_win.type_checker_filter import is_mutated_method_name as is_typecheck_mutant_name

_SEP = CLASS_NAME_SEPARATOR
#: U+FF2B FULLWIDTH LATIN CAPITAL LETTER K - NFKC-equivalent to "K".
_FULLWIDTH_K = "\uff2b"
#: U+FF23 FULLWIDTH LATIN CAPITAL LETTER C - NFKC-equivalent to "C".
_FULLWIDTH_C = "\uff23"
_DUPLICATE_SOURCE = """\
def f():
    return 10
first_f = f
def f():
    return 20
second_f = f

class C:
    def m(self):
        return 30
    first_m = m
    def m(self):
        return 40
FirstC = C

class C:
    def m(self):
        return 50
"""

_EXPECTED_LOCAL_NAMES = (
    "x_f__mutmut_1",
    f"x_f{_SEP}2__mutmut_1",
    f"x{_SEP}C{_SEP}m__mutmut_1",
    f"x{_SEP}C{_SEP}m{_SEP}2__mutmut_1",
    f"x{_SEP}C{_SEP}m{_SEP}3__mutmut_1",
)


def _generated_duplicate_module() -> tuple[str, tuple[str, ...]]:
    generated, names = mutate_file_contents(
        "src/mod.py",
        _DUPLICATE_SOURCE,
        active_profile=Profile.BASIC,
    )
    return generated, tuple(names)


def _runtime_values(namespace: dict[str, object]) -> tuple[int, ...]:
    first_f = cast("object", namespace["first_f"])
    second_f = cast("object", namespace["second_f"])
    first_class = cast("type[object]", namespace["FirstC"])
    current_class = cast("type[object]", namespace["C"])
    first_instance = first_class()
    current_instance = current_class()
    return (
        cast("int", first_f()),  # type: ignore[operator]
        cast("int", second_f()),  # type: ignore[operator]
        cast("int", first_instance.first_m()),  # type: ignore[attr-defined]
        cast("int", first_instance.m()),  # type: ignore[attr-defined]
        cast("int", current_instance.m()),  # type: ignore[attr-defined]
    )


def _stage_duplicate_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str = _DUPLICATE_SOURCE,
) -> tuple[MutmutConfig, Path, tuple[str, ...]]:
    monkeypatch.chdir(tmp_path)
    source_path = tmp_path / "src" / "mod.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source, encoding="utf-8")
    generated, local_names = mutate_file_contents(
        "src/mod.py",
        source,
        active_profile=Profile.BASIC,
    )
    staged_path = tmp_path / "mutants" / "src" / "mod.py"
    staged_path.parent.mkdir(parents=True)
    staged_path.write_text(generated, encoding="utf-8")

    qualified_names = tuple(
        get_mutant_name(Path("src/mod.py"), local_name) for local_name in local_names
    )
    metadata = SourceFileMutationData(
        path="src/mod.py",
        exit_code_by_key=dict.fromkeys(qualified_names),
        source_hash=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        generated_hash=hashlib.sha256(staged_path.read_bytes()).hexdigest(),
    )
    metadata.save()
    return MutmutConfig(paths_to_mutate=["src"]), source_path, qualified_names


def test_ordinal_encoding_is_reversible_and_first_definition_is_backward_compatible() -> None:
    assert mangle_function_name(name="f", class_name=None) == "x_f"
    assert mangle_function_name(name="f", class_name=None, definition_ordinal=2) == f"x_f{_SEP}2"
    assert (
        mangle_function_name(name="m", class_name="C", definition_ordinal=3)
        == f"x{_SEP}C{_SEP}m{_SEP}3"
    )

    top_level = function_definition_location_from_key(f"pkg.mod.x_f{_SEP}2__mutmut_7")
    assert (top_level.function_name, top_level.class_name, top_level.definition_ordinal) == (
        "f",
        None,
        2,
    )
    method = function_definition_location_from_key(f"pkg.mod.x{_SEP}C{_SEP}m{_SEP}3__mutmut_1")
    assert (method.function_name, method.class_name, method.definition_ordinal) == (
        "m",
        "C",
        3,
    )
    # The legacy two-tuple API decodes the ordinal without leaking it into the
    # Python source identifier.
    assert orig_function_and_class_names_from_key(f"pkg.mod.x{_SEP}C{_SEP}m{_SEP}3__mutmut_1") == (
        "m",
        "C",
    )


def test_reserved_mutant_delimiter_uses_reversible_collision_safe_encoding() -> None:
    top = mangle_function_name(name="f__mutmut_1", class_name=None)
    boundary = mangle_function_name(name="f__mutmut", class_name=None)
    prefix_boundary = mangle_function_name(name="_mutmut_target", class_name=None)
    method = mangle_function_name(
        name="m__mutmut_2",
        class_name="C__mutmut_3",
        definition_ordinal=2,
    )

    assert "__mutmut_" not in top
    assert "__mutmut_" not in boundary
    assert "__mutmut_" not in prefix_boundary
    assert "__mutmut_" not in method
    assert function_definition_location_from_key(
        f"pkg.{top}__mutmut_7"
    ) == FunctionDefinitionLocation(
        "f__mutmut_1",
        None,
        1,
    )
    assert function_definition_location_from_key(
        f"pkg.{boundary}__mutmut_7"
    ) == FunctionDefinitionLocation(
        "f__mutmut",
        None,
        1,
    )
    assert function_definition_location_from_key(
        f"pkg.{prefix_boundary}__mutmut_7"
    ) == FunctionDefinitionLocation(
        "_mutmut_target",
        None,
        1,
    )
    location = function_definition_location_from_key(f"pkg.{method}__mutmut_1")
    assert (location.function_name, location.class_name, location.definition_ordinal) == (
        "m__mutmut_2",
        "C__mutmut_3",
        2,
    )
    assert is_typecheck_mutant_name(f"{top}__mutmut_1")
    assert is_typecheck_mutant_name(f"{method}__mutmut_1")


def test_reserved_delimiter_functions_have_distinct_runtime_mutants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """\
def f(value):
    return value + 1

def f__mutmut_1(value):
    return value * 2
"""
    generated, names = mutate_file_contents("collision.py", source, active_profile=Profile.BASIC)
    namespace: dict[str, object] = {"__name__": "collision"}
    exec(compile(generated, "collision.py", "exec", dont_inherit=True), namespace)  # noqa: S102

    by_source_name: dict[str, list[str]] = {}
    for name in names:
        location = function_definition_location_from_key(f"collision.{name}")
        by_source_name.setdefault(location.function_name, []).append(name)

    assert set(by_source_name) == {"f", "f__mutmut_1"}
    assert len(names) == len(set(names))
    first = cast("object", namespace["f"])
    second = cast("object", namespace["f__mutmut_1"])
    assert first(3) == 4  # type: ignore[operator]
    assert second(3) == 6  # type: ignore[operator]

    monkeypatch.setenv("MUTANT_UNDER_TEST", f"collision.{by_source_name['f'][0]}")
    assert first(3) != 4  # type: ignore[operator]
    assert second(3) == 6  # type: ignore[operator]

    monkeypatch.setenv(
        "MUTANT_UNDER_TEST",
        f"collision.{by_source_name['f__mutmut_1'][0]}",
    )
    assert first(3) == 4  # type: ignore[operator]
    assert second(3) != 6  # type: ignore[operator]


@pytest.mark.parametrize("ordinal", [0, -1, True, 1.5, "2"])
def test_invalid_definition_ordinals_fail_closed(ordinal: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        mangle_function_name(
            name="f",
            class_name=None,
            definition_ordinal=ordinal,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "mutant_name",
    [
        f"pkg.x_f{_SEP}1__mutmut_1",
        f"pkg.x_f{_SEP}02__mutmut_1",
        f"pkg.x_f{_SEP}٢__mutmut_1",
        f"pkg.x_f{_SEP}zero__mutmut_1",
        f"pkg.x_f{_SEP}2{_SEP}3__mutmut_1",
    ],
)
def test_noncanonical_encoded_ordinals_fail_closed(mutant_name: str) -> None:
    with pytest.raises(ValueError, match="Malformed definition ordinal"):
        function_definition_location_from_key(mutant_name)


def test_generation_assigns_unique_stable_ids_across_functions_and_methods() -> None:
    generated, names = _generated_duplicate_module()

    assert names == _EXPECTED_LOCAL_NAMES
    assert len(names) == len(set(names))
    for name in names:
        assert f"def {name}(" in generated
    compile(generated, "src/mod.py", "exec")


def test_ordinal_names_remain_visible_to_the_typecheck_filter() -> None:
    assert is_typecheck_mutant_name(f"x_f{_SEP}2__mutmut_1")
    assert is_typecheck_mutant_name(f"x{_SEP}C{_SEP}m{_SEP}3__mutmut_1")


def test_user_symbol_collision_skips_only_the_conflicting_duplicate() -> None:
    source = f"""\
x_f{_SEP}2__mutmut_orig = object()
def f():
    return 1
first_f = f
def f():
    return 2
"""
    with pytest.warns(SyntaxWarning, match="internal trampoline namespace"):
        generated, names = mutate_file_contents(
            "src/mod.py",
            source,
            active_profile=Profile.BASIC,
        )

    assert tuple(names) == ("x_f__mutmut_1",)
    namespace: dict[str, object] = {"__name__": "collision_runtime"}
    exec(compile(generated, "src/mod.py", "exec"), namespace)  # noqa: S102  # nosemgrep
    assert cast("object", namespace["first_f"])() == 1  # type: ignore[operator]
    assert cast("object", namespace["f"])() == 2  # type: ignore[operator]


def test_ordinal_counts_unmutated_earlier_definition_for_source_location() -> None:
    source = """\
@registered
def f():
    return 1

def f():
    return 2
"""
    _generated, names = mutate_file_contents(
        "src/mod.py",
        source,
        active_profile=Profile.BASIC,
    )

    assert tuple(names) == (f"x_f{_SEP}2__mutmut_1",)


def test_clean_runtime_preserves_every_reachable_duplicate_binding() -> None:
    generated, _names = _generated_duplicate_module()
    namespace: dict[str, object] = {"__name__": "duplicate_runtime"}

    exec(compile(generated, "src/mod.py", "exec"), namespace)  # noqa: S102  # nosemgrep

    assert _runtime_values(namespace) == (10, 20, 30, 40, 50)


def test_each_duplicate_mutant_dispatches_only_to_its_own_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated, names = _generated_duplicate_module()
    namespace: dict[str, object] = {"__name__": "duplicate_runtime"}
    exec(compile(generated, "src/mod.py", "exec"), namespace)  # noqa: S102  # nosemgrep
    clean = (10, 20, 30, 40, 50)

    for index, name in enumerate(names):
        monkeypatch.setenv("MUTANT_UNDER_TEST", f"duplicate_runtime.{name}")
        expected = list(clean)
        expected[index] += 1
        assert _runtime_values(namespace) == tuple(expected)


def test_stats_and_test_mapping_keep_duplicate_definitions_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mutmut_win import hit_recording
    from mutmut_win._state import _stats

    generated, names = _generated_duplicate_module()
    namespace: dict[str, object] = {"__name__": "duplicate_runtime"}
    exec(compile(generated, "src/mod.py", "exec"), namespace)  # noqa: S102  # nosemgrep
    _stats.clear()
    monkeypatch.setenv("MUTANT_UNDER_TEST", "stats")
    monkeypatch.setattr(hit_recording, "_get_max_stack_depth", lambda: -1)

    assert _runtime_values(namespace) == (10, 20, 30, 40, 50)

    expected_mangled = {f"duplicate_runtime.{name.partition('__mutmut_')[0]}" for name in names}
    assert set(_stats) == expected_mangled
    mapping = {
        mangled: {f"tests/test_duplicates.py::test_{index}"}
        for index, mangled in enumerate(sorted(expected_mangled))
    }
    for name in names:
        qualified = f"duplicate_runtime.{name}"
        mangled = qualified.partition("__mutmut_")[0]
        assert tests_for_mutant_names([qualified], mapping) == mapping[mangled]
    _stats.clear()


def test_unique_ids_survive_historical_db_persistence(tmp_path: Path) -> None:
    _generated, names = _generated_duplicate_module()
    qualified = tuple(f"pkg.mod.{name}" for name in names)
    db_path = tmp_path / "cache.db"

    save_results(
        db_path,
        [(name, "killed", 1, 0.1, None, None, None) for name in qualified],
    )

    assert {result.mutant_name for result in load_results(db_path)} == set(qualified)


def test_show_diff_uses_the_exact_duplicate_source_occurrence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _source_path, names = _stage_duplicate_module(tmp_path, monkeypatch)

    second_function_diff = get_diff_for_mutant(names[1], config)
    third_method_diff = get_diff_for_mutant(names[4], config)

    assert "-    return 20" in second_function_diff
    assert "+    return 21" in second_function_diff
    assert "return 10" not in second_function_diff
    assert "@@ -4" in second_function_diff
    # The shared show diff now uses the real source indentation, so it is
    # directly patchable even for a class method.
    assert "-        return 50" in third_method_diff
    assert "+        return 51" in third_method_diff
    assert "return 30" not in third_method_diff
    assert "return 40" not in third_method_diff
    assert "@@ -17" in third_method_diff


def test_apply_targets_second_function_and_later_repeated_class_method(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, source_path, names = _stage_duplicate_module(tmp_path, monkeypatch)

    apply_mutant(names[1], config)
    applied_function = source_path.read_text(encoding="utf-8")
    assert "return 10" in applied_function
    assert "return 21" in applied_function
    assert "return 20" not in applied_function
    assert "return 30" in applied_function
    assert "return 40" in applied_function
    assert "return 50" in applied_function

    # Restore byte-for-byte so the staging hash is authoritative again, then
    # apply the third C.m occurrence (the method on the second class C).
    source_path.write_text(_DUPLICATE_SOURCE, encoding="utf-8")
    apply_mutant(names[4], config)
    applied_method = source_path.read_text(encoding="utf-8")
    assert "return 10" in applied_method
    assert "return 20" in applied_method
    assert "return 30" in applied_method
    assert "return 40" in applied_method
    assert "return 51" in applied_method
    assert "return 50" not in applied_method


def test_generated_ids_and_source_locations_are_deterministic() -> None:
    first_code, first_names = _generated_duplicate_module()
    second_code, second_names = _generated_duplicate_module()

    assert second_names == first_names
    assert second_code == first_code
    locations = [function_definition_location_from_key(name) for name in first_names]
    assert [location.definition_ordinal for location in locations] == [1, 2, 1, 2, 3]


# --- M-041: NFKC-equivalent identifiers ----------------------------------------


_NFKC_SOURCE = f"def K():\n    return 10\nfirst = K\ndef {_FULLWIDTH_K}():\n    return 20\n"

_NFKC_METHOD_SOURCE = (
    "class C:\n"
    "    def K(self):\n"
    "        return 10\n"
    "    first_m = K\n"
    f"    def {_FULLWIDTH_K}(self):\n"
    "        return 20\n"
)

_NFKC_CLASS_SOURCE = (
    "class C:\n"
    "    def m(self):\n"
    "        return 10\n"
    "FirstC = C\n"
    f"class {_FULLWIDTH_C}:\n"
    "    def m(self):\n"
    "        return 20\n"
)


def _exec_nfkc_module(source: str) -> tuple[dict[str, object], tuple[str, ...]]:
    generated, names = mutate_file_contents("src/mod.py", source, active_profile=Profile.BASIC)
    namespace: dict[str, object] = {"__name__": "nfkc_runtime"}
    exec(compile(generated, "src/mod.py", "exec"), namespace)  # noqa: S102  # nosemgrep
    return namespace, tuple(names)


def test_nfkc_equivalent_top_level_names_keep_distinct_private_bindings() -> None:
    namespace, names = _exec_nfkc_module(_NFKC_SOURCE)

    # Clean-Python oracle: the alias holds the FIRST function object (1),
    # while the public binding after both definitions points at the second
    # (2).  Pre-fix the mutated module returned 20 from the alias because
    # both private namespaces collapsed onto the compiled name
    # "x_K__mutmut_orig" and the wrapper resolved _orig at call time.
    assert cast("object", namespace["first"])() == 10  # type: ignore[operator]
    assert cast("object", namespace["K"])() == 20  # type: ignore[operator]

    assert len(names) == len(set(names))
    normalized = {unicodedata.normalize("NFKC", name) for name in names}
    assert len(normalized) == len(names)

    second = function_definition_location_from_key(f"nfkc_runtime.{names[1]}")
    assert second == FunctionDefinitionLocation(_FULLWIDTH_K, None, 1)
    assert is_typecheck_mutant_name(names[1])


def test_nfkc_equivalent_top_level_mutants_dispatch_to_their_own_bindings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace, names = _exec_nfkc_module(_NFKC_SOURCE)
    first = cast("object", namespace["first"])
    public = cast("object", namespace["K"])

    monkeypatch.setenv("MUTANT_UNDER_TEST", f"nfkc_runtime.{names[0]}")
    assert first() == 11  # type: ignore[operator]  # 10 -> 11
    assert public() == 20  # type: ignore[operator]

    monkeypatch.setenv("MUTANT_UNDER_TEST", f"nfkc_runtime.{names[1]}")
    assert first() == 10  # type: ignore[operator]
    assert public() == 21  # type: ignore[operator]  # 20 -> 21


def test_nfkc_equivalent_method_names_keep_distinct_private_bindings() -> None:
    namespace, _names = _exec_nfkc_module(_NFKC_METHOD_SOURCE)

    instance = cast("type[object]", namespace["C"])()
    # The class-body alias holds the FIRST method wrapper; its module-level
    # _orig_ref must not have been rebound by the U+FF2B definition.
    assert cast("int", instance.first_m()) == 10  # type: ignore[attr-defined]
    assert cast("int", instance.K()) == 20  # type: ignore[attr-defined]


def test_nfkc_equivalent_class_names_keep_distinct_method_bindings() -> None:
    namespace, _names = _exec_nfkc_module(_NFKC_CLASS_SOURCE)

    first_class = cast("type[object]", namespace["FirstC"])
    current_class = cast("type[object]", namespace["C"])
    assert cast("int", first_class().m()) == 10  # type: ignore[attr-defined]
    assert cast("int", current_class().m()) == 20  # type: ignore[attr-defined]


def test_nfkc_variant_definition_ordinals_round_trip() -> None:
    encoded = _FULLWIDTH_K.encode("utf-8").hex()
    assert (
        mangle_function_name(name=_FULLWIDTH_K, class_name=None, definition_ordinal=2)
        == f"xq_{encoded}{_SEP}2"
    )
    location = function_definition_location_from_key(f"pkg.mod.xq_{encoded}{_SEP}2__mutmut_3")
    assert location == FunctionDefinitionLocation(_FULLWIDTH_K, None, 2)
    assert is_typecheck_mutant_name(f"xq_{encoded}{_SEP}2__mutmut_1")

    method = mangle_function_name(name=_FULLWIDTH_K, class_name=_FULLWIDTH_C, definition_ordinal=2)
    assert function_definition_location_from_key(
        f"pkg.mod.{method}__mutmut_1"
    ) == FunctionDefinitionLocation(
        _FULLWIDTH_K,
        _FULLWIDTH_C,
        2,
    )
    assert is_typecheck_mutant_name(f"{method}__mutmut_1")


def test_nfkc_colliding_source_identifier_fails_closed() -> None:
    # Raw, the source identifier does NOT start with "x_K__mutmut_"; the
    # compiler still binds it as exactly that name, so it would silently
    # overwrite the trampoline namespace of "K" in the clean module.
    source = f"def K():\n    return 1\nx_{_FULLWIDTH_K}__mutmut_orig = 0\n"
    with pytest.warns(SyntaxWarning, match="internal trampoline namespace"):
        generated, names = mutate_file_contents("src/mod.py", source, active_profile=Profile.BASIC)
    assert not names

    namespace: dict[str, object] = {"__name__": "nfkc_collision"}
    exec(compile(generated, "src/mod.py", "exec"), namespace)  # noqa: S102  # nosemgrep
    assert cast("object", namespace["K"])() == 1  # type: ignore[operator]


def test_natural_xq_prefixed_source_name_stays_decodable_and_distinct() -> None:
    encoded = _FULLWIDTH_K.encode("utf-8").hex()
    _generated, names = mutate_file_contents(
        "src/mod.py",
        "def xq_ff2b():\n    return 1\n",
        active_profile=Profile.BASIC,
    )
    # A source name that naturally starts with "xq_" keeps the LEGACY
    # encoding and decodes to itself ...
    assert tuple(names) == ("x_xq_ff2b__mutmut_1",)
    assert function_definition_location_from_key(
        f"pkg.mod.{names[0]}"
    ) == FunctionDefinitionLocation(
        "xq_ff2b",
        None,
        1,
    )
    # ... while the encoded fullwidth identifier decodes to the RAW name.
    assert function_definition_location_from_key(
        f"pkg.mod.xq_{encoded}__mutmut_1"
    ) == FunctionDefinitionLocation(
        _FULLWIDTH_K,
        None,
        1,
    )
    assert is_typecheck_mutant_name(f"xq_{encoded}__mutmut_1")


def test_mutant_diff_finds_the_fullwidth_definition_by_raw_name() -> None:
    module = cst.parse_module(_NFKC_SOURCE)
    node = _find_function_in_scope(module, _FULLWIDTH_K, None, 1)
    assert node is not None
    assert node.name.value == _FULLWIDTH_K
    assert _find_function_in_scope(module, _FULLWIDTH_K, None, 2) is None


def test_show_and_apply_target_the_fullwidth_definition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, source_path, names = _stage_duplicate_module(tmp_path, monkeypatch, source=_NFKC_SOURCE)

    diff = get_diff_for_mutant(names[1], config)
    assert "-    return 20" in diff
    assert "+    return 21" in diff
    assert "return 10" not in diff

    apply_mutant(names[1], config)
    applied = source_path.read_text(encoding="utf-8")
    assert "return 10" in applied
    assert "return 21" in applied
    assert "return 20" not in applied


def test_nfkc_variant_ids_survive_db_persistence(tmp_path: Path) -> None:
    _namespace, names = _exec_nfkc_module(_NFKC_SOURCE)
    qualified = tuple(f"pkg.mod.{name}" for name in names)
    db_path = tmp_path / "cache.db"

    save_results(
        db_path,
        [(name, "killed", 1, 0.1, None, None, None) for name in qualified],
    )

    assert {result.mutant_name for result in load_results(db_path)} == set(qualified)


# Identifier-shaped names incl. NFKC variant characters (fullwidth letters,
# KELVIN SIGN, MICRO SIGN, LATIN SMALL LIGATURE FI, FULLWIDTH LOW LINE).  The
# strategy cannot produce the mangling separator U+01C1, which mangle_function_name
# rejects by design.
_NFKC_IDENTIFIER_STRATEGY = st.from_regex(
    r"[A-Za-z\uff21-\uff3a\uff41-\uff5a\u212a\u00b5\ufb01]"
    r"[A-Za-z0-9_\uff3f\uff21-\uff3a\uff41-\uff5a\u212a\u00b5\ufb01]{0,7}",
    fullmatch=True,
)


@given(
    name_a=_NFKC_IDENTIFIER_STRATEGY,
    name_b=_NFKC_IDENTIFIER_STRATEGY,
    class_name=st.sampled_from([None, "C", "_C", "\uff23"]),
)
def test_distinct_raw_identifiers_keep_nfkc_distinct_reversible_mutant_ids(
    name_a: str, name_b: str, class_name: str | None
) -> None:
    """M-041 property: mutant identity is per RAW identifier.

    Two different raw spellings must never collapse onto the same compiled
    private name (NFKC distinctness), and every encoding must decode back
    to the exact raw function and class components.
    """
    assume(name_a != name_b)
    mangled_a = mangle_function_name(name=name_a, class_name=class_name)
    mangled_b = mangle_function_name(name=name_b, class_name=class_name)

    assert unicodedata.normalize("NFKC", mangled_a) != unicodedata.normalize("NFKC", mangled_b)
    assert function_definition_location_from_key(
        f"m.{mangled_a}__mutmut_1"
    ) == FunctionDefinitionLocation(
        function_name=name_a,
        class_name=class_name,
        definition_ordinal=1,
    )
