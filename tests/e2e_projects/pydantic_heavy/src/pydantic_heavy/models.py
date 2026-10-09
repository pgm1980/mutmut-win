"""Pydantic inheritance, validators and computed fields behind a class trampoline."""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field, field_validator


class LineItem(BaseModel):
    """Nested model with validation."""

    name: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0.0)

    @field_validator("name")
    @classmethod
    def name_is_trimmed(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("name must be trimmed")
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class Order(BaseModel):
    """Aggregating model with a computed summary."""

    order_id: str
    items: list[LineItem] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def grand_total(self) -> float:
        return round(sum(item.total for item in self.items), 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def item_count(self) -> int:
        return len(self.items)

    @field_validator("order_id")
    @classmethod
    def order_id_shape(cls, value: str) -> str:
        if not value.startswith("ORD-") or len(value) != 8:
            raise ValueError("order_id must look like ORD-0001")
        return value


class DiscountedOrder(Order):
    """Inheritance plus cross-field validation."""

    discount_percent: int = Field(ge=0, le=100)

    def requires_payment(self) -> bool:
        """Evaluate the nested, validated and discounted computed total."""
        return self.payable > 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def payable(self) -> float:
        factor = (100 - self.discount_percent) / 100
        return round(self.grand_total * factor, 2)
