from uuid import UUID

from pydantic import BaseModel


class ExtractionTaskAcceptedResponse(BaseModel):
    task_id: str
    invoice_id: UUID | None = None
    extraction_status: str
