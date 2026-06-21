from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.extraction_constants import (
    INVOICE_HEADER_FIELDS,
    INVOICE_LINE_ITEM_FIELDS,
    INVOICE_VENDOR_FIELDS,
)
from src.data.models.postgres.enums import (
    ExtractionStatus,
)
from src.data.models.postgres.invoices import Invoice
from src.data.models.postgres.vendor_master import VendorMaster
from src.data.repositories.extraction_field_confidence_repo import (
    ExtractionFieldConfidenceRepository,
)
from src.data.repositories.invoice_email_repo import (
    InvoiceEmailRepository,
)
from src.data.repositories.invoice_extracted_vendor_repo import (
    InvoiceExtractedVendorRepository,
)
from src.data.repositories.invoice_line_item_repo import (
    InvoiceLineItemRepository,
)
from src.data.repositories.invoice_repo import (
    InvoiceRepository,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
    ExtractedInvoicePayload,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
    InvoiceLineItemExtractionSchema,
)
from src.utils.tax_details_utils import (
    normalize_tax_details,
)


class InvoiceService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.invoice_repo = InvoiceRepository(
            session,
        )
        self.invoice_extracted_vendor_repo = (
            InvoiceExtractedVendorRepository(
                session,
            )
        )
        self.invoice_line_item_repo = (
            InvoiceLineItemRepository(
                session,
            )
        )
        self.invoice_email_repo = (
            InvoiceEmailRepository(
                session,
            )
        )
        self.confidence_repo = (
            ExtractionFieldConfidenceRepository(
                session,
            )
        )

    async def message_already_processed(
        self,
        gmail_message_id: str,
    ) -> bool:
        return (
            await self.invoice_repo.exists_for_gmail_message_id(
                gmail_message_id,
            )
        )

    async def attachment_already_processed(
        self,
        gcs_file_path: str,
    ) -> bool:
        return (
            await self.invoice_repo.exists_for_gcs_file_path(
                gcs_file_path,
            )
        )

    async def save_extracted_invoice(
        self,
        extraction: InvoiceExtractionSchema,
        gcs_file_path: str,
        received_email: str | None,
        *,
        message_id: str | None = None,
        subject: str | None = None,
        body_text: str | None = None,
        attachment_filename: str | None = None,
        confidence_records: list[
            ConfidenceRecordPayload
        ] | None = None,
        has_low_confidence: bool = False,
    ) -> Invoice | None:
        if await self.attachment_already_processed(
            gcs_file_path,
        ):
            print(
                "Invoice already exists for file: "
                f"{gcs_file_path}",
            )
            existing_invoice = (
                await self.invoice_repo.get_by_gcs_file_path(
                    gcs_file_path,
                )
            )

            if existing_invoice is not None:
                await self._save_invoice_email(
                    invoice_id=existing_invoice.id,
                    message_id=message_id,
                    received_email=received_email,
                    subject=subject,
                    body_text=body_text,
                    attachment_filename=attachment_filename,
                    gcs_file_path=gcs_file_path,
                )

            return existing_invoice

        payload = self._build_payload(
            extraction,
        )
        vendor_id = await self._resolve_vendor_id(
            payload.vendor_fields,
        )

        if not payload.header_fields.get(
            "currency",
        ):
            payload.header_fields[
                "currency"
            ] = "INR"

        if "discount_amount" not in payload.header_fields:
            payload.header_fields[
                "discount_amount"
            ] = Decimal(
                "0",
            )

        extraction_status = (
            ExtractionStatus.LOW_CONFIDENCE
            if has_low_confidence
            else ExtractionStatus.EXTRACTED
        )

        invoice = await self.invoice_repo.create(
            gcs_file_path=gcs_file_path,
            received_email=received_email,
            extraction_status=extraction_status,
            header_fields=payload.header_fields,
        )

        if vendor_id is not None:
            invoice.vendor_id = vendor_id

        if payload.vendor_fields:
            vendor = await self.invoice_extracted_vendor_repo.create(
                invoice_id=invoice.id,
                vendor_fields=payload.vendor_fields,
            )

            if vendor_id is not None:
                vendor.vendor_master_id = vendor_id

        for line_item_fields in payload.line_items:
            await self.invoice_line_item_repo.create(
                invoice_id=invoice.id,
                line_item_fields=line_item_fields,
            )

        await self._save_invoice_email(
            invoice_id=invoice.id,
            message_id=message_id,
            received_email=received_email,
            subject=subject,
            body_text=body_text,
            attachment_filename=attachment_filename,
            gcs_file_path=gcs_file_path,
        )

        if confidence_records:
            for record in confidence_records:
                await self.confidence_repo.create(
                    invoice_id=invoice.id,
                    record=record,
                )

        await self.invoice_repo.flush()

        print(
            f"Invoice saved: id={invoice.id}, "
            f"number={invoice.invoice_number}, "
            f"line_items={len(payload.line_items)}, "
            f"status={invoice.extraction_status.value}",
        )

        return invoice

    async def _save_invoice_email(
        self,
        *,
        invoice_id: UUID,
        message_id: str | None,
        received_email: str | None,
        subject: str | None,
        body_text: str | None,
        attachment_filename: str | None,
        gcs_file_path: str,
    ) -> None:
        if message_id is None:
            return

        if await self.invoice_email_repo.exists_for_invoice_id(
            invoice_id,
        ):
            return

        email_message_id = self._build_email_message_id(
            message_id=message_id,
            attachment_filename=attachment_filename,
        )

        if await self.invoice_email_repo.exists_for_message_id(
            email_message_id,
        ):
            return

        await self.invoice_email_repo.create(
            invoice_id=invoice_id,
            message_id=email_message_id,
            received_from=self._normalize_received_from(
                received_email,
            ),
            subject=subject,
            body_text=body_text,
            attachment_filename=attachment_filename,
            gcs_attachment_path=gcs_file_path,
        )

        print(
            "Invoice email saved: "
            f"invoice_id={invoice_id}, "
            f"message_id={email_message_id}",
        )

    async def _resolve_vendor_id(
        self,
        vendor_fields: dict[str, Any],
    ):
        lookup_fields = [
            (
                VendorMaster.gstin,
                vendor_fields.get("vendor_gstin"),
            ),
            (
                VendorMaster.vendor_name,
                vendor_fields.get("vendor_name"),
            ),
            (
                VendorMaster.email,
                vendor_fields.get("vendor_email"),
            ),
            (
                VendorMaster.phone,
                vendor_fields.get("vendor_phone"),
            ),
            (
                VendorMaster.account_number,
                vendor_fields.get("bank_account_number"),
            ),
            (
                VendorMaster.ifsc_code,
                vendor_fields.get("ifsc_code"),
            ),
            (
                VendorMaster.account_holder_name,
                vendor_fields.get("account_holder_name"),
            ),
            (
                VendorMaster.bank_name,
                vendor_fields.get("bank_name"),
            ),
        ]

        for column, value in lookup_fields:
            if not value:
                continue

            result = await self.invoice_repo.execute(
                select(VendorMaster.id).where(
                    column == value,
                ).limit(2),
            )
            ids = list(result.scalars().all())

            if len(ids) == 1:
                return ids[0]

        return None

    def _build_payload(
        self,
        extraction: InvoiceExtractionSchema,
    ) -> ExtractedInvoicePayload:
        header_fields: dict[str, Any] = {}

        for field_name in INVOICE_HEADER_FIELDS:
            value = getattr(
                extraction,
                field_name,
            )

            if value is not None:
                header_fields[field_name] = value

        vendor_fields: dict[str, Any] = {}

        if extraction.vendor is not None:
            for field_name in INVOICE_VENDOR_FIELDS:
                value = getattr(
                    extraction.vendor,
                    field_name,
                )

                if value is not None:
                    vendor_fields[field_name] = value

        line_items: list[dict[str, Any]] = []

        for index, line_item in enumerate(
            extraction.line_items,
        ):
            line_values = self._build_line_item_values(
                line_item,
                index=index,
            )

            if line_values is not None:
                line_items.append(
                    line_values,
                )

        return ExtractedInvoicePayload(
            header_fields=header_fields,
            vendor_fields=vendor_fields,
            line_items=line_items,
        )

    def _build_line_item_values(
        self,
        line_item: InvoiceLineItemExtractionSchema,
        *,
        index: int,
    ) -> dict[str, Any] | None:
        line_number = (
            line_item.line_number
            if line_item.line_number is not None
            else index + 1
        )
        quantity = line_item.quantity_billed
        unit_price = line_item.unit_price
        line_total = line_item.line_total
        tax_details = normalize_tax_details(
            line_item.tax_details,
        )

        has_content = any(
            [
                line_item.item_description,
                line_item.item_code,
                quantity is not None,
                unit_price is not None,
                line_total is not None,
            ],
        )

        if not has_content:
            return None

        if (
            line_total is None
            and quantity is not None
            and unit_price is not None
        ):
            line_total = (
                Decimal(
                    str(quantity),
                )
                * Decimal(
                    str(unit_price),
                )
            )

        if (
            quantity is None
            and line_total is not None
            and unit_price is not None
            and unit_price != 0
        ):
            quantity = (
                Decimal(
                    str(line_total),
                )
                / Decimal(
                    str(unit_price),
                )
            )

        if (
            unit_price is None
            and line_total is not None
            and quantity is not None
            and quantity != 0
        ):
            unit_price = (
                Decimal(
                    str(line_total),
                )
                / Decimal(
                    str(quantity),
                )
            )

        if quantity is None:
            quantity = Decimal(
                "1",
            )

        if (
            unit_price is None
            and line_total is not None
        ):
            unit_price = (
                Decimal(
                    str(line_total),
                )
                / quantity
            )

        if (
            line_total is None
            and unit_price is not None
        ):
            line_total = (
                quantity
                * unit_price
            )

        if (
            line_total is None
            or unit_price is None
        ):
            return None

        line_values: dict[str, Any] = {
            "line_number": line_number,
            "quantity_billed": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        }

        for field_name in INVOICE_LINE_ITEM_FIELDS:
            if field_name in line_values:
                continue

            value = getattr(
                line_item,
                field_name,
            )

            if value is not None:
                if field_name == "tax_details":
                    line_values[
                        field_name
                    ] = tax_details
                else:
                    line_values[
                        field_name
                    ] = value

        if "discount_amount" not in line_values:
            line_values[
                "discount_amount"
            ] = Decimal(
                "0",
            )

        return line_values

    @staticmethod
    def _build_email_message_id(
        message_id: str,
        attachment_filename: str | None,
    ) -> str:
        if attachment_filename:
            composite = (
                f"{message_id}::{attachment_filename}"
            )
            return composite[:500]

        return message_id[:500]

    @staticmethod
    def _normalize_received_from(
        received_email: str | None,
    ) -> str:
        if received_email and received_email.strip():
            return received_email.strip()[:255]

        return "unknown@unknown"

