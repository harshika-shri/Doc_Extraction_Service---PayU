from __future__ import annotations

from typing import Any

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
from src.core.services.purchase_order.po_extraction_orchestrator import (
    POExtractionResult,
)
from src.schemas.po_extraction_schema import (
    POExtractionSchema,
    POVendorExtractionSchema,
)
from src.utils.extraction_field_utils import (
    collect_confidence_records,
)


def build_po_extraction_result(
    payload: dict[str, Any],
) -> POExtractionResult:
    header_fields = (
        POHeaderExtractionService._parse_fields(
            payload,
        )
    )
    company_fields = (
        POCompanyExtractionService._parse_fields(
            payload,
        )
    )
    vendor_fields = (
        POVendorExtractionService._parse_fields(
            payload,
        )
    )
    line_item_service = (
        POLineItemExtractionService()
    )
    line_items, line_confidence_records = (
        line_item_service._parse_line_items(
            payload.get(
                "line_items",
            ),
        )
    )

    vendor_values = {
        field_name: parsed_field.value
        for field_name, parsed_field in vendor_fields.items()
        if parsed_field.value is not None
    }
    vendor = (
        POVendorExtractionSchema(
            **vendor_values,
        )
        if vendor_values
        else None
    )
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
        po_number=header_fields[
            "po_number"
        ].value,
        po_date=header_fields[
            "po_date"
        ].value,
        subtotal_amount=header_fields[
            "subtotal_amount"
        ].value,
        tax_amount=header_fields[
            "tax_amount"
        ].value,
        total_amount=header_fields[
            "total_amount"
        ].value,
        company_name=company_fields[
            "buyer_company_name"
        ].value,
        company_gstin=company_fields[
            "buyer_company_gstin"
        ].value,
        vendor_name=vendor_name,
        vendor_gstin=vendor_gstin,
        vendor=vendor,
        line_items=line_items,
    )

    confidence_records = [
        *collect_confidence_records(
            {
                "po_number": header_fields[
                    "po_number"
                ],
                "po_date": header_fields[
                    "po_date"
                ],
                "subtotal_amount": header_fields[
                    "subtotal_amount"
                ],
                "tax_amount": header_fields[
                    "tax_amount"
                ],
                "total_amount": header_fields[
                    "total_amount"
                ],
            },
        ),
        *collect_confidence_records(
            {
                "company_name": company_fields[
                    "buyer_company_name"
                ],
                "company_gstin": company_fields[
                    "buyer_company_gstin"
                ],
            },
        ),
        *collect_confidence_records(
            {
                f"vendor.{field_name}": parsed_field
                for field_name, parsed_field in vendor_fields.items()
            },
        ),
        *line_confidence_records,
    ]

    return POExtractionResult(
        extraction=extraction,
        confidence_records=confidence_records,
    )
