import base64
import json

from fastapi import APIRouter, Request

from src.data.models.postgres.enums import (
    ExtractionStatus,
)
from src.schemas.extraction_task_schema import (
    ExtractionTaskAcceptedResponse,
)
from src.tasks.extraction_tasks import (
    process_invoice,
)
from src.utils.gmail_history_cache import (
    is_monitoring_active,
)
from src.utils.gmail_notification_coordinator import (
    should_enqueue_gmail_worker,
    update_pending_history_id,
)

router = APIRouter(
    prefix="/gmail",
    tags=["Gmail Webhook"],
)


@router.post(
    "/webhook",
    response_model=ExtractionTaskAcceptedResponse,
)
async def gmail_webhook(
    request: Request,
) -> ExtractionTaskAcceptedResponse:
    payload = await request.json()

    print("\n" + "=" * 80)
    print("PUBSUB MESSAGE RECEIVED")
    print("=" * 80)
    print(payload)

    encoded_data = payload["message"]["data"]

    decoded_data = (
        base64.b64decode(
            encoded_data,
        ).decode(
            "utf-8",
        )
    )

    gmail_data = json.loads(
        decoded_data,
    )

    print("\n" + "=" * 80)
    print("DECODED GMAIL DATA")
    print("=" * 80)
    print(gmail_data)

    email_address = gmail_data[
        "emailAddress"
    ]
    history_id = int(
        gmail_data[
            "historyId"
        ],
    )

    if not is_monitoring_active(
        email_address,
    ):
        print(
            "Skipping Gmail webhook for "
            f"{email_address}: monitoring is inactive.",
        )

        return ExtractionTaskAcceptedResponse(
            task_id="skipped-monitoring-inactive",
            invoice_id=None,
            extraction_status=ExtractionStatus.PENDING.value,
        )

    target_history_id = update_pending_history_id(
        email_address,
        history_id,
    )

    if not should_enqueue_gmail_worker(
        email_address,
        target_history_id,
    ):
        print(
            "Skipping Gmail webhook enqueue for "
            f"{email_address}: "
            f"history_id={target_history_id} "
            "(stale notification or worker already active).",
        )

        return ExtractionTaskAcceptedResponse(
            task_id="skipped-duplicate-notification",
            invoice_id=None,
            extraction_status=ExtractionStatus.PENDING.value,
        )

    task = process_invoice.delay(
        email_address=email_address,
        history_id=target_history_id,
    )

    print(
        f"Queued Celery task process_invoice: "
        f"task_id={task.id}, "
        f"history_id={target_history_id}",
    )

    return ExtractionTaskAcceptedResponse(
        task_id=task.id,
        invoice_id=None,
        extraction_status=ExtractionStatus.PENDING.value,
    )
