from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.data.models.postgres.notifications import Notification
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class NotificationRow:
    id: UUID
    user_id: UUID
    invoice_id: UUID | None
    title: str
    message: str
    is_read: bool
    created_at: datetime


class NotificationRepository(BaseRepository):
    async def create(
        self,
        *,
        user_id: UUID,
        invoice_id: UUID | None,
        title: str,
        message: str,
    ) -> NotificationRow:
        notification = Notification(
            user_id=user_id,
            invoice_id=invoice_id,
            title=title,
            message=message,
            is_read=False,
        )
        self.session.add(notification)
        await self.session.flush()

        return NotificationRow(
            id=notification.id,
            user_id=notification.user_id,
            invoice_id=notification.invoice_id,
            title=notification.title,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )
