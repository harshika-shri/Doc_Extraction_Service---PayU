from uuid import UUID

from sqlalchemy import select

from src.data.models.postgres.invoice_emails import (
    InvoiceEmail,
)
from src.data.repositories.base_repo import BaseRepository


class InvoiceEmailRepository(BaseRepository):
    async def exists_for_message_id(
        self,
        message_id: str,
    ) -> bool:
        stmt = select(
            InvoiceEmail.id,
        ).where(
            InvoiceEmail.message_id
            == message_id,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def exists_for_invoice_id(
        self,
        invoice_id: UUID,
    ) -> bool:
        stmt = select(
            InvoiceEmail.id,
        ).where(
            InvoiceEmail.invoice_id
            == invoice_id,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def get_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> InvoiceEmail | None:
        stmt = select(
            InvoiceEmail,
        ).where(
            InvoiceEmail.invoice_id
            == invoice_id,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none()

    async def create(
        self,
        invoice_id: UUID,
        message_id: str,
        received_from: str,
        subject: str | None,
        body_text: str | None,
        attachment_filename: str | None,
        gcs_attachment_path: str | None,
    ) -> InvoiceEmail:
        invoice_email = InvoiceEmail(
            invoice_id=invoice_id,
            message_id=message_id,
            received_from=received_from,
            subject=subject,
            body_text=body_text,
            attachment_filename=attachment_filename,
            gcs_attachment_path=gcs_attachment_path,
        )

        self.session.add(invoice_email)
        await self.session.flush()

        return invoice_email
