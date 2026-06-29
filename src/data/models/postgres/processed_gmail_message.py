from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.mixins import CreatedAtMixin


class ProcessedGmailMessage(Base, CreatedAtMixin):
    __tablename__ = "processed_gmail_messages"

    message_id: Mapped[str] = mapped_column(
        String(500),
        primary_key=True,
    )

    email_address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
