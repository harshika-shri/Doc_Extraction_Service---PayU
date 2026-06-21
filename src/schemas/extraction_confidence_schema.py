from pydantic import BaseModel, Field


class FieldConfidenceItem(BaseModel):
    field_name: str
    confidence: float = Field(
        ge=0,
        le=100,
    )


class ExtractionConfidenceResponse(BaseModel):
    field_scores: list[FieldConfidenceItem] = Field(
        default_factory=list,
    )
