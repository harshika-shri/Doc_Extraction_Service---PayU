from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
    require_roles,
)
from src.core.services.purchase_order_service import (
    PurchaseOrderService,
)
from src.data.models.postgres.enums import UserRole
from src.data.models.postgres.users import User
from src.schemas.purchase_order_schema import (
    PurchaseOrderDetailResponse,
    PurchaseOrderListResponse,
    PurchaseOrderUploadResponse,
)
from src.utils.file_utils import guess_mime_type

router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"],
)


@router.post(
    "/upload",
    response_model=PurchaseOrderUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_purchase_order(
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
) -> PurchaseOrderUploadResponse:
    service = PurchaseOrderService(
        db,
    )

    return await service.upload_purchase_order(
        file,
        current_user,
        request=request,
    )


@router.get(
    "",
    response_model=PurchaseOrderListResponse,
)
async def list_purchase_orders(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> PurchaseOrderListResponse:
    service = PurchaseOrderService(
        db,
    )

    return await service.list_purchase_orders(
        current_user=current_user,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{po_id}",
    response_model=PurchaseOrderDetailResponse,
)
async def get_purchase_order(
    po_id: UUID,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> PurchaseOrderDetailResponse:
    service = PurchaseOrderService(
        db,
    )

    return await service.get_purchase_order_detail(
        po_id,
        current_user,
    )


@router.get(
    "/{po_id}/document",
    response_class=FileResponse,
)
async def get_purchase_order_document(
    po_id: UUID,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    current_user: User = Depends(
        require_roles(
            UserRole.FINANCE_ASSOCIATE,
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> FileResponse:
    service = PurchaseOrderService(
        db,
    )

    file_path = await service.get_purchase_order_file_path(
        po_id,
        current_user,
    )

    return FileResponse(
        path=str(file_path),
        media_type=guess_mime_type(file_path),
        filename=file_path.name,
    )
