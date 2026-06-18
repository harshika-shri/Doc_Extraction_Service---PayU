from pydantic import BaseModel

from src.constants.document_type import (
    DocumentType,
)


class DocumentClassificationSchema(
    BaseModel,
):
    document_type: DocumentType
    confidence: float | None = None
    reason: str | None = None
