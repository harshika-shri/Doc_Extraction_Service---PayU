from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.services.invoice.invoice_company_extraction_service import (
    InvoiceCompanyExtractionService,
)
from src.core.services.invoice.invoice_header_extraction_service import (
    InvoiceHeaderExtractionService,
)
from src.core.services.invoice.invoice_line_item_extraction_service import (
    InvoiceLineItemExtractionService,
)
from src.core.services.invoice.invoice_vendor_extraction_service import (
    InvoiceVendorExtractionService,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
)


@dataclass(frozen=True, slots=True)
class InvoiceExtractionResult:
    extraction: InvoiceExtractionSchema
    confidence_records: list[ConfidenceRecordPayload]


class InvoiceExtractionOrchestrator:
    def __init__(self) -> None:
        self.header_service = (
            InvoiceHeaderExtractionService()
        )
        self.company_service = (
            InvoiceCompanyExtractionService()
        )
        self.vendor_service = (
            InvoiceVendorExtractionService()
        )
        self.line_item_service = (
            InvoiceLineItemExtractionService()
        )

    def extract(
        self,
        file_path: Path,
    ) -> InvoiceExtractionResult:
        header = self.header_service.extract(
            file_path,
        )
        company = self.company_service.extract(
            file_path,
        )
        vendor = self.vendor_service.extract(
            file_path,
        )
        line_items = self.line_item_service.extract(
            file_path,
        )

        po_numbers_extracted = (
            [header.po_number]
            if header.po_number
            else None
        )

        extraction = InvoiceExtractionSchema(
            invoice_number=header.invoice_number,
            invoice_date=header.invoice_date,
            due_date=header.due_date,
            po_numbers_extracted=po_numbers_extracted,
            subtotal_amount=header.subtotal_amount,
            tax_amount=header.tax_amount,
            total_amount=header.total_amount,
            company_name=company.company_name,
            company_gstin=company.company_gstin,
            company_address=company.company_address,
            vendor=vendor.vendor,
            line_items=line_items.line_items,
        )

        confidence_records = [
            *header.confidence_records,
            *company.confidence_records,
            *vendor.confidence_records,
            *line_items.confidence_records,
        ]

        print("\n" + "=" * 80)
        print("INVOICE STRUCTURED EXTRACTION")
        print("=" * 80)
        print(
            extraction.model_dump_json(
                indent=2,
            ),
        )

        return InvoiceExtractionResult(
            extraction=extraction,
            confidence_records=confidence_records,
        )
