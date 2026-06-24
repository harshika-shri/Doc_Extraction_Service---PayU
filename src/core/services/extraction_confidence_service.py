import json
from decimal import Decimal
from typing import Any

from src.config.llm_config import (
    GROQ_MODEL_CONFIDENCE,
    LOW_CONFIDENCE_THRESHOLD,
)
from src.constants.llm_prompt_constants import (
    CONFIDENCE_SCORE_PROMPT,
)
from src.schemas.extraction_confidence_schema import (
    ExtractionConfidenceResponse,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
)
from src.utils.llm_response_utils import (
    call_groq_llm,
    parse_llm_model,
)


class ExtractionConfidenceService:
    def score_invoice_extraction(
        self,
        extraction: InvoiceExtractionSchema,
    ) -> tuple[
        list[ConfidenceRecordPayload],
        bool,
    ]:
        field_values = (
            self._build_invoice_field_summary(
                extraction,
            )
        )

        if not field_values:
            return [], False

        prompt = (
            f"{CONFIDENCE_SCORE_PROMPT}\n"
            f"{json.dumps(field_values, default=str)}"
        )

        response_text = call_groq_llm(
            prompt,
            model=GROQ_MODEL_CONFIDENCE,
            max_tokens=1024,
        )
        confidence_response = parse_llm_model(
            response_text,
            ExtractionConfidenceResponse,
        )

        records: list[
            ConfidenceRecordPayload
        ] = []
        has_low_confidence = False

        for item in confidence_response.field_scores:
            is_flagged = (
                item.confidence
                < LOW_CONFIDENCE_THRESHOLD
            )

            if is_flagged:
                has_low_confidence = True

            records.append(
                ConfidenceRecordPayload(
                    field_name=item.field_name,
                    extracted_value=self._stringify_value(
                        field_values.get(
                            item.field_name,
                        ),
                    ),
                    confidence_score=Decimal(
                        str(
                            round(
                                item.confidence,
                                2,
                            ),
                        ),
                    ),
                    is_flagged=is_flagged,
                ),
            )

        print("\n" + "=" * 80)
        print("EXTRACTION CONFIDENCE SCORING")
        print("=" * 80)
        print(
            f"Fields scored: {len(records)}, "
            f"low_confidence={has_low_confidence}",
        )

        return records, has_low_confidence

    @staticmethod
    def _build_invoice_field_summary(
        extraction: InvoiceExtractionSchema,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {}

        header_fields = {
            "invoice_number": extraction.invoice_number,
            "invoice_date": extraction.invoice_date,
            "total_amount": extraction.total_amount,
            "tax_amount": extraction.tax_amount,
            "subtotal_amount": extraction.subtotal_amount,
            "company_name": extraction.company_name,
            "company_gstin": extraction.company_gstin,
            "currency": extraction.currency,
        }

        for field_name, value in header_fields.items():
            if value is not None:
                summary[
                    field_name
                ] = value

        if extraction.vendor is not None:
            vendor_fields = {
                "vendor.vendor_name": extraction.vendor.vendor_name,
                "vendor.vendor_gstin": extraction.vendor.vendor_gstin,
                "vendor.vendor_email": extraction.vendor.vendor_email,
            }

            for field_name, value in vendor_fields.items():
                if value is not None:
                    summary[
                        field_name
                    ] = value

        if extraction.line_items:
            summary[
                "line_items.count"
            ] = len(
                extraction.line_items,
            )
            first_item = extraction.line_items[0]
            summary[
                "line_items.first_description"
            ] = first_item.item_description
            summary[
                "line_items.first_total"
            ] = first_item.line_total

        return summary

    @staticmethod
    def _stringify_value(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        return str(value)
