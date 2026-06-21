from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

from src.utils.tax_details_utils import (
    normalize_tax_details,
)


class POLineItemExtractionSchema(BaseModel):
    line_number: int | None = None
    item_code: str | None = None
    item_description: str | None = None
    uom: str | None = None
    quantity_ordered: Decimal | None = None
    unit_price: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_details: dict[str, Any] | None = None
    line_total: Decimal | None = None

    @field_validator(
        "tax_details",
        mode="before",
    )
    @classmethod
    def validate_tax_details(
        cls,
        value: Any,
    ) -> dict[str, Any] | None:
        return normalize_tax_details(
            value,
        )


class POExtractionSchema(BaseModel):
    po_number: str | None = None
    company_name: str | None = None
    company_gstin: str | None = None
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    delivery_address: str | None = None
    currency: str | None = None
    payment_terms: str | None = None
    po_date: date | None = None
    valid_until: date | None = None
    subtotal_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    line_items: list[POLineItemExtractionSchema] = []
