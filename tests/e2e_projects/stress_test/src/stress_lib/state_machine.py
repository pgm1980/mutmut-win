"""State machine implementations using match/case (Python 3.10+).

Designed to trigger mutations on: match/case arms, string literals in cases,
comparison operators in guards, and return-value mutations.
"""

from __future__ import annotations

from enum import Enum, auto


class TrafficLight(Enum):
    """Traffic light states."""

    RED = auto()
    YELLOW = auto()
    GREEN = auto()


class OrderState(Enum):
    """E-commerce order states."""

    PENDING = auto()
    CONFIRMED = auto()
    SHIPPED = auto()
    DELIVERED = auto()
    CANCELLED = auto()
    REFUNDED = auto()


def traffic_light_next(state: TrafficLight) -> TrafficLight:
    """Return the next traffic light state."""
    match state:
        case TrafficLight.RED:
            return TrafficLight.GREEN
        case TrafficLight.GREEN:
            return TrafficLight.YELLOW
        case TrafficLight.YELLOW:
            return TrafficLight.RED


def traffic_light_duration(state: TrafficLight) -> int:
    """Return the default duration in seconds for a traffic light state."""
    match state:
        case TrafficLight.RED:
            return 30
        case TrafficLight.GREEN:
            return 25
        case TrafficLight.YELLOW:
            return 5


def traffic_light_can_go(state: TrafficLight) -> bool:
    """Return True if traffic can proceed."""
    match state:
        case TrafficLight.GREEN:
            return True
        case TrafficLight.RED | TrafficLight.YELLOW:
            return False


def order_can_cancel(state: OrderState) -> bool:
    """Return True if the order can be cancelled in its current state."""
    match state:
        case OrderState.PENDING | OrderState.CONFIRMED:
            return True
        case OrderState.SHIPPED | OrderState.DELIVERED:
            return False
        case OrderState.CANCELLED | OrderState.REFUNDED:
            return False


def order_next_state(state: OrderState) -> OrderState | None:
    """Return the natural next state of an order, or None if terminal."""
    match state:
        case OrderState.PENDING:
            return OrderState.CONFIRMED
        case OrderState.CONFIRMED:
            return OrderState.SHIPPED
        case OrderState.SHIPPED:
            return OrderState.DELIVERED
        case OrderState.DELIVERED | OrderState.CANCELLED | OrderState.REFUNDED:
            return None


def parse_token(token: str) -> dict[str, object]:
    """Parse a simple command token into a structured dict."""
    match token.split(":"):
        case [cmd]:
            return dict(command=cmd, args=[], flags=[])
        case [cmd, args_str]:
            args = args_str.split(",")
            return dict(command=cmd, args=args, flags=[])
        case [cmd, args_str, flags_str]:
            args = args_str.split(",")
            flags = flags_str.split(",")
            return dict(command=cmd, args=args, flags=flags)
        case _:
            return dict(command="unknown", args=[], flags=[])


def classify_http_status(code: int) -> str:
    """Classify an HTTP status code into a category string."""
    match code:
        case c if 100 <= c <= 199:
            return "informational"
        case c if 200 <= c <= 299:
            return "success"
        case c if 300 <= c <= 399:
            return "redirection"
        case c if 400 <= c <= 499:
            return "client_error"
        case c if 500 <= c <= 599:
            return "server_error"
        case _:
            return "unknown"


def describe_point(point: tuple[int, int]) -> str:
    """Describe a 2D point by its quadrant or axis."""
    match point:
        case (0, 0):
            return "origin"
        case (x, 0) if x > 0:
            return "positive_x_axis"
        case (x, 0) if x < 0:
            return "negative_x_axis"
        case (0, y) if y > 0:
            return "positive_y_axis"
        case (0, y) if y < 0:
            return "negative_y_axis"
        case (x, y) if x > 0 and y > 0:
            return "quadrant_1"
        case (x, y) if x < 0 and y > 0:
            return "quadrant_2"
        case (x, y) if x < 0 and y < 0:
            return "quadrant_3"
        case (x, y) if x > 0 and y < 0:
            return "quadrant_4"
        case _:
            return "unknown"
