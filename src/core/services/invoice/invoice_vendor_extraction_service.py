from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.constants.prompts.invoice_vendor_prompt import (
    INVOICE_VENDOR_PROMPT,
)
from src.core.services.base_vision_extraction_service import (
    BaseVisionExtractionService,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceVendorExtractionSchema,
)
from src.utils.extraction_field_utils import (
    ParsedField,
    collect_confidence_records,
    parse_string_field,
)


@dataclass(frozen=True, slots=True)
class InvoiceVendorExtractionResult:
    vendor: InvoiceVendorExtractionSchema | None
    confidence_records: list[ConfidenceRecordPayload]


class InvoiceVendorExtractionService(
    BaseVisionExtractionService,
):
    def extract(
        self,
        file_path: Path,
    ) -> InvoiceVendorExtractionResult:
        payload = self._extract_payload(
            file_path,
            INVOICE_VENDOR_PROMPT,
            max_tokens=768,
        )
        fields = self._parse_fields(
            payload,
        )
        vendor_values = {
            field_name: parsed_field.value
            for field_name, parsed_field in fields.items()
            if parsed_field.value is not None
        }

        vendor = (
            InvoiceVendorExtractionSchema(
                **vendor_values,
            )
            if vendor_values
            else None
        )

        confidence_records = collect_confidence_records(
            {
                f"vendor.{field_name}": parsed_field
                for field_name, parsed_field in fields.items()
            },
        )

        return InvoiceVendorExtractionResult(
            vendor=vendor,
            confidence_records=confidence_records,
        )

    @staticmethod
    def _parse_fields(
        payload: dict[str, Any],
    ) -> dict[str, ParsedField]:
        return {
            field_name: parse_string_field(
                payload.get(
                    field_name,
                ),
            )
            for field_name in (
                "vendor_name",
                "vendor_gstin",
                "vendor_address",
                "vendor_email",
                "vendor_phone",
                "bank_account_number",
                "bank_name",
                "ifsc_code",
                "account_holder_name",
            )
        }
