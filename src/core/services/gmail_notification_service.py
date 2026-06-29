import asyncio
import traceback
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.core.exceptions.gmail_exc import (
    GmailHistoryStaleError,
)
from src.core.services.document_processing_service import (
    DocumentProcessingService,
)
from src.core.services.invoice_service import (
    InvoiceService,
)
from src.messaging.post_commit import (
    discard_pending_extraction_events,
    publish_committed_extraction_events,
)
from src.data.models.postgres.gmail_monitoring_state import (
    GmailMonitoringState,
)
from src.data.repositories.gmail_monitoring_repo import (
    GmailMonitoringRepository,
)
from src.data.repositories.processed_gmail_message_repo import (
    ProcessedGmailMessageRepository,
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
from src.utils.gmail_history_cache import (
    cache_last_processed_history_id,
)
from src.utils.gmail_notification_coordinator import (
    claim_message_for_task,
    clear_pending_history_id,
    is_gmail_message_processed,
    mark_gmail_message_processed,
    release_message_claim,
    release_message_lock,
    try_acquire_message_lock,
)
from src.utils.transient_errors import (
    is_transient_error,
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
        *,
        task_id: str = "unknown",
    ) -> dict[str, str]:
        print(
            "\n"
            + "=" * 80
            + "\nGMAIL CELERY PROCESSING STARTED\n"
            + "=" * 80
        )
        print(
            f"email={email_address}, "
            f"history_id={history_id}",
        )

        state = (
            await self.repo.get_by_email(
                email_address,
            )
        )

        if state is None:
            print(
                "Gmail processing skipped: "
                "monitoring state not found. "
                "Start monitoring via "
                "/gmail-monitoring/start first.",
            )
            return {
                "status": (
                    "monitoring_state_not_found"
                ),
            }

        if not state.is_monitoring:
            print(
                "Gmail processing skipped: "
                "monitoring is inactive.",
            )
            return {
                "status": (
                    "monitoring_inactive"
                ),
            }

        processed_messages = (
            await self.process_pending_messages(
                state=state,
                end_history_id=history_id,
                task_id=task_id,
            )
        )

        print(
            "Gmail processing finished: "
            f"messages_processed="
            f"{len(processed_messages)}",
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
        *,
        task_id: str = "unknown",
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
                    "Skipping duplicate or stale "
                    "Gmail notification. "
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

            try:
                message_ids = (
                    message_handler.get_message_ids_from_history(
                        start_history_id=stored_history_id,
                    )
                )
            except GmailHistoryStaleError:
                return await self._recover_after_stale_history(
                    email_address=email_address,
                    message_handler=message_handler,
                    stored_history_id=stored_history_id,
                    end_history_id=end_history_id,
                    is_monitoring=is_monitoring,
                    task_id=task_id,
                )

            print(
                f"Gmail history fetch: "
                f"stored={stored_history_id}, "
                f"incoming={end_history_id}, "
                f"message_ids={len(message_ids)}",
            )

            message_ids = (
                message_handler.sort_message_ids_by_arrival(
                    message_ids,
                )
            )

            return await self._process_message_ids(
                email_address=email_address,
                message_ids=message_ids,
                message_handler=message_handler,
                end_history_id=end_history_id,
                is_monitoring=is_monitoring,
                task_id=task_id,
            )

    async def _recover_after_stale_history(
        self,
        *,
        email_address: str,
        message_handler: GmailMessageHandler,
        stored_history_id: int,
        end_history_id: int,
        is_monitoring: bool,
        task_id: str = "unknown",
    ) -> list[GmailMessageSchema]:
        mailbox_history_id = (
            message_handler.get_mailbox_history_id()
        )

        if (
            mailbox_history_id
            <= stored_history_id
        ):
            print(
                "Gmail history cursor is stale but "
                "mailbox history is not ahead of "
                f"stored={stored_history_id}. "
                "No backlog will be processed.",
            )
            return []

        message_ids = (
            message_handler.get_inbox_message_ids_for_recovery()
        )

        print(
            "Gmail history cursor is stale. "
            f"Recovering up to {len(message_ids)} "
            "INBOX messages before advancing cursor. "
            f"stored={stored_history_id}, "
            f"mailbox={mailbox_history_id}",
        )

        target_history_id = max(
            end_history_id,
            mailbox_history_id,
        )

        return await self._process_message_ids(
            email_address=email_address,
            message_ids=message_ids,
            message_handler=message_handler,
            end_history_id=target_history_id,
            is_monitoring=is_monitoring,
            task_id=task_id,
        )

    async def _process_message_ids(
        self,
        *,
        email_address: str,
        message_ids: list[str],
        message_handler: GmailMessageHandler,
        end_history_id: int,
        is_monitoring: bool,
        task_id: str = "unknown",
    ) -> list[GmailMessageSchema]:
        invoice_service = InvoiceService(
            self.session,
        )
        processed_message_repo = (
            ProcessedGmailMessageRepository(
                self.session,
            )
        )
        processed_messages: list[
            GmailMessageSchema
        ] = []
        had_failures = False
        had_deferred = False
        monitoring_stopped = False

        for message_id in message_ids:
            if not await self._is_monitoring_active(
                email_address,
            ):
                monitoring_stopped = True
                print(
                    "Stopping Gmail message processing "
                    "because monitoring is inactive.",
                )
                break

            if is_gmail_message_processed(
                message_id,
            ):
                print(
                    "Skipping already handled "
                    f"message: {message_id}",
                )
                continue

            if await invoice_service.message_already_processed(
                message_id,
            ):
                await processed_message_repo.mark_processed(
                    message_id=message_id,
                    email_address=email_address,
                )
                mark_gmail_message_processed(
                    message_id,
                )
                print(
                    "Skipping already processed "
                    f"message: {message_id}",
                )
                continue

            if not claim_message_for_task(
                message_id,
                task_id,
            ):
                had_deferred = True
                print(
                    "Deferring message already being "
                    f"processed by another task: {message_id}",
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
                else:
                    print(
                        "No processable attachments "
                        f"for message {message_id}.",
                    )

                processed_messages.append(
                    message,
                )
                await processed_message_repo.mark_processed(
                    message_id=message_id,
                    email_address=email_address,
                )
                mark_gmail_message_processed(
                    message_id,
                )
                release_message_claim(
                    message_id,
                    task_id,
                )
                await self.session.commit()
                publish_committed_extraction_events()
            except Exception as error:
                if is_transient_error(
                    error,
                ):
                    had_failures = True
                    print(
                        f"\nTransient failure processing "
                        f"message {message_id}:",
                    )
                    traceback.print_exc()
                    await self.session.rollback()
                    discard_pending_extraction_events()
                    raise

                release_message_claim(
                    message_id,
                    task_id,
                )
                had_failures = True
                print(
                    f"\nFailed to process message "
                    f"{message_id}:",
                )
                traceback.print_exc()
                await self.session.rollback()
                discard_pending_extraction_events()

        refreshed_state = (
            await self.repo.get_by_email(
                email_address,
            )
        )

        if refreshed_state is None:
            return processed_messages

        if (
            had_failures
            or had_deferred
            or monitoring_stopped
        ):
            reason = (
                "monitoring was stopped"
                if monitoring_stopped
                else (
                    "one or more messages failed to process"
                    if had_failures
                    else "one or more messages are still being processed"
                )
            )
            print(
                "Gmail history cursor not advanced "
                f"because {reason}. "
                f"stored remains "
                f"{refreshed_state.last_processed_history_id}.",
            )
            return processed_messages

        if (
            end_history_id
            <= refreshed_state.last_processed_history_id
        ):
            return processed_messages

        await self.session.commit()

        await self._advance_history_cursor(
            state=refreshed_state,
            history_id=end_history_id,
            is_monitoring=refreshed_state.is_monitoring,
        )
        clear_pending_history_id(
            email_address,
            history_id=end_history_id,
        )

        return processed_messages

    async def _is_monitoring_active(
        self,
        email_address: str,
    ) -> bool:
        state = await self.repo.get_by_email(
            email_address,
        )

        return (
            state is not None
            and state.is_monitoring
        )

    async def _advance_history_cursor(
        self,
        *,
        state: GmailMonitoringState,
        history_id: int,
        is_monitoring: bool,
    ) -> None:
        await self.repo.update_monitoring_state(
            state=state,
            history_id=history_id,
            is_monitoring=is_monitoring,
        )
        await self.session.commit()
        publish_committed_extraction_events()
        cache_last_processed_history_id(
            state.email_address,
            history_id,
        )

        print(
            "Gmail history cursor advanced to "
            f"{history_id}",
        )

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
