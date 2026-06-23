from fastapi import APIRouter, Depends, File, UploadFile
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
    PurchaseOrderListResponse,
    PurchaseOrderUploadResponse,
)

router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"],
)


@router.post(
    "/upload",
    response_model=PurchaseOrderUploadResponse,
)
async def upload_purchase_order(
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
        file=file,
        current_user=current_user,
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
        limit=limit,
        offset=offset,
    )
