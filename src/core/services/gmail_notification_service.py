import asyncio
import traceback
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.core.services.document_processing_service import (
    DocumentProcessingService,
)
from src.core.services.invoice_service import (
    InvoiceService,
)
from src.data.models.postgres.gmail_monitoring_state import (
    GmailMonitoringState,
)
from src.data.repositories.gmail_monitoring_repo import (
    GmailMonitoringRepository,
)
from src.handlers.gmail.gmail_client import (
    GmailClient,
)
from src.handlers.gmail.gmail_message_handler import (
    GmailMessageHandler,
)
from src.schemas.gmail_message_schema import (
    GmailMessageSchema,
)

_mailbox_processing_locks: dict[
    str,
    asyncio.Lock,
] = {}


def _get_mailbox_lock(
    email_address: str,
) -> asyncio.Lock:
    lock = _mailbox_processing_locks.get(
        email_address,
    )

    if lock is None:
        lock = asyncio.Lock()
        _mailbox_processing_locks[
            email_address
        ] = lock

    return lock


class GmailNotificationService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session
        self.repo = (
            GmailMonitoringRepository(
                session,
            )
        )

    async def process_notification(
        self,
        email_address: str,
        history_id: int,
    ) -> dict[str, str]:
        state = (
            await self.repo.get_by_email(
                email_address,
            )
        )

        if state is None:
            return {
                "status": (
                    "monitoring_state_not_found"
                ),
            }

        if not state.is_monitoring:
            return {
                "status": (
                    "monitoring_inactive"
                ),
            }

        processed_messages = (
            await self.process_pending_messages(
                state=state,
                end_history_id=history_id,
            )
        )

        return {
            "status": "processed",
            "messages_processed": str(
                len(
                    processed_messages,
                ),
            ),
        }

    async def process_pending_messages(
        self,
        state: GmailMonitoringState,
        end_history_id: int,
    ) -> list[
        GmailMessageSchema
    ]:
        email_address = state.email_address
        lock = _get_mailbox_lock(
            email_address,
        )

        async with lock:
            current_state = (
                await self.repo.get_by_email(
                    email_address,
                )
            )

            if current_state is None:
                return []

            stored_history_id = (
                current_state.last_processed_history_id
            )
            is_monitoring = (
                current_state.is_monitoring
            )

            if (
                end_history_id
                <= stored_history_id
            ):
                print(
                    "No new Gmail history to process. "
                    f"stored={stored_history_id}, "
                    f"incoming={end_history_id}",
                )
                return []

            message_handler = (
                GmailMessageHandler(
                    service=GmailClient.get_service(),
                    attachment_download_dir=Path(
                        settings.GMAIL_ATTACHMENT_DOWNLOAD_DIR,
                    ),
                )
            )

            message_ids = (
                message_handler.get_message_ids_from_history(
                    start_history_id=stored_history_id,
                )
            )

            invoice_service = InvoiceService(
                self.session,
            )
            processed_messages: list[
                GmailMessageSchema
            ] = []

            for message_id in message_ids:
                if await invoice_service.message_already_processed(
                    message_id,
                ):
                    print(
                        "Skipping already processed "
                        f"message: {message_id}",
                    )
                    continue

                try:
                    message = (
                        message_handler.fetch_message(
                            message_id,
                        )
                    )

                    self._print_message(
                        message,
                    )

                    if message.attachments:
                        document_processing_service = (
                            DocumentProcessingService(
                                self.session,
                            )
                        )
                        await document_processing_service.process_message_attachments(
                            message,
                        )

                    processed_messages.append(
                        message,
                    )
                except Exception:
                    print(
                        f"\nFailed to process message "
                        f"{message_id}:",
                    )
                    traceback.print_exc()
                    await self.session.rollback()

            refreshed_state = (
                await self.repo.get_by_email(
                    email_address,
                )
            )

            if refreshed_state is None:
                return processed_messages

            await self.repo.update_monitoring_state(
                state=refreshed_state,
                history_id=end_history_id,
                is_monitoring=is_monitoring,
            )

            return processed_messages

    @staticmethod
    def _print_message(
        message: GmailMessageSchema,
    ) -> None:
        print("\n" + "=" * 80)
        print("NEW EMAIL RECEIVED")
        print("=" * 80)
        print(
            f"Message ID: "
            f"{message.message_id}",
        )
        print(
            f"Subject: "
            f"{message.subject}",
        )
        print("\nBody:")
        print(message.body)

        if message.attachments:
            print("\nAttachments:")
            for attachment in message.attachments:
                print(
                    f"- "
                    f"{attachment.filename} "
                    f"-> "
                    f"{attachment.file_path}",
                )
        else:
            print(
                "\nNo attachments found.",
            )
