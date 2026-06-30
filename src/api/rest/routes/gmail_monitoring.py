from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
    require_roles,
)
from src.config.settings import settings
from src.core.services.gmail_monitoring_service import (
    GmailMonitoringService,
)
from src.data.models.postgres.enums import (
    ExtractionStatus,
    UserRole,
)
from src.data.models.postgres.users import User
from src.data.repositories.invoice_email_repo import (
    InvoiceEmailRepository,
)
from src.data.repositories.invoice_repo import (
    InvoiceRepository,
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
from src.utils.file_utils import guess_mime_type
from src.utils.gmail_notification_coordinator import (
    should_enqueue_gmail_worker,
    update_pending_history_id,
)

router = APIRouter(
    prefix="/gmail-monitoring",
    tags=["Gmail Monitoring"],
)


def _resolve_storage_path(
    relative_path: str,
) -> Path:
    file_path = Path(
        relative_path,
    )

    if not file_path.is_absolute():
        file_path = Path(
            "/app",
        ) / file_path

    return file_path


@router.get(
    "/messages/{message_id}/attachment",
    response_class=FileResponse,
)
async def get_message_attachment(
    message_id: str,
    db: AsyncSession = Depends(
        get_db_session,
    ),
    _: User = Depends(
        require_roles(
            UserRole.FINANCE_MANAGER,
        ),
    ),
) -> FileResponse:
    email_repo = InvoiceEmailRepository(
        db,
    )
    invoice_email = (
        await email_repo.get_by_message_id(
            message_id,
        )
    )

    candidate_paths: list[Path] = []

    if (
        invoice_email is not None
        and invoice_email.gcs_attachment_path
    ):
        candidate_paths.append(
            _resolve_storage_path(
                invoice_email.gcs_attachment_path,
            ),
        )

    if invoice_email is not None:
        invoice_repo = InvoiceRepository(
            db,
        )
        invoice = await invoice_repo.get_by_id(
            invoice_email.invoice_id,
        )

        if (
            invoice is not None
            and invoice.gcs_file_path
        ):
            candidate_paths.append(
                _resolve_storage_path(
                    invoice.gcs_file_path,
                ),
            )

    attachment_dir = _resolve_storage_path(
        settings.GMAIL_ATTACHMENT_DOWNLOAD_DIR,
    ) / message_id

    if attachment_dir.is_dir():
        for child in sorted(
            attachment_dir.iterdir(),
        ):
            if child.is_file():
                candidate_paths.append(
                    child,
                )

    for file_path in candidate_paths:
        if file_path.exists() and file_path.is_file():
            return FileResponse(
                path=str(
                    file_path,
                ),
                media_type=guess_mime_type(
                    file_path,
                ),
                filename=file_path.name,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Attachment file not found.",
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

    target_history_id = update_pending_history_id(
        payload.email_address,
        int(
            result[
                "history_id"
            ],
        ),
    )

    task_id = "skipped-worker-active"

    if should_enqueue_gmail_worker(
        payload.email_address,
        target_history_id,
    ):
        task = process_invoice.delay(
            email_address=payload.email_address,
            history_id=target_history_id,
        )
        task_id = task.id

    return ExtractionTaskAcceptedResponse(
        task_id=task_id,
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
