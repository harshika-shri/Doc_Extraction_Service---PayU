from pathlib import Path

from src.core.services.extraction.document_extraction_pipeline import (
    DocumentExtractionPipeline,
)
from src.core.services.purchase_order.po_extraction_orchestrator import (
    POExtractionResult,
)
from src.schemas.po_extraction_schema import (
    POExtractionSchema,
)


class POExtractionService:
    def __init__(self) -> None:
        self._pipeline = DocumentExtractionPipeline()

    def extract_purchase_order(
        self,
        file_path: Path,
    ) -> POExtractionSchema:
        return self._pipeline.extract_purchase_order(
            file_path,
        ).extraction

    def extract_purchase_order_with_confidence(
        self,
        file_path: Path,
    ) -> POExtractionResult:
        return self._pipeline.extract_purchase_order(
            file_path,
        )
