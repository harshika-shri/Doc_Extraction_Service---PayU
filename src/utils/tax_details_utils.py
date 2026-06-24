from __future__ import annotations

from decimal import Decimal
from typing import Any


def normalize_tax_details(
    tax_details: Any,
) -> dict[str, Any] | None:
    if tax_details is None:
        return None

    if isinstance(
        tax_details,
        dict,
    ):
        return _normalize_tax_dict(
            tax_details,
        )

    if isinstance(
        tax_details,
        list,
    ):
        normalized: dict[str, Any] = {}

        for index, item in enumerate(
            tax_details,
        ):
            if isinstance(
                item,
                dict,
            ):
                tax_name = (
                    item.get(
                        "tax_name",
                    )
                    or item.get(
                        "name",
                    )
                    or item.get(
                        "type",
                    )
                )
                tax_value = (
                    item.get(
                        "tax_value",
                    )
                    or item.get(
                        "value",
                    )
                    or item.get(
                        "rate",
                    )
                    or item.get(
                        "amount",
                    )
                )

                if tax_name is not None:
                    normalized[
                        str(tax_name)
                    ] = _normalize_tax_value(
                        tax_value,
                    )
                elif tax_value is not None:
                    normalized[
                        f"tax_{index + 1}"
                    ] = _normalize_tax_value(
                        tax_value,
                    )

                continue

            if item is not None:
                normalized[
                    f"tax_{index + 1}"
                ] = _normalize_tax_value(
                    item,
                )

        return normalized or None

    return {
        "value": _normalize_tax_value(
            tax_details,
        ),
    }


def _normalize_tax_dict(
    tax_details: dict[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    for key, value in tax_details.items():
        if value is None:
            continue

        if isinstance(
            value,
            dict,
        ):
            tax_name = (
                value.get(
                    "tax_name",
                )
                or value.get(
                    "name",
                )
                or key
            )
            tax_value = (
                value.get(
                    "tax_value",
                )
                or value.get(
                    "value",
                )
                or value.get(
                    "rate",
                )
                or value.get(
                    "amount",
                )
            )
            normalized[
                str(tax_name)
            ] = _normalize_tax_value(
                tax_value,
            )
            continue

        normalized[
            str(key)
        ] = _normalize_tax_value(
            value,
        )

    return normalized or {}


def _normalize_tax_value(
    value: Any,
) -> Any:
    if isinstance(
        value,
        Decimal,
    ):
        return str(value)

    return value
