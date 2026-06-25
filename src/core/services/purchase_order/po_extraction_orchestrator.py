from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.services.purchase_order.po_company_extraction_service import (
    POCompanyExtractionService,
)
from src.core.services.purchase_order.po_header_extraction_service import (
    POHeaderExtractionService,
)
from src.core.services.purchase_order.po_line_item_extraction_service import (
    POLineItemExtractionService,
)
from src.core.services.purchase_order.po_vendor_extraction_service import (
    POVendorExtractionService,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.schemas.po_extraction_schema import (
    POExtractionSchema,
)


@dataclass(frozen=True, slots=True)
class POExtractionResult:
    extraction: POExtractionSchema
    confidence_records: list[ConfidenceRecordPayload]


class POExtractionOrchestrator:
    def __init__(self) -> None:
        self.header_service = (
            POHeaderExtractionService()
        )
        self.company_service = (
            POCompanyExtractionService()
        )
        self.vendor_service = (
            POVendorExtractionService()
        )
        self.line_item_service = (
            POLineItemExtractionService()
        )

    def extract(
        self,
        file_path: Path,
    ) -> POExtractionResult:
        header = self.header_service.extract(
            file_path,
        )
        company = self.company_service.extract(
            file_path,
        )
        vendor_result = self.vendor_service.extract(
            file_path,
        )
        line_items = self.line_item_service.extract(
            file_path,
        )

        vendor = vendor_result.vendor
        vendor_name = (
            vendor.vendor_name
            if vendor is not None
            else None
        )
        vendor_gstin = (
            vendor.vendor_gstin
            if vendor is not None
            else None
        )

        extraction = POExtractionSchema(
            po_number=header.po_number,
            po_date=header.po_date,
            subtotal_amount=header.subtotal_amount,
            tax_amount=header.tax_amount,
            total_amount=header.total_amount,
            company_name=company.company_name,
            company_gstin=company.company_gstin,
            vendor_name=vendor_name,
            vendor_gstin=vendor_gstin,
            vendor=vendor,
            line_items=line_items.line_items,
        )

        confidence_records = [
            *header.confidence_records,
            *company.confidence_records,
            *vendor_result.confidence_records,
            *line_items.confidence_records,
        ]

        print("\n" + "=" * 80)
        print("PURCHASE ORDER STRUCTURED EXTRACTION")
        print("=" * 80)
        print(
            extraction.model_dump_json(
                indent=2,
            ),
        )

        return POExtractionResult(
            extraction=extraction,
            confidence_records=confidence_records,
        )
