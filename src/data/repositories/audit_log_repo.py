from __future__ import annotations

from uuid import UUID

from src.data.models.postgres.audit_log import AuditLog
from src.data.repositories.base_repo import BaseRepository


class AuditLogRepository(BaseRepository):
    async def create(
        self,
        *,
        invoice_id: UUID,
        action: str,
        old_status: str | None,
        new_status: str | None,
        remarks: str | None,
        performed_by: UUID | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            invoice_id=invoice_id,
            action=action,
            old_status=old_status,
            new_status=new_status,
            remarks=remarks,
            performed_by=performed_by,
        )
        self.session.add(
            audit_log,
        )
        await self.session.flush()

        return audit_log
