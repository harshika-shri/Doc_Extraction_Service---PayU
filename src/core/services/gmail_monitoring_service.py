from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.postgres.gmail_monitoring_state import (
    GmailMonitoringState,
)
from src.data.repositories.gmail_monitoring_repo import (
    GmailMonitoringRepository,
)
from src.handlers.gmail.gmail_watch import (
    GmailWatch,
)
from src.schemas.gmail_monitoring_schema import (
    MonitoringStatusResponse,
)
from src.utils.gmail_history_cache import (
    cache_last_processed_history_id,
    set_monitoring_active,
)
from src.utils.gmail_notification_coordinator import (
    clear_pending_history_id,
    force_release_gmail_worker,
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
            cache_last_processed_history_id(
                email_address,
                current_history_id,
            )
            set_monitoring_active(
                email_address,
                active=True,
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
        await self.session.commit()
        cache_last_processed_history_id(
            email_address,
            state.last_processed_history_id,
        )
        set_monitoring_active(
            email_address,
            active=True,
        )

        return {
            "message": (
                "Monitoring started"
            ),
            "history_id": str(
                current_history_id,
            ),
            "stored_history_id": str(
                state.last_processed_history_id,
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
        await self.session.commit()
        set_monitoring_active(
            email_address,
            active=False,
        )
        force_release_gmail_worker(
            email_address,
        )
        clear_pending_history_id(
            email_address,
        )

        return {
            "message": (
                "Monitoring stopped"
            ),
            "history_id": str(
                last_processed_history_id,
            ),
        }

    async def get_monitoring_status(
        self,
        email_address: str,
    ) -> MonitoringStatusResponse:
        state = await self.repo.get_by_email(
            email_address,
        )

        if state is None:
            return MonitoringStatusResponse(
                email_address=email_address,
                is_monitoring=False,
                last_processed_history_id=None,
            )

        return MonitoringStatusResponse(
            email_address=state.email_address,
            is_monitoring=state.is_monitoring,
            last_processed_history_id=state.last_processed_history_id,
        )
