"""Complete behavioural coverage for the pydantic_heavy fixture."""

from __future__ import annotations

import math

from pydantic import ValidationError

from pydantic_heavy.models import DiscountedOrder, LineItem, Order


def _sample_order() -> Order:
    return Order(
        order_id="ORD-0001",
        items=[
            LineItem(name="alpha", quantity=2, unit_price=3.5),
            LineItem(name="beta", quantity=1, unit_price=9.99),
        ],
    )


class TestLineItem:
    def test_total_multiplies_quantity_and_price(self) -> None:
        assert LineItem(name="x", quantity=3, unit_price=2.0).total == 6.0

    def test_total_rounds_to_cents(self) -> None:
        total = LineItem(name="x", quantity=3, unit_price=0.1).total
        assert math.isclose(total, 0.3, abs_tol=1e-9)

    def test_quantity_must_be_positive(self) -> None:
        try:
            LineItem(name="x", quantity=0, unit_price=1.0)
        except ValidationError:
            pass
        else:
            raise AssertionError("quantity=0 must be rejected")

    def test_untrimmed_name_is_rejected(self) -> None:
        try:
            LineItem(name=" x", quantity=1, unit_price=1.0)
        except ValidationError:
            pass
        else:
            raise AssertionError("untrimmed name must be rejected")


class TestOrder:
    def test_grand_total_sums_item_totals(self) -> None:
        # 2*3.5 + 1*9.99 = 16.99
        assert _sample_order().grand_total == 16.99

    def test_item_count_counts_items(self) -> None:
        assert _sample_order().item_count == 2

    def test_empty_order_totals_zero(self) -> None:
        assert Order(order_id="ORD-0002").grand_total == 0.0

    def test_order_id_shape_is_enforced(self) -> None:
        try:
            Order(order_id="nope")
        except ValidationError:
            pass
        else:
            raise AssertionError("malformed order_id must be rejected")


class TestDiscountedOrder:
    def test_payable_applies_discount(self) -> None:
        order = DiscountedOrder(
            order_id="ORD-0003",
            items=[LineItem(name="x", quantity=2, unit_price=10.0)],
            discount_percent=25,
        )
        assert order.payable == 15.0

    def test_full_discount_makes_order_free(self) -> None:
        order = DiscountedOrder(
            order_id="ORD-0004",
            items=[LineItem(name="x", quantity=1, unit_price=5.0)],
            discount_percent=100,
        )
        assert order.payable == 0.0

    def test_discount_bounds_are_enforced(self) -> None:
        try:
            DiscountedOrder(order_id="ORD-0005", discount_percent=101)
        except ValidationError:
            pass
        else:
            raise AssertionError("discount over 100 must be rejected")
