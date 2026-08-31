"""Acceptance targets — one construct per PLANNED mutmut-win operator
(see reporting/MUTMUT_WIN_OPERATOR_ROADMAP.md). Each function carries the exact
syntax a new operator must mutate; the matching test in tests/test_roadmap.py
is strong enough to KILL that operator's expected mutant(s) once implemented.

In the original v2.14.0 baseline (operator absent) the future mutant was not generated, so
the test passes trivially — and ROADMAP_SPEC.md records the expected-vs-current
mutant gap as the maintainer's acceptance criterion.
"""


# --- advanced #3 — ROR full matrix: `<` must also yield >, >=, ==, != -------
def ror(a, b):
    return a < b


# --- advanced #15 — number-literal CRCR: 7 must also yield 0, 1, -1, -7 -----
def crcr():
    return 7


# --- advanced #22 — negate whole condition: `if flag` -> `if not flag` ------
def negate_cond(flag):
    if flag:
        return "t"
    return "f"


# --- advanced #23 — force conditional: `if x>0` -> `if True` / `if False` ---
def force_cond(x):
    if x > 0:
        return "pos"
    return "nonpos"


# --- advanced #38 — collection-literal emptying ----------------------------
def coll_list():
    return [1, 2, 3]


def coll_dict():
    return {"a": 1, "b": 2}


def coll_set():
    return {1, 2, 3}


def coll_tuple():
    return (1, 2, 3)


# --- advanced #41 — match guard: `case x if g` -> guard True / False --------
def match_guard(n):
    match n:
        case x if x > 0:
            return "pos"
        case _:
            return "other"


# --- all #2 (AOD: a+b -> a / b) and #12 (UOI: insert unary) -----------------
def aod_uoi(a, b):
    return a + b


# --- all #29 — member/attr-assignment removal (vs current a=None neutralize) -
class Counter:
    def __init__(self):
        self.value = 5

    def get(self):
        return self.value


# --- all #44 — exception swap: raise ValueError -> raise TypeError ----------
def guard_raise(x):
    if x < 0:
        raise ValueError("negative")
    return x


# --- backport: @staticmethod / @classmethod must be mutated (mutmut 3.6.0) --
# In the original v2.14.0 baseline ALL decorated functions were skipped (mutation.py:245), so
# these produce ZERO mutants. After the backport they must produce mutants
# (killed by test_calc_static_class). @property must STAY skipped.
class Calc:
    @staticmethod
    def double(x):
        return x * 2

    @classmethod
    def triple(cls, x):
        return x * 3
