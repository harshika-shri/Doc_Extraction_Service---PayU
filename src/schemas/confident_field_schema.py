from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class ConfidentField(BaseModel, Generic[T]):
    value: T | None = None
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_input(
        cls,
        data: Any,
    ) -> Any:
        if data is None:
            return {}

        return data

