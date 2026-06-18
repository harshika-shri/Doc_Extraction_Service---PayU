from decimal import Decimal
from uuid import UUID

from src.data.models.postgres.enums import (
    PurchaseOrderStatus,
)
from src.data.models.postgres.purchase_orders import (
    PurchaseOrder,
)
from src.data.repositories.base_repo import BaseRepository


class PurchaseOrderRepository(BaseRepository):
    async def create(
        self,
        gcs_file_path: str,
        company_id: UUID,
        uploaded_by: UUID,
        header_fields: dict,
    ) -> PurchaseOrder:
        purchase_order = PurchaseOrder(
            gcs_file_path=gcs_file_path,
            company_id=company_id,
            uploaded_by=uploaded_by,
            status=PurchaseOrderStatus.OPEN,
            currency=header_fields.get(
                "currency",
                "INR",
            ),
            discount_amount=header_fields.get(
                "discount_amount",
                Decimal("0"),
            ),
            **{
                key: value
                for key, value in header_fields.items()
                if key
                not in {
                    "currency",
                    "discount_amount",
                }
            },
        )

        self.session.add(purchase_order)

        await self.session.flush()

        return purchase_order

    async def flush(self) -> None:
        await self.session.flush()
