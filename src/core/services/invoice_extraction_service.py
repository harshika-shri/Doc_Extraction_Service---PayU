from pathlib import Path

from src.core.services.invoice.invoice_extraction_orchestrator import (
    InvoiceExtractionOrchestrator,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
)


class InvoiceExtractionService:
    def __init__(self) -> None:
        self._orchestrator = (
            InvoiceExtractionOrchestrator()
        )

    def extract_invoice_from_file(
        self,
        file_path: Path,
    ) -> InvoiceExtractionSchema:
        return self._orchestrator.extract(
            file_path,
        ).extraction

    def extract_invoice_with_confidence(
        self,
        file_path: Path,
    ):
        return self._orchestrator.extract(
            file_path,
        )
