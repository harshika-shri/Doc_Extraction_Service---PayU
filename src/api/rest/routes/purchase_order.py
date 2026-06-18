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
