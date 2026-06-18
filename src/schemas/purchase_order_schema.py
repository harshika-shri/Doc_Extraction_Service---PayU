from datetime import date
from uuid import UUID

from pydantic import BaseModel


class PurchaseOrderUploadResponse(BaseModel):
    id: UUID
    po_number: str
    po_date: date
    status: str
    gcs_file_path: str
    line_items_saved: int
