from enum import StrEnum


class DocumentType(
    StrEnum,
):
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    OTHER = "other"
