from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from src.data.models.postgres.enums import (
    PurchaseOrderStatus,
)
from src.data.models.postgres.purchase_orders import (
    PurchaseOrder,
)
from src.data.repositories.base_repo import BaseRepository


class PurchaseOrderRepository(BaseRepository):
    async def exists_for_gcs_file_path(
        self,
        gcs_file_path: str,
    ) -> bool:
        stmt = select(
            PurchaseOrder.id,
        ).where(
            PurchaseOrder.gcs_file_path
            == gcs_file_path,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def exists_for_po_number(
        self,
        po_number: str,
    ) -> bool:
        stmt = select(
            PurchaseOrder.id,
        ).where(
            PurchaseOrder.po_number == po_number,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def get_by_gcs_file_path(
        self,
        gcs_file_path: str,
    ) -> PurchaseOrder | None:
        stmt = select(
            PurchaseOrder,
        ).where(
            PurchaseOrder.gcs_file_path
            == gcs_file_path,
        )

        result = await self.execute(stmt)

        return result.scalar_one_or_none()

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

    async def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PurchaseOrder], int]:
        count_stmt = select(
            func.count(),
        ).select_from(
            PurchaseOrder,
        )
        count_result = await self.execute(
            count_stmt,
        )
        total = int(
            count_result.scalar_one(),
        )

        stmt = (
            select(
                PurchaseOrder,
            )
            .order_by(
                PurchaseOrder.created_at.desc(),
            )
            .limit(
                limit,
            )
            .offset(
                offset,
            )
        )
        result = await self.execute(
            stmt,
        )

        return (
            list(
                result.scalars().all(),
            ),
            total,
        )
