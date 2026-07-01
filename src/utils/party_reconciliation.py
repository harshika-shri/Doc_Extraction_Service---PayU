from __future__ import annotations

import re

from src.utils.extraction_field_utils import ParsedField


def _normalize_name(
    value: str | None,
) -> str:
    if not value:
        return ""

    collapsed = re.sub(
        r"\s+",
        " ",
        value.strip(),
    )

    return collapsed.casefold()


def _normalize_gstin(
    value: str | None,
) -> str:
    if not value:
        return ""

    return re.sub(
        r"\s+",
        "",
        value.strip(),
    ).upper()


def _names_match(
    left: str | None,
    right: str | None,
) -> bool:
    normalized_left = _normalize_name(
        left,
    )
    normalized_right = _normalize_name(
        right,
    )

    if not normalized_left or not normalized_right:
        return False

    if normalized_left == normalized_right:
        return True

    return (
        normalized_left in normalized_right
        or normalized_right in normalized_left
    )


def _gstins_match(
    left: str | None,
    right: str | None,
) -> bool:
    normalized_left = _normalize_gstin(
        left,
    )
    normalized_right = _normalize_gstin(
        right,
    )

    if not normalized_left or not normalized_right:
        return False

    return normalized_left == normalized_right


def _field_value(
    fields: dict[str, ParsedField],
    key: str,
) -> str | None:
    parsed = fields.get(
        key,
    )

    if parsed is None:
        return None

    value = parsed.value

    if value is None:
        return None

    text = str(
        value,
    ).strip()

    return text or None


def _set_field_value(
    fields: dict[str, ParsedField],
    key: str,
    value: str | None,
) -> None:
    existing = fields.get(
        key,
    )
    confidence = (
        existing.confidence
        if existing is not None
        else None
    )

    fields[key] = ParsedField(
        value=value,
        confidence=confidence,
    )


def _should_swap_parties(
    *,
    buyer_name: str | None,
    buyer_gstin: str | None,
    vendor_name: str | None,
    vendor_gstin: str | None,
) -> bool:
    if (
        buyer_gstin
        and vendor_gstin
        and _gstins_match(
            buyer_gstin,
            vendor_gstin,
        )
    ):
        return True

    if (
        buyer_name
        and vendor_name
        and _names_match(
            buyer_name,
            vendor_name,
        )
    ):
        return False

    if (
        vendor_name
        and buyer_name
        and _looks_like_bill_to_party(
            vendor_name,
        )
        and not _looks_like_bill_to_party(
            buyer_name,
        )
    ):
        return True

    return False


def _swap_invoice_party_fields(
    *,
    buyer_name: str | None,
    buyer_gstin: str | None,
    buyer_address: str | None,
    vendor_fields: dict[str, ParsedField],
) -> tuple[
    str | None,
    str | None,
    str | None,
    dict[str, ParsedField],
]:
    vendor_name = _field_value(
        vendor_fields,
        "vendor_name",
    )
    vendor_gstin = _field_value(
        vendor_fields,
        "vendor_gstin",
    )
    vendor_address = _field_value(
        vendor_fields,
        "vendor_address",
    )

    _set_field_value(
        vendor_fields,
        "vendor_name",
        buyer_name,
    )
    _set_field_value(
        vendor_fields,
        "vendor_gstin",
        buyer_gstin,
    )
    _set_field_value(
        vendor_fields,
        "vendor_address",
        buyer_address,
    )

    return (
        vendor_name,
        vendor_gstin,
        vendor_address,
        vendor_fields,
    )


def reconcile_invoice_parties(
    *,
    buyer_name: str | None,
    buyer_gstin: str | None,
    buyer_address: str | None,
    vendor_fields: dict[str, ParsedField],
) -> tuple[
    str | None,
    str | None,
    str | None,
    dict[str, ParsedField],
]:
    vendor_name = _field_value(
        vendor_fields,
        "vendor_name",
    )
    vendor_gstin = _field_value(
        vendor_fields,
        "vendor_gstin",
    )
    vendor_address = _field_value(
        vendor_fields,
        "vendor_address",
    )
    account_holder = _field_value(
        vendor_fields,
        "account_holder_name",
    )

    if _should_swap_parties(
        buyer_name=buyer_name,
        buyer_gstin=buyer_gstin,
        vendor_name=vendor_name,
        vendor_gstin=vendor_gstin,
    ):
        return _swap_invoice_party_fields(
            buyer_name=buyer_name,
            buyer_gstin=buyer_gstin,
            buyer_address=buyer_address,
            vendor_fields=vendor_fields,
        )

    if (
        vendor_name
        and account_holder
        and not _names_match(
            vendor_name,
            account_holder,
        )
        and (
            not buyer_name
            or _names_match(
                vendor_name,
                buyer_name,
            )
        )
        and not _names_match(
            account_holder,
            buyer_name,
        )
    ):
        resolved_buyer_name = buyer_name or vendor_name
        resolved_buyer_gstin = buyer_gstin or vendor_gstin
        resolved_buyer_address = (
            buyer_address or vendor_address
        )

        _set_field_value(
            vendor_fields,
            "vendor_name",
            account_holder,
        )

        if _names_match(
            vendor_name,
            resolved_buyer_name,
        ):
            _set_field_value(
                vendor_fields,
                "vendor_gstin",
                None,
            )

        return (
            resolved_buyer_name,
            resolved_buyer_gstin,
            resolved_buyer_address,
            vendor_fields,
        )

    return (
        buyer_name,
        buyer_gstin,
        buyer_address,
        vendor_fields,
    )


def reconcile_po_parties(
    *,
    buyer_name: str | None,
    buyer_gstin: str | None,
    vendor_fields: dict[str, ParsedField],
) -> tuple[
    str | None,
    str | None,
    dict[str, ParsedField],
]:
    vendor_name = _field_value(
        vendor_fields,
        "vendor_name",
    )
    vendor_gstin = _field_value(
        vendor_fields,
        "vendor_gstin",
    )

    if _should_swap_parties(
        buyer_name=buyer_name,
        buyer_gstin=buyer_gstin,
        vendor_name=vendor_name,
        vendor_gstin=vendor_gstin,
    ):
        _set_field_value(
            vendor_fields,
            "vendor_name",
            buyer_name,
        )
        _set_field_value(
            vendor_fields,
            "vendor_gstin",
            buyer_gstin,
        )

        return (
            vendor_name,
            vendor_gstin,
            vendor_fields,
        )

    if (
        vendor_name
        and not buyer_name
        and _looks_like_bill_to_party(
            vendor_name,
        )
    ):
        _set_field_value(
            vendor_fields,
            "vendor_name",
            None,
        )
        _set_field_value(
            vendor_fields,
            "vendor_gstin",
            None,
        )

        return (
            vendor_name,
            vendor_gstin,
            vendor_fields,
        )

    return (
        buyer_name,
        buyer_gstin,
        vendor_fields,
    )


def _looks_like_bill_to_party(
    name: str,
) -> bool:
    normalized = _normalize_name(
        name,
    )

    return "payu" in normalized
