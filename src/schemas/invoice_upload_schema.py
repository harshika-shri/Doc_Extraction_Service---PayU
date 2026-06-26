from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class InvoiceUploadResponse(BaseModel):
    invoice_id: UUID | None
    extraction_status: str | None
    document_type: str
    message: str
