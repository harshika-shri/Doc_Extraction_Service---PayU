from pathlib import Path

from src.core.services.purchase_order.po_extraction_orchestrator import (
    POExtractionOrchestrator,
)
from src.schemas.po_extraction_schema import (
    POExtractionSchema,
)


class POExtractionService:
    def __init__(self) -> None:
        self._orchestrator = (
            POExtractionOrchestrator()
        )

    def extract_purchase_order(
        self,
        file_path: Path,
    ) -> POExtractionSchema:
        return self._orchestrator.extract(
            file_path,
        ).extraction

    def extract_purchase_order_with_confidence(
        self,
        file_path: Path,
    ):
        return self._orchestrator.extract(
            file_path,
        )
