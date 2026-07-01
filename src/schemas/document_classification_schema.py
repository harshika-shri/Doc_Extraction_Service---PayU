from pydantic import BaseModel, field_validator

from src.constants.document_format import (
    DocumentFormat,
)
from src.constants.document_type import (
    DocumentType,
)


class DocumentClassificationSchema(
    BaseModel,
):
    document_type: DocumentType
    document_format: DocumentFormat | None = None
    confidence: float | None = None
    reason: str | None = None

    @field_validator(
        "document_format",
        mode="before",
    )
    @classmethod
    def normalize_document_format(
        cls,
        value: object,
    ) -> DocumentFormat | None:
        if value is None or value == "null":
            return None

        if isinstance(
            value,
            DocumentFormat,
        ):
            return value

        if isinstance(
            value,
            str,
        ):
            normalized = value.strip().lower()

            if normalized in {
                "",
                "null",
                "none",
            }:
                return None

            return DocumentFormat(
                normalized,
            )

        return None
