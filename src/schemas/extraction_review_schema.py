from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.utils.tax_details_utils import (
    normalize_tax_details,
)


class InvoiceHeaderReview(BaseModel):
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


class CompanyDetailsReview(BaseModel):
    company_name: str | None = None
    company_gstin: str | None = None
    company_address: str | None = None


class VendorDetailsReview(BaseModel):
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    vendor_address: str | None = None
    vendor_email: str | None = None
    vendor_phone: str | None = None


class BankDetailsReview(BaseModel):
    bank_account_number: str | None = None
    bank_name: str | None = None
    ifsc_code: str | None = None
    account_holder_name: str | None = None


class LineItemReview(BaseModel):
    id: UUID | None = None
    line_number: int
    item_code: str | None = None
    item_description: str | None = None
    uom: str | None = None
    quantity_billed: Decimal
    unit_price: Decimal
    discount_amount: Decimal | None = None
    tax_details: dict[str, Any] | None = None
    hsn_sac_code: str | None = None
    line_total: Decimal

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


class LineItemUpdate(BaseModel):
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


class FieldConfidenceReview(BaseModel):
    id: UUID
    field_name: str
    extracted_value: str | None
    confidence_score: float
    is_flagged: bool


class ExtractionReviewResponse(BaseModel):
    invoice_id: UUID
    invoice_header: InvoiceHeaderReview
    vendor_details: VendorDetailsReview | None = None
    company_details: CompanyDetailsReview
    bank_details: BankDetailsReview | None = None
    line_items: list[LineItemReview] = Field(
        default_factory=list,
    )
    field_confidence_scores: list[FieldConfidenceReview] = Field(
        default_factory=list,
    )
    extraction_status: str


class ExtractionUpdateRequest(BaseModel):
    invoice_header: InvoiceHeaderReview | None = None
    vendor_details: VendorDetailsReview | None = None
    company_details: CompanyDetailsReview | None = None
    bank_details: BankDetailsReview | None = None
    line_items: list[LineItemUpdate] | None = None


class ExtractionApproveResponse(BaseModel):
    invoice_id: UUID
    extraction_status: str
    message: str
