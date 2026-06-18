from uuid import UUID

from src.data.models.postgres.invoice_line_items import (
    InvoiceLineItem,
)
from src.data.repositories.base_repo import BaseRepository


class InvoiceLineItemRepository(BaseRepository):
    async def create(
        self,
        invoice_id: UUID,
        line_item_fields: dict,
    ) -> InvoiceLineItem:
        line_item = InvoiceLineItem(
            invoice_id=invoice_id,
            **line_item_fields,
        )

        self.session.add(line_item)

        return line_item
