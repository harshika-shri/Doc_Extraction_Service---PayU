from decimal import Decimal
from typing import Any

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
from src.data.repositories.invoice_validation_issue_repo import (
    InvoiceValidationIssueRepository,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
    ExtractedInvoicePayload,
    ValidationIssuePayload,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
    InvoiceLineItemExtractionSchema,
)
from src.schemas.invoice_schema import (
    InvoiceProcessingItem,
    InvoiceProcessingListResponse,
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
        self.extraction_field_confidence_repo = (
            ExtractionFieldConfidenceRepository(
                session,
            )
        )
        self.invoice_validation_issue_repo = (
            InvoiceValidationIssueRepository(
                session,
            )
        )

    async def attachment_already_processed(
        self,
        gcs_file_path: str,
    ) -> bool:
        return await self.invoice_repo.exists_for_gcs_file_path(
            gcs_file_path,
        )

    async def message_already_processed(
        self,
        gmail_message_id: str,
    ) -> bool:
        return await self.invoice_repo.exists_for_gmail_message_id(
            gmail_message_id,
        )

    async def save_extracted_invoice(
        self,
        extraction: InvoiceExtractionSchema,
        gcs_file_path: str,
        received_email: str | None,
        message_id: str,
        subject: str | None,
        body_text: str | None,
        attachment_filename: str | None,
        confidence_records: list[ConfidenceRecordPayload],
        has_low_confidence: bool,
    ) -> Invoice:
        if await self.attachment_already_processed(
            gcs_file_path,
        ):
            existing = (
                await self.invoice_repo.get_by_gcs_file_path(
                    gcs_file_path,
                )
            )
            if existing is not None:
                return existing

        payload = self._build_payload(
            extraction,
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

        if payload.vendor_fields:
            await self.invoice_extracted_vendor_repo.create(
                invoice_id=invoice.id,
                vendor_fields=payload.vendor_fields,
            )

        for line_item_fields in payload.line_items:
            await self.invoice_line_item_repo.create(
                invoice_id=invoice.id,
                line_item_fields=line_item_fields,
            )

        for record in confidence_records:
            await self.extraction_field_confidence_repo.create(
                invoice_id=invoice.id,
                record=record,
            )

            if record.is_flagged:
                await self.invoice_validation_issue_repo.create(
                    invoice_id=invoice.id,
                    issue=ValidationIssuePayload(
                        check_name="low_confidence",
                        field_name=record.field_name,
                        description=(
                            "Low confidence extraction for "
                            f"{record.field_name}."
                        ),
                        actual_value=record.extracted_value,
                    ),
                )

        email_message_id = self._build_email_message_id(
            message_id=message_id,
            attachment_filename=attachment_filename,
        )

        if received_email is not None:
            await self.invoice_email_repo.create(
                invoice_id=invoice.id,
                message_id=email_message_id,
                received_from=received_email,
                subject=subject,
                body_text=body_text,
                attachment_filename=attachment_filename,
                gcs_attachment_path=gcs_file_path,
            )

        await self.invoice_repo.flush()

        print(
            f"Invoice saved: id={invoice.id}, "
            f"number={invoice.invoice_number}, "
            f"line_items={len(payload.line_items)}, "
            f"status={invoice.extraction_status.value}",
        )

        return invoice

    async def list_processing_invoices(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> InvoiceProcessingListResponse:
        invoices, total = (
            await self.invoice_repo.list_processing(
                limit=limit,
                offset=offset,
            )
        )

        items = [
            InvoiceProcessingItem(
                id=invoice.id,
                invoice_number=invoice.invoice_number,
                invoice_date=invoice.invoice_date,
                received_email=invoice.received_email,
                extraction_status=invoice.extraction_status.value
                if hasattr(
                    invoice.extraction_status,
                    "value",
                )
                else str(
                    invoice.extraction_status,
                ),
                invoice_status=invoice.invoice_status.value
                if invoice.invoice_status
                is not None
                and hasattr(
                    invoice.invoice_status,
                    "value",
                )
                else (
                    str(
                        invoice.invoice_status,
                    )
                    if invoice.invoice_status
                    is not None
                    else None
                ),
                total_amount=float(
                    invoice.total_amount,
                )
                if invoice.total_amount
                is not None
                else None,
                currency=invoice.currency,
                created_at=invoice.created_at,
            )
            for invoice in invoices
        ]

        return InvoiceProcessingListResponse(
            items=items,
            total=total,
        )

    def _build_email_message_id(
        self,
        *,
        message_id: str,
        attachment_filename: str | None,
    ) -> str:
        if attachment_filename:
            return (
                f"{message_id}::{attachment_filename}"
            )

        return message_id

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
