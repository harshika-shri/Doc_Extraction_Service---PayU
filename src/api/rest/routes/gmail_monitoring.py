from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
)
from src.core.services.gmail_monitoring_service import (
    GmailMonitoringService,
)
from src.data.models.postgres.enums import (
    ExtractionStatus,
)
from src.schemas.extraction_task_schema import (
    ExtractionTaskAcceptedResponse,
)
from src.schemas.gmail_monitoring_schema import (
    MonitoringStatusResponse,
    StartMonitoringRequest,
    StopMonitoringRequest,
)
from src.tasks.extraction_tasks import (
    process_invoice,
)

router = APIRouter(
    prefix="/gmail-monitoring",
    tags=["Gmail Monitoring"],
)


@router.post(
    "/start",
    response_model=ExtractionTaskAcceptedResponse,
)
async def start_monitoring(
    payload: StartMonitoringRequest,
    db: AsyncSession = Depends(
        get_db_session,
    ),
) -> ExtractionTaskAcceptedResponse:
    service = (
        GmailMonitoringService(
            db,
        )
    )

    result = await service.start_monitoring(
        payload.email_address,
    )

    task = process_invoice.delay(
        email_address=payload.email_address,
        history_id=int(
            result[
                "history_id"
            ],
        ),
    )

    return ExtractionTaskAcceptedResponse(
        task_id=task.id,
        invoice_id=None,
        extraction_status=ExtractionStatus.PENDING.value,
    )


@router.post(
    "/stop",
)
async def stop_monitoring(
    payload: StopMonitoringRequest,
    db: AsyncSession = Depends(
        get_db_session,
    ),
) -> dict[str, str]:
    service = (
        GmailMonitoringService(
            db,
        )
    )

    return await service.stop_monitoring(
        payload.email_address,
    )


@router.get(
    "/status",
    response_model=MonitoringStatusResponse,
)
async def get_monitoring_status(
    email_address: str,
    db: AsyncSession = Depends(
        get_db_session,
    ),
) -> MonitoringStatusResponse:
    service = GmailMonitoringService(
        db,
    )

    return await service.get_monitoring_status(
        email_address,
    )
