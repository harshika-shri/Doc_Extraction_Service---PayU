from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.postgres.base import Base
from src.data.models.postgres.enums import AllocationMatchType
from src.data.models.postgres.mixins import CreatedAtMixin


class InvoiceLinePOAllocation(Base, CreatedAtMixin):
    __tablename__ = "invoice_line_po_allocations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    invoice_line_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoice_line_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    po_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id"),
        nullable=False,
    )

    po_line_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("po_line_items.id"),
        nullable=False,
    )

    allocated_quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 3),
        nullable=False,
    )

    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    match_type: Mapped[AllocationMatchType | None] = mapped_column(
        Enum(AllocationMatchType),
        nullable=True,
    )

    match_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    is_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
