import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from src.schemas.invoice_extraction_schema import (
    InvoiceExtractionSchema,
    InvoiceLineItemExtractionSchema,
    InvoiceVendorExtractionSchema,
)
from src.schemas.po_extraction_schema import (
    POExtractionSchema,
    POLineItemExtractionSchema,
)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _parse_json(raw_text: str) -> dict[str, Any]:
    payload = json.loads(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object from Llama extraction")
    return payload


def _build_label_map(items: list[dict[str, Any]] | None) -> dict[str, str]:
    label_map: dict[str, str] = {}

    for item in items or []:
        if not isinstance(item, dict):
            continue

        field_name = item.get("field_name")
        field_value = item.get("field_value")

        if field_name and field_value:
            label_map[_normalize_text(str(field_name))] = str(field_value).strip()

    return label_map


def _lookup_label(label_map: dict[str, str], *candidates: str) -> str | None:
    for candidate in candidates:
        normalized = _normalize_text(candidate)
        if normalized in label_map:
            return label_map[normalized]

    for key, value in label_map.items():
        for candidate in candidates:
            normalized = _normalize_text(candidate)
            if normalized in key or key in normalized:
                return value

    return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None

    try:
        return Decimal(text)
    except Exception:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None

    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value

    text = str(value).strip()
    if not text:
        return None

    for fmt in (
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


def _extract_gstin(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"GSTIN\s*:?\s*([A-Z0-9]{10,20})", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def _extract_email(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE)
    if match:
        return match.group(0).strip("<>")

    return None


def _extract_phone(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"(?:\+?\d[\d\-\s()]{7,}\d)", text)
    if match:
        return match.group(1) if match.lastindex else match.group(0).strip()

    return None


def _extract_account_number(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"Account Number\s*:?\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def _split_bill_to(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None

    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        return None, value

    company_name = parts[0]
    address_parts = parts[1:]
    if address_parts and _extract_gstin(value):
        gstin = _extract_gstin(value)
        address_parts = [part for part in address_parts if gstin not in part]

    return company_name, ", ".join(address_parts) or None


def _parse_invoice_line_items(rows: list[str] | None) -> list[InvoiceLineItemExtractionSchema]:
    line_items: list[InvoiceLineItemExtractionSchema] = []

    for row in rows or []:
        if not isinstance(row, str):
            continue

        cleaned_row = row.strip()
        if not cleaned_row or cleaned_row.startswith("#"):
            continue

        parts = [part.strip() for part in cleaned_row.split("|")]
        if len(parts) < 4:
            continue

        first_part = parts[0]
        match = re.match(r"^(\d+)\s+(.*)$", first_part)
        line_number = int(match.group(1)) if match else None
        description = match.group(2).strip() if match else first_part

        hsn = parts[1] if len(parts) > 1 else None
        quantity = _parse_decimal(parts[2]) if len(parts) > 2 else None
        unit_price = _parse_decimal(parts[3]) if len(parts) > 3 else None
        line_total = _parse_decimal(parts[4]) if len(parts) > 4 else None

        line_items.append(
            InvoiceLineItemExtractionSchema(
                line_number=line_number,
                item_description=description or None,
                hsn_sac_code=hsn or None,
                quantity_billed=quantity,
                unit_price=unit_price,
                line_total=line_total,
            ),
        )

    return line_items


def _parse_po_line_items(rows: list[str] | None) -> list[POLineItemExtractionSchema]:
    line_items: list[POLineItemExtractionSchema] = []

    for row in rows or []:
        if isinstance(row, dict):
            line_items.append(
                POLineItemExtractionSchema(
                    line_number=row.get("line_number"),
                    item_code=str(row.get("item_code")).strip() if row.get("item_code") is not None else None,
                    item_description=str(row.get("item_description")).strip() if row.get("item_description") is not None else None,
                    uom=str(row.get("uom")).strip() if row.get("uom") is not None else None,
                    quantity_ordered=_parse_decimal(row.get("quantity_ordered")),
                    unit_price=_parse_decimal(row.get("unit_price")),
                    discount_amount=_parse_decimal(row.get("discount_amount")),
                    tax_details=row.get("tax_details"),
                    line_total=_parse_decimal(row.get("line_total")),
                ),
            )
            continue

        if not isinstance(row, str):
            continue

        cleaned_row = row.strip()
        if not cleaned_row or cleaned_row.startswith("#"):
            continue

        parts = [part.strip() for part in cleaned_row.split("|")]
        if len(parts) < 4:
            continue

        first_part = parts[0]
        match = re.match(r"^(\d+)\s+(.*)$", first_part)
        line_number = int(match.group(1)) if match else None
        description = match.group(2).strip() if match else first_part

        item_code = None
        uom = None
        quantity_index = 2

        if len(parts) >= 6:
            item_code = parts[1] or None
            uom = parts[2] or None
            quantity_index = 3
        elif len(parts) == 5:
            item_code = parts[1] or None
            quantity_index = 2

        quantity = _parse_decimal(parts[quantity_index]) if len(parts) > quantity_index else None
        unit_price = _parse_decimal(parts[quantity_index + 1]) if len(parts) > quantity_index + 1 else None
        line_total = _parse_decimal(parts[quantity_index + 2]) if len(parts) > quantity_index + 2 else None

        line_items.append(
            POLineItemExtractionSchema(
                line_number=line_number,
                item_code=item_code,
                item_description=description or None,
                uom=uom,
                quantity_ordered=quantity,
                unit_price=unit_price,
                line_total=line_total,
            ),
        )

    return line_items


def _parse_structured_invoice_line_items(
    rows: list[object] | None,
) -> list[InvoiceLineItemExtractionSchema]:
    line_items: list[InvoiceLineItemExtractionSchema] = []

    for row in rows or []:
        if not isinstance(row, dict):
            continue

        line_items.append(
            InvoiceLineItemExtractionSchema(
                line_number=row.get("line_number"),
                item_code=(
                    str(row.get("item_code")).strip()
                    if row.get("item_code") is not None
                    else None
                ),
                item_description=(
                    str(row.get("item_description")).strip()
                    if row.get("item_description") is not None
                    else None
                ),
                uom=(
                    str(row.get("uom")).strip()
                    if row.get("uom") is not None
                    else None
                ),
                quantity_billed=_parse_decimal(
                    row.get("quantity_billed"),
                ),
                unit_price=_parse_decimal(
                    row.get("unit_price"),
                ),
                discount_amount=_parse_decimal(
                    row.get("discount_amount"),
                ),
                tax_details=row.get("tax_details"),
                hsn_sac_code=(
                    str(row.get("hsn_sac_code")).strip()
                    if row.get("hsn_sac_code") is not None
                    else None
                ),
                line_total=_parse_decimal(
                    row.get("line_total"),
                ),
            ),
        )

    return line_items


def _optional_str(
    value: Any,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def parse_structured_invoice_llama_extraction(
    raw_text: str,
) -> InvoiceExtractionSchema:
    payload = _parse_json(raw_text)

    po_numbers = payload.get(
        "po_numbers_extracted",
    )
    if isinstance(
        po_numbers,
        str,
    ):
        po_numbers = [
            po_numbers,
        ]
    elif not isinstance(
        po_numbers,
        list,
    ):
        po_numbers = None

    vendor = InvoiceVendorExtractionSchema(
        vendor_name=_optional_str(
            payload.get("vendor_name"),
        ),
        vendor_gstin=_optional_str(
            payload.get("vendor_gstin"),
        ),
        vendor_address=_optional_str(
            payload.get("vendor_address"),
        ),
        vendor_email=_optional_str(
            payload.get("vendor_email"),
        ),
        vendor_phone=_optional_str(
            payload.get("vendor_phone"),
        ),
        bank_account_number=_optional_str(
            payload.get("bank_account_number"),
        ),
        bank_name=_optional_str(
            payload.get("bank_name"),
        ),
        ifsc_code=_optional_str(
            payload.get("ifsc_code"),
        ),
        account_holder_name=_optional_str(
            payload.get("account_holder_name"),
        ),
    )

    has_vendor = any(
        [
            vendor.vendor_name,
            vendor.vendor_gstin,
            vendor.vendor_address,
            vendor.vendor_email,
            vendor.vendor_phone,
            vendor.bank_account_number,
            vendor.bank_name,
            vendor.ifsc_code,
            vendor.account_holder_name,
        ],
    )

    return InvoiceExtractionSchema(
        invoice_number=_optional_str(
            payload.get("invoice_number"),
        ),
        invoice_date=_parse_date(
            payload.get("invoice_date"),
        ),
        po_numbers_extracted=po_numbers,
        due_date=_parse_date(
            payload.get("due_date"),
        ),
        currency=_optional_str(
            payload.get("currency"),
        )
        or "INR",
        payment_terms=_optional_str(
            payload.get("payment_terms"),
        ),
        subtotal_amount=_parse_decimal(
            payload.get("subtotal_amount"),
        ),
        discount_amount=_parse_decimal(
            payload.get("discount_amount"),
        ),
        tax_amount=_parse_decimal(
            payload.get("tax_amount"),
        ),
        total_amount=_parse_decimal(
            payload.get("total_amount"),
        ),
        notes=_optional_str(
            payload.get("notes"),
        ),
        company_name=_optional_str(
            payload.get("company_name"),
        ),
        company_gstin=_optional_str(
            payload.get("company_gstin"),
        ),
        company_address=_optional_str(
            payload.get("company_address"),
        ),
        vendor=vendor if has_vendor else None,
        line_items=_parse_structured_invoice_line_items(
            payload.get("line_items"),
        ),
    )


def parse_invoice_llama_extraction(raw_text: str) -> InvoiceExtractionSchema:
    payload = _parse_json(raw_text)
    labeled_fields = _build_label_map(payload.get("labeled_fields"))
    payment_details = _build_label_map(payload.get("payment_and_bank_details"))

    bill_to = _lookup_label(labeled_fields, "Bill To")
    ship_to = _lookup_label(labeled_fields, "Ship To")
    vendor_name = _lookup_label(labeled_fields, "Vendor Name")
    vendor_email = _lookup_label(labeled_fields, "Vendor Email") or _extract_email(payload.get("full_document_text", ""))
    vendor_phone = _lookup_label(labeled_fields, "Vendor Phone")
    vendor_gstin = _lookup_label(labeled_fields, "Vendor GSTIN")
    vendor_pan = _lookup_label(labeled_fields, "Vendor PAN")

    company_name, company_address = _split_bill_to(bill_to)
    company_gstin = _extract_gstin(bill_to) or _lookup_label(labeled_fields, "GSTIN")

    subtotal_amount = _parse_decimal(_lookup_label(labeled_fields, "Subtotal"))
    discount_amount = _parse_decimal(_lookup_label(labeled_fields, "Discount"))
    tax_amount = (
        (_parse_decimal(_lookup_label(labeled_fields, "CGST @ 9%")) or Decimal("0"))
        + (_parse_decimal(_lookup_label(labeled_fields, "SGST @ 9%")) or Decimal("0"))
        + (_parse_decimal(_lookup_label(labeled_fields, "IGST")) or Decimal("0"))
    )
    total_amount = _parse_decimal(_lookup_label(labeled_fields, "Total Invoice Value (INR)", "Total Invoice Value", "Grand Total", "Total"))

    bank_name = _lookup_label(payment_details, "Bank Name")
    bank_account_number = _lookup_label(payment_details, "Account Number")
    ifsc_code = _lookup_label(payment_details, "IFSC Code")
    account_holder_name = _lookup_label(payment_details, "Account Holder Name")

    invoice = InvoiceExtractionSchema(
        invoice_number=_lookup_label(labeled_fields, "Invoice No.", "Invoice Number", "Invoice #"),
        invoice_date=_parse_date(_lookup_label(labeled_fields, "Invoice Date")),
        po_numbers_extracted=[value for value in [_lookup_label(labeled_fields, "PO Number")] if value],
        due_date=_parse_date(_lookup_label(labeled_fields, "Due Date")),
        currency=_lookup_label(labeled_fields, "Currency") or "INR",
        payment_terms=_lookup_label(labeled_fields, "Payment Terms"),
        subtotal_amount=subtotal_amount,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        notes=_lookup_label(labeled_fields, "Amount in Words"),
        company_name=company_name,
        company_gstin=company_gstin,
        company_address=company_address,
        vendor=InvoiceVendorExtractionSchema(
            vendor_name=vendor_name,
            vendor_gstin=vendor_gstin,
            vendor_address=_lookup_label(labeled_fields, "Vendor Address") or None,
            vendor_email=vendor_email,
            vendor_phone=vendor_phone,
            bank_account_number=bank_account_number,
            bank_name=bank_name,
            ifsc_code=ifsc_code,
            account_holder_name=account_holder_name,
        ),
        line_items=_parse_invoice_line_items(
            next(
                (
                    table.get("rows")
                    for table in payload.get("tables", [])
                    if _normalize_text(str(table.get("table_name", ""))).find("line item") >= 0
                    or _normalize_text(str(table.get("table_name", ""))).find("invoice") >= 0
                ),
                [],
            ),
        ),
    )

    if vendor_pan and not invoice.vendor.account_holder_name:
        invoice.vendor.account_holder_name = account_holder_name

    return invoice


def parse_po_llama_extraction(raw_text: str) -> POExtractionSchema:
    payload = _parse_json(raw_text)
    labeled_fields = _build_label_map(payload.get("labeled_fields"))

    po_number = (
        _lookup_label(labeled_fields, "PO Number", "Purchase Order No", "Purchase Order #")
        or str(payload.get("po_number") or "").strip() or None
    )
    company_name = (
        _lookup_label(labeled_fields, "Buyer", "Bill To", "Company Name")
        or str(payload.get("company_name") or "").strip() or None
    )
    company_gstin = (
        _extract_gstin(_lookup_label(labeled_fields, "Buyer GSTIN", "Company GSTIN") or "")
        or str(payload.get("company_gstin") or "").strip() or None
    )
    vendor_name = (
        _lookup_label(labeled_fields, "Vendor Name", "Supplier Name")
        or str(payload.get("vendor_name") or "").strip() or None
    )
    vendor_gstin = (
        _extract_gstin(_lookup_label(labeled_fields, "Vendor GSTIN", "Supplier GSTIN") or "")
        or str(payload.get("vendor_gstin") or "").strip() or None
    )
    delivery_address = (
        _lookup_label(labeled_fields, "Delivery Address", "Ship To", "Delivery")
        or str(payload.get("delivery_address") or "").strip() or None
    )
    currency = str(payload.get("currency") or _lookup_label(labeled_fields, "Currency") or "INR").strip() or "INR"
    payment_terms = (
        _lookup_label(labeled_fields, "Payment Terms")
        or str(payload.get("payment_terms") or "").strip() or None
    )
    po_date = _parse_date(_lookup_label(labeled_fields, "PO Date", "Purchase Order Date") or payload.get("po_date"))
    valid_until = _parse_date(_lookup_label(labeled_fields, "Valid Until", "Expiry Date", "PO Valid Until") or payload.get("valid_until"))
    subtotal_amount = _parse_decimal(_lookup_label(labeled_fields, "Subtotal") or payload.get("subtotal_amount"))
    discount_amount = _parse_decimal(_lookup_label(labeled_fields, "Discount") or payload.get("discount_amount"))
    tax_amount = _parse_decimal(_lookup_label(labeled_fields, "Tax", "Tax Amount") or payload.get("tax_amount"))
    total_amount = _parse_decimal(_lookup_label(labeled_fields, "Total", "Grand Total", "Net Amount") or payload.get("total_amount"))

    return POExtractionSchema(
        po_number=po_number,
        company_name=company_name,
        company_gstin=company_gstin,
        vendor_name=vendor_name,
        vendor_gstin=vendor_gstin,
        delivery_address=delivery_address,
        currency=currency,
        payment_terms=payment_terms,
        po_date=po_date,
        valid_until=valid_until,
        subtotal_amount=subtotal_amount,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        line_items=_parse_po_line_items(payload.get("line_items") or next(
            (
                table.get("rows")
                for table in payload.get("tables", [])
                if _normalize_text(str(table.get("table_name", ""))).find("line item") >= 0
                or _normalize_text(str(table.get("table_name", ""))).find("item") >= 0
            ),
            [],
        )),
    )