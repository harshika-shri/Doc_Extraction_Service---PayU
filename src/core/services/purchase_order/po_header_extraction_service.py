from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.constants.prompts.po_header_prompt import (
    PO_HEADER_PROMPT,
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
class POHeaderExtractionResult:
    po_number: str | None
    po_date: Any
    subtotal_amount: Any
    tax_amount: Any
    total_amount: Any
    confidence_records: list[ConfidenceRecordPayload]


class POHeaderExtractionService(
    BaseVisionExtractionService,
):
    def extract(
        self,
        file_path: Path,
    ) -> POHeaderExtractionResult:
        payload = self._extract_payload(
            file_path,
            PO_HEADER_PROMPT,
            max_tokens=512,
        )
        fields = self._parse_fields(
            payload,
        )

        return POHeaderExtractionResult(
            po_number=fields[
                "po_number"
            ].value,
            po_date=fields[
                "po_date"
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
                    "po_number": fields[
                        "po_number"
                    ],
                    "po_date": fields[
                        "po_date"
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
            "po_number": parse_string_field(
                payload.get(
                    "po_number",
                ),
            ),
            "po_date": parse_date_field(
                payload.get(
                    "po_date",
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
