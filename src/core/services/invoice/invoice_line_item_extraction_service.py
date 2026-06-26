from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.constants.prompts.invoice_line_item_prompt import (
    INVOICE_LINE_ITEM_PROMPT,
)
from src.core.services.base_vision_extraction_service import (
    BaseVisionExtractionService,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceLineItemExtractionSchema,
)
from src.utils.extraction_field_utils import (
    ParsedField,
    build_confidence_record,
    parse_confident_field,
    parse_decimal_field,
    parse_string_field,
)
from src.utils.tax_details_utils import (
    normalize_tax_details,
)


@dataclass(frozen=True, slots=True)
class InvoiceLineItemExtractionResult:
    line_items: list[InvoiceLineItemExtractionSchema]
    confidence_records: list[ConfidenceRecordPayload]


class InvoiceLineItemExtractionService(
    BaseVisionExtractionService,
):
    def extract(
        self,
        file_path: Path,
    ) -> InvoiceLineItemExtractionResult:
        payload = self._extract_payload(
            file_path,
            INVOICE_LINE_ITEM_PROMPT,
            max_tokens=1500,
        )
        line_items, confidence_records = (
            self._parse_line_items(
                payload.get(
                    "line_items",
                ),
            )
        )

        return InvoiceLineItemExtractionResult(
            line_items=line_items,
            confidence_records=confidence_records,
        )

    def _parse_line_items(
        self,
        raw_line_items: Any,
    ) -> tuple[
        list[InvoiceLineItemExtractionSchema],
        list[ConfidenceRecordPayload],
    ]:
        if not isinstance(
            raw_line_items,
            list,
        ):
            return [], []

        line_items: list[
            InvoiceLineItemExtractionSchema
        ] = []
        confidence_records: list[
            ConfidenceRecordPayload
        ] = []

        for index, raw_item in enumerate(
            raw_line_items,
            start=1,
        ):
            if not isinstance(
                raw_item,
                dict,
            ):
                continue

            parsed_fields = self._parse_line_item_fields(
                raw_item,
            )
            values = {
                field_name: parsed_field.value
                for field_name, parsed_field in parsed_fields.items()
                if parsed_field.value is not None
            }

            if not values.get(
                "item_description",
            ) and not values.get(
                "line_total",
            ):
                continue

            if values.get(
                "line_number",
            ) is None:
                values[
                    "line_number"
                ] = index

            line_items.append(
                InvoiceLineItemExtractionSchema(
                    **values,
                ),
            )

            prefix = (
                f"line_items[{index}]"
            )

            for field_name, parsed_field in parsed_fields.items():
                if parsed_field.value is None:
                    continue

                record = build_confidence_record(
                    field_name=(
                        f"{prefix}.{field_name}"
                    ),
                    value=parsed_field.value,
                    confidence=parsed_field.confidence,
                )

                if record is not None:
                    confidence_records.append(
                        record,
                    )

        return line_items, confidence_records

    @staticmethod
    def _parse_line_item_fields(
        raw_item: dict[str, Any],
    ) -> dict[str, ParsedField]:
        tax_details = parse_confident_field(
            raw_item.get(
                "tax_details",
            ),
        )

        if tax_details.value is not None:
            tax_details = ParsedField(
                value=normalize_tax_details(
                    tax_details.value,
                ),
                confidence=tax_details.confidence,
            )

        line_number = parse_confident_field(
            raw_item.get(
                "line_number",
            ),
        )

        if line_number.value is not None:
            try:
                line_number = ParsedField(
                    value=int(
                        line_number.value,
                    ),
                    confidence=line_number.confidence,
                )
            except (
                TypeError,
                ValueError,
            ):
                line_number = ParsedField(
                    value=None,
                    confidence=None,
                )

        discount_amount = parse_decimal_field(
            raw_item.get(
                "discount_amount",
            ),
        )

        if (
            discount_amount.value is None
        ):
            discount_amount = ParsedField(
                value=Decimal(
                    "0",
                ),
                confidence=None,
            )

        return {
            "line_number": line_number,
            "item_code": parse_string_field(
                raw_item.get(
                    "item_code",
                ),
            ),
            "item_description": parse_string_field(
                raw_item.get(
                    "item_description",
                ),
            ),
            "uom": parse_string_field(
                raw_item.get(
                    "uom",
                ),
            ),
            "quantity_billed": parse_decimal_field(
                raw_item.get(
                    "quantity_billed",
                ),
            ),
            "unit_price": parse_decimal_field(
                raw_item.get(
                    "unit_price",
                ),
            ),
            "discount_amount": discount_amount,
            "hsn_sac_code": parse_string_field(
                raw_item.get(
                    "hsn_sac_code",
                ),
            ),
            "tax_details": tax_details,
            "line_total": parse_decimal_field(
                raw_item.get(
                    "line_total",
                ),
            ),
        }
