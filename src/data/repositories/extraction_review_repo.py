from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select

from src.data.models.postgres.enums import ExtractionStatus
from src.data.models.postgres.extraction_field_confidence import (
    ExtractionFieldConfidence,
)
from src.data.models.postgres.invoice_extracted_vendor import (
    InvoiceExtractedVendor,
)
from src.data.models.postgres.invoice_line_items import InvoiceLineItem
from src.data.models.postgres.invoices import Invoice
from src.data.repositories.base_repo import BaseRepository


class ExtractionReviewRepository(BaseRepository):
    async def get_invoice_by_id(
        self,
        invoice_id: UUID,
    ) -> Invoice | None:
        stmt = select(
            Invoice,
        ).where(
            Invoice.id == invoice_id,
        )

        result = await self.execute(
            stmt,
        )

        return result.scalar_one_or_none()

    async def get_vendor_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> InvoiceExtractedVendor | None:
        stmt = select(
            InvoiceExtractedVendor,
        ).where(
            InvoiceExtractedVendor.invoice_id
            == invoice_id,
        )

        result = await self.execute(
            stmt,
        )

        return result.scalar_one_or_none()

    async def get_line_items_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> list[InvoiceLineItem]:
        stmt = (
            select(
                InvoiceLineItem,
            )
            .where(
                InvoiceLineItem.invoice_id
                == invoice_id,
            )
            .order_by(
                InvoiceLineItem.line_number.asc(),
            )
        )

        result = await self.execute(
            stmt,
        )

        return list(
            result.scalars().all(),
        )

    async def get_confidence_scores_by_invoice_id(
        self,
        invoice_id: UUID,
    ) -> list[ExtractionFieldConfidence]:
        stmt = (
            select(
                ExtractionFieldConfidence,
            )
            .where(
                ExtractionFieldConfidence.invoice_id
                == invoice_id,
            )
            .order_by(
                ExtractionFieldConfidence.field_name.asc(),
            )
        )

        result = await self.execute(
            stmt,
        )

        return list(
            result.scalars().all(),
        )

    async def update_invoice_header_fields(
        self,
        invoice: Invoice,
        header_fields: dict,
    ) -> Invoice:
        for field_name, value in header_fields.items():
            setattr(
                invoice,
                field_name,
                value,
            )

        await self.session.flush()

        return invoice

    async def create_vendor(
        self,
        invoice_id: UUID,
        vendor_fields: dict,
    ) -> InvoiceExtractedVendor:
        vendor = InvoiceExtractedVendor(
            invoice_id=invoice_id,
            **vendor_fields,
        )

        self.session.add(
            vendor,
        )
        await self.session.flush()

        return vendor

    async def update_vendor_fields(
        self,
        vendor: InvoiceExtractedVendor,
        vendor_fields: dict,
    ) -> InvoiceExtractedVendor:
        for field_name, value in vendor_fields.items():
            setattr(
                vendor,
                field_name,
                value,
            )

        await self.session.flush()

        return vendor

    async def replace_line_items(
        self,
        invoice_id: UUID,
        line_item_fields_list: list[dict],
    ) -> list[InvoiceLineItem]:
        await self.execute(
            delete(
                InvoiceLineItem,
            ).where(
                InvoiceLineItem.invoice_id
                == invoice_id,
            ),
        )

        line_items: list[InvoiceLineItem] = []

        for line_item_fields in line_item_fields_list:
            line_item = InvoiceLineItem(
                invoice_id=invoice_id,
                **line_item_fields,
            )
            self.session.add(
                line_item,
            )
            line_items.append(
                line_item,
            )

        await self.session.flush()

        return line_items

    async def update_extraction_status(
        self,
        invoice: Invoice,
        extraction_status: ExtractionStatus,
    ) -> Invoice:
        invoice.extraction_status = extraction_status
        await self.session.flush()

        return invoice
