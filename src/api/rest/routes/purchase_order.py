from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
    require_roles,
)
from src.core.services.purchase_order_service import (
    PurchaseOrderService,
)
from src.data.models.postgres.enums import (
    ExtractionStatus,
    UserRole,
)
from src.data.models.postgres.users import User
from src.schemas.purchase_order_schema import (
    PurchaseOrderListResponse,
    PurchaseOrderUploadAcceptedResponse,
)
from src.tasks.extraction_tasks import (
    process_purchase_order,
)

router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"],
)


@router.post(
    "/upload",
    response_model=PurchaseOrderUploadAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
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
) -> PurchaseOrderUploadAcceptedResponse:
    service = PurchaseOrderService(
        db,
    )

    file_path = await service.stage_purchase_order_upload(
        file,
    )

    task = process_purchase_order.delay(
        file_path=str(
            file_path,
        ),
        company_id=str(
            current_user.company_id,
        ),
        uploaded_by=str(
            current_user.id,
        ),
    )

    return PurchaseOrderUploadAcceptedResponse(
        task_id=task.id,
        invoice_id=None,
        extraction_status=ExtractionStatus.PENDING.value,
        file_path=str(
            file_path,
        ),
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
