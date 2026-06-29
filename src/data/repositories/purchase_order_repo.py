from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from src.data.models.postgres.company_master import CompanyMaster
from src.data.models.postgres.enums import PurchaseOrderStatus
from src.data.models.postgres.po_line_items import POLineItem
from src.data.models.postgres.purchase_orders import PurchaseOrder
from src.data.models.postgres.users import User
from src.data.models.postgres.vendor_master import VendorMaster
from src.data.repositories.base_repo import BaseRepository


@dataclass(frozen=True, slots=True)
class PurchaseOrderListRow:
    id: UUID
    po_number: str
    po_date: date
    status: PurchaseOrderStatus
    total_amount: Decimal | None
    currency: str
    created_at: datetime
    uploaded_by_id: UUID | None
    uploaded_by_name: str | None
    uploaded_by_email: str | None


@dataclass(frozen=True, slots=True)
class PurchaseOrderDetailRow:
    id: UUID
    po_number: str
    po_date: date
    valid_until: date | None
    status: PurchaseOrderStatus
    currency: str
    payment_terms: str | None
    delivery_address: str | None
    subtotal_amount: Decimal | None
    discount_amount: Decimal
    tax_amount: Decimal | None
    total_amount: Decimal | None
    consumed_amount: Decimal
    gcs_file_path: str
    created_at: datetime
    updated_at: datetime
    uploaded_by_id: UUID | None
    uploaded_by_name: str | None
    uploaded_by_email: str | None
    vendor_name: str | None
    vendor_code: str | None
    vendor_gstin: str | None
    vendor_email: str | None
    company_name: str | None
    company_code: str | None
    company_gstin: str | None


@dataclass(frozen=True, slots=True)
class POLineItemRow:
    id: UUID
    line_number: int
    item_code: str | None
    item_description: str
    uom: str
    quantity_ordered: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal
    consumed_quantity: Decimal


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

    def _list_base_query(self, *, uploaded_by: UUID | None = None):
        stmt = (
            select(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                PurchaseOrder.po_date,
                PurchaseOrder.status,
                PurchaseOrder.total_amount,
                PurchaseOrder.currency,
                PurchaseOrder.created_at,
                PurchaseOrder.uploaded_by,
                User.name.label("uploaded_by_name"),
                User.email.label("uploaded_by_email"),
            )
            .select_from(PurchaseOrder)
            .outerjoin(User, PurchaseOrder.uploaded_by == User.id)
            .order_by(PurchaseOrder.created_at.desc())
        )

        if uploaded_by is not None:
            stmt = stmt.where(PurchaseOrder.uploaded_by == uploaded_by)

        return stmt

    async def list_for_viewer(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        uploaded_by: UUID | None = None,
    ) -> tuple[list[PurchaseOrderListRow], int]:
        count_stmt = select(func.count()).select_from(PurchaseOrder)
        if uploaded_by is not None:
            count_stmt = count_stmt.where(
                PurchaseOrder.uploaded_by == uploaded_by,
            )

        count_result = await self.execute(count_stmt)
        total = int(count_result.scalar_one())

        stmt = self._list_base_query(uploaded_by=uploaded_by).limit(limit).offset(offset)
        result = await self.execute(stmt)

        items = [
            PurchaseOrderListRow(
                id=row.id,
                po_number=row.po_number,
                po_date=row.po_date,
                status=row.status,
                total_amount=row.total_amount,
                currency=row.currency,
                created_at=row.created_at,
                uploaded_by_id=row.uploaded_by,
                uploaded_by_name=row.uploaded_by_name,
                uploaded_by_email=row.uploaded_by_email,
            )
            for row in result.all()
        ]

        return items, total

    async def get_detail_by_id(
        self,
        po_id: UUID,
    ) -> PurchaseOrderDetailRow | None:
        result = await self.execute(
            select(
                PurchaseOrder.id,
                PurchaseOrder.po_number,
                PurchaseOrder.po_date,
                PurchaseOrder.valid_until,
                PurchaseOrder.status,
                PurchaseOrder.currency,
                PurchaseOrder.payment_terms,
                PurchaseOrder.delivery_address,
                PurchaseOrder.subtotal_amount,
                PurchaseOrder.discount_amount,
                PurchaseOrder.tax_amount,
                PurchaseOrder.total_amount,
                PurchaseOrder.consumed_amount,
                PurchaseOrder.gcs_file_path,
                PurchaseOrder.created_at,
                PurchaseOrder.updated_at,
                PurchaseOrder.uploaded_by,
                User.name.label("uploaded_by_name"),
                User.email.label("uploaded_by_email"),
                VendorMaster.vendor_name,
                VendorMaster.vendor_code,
                VendorMaster.gstin.label("vendor_gstin"),
                VendorMaster.email.label("vendor_email"),
                CompanyMaster.company_name,
                CompanyMaster.company_code,
                CompanyMaster.gstin.label("company_gstin"),
            )
            .select_from(PurchaseOrder)
            .outerjoin(User, PurchaseOrder.uploaded_by == User.id)
            .outerjoin(VendorMaster, PurchaseOrder.vendor_id == VendorMaster.id)
            .outerjoin(CompanyMaster, PurchaseOrder.company_id == CompanyMaster.id)
            .where(PurchaseOrder.id == po_id),
        )
        row = result.one_or_none()

        if row is None:
            return None

        return PurchaseOrderDetailRow(
            id=row.id,
            po_number=row.po_number,
            po_date=row.po_date,
            valid_until=row.valid_until,
            status=row.status,
            currency=row.currency,
            payment_terms=row.payment_terms,
            delivery_address=row.delivery_address,
            subtotal_amount=row.subtotal_amount,
            discount_amount=row.discount_amount,
            tax_amount=row.tax_amount,
            total_amount=row.total_amount,
            consumed_amount=row.consumed_amount,
            gcs_file_path=row.gcs_file_path,
            created_at=row.created_at,
            updated_at=row.updated_at,
            uploaded_by_id=row.uploaded_by,
            uploaded_by_name=row.uploaded_by_name,
            uploaded_by_email=row.uploaded_by_email,
            vendor_name=row.vendor_name,
            vendor_code=row.vendor_code,
            vendor_gstin=row.vendor_gstin,
            vendor_email=row.vendor_email,
            company_name=row.company_name,
            company_code=row.company_code,
            company_gstin=row.company_gstin,
        )

    async def list_line_items(
        self,
        po_id: UUID,
    ) -> list[POLineItemRow]:
        result = await self.execute(
            select(POLineItem)
            .where(POLineItem.po_id == po_id)
            .order_by(POLineItem.line_number.asc()),
        )

        return [
            POLineItemRow(
                id=item.id,
                line_number=item.line_number,
                item_code=item.item_code,
                item_description=item.item_description,
                uom=item.uom,
                quantity_ordered=item.quantity_ordered,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                line_total=item.line_total,
                consumed_quantity=item.consumed_quantity,
            )
            for item in result.scalars().all()
        ]

    async def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PurchaseOrder], int]:
        """Deprecated — use list_for_viewer instead."""
        count_stmt = select(func.count()).select_from(PurchaseOrder)
        count_result = await self.execute(count_stmt)
        total = int(count_result.scalar_one())

        stmt = (
            select(PurchaseOrder)
            .order_by(PurchaseOrder.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.execute(stmt)

        return list(result.scalars().all()), total
