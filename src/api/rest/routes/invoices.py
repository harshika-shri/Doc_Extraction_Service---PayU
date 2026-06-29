from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
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
from src.data.repositories.invoice_repo import InvoiceRepository
from src.schemas.invoice_schema import (
    InvoiceProcessingListResponse,
)
from src.schemas.invoice_upload_schema import (
    InvoiceUploadResponse,
)
from src.utils.file_utils import guess_mime_type

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
    request: Request,
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
        request=request,
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


@router.get(
    "/{invoice_id}/document",
    response_class=FileResponse,
)
async def get_invoice_document(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    _: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> FileResponse:
    repo = InvoiceRepository(db)
    invoice = await repo.get_by_id(invoice_id)

    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )

    # gcs_file_path is stored as a relative path (e.g. "uploads/invoices/...")
    # Resolve against the working directory (/app inside Docker)
    file_path = Path(invoice.gcs_file_path)
    if not file_path.is_absolute():
        file_path = Path("/app") / file_path

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on server.",
        )

    mime_type = guess_mime_type(file_path)

    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=file_path.name,
    )
