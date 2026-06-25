from __future__ import annotations

from src.core.exceptions.base_exc import AppException


class ExtractionReviewNotFoundError(AppException):
    def __init__(
        self,
        invoice_id: str,
    ) -> None:
        super().__init__(
            detail=f"Invoice extraction not found: {invoice_id}",
            status_code=404,
            error_code="EXTRACTION_NOT_FOUND",
        )


class ExtractionReviewAccessDeniedError(AppException):
    def __init__(
        self,
    ) -> None:
        super().__init__(
            detail="You do not have access to this invoice",
            status_code=403,
            error_code="EXTRACTION_ACCESS_DENIED",
        )


class ExtractionReviewStateError(AppException):
    def __init__(
        self,
        detail: str,
    ) -> None:
        super().__init__(
            detail=detail,
            status_code=400,
            error_code="EXTRACTION_INVALID_STATE",
        )


class ExtractionReviewValidationError(AppException):
    def __init__(
        self,
        detail: str,
    ) -> None:
        super().__init__(
            detail=detail,
            status_code=422,
            error_code="EXTRACTION_VALIDATION_ERROR",
        )
