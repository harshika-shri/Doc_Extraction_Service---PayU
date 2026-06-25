from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.constants.prompts.po_vendor_prompt import (
    PO_VENDOR_PROMPT,
)
from src.core.services.base_vision_extraction_service import (
    BaseVisionExtractionService,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.schemas.po_extraction_schema import (
    POVendorExtractionSchema,
)
from src.utils.extraction_field_utils import (
    ParsedField,
    collect_confidence_records,
    parse_string_field,
)


@dataclass(frozen=True, slots=True)
class POVendorExtractionResult:
    vendor: POVendorExtractionSchema | None
    confidence_records: list[ConfidenceRecordPayload]


class POVendorExtractionService(
    BaseVisionExtractionService,
):
    def extract(
        self,
        file_path: Path,
    ) -> POVendorExtractionResult:
        payload = self._extract_payload(
            file_path,
            PO_VENDOR_PROMPT,
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
            POVendorExtractionSchema(
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

        return POVendorExtractionResult(
            vendor=vendor,
            confidence_records=confidence_records,
        )

    @staticmethod
    def _parse_fields(
        payload: dict[str, Any],
    ) -> dict[str, ParsedField]:
        raw_fields = {
            "vendor_code": parse_string_field(
                payload.get(
                    "vendor_code",
                ),
            ),
            "vendor_name": parse_string_field(
                payload.get(
                    "vendor_name",
                ),
            ),
            "vendor_gstin": parse_string_field(
                payload.get(
                    "vendor_gstin",
                ),
            ),
            "pan_number": parse_string_field(
                payload.get(
                    "pan_number",
                ),
            ),
            "email": parse_string_field(
                payload.get(
                    "vendor_email",
                ),
            ),
            "phone": parse_string_field(
                payload.get(
                    "vendor_phone",
                ),
            ),
            "address_line_1": parse_string_field(
                payload.get(
                    "address_line_1",
                ),
            ),
            "address_line_2": parse_string_field(
                payload.get(
                    "address_line_2",
                ),
            ),
            "city": parse_string_field(
                payload.get(
                    "city",
                ),
            ),
            "state": parse_string_field(
                payload.get(
                    "state",
                ),
            ),
            "bank_name": parse_string_field(
                payload.get(
                    "bank_name",
                ),
            ),
            "account_number": parse_string_field(
                payload.get(
                    "bank_account_number",
                ),
            ),
            "ifsc_code": parse_string_field(
                payload.get(
                    "ifsc_code",
                ),
            ),
            "account_holder_name": parse_string_field(
                payload.get(
                    "account_holder_name",
                ),
            ),
        }

        return raw_fields
