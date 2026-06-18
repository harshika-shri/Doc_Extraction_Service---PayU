import base64
import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependencies import (
    get_db_session,
)
from src.core.services.gmail_notification_service import (
    GmailNotificationService,
)

router = APIRouter(
    prefix="/gmail",
    tags=["Gmail Webhook"],
)


@router.post(
    "/webhook",
)
async def gmail_webhook(
    request: Request,
    db: AsyncSession = Depends(
        get_db_session,
    ),
) -> dict[str, str]:
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

    service = (
        GmailNotificationService(
            db,
        )
    )

    return await service.process_notification(
        email_address=gmail_data[
            "emailAddress"
        ],
        history_id=int(
            gmail_data[
                "historyId"
            ],
        ),
    )
