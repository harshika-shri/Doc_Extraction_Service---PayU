from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.data.models.postgres.processed_gmail_message import (
    ProcessedGmailMessage,
)
from src.data.repositories.base_repo import BaseRepository


class ProcessedGmailMessageRepository(BaseRepository):
    async def exists(
        self,
        message_id: str,
    ) -> bool:
        stmt = select(
            ProcessedGmailMessage.message_id,
        ).where(
            ProcessedGmailMessage.message_id
            == message_id,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def mark_processed(
        self,
        *,
        message_id: str,
        email_address: str,
    ) -> None:
        stmt = (
            insert(
                ProcessedGmailMessage,
            )
            .values(
                message_id=message_id,
                email_address=email_address,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "message_id",
                ],
            )
        )

        await self.execute(stmt)
        await self.session.flush()
