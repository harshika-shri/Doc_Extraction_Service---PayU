from __future__ import annotations

from typing import Any

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
from src.core.services.invoice.invoice_extraction_orchestrator import (
    InvoiceExtractionResult,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
    InvoiceVendorExtractionSchema,
)
from src.utils.extraction_field_utils import (
    collect_confidence_records,
)


def build_invoice_extraction_result(
    payload: dict[str, Any],
) -> InvoiceExtractionResult:
    header_fields = (
        InvoiceHeaderExtractionService._parse_fields(
            payload,
        )
    )
    company_fields = (
        InvoiceCompanyExtractionService._parse_fields(
            payload,
        )
    )
    vendor_result = (
        InvoiceVendorExtractionService._parse_fields(
            payload,
        )
    )
    line_item_service = (
        InvoiceLineItemExtractionService()
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
        for field_name, parsed_field in vendor_result.items()
        if parsed_field.value is not None
    }
    vendor = None

    if vendor_values:
        vendor = InvoiceVendorExtractionSchema(
            **vendor_values,
        )

    po_number = header_fields[
        "po_number"
    ].value
    po_numbers_extracted = (
        [po_number]
        if po_number
        else None
    )

    extraction = InvoiceExtractionSchema(
        invoice_number=header_fields[
            "invoice_number"
        ].value,
        invoice_date=header_fields[
            "invoice_date"
        ].value,
        due_date=header_fields[
            "due_date"
        ].value,
        po_numbers_extracted=po_numbers_extracted,
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
        company_address=company_fields[
            "buyer_company_address"
        ].value,
        vendor=vendor,
        line_items=line_items,
    )

    confidence_records = [
        *collect_confidence_records(
            {
                "invoice_number": header_fields[
                    "invoice_number"
                ],
                "invoice_date": header_fields[
                    "invoice_date"
                ],
                "due_date": header_fields[
                    "due_date"
                ],
                "po_number": header_fields[
                    "po_number"
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
                "company_address": company_fields[
                    "buyer_company_address"
                ],
            },
        ),
        *collect_confidence_records(
            {
                f"vendor.{field_name}": parsed_field
                for field_name, parsed_field in vendor_result.items()
            },
        ),
        *line_confidence_records,
    ]

    return InvoiceExtractionResult(
        extraction=extraction,
        confidence_records=confidence_records,
    )
