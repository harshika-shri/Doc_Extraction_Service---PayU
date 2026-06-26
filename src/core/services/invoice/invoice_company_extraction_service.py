from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.constants.prompts.invoice_company_prompt import (
    INVOICE_COMPANY_PROMPT,
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
    parse_string_field,
)


@dataclass(frozen=True, slots=True)
class InvoiceCompanyExtractionResult:
    company_name: str | None
    company_gstin: str | None
    company_address: str | None
    confidence_records: list[ConfidenceRecordPayload]


class InvoiceCompanyExtractionService(
    BaseVisionExtractionService,
):
    def extract(
        self,
        file_path: Path,
    ) -> InvoiceCompanyExtractionResult:
        payload = self._extract_payload(
            file_path,
            INVOICE_COMPANY_PROMPT,
            max_tokens=256,
        )
        fields = self._parse_fields(
            payload,
        )

        return InvoiceCompanyExtractionResult(
            company_name=fields[
                "buyer_company_name"
            ].value,
            company_gstin=fields[
                "buyer_company_gstin"
            ].value,
            company_address=fields[
                "buyer_company_address"
            ].value,
            confidence_records=collect_confidence_records(
                {
                    "company_name": fields[
                        "buyer_company_name"
                    ],
                    "company_gstin": fields[
                        "buyer_company_gstin"
                    ],
                    "company_address": fields[
                        "buyer_company_address"
                    ],
                },
            ),
        )

    @staticmethod
    def _parse_fields(
        payload: dict[str, Any],
    ) -> dict[str, ParsedField]:
        return {
            "buyer_company_name": parse_string_field(
                payload.get(
                    "buyer_company_name",
                ),
            ),
            "buyer_company_gstin": parse_string_field(
                payload.get(
                    "buyer_company_gstin",
                ),
            ),
            "buyer_company_address": parse_string_field(
                payload.get(
                    "buyer_company_address",
                ),
            ),
        }
