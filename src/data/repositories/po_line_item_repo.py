from decimal import Decimal
from uuid import UUID

from src.data.models.postgres.po_line_items import (
    POLineItem,
)
from src.data.repositories.base_repo import BaseRepository


class POLineItemRepository(BaseRepository):
    async def create(
        self,
        po_id: UUID,
        line_item_fields: dict,
    ) -> POLineItem:
        line_item = POLineItem(
            po_id=po_id,
            discount_amount=line_item_fields.get(
                "discount_amount",
                Decimal("0"),
            ),
            **{
                key: value
                for key, value in line_item_fields.items()
                if key != "discount_amount"
            },
        )

        self.session.add(line_item)

        return line_item
