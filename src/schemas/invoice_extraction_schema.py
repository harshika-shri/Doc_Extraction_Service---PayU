from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

from src.utils.tax_details_utils import (
    normalize_tax_details,
)


class InvoiceLineItemExtractionSchema(BaseModel):
    line_number: int | None = None
    item_code: str | None = None
    item_description: str | None = None
    uom: str | None = None
    quantity_billed: Decimal | None = None
    unit_price: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_details: dict[str, Any] | None = None
    hsn_sac_code: str | None = None
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


class InvoiceVendorExtractionSchema(BaseModel):
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    vendor_address: str | None = None
    vendor_email: str | None = None
    vendor_phone: str | None = None
    bank_account_number: str | None = None
    bank_name: str | None = None
    ifsc_code: str | None = None
    account_holder_name: str | None = None


class InvoiceExtractionSchema(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    po_numbers_extracted: list[str] | None = None
    due_date: date | None = None
    currency: str | None = None
    payment_terms: str | None = None
    subtotal_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    notes: str | None = None
    company_name: str | None = None
    company_gstin: str | None = None
    company_address: str | None = None
    vendor: InvoiceVendorExtractionSchema | None = None
    line_items: list[InvoiceLineItemExtractionSchema] = []
