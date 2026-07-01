from src.utils.extraction_field_utils import ParsedField
from src.utils.party_reconciliation import (
    reconcile_invoice_parties,
    reconcile_po_parties,
)


def _vendor_fields(
  **values: str | None,
) -> dict[str, ParsedField]:
    return {
        key: ParsedField(
            value=value,
            confidence=100.0,
        )
        for key, value in values.items()
    }


def test_reconcile_invoice_swaps_when_vendor_has_payu_and_buyer_has_supplier() -> (
    None
):
    vendor_fields = _vendor_fields(
        vendor_name="PayU Payments Pvt Ltd",
        vendor_gstin="29AABCP1234F1Z5",
        vendor_address="Prestige Tech Park, Bengaluru",
        account_holder_name="Camlin Kokuyo Products Ltd.",
    )

    buyer_name, buyer_gstin, buyer_address, vendor_fields = (
        reconcile_invoice_parties(
            buyer_name="Camlin Kokuyo Products Ltd.",
            buyer_gstin="27AAACC1202R1ZK",
            buyer_address="Camlin House, Mumbai",
            vendor_fields=vendor_fields,
        )
    )

    assert buyer_name == "PayU Payments Pvt Ltd"
    assert buyer_gstin == "29AABCP1234F1Z5"
    assert (
        vendor_fields["vendor_name"].value
        == "Camlin Kokuyo Products Ltd."
    )
    assert (
        vendor_fields["vendor_gstin"].value
        == "27AAACC1202R1ZK"
    )


def test_reconcile_invoice_uses_account_holder_when_vendor_is_payu_only() -> (
    None
):
    vendor_fields = _vendor_fields(
        vendor_name="PayU Payments Pvt Ltd",
        vendor_gstin="29AABCP1234F1Z5",
        vendor_address="Prestige Tech Park, Bengaluru",
        account_holder_name="Reynolds Pens India Pvt. Ltd.",
    )

    buyer_name, buyer_gstin, buyer_address, vendor_fields = (
        reconcile_invoice_parties(
            buyer_name=None,
            buyer_gstin=None,
            buyer_address=None,
            vendor_fields=vendor_fields,
        )
    )

    assert buyer_name == "PayU Payments Pvt Ltd"
    assert buyer_gstin == "29AABCP1234F1Z5"
    assert (
        vendor_fields["vendor_name"].value
        == "Reynolds Pens India Pvt. Ltd."
    )
    assert vendor_fields["vendor_gstin"].value is None


def test_reconcile_po_swaps_when_vendor_has_payu_and_buyer_has_supplier() -> (
    None
):
    vendor_fields = _vendor_fields(
        vendor_name="PayU Payments Pvt Ltd",
        vendor_gstin="29AABCP1234F1Z5",
    )

    buyer_name, buyer_gstin, vendor_fields = reconcile_po_parties(
        buyer_name="Camlin Kokuyo Products Ltd.",
        buyer_gstin="27AAACC1202R1ZK",
        vendor_fields=vendor_fields,
    )

    assert buyer_name == "PayU Payments Pvt Ltd"
    assert buyer_gstin == "29AABCP1234F1Z5"
    assert (
        vendor_fields["vendor_name"].value
        == "Camlin Kokuyo Products Ltd."
    )
    assert (
        vendor_fields["vendor_gstin"].value
        == "27AAACC1202R1ZK"
    )


def test_reconcile_po_moves_payu_from_vendor_to_buyer_when_buyer_missing() -> (
    None
):
    vendor_fields = _vendor_fields(
        vendor_name="PayU Payments Pvt Ltd",
        vendor_gstin="29AABCP1234F1Z5",
    )

    buyer_name, buyer_gstin, vendor_fields = reconcile_po_parties(
        buyer_name=None,
        buyer_gstin=None,
        vendor_fields=vendor_fields,
    )

    assert buyer_name == "PayU Payments Pvt Ltd"
    assert buyer_gstin == "29AABCP1234F1Z5"
    assert vendor_fields["vendor_name"].value is None
