from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.gmail_notification_service import (
    GmailNotificationService,
)
from src.data.models.postgres.gmail_monitoring_state import (
    GmailMonitoringState,
)
from src.data.repositories.gmail_monitoring_repo import (
    GmailMonitoringRepository,
)
from src.handlers.gmail.gmail_watch import (
    GmailWatch,
)


class GmailMonitoringService:
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

    async def start_monitoring(
        self,
        email_address: str,
    ) -> dict[str, str]:
        watch = GmailWatch()

        watch_response = (
            watch.start_watch()
        )

        current_history_id = int(
            watch_response[
                "history_id"
            ]
        )

        state = (
            await self.repo.get_by_email(
                email_address,
            )
        )

        if state is None:
            state = (
                GmailMonitoringState(
                    email_address=email_address,
                    last_processed_history_id=current_history_id,
                    is_monitoring=True,
                )
            )

            await self.repo.create(
                state,
            )

            return {
                "message": (
                    "Monitoring started"
                ),
                "history_id": str(
                    current_history_id,
                ),
                "messages_processed": "0",
            }

        await self.repo.update_monitoring_state(
            state=state,
            history_id=(
                state.last_processed_history_id
            ),
            is_monitoring=True,
        )

        refreshed_state = (
            await self.repo.get_by_email(
                email_address,
            )
        )

        if refreshed_state is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Failed to load monitoring state"
                ),
            )

        notification_service = (
            GmailNotificationService(
                self.session,
            )
        )

        processed_messages = (
            await notification_service.process_pending_messages(
                state=refreshed_state,
                end_history_id=current_history_id,
            )
        )

        return {
            "message": (
                "Monitoring started"
            ),
            "history_id": str(
                current_history_id,
            ),
            "messages_processed": str(
                len(
                    processed_messages,
                ),
            ),
        }

    async def stop_monitoring(
        self,
        email_address: str,
    ) -> dict[str, str]:
        state = (
            await self.repo.get_by_email(
                email_address,
            )
        )

        if state is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Monitoring state not found"
                ),
            )

        watch = GmailWatch()

        watch.stop_watch()

        last_processed_history_id = (
            state.last_processed_history_id
        )

        await self.repo.update_monitoring_state(
            state=state,
            history_id=last_processed_history_id,
            is_monitoring=False,
        )

        return {
            "message": (
                "Monitoring stopped"
            ),
            "history_id": str(
                last_processed_history_id,
            ),
        }
