from typing import cast

from sqlalchemy import select

from src.data.models.postgres.gmail_monitoring_state import (
    GmailMonitoringState,
)
from src.data.repositories.base_repo import BaseRepository


class GmailMonitoringRepository(BaseRepository):
    async def get_by_email(
        self,
        email_address: str,
    ) -> GmailMonitoringState | None:
        stmt = select(
            GmailMonitoringState,
        ).where(
            GmailMonitoringState.email_address
            == email_address,
        )

        result = await self.execute(stmt)

        return cast(
            GmailMonitoringState | None,
            result.scalar_one_or_none(),
        )

    async def list_active(
        self,
    ) -> list[GmailMonitoringState]:
        stmt = select(
            GmailMonitoringState,
        ).where(
            GmailMonitoringState.is_monitoring.is_(
                True,
            ),
        )

        result = await self.execute(stmt)

        return list(
            result.scalars().all(),
        )

    async def create(
        self,
        state: GmailMonitoringState,
    ) -> GmailMonitoringState:
        self.session.add(
            state,
        )

        await self.session.commit()

        await self.session.refresh(
            state,
        )

        return state

    async def update_monitoring_state(
        self,
        state: GmailMonitoringState,
        history_id: int,
        is_monitoring: bool,
    ) -> GmailMonitoringState:
        state.last_processed_history_id = (
            history_id
        )

        state.is_monitoring = (
            is_monitoring
        )

        await self.session.flush()

        return state
