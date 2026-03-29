"""Constants for mutmut-win: exit code mappings and status definitions."""

from collections import defaultdict

# Exit code to status mapping for Windows.
# Based on mutmut 3.5.0, adapted for Windows (no SIGXCPU/-24/152).
# Timeout detection is event-based, not exit-code-based.
status_by_exit_code: defaultdict[int | None, str] = defaultdict(
    lambda: "suspicious",
    {
        0: "survived",
        1: "killed",
        2: "check was interrupted by user",
        3: "killed",  # internal error in pytest means a kill
        5: "no tests",
        33: "no tests",
        34: "skipped",
        35: "suspicious",
        36: "timeout",
        37: "caught by type check",
        255: "timeout",
        None: "not checked",
    },
)

emoji_by_status: dict[str, str] = {
    "survived": "\U0001f641",
    "no tests": "\U0001fae5",
    "timeout": "\u23f0",
    "suspicious": "\U0001f914",
    "skipped": "\U0001f507",
    "caught by type check": "\U0001f9d9",
    "check was interrupted by user": "\U0001f6d1",
    "not checked": "?",
    "killed": "",
    "segfault": "\U0001f4a5",
}

exit_code_to_emoji: defaultdict[int | None, str] = defaultdict(
    lambda: emoji_by_status["suspicious"],
    {code: emoji_by_status.get(status, "") for code, status in status_by_exit_code.items()},
)

# Internal exit codes used by mutmut-win for non-pytest results.
EXIT_CODE_TIMEOUT: int = 36
EXIT_CODE_SKIPPED: int = 34
EXIT_CODE_TYPE_CHECK: int = 37
