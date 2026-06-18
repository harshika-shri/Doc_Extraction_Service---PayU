from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceRecordPayload(BaseModel):
    field_name: str
    extracted_value: str | None = None
    confidence_score: Decimal
    is_flagged: bool = False


class ValidationIssuePayload(BaseModel):
    check_stage: str = "extraction"
    check_name: str = "low_confidence"
    field_name: str | None = None
    field_path: str | None = None
    issue_type: str = "low_confidence"
    description: str
    expected_value: str | None = None
    actual_value: str | None = None
    status: str = "open"
    metadata: dict[str, Any] | None = None


class ExtractedInvoicePayload(BaseModel):
    header_fields: dict[str, Any] = Field(
        default_factory=dict,
    )
    vendor_fields: dict[str, Any] = Field(
        default_factory=dict,
    )
    line_items: list[dict[str, Any]] = Field(
        default_factory=list,
    )
    confidence_records: list[
        ConfidenceRecordPayload
    ] = Field(
        default_factory=list,
    )
    validation_issues: list[
        ValidationIssuePayload
    ] = Field(
        default_factory=list,
    )
    has_low_confidence: bool = False


class ExtractedPurchaseOrderPayload(BaseModel):
    header_fields: dict[str, Any] = Field(
        default_factory=dict,
    )
    line_items: list[dict[str, Any]] = Field(
        default_factory=list,
    )
