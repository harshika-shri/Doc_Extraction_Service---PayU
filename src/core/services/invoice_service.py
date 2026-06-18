from decimal import Decimal
from typing import Any

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
    ExtractedInvoicePayload,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
    InvoiceLineItemExtractionSchema,
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
    ) -> Invoice | None:
        if await self.attachment_already_processed(
            gcs_file_path,
        ):
            print(
                "Invoice already exists for file: "
                f"{gcs_file_path}",
            )
            return None

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

        invoice = await self.invoice_repo.create(
            gcs_file_path=gcs_file_path,
            received_email=received_email,
            extraction_status=ExtractionStatus.EXTRACTED,
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

        await self.invoice_repo.flush()

        print(
            f"Invoice saved: id={invoice.id}, "
            f"number={invoice.invoice_number}, "
            f"line_items={len(payload.line_items)}, "
            f"status={invoice.extraction_status.value}",
        )

        return invoice

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
        tax_details = self._normalize_tax_details(
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
    def _normalize_tax_details(
        tax_details: Any,
    ) -> dict[str, Any] | None:
        if tax_details is None:
            return None

        if isinstance(
            tax_details,
            dict,
        ):
            return tax_details

        if isinstance(
            tax_details,
            list,
        ):
            normalized: dict[str, Any] = {}

            for index, item in enumerate(
                tax_details,
            ):
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                tax_name = item.get(
                    "tax_name",
                ) or item.get(
                    "name",
                )
                tax_value = item.get(
                    "tax_value",
                ) or item.get(
                    "value",
                )

                if tax_name is not None:
                    normalized[
                        str(tax_name)
                    ] = tax_value

                elif tax_value is not None:
                    normalized[
                        f"tax_{index + 1}"
                    ] = tax_value

            return normalized or None

        return {
            "value": tax_details,
        }
