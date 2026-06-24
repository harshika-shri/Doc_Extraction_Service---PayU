from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class InvoiceProcessingItem(BaseModel):
    id: UUID
    invoice_number: str | None
    invoice_date: date | None
    received_email: str | None
    extraction_status: str
    invoice_status: str | None
    total_amount: float | None
    currency: str | None
    created_at: datetime | None


class InvoiceProcessingListResponse(BaseModel):
    items: list[InvoiceProcessingItem]
    total: int
