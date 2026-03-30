"""Tests for state_machine — ~65% well covered."""

from __future__ import annotations

import pytest

from stress_lib.state_machine import (
    TrafficLight,
    OrderState,
    traffic_light_next,
    traffic_light_duration,
    traffic_light_can_go,
    order_can_cancel,
    order_next_state,
    parse_token,
    classify_http_status,
    describe_point,
)


class TestTrafficLightNext:
    def test_red_to_green(self) -> None:
        assert traffic_light_next(TrafficLight.RED) == TrafficLight.GREEN

    def test_green_to_yellow(self) -> None:
        assert traffic_light_next(TrafficLight.GREEN) == TrafficLight.YELLOW

    def test_yellow_to_red(self) -> None:
        assert traffic_light_next(TrafficLight.YELLOW) == TrafficLight.RED

    def test_cycle(self) -> None:
        state = TrafficLight.RED
        state = traffic_light_next(state)  # GREEN
        state = traffic_light_next(state)  # YELLOW
        state = traffic_light_next(state)  # RED
        assert state == TrafficLight.RED


class TestTrafficLightDuration:
    def test_red_duration(self) -> None:
        assert traffic_light_duration(TrafficLight.RED) == 30

    def test_green_duration(self) -> None:
        assert traffic_light_duration(TrafficLight.GREEN) == 25

    def test_yellow_duration(self) -> None:
        assert traffic_light_duration(TrafficLight.YELLOW) == 5

    def test_all_positive(self) -> None:
        for state in TrafficLight:
            assert traffic_light_duration(state) > 0


class TestTrafficLightCanGo:
    def test_green_can_go(self) -> None:
        assert traffic_light_can_go(TrafficLight.GREEN) is True

    def test_red_cannot_go(self) -> None:
        assert traffic_light_can_go(TrafficLight.RED) is False

    def test_yellow_cannot_go(self) -> None:
        assert traffic_light_can_go(TrafficLight.YELLOW) is False


class TestOrderCanCancel:
    def test_pending_can_cancel(self) -> None:
        assert order_can_cancel(OrderState.PENDING) is True

    def test_confirmed_can_cancel(self) -> None:
        assert order_can_cancel(OrderState.CONFIRMED) is True

    def test_shipped_cannot_cancel(self) -> None:
        assert order_can_cancel(OrderState.SHIPPED) is False

    def test_delivered_cannot_cancel(self) -> None:
        assert order_can_cancel(OrderState.DELIVERED) is False

    def test_cancelled_cannot_cancel(self) -> None:
        assert order_can_cancel(OrderState.CANCELLED) is False

    def test_refunded_cannot_cancel(self) -> None:
        assert order_can_cancel(OrderState.REFUNDED) is False


class TestOrderNextState:
    def test_pending_to_confirmed(self) -> None:
        assert order_next_state(OrderState.PENDING) == OrderState.CONFIRMED

    def test_confirmed_to_shipped(self) -> None:
        assert order_next_state(OrderState.CONFIRMED) == OrderState.SHIPPED

    def test_shipped_to_delivered(self) -> None:
        assert order_next_state(OrderState.SHIPPED) == OrderState.DELIVERED

    def test_delivered_is_terminal(self) -> None:
        assert order_next_state(OrderState.DELIVERED) is None

    def test_cancelled_is_terminal(self) -> None:
        assert order_next_state(OrderState.CANCELLED) is None

    def test_refunded_is_terminal(self) -> None:
        assert order_next_state(OrderState.REFUNDED) is None


class TestParseToken:
    def test_command_only(self) -> None:
        result = parse_token("run")
        assert result["command"] == "run"
        assert result["args"] == []
        assert result["flags"] == []

    def test_command_with_args(self) -> None:
        result = parse_token("run:a,b,c")
        assert result["command"] == "run"
        assert result["args"] == ["a", "b", "c"]

    def test_command_with_args_and_flags(self) -> None:
        result = parse_token("run:a,b:x,y")
        assert result["command"] == "run"
        assert result["args"] == ["a", "b"]
        assert result["flags"] == ["x", "y"]

    def test_too_many_parts(self) -> None:
        result = parse_token("a:b:c:d")
        assert result["command"] == "unknown"


class TestClassifyHttpStatus:
    def test_200_success(self) -> None:
        assert classify_http_status(200) == "success"

    def test_404_client_error(self) -> None:
        assert classify_http_status(404) == "client_error"

    def test_500_server_error(self) -> None:
        assert classify_http_status(500) == "server_error"

    def test_301_redirection(self) -> None:
        assert classify_http_status(301) == "redirection"

    def test_100_informational(self) -> None:
        assert classify_http_status(100) == "informational"

    def test_unknown(self) -> None:
        assert classify_http_status(999) == "unknown"

    def test_boundary_200(self) -> None:
        assert classify_http_status(200) == "success"

    def test_boundary_299(self) -> None:
        assert classify_http_status(299) == "success"

    def test_boundary_300(self) -> None:
        assert classify_http_status(300) == "redirection"


class TestDescribePoint:
    def test_origin(self) -> None:
        assert describe_point((0, 0)) == "origin"

    def test_positive_x_axis(self) -> None:
        assert describe_point((3, 0)) == "positive_x_axis"

    def test_negative_x_axis(self) -> None:
        assert describe_point((-3, 0)) == "negative_x_axis"

    def test_positive_y_axis(self) -> None:
        assert describe_point((0, 4)) == "positive_y_axis"

    def test_negative_y_axis(self) -> None:
        assert describe_point((0, -4)) == "negative_y_axis"

    def test_quadrant_1(self) -> None:
        assert describe_point((1, 1)) == "quadrant_1"

    def test_quadrant_2(self) -> None:
        assert describe_point((-1, 1)) == "quadrant_2"

    def test_quadrant_3(self) -> None:
        assert describe_point((-1, -1)) == "quadrant_3"

    def test_quadrant_4(self) -> None:
        assert describe_point((1, -1)) == "quadrant_4"
