from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
    require_roles,
)
from src.core.services.extraction_review_service import (
    ExtractionReviewService,
)
from src.data.models.postgres.enums import UserRole
from src.data.models.postgres.users import User
from src.schemas.extraction_review_schema import (
    ExtractionApproveResponse,
    ExtractionReviewResponse,
    ExtractionUpdateRequest,
)

router = APIRouter(
    prefix="/extractions",
    tags=["Extractions"],
)


@router.get(
    "/{invoice_id}/review",
    response_model=ExtractionReviewResponse,
)
async def get_extraction_review(
    invoice_id: UUID,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> ExtractionReviewResponse:
    service = ExtractionReviewService(
        db,
    )

    return await service.get_review(
        invoice_id,
        current_user,
    )


@router.put(
    "/{invoice_id}",
    response_model=ExtractionReviewResponse,
)
async def update_extraction(
    invoice_id: UUID,
    payload: ExtractionUpdateRequest,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
        ),
    ),
) -> ExtractionReviewResponse:
    service = ExtractionReviewService(
        db,
    )

    return await service.update_extraction(
        invoice_id,
        payload,
        current_user,
    )


@router.post(
    "/{invoice_id}/approve",
    response_model=ExtractionApproveResponse,
)
async def approve_extraction(
    invoice_id: UUID,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
        ),
    ),
) -> ExtractionApproveResponse:
    service = ExtractionReviewService(
        db,
    )

    return await service.approve_extraction(
        invoice_id,
        current_user,
    )
