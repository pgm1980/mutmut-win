"""Verified mutation results from mutmut 3.5.0 E2E test suite.

These are the expected exit codes for each mutant when running the reference
test projects through mutmut. mutmut-win must produce identical results
(except for platform-specific differences like segfault exit codes).

Exit code semantics:
    0  = mutant survived (tests passed with the mutant active — bad test)
    1  = mutant killed (tests detected the mutation — good test)
    33 = mutant not covered / not reachable
    37 = mutant caught by type checker
    -11 = segfault (Unix SIGSEGV) — Windows will produce a different code
"""

from __future__ import annotations

EXPECTED_MY_LIB: dict[str, dict[str, int]] = {
    "mutants/src/my_lib/__init__.py.meta": {
        "my_lib.x_hello__mutmut_1": 1,
        "my_lib.x_hello__mutmut_2": 1,
        "my_lib.x_hello__mutmut_3": 1,
        "my_lib.x_badly_tested__mutmut_1": 0,
        "my_lib.x_badly_tested__mutmut_2": 0,
        "my_lib.x_badly_tested__mutmut_3": 0,
        "my_lib.x_untested__mutmut_1": 33,
        "my_lib.x_untested__mutmut_2": 33,
        "my_lib.x_untested__mutmut_3": 33,
        "my_lib.x_make_greeter__mutmut_1": 1,
        "my_lib.x_make_greeter__mutmut_2": 1,
        "my_lib.x_make_greeter__mutmut_3": 1,
        "my_lib.x_make_greeter__mutmut_4": 1,
        "my_lib.x_make_greeter__mutmut_5": 0,
        "my_lib.x_make_greeter__mutmut_6": 0,
        "my_lib.x_make_greeter__mutmut_7": 0,
        "my_lib.x_fibonacci__mutmut_1": 1,
        "my_lib.x_fibonacci__mutmut_2": 0,
        "my_lib.x_fibonacci__mutmut_3": 0,
        "my_lib.x_fibonacci__mutmut_4": 0,
        "my_lib.x_fibonacci__mutmut_5": 0,
        "my_lib.x_fibonacci__mutmut_6": 0,
        "my_lib.x_fibonacci__mutmut_7": 0,
        "my_lib.x_fibonacci__mutmut_8": 0,
        "my_lib.x_fibonacci__mutmut_9": 0,
        "my_lib.x_async_consumer__mutmut_1": 1,
        "my_lib.x_async_consumer__mutmut_2": 1,
        "my_lib.x_async_generator__mutmut_1": 1,
        "my_lib.x_async_generator__mutmut_2": 1,
        "my_lib.x_simple_consumer__mutmut_1": 1,
        "my_lib.x_simple_consumer__mutmut_2": 1,
        "my_lib.x_simple_consumer__mutmut_3": 1,
        "my_lib.x_simple_consumer__mutmut_4": 1,
        "my_lib.x_simple_consumer__mutmut_5": 1,
        "my_lib.x_simple_consumer__mutmut_6": 0,
        "my_lib.x_simple_consumer__mutmut_7": 1,
        "my_lib.x_double_generator__mutmut_1": 1,
        "my_lib.x_double_generator__mutmut_2": 1,
        "my_lib.x_double_generator__mutmut_3": 0,
        "my_lib.x_double_generator__mutmut_4": 0,
        "my_lib.xǁPointǁ__init____mutmut_1": 1,
        "my_lib.xǁPointǁ__init____mutmut_2": 1,
        "my_lib.xǁPointǁabs__mutmut_1": 33,
        "my_lib.xǁPointǁabs__mutmut_2": 33,
        "my_lib.xǁPointǁabs__mutmut_3": 33,
        "my_lib.xǁPointǁabs__mutmut_4": 33,
        "my_lib.xǁPointǁabs__mutmut_5": 33,
        "my_lib.xǁPointǁabs__mutmut_6": 33,
        "my_lib.xǁPointǁadd__mutmut_1": 0,
        "my_lib.xǁPointǁadd__mutmut_2": 1,
        "my_lib.xǁPointǁadd__mutmut_3": 1,
        "my_lib.xǁPointǁadd__mutmut_4": 0,
        "my_lib.xǁPointǁto_origin__mutmut_1": 1,
        "my_lib.xǁPointǁto_origin__mutmut_2": 1,
        "my_lib.xǁPointǁto_origin__mutmut_3": 0,
        "my_lib.xǁPointǁto_origin__mutmut_4": 0,
        "my_lib.xǁPointǁ__len____mutmut_1": 33,
        "my_lib.x_escape_sequences__mutmut_1": 1,
        "my_lib.x_escape_sequences__mutmut_2": 0,
        "my_lib.x_escape_sequences__mutmut_3": 1,
        "my_lib.x_escape_sequences__mutmut_4": 0,
        "my_lib.x_escape_sequences__mutmut_5": 0,
        "my_lib.x_create_a_segfault_when_mutated__mutmut_1": -11,
        "my_lib.x_create_a_segfault_when_mutated__mutmut_2": 0,
        "my_lib.x_create_a_segfault_when_mutated__mutmut_3": 0,
        "my_lib.x_some_func__mutmut_1": 0,
        "my_lib.x_some_func__mutmut_2": 0,
        "my_lib.x_some_func__mutmut_3": 1,
        "my_lib.x_func_with_star__mutmut_1": 1,
        "my_lib.x_func_with_star__mutmut_2": 1,
        "my_lib.x_func_with_star__mutmut_3": 1,
        "my_lib.x_func_with_arbitrary_args__mutmut_1": 1,
    },
}

EXPECTED_CONFIG: dict[str, dict[str, int]] = {
    "mutants/config_pkg/__init__.py.meta": {
        "config_pkg.x_hello__mutmut_1": 1,
        "config_pkg.x_hello__mutmut_2": 1,
        "config_pkg.x_hello__mutmut_3": 1,
    },
    "mutants/config_pkg/math.py.meta": {
        "config_pkg.math.x_add__mutmut_1": 0,
        "config_pkg.math.x_call_depth_two__mutmut_1": 1,
        "config_pkg.math.x_call_depth_two__mutmut_2": 1,
        "config_pkg.math.x_call_depth_three__mutmut_1": 1,
        "config_pkg.math.x_call_depth_three__mutmut_2": 1,
        "config_pkg.math.x_call_depth_four__mutmut_1": 33,
        "config_pkg.math.x_call_depth_four__mutmut_2": 33,
        "config_pkg.math.x_call_depth_five__mutmut_1": 33,
        "config_pkg.math.x_func_with_no_tests__mutmut_1": 33,
    },
}

EXPECTED_COVERAGE: dict[str, dict[str, int]] = {
    "mutants/src/mutate_only_covered_lines/__init__.py.meta": {
        "mutate_only_covered_lines.x_hello_mutate_only_covered_lines__mutmut_1": 1,
        "mutate_only_covered_lines.x_hello_mutate_only_covered_lines__mutmut_2": 1,
        "mutate_only_covered_lines.x_hello_mutate_only_covered_lines__mutmut_3": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_1": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_2": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_3": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_4": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_5": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_6": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_7": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_8": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_9": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_10": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_11": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_12": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_13": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_14": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_15": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_16": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_17": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_18": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_19": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_20": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_21": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_22": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_23": 0,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_24": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_25": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_26": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_27": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_28": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_29": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_30": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_31": 1,
        "mutate_only_covered_lines.x_mutate_only_covered_lines_multiline__mutmut_32": 1,
    },
    "mutants/src/mutate_only_covered_lines/omit_me.py.meta": {},
}

EXPECTED_TYPE_CHECKING: dict[str, dict[str, int]] = {
    "mutants/src/type_checking/__init__.py.meta": {
        "type_checking.x_hello__mutmut_1": 37,
        "type_checking.x_hello__mutmut_2": 1,
        "type_checking.x_hello__mutmut_3": 1,
        "type_checking.x_hello__mutmut_4": 1,
        "type_checking.x_a_hello_wrapper__mutmut_1": 37,
        "type_checking.x_a_hello_wrapper__mutmut_2": 0,
        "type_checking.xǁPersonǁset_name__mutmut_1": 37,
        "type_checking.x_mutate_me__mutmut_1": 37,
        "type_checking.x_mutate_me__mutmut_2": 37,
        "type_checking.x_mutate_me__mutmut_3": 1,
        "type_checking.x_mutate_me__mutmut_4": 1,
        "type_checking.x_mutate_me__mutmut_5": 37,
    },
}

EXPECTED_PY3_14: dict[str, dict[str, int]] = {
    "mutants/src/py3_14_features/__init__.py.meta": {
        "py3_14_features.x_get_len__mutmut_1": 0,
        "py3_14_features.x_get_len__mutmut_2": 1,
        "py3_14_features.x_get_foo_len__mutmut_1": 0,
        "py3_14_features.x_get_foo_len__mutmut_2": 1,
    },
}

# Windows-specific adjustments:
# On Unix, a segfault yields exit code -11 (SIGSEGV).
# On Windows the process is terminated with an access violation,
# yielding exit code -1073741819 (0xC0000005) or similar OS-dependent value.
# mutmut-win tests that compare against EXPECTED_MY_LIB should treat
# entries in SEGFAULT_MUTANTS specially.
SEGFAULT_MUTANTS: list[str] = [
    "my_lib.x_create_a_segfault_when_mutated__mutmut_1",
]
