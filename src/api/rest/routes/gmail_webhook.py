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

    task = process_invoice.delay(
        email_address=gmail_data[
            "emailAddress"
        ],
        history_id=int(
            gmail_data[
                "historyId"
            ],
        ),
    )

    return ExtractionTaskAcceptedResponse(
        task_id=task.id,
        invoice_id=None,
        extraction_status=ExtractionStatus.PENDING.value,
    )
