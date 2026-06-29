from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.constants.prompts.invoice_header_prompt import (
    INVOICE_HEADER_PROMPT,
)
from src.core.services.base_vision_extraction_service import (
    BaseVisionExtractionService,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.utils.extraction_field_utils import (
    ParsedField,
    collect_confidence_records,
    parse_date_field,
    parse_decimal_field,
    parse_string_field,
)


@dataclass(frozen=True, slots=True)
class InvoiceHeaderExtractionResult:
    invoice_number: str | None
    invoice_date: Any
    due_date: Any
    po_number: str | None
    subtotal_amount: Any
    tax_amount: Any
    total_amount: Any
    confidence_records: list[ConfidenceRecordPayload]


class InvoiceHeaderExtractionService(
    BaseVisionExtractionService,
):
    def extract(
        self,
        file_path: Path,
    ) -> InvoiceHeaderExtractionResult:
        payload = self._extract_payload(
            file_path,
            INVOICE_HEADER_PROMPT,
            max_tokens=512,
        )
        fields = self._parse_fields(
            payload,
        )

        return InvoiceHeaderExtractionResult(
            invoice_number=fields[
                "invoice_number"
            ].value,
            invoice_date=fields[
                "invoice_date"
            ].value,
            due_date=fields[
                "due_date"
            ].value,
            po_number=fields[
                "po_number"
            ].value,
            subtotal_amount=fields[
                "subtotal_amount"
            ].value,
            tax_amount=fields[
                "tax_amount"
            ].value,
            total_amount=fields[
                "total_amount"
            ].value,
            confidence_records=collect_confidence_records(
                {
                    "invoice_number": fields[
                        "invoice_number"
                    ],
                    "invoice_date": fields[
                        "invoice_date"
                    ],
                    "due_date": fields[
                        "due_date"
                    ],
                    "po_number": fields[
                        "po_number"
                    ],
                    "subtotal_amount": fields[
                        "subtotal_amount"
                    ],
                    "tax_amount": fields[
                        "tax_amount"
                    ],
                    "total_amount": fields[
                        "total_amount"
                    ],
                },
            ),
        )

    @staticmethod
    def _parse_fields(
        payload: dict[str, Any],
    ) -> dict[str, ParsedField]:
        return {
            "invoice_number": parse_string_field(
                payload.get(
                    "invoice_number",
                ),
            ),
            "invoice_date": parse_date_field(
                payload.get(
                    "invoice_date",
                ),
            ),
            "due_date": parse_date_field(
                payload.get(
                    "due_date",
                ),
            ),
            "po_number": parse_string_field(
                payload.get(
                    "po_number",
                ),
            ),
            "subtotal_amount": parse_decimal_field(
                payload.get(
                    "subtotal_amount",
                ),
            ),
            "tax_amount": parse_decimal_field(
                payload.get(
                    "tax_amount",
                ),
            ),
            "total_amount": parse_decimal_field(
                payload.get(
                    "total_amount",
                ),
            ),
        }
