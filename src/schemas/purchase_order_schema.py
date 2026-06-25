from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class PurchaseOrderUploadResponse(BaseModel):
    id: UUID
    po_number: str
    po_date: date
    status: str
    gcs_file_path: str
    line_items_saved: int


class PurchaseOrderUploadAcceptedResponse(BaseModel):
    task_id: str
    invoice_id: UUID | None = None
    extraction_status: str
    file_path: str


class PurchaseOrderListItem(BaseModel):
    id: UUID
    po_number: str
    po_date: date
    status: str
    total_amount: float | None
    currency: str
    created_at: datetime | None = None


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderListItem]
    total: int
