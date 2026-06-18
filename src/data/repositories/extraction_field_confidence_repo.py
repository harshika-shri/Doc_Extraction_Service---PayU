from uuid import UUID

from src.data.models.postgres.extraction_field_confidence import (
    ExtractionFieldConfidence,
)
from src.data.repositories.base_repo import BaseRepository
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)


class ExtractionFieldConfidenceRepository(BaseRepository):
    async def create(
        self,
        invoice_id: UUID,
        record: ConfidenceRecordPayload,
    ) -> ExtractionFieldConfidence:
        field_confidence = ExtractionFieldConfidence(
            invoice_id=invoice_id,
            field_name=record.field_name,
            extracted_value=record.extracted_value,
            confidence_score=record.confidence_score,
            is_flagged=record.is_flagged,
        )

        self.session.add(field_confidence)

        return field_confidence
