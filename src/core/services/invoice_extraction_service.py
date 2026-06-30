from pathlib import Path

from src.core.services.extraction.document_extraction_pipeline import (
    DocumentExtractionPipeline,
)
from src.core.services.invoice.invoice_extraction_orchestrator import (
    InvoiceExtractionResult,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
)


class InvoiceExtractionService:
    def __init__(self) -> None:
        self._pipeline = DocumentExtractionPipeline()

    def extract_invoice_from_file(
        self,
        file_path: Path,
    ) -> InvoiceExtractionSchema:
        return self._pipeline.extract_invoice(
            file_path,
        ).extraction

    def extract_invoice_with_confidence(
        self,
        file_path: Path,
    ) -> InvoiceExtractionResult:
        return self._pipeline.extract_invoice(
            file_path,
        )
