"""Arithmetic, bitwise, and numeric operations.

Designed to trigger arithmetic operator mutations (+/-/*/////%), comparison
mutations (</<=/>/>==/!=), bitwise mutations (&/|/^/~/<</>>), and
augmented-assignment mutations (+=/-=/*= etc.).
"""

from __future__ import annotations


def add(a: int | float, b: int | float) -> int | float:
    """Return a + b."""
    return a + b


def subtract(a: int | float, b: int | float) -> int | float:
    """Return a - b."""
    return a - b


def multiply(a: int | float, b: int | float) -> int | float:
    """Return a * b."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return a / b (true division). Raises ZeroDivisionError if b == 0."""
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


def modulo(a: int, b: int) -> int:
    """Return a % b."""
    if b == 0:
        raise ZeroDivisionError("modulo by zero")
    return a % b


def power(base: int | float, exp: int | float) -> int | float:
    """Return base ** exp."""
    return base ** exp


def floor_divide(a: int, b: int) -> int:
    """Return a // b."""
    if b == 0:
        raise ZeroDivisionError("floor division by zero")
    return a // b


def bitwise_and(a: int, b: int) -> int:
    """Return a & b."""
    return a & b


def bitwise_or(a: int, b: int) -> int:
    """Return a | b."""
    return a | b


def bitwise_xor(a: int, b: int) -> int:
    """Return a ^ b."""
    return a ^ b


def bitwise_not(a: int) -> int:
    """Return ~a."""
    return ~a


def left_shift(a: int, n: int) -> int:
    """Return a << n. n must be >= 0."""
    if n < 0:
        raise ValueError("shift count must be >= 0")
    return a << n


def right_shift(a: int, n: int) -> int:
    """Return a >> n. n must be >= 0."""
    if n < 0:
        raise ValueError("shift count must be >= 0")
    return a >> n


def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
    """Clamp value into [low, high]."""
    if low > high:
        raise ValueError("low must be <= high")
    if value < low:
        return low
    if value > high:
        return high
    return value


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """Return a / b, or default when b is zero."""
    if b == 0.0:
        return default
    return a / b


def running_average(values: list[float]) -> float:
    """Return the arithmetic mean of values. Raises ValueError on empty list."""
    if len(values) == 0:
        raise ValueError("values must not be empty")
    total = 0.0
    for v in values:
        total += v
    return total / len(values)


def sum_of_squares(n: int) -> int:
    """Return 1^2 + 2^2 + ... + n^2 for n >= 0."""
    result = 0
    for i in range(1, n + 1):
        result += i * i
    return result


def factorial(n: int) -> int:
    """Return n! for n >= 0."""
    if n < 0:
        raise ValueError("n must be >= 0")
    if n == 0:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def gcd(a: int, b: int) -> int:
    """Return the greatest common divisor of a and b (both must be > 0)."""
    while b != 0:
        a, b = b, a % b
    return a


def lcm(a: int, b: int) -> int:
    """Return the least common multiple of a and b."""
    return (a * b) // gcd(a, b)


def count_bits(n: int) -> int:
    """Return the number of set bits in the binary representation of n (>= 0)."""
    if n < 0:
        raise ValueError("n must be >= 0")
    count = 0
    while n > 0:
        count += n & 1
        n >>= 1
    return count


def is_power_of_two(n: int) -> bool:
    """Return True if n is a power of two (n > 0)."""
    if n <= 0:
        return False
    return (n & (n - 1)) == 0


def manhattan_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Return |x2 - x1| + |y2 - y1|."""
    return abs(x2 - x1) + abs(y2 - y1)


def percentage(part: float, whole: float) -> float:
    """Return part / whole * 100. Raises ZeroDivisionError if whole == 0."""
    if whole == 0.0:
        raise ZeroDivisionError("whole must not be zero")
    return part / whole * 100.0


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32) * 5 / 9


def compound_interest(principal: float, rate: float, periods: int) -> float:
    """Return principal * (1 + rate) ** periods."""
    if periods < 0:
        raise ValueError("periods must be >= 0")
    return principal * (1 + rate) ** periods
