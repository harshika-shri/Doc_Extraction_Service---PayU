from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
    require_roles,
)
from src.core.services.invoice_service import (
    InvoiceService,
)
from src.core.services.invoice_upload_service import (
    InvoiceUploadService,
)
from src.data.models.postgres.enums import UserRole
from src.data.models.postgres.users import User
from src.schemas.invoice_schema import (
    InvoiceProcessingListResponse,
)
from src.schemas.invoice_upload_schema import (
    InvoiceUploadResponse,
)

router = APIRouter(
    prefix="/invoices",
    tags=["Invoices"],
)


@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_invoice(
    file: UploadFile = File(
        ...,
    ),
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> InvoiceUploadResponse:
    service = InvoiceUploadService(
        db,
    )

    return await service.upload_and_process(
        file,
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
