from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from src.config.llm_config import (
    LOW_CONFIDENCE_THRESHOLD,
)
from src.schemas.extraction_persistence_schema import (
    ConfidenceRecordPayload,
)
from src.utils.llama_document_parser import (
    _parse_date,
    _parse_decimal,
)


@dataclass(frozen=True, slots=True)
class ParsedField:
    value: Any
    confidence: float | None


def normalize_confidence_score(
    confidence: float | None,
) -> Decimal | None:
    if confidence is None:
        return None

    score = float(
        confidence,
    )

    if score <= 1:
        score *= 100

    return Decimal(
        str(
            round(
                score,
                2,
            ),
        ),
    )


def parse_confident_field(
    payload: Any,
    *,
    parser: Any | None = None,
) -> ParsedField:
    if payload is None:
        return ParsedField(
            value=None,
            confidence=None,
        )

    if isinstance(
        payload,
        dict,
    ) and "value" in payload:
        raw_value = payload.get(
            "value",
        )
        confidence = payload.get(
            "confidence",
        )

        if raw_value is None:
            return ParsedField(
                value=None,
                confidence=None,
            )

        parsed_value = (
            parser(
                raw_value,
            )
            if parser is not None
            else raw_value
        )

        return ParsedField(
            value=parsed_value,
            confidence=(
                float(
                    confidence,
                )
                if confidence is not None
                else None
            ),
        )

    if parser is not None:
        return ParsedField(
            value=parser(
                payload,
            ),
            confidence=None,
        )

    return ParsedField(
        value=payload,
        confidence=None,
    )


def identify_review_fields(
    confidence_records: list[ConfidenceRecordPayload],
) -> tuple[
    list[ConfidenceRecordPayload],
    bool,
]:
    reviewed_records: list[
        ConfidenceRecordPayload
    ] = []
    has_low_confidence = False
    threshold = Decimal(
        str(
            LOW_CONFIDENCE_THRESHOLD,
        ),
    )

    for record in confidence_records:
        is_flagged = (
            record.confidence_score
            < threshold
        )

        if is_flagged:
            has_low_confidence = True

        reviewed_records.append(
            ConfidenceRecordPayload(
                field_name=record.field_name,
                extracted_value=record.extracted_value,
                confidence_score=record.confidence_score,
                is_flagged=is_flagged,
            ),
        )

    return reviewed_records, has_low_confidence


def build_confidence_record(
    field_name: str,
    value: Any,
    confidence: float | None,
) -> ConfidenceRecordPayload | None:
    normalized_confidence = normalize_confidence_score(
        confidence,
    )

    if normalized_confidence is None:
        return None

    return ConfidenceRecordPayload(
        field_name=field_name,
        extracted_value=_stringify_value(
            value,
        ),
        confidence_score=normalized_confidence,
        is_flagged=False,
    )


def collect_confidence_records(
    field_map: dict[str, ParsedField],
) -> list[ConfidenceRecordPayload]:
    records: list[ConfidenceRecordPayload] = []

    for field_name, parsed_field in field_map.items():
        if parsed_field.value is None:
            continue

        record = build_confidence_record(
            field_name=field_name,
            value=parsed_field.value,
            confidence=parsed_field.confidence,
        )

        if record is not None:
            records.append(
                record,
            )

    return records


def parse_decimal_field(
    payload: Any,
) -> ParsedField:
    parsed = parse_confident_field(
        payload,
        parser=_parse_decimal,
    )

    return parsed


def parse_date_field(
    payload: Any,
) -> ParsedField:
    return parse_confident_field(
        payload,
        parser=_parse_date,
    )


def parse_string_field(
    payload: Any,
) -> ParsedField:
    parsed = parse_confident_field(
        payload,
    )

    if parsed.value is None:
        return parsed

    text = str(
        parsed.value,
    ).strip()

    return ParsedField(
        value=text or None,
        confidence=parsed.confidence,
    )


def _stringify_value(
    value: Any,
) -> str | None:
    if value is None:
        return None

    return str(
        value,
    )
