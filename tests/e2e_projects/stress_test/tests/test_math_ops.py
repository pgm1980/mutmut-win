"""Tests for math_ops — ~70% well covered, ~30% medium/weak."""

from __future__ import annotations

import pytest

from stress_lib.math_ops import (
    add,
    subtract,
    multiply,
    divide,
    modulo,
    power,
    floor_divide,
    bitwise_and,
    bitwise_or,
    bitwise_xor,
    bitwise_not,
    left_shift,
    right_shift,
    clamp,
    safe_divide,
    running_average,
    sum_of_squares,
    factorial,
    gcd,
    lcm,
    count_bits,
    is_power_of_two,
    manhattan_distance,
    percentage,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    compound_interest,
)


# --- Basic arithmetic (well covered) ---

class TestAdd:
    def test_positive(self) -> None:
        assert add(2, 3) == 5

    def test_negative(self) -> None:
        assert add(-1, -4) == -5

    def test_zero(self) -> None:
        assert add(0, 0) == 0

    def test_float(self) -> None:
        assert add(1.5, 2.5) == 4.0

    def test_mixed(self) -> None:
        assert add(1, 0.5) == 1.5


class TestSubtract:
    def test_basic(self) -> None:
        assert subtract(10, 3) == 7

    def test_negative_result(self) -> None:
        assert subtract(3, 10) == -7

    def test_zero(self) -> None:
        assert subtract(5, 5) == 0

    def test_float(self) -> None:
        assert subtract(3.5, 1.5) == 2.0


class TestMultiply:
    def test_positive(self) -> None:
        assert multiply(4, 3) == 12

    def test_by_zero(self) -> None:
        assert multiply(5, 0) == 0

    def test_negative(self) -> None:
        assert multiply(-2, 3) == -6

    def test_float(self) -> None:
        assert multiply(2.5, 4.0) == 10.0


class TestDivide:
    def test_basic(self) -> None:
        assert divide(10.0, 2.0) == 5.0

    def test_fraction(self) -> None:
        assert divide(1.0, 4.0) == 0.25

    def test_divide_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            divide(5.0, 0.0)

    def test_negative(self) -> None:
        assert divide(-6.0, 3.0) == -2.0


class TestModulo:
    def test_basic(self) -> None:
        assert modulo(10, 3) == 1

    def test_exact(self) -> None:
        assert modulo(9, 3) == 0

    def test_zero_divisor(self) -> None:
        with pytest.raises(ZeroDivisionError):
            modulo(5, 0)


class TestPower:
    def test_square(self) -> None:
        assert power(3, 2) == 9

    def test_zero_exp(self) -> None:
        assert power(5, 0) == 1

    def test_one_exp(self) -> None:
        assert power(7, 1) == 7

    def test_float(self) -> None:
        assert power(4.0, 0.5) == pytest.approx(2.0)


class TestFloorDivide:
    def test_exact(self) -> None:
        assert floor_divide(10, 2) == 5

    def test_remainder(self) -> None:
        assert floor_divide(7, 2) == 3

    def test_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            floor_divide(5, 0)


# --- Bitwise operations (well covered) ---

class TestBitwiseAnd:
    def test_basic(self) -> None:
        assert bitwise_and(0b1010, 0b1100) == 0b1000

    def test_zero(self) -> None:
        assert bitwise_and(5, 0) == 0

    def test_identity(self) -> None:
        assert bitwise_and(7, 7) == 7


class TestBitwiseOr:
    def test_basic(self) -> None:
        assert bitwise_or(0b1010, 0b0101) == 0b1111

    def test_zero(self) -> None:
        assert bitwise_or(5, 0) == 5

    def test_identity(self) -> None:
        assert bitwise_or(7, 7) == 7


class TestBitwiseXor:
    def test_basic(self) -> None:
        assert bitwise_xor(0b1010, 0b1100) == 0b0110

    def test_self(self) -> None:
        assert bitwise_xor(5, 5) == 0

    def test_zero(self) -> None:
        assert bitwise_xor(5, 0) == 5


class TestBitwiseNot:
    def test_zero(self) -> None:
        assert bitwise_not(0) == -1

    def test_positive(self) -> None:
        assert bitwise_not(5) == -6


class TestShifts:
    def test_left_shift(self) -> None:
        assert left_shift(1, 3) == 8

    def test_right_shift(self) -> None:
        assert right_shift(8, 3) == 1

    def test_shift_zero(self) -> None:
        assert left_shift(5, 0) == 5
        assert right_shift(5, 0) == 5

    def test_negative_shift_raises(self) -> None:
        with pytest.raises(ValueError):
            left_shift(1, -1)
        with pytest.raises(ValueError):
            right_shift(1, -1)


# --- Clamp (well covered) ---

class TestClamp:
    def test_within_range(self) -> None:
        assert clamp(5, 0, 10) == 5

    def test_below_low(self) -> None:
        assert clamp(-1, 0, 10) == 0

    def test_above_high(self) -> None:
        assert clamp(11, 0, 10) == 10

    def test_at_low(self) -> None:
        assert clamp(0, 0, 10) == 0

    def test_at_high(self) -> None:
        assert clamp(10, 0, 10) == 10

    def test_invalid_range(self) -> None:
        with pytest.raises(ValueError):
            clamp(5, 10, 0)


# --- safe_divide (medium coverage) ---

class TestSafeDivide:
    def test_basic(self) -> None:
        assert safe_divide(10.0, 2.0) == 5.0

    def test_zero_divisor_default(self) -> None:
        assert safe_divide(5.0, 0.0) == 0.0

    def test_custom_default(self) -> None:
        assert safe_divide(5.0, 0.0, default=-1.0) == -1.0


# --- running_average (well covered) ---

class TestRunningAverage:
    def test_basic(self) -> None:
        assert running_average([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_single(self) -> None:
        assert running_average([5.0]) == 5.0

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            running_average([])

    def test_negative(self) -> None:
        assert running_average([-3.0, 3.0]) == pytest.approx(0.0)


# --- sum_of_squares (medium coverage) ---

class TestSumOfSquares:
    def test_zero(self) -> None:
        assert sum_of_squares(0) == 0

    def test_three(self) -> None:
        assert sum_of_squares(3) == 14  # 1+4+9

    def test_five(self) -> None:
        assert sum_of_squares(5) == 55  # 1+4+9+16+25


# --- factorial (well covered) ---

class TestFactorial:
    def test_zero(self) -> None:
        assert factorial(0) == 1

    def test_one(self) -> None:
        assert factorial(1) == 1

    def test_five(self) -> None:
        assert factorial(5) == 120

    def test_ten(self) -> None:
        assert factorial(10) == 3628800

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            factorial(-1)


# --- gcd / lcm (well covered) ---

class TestGcd:
    def test_basic(self) -> None:
        assert gcd(12, 8) == 4

    def test_coprime(self) -> None:
        assert gcd(7, 13) == 1

    def test_same(self) -> None:
        assert gcd(6, 6) == 6


class TestLcm:
    def test_basic(self) -> None:
        assert lcm(4, 6) == 12

    def test_coprime(self) -> None:
        assert lcm(3, 7) == 21


# --- count_bits (well covered) ---

class TestCountBits:
    def test_zero(self) -> None:
        assert count_bits(0) == 0

    def test_one(self) -> None:
        assert count_bits(1) == 1

    def test_seven(self) -> None:
        assert count_bits(7) == 3

    def test_255(self) -> None:
        assert count_bits(255) == 8

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            count_bits(-1)


# --- is_power_of_two (well covered) ---

class TestIsPowerOfTwo:
    def test_one(self) -> None:
        assert is_power_of_two(1) is True

    def test_two(self) -> None:
        assert is_power_of_two(2) is True

    def test_four(self) -> None:
        assert is_power_of_two(4) is True

    def test_three(self) -> None:
        assert is_power_of_two(3) is False

    def test_zero(self) -> None:
        assert is_power_of_two(0) is False

    def test_negative(self) -> None:
        assert is_power_of_two(-4) is False


# --- manhattan_distance (medium coverage) ---

class TestManhattanDistance:
    def test_basic(self) -> None:
        assert manhattan_distance(0, 0, 3, 4) == 7

    def test_same_point(self) -> None:
        assert manhattan_distance(1, 1, 1, 1) == 0

    def test_negative(self) -> None:
        assert manhattan_distance(-1, -1, 1, 1) == 4


# --- percentage (medium coverage) ---

class TestPercentage:
    def test_half(self) -> None:
        assert percentage(50.0, 100.0) == pytest.approx(50.0)

    def test_full(self) -> None:
        assert percentage(100.0, 100.0) == pytest.approx(100.0)

    def test_zero_whole_raises(self) -> None:
        with pytest.raises(ZeroDivisionError):
            percentage(5.0, 0.0)


# --- temperature conversions (weak coverage — some mutants survive) ---

class TestTemperatureConversions:
    def test_freezing_c_to_f(self) -> None:
        assert celsius_to_fahrenheit(0) == pytest.approx(32.0)

    def test_boiling_c_to_f(self) -> None:
        assert celsius_to_fahrenheit(100) == pytest.approx(212.0)

    def test_freezing_f_to_c(self) -> None:
        assert fahrenheit_to_celsius(32) == pytest.approx(0.0)


# --- compound_interest (weak coverage) ---

class TestCompoundInterest:
    def test_zero_periods(self) -> None:
        assert compound_interest(1000.0, 0.05, 0) == pytest.approx(1000.0)

    def test_one_period(self) -> None:
        assert compound_interest(1000.0, 0.10, 1) == pytest.approx(1100.0)

    def test_negative_periods_raises(self) -> None:
        with pytest.raises(ValueError):
            compound_interest(1000.0, 0.05, -1)
