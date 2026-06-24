from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
    require_roles,
)
from src.core.services.invoice_service import (
    InvoiceService,
)
from src.data.models.postgres.enums import UserRole
from src.data.models.postgres.users import User
from src.schemas.invoice_schema import (
    InvoiceProcessingListResponse,
)

router = APIRouter(
    prefix="/invoices",
    tags=["Invoices"],
)


@router.get(
    "/processing",
    response_model=InvoiceProcessingListResponse,
)
async def list_processing_invoices(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> InvoiceProcessingListResponse:
    service = InvoiceService(
        db,
    )

    return await service.list_processing_invoices(
        limit=limit,
        offset=offset,
    )
